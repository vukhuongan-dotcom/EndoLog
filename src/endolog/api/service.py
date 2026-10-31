"""Transactional domain service coordinating longitudinal patients, episodes, cases, OCC, and audit chain."""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
from typing import Any

from endolog.clinical.adverse_events import summarize_case_adverse_events
from endolog.clinical.bbps import evaluate_bbps, extract_bbps_segments
from endolog.clinical.quality_metrics import (
    compute_ercp_session_indices,
    is_difficult_cannulation_esge_2016,
)
from endolog.clinical.surveillance_scheduler import build_surveillance_recommendation
from endolog.core.audit import build_audit_entry
from endolog.core.config import EndoLogSettings
from endolog.core.dlp import scan_payload_notes
from endolog.core.persistence import AtomicJsonStore
from endolog.schemas.clinical import (
    CaseCreateRequest,
    CasePhasePatchRequest,
    compute_privacy_initials,
)


class ConcurrencyConflictError(Exception):
    pass


class DuplicateOutpatientConfirmationRequired(Exception):
    def __init__(self, candidates: list[dict[str, Any]]) -> None:
        self.candidates = candidates
        super().__init__("OUTPATIENT_POTENTIAL_DUPLICATE_CONFIRM_REQUIRED")


def _new_uid(prefix: str) -> str:
    ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    return f"{prefix}_{ms:012x}{secrets.token_hex(4)}"


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _mrn_hmac(settings: EndoLogSettings, raw_mrn: str) -> str:
    cleaned = raw_mrn.strip().upper()
    return hmac.new(settings.master_research_key, f"mrn:{cleaned}".encode("utf-8"), hashlib.sha256).hexdigest()


def _mask_mrn(raw_mrn: str | None) -> str | None:
    if not raw_mrn:
        return None
    s = raw_mrn.strip()
    if len(s) <= 4:
        return s
    return f"***{s[-4:]}"


class EndoLogService:
    def __init__(self, settings: EndoLogSettings, store: AtomicJsonStore) -> None:
        self.settings = settings
        self.store = store

    def create_case(
        self,
        req: CaseCreateRequest,
        *,
        actor_username: str,
        actor_role: str,
    ) -> dict[str, Any]:
        raw_dump = req.model_dump()
        scan_payload_notes(raw_dump)

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            patients = state["patients"]
            episodes = state["episodes"]
            cases = state["cases"]
            surveillance = state["surveillance"]
            counters = state["counters"]
            primary_mode = state["settings"].get("colo_guideline_mode", "USMSTF_2020")

            mrn_clean = (req.hospital_mrn or "").strip() or None
            mrn_hash = _mrn_hmac(self.settings, mrn_clean) if mrn_clean else None

            # 1. Resolve or create PatientRecord (OD-04)
            patient_uid = req.patient_uid
            if patient_uid:
                if patient_uid not in patients:
                    raise KeyError(f"Không tìm thấy patient_uid={patient_uid}.")
            elif mrn_hash:
                for p_uid, p_obj in patients.items():
                    if p_obj.get("hospital_mrn_hash") == mrn_hash and p_obj.get("status", "ACTIVE") == "ACTIVE":
                        patient_uid = p_uid
                        break
                if not patient_uid:
                    patient_uid = _new_uid("pat")
                    patients[patient_uid] = {
                        "patient_uid": patient_uid,
                        "full_name": req.full_name.strip(),
                        "privacy_initials": compute_privacy_initials(req.full_name),
                        "birth_year": req.birth_year,
                        "sex": req.sex,
                        "hospital_mrn": mrn_clean,
                        "hospital_mrn_masked": _mask_mrn(mrn_clean),
                        "hospital_mrn_hash": mrn_hash,
                        "status": "ACTIVE",
                        "created_at": now_iso,
                    }
            else:
                # Outpatient without hospital_mrn: NEVER auto-merge on full_name + birth_year!
                norm_target = _normalize_name(req.full_name)
                collisions = [
                    {
                        "patient_uid": p["patient_uid"],
                        "privacy_initials": p["privacy_initials"],
                        "birth_year": p["birth_year"],
                        "sex": p["sex"],
                    }
                    for p in patients.values()
                    if p.get("status", "ACTIVE") == "ACTIVE"
                    and _normalize_name(p.get("full_name", "")) == norm_target
                    and int(p.get("birth_year", 0)) == req.birth_year
                ]
                if collisions and not req.confirm_outpatient_new_patient:
                    raise DuplicateOutpatientConfirmationRequired(collisions)
                patient_uid = _new_uid("pat")
                patients[patient_uid] = {
                    "patient_uid": patient_uid,
                    "full_name": req.full_name.strip(),
                    "privacy_initials": compute_privacy_initials(req.full_name),
                    "birth_year": req.birth_year,
                    "sex": req.sex,
                    "hospital_mrn": None,
                    "hospital_mrn_masked": None,
                    "hospital_mrn_hash": None,
                    "status": "ACTIVE",
                    "created_at": now_iso,
                }

            # 2. Resolve or create AdmissionEpisode
            proc_date = req.procedure_start_at[:10]
            episode_id = req.episode_id
            if episode_id:
                if episode_id not in episodes:
                    raise KeyError(f"Không tìm thấy episode_id={episode_id}.")
            elif req.care_setting == "INPATIENT":
                adm_date = req.admission_date or proc_date
                for ep_id, ep_obj in episodes.items():
                    if (
                        ep_obj.get("patient_uid") == patient_uid
                        and ep_obj.get("care_setting") == "INPATIENT"
                        and ep_obj.get("discharge_date") is None
                    ):
                        episode_id = ep_id
                        break
                if not episode_id:
                    episode_id = _new_uid("epi")
                    episodes[episode_id] = {
                        "episode_id": episode_id,
                        "patient_uid": patient_uid,
                        "care_setting": "INPATIENT",
                        "admission_date": adm_date,
                        "discharge_date": None,
                        "referring_dept": req.referring_dept,
                        "prior_unrecorded_ercp_offset": req.prior_unrecorded_ercp_offset,
                        "created_at": now_iso,
                    }
            else:
                episode_id = _new_uid("epi")
                episodes[episode_id] = {
                    "episode_id": episode_id,
                    "patient_uid": patient_uid,
                    "care_setting": "OUTPATIENT",
                    "admission_date": proc_date,
                    "discharge_date": proc_date,
                    "referring_dept": req.referring_dept,
                    "prior_unrecorded_ercp_offset": 0,
                    "created_at": now_iso,
                }

            # 3. Generate deterministic case_code
            proc_year = req.procedure_start_at[:4]
            counter_key = f"{req.track}-{proc_year}"
            next_num = int(counters.get(counter_key, 0)) + 1
            counters[counter_key] = next_num
            case_code = f"{counter_key}-{next_num:04d}"
            case_id = _new_uid("cas")

            case_record: dict[str, Any] = {
                "case_id": case_id,
                "case_code": case_code,
                "patient_uid": patient_uid,
                "episode_id": episode_id,
                "track": req.track,
                "care_setting": req.care_setting,
                "procedure_start_at": req.procedure_start_at,
                "created_at": now_iso,
                "updated_at": now_iso,
                "operator_name": req.operator_name,
                "indication": req.indication,
                "indication_detail": req.indication_detail,
                "has_ibd_or_polyposis": req.has_ibd_or_polyposis,
                "exclude_from_cir": req.exclude_from_cir,
                "prior_unrecorded_ercp_offset": req.prior_unrecorded_ercp_offset,
                "bbps_right": req.bbps_right,
                "bbps_transverse": req.bbps_transverse,
                "bbps_left": req.bbps_left,
                "cecal_intubation": req.cecal_intubation,
                "cecal_failure_reason": req.cecal_failure_reason,
                "withdrawal_time_clean_min": req.withdrawal_time_clean_min,
                "pathology_completion_status": req.pathology_completion_status,
                "followup_30d_status": req.followup_30d_status,
                "clinician_followup_due_date": req.clinician_followup_due_date,
                "clinician_followup_note": req.clinician_followup_note,
                "index_lesion": req.index_lesion.model_dump() if req.index_lesion else None,
                "whole_case_summary": req.whole_case_summary.model_dump() if req.whole_case_summary else None,
                "ercp_detail": req.ercp_detail.model_dump() if req.ercp_detail else None,
                "adverse_events": [ev.model_dump() for ev in req.adverse_events],
                "clinical_note": req.clinical_note,
                "version": 1,
                "record_status": "ACTIVE",
            }
            cases[case_id] = case_record

            rec = build_surveillance_recommendation(case_record, primary_colo_mode=primary_mode)
            rec["rec_id"] = f"rec_{case_id}"
            surveillance[case_id] = rec

            state["audit_chain"].append(
                build_audit_entry(
                    state["audit_chain"],
                    actor_username=actor_username,
                    actor_role=actor_role,
                    action="CASE_CREATE",
                    entity_type="ENDOSCOPY_CASE",
                    entity_id=case_id,
                    detail={"case_code": case_code, "track": req.track, "version": 1},
                    now_utc=now_iso,
                )
            )
            return self._enrich_case(case_record, state)

        return self.store.transact(_mutator)

    def patch_case(
        self,
        case_id: str,
        patch: CasePhasePatchRequest,
        *,
        actor_username: str,
        actor_role: str,
    ) -> dict[str, Any]:
        raw_dump = patch.model_dump(exclude_none=True)
        scan_payload_notes(raw_dump)

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            cases = state["cases"]
            if case_id not in cases or cases[case_id].get("record_status") != "ACTIVE":
                raise KeyError(f"Không tìm thấy hồ sơ ca nội soi {case_id}.")
            rec_case = cases[case_id]
            if int(rec_case["version"]) != int(patch.expected_version):
                raise ConcurrencyConflictError(
                    f"Xung đột phiên bản OCC: máy chủ đang ở v{rec_case['version']}, yêu cầu gửi v{patch.expected_version}."
                )

            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            changed_fields: list[str] = []
            for field_name in (
                "pathology_completion_status",
                "followup_30d_status",
                "clinician_followup_due_date",
                "clinician_followup_note",
                "bbps_right",
                "bbps_transverse",
                "bbps_left",
                "cecal_intubation",
                "withdrawal_time_clean_min",
                "clinical_note",
            ):
                val = getattr(patch, field_name)
                if val is not None:
                    rec_case[field_name] = val
                    changed_fields.append(field_name)

            if patch.index_lesion is not None:
                rec_case["index_lesion"] = patch.index_lesion.model_dump()
                changed_fields.append("index_lesion")
            if patch.whole_case_summary is not None:
                rec_case["whole_case_summary"] = patch.whole_case_summary.model_dump()
                changed_fields.append("whole_case_summary")
            if patch.ercp_detail is not None:
                rec_case["ercp_detail"] = patch.ercp_detail.model_dump()
                changed_fields.append("ercp_detail")
            if patch.adverse_events is not None:
                rec_case["adverse_events"] = [ev.model_dump() for ev in patch.adverse_events]
                changed_fields.append("adverse_events")

            rec_case["version"] = int(rec_case["version"]) + 1
            rec_case["updated_at"] = now_iso

            primary_mode = state["settings"].get("colo_guideline_mode", "USMSTF_2020")
            existing_surv = state["surveillance"].get(case_id) or {}
            rebuilt = build_surveillance_recommendation(rec_case, primary_colo_mode=primary_mode)
            rebuilt["rec_id"] = existing_surv.get("rec_id") or f"rec_{case_id}"
            if existing_surv.get("fulfilled_by_case_id"):
                rebuilt["fulfilled_by_case_id"] = existing_surv["fulfilled_by_case_id"]
                rebuilt["status"] = "COMPLETED_LINKED"
            state["surveillance"][case_id] = rebuilt

            if patch.fulfill_surveillance_rec_id:
                for origin_cid, s_obj in state["surveillance"].items():
                    if s_obj.get("rec_id") == patch.fulfill_surveillance_rec_id or origin_cid == patch.fulfill_surveillance_rec_id:
                        s_obj["fulfilled_by_case_id"] = case_id
                        s_obj["status"] = "COMPLETED_LINKED"
                        changed_fields.append("fulfill_surveillance_link")

            state["audit_chain"].append(
                build_audit_entry(
                    state["audit_chain"],
                    actor_username=actor_username,
                    actor_role=actor_role,
                    action="CASE_PATCH_PHASE",
                    entity_type="ENDOSCOPY_CASE",
                    entity_id=case_id,
                    detail={
                        "case_code": rec_case["case_code"],
                        "new_version": rec_case["version"],
                        "changed_fields": changed_fields,
                    },
                    now_utc=now_iso,
                )
            )
            return self._enrich_case(rec_case, state)

        return self.store.transact(_mutator)

    def supersede_case(self, case_id: str, *, actor_username: str, actor_role: str) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền hủy hiệu lực hồ sơ ca soi.")

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            if case_id not in state["cases"]:
                raise KeyError(case_id)
            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            c = state["cases"][case_id]
            c["record_status"] = "SUPERSEDED"
            c["version"] = int(c["version"]) + 1
            c["updated_at"] = now_iso
            state["audit_chain"].append(
                build_audit_entry(
                    state["audit_chain"],
                    actor_username=actor_username,
                    actor_role=actor_role,
                    action="CASE_SUPERSEDE",
                    entity_type="ENDOSCOPY_CASE",
                    entity_id=case_id,
                    detail={"case_code": c["case_code"]},
                    now_utc=now_iso,
                )
            )
            return {"case_id": case_id, "record_status": "SUPERSEDED"}

        return self.store.transact(_mutator)

    def list_enriched_cases(self, *, track: str | None = None) -> list[dict[str, Any]]:
        snap = self.store.read_snapshot()
        active_cases = [
            c for c in snap["cases"].values() if c.get("record_status", "ACTIVE") == "ACTIVE"
        ]
        ercp_map = compute_ercp_session_indices(active_cases, snap.get("episodes"))
        out = []
        for c in active_cases:
            if track and c.get("track") != track:
                continue
            out.append(self._enrich_case(c, snap, ercp_map=ercp_map))
        out.sort(key=lambda x: (x.get("procedure_start_at") or "", x.get("case_code") or ""), reverse=True)
        return out

    def _enrich_case(
        self,
        case: dict[str, Any],
        state: dict[str, Any],
        *,
        ercp_map: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        pat = state["patients"].get(case["patient_uid"]) or {}
        epi = state["episodes"].get(case["episode_id"]) or {}
        if ercp_map is None:
            active_cases = [
                c for c in state["cases"].values() if c.get("record_status", "ACTIVE") == "ACTIVE"
            ]
            ercp_map = compute_ercp_session_indices(active_cases, state.get("episodes"))

        segs = extract_bbps_segments(case)
        bbps_info = (
            evaluate_bbps(segs[0], segs[1], segs[2], cecal_intubation=case.get("cecal_intubation") or "NA")
            if segs
            else {"evaluable": False, "segments": None, "total": None, "adequate": False}
        )
        ae_info = summarize_case_adverse_events(case)
        primary_mode = state["settings"].get("colo_guideline_mode", "USMSTF_2020")
        surv = build_surveillance_recommendation(case, primary_colo_mode=primary_mode)
        stored_surv = state.get("surveillance", {}).get(case["case_id"]) or {}
        if stored_surv.get("fulfilled_by_case_id"):
            surv["fulfilled_by_case_id"] = stored_surv["fulfilled_by_case_id"]
            surv["status"] = "COMPLETED_LINKED"
        surv["rec_id"] = stored_surv.get("rec_id") or f"rec_{case['case_id']}"

        ercp_extra = None
        if case["track"] == "ERCP" and case.get("ercp_detail"):
            det = case["ercp_detail"]
            diff = is_difficult_cannulation_esge_2016(
                det.get("papilla_status", "NATIVE_INTACT"),
                int(det.get("cannulation_contacts_count") or 0),
                float(det.get("cannulation_time_min") or 0.0),
                int(det.get("unintended_pd_count") or 0),
            )
            ercp_extra = {
                **det,
                "difficult_cannulation_esge2016": diff,
                "ercp_session_index_in_episode": ercp_map.get(case["case_id"], 1),
            }

        proc_year = int((case.get("procedure_start_at") or "2026")[:4])
        birth_year = int(pat.get("birth_year") or proc_year)
        age = max(0, proc_year - birth_year)

        # Compute primary clinical status badge semantic key (--clinical-*) with Vietnamese label
        pep_severity_vi = {
            "MILD": "mức nhẹ",
            "MODERATE": "mức vừa",
            "SEVERE": "mức nặng",
        }
        has_recorded_ae = bool(
            ae_info["is_agree_any"]
            or ae_info["has_pep"]
            or ae_info["followup_30d_status"] == "COMPLETED_WITH_AE"
        )
        if surv["category"] == "SURGICAL_MDT_CONSULT_ALERT" or has_recorded_ae:
            clinical_badge_key = "urgent"
            if surv["category"] == "SURGICAL_MDT_CONSULT_ALERT":
                clinical_badge_label = f"Cảnh báo hội chẩn {surv['surgical_consult_target_dept']}"
            elif ae_info["highest_agree_grade"] != "NONE":
                if ae_info["has_pep"]:
                    pep_sev_txt = pep_severity_vi.get(str(ae_info["highest_pep_severity"]), "ghi nhận")
                    clinical_badge_label = f"Viêm tụy sau ERCP {pep_sev_txt} · AGREE {ae_info['highest_agree_grade']}"
                else:
                    clinical_badge_label = f"Biến cố AGREE {ae_info['highest_agree_grade']}"
            elif ae_info["has_pep"]:
                pep_sev_txt = pep_severity_vi.get(str(ae_info["highest_pep_severity"]), "ghi nhận")
                clinical_badge_label = f"Viêm tụy sau ERCP {pep_sev_txt} (chưa phân độ AGREE)"
            else:
                clinical_badge_label = "Có biến cố sau thủ thuật (chưa phân độ AGREE)"
        elif case.get("pathology_completion_status") in ("PENDING", "PARTIAL"):
            clinical_badge_key = "pending"
            clinical_badge_label = "Chờ GPB"
        elif ae_info["followup_30d_status"] == "PENDING_WINDOW":
            clinical_badge_key = "due"
            clinical_badge_label = "Theo dõi 14–30 ngày"
        elif ae_info["followup_30d_status"] == "LOST_TO_FOLLOWUP":
            clinical_badge_key = "neutral"
            clinical_badge_label = "Mất dấu theo dõi"
        else:
            clinical_badge_key = "ned"
            clinical_badge_label = "Không biến cố / hoàn tất"

        return {
            **case,
            "etag": f'W/"v{case["version"]}"',
            "patient": {
                "patient_uid": pat.get("patient_uid"),
                "full_name": pat.get("full_name"),
                "privacy_initials": pat.get("privacy_initials"),
                "birth_year": birth_year,
                "age": age,
                "sex": pat.get("sex"),
                "hospital_mrn_masked": pat.get("hospital_mrn_masked"),
            },
            "episode": {
                "episode_id": epi.get("episode_id"),
                "care_setting": epi.get("care_setting"),
                "referring_dept": epi.get("referring_dept"),
            },
            "bbps": bbps_info,
            "adverse_summary": ae_info,
            "ercp_computed": ercp_extra,
            "surveillance": surv,
            "clinical_badge": {
                "tone": clinical_badge_key,
                "label": clinical_badge_label,
            },
        }
