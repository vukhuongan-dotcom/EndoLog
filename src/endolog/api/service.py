"""Transactional domain service coordinating longitudinal patients, episodes, cases, OCC, Superadmin governance, and audit chain."""

from __future__ import annotations

import base64
import copy
import datetime as dt
import hashlib
import hmac
import json
import secrets
from typing import Any

from endolog.clinical.adverse_events import summarize_case_adverse_events
from endolog.clinical.bbps import evaluate_bbps, extract_bbps_segments
from endolog.clinical.export_profiles import (
    MAX_VAULT_BLOB_BYTES,
    VaultPayloadTooLargeError,
    VaultSchemaValidationError,
    decrypt_profile_a_vault,
    validate_restored_vault_domain,
)
from endolog.clinical.quality_metrics import (
    compute_ercp_session_indices,
    is_difficult_cannulation_esge_2016,
)
from endolog.clinical.surveillance_scheduler import build_surveillance_recommendation
from endolog.core.audit import build_audit_entry, verify_audit_chain
from endolog.core.config import EndoLogSettings
from endolog.core.dlp import scan_payload_notes
from endolog.core.persistence import AtomicJsonStore, normalize_state_compat
from endolog.core.security import hash_password, verify_password
from endolog.schemas.clinical import (
    AdminPasswordResetRequest,
    CaseCreateRequest,
    CasePhasePatchRequest,
    EpisodeReconcileRequest,
    PasswordChangeRequest,
    PatientMergeRequest,
    ProfileARestoreRequest,
    compute_privacy_initials,
)


class ConcurrencyConflictError(Exception):
    pass


class DomainConflictError(Exception):
    """Domain-level HTTP 409 conflict with structured code and optional metadata."""

    def __init__(self, code: str, message: str, extra: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.extra = extra or {}
        super().__init__(message)


class DomainValidationError(Exception):
    """Domain-level HTTP 422 validation error with structured code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class InvalidPasswordError(Exception):
    """Domain-level HTTP 400 error when current password verification fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


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


def _sanitize_user(user_obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "username": user_obj["username"],
        "display_name": user_obj["display_name"],
        "role": user_obj["role"],
        "department": user_obj["department"],
        "active": bool(user_obj.get("active", True)),
        "auth_version": int(user_obj.get("auth_version", 1) or 1),
        "created_at": user_obj.get("created_at"),
        "password_updated_at": user_obj.get("password_updated_at"),
    }


def _find_active_patient_by_mrn_hash(patients: dict[str, dict[str, Any]], mrn_hash: str) -> str | None:
    for p_uid, p_obj in patients.items():
        if p_obj.get("status", "ACTIVE") != "ACTIVE":
            continue
        if p_obj.get("hospital_mrn_hash") == mrn_hash or mrn_hash in (p_obj.get("secondary_mrn_hashes") or []):
            return p_uid
    return None


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

            # 1. Resolve or create PatientRecord (OD-04 + G05 post-merge write guard)
            patient_uid = req.patient_uid
            if patient_uid:
                if patient_uid not in patients:
                    raise DomainValidationError(
                        "PATIENT_NOT_FOUND",
                        f"Không tìm thấy hồ sơ người bệnh {patient_uid}.",
                    )
                p_existing = patients[patient_uid]
                if p_existing.get("status", "ACTIVE") != "ACTIVE":
                    canonical_uid = p_existing.get("merged_into_patient_uid")
                    raise DomainConflictError(
                        "PATIENT_MERGED_SUPERSEDED",
                        "Hồ sơ người bệnh này đã được gộp sang hồ sơ chính; không thể thêm ca mới vào định danh cũ.",
                        extra={
                            "canonical_patient_uid": canonical_uid,
                            "merged_into_patient_uid": canonical_uid,
                        },
                    )
                if mrn_clean and mrn_hash:
                    owner_uid = _find_active_patient_by_mrn_hash(patients, mrn_hash)
                    if owner_uid and owner_uid != patient_uid:
                        raise DomainConflictError(
                            "MRN_BELONGS_TO_OTHER_PATIENT",
                            "Mã hồ sơ bệnh viện đã gắn với một người bệnh đang hoạt động khác.",
                            extra={"conflicting_patient_uid": owner_uid},
                        )
                    if not p_existing.get("hospital_mrn_hash"):
                        p_existing["hospital_mrn"] = mrn_clean
                        p_existing["hospital_mrn_masked"] = _mask_mrn(mrn_clean)
                        p_existing["hospital_mrn_hash"] = mrn_hash
                        p_existing["version"] = int(p_existing.get("version", 1)) + 1
                        p_existing["updated_at"] = now_iso
            elif mrn_hash:
                patient_uid = _find_active_patient_by_mrn_hash(patients, mrn_hash)
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
                        "version": 1,
                        "secondary_mrn_hashes": [],
                        "secondary_mrns": [],
                        "merged_from_aliases": [],
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
                    "version": 1,
                    "secondary_mrn_hashes": [],
                    "secondary_mrns": [],
                    "merged_from_aliases": [],
                    "created_at": now_iso,
                }

            # 2. Resolve or create AdmissionEpisode (G05 ownership & superseded checks)
            proc_date = req.procedure_start_at[:10]
            episode_id = req.episode_id
            if episode_id:
                if episode_id not in episodes:
                    raise DomainValidationError(
                        "EPISODE_NOT_FOUND",
                        f"Không tìm thấy đợt điều trị {episode_id}.",
                    )
                ep_existing = episodes[episode_id]
                if ep_existing.get("status", "ACTIVE") != "ACTIVE":
                    canonical_ep = ep_existing.get("merged_into_episode_id")
                    raise DomainConflictError(
                        "EPISODE_SUPERSEDED",
                        "Đợt điều trị này đã được hợp nhất sang đợt đích; không thể gắn ca mới vào đợt cũ.",
                        extra={
                            "canonical_episode_id": canonical_ep,
                            "merged_into_episode_id": canonical_ep,
                        },
                    )
                if ep_existing.get("patient_uid") != patient_uid:
                    raise DomainValidationError(
                        "EPISODE_PATIENT_MISMATCH",
                        "Đợt điều trị được chọn thuộc về một người bệnh khác.",
                    )
                if ep_existing.get("care_setting") != req.care_setting:
                    raise DomainValidationError(
                        "EPISODE_CARE_SETTING_MISMATCH",
                        "Loại hình điều trị của ca không khớp với đợt điều trị được chọn.",
                    )
            elif req.care_setting == "INPATIENT":
                adm_date = req.admission_date or proc_date
                for ep_id, ep_obj in episodes.items():
                    if (
                        ep_obj.get("status", "ACTIVE") == "ACTIVE"
                        and ep_obj.get("patient_uid") == patient_uid
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
                        "status": "ACTIVE",
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
                    "status": "ACTIVE",
                    "created_at": now_iso,
                }

            # Verify surveillance link ownership before mutating cases
            matched_surv_origin_cid: str | None = None
            if req.fulfill_surveillance_rec_id:
                for origin_cid, s_obj in surveillance.items():
                    if s_obj.get("rec_id") == req.fulfill_surveillance_rec_id or origin_cid == req.fulfill_surveillance_rec_id:
                        origin_case = cases.get(origin_cid)
                        if not origin_case or origin_case.get("patient_uid") != patient_uid:
                            raise DomainValidationError(
                                "SURVEILLANCE_PATIENT_MISMATCH",
                                "Lịch hẹn soi lại được liên kết không thuộc cùng người bệnh.",
                            )
                        matched_surv_origin_cid = origin_cid
                        break
                if matched_surv_origin_cid is None:
                    raise DomainValidationError(
                        "SURVEILLANCE_REC_NOT_FOUND",
                        "Không tìm thấy bản ghi hẹn soi lại cần liên kết.",
                    )

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

            if matched_surv_origin_cid and matched_surv_origin_cid != case_id:
                surveillance[matched_surv_origin_cid]["fulfilled_by_case_id"] = case_id
                surveillance[matched_surv_origin_cid]["status"] = "COMPLETED_LINKED"

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
        if_match_epoch: int | None = None,
    ) -> dict[str, Any]:
        raw_dump = patch.model_dump(exclude_none=True)
        scan_payload_notes(raw_dump)

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            state_epoch = int(state.get("store_epoch", 1) or 1)
            if state_epoch > 1 and if_match_epoch is None and patch.expected_store_epoch is None:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Kho dữ liệu đang ở thế hệ e{state_epoch}; yêu cầu cập nhật bắt buộc gửi kèm ETag hoặc expected_store_epoch.",
                    extra={"current_store_epoch": state_epoch},
                )
            if if_match_epoch is not None and int(if_match_epoch) != state_epoch:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Xung đột thế hệ kho OCC: máy chủ đang ở e{state_epoch}, header If-Match gửi e{if_match_epoch}.",
                    extra={"current_store_epoch": state_epoch},
                )
            if patch.expected_store_epoch is not None and int(patch.expected_store_epoch) != state_epoch:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Xung đột thế hệ kho OCC: máy chủ đang ở e{state_epoch}, yêu cầu gửi e{patch.expected_store_epoch}.",
                    extra={"current_store_epoch": state_epoch},
                )

            cases = state["cases"]
            if case_id not in cases or cases[case_id].get("record_status") != "ACTIVE":
                raise KeyError(f"Không tìm thấy hồ sơ ca nội soi {case_id}.")
            rec_case = cases[case_id]

            pat_obj = state["patients"].get(rec_case["patient_uid"])
            if not pat_obj or pat_obj.get("status", "ACTIVE") != "ACTIVE":
                canonical_uid = (pat_obj or {}).get("merged_into_patient_uid")
                raise DomainConflictError(
                    "PATIENT_MERGED_SUPERSEDED",
                    "Hồ sơ người bệnh của ca này đã chuyển trạng thái gộp; vui lòng tải lại danh sách.",
                    extra={
                        "canonical_patient_uid": canonical_uid,
                        "merged_into_patient_uid": canonical_uid,
                    },
                )
            epi_obj = state["episodes"].get(rec_case["episode_id"])
            if not epi_obj or epi_obj.get("status", "ACTIVE") != "ACTIVE":
                canonical_ep = (epi_obj or {}).get("merged_into_episode_id")
                raise DomainConflictError(
                    "EPISODE_SUPERSEDED",
                    "Đợt điều trị của ca này đã chuyển trạng thái hợp nhất; vui lòng tải lại danh sách.",
                    extra={
                        "canonical_episode_id": canonical_ep,
                        "merged_into_episode_id": canonical_ep,
                    },
                )
            if epi_obj.get("patient_uid") != rec_case["patient_uid"]:
                raise DomainValidationError(
                    "EPISODE_PATIENT_MISMATCH",
                    "Đợt điều trị không thuộc cùng người bệnh của ca nội soi.",
                )

            if int(rec_case["version"]) != int(patch.expected_version):
                raise ConcurrencyConflictError(
                    f"Xung đột phiên bản OCC: máy chủ đang ở v{rec_case['version']}, yêu cầu gửi v{patch.expected_version}."
                )

            matched_surv_origin_cid: str | None = None
            if patch.fulfill_surveillance_rec_id:
                for origin_cid, s_obj in state["surveillance"].items():
                    if s_obj.get("rec_id") == patch.fulfill_surveillance_rec_id or origin_cid == patch.fulfill_surveillance_rec_id:
                        origin_case = cases.get(origin_cid)
                        if (
                            origin_cid == case_id
                            or not origin_case
                            or origin_case.get("patient_uid") != rec_case["patient_uid"]
                        ):
                            raise DomainValidationError(
                                "SURVEILLANCE_PATIENT_MISMATCH",
                                "Liên kết hẹn soi lại không hợp lệ hoặc khác người bệnh.",
                            )
                        matched_surv_origin_cid = origin_cid
                        break
                if matched_surv_origin_cid is None:
                    raise DomainValidationError(
                        "SURVEILLANCE_REC_NOT_FOUND",
                        "Không tìm thấy bản ghi hẹn soi lại cần liên kết.",
                    )

            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            changed_fields: list[str] = []
            for field_name in (
                "procedure_start_at",
                "prior_unrecorded_ercp_offset",
                "indication",
                "indication_detail",
                "has_ibd_or_polyposis",
                "exclude_from_cir",
                "pathology_completion_status",
                "followup_30d_status",
                "clinician_followup_due_date",
                "clinician_followup_note",
                "bbps_right",
                "bbps_transverse",
                "bbps_left",
                "cecal_intubation",
                "cecal_failure_reason",
                "withdrawal_time_clean_min",
                "clinical_note",
            ):
                val = getattr(patch, field_name)
                if val is not None:
                    rec_case[field_name] = val
                    changed_fields.append(field_name)

            if patch.referring_dept is not None:
                epi_obj["referring_dept"] = patch.referring_dept
                changed_fields.append("referring_dept")
            if patch.prior_unrecorded_ercp_offset is not None and epi_obj.get("care_setting") == "INPATIENT":
                epi_obj["prior_unrecorded_ercp_offset"] = patch.prior_unrecorded_ercp_offset

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

            if matched_surv_origin_cid:
                state["surveillance"][matched_surv_origin_cid]["fulfilled_by_case_id"] = case_id
                state["surveillance"][matched_surv_origin_cid]["status"] = "COMPLETED_LINKED"
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

    def supersede_case(
        self,
        case_id: str,
        *,
        actor_username: str,
        actor_role: str,
        if_match_epoch: int | None = None,
        if_match_version: int | None = None,
    ) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền hủy hiệu lực hồ sơ ca soi.")

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            state_epoch = int(state.get("store_epoch", 1) or 1)
            if state_epoch > 1 and if_match_epoch is None:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Kho dữ liệu đang ở thế hệ e{state_epoch}; yêu cầu hủy hiệu lực bắt buộc gửi kèm header If-Match.",
                    extra={"current_store_epoch": state_epoch},
                )
            if if_match_epoch is not None and int(if_match_epoch) != state_epoch:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Xung đột thế hệ kho OCC: máy chủ đang ở e{state_epoch}, header If-Match gửi e{if_match_epoch}.",
                    extra={"current_store_epoch": state_epoch},
                )
            if case_id not in state["cases"]:
                raise KeyError(case_id)
            c = state["cases"][case_id]
            if if_match_version is not None and int(if_match_version) != int(c["version"]):
                raise ConcurrencyConflictError(
                    f"Xung đột phiên bản OCC khi hủy hiệu lực: máy chủ đang ở v{c['version']}, header If-Match gửi v{if_match_version}."
                )
            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
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
                    detail={"case_code": c["case_code"], "store_epoch": state_epoch},
                    now_utc=now_iso,
                )
            )
            return {
                "case_id": case_id,
                "record_status": "SUPERSEDED",
                "store_epoch": state_epoch,
                "version": c["version"],
            }

        return self.store.transact(_mutator)

    # -------------------------------------------------------------------------
    # Phase 4C (v0.3.0): Auth / Password Management (G01)
    # -------------------------------------------------------------------------
    def change_own_password(
        self,
        *,
        actor_username: str,
        req: PasswordChangeRequest,
    ) -> dict[str, Any]:
        if req.new_password == req.current_password:
            raise DomainValidationError(
                "PASSWORD_UNCHANGED",
                "Mật khẩu mới phải khác mật khẩu hiện tại.",
            )

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            user = state["users"].get(actor_username)
            if not user or not user.get("active"):
                raise KeyError(actor_username)
            if not verify_password(user["password_hash"], req.current_password):
                raise InvalidPasswordError(
                    "INVALID_CURRENT_PASSWORD",
                    "Mật khẩu hiện tại không chính xác.",
                )
            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            user["password_hash"] = hash_password(req.new_password)
            user["auth_version"] = int(user.get("auth_version", 1) or 1) + 1
            user["password_updated_at"] = now_iso
            state["audit_chain"].append(
                build_audit_entry(
                    state["audit_chain"],
                    actor_username=user["username"],
                    actor_role=user["role"],
                    action="AUTH_PASSWORD_CHANGED",
                    entity_type="USER_ACCOUNT",
                    entity_id=user["username"],
                    detail={"new_auth_version": user["auth_version"]},
                    now_utc=now_iso,
                )
            )
            return {
                "user": _sanitize_user(user),
                "store_epoch": int(state.get("store_epoch", 1) or 1),
            }

        return self.store.transact(_mutator)

    def list_users_sanitized(self, *, actor_role: str) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) được xem danh sách tài khoản hệ thống.")
        snap = self.store.read_snapshot()
        items = [_sanitize_user(u) for u in snap.get("users", {}).values()]
        items.sort(key=lambda x: (0 if x["role"] == "superadmin" else 1, x["username"]))
        return {
            "store_epoch": int(snap.get("store_epoch", 1) or 1),
            "items": items,
            "total": len(items),
        }

    def admin_reset_user_password(
        self,
        target_username: str,
        req: AdminPasswordResetRequest,
        *,
        actor_username: str,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền đặt lại mật khẩu tài khoản.")
        scan_payload_notes({"reason": req.reason})

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            target_key = target_username.strip()
            target_user = state["users"].get(target_key)
            if not target_user:
                raise KeyError(target_key)
            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            target_user["password_hash"] = hash_password(req.new_password)
            target_user["auth_version"] = int(target_user.get("auth_version", 1) or 1) + 1
            target_user["password_updated_at"] = now_iso
            state["audit_chain"].append(
                build_audit_entry(
                    state["audit_chain"],
                    actor_username=actor_username,
                    actor_role=actor_role,
                    action="SUPERADMIN_PASSWORD_RESET",
                    entity_type="USER_ACCOUNT",
                    entity_id=target_user["username"],
                    detail={
                        "target_username": target_user["username"],
                        "new_auth_version": target_user["auth_version"],
                    },
                    now_utc=now_iso,
                )
            )
            return {
                "target_user": _sanitize_user(target_user),
                "store_epoch": int(state.get("store_epoch", 1) or 1),
                "actor_self_reset": target_user["username"] == actor_username,
            }

        return self.store.transact(_mutator)

    # -------------------------------------------------------------------------
    # Phase 4C (v0.3.0): Patient Merge & Episode Reconciliation (G05)
    # -------------------------------------------------------------------------
    def list_admin_patients(self, *, actor_role: str) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) được truy cập danh mục quản trị người bệnh.")
        snap = self.store.read_snapshot()
        patients_map = snap.get("patients", {})
        episodes_map = snap.get("episodes", {})
        cases_map = snap.get("cases", {})

        active_cases_by_pat: dict[str, list[dict[str, Any]]] = {}
        active_cases_by_ep: dict[str, list[dict[str, Any]]] = {}
        for c in cases_map.values():
            if c.get("record_status", "ACTIVE") != "ACTIVE":
                continue
            active_cases_by_pat.setdefault(c["patient_uid"], []).append(c)
            active_cases_by_ep.setdefault(c["episode_id"], []).append(c)

        eps_by_pat: dict[str, list[dict[str, Any]]] = {}
        for ep in episodes_map.values():
            if ep.get("status", "ACTIVE") != "ACTIVE":
                continue
            ep_cases = sorted(
                active_cases_by_ep.get(ep["episode_id"], []),
                key=lambda x: (x.get("procedure_start_at") or "", x.get("case_code") or ""),
            )
            eps_by_pat.setdefault(ep["patient_uid"], []).append(
                {
                    "episode_id": ep["episode_id"],
                    "care_setting": ep.get("care_setting", "OUTPATIENT"),
                    "admission_date": ep.get("admission_date"),
                    "discharge_date": ep.get("discharge_date"),
                    "referring_dept": ep.get("referring_dept"),
                    "prior_unrecorded_ercp_offset": int(ep.get("prior_unrecorded_ercp_offset", 0) or 0),
                    "status": ep.get("status", "ACTIVE"),
                    "active_case_ids": [c["case_id"] for c in ep_cases],
                    "case_codes": [c["case_code"] for c in ep_cases],
                    "ercp_case_count": sum(1 for c in ep_cases if c.get("track") == "ERCP"),
                }
            )

        active_items: list[dict[str, Any]] = []
        superseded_count = 0
        dup_buckets: dict[str, list[str]] = {}
        for p_uid, p_obj in patients_map.items():
            if p_obj.get("status", "ACTIVE") != "ACTIVE":
                superseded_count += 1
                continue
            p_cases = sorted(
                active_cases_by_pat.get(p_uid, []),
                key=lambda x: (x.get("procedure_start_at") or "", x.get("case_code") or ""),
            )
            p_eps = sorted(
                eps_by_pat.get(p_uid, []),
                key=lambda x: (x.get("admission_date") or "", x["episode_id"]),
            )
            inpatient_ep_count = sum(1 for e in p_eps if e["care_setting"] == "INPATIENT")
            item = {
                "patient_uid": p_uid,
                "full_name": p_obj.get("full_name"),
                "privacy_initials": p_obj.get("privacy_initials"),
                "birth_year": int(p_obj.get("birth_year") or 0),
                "sex": p_obj.get("sex"),
                "hospital_mrn_masked": p_obj.get("hospital_mrn_masked"),
                "has_hospital_mrn": bool(p_obj.get("hospital_mrn_hash")),
                "secondary_mrn_count": len(p_obj.get("secondary_mrn_hashes") or []),
                "merged_alias_count": len(p_obj.get("merged_from_aliases") or []),
                "version": int(p_obj.get("version", 1) or 1),
                "status": "ACTIVE",
                "active_case_ids": [c["case_id"] for c in p_cases],
                "case_codes": [c["case_code"] for c in p_cases],
                "episodes": p_eps,
                "inpatient_episode_count": inpatient_ep_count,
            }
            active_items.append(item)
            bucket_key = f"{_normalize_name(p_obj.get('full_name') or '')}|{p_obj.get('birth_year')}"
            dup_buckets.setdefault(bucket_key, []).append(p_uid)

        active_items.sort(key=lambda x: (x["full_name"] or "", x["birth_year"], x["patient_uid"]))
        duplicate_groups = [
            {"group_key": idx + 1, "patient_uids": uids}
            for idx, uids in enumerate(dup_buckets.values())
            if len(uids) >= 2
        ]
        return {
            "store_epoch": int(snap.get("store_epoch", 1) or 1),
            "profile_b_lineage_seq": int((snap.get("settings") or {}).get("profile_b_lineage_seq", 1) or 1),
            "items": active_items,
            "total_active": len(active_items),
            "superseded_count": superseded_count,
            "duplicate_groups": duplicate_groups,
        }

    def merge_patients(
        self,
        req: PatientMergeRequest,
        *,
        actor_username: str,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền gộp hồ sơ người bệnh.")
        scan_payload_notes({"reason": req.reason})
        if req.source_patient_uid == req.target_patient_uid:
            raise DomainValidationError(
                "SAME_PATIENT_MERGE_INVALID",
                "Hồ sơ nguồn và hồ sơ đích phải là hai bản ghi người bệnh khác nhau.",
            )

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            state_epoch = int(state.get("store_epoch", 1) or 1)
            if int(req.expected_store_epoch) != state_epoch:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Kho dữ liệu đang ở thế hệ e{state_epoch}, yêu cầu gửi e{req.expected_store_epoch}.",
                    extra={"current_store_epoch": state_epoch},
                )

            patients = state["patients"]
            episodes = state["episodes"]
            cases = state["cases"]
            if req.source_patient_uid not in patients or req.target_patient_uid not in patients:
                raise KeyError("Không tìm thấy hồ sơ người bệnh nguồn hoặc đích.")

            src = patients[req.source_patient_uid]
            tgt = patients[req.target_patient_uid]
            if src.get("status", "ACTIVE") != "ACTIVE" or tgt.get("status", "ACTIVE") != "ACTIVE":
                raise DomainConflictError(
                    "MERGE_PATIENT_NOT_ACTIVE",
                    "Một trong hai hồ sơ người bệnh đã được gộp trước đó.",
                )

            src_ver = int(src.get("version", 1) or 1)
            tgt_ver = int(tgt.get("version", 1) or 1)
            actual_src_case_ids = sorted(
                cid
                for cid, c in cases.items()
                if c.get("patient_uid") == req.source_patient_uid and c.get("record_status", "ACTIVE") == "ACTIVE"
            )
            expected_src_case_ids = sorted(set(req.expected_source_case_ids))
            if (
                src_ver != int(req.source_expected_version)
                or tgt_ver != int(req.target_expected_version)
                or actual_src_case_ids != expected_src_case_ids
            ):
                raise DomainConflictError(
                    "MERGE_PRECONDITION_CONFLICT",
                    "Trạng thái phiên bản người bệnh hoặc danh sách ca thuộc hồ sơ nguồn đã thay đổi trước khi gộp.",
                    extra={
                        "actual_source_version": src_ver,
                        "actual_target_version": tgt_ver,
                        "actual_source_case_ids": actual_src_case_ids,
                    },
                )

            has_demo_conflict = (
                _normalize_name(src.get("full_name", "")) != _normalize_name(tgt.get("full_name", ""))
                or int(src.get("birth_year") or 0) != int(tgt.get("birth_year") or 0)
                or src.get("sex") != tgt.get("sex")
            )
            if has_demo_conflict and not req.confirm_demographic_conflict:
                raise DomainConflictError(
                    "DEMOGRAPHIC_CONFLICT_CONFIRM_REQUIRED",
                    "Hai hồ sơ lệch họ tên, năm sinh hoặc giới tính; cần xác nhận tường minh thông tin giữ lại.",
                )

            src_mrn = (src.get("hospital_mrn") or "").strip() or None
            src_hash = src.get("hospital_mrn_hash") or None
            tgt_mrn = (tgt.get("hospital_mrn") or "").strip() or None
            tgt_hash = tgt.get("hospital_mrn_hash") or None
            had_distinct_mrn = bool(src_hash and tgt_hash and src_hash != tgt_hash)
            if had_distinct_mrn and not req.confirm_distinct_mrn_override:
                raise DomainConflictError(
                    "DISTINCT_HOSPITAL_MRN_CONFLICT",
                    "Hai hồ sơ có hai mã hồ sơ bệnh viện khác nhau; mặc định từ chối gộp trừ khi xác nhận ghi đè tường minh.",
                )

            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

            # Preserve alias provenance before applying resolved fields
            tgt_aliases = list(tgt.get("merged_from_aliases") or [])
            tgt_aliases.append(
                {
                    "source_patient_uid": req.source_patient_uid,
                    "merged_at_utc": now_iso,
                    "privacy_initials": src.get("privacy_initials"),
                    "full_name": src.get("full_name"),
                    "birth_year": src.get("birth_year"),
                    "sex": src.get("sex"),
                    "hospital_mrn_masked": src.get("hospital_mrn_masked"),
                }
            )
            for inherited_alias in src.get("merged_from_aliases") or []:
                tgt_aliases.append(inherited_alias)
            tgt["merged_from_aliases"] = tgt_aliases

            if has_demo_conflict:
                if req.resolved_full_name:
                    tgt["full_name"] = req.resolved_full_name.strip()
                    tgt["privacy_initials"] = compute_privacy_initials(tgt["full_name"])
                if req.resolved_birth_year is not None:
                    tgt["birth_year"] = int(req.resolved_birth_year)
                if req.resolved_sex is not None:
                    tgt["sex"] = req.resolved_sex

            sec_hashes = list(tgt.get("secondary_mrn_hashes") or [])
            sec_mrns = list(tgt.get("secondary_mrns") or [])

            def _norm_mrn(val: str | None) -> str:
                return (val or "").strip().upper()

            def _add_secondary(m_raw: str | None, m_hash: str | None) -> None:
                if m_hash and m_hash != tgt.get("hospital_mrn_hash") and m_hash not in sec_hashes:
                    sec_hashes.append(m_hash)
                m_clean = (m_raw or "").strip()
                if m_clean:
                    m_norm = _norm_mrn(m_clean)
                    if m_norm != _norm_mrn(tgt.get("hospital_mrn")) and all(_norm_mrn(x) != m_norm for x in sec_mrns):
                        sec_mrns.append(m_clean)

            if had_distinct_mrn:
                if req.primary_mrn_choice == "SOURCE" and src_mrn and src_hash:
                    old_tgt_mrn, old_tgt_hash = tgt_mrn, tgt_hash
                    tgt["hospital_mrn"] = src_mrn
                    tgt["hospital_mrn_masked"] = _mask_mrn(src_mrn)
                    tgt["hospital_mrn_hash"] = src_hash
                    _add_secondary(old_tgt_mrn, old_tgt_hash)
                else:
                    _add_secondary(src_mrn, src_hash)
            elif src_hash and not tgt_hash and src_mrn:
                tgt["hospital_mrn"] = src_mrn
                tgt["hospital_mrn_masked"] = _mask_mrn(src_mrn)
                tgt["hospital_mrn_hash"] = src_hash

            for h_extra in src.get("secondary_mrn_hashes") or []:
                _add_secondary(None, h_extra)
            for m_extra in src.get("secondary_mrns") or []:
                _add_secondary(m_extra, _mrn_hmac(self.settings, m_extra))

            primary_norm = _norm_mrn(tgt.get("hospital_mrn"))
            deduped_sec_mrns: list[str] = []
            seen_sec_norms: set[str] = set()
            for m_item in sec_mrns:
                mc = str(m_item).strip()
                mn = _norm_mrn(mc)
                if mc and mn != primary_norm and mn not in seen_sec_norms:
                    seen_sec_norms.add(mn)
                    deduped_sec_mrns.append(mc)

            tgt["secondary_mrn_hashes"] = [h for h in sec_hashes if h != tgt.get("hospital_mrn_hash")]
            tgt["secondary_mrns"] = deduped_sec_mrns

            # Reassign episodes & cases WITHOUT merging episodes (G05 invariant)
            moved_episode_ids: list[str] = []
            for ep_id, ep_obj in episodes.items():
                if ep_obj.get("patient_uid") == req.source_patient_uid:
                    ep_obj["patient_uid"] = req.target_patient_uid
                    ep_obj["updated_at"] = now_iso
                    moved_episode_ids.append(ep_id)

            moved_case_ids: list[str] = []
            for c_id, c_obj in cases.items():
                if c_obj.get("patient_uid") == req.source_patient_uid:
                    c_obj["patient_uid"] = req.target_patient_uid
                    c_obj["version"] = int(c_obj.get("version", 1)) + 1
                    c_obj["updated_at"] = now_iso
                    moved_case_ids.append(c_id)

            # Flatten transitive merged_into_patient_uid pointers
            for other_p in patients.values():
                if other_p.get("merged_into_patient_uid") == req.source_patient_uid:
                    other_p["merged_into_patient_uid"] = req.target_patient_uid

            src["status"] = "MERGED_SUPERSEDED"
            src["merged_into_patient_uid"] = req.target_patient_uid
            src["version"] = src_ver + 1
            src["updated_at"] = now_iso

            tgt["version"] = tgt_ver + 1
            tgt["updated_at"] = now_iso

            new_lineage_seq = int(state["settings"].get("profile_b_lineage_seq", 1) or 1) + 1
            state["settings"]["profile_b_lineage_seq"] = new_lineage_seq

            state["audit_chain"].append(
                build_audit_entry(
                    state["audit_chain"],
                    actor_username=actor_username,
                    actor_role=actor_role,
                    action="SUPERADMIN_PATIENT_MERGE",
                    entity_type="PATIENT",
                    entity_id=req.target_patient_uid,
                    detail={
                        "source_patient_uid": req.source_patient_uid,
                        "target_patient_uid": req.target_patient_uid,
                        "moved_episode_count": len(moved_episode_ids),
                        "moved_case_count": len(moved_case_ids),
                        "had_demographic_conflict": has_demo_conflict,
                        "had_distinct_mrn_override": had_distinct_mrn,
                        "profile_b_lineage_seq": new_lineage_seq,
                    },
                    now_utc=now_iso,
                )
            )
            return {
                "merged": True,
                "source_patient_uid": req.source_patient_uid,
                "target_patient_uid": req.target_patient_uid,
                "target_version": tgt["version"],
                "moved_episode_ids": sorted(moved_episode_ids),
                "moved_case_ids": sorted(moved_case_ids),
                "store_epoch": state_epoch,
                "profile_b_lineage_seq": new_lineage_seq,
            }

        return self.store.transact(_mutator)

    def reconcile_episodes(
        self,
        req: EpisodeReconcileRequest,
        *,
        actor_username: str,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền hợp nhất đợt nhập viện nội trú.")
        scan_payload_notes({"reason": req.reason})
        if req.source_episode_id == req.target_episode_id:
            raise DomainValidationError(
                "SAME_EPISODE_RECONCILE_INVALID",
                "Đợt điều trị nguồn và đợt đích phải khác nhau.",
            )

        def _mutator(state: dict[str, Any]) -> dict[str, Any]:
            state_epoch = int(state.get("store_epoch", 1) or 1)
            if int(req.expected_store_epoch) != state_epoch:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Kho dữ liệu đang ở thế hệ e{state_epoch}, yêu cầu gửi e{req.expected_store_epoch}.",
                    extra={"current_store_epoch": state_epoch},
                )

            patients = state["patients"]
            episodes = state["episodes"]
            cases = state["cases"]
            if req.patient_uid not in patients:
                raise KeyError(req.patient_uid)
            if patients[req.patient_uid].get("status", "ACTIVE") != "ACTIVE":
                canonical_uid = patients[req.patient_uid].get("merged_into_patient_uid")
                raise DomainConflictError(
                    "PATIENT_MERGED_SUPERSEDED",
                    "Hồ sơ người bệnh đã ở trạng thái gộp.",
                    extra={
                        "canonical_patient_uid": canonical_uid,
                        "merged_into_patient_uid": canonical_uid,
                    },
                )
            if req.source_episode_id not in episodes or req.target_episode_id not in episodes:
                raise KeyError("Không tìm thấy đợt điều trị nguồn hoặc đợt đích.")

            src_ep = episodes[req.source_episode_id]
            tgt_ep = episodes[req.target_episode_id]
            if src_ep.get("status", "ACTIVE") != "ACTIVE" or tgt_ep.get("status", "ACTIVE") != "ACTIVE":
                canonical_ep = src_ep.get("merged_into_episode_id") or tgt_ep.get("merged_into_episode_id")
                raise DomainConflictError(
                    "EPISODE_SUPERSEDED",
                    "Một trong hai đợt điều trị đã được hợp nhất trước đó.",
                    extra={
                        "canonical_episode_id": canonical_ep,
                        "merged_into_episode_id": canonical_ep,
                    },
                )
            if src_ep.get("patient_uid") != req.patient_uid or tgt_ep.get("patient_uid") != req.patient_uid:
                raise DomainValidationError(
                    "EPISODE_PATIENT_MISMATCH",
                    "Hai đợt điều trị phải cùng thuộc một người bệnh trước khi đối soát hợp nhất.",
                )
            if src_ep.get("care_setting") != "INPATIENT" or tgt_ep.get("care_setting") != "INPATIENT":
                raise DomainValidationError(
                    "EPISODE_RECONCILE_INPATIENT_ONLY",
                    "Chỉ cho phép đối soát hợp nhất các đợt điều trị nội trú (INPATIENT) cùng lần nhập viện.",
                )

            actual_case_ids = sorted(
                cid
                for cid, c in cases.items()
                if c.get("episode_id") in (req.source_episode_id, req.target_episode_id)
                and c.get("record_status", "ACTIVE") == "ACTIVE"
            )
            if actual_case_ids != sorted(set(req.expected_case_ids)):
                raise DomainConflictError(
                    "EPISODE_RECONCILE_PRECONDITION_CONFLICT",
                    "Danh sách ca trong hai đợt điều trị đã thay đổi trước khi hợp nhất; vui lòng tải lại để xem trước.",
                    extra={"actual_case_ids": actual_case_ids},
                )

            now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            reassigned_case_ids: list[str] = []
            for cid, c_obj in cases.items():
                if c_obj.get("episode_id") in (req.source_episode_id, req.target_episode_id):
                    if c_obj.get("episode_id") == req.source_episode_id:
                        c_obj["episode_id"] = req.target_episode_id
                        reassigned_case_ids.append(cid)
                    if c_obj.get("track") == "ERCP":
                        c_obj["prior_unrecorded_ercp_offset"] = int(req.resolved_prior_unrecorded_ercp_offset)
                    c_obj["version"] = int(c_obj.get("version", 1)) + 1
                    c_obj["updated_at"] = now_iso

            src_adm = src_ep.get("admission_date") or ""
            tgt_adm = tgt_ep.get("admission_date") or ""
            if src_adm and (not tgt_adm or src_adm < tgt_adm):
                tgt_ep["admission_date"] = src_adm
            tgt_ep["prior_unrecorded_ercp_offset"] = int(req.resolved_prior_unrecorded_ercp_offset)
            tgt_ep["updated_at"] = now_iso

            for other_ep in episodes.values():
                if other_ep.get("merged_into_episode_id") == req.source_episode_id:
                    other_ep["merged_into_episode_id"] = req.target_episode_id

            src_ep["status"] = "MERGED_SUPERSEDED"
            src_ep["merged_into_episode_id"] = req.target_episode_id
            src_ep["updated_at"] = now_iso

            new_lineage_seq = int(state["settings"].get("profile_b_lineage_seq", 1) or 1) + 1
            state["settings"]["profile_b_lineage_seq"] = new_lineage_seq

            active_cases = [c for c in cases.values() if c.get("record_status", "ACTIVE") == "ACTIVE"]
            ercp_indices = compute_ercp_session_indices(active_cases, episodes)
            episode_ercp_sessions = {
                cid: ercp_indices[cid]
                for cid in actual_case_ids
                if cid in ercp_indices
            }

            state["audit_chain"].append(
                build_audit_entry(
                    state["audit_chain"],
                    actor_username=actor_username,
                    actor_role=actor_role,
                    action="SUPERADMIN_EPISODE_RECONCILE",
                    entity_type="EPISODE",
                    entity_id=req.target_episode_id,
                    detail={
                        "patient_uid": req.patient_uid,
                        "source_episode_id": req.source_episode_id,
                        "target_episode_id": req.target_episode_id,
                        "reassigned_case_count": len(reassigned_case_ids),
                        "resolved_prior_unrecorded_ercp_offset": int(req.resolved_prior_unrecorded_ercp_offset),
                        "profile_b_lineage_seq": new_lineage_seq,
                    },
                    now_utc=now_iso,
                )
            )
            return {
                "reconciled": True,
                "patient_uid": req.patient_uid,
                "source_episode_id": req.source_episode_id,
                "target_episode_id": req.target_episode_id,
                "reassigned_case_ids": sorted(reassigned_case_ids),
                "ercp_session_indices": episode_ercp_sessions,
                "store_epoch": state_epoch,
                "profile_b_lineage_seq": new_lineage_seq,
            }

        return self.store.transact(_mutator)

    # -------------------------------------------------------------------------
    # Phase 4C (v0.3.0): Profile A Vault Restore Engine (G02, G03, G04)
    # -------------------------------------------------------------------------
    def extract_vault_blob_from_request(self, req: ProfileARestoreRequest) -> bytes:
        provided = [
            req.vault_text is not None,
            req.vault_envelope is not None,
            req.vault_base64 is not None,
        ]
        if sum(1 for x in provided if x) != 1:
            raise VaultSchemaValidationError(
                "AMBIGUOUS_VAULT_PAYLOAD",
                "Yêu cầu khôi phục phải cung cấp đúng một trong ba trường vault_text, vault_envelope hoặc vault_base64.",
            )
        if req.vault_text is not None:
            blob = req.vault_text.encode("utf-8")
        elif req.vault_base64 is not None:
            try:
                blob = base64.b64decode(req.vault_base64.encode("ascii"), validate=True)
            except Exception as exc:
                raise VaultSchemaValidationError(
                    "INVALID_VAULT_BASE64",
                    "Chuỗi mã hóa Base64 của tệp sao lưu không hợp lệ.",
                ) from exc
        else:
            blob = json.dumps(req.vault_envelope, ensure_ascii=False, indent=2).encode("utf-8")

        if len(blob) > MAX_VAULT_BLOB_BYTES:
            raise VaultPayloadTooLargeError()
        return blob

    def restore_profile_a_vault(
        self,
        req: ProfileARestoreRequest,
        *,
        actor_username: str,
        actor_role: str,
    ) -> dict[str, Any]:
        if actor_role != "superadmin":
            raise PermissionError("Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền khôi phục kho sao lưu Hồ sơ A.")

        vault_blob = self.extract_vault_blob_from_request(req)
        vault_blob_sha256 = hashlib.sha256(vault_blob).hexdigest()

        # Layer 1 (Pre-KDF) + Layer 2 (AES-GCM Decrypt + Domain Referential Validator)
        decrypted = decrypt_profile_a_vault(vault_blob, req.passphrase)
        validated = validate_restored_vault_domain(
            decrypted,
            preserve_current_users=req.preserve_current_users,
        )
        vault_norm = normalize_state_compat(
            validated,
            default_kpi_min_sample_size=self.settings.kpi_min_sample_size,
        )

        def _prepare_restore(
            live_state: dict[str, Any],
        ) -> tuple[dict[str, Any], Any]:
            live_epoch = int(live_state.get("store_epoch", 1) or 1)
            if req.expected_store_epoch is not None and int(req.expected_store_epoch) != live_epoch:
                raise DomainConflictError(
                    "OCC_STORE_EPOCH_MISMATCH",
                    f"Kho dữ liệu đang ở thế hệ e{live_epoch}, yêu cầu gửi e{req.expected_store_epoch}.",
                    extra={"current_store_epoch": live_epoch},
                )

            live_audit_ver = verify_audit_chain(live_state.get("audit_chain", []))
            if not live_audit_ver.get("valid"):
                raise DomainConflictError(
                    "LIVE_AUDIT_CHAIN_BROKEN",
                    "Chuỗi kiểm toán hiện hành không toàn vẹn; dừng khôi phục để bảo toàn bằng chứng kiểm tra.",
                )
            backup_audit_ver = verify_audit_chain(vault_norm["audit_chain"])

            candidate = copy.deepcopy(vault_norm)

            # Layer 3: Cross-machine HMAC key fingerprint verification & optional rekeying (G03)
            backup_cctx = candidate.get("crypto_context")
            keys_match = bool(
                isinstance(backup_cctx, dict)
                and backup_cctx.get("mrn_key_fp") == self.settings.mrn_key_fp
                and backup_cctx.get("shift_key_fp") == self.settings.shift_key_fp
            )

            live_ds_epoch = int((live_state.get("settings") or {}).get("export_dataset_epoch", 1) or 1)
            backup_ds_epoch = int((candidate.get("settings") or {}).get("export_dataset_epoch", 1) or 1)
            if isinstance(backup_cctx, dict) and backup_cctx.get("export_dataset_epoch"):
                backup_ds_epoch = max(backup_ds_epoch, int(backup_cctx["export_dataset_epoch"]))

            if not keys_match and req.key_mismatch_policy == "REJECT":
                raise DomainConflictError(
                    "CRYPTO_KEY_FINGERPRINT_MISMATCH",
                    "Phát hiện lệch dấu vân tay khóa HMAC giữa tệp sao lưu và máy chủ hiện hành. "
                    "Hãy cấu hình cùng bộ khóa gốc để giữ mã nghiên cứu dọc Hồ sơ B, hoặc xác nhận chính sách đặt lại khóa và tăng thế hệ dữ liệu.",
                    extra={
                        "backup_crypto_context": backup_cctx,
                        "server_mrn_key_fp": self.settings.mrn_key_fp,
                        "server_shift_key_fp": self.settings.shift_key_fp,
                    },
                )

            # Check active MRN uniqueness across candidate patients & verify/recompute hashes
            seen_norm_mrns: set[str] = set()
            for p_uid, p_obj in candidate["patients"].items():
                is_active = p_obj.get("status", "ACTIVE") == "ACTIVE"
                raw_mrn = (p_obj.get("hospital_mrn") or "").strip() or None
                if raw_mrn:
                    norm_m = raw_mrn.upper()
                    if is_active:
                        if norm_m in seen_norm_mrns:
                            raise DomainValidationError(
                                "DUPLICATE_ACTIVE_MRN_IN_VAULT",
                                f"Phát hiện trùng mã hồ sơ bệnh viện đang hoạt động trên hồ sơ '{p_uid}'.",
                            )
                        seen_norm_mrns.add(norm_m)
                    computed_hash = _mrn_hmac(self.settings, raw_mrn)
                    if keys_match:
                        if p_obj.get("hospital_mrn_hash") != computed_hash:
                            raise DomainValidationError(
                                "MRN_HASH_INTEGRITY_MISMATCH",
                                f"Mã băm hồ sơ bệnh viện của '{p_uid}' không khớp khóa HMAC của máy chủ.",
                            )
                    else:
                        p_obj["hospital_mrn_hash"] = computed_hash
                        p_obj["hospital_mrn_masked"] = _mask_mrn(raw_mrn)
                else:
                    if keys_match:
                        if p_obj.get("hospital_mrn_hash"):
                            raise DomainValidationError(
                                "MRN_HASH_INTEGRITY_MISMATCH",
                                f"Hồ sơ '{p_uid}' không có mã hồ sơ bệnh viện nhưng chứa hospital_mrn_hash không hợp lệ.",
                            )
                    else:
                        p_obj["hospital_mrn"] = None
                        p_obj["hospital_mrn_masked"] = None
                        p_obj["hospital_mrn_hash"] = None

                sec_mrns_clean: list[str] = []
                recomputed_sec_hashes: list[str] = []
                for sm in p_obj.get("secondary_mrns") or []:
                    sm_clean = str(sm).strip()
                    if not sm_clean:
                        continue
                    norm_sm = sm_clean.upper()
                    if is_active:
                        if norm_sm in seen_norm_mrns:
                            raise DomainValidationError(
                                "DUPLICATE_ACTIVE_SECONDARY_MRN_IN_VAULT",
                                f"Phát hiện trùng mã hồ sơ phụ trên người bệnh '{p_uid}'.",
                            )
                        seen_norm_mrns.add(norm_sm)
                    sec_mrns_clean.append(sm_clean)
                    recomputed_sec_hashes.append(_mrn_hmac(self.settings, sm_clean))

                if keys_match:
                    if list(p_obj.get("secondary_mrn_hashes") or []) != recomputed_sec_hashes:
                        raise DomainValidationError(
                            "SECONDARY_MRN_HASH_INTEGRITY_MISMATCH",
                            f"Danh sách secondary_mrn_hashes của '{p_uid}' không khớp khóa HMAC của máy chủ.",
                        )
                else:
                    p_obj["secondary_mrns"] = sec_mrns_clean
                    p_obj["secondary_mrn_hashes"] = recomputed_sec_hashes

            new_dataset_epoch = (
                max(live_ds_epoch, backup_ds_epoch)
                if keys_match
                else max(live_ds_epoch, backup_ds_epoch) + 1
            )

            # Layer 5: Bump store_epoch & enforce user session policy (G01 & G04)
            backup_epoch = int(candidate.get("store_epoch", 1) or 1)
            new_store_epoch = max(live_epoch, backup_epoch) + 1

            if req.preserve_current_users:
                preserved_users = copy.deepcopy(live_state["users"])
                for u_obj in preserved_users.values():
                    u_obj["auth_version"] = int(u_obj.get("auth_version", 1) or 1) + 1
                candidate["users"] = preserved_users

            candidate["schema_version"] = "1.1.0"
            candidate["store_epoch"] = new_store_epoch
            candidate["revoked_jtis"] = {}
            candidate["settings"]["export_dataset_epoch"] = new_dataset_epoch
            candidate["settings"]["profile_b_lineage_seq"] = max(
                int((live_state.get("settings") or {}).get("profile_b_lineage_seq", 1) or 1),
                int(candidate["settings"].get("profile_b_lineage_seq", 1) or 1),
            )
            candidate["crypto_context"] = self.settings.build_crypto_context(new_dataset_epoch)

            merged_bridges: list[dict[str, Any]] = []
            seen_bridge_shas: set[str] = set()
            for br in list(candidate.get("audit_lineage_bridges") or []) + list(
                live_state.get("audit_lineage_bridges") or []
            ):
                b_sha = str(br.get("pre_restore_sha256") or "")
                if b_sha and b_sha in seen_bridge_shas:
                    continue
                if b_sha:
                    seen_bridge_shas.add(b_sha)
                merged_bridges.append(copy.deepcopy(br))
            candidate["audit_lineage_bridges"] = merged_bridges

            def _finalize(
                cand: dict[str, Any],
                pre_restore_filename: str,
                pre_restore_sha256: str,
            ) -> dict[str, Any]:
                now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
                bridge_record = {
                    "restored_at_utc": now_iso,
                    "actor_username": actor_username,
                    "vault_blob_sha256": vault_blob_sha256,
                    "backup_pre_append_head_hash": backup_audit_ver["head_hash"],
                    "backup_pre_append_seq": len(vault_norm["audit_chain"]),
                    "displaced_live_head_hash": live_audit_ver["head_hash"],
                    "displaced_live_seq": len(live_state["audit_chain"]),
                    "pre_restore_filename": pre_restore_filename,
                    "pre_restore_sha256": pre_restore_sha256,
                    "previous_store_epoch": live_epoch,
                    "new_store_epoch": new_store_epoch,
                    "preserve_current_users": bool(req.preserve_current_users),
                    "key_mismatch_policy": req.key_mismatch_policy,
                }
                cand["audit_lineage_bridges"].append(bridge_record)
                cand["audit_chain"].append(
                    build_audit_entry(
                        cand["audit_chain"],
                        actor_username=actor_username,
                        actor_role=actor_role,
                        action="RESTORE_PROFILE_A_ENCRYPTED",
                        entity_type="STORE",
                        entity_id="endolog_state_v1",
                        detail={
                            "vault_blob_sha256": vault_blob_sha256,
                            "backup_pre_append_head_hash": backup_audit_ver["head_hash"],
                            "backup_pre_append_seq": len(vault_norm["audit_chain"]),
                            "displaced_live_head_hash": live_audit_ver["head_hash"],
                            "displaced_live_seq": len(live_state["audit_chain"]),
                            "pre_restore_filename": pre_restore_filename,
                            "pre_restore_sha256": pre_restore_sha256,
                            "new_store_epoch": new_store_epoch,
                            "export_dataset_epoch": new_dataset_epoch,
                            "preserve_current_users": bool(req.preserve_current_users),
                            "key_mismatch_policy": req.key_mismatch_policy,
                        },
                        now_utc=now_iso,
                    )
                )
                actor_after = cand["users"].get(actor_username)
                return {
                    "restored": True,
                    "new_store_epoch": new_store_epoch,
                    "export_dataset_epoch": new_dataset_epoch,
                    "preserve_current_users": bool(req.preserve_current_users),
                    "reauthentication_required": not bool(req.preserve_current_users),
                    "pre_restore_filename": pre_restore_filename,
                    "pre_restore_sha256": pre_restore_sha256,
                    "restored_case_count": sum(
                        1 for c in cand["cases"].values() if c.get("record_status", "ACTIVE") == "ACTIVE"
                    ),
                    "actor_user": _sanitize_user(actor_after) if (req.preserve_current_users and actor_after) else None,
                }

            return candidate, _finalize

        return self.store.restore_vault_atomic(_prepare_restore)

    # -------------------------------------------------------------------------
    # Case Enrichment & Presentation Projection
    # -------------------------------------------------------------------------
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
        store_epoch = int(state.get("store_epoch", 1) or 1)
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
            "store_epoch": store_epoch,
            "etag": f'W/"e{store_epoch}:v{case["version"]}"',
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
                "admission_date": epi.get("admission_date"),
                "referring_dept": epi.get("referring_dept"),
                "prior_unrecorded_ercp_offset": epi.get(
                    "prior_unrecorded_ercp_offset",
                    case.get("prior_unrecorded_ercp_offset", 0),
                ),
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
