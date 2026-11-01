"""Differential Parity & Zero-PHI Sandbox Gate for GitHub Pages Interactive RAM Engine (Phương án G1+ / v0.3.2).

Executes 12 clinical & Superadmin mutation scenarios in lockstep against:
  1) Python FastAPI + EndoLogService (`TestClient`)
  2) Pure-JS In-Memory RAM Engine (`dist_pages/js/demo-synthetic-adapter.js` via Node.js)

Asserts 100% exact JSON and byte-for-byte CSV / SHA-256 audit-chain parity at every checkpoint.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import hmac
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import endolog.api.service as service_mod
import endolog.core.audit as audit_mod
import endolog.main as main_mod
from endolog.core.config import (
    DEV_JWT_FALLBACK,
    DEV_RESEARCH_FALLBACK,
    DEV_SHIFT_FALLBACK,
    EndoLogSettings,
)
from endolog.core.security import create_access_token, hash_password
from endolog.main import create_app
from tools.build_gh_pages_demo import build_gh_pages_demo


def _require_node() -> str:
    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js binary not available")
    return node_bin


def _run_node_json(node_bin: str, script_text: str, stdin_payload: dict[str, Any]) -> Any:
    proc = subprocess.run(
        [node_bin, "-e", script_text],
        input=json.dumps(stdin_payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Node differential runner failed:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    return json.loads(proc.stdout)


def _hydrate_python_state_from_bundle(
    sanitized_store: dict[str, Any],
    cfg: EndoLogSettings,
) -> dict[str, Any]:
    state = copy.deepcopy(sanitized_store)
    state["crypto_context"] = cfg.build_crypto_context(
        int((state.get("settings") or {}).get("export_dataset_epoch", 1) or 1)
    )
    state["revoked_jtis"] = {}
    pwd_hash = hash_password("TestParityPassphrase!2026")
    for u_obj in state.get("users", {}).values():
        u_obj["password_hash"] = pwd_hash
    for p_obj in state.get("patients", {}).values():
        raw_mrn = (p_obj.get("hospital_mrn") or "").strip() or None
        if raw_mrn:
            p_obj["hospital_mrn"] = raw_mrn
            p_obj["hospital_mrn_hash"] = hmac.new(
                cfg.master_research_key,
                f"mrn:{raw_mrn.upper()}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        else:
            p_obj["hospital_mrn"] = None
            p_obj["hospital_mrn_hash"] = None
        sec_mrns = [str(m).strip() for m in (p_obj.get("secondary_mrns") or []) if str(m).strip()]
        p_obj["secondary_mrns"] = sec_mrns
        p_obj["secondary_mrn_hashes"] = [
            hmac.new(cfg.master_research_key, f"mrn:{m.upper()}".encode("utf-8"), hashlib.sha256).hexdigest()
            for m in sec_mrns
        ]
    return state


def test_g1plus_crypto_and_bankers_rounding_primitives_match_python(tmp_path: Path) -> None:
    node_bin = _require_node()
    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir, base_path="/endolog/")
    adapter_path = str(out_dir / "js" / "demo-synthetic-adapter.js")

    messages = [
        "",
        "EndoLog BVBD 2026 — ThS. BSCKI. Nguyễn Bình An",
        "mrn:SYN-DEMO-2606",
        "Lê Thị Minh Thảo | Võ Thị Ngọc Lan | Cắt từng mảnh ≥ 20 mm",
        "a" * 1000,
    ]
    hmac_keys = [
        DEV_RESEARCH_FALLBACK,
        DEV_SHIFT_FALLBACK,
        "khóa-hmac-dài-hơn-64-bytes-tiếng-việt-có-dấu-để-kiểm-tra-nhánh-sha256-key-compression-2026",
    ]
    round_inputs = [
        (0.0, 1),
        (-0.0, 1),
        (2.5, 0),
        (3.5, 0),
        (1.25, 1),
        (1.35, 1),
        (33.3333333333, 1),
        (66.6666666667, 1),
        (8.425, 2),
        (8.435, 2),
    ]
    canon_objs = [
        {"z": 1, "a": "Tiếng Việt ≥ 20 mm", "m": [True, False, None, {"k2": 2, "k1": 1}]},
        {"case_code": "COL-2026-0006", "changed_fields": ["pathology_completion_status", "index_lesion"]},
    ]

    node_script = """
    const fs = require('fs');
    const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
    const mod = require(payload.adapterPath);
    const out = {
      sha256: payload.messages.map(m => mod.sha256Hex(m)),
      hmac: payload.hmacPairs.map(([k, m]) => mod.hmacSha256Hex(k, m)),
      rounds: payload.roundInputs.map(([v, d]) => mod.pyRound(v, d)),
      canon: payload.canonObjs.map(o => mod.canonicalJson(o))
    };
    process.stdout.write(JSON.stringify(out));
    """
    hmac_pairs = [[k, m] for k in hmac_keys for m in messages]
    res = _run_node_json(
        node_bin,
        node_script,
        {
            "adapterPath": adapter_path,
            "messages": messages,
            "hmacPairs": hmac_pairs,
            "roundInputs": round_inputs,
            "canonObjs": canon_objs,
        },
    )

    assert res["sha256"] == [hashlib.sha256(m.encode("utf-8")).hexdigest() for m in messages]
    assert res["hmac"] == [
        hmac.new(k.encode("utf-8"), m.encode("utf-8"), hashlib.sha256).hexdigest()
        for k, m in hmac_pairs
    ]
    assert res["rounds"] == [round(v, d) for v, d in round_inputs]
    assert res["canon"] == [
        json.dumps(o, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for o in canon_objs
    ]


class _DeterministicClock:
    def __init__(self, base: dt.datetime) -> None:
        self._current = base

    def set_step(self, step_index: int) -> str:
        self._current = dt.datetime(2026, 11, 1, 3, 0, 0, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=step_index)
        return self._current.replace(microsecond=0).isoformat()

    def iso(self) -> str:
        return self._current.replace(microsecond=0).isoformat()


class _DatetimeProxy:
    timezone = dt.timezone
    timedelta = dt.timedelta
    date = dt.date

    def __init__(self, clock: _DeterministicClock) -> None:
        self._clock = clock

    @property
    def datetime(self) -> Any:
        clock = self._clock

        class _FakeDT(dt.datetime):
            @classmethod
            def now(cls, tz: Any = None) -> dt.datetime:
                val = clock._current
                return val.astimezone(tz) if tz is not None else val.replace(tzinfo=None)

        return _FakeDT


def test_g1plus_twelve_scenario_lockstep_differential_parity_with_python_fastapi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    node_bin = _require_node()
    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir, base_path="/endolog/")

    bundle_path = out_dir / "data" / "od05_precomputed_bundle.json"
    adapter_path = out_dir / "js" / "demo-synthetic-adapter.js"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    # Deterministic UID counter and UTC clock shared in lockstep with Node.js
    uid_seq = {"n": 1}

    def _det_uid(prefix: str) -> str:
        idx = uid_seq["n"]
        uid_seq["n"] = idx + 1
        return f"{prefix}_det_{idx:06d}"

    clock = _DeterministicClock(dt.datetime(2026, 11, 1, 3, 0, 0, tzinfo=dt.timezone.utc))
    dt_proxy = _DatetimeProxy(clock)
    monkeypatch.setattr(service_mod, "_new_uid", _det_uid)
    monkeypatch.setattr(service_mod, "dt", dt_proxy)
    monkeypatch.setattr(audit_mod, "dt", dt_proxy)

    cfg = EndoLogSettings(
        env_mode="local_dev_synthetic",
        enable_dev_bypass=True,
        bind_host="127.0.0.1",
        data_dir=tmp_path / "py_data",
        backup_dir=tmp_path / "py_backups",
        jwt_secret=DEV_JWT_FALLBACK,
        master_research_key=DEV_RESEARCH_FALLBACK.encode("utf-8"),
        shift_key=DEV_SHIFT_FALLBACK.encode("utf-8"),
        session_timeout_seconds=900,
        kpi_min_sample_size=20,
    )
    app = create_app(cfg, auto_seed_synthetic=False)
    hydrated_state = _hydrate_python_state_from_bundle(bundle["initial_ram_store"], cfg)
    app.state.store.transact(lambda st: st.update(copy.deepcopy(hydrated_state)))

    client = TestClient(app)
    snap0 = app.state.store.read_snapshot()
    endo_tok, _ = create_access_token(
        cfg,
        username="nguyenbinhan",
        role="endoscopist",
        display_name=snap0["users"]["nguyenbinhan"]["display_name"],
        department=snap0["users"]["nguyenbinhan"]["department"],
        auth_ver=1,
        store_epoch=1,
    )
    admin_tok, _ = create_access_token(
        cfg,
        username="vukhuongan",
        role="superadmin",
        display_name=snap0["users"]["vukhuongan"]["display_name"],
        department=snap0["users"]["vukhuongan"]["department"],
        auth_ver=1,
        store_epoch=1,
    )
    headers_by_actor = {
        "nguyenbinhan": {"Authorization": f"Bearer {endo_tok}"},
        "vukhuongan": {"Authorization": f"Bearer {admin_tok}"},
    }

    # Find OD-05 patient #1 (Lê Thị Minh Thảo) and patient #5 (Võ Thị Ngọc Lan, ERCP inpatient)
    od05_thao_uid = next(
        uid for uid, p in snap0["patients"].items() if p["full_name"] == "Lê Thị Minh Thảo"
    )
    od05_lan_uid = next(
        uid for uid, p in snap0["patients"].items() if p["full_name"] == "Võ Thị Ngọc Lan"
    )

    ops_log: list[dict[str, Any]] = []
    step_counter = {"k": 1}

    def _exec_py(
        actor: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
        raw_text: bool = False,
    ) -> tuple[int, Any, dict[str, str]]:
        step_iso = clock.set_step(step_counter["k"])
        step_counter["k"] += 1
        hdrs = dict(headers_by_actor[actor])
        if extra_headers:
            hdrs.update(extra_headers)
        resp = client.request(method, path, json=body, headers=hdrs)
        ops_log.append(
            {
                "stepIso": step_iso,
                "actor": actor,
                "method": method,
                "path": path,
                "headers": extra_headers or {},
                "body": body,
                "rawText": raw_text,
                "pyStatus": resp.status_code,
                "pyPayload": resp.text if raw_text else resp.json(),
            }
        )
        return resp.status_code, (resp.text if raw_text else resp.json()), dict(resp.headers)

    def _snapshot_checkpoint(label: str) -> None:
        for check_actor, check_path in [
            ("nguyenbinhan", "/api/cases"),
            ("nguyenbinhan", "/api/surveillance"),
            ("nguyenbinhan", "/api/metrics/kpi?min_adr_age=45"),
            ("nguyenbinhan", "/api/metrics/kpi?min_adr_age=50"),
            ("nguyenbinhan", "/api/metrics/cusum?metric=CIR&preset=DEFAULT_90"),
            ("nguyenbinhan", "/api/metrics/cusum?metric=CIR&preset=SCREENING_CIR_95"),
            ("nguyenbinhan", "/api/metrics/cusum?metric=ERCP_NATIVE&preset=DEFAULT_90"),
            ("nguyenbinhan", "/api/metrics/cusum?metric=ERCP_PEP_OR_SEVERE&preset=DEFAULT_90"),
            ("vukhuongan", "/api/admin/patients"),
            ("nguyenbinhan", "/api/audit/verify"),
        ]:
            st, _, _ = _exec_py(check_actor, "GET", check_path)
            assert st == 200, f"[{label}] {check_path} returned {st}"

    # Scenario 1: COL screening normal (0 polyp, BBPS 3+3+3, WT 8.5 min)
    st1, s1_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "full_name": "BN. Giả Lập 06",
            "birth_year": 1969,
            "sex": "M",
            "hospital_mrn": "SYN-DEMO-2606",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-20T08:15",
            "indication": "SCREENING",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 8.5,
            "pathology_completion_status": "NOT_APPLICABLE",
            "followup_30d_status": "COMPLETED_NO_AE",
        },
    )
    assert st1 == 201 and s1_case["surveillance"]["recommended_interval_code"] == "10Y"
    _snapshot_checkpoint("S1_COL_NORMAL")

    # Scenario 2: COL piecemeal EMR >= 20mm (6M USMSTF vs 3_6M ESGE)
    st2, s2_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "full_name": "BN. Giả Lập 07",
            "birth_year": 1972,
            "sex": "F",
            "hospital_mrn": "SYN-DEMO-2607",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-21T09:00",
            "indication": "SCREENING",
            "bbps_right": 2,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "pathology_completion_status": "COMPLETE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "index_lesion": {
                "anatomical_site": "Đại tràng lên",
                "size_mm": 24,
                "paris_class": "0-IIa",
                "resection_method": "EMR_PIECEMEAL",
                "histology_type": "TUBULAR_ADENOMA",
                "dysplasia_grade": "LGD",
                "margins_status": "RX_PIECEMEAL",
            },
            "whole_case_summary": {
                "macroscopic_polyp_count": 1,
                "complete_resection_all_lesions": "ALL_RESECTED_COMPLETELY",
                "any_piecemeal_ge_20mm": "YES",
                "any_confirmed_adenoma": "YES",
                "confirmed_adenoma_count_bin": "1_2",
                "max_adenoma_size_mm": 24,
            },
        },
    )
    assert st2 == 201
    assert s2_case["surveillance"]["recommended_interval_code"] == "6M"
    assert s2_case["surveillance"]["reference_interval_code"] == "3_6M"
    assert s2_case["surveillance"]["is_divergent_guideline"] is True
    _snapshot_checkpoint("S2_COL_PIECEMEAL_20MM")

    # Scenario 3: COL polyp with PENDING GPB (excluded from ADR/SSLDR denominator)
    st3, s3_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "full_name": "BN. Giả Lập 08",
            "birth_year": 1961,
            "sex": "M",
            "hospital_mrn": "SYN-DEMO-2608",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-22T10:00",
            "indication": "DIAGNOSTIC",
            "bbps_right": 2,
            "bbps_transverse": 2,
            "bbps_left": 2,
            "cecal_intubation": "YES",
            "pathology_completion_status": "PENDING",
            "index_lesion": {
                "anatomical_site": "Đại tràng chậu hông",
                "size_mm": 8,
                "resection_method": "COLD_SNARE",
            },
            "whole_case_summary": {
                "macroscopic_polyp_count": 2,
                "complete_resection_all_lesions": "ALL_RESECTED_COMPLETELY",
                "any_confirmed_adenoma": "PENDING_UNKNOWN",
            },
        },
    )
    assert st3 == 201 and s3_case["surveillance"]["status"] == "PENDING_GPB"
    _snapshot_checkpoint("S3_COL_PENDING_GPB")

    # Scenario 4: COL high-risk ESD (sm > 1000 um + LVI+ -> SURGICAL_MDT_CONSULT_ALERT)
    st4, s4_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "full_name": "BN. Giả Lập 09",
            "birth_year": 1976,
            "sex": "F",
            "hospital_mrn": "SYN-DEMO-2609",
            "care_setting": "INPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-23T11:00",
            "indication": "EARLY_CANCER_WORKUP",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "pathology_completion_status": "COMPLETE",
            "index_lesion": {
                "anatomical_site": "Trực tràng thấp",
                "size_mm": 28,
                "paris_class": "0-IIa+IIc",
                "resection_method": "ESD",
                "histology_type": "ADENOCARCINOMA_INVASIVE",
                "dysplasia_grade": "INVASIVE",
                "margins_status": "VM1_OR_R1",
                "sm_invasion_um": 1400,
                "lvi_status": "POSITIVE",
                "differentiation": "WELL_MOD",
                "budding_grade": "BD2_BD3",
            },
        },
    )
    assert st4 == 201 and s4_case["surveillance"]["category"] == "SURGICAL_MDT_CONSULT_ALERT"
    _snapshot_checkpoint("S4_COL_ESD_ALERT")

    # Scenario 5: EGD GI bleeding + hemostasis
    st5, s5_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "full_name": "BN. Giả Lập 10",
            "birth_year": 1957,
            "sex": "M",
            "hospital_mrn": "SYN-DEMO-2610",
            "care_setting": "INPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-24T07:30",
            "indication": "GI_BLEEDING",
            "followup_30d_status": "COMPLETED_NO_AE",
            "index_lesion": {
                "anatomical_site": "Hành tá tràng",
                "size_mm": 12,
                "bleeding_source_type": "NON_VARICEAL_ULCER",
                "forrest_class": "IIa",
                "hemostasis_modality": "Adrenaline + Hemoclip",
                "hemostasis_initial_success": "YES",
                "resection_method": "HEMOSTASIS",
            },
        },
    )
    assert st5 == 201 and s5_case["track"] == "EGD"
    _snapshot_checkpoint("S5_EGD_HEMOSTASIS")

    # Scenario 6: ERCP 2nd session in same open inpatient episode (Võ Thị Ngọc Lan / SYN-INP-2605)
    st6, s6_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "patient_uid": od05_lan_uid,
            "full_name": "Võ Thị Ngọc Lan",
            "birth_year": 1962,
            "sex": "F",
            "hospital_mrn": "SYN-INP-2605",
            "care_setting": "INPATIENT",
            "track": "ERCP",
            "procedure_start_at": "2026-11-02T13:30",
            "indication": "STENT_EXCHANGE",
            "ercp_detail": {
                "papilla_status": "NATIVE_INTACT",
                "selective_cannulation": "SUCCESS",
                "cannulation_contacts_count": 6,
                "cannulation_time_min": 6.5,
                "unintended_pd_count": 0,
                "biliary_interventions": ["STONE_EXTRACTION_BALLOON"],
                "pep_prophylaxis": ["RECTAL_INDOMETHACIN_100MG"],
            },
        },
    )
    assert st6 == 201
    assert s6_case["ercp_computed"]["ercp_session_index_in_episode"] == 2
    assert s6_case["ercp_computed"]["difficult_cannulation_esge2016"] == "YES"
    _snapshot_checkpoint("S6_ERCP_SECOND_SESSION")

    # Scenario 7: PATCH Phase 4 (COMPLETE adenoma on s3_case) + Phase 3 (AE on s6_case) + OCC 409 conflict
    st7a, s3_patched, _ = _exec_py(
        "nguyenbinhan",
        "PATCH",
        f"/api/cases/{s3_case['case_id']}",
        {
            "expected_version": 1,
            "pathology_completion_status": "COMPLETE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "index_lesion": {
                "anatomical_site": "Đại tràng chậu hông",
                "size_mm": 8,
                "resection_method": "COLD_SNARE",
                "histology_type": "TUBULAR_ADENOMA",
                "dysplasia_grade": "LGD",
                "margins_status": "R0",
            },
            "whole_case_summary": {
                "macroscopic_polyp_count": 2,
                "complete_resection_all_lesions": "ALL_RESECTED_COMPLETELY",
                "any_confirmed_adenoma": "YES",
                "confirmed_adenoma_count_bin": "1_2",
                "max_adenoma_size_mm": 8,
            },
        },
        extra_headers={"If-Match": s3_case["etag"]},
    )
    assert st7a == 200 and s3_patched["version"] == 2

    # Stale expected_version=1 must return 409 OCC_VERSION_CONFLICT in both Python & JS
    st7_occ, occ_err, _ = _exec_py(
        "nguyenbinhan",
        "PATCH",
        f"/api/cases/{s3_case['case_id']}",
        {"expected_version": 1, "clinical_note": "Cập nhật phiên bản cũ"},
        extra_headers={"If-Match": s3_case["etag"]},
    )
    assert st7_occ == 409 and occ_err["detail"]["code"] == "OCC_VERSION_CONFLICT"

    st7b, s6_patched, _ = _exec_py(
        "nguyenbinhan",
        "PATCH",
        f"/api/cases/{s6_case['case_id']}",
        {
            "expected_version": 1,
            "followup_30d_status": "COMPLETED_WITH_AE",
            "adverse_events": [
                {
                    "ae_id": "ae_det_pep_01",
                    "window": "INPATIENT_EARLY",
                    "event_type": "PEP",
                    "pep_severity": "MILD",
                    "agree_grade": "II",
                    "note": "Đau thượng vị nhẹ đáp ứng điều trị nội khoa",
                }
            ],
        },
        extra_headers={"If-Match": s6_case["etag"]},
    )
    assert st7b == 200 and s6_patched["clinical_badge"]["tone"] == "urgent"
    _snapshot_checkpoint("S7_PATCH_AND_OCC")

    # Scenario 8: Linked surveillance follow-up case closes origin rec (COMPLETED_LINKED)
    st8, s8_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "patient_uid": s2_case["patient"]["patient_uid"],
            "full_name": "BN. Giả Lập 07",
            "birth_year": 1972,
            "sex": "F",
            "hospital_mrn": "SYN-DEMO-2607",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-28T08:45",
            "indication": "SURVEILLANCE",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 9.0,
            "pathology_completion_status": "NOT_APPLICABLE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "fulfill_surveillance_rec_id": s2_case["surveillance"]["rec_id"],
        },
    )
    assert st8 == 201 and s8_case["case_id"]
    _snapshot_checkpoint("S8_LINKED_SURVEILLANCE")

    # Scenario 9: Settings RBAC (403 for endoscopist on statistical params) + Superadmin ESGE_2020/50/n_min=5/CUSUM 95%
    st9_forbid, err9, _ = _exec_py(
        "nguyenbinhan",
        "PATCH",
        "/api/settings",
        {"kpi_min_sample_size": 5},
    )
    assert st9_forbid == 403 and err9["detail"]["code"] == "SUPERADMIN_REQUIRED_FOR_STATISTICAL_SETTINGS"

    st9_ok, cfg9, _ = _exec_py(
        "vukhuongan",
        "PATCH",
        "/api/settings",
        {
            "colo_guideline_mode": "ESGE_2020",
            "adr_min_age": 50,
            "kpi_min_sample_size": 5,
            "cusum_preset": "SCREENING_CIR_95",
        },
    )
    assert st9_ok == 200 and cfg9["colo_guideline_mode"] == "ESGE_2020"
    _snapshot_checkpoint("S9_SETTINGS_ESGE_AND_RBAC")

    # Scenario 10: Outpatient no-MRN duplicate 409 -> confirm new patient -> Superadmin merge -> 409 post-merge write guard
    dup_payload = {
        "full_name": "Lê Thị Minh Thảo",
        "birth_year": 1974,
        "sex": "F",
        "care_setting": "OUTPATIENT",
        "track": "EGD",
        "procedure_start_at": "2026-10-29T09:15",
        "indication": "DIAGNOSTIC",
        "followup_30d_status": "COMPLETED_NO_AE",
    }
    st10_dup, err10, _ = _exec_py("nguyenbinhan", "POST", "/api/cases", dup_payload)
    assert st10_dup == 409 and err10["detail"]["code"] == "OUTPATIENT_POTENTIAL_DUPLICATE_CONFIRM_REQUIRED"

    st10_new, s10_case, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {**dup_payload, "confirm_outpatient_new_patient": True},
    )
    assert st10_new == 201
    dup_pat_uid = s10_case["patient"]["patient_uid"]
    assert dup_pat_uid != od05_thao_uid

    st10_merge, merge10, _ = _exec_py(
        "vukhuongan",
        "POST",
        "/api/admin/patients/merge",
        {
            "source_patient_uid": dup_pat_uid,
            "target_patient_uid": od05_thao_uid,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [s10_case["case_id"]],
            "reason": "Gộp hồ sơ ngoại trú không mã HS vào hồ sơ chính SYN-OUT-2601",
        },
    )
    assert st10_merge == 200 and merge10["profile_b_lineage_seq"] == 2

    st10_guard, err10_guard, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {**dup_payload, "patient_uid": dup_pat_uid},
    )
    assert st10_guard == 409 and err10_guard["detail"]["code"] == "PATIENT_MERGED_SUPERSEDED"
    _snapshot_checkpoint("S10_DUPLICATE_AND_PATIENT_MERGE")

    # Scenario 11: Create 2 separate inpatient ERCP patients -> merge patients (preserving 2 INPATIENT episodes per G05) -> reconcile episodes
    _, s11a, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "full_name": "BN. Giả Lập 11",
            "birth_year": 1965,
            "sex": "F",
            "hospital_mrn": "SYN-DEMO-2611",
            "care_setting": "INPATIENT",
            "admission_date": "2026-10-25",
            "track": "ERCP",
            "procedure_start_at": "2026-10-26T10:00",
            "indication": "BILIARY_STONE",
        },
    )
    _, s11b, _ = _exec_py(
        "nguyenbinhan",
        "POST",
        "/api/cases",
        {
            "full_name": "BN. Giả Lập 13",
            "birth_year": 1954,
            "sex": "F",
            "hospital_mrn": "SYN-DEMO-2613",
            "care_setting": "INPATIENT",
            "admission_date": "2026-10-25",
            "track": "ERCP",
            "procedure_start_at": "2026-10-27T14:00",
            "indication": "STENT_EXCHANGE",
        },
    )
    p11_target = s11a["patient"]["patient_uid"]
    p11_source = s11b["patient"]["patient_uid"]
    ep11_target = s11a["episode"]["episode_id"]
    ep11_source = s11b["episode"]["episode_id"]

    st11_m, _, _ = _exec_py(
        "vukhuongan",
        "POST",
        "/api/admin/patients/merge",
        {
            "source_patient_uid": p11_source,
            "target_patient_uid": p11_target,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [s11b["case_id"]],
            "confirm_demographic_conflict": True,
            "resolved_full_name": "BN. Giả Lập 11",
            "resolved_birth_year": 1965,
            "resolved_sex": "F",
            "confirm_distinct_mrn_override": True,
            "primary_mrn_choice": "TARGET",
            "reason": "Gộp hai hồ sơ nội trú để đối soát đợt điều trị",
        },
    )
    assert st11_m == 200

    st11_rec, rec11, _ = _exec_py(
        "vukhuongan",
        "POST",
        "/api/admin/episodes/reconcile",
        {
            "patient_uid": p11_target,
            "source_episode_id": ep11_source,
            "target_episode_id": ep11_target,
            "expected_store_epoch": 1,
            "expected_case_ids": sorted([s11a["case_id"], s11b["case_id"]]),
            "resolved_prior_unrecorded_ercp_offset": 1,
            "reason": "Hợp nhất hai đợt nội trú cùng lần nhập viện và đánh số lại phiên ERCP",
        },
    )
    assert st11_rec == 200
    assert rec11["ercp_session_indices"] == {s11a["case_id"]: 2, s11b["case_id"]: 3}
    _snapshot_checkpoint("S11_EPISODE_RECONCILE")

    # Scenario 12: Endoscopist 403 on DELETE + Superadmin DELETE (SUPERSEDED) + Profile B CSV & Profile C JSON byte parity
    st12_forbid, _, _ = _exec_py("nguyenbinhan", "DELETE", f"/api/cases/{s5_case['case_id']}")
    assert st12_forbid == 403

    st12_del, del12, _ = _exec_py(
        "vukhuongan",
        "DELETE",
        f"/api/cases/{s5_case['case_id']}",
        extra_headers={"If-Match": s5_case["etag"]},
    )
    assert st12_del == 200 and del12["record_status"] == "SUPERSEDED"
    _snapshot_checkpoint("S12_SUPERSEDE_CASE")

    # Export Profile B CSV (byte-for-byte including UTF-8 BOM & CRLF) and Profile C JSON (suppress=true & false)
    st_pb, py_csv, pb_hdrs = _exec_py("nguyenbinhan", "GET", "/api/exports/profile-b?fmt=csv", raw_text=True)
    assert st_pb == 200 and py_csv.startswith("\ufeff") and "\r\n" in py_csv
    assert pb_hdrs.get("x-endolog-lineage-seq") == "4"

    st_pc_t, _, _ = _exec_py("nguyenbinhan", "GET", "/api/exports/profile-c?suppress_small_cells=true")
    st_pc_f, _, _ = _exec_py("nguyenbinhan", "GET", "/api/exports/profile-c?suppress_small_cells=false")
    assert st_pc_t == 200 and st_pc_f == 200
    _snapshot_checkpoint("FINAL_POST_EXPORT_AUDIT_PARITY")

    # Replay the exact same ops_log inside Node.js createSyntheticRamEngine and compare EVERY step!
    node_runner = """
    const fs = require('fs');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const bundle = JSON.parse(fs.readFileSync(input.bundlePath, 'utf8'));
    const mod = require(input.adapterPath);

    let currentIso = '2026-11-01T03:00:00+00:00';
    const engine = mod.createSyntheticRamEngine(bundle, {
      initialPersonaKey: 'nguyenbinhan',
      todayIsoProvider: () => input.todayIso,
      nowIsoProvider: () => currentIso,
      uidProvider: (prefix, seq) => `${prefix}_det_${String(seq).padStart(6, '0')}`
    });

    const mismatches = [];
    for (let i = 0; i < input.ops.length; i += 1) {
      const op = input.ops[i];
      currentIso = op.stepIso;
      engine.setPersona(op.actor);
      const res = engine.handleRequest(op.method, op.path, op.headers, op.body);
      if (res.status !== op.pyStatus) {
        mismatches.push({ index: i, path: op.path, field: 'status', py: op.pyStatus, js: res.status, jsBody: res.body });
        break;
      }
      const pyCanon = op.rawText ? String(op.pyPayload) : mod.canonicalJson(op.pyPayload);
      const jsCanon = op.rawText ? String(res.body) : mod.canonicalJson(res.body);
      if (pyCanon !== jsCanon) {
        mismatches.push({
          index: i,
          method: op.method,
          path: op.path,
          pyPreview: pyCanon.slice(0, 600),
          jsPreview: jsCanon.slice(0, 600),
          pyPayload: op.pyPayload,
          jsPayload: res.body
        });
        break;
      }
    }
    process.stdout.write(JSON.stringify({ totalOps: input.ops.length, mismatches }));
    """
    diff_report = _run_node_json(
        node_bin,
        node_runner,
        {
            "bundlePath": str(bundle_path),
            "adapterPath": str(adapter_path),
            "todayIso": dt.date.today().isoformat(),
            "ops": ops_log,
        },
    )
    assert diff_report["mismatches"] == [], f"Differential mismatch detected: {json.dumps(diff_report['mismatches'], ensure_ascii=False, indent=2)}"
    assert diff_report["totalOps"] >= 130


def test_g1plus_sandbox_zero_phi_dlp_identity_and_simulated_restore_guards(tmp_path: Path) -> None:
    node_bin = _require_node()
    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir, base_path="/endolog/")

    node_script = """
    const fs = require('fs');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const bundle = JSON.parse(fs.readFileSync(input.bundlePath, 'utf8'));
    const mod = require(input.adapterPath);
    const engine = mod.createSyntheticRamEngine(bundle, { initialPersonaKey: 'nguyenbinhan' });

    const baseValid = {
      full_name: 'BN. Giả Lập 06',
      birth_year: 1969,
      sex: 'M',
      hospital_mrn: 'SYN-DEMO-2606',
      care_setting: 'OUTPATIENT',
      track: 'EGD',
      procedure_start_at: '2026-10-30T08:00',
      indication: 'DIAGNOSTIC'
    };

    const rRealName = engine.handleRequest('POST', '/api/cases', {}, Object.assign({}, baseValid, { full_name: 'Nguyễn Văn Thật' }));
    const rRealMrnField = engine.handleRequest('POST', '/api/cases', {}, Object.assign({}, baseValid, { hospital_mrn: 'HS26-88412' }));
    const rDlpMrnNote = engine.handleRequest('POST', '/api/cases', {}, Object.assign({}, baseValid, { clinical_note: 'Đối chiếu mã HS26-88412 phòng khám' }));
    const rDlpPhoneNote = engine.handleRequest('POST', '/api/cases', {}, Object.assign({}, baseValid, { clinical_note: 'Gọi số 0901234567 hẹn kết quả' }));
    const rDlpCccdNote = engine.handleRequest('POST', '/api/cases', {}, Object.assign({}, baseValid, { clinical_note: 'CCCD 079085001234' }));
    const rXlsxLocked = engine.handleRequest('GET', '/api/exports/profile-b?fmt=xlsx', {}, null);
    const rSimForbid = engine.handleRequest('POST', '/api/admin/demo-simulate-restore', {}, {});

    // Create 1 valid virtual case so displaced audit chain differs from seed before simulated restore
    const rCreated = engine.handleRequest('POST', '/api/cases', {}, baseValid);
    engine.setPersona('vukhuongan');
    const rSimOk = engine.handleRequest('POST', '/api/admin/demo-simulate-restore', {}, {});
    const rAuditAfterSim = engine.handleRequest('GET', '/api/audit/verify', {}, null);
    const firstCaseId = engine.handleRequest('GET', '/api/cases', {}, null).body.items[0].case_id;
    const rStaleEpochPatch = engine.handleRequest(
      'PATCH',
      '/api/cases/' + firstCaseId,
      { 'If-Match': 'W/"e1:v1"' },
      { expected_version: 1, clinical_note: 'Ghi chú từ thẻ cũ e1' }
    );

    // Logout must wipe RAM back to store_epoch=1 and 5 clean OD-05 cases
    engine.handleRequest('POST', '/api/auth/logout', {}, {});
    engine.handleRequest('POST', '/api/auth/local-bypass', {}, { target_username: 'nguyenbinhan' });
    const rAfterLogout = engine.handleRequest('GET', '/api/cases', {}, null);

    process.stdout.write(JSON.stringify({
      rRealName,
      rRealMrnField,
      rDlpMrnNote,
      rDlpPhoneNote,
      rDlpCccdNote,
      rXlsxLocked,
      rSimForbid,
      rCreatedStatus: rCreated.status,
      rSimOk,
      rAuditAfterSim,
      rStaleEpochPatch,
      afterLogoutEpoch: rAfterLogout.body.store_epoch,
      afterLogoutTotal: rAfterLogout.body.total
    }));
    """
    res = _run_node_json(
        node_bin,
        node_script,
        {
            "bundlePath": str(out_dir / "data" / "od05_precomputed_bundle.json"),
            "adapterPath": str(out_dir / "js" / "demo-synthetic-adapter.js"),
        },
    )

    assert res["rRealName"]["status"] == 422
    assert res["rRealName"]["body"]["detail"]["code"] == "SYNTHETIC_IDENTITY_REQUIRED"
    assert res["rRealMrnField"]["status"] == 422
    assert res["rRealMrnField"]["body"]["detail"]["code"] == "SYNTHETIC_MRN_REQUIRED"
    assert res["rDlpMrnNote"]["status"] == 422
    assert res["rDlpMrnNote"]["body"]["detail"]["code"] == "REAL_HOSPITAL_MRN"
    assert res["rDlpPhoneNote"]["status"] == 422
    assert res["rDlpPhoneNote"]["body"]["detail"]["code"] == "VN_PHONE_NUMBER"
    assert res["rDlpCccdNote"]["status"] == 422
    assert res["rDlpCccdNote"]["body"]["detail"]["code"] == "CCCD_12_DIGITS"
    assert res["rXlsxLocked"]["status"] == 403
    assert res["rXlsxLocked"]["body"]["detail"]["code"] == "STATIC_DEMO_XLSX_LOCKED"
    assert res["rSimForbid"]["status"] == 403
    assert res["rCreatedStatus"] == 201

    assert res["rSimOk"]["status"] == 200
    assert res["rSimOk"]["body"]["new_store_epoch"] == 2
    assert res["rSimOk"]["body"]["restored_case_count"] == 5
    assert res["rAuditAfterSim"]["body"]["verification"]["valid"] is True
    assert res["rAuditAfterSim"]["body"]["lineage_verification"]["valid"] is True
    assert res["rAuditAfterSim"]["body"]["lineage_verification"]["bridge_count"] == 1
    assert res["rStaleEpochPatch"]["status"] == 409
    assert res["rStaleEpochPatch"]["body"]["detail"]["code"] == "OCC_STORE_EPOCH_MISMATCH"

    assert res["afterLogoutEpoch"] == 1
    assert res["afterLogoutTotal"] == 5


def test_g1plus_dlp_schema_bounds_and_merge_synthetic_parity(tmp_path: Path) -> None:
    """Regression suite for F1 (free-text DLP parity + readonly operator), F2 (merge resolved_full_name guard), and F5 (schema extra=forbid & bounds)."""
    node_bin = _require_node()
    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir)  # Default /EndoLog/

    bundle_path = out_dir / "data" / "od05_precomputed_bundle.json"
    adapter_path = out_dir / "js" / "demo-synthetic-adapter.js"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    cfg = EndoLogSettings(
        env_mode="local_dev_synthetic",
        enable_dev_bypass=True,
        bind_host="127.0.0.1",
        data_dir=tmp_path / "py_data_f125",
        backup_dir=tmp_path / "py_backups_f125",
        jwt_secret=DEV_JWT_FALLBACK,
        master_research_key=DEV_RESEARCH_FALLBACK.encode("utf-8"),
        shift_key=DEV_SHIFT_FALLBACK.encode("utf-8"),
        session_timeout_seconds=900,
        kpi_min_sample_size=20,
    )
    app = create_app(cfg, auto_seed_synthetic=False)
    hydrated_state = _hydrate_python_state_from_bundle(bundle["initial_ram_store"], cfg)
    app.state.store.transact(lambda st: st.update(copy.deepcopy(hydrated_state)))
    client = TestClient(app)
    snap0 = app.state.store.read_snapshot()
    admin_tok, _ = create_access_token(
        cfg,
        username="vukhuongan",
        role="superadmin",
        display_name=snap0["users"]["vukhuongan"]["display_name"],
        department=snap0["users"]["vukhuongan"]["department"],
        auth_ver=1,
        store_epoch=1,
    )
    hdrs = {"Authorization": f"Bearer {admin_tok}"}
    first_case_id = next(iter(snap0["cases"].keys()))
    pat_uids = sorted(snap0["patients"].keys())
    ep_ids = sorted(snap0["episodes"].keys())

    base_case = {
        "full_name": "BN. Giả Lập 06",
        "birth_year": 1969,
        "sex": "M",
        "hospital_mrn": "SYN-DEMO-2606",
        "care_setting": "OUTPATIENT",
        "track": "COL",
        "procedure_start_at": "2026-10-30T08:00",
        "indication": "DIAGNOSTIC",
    }

    parity_422_probes: list[tuple[str, str, dict[str, Any]]] = [
        # F1: Free-text DLP across lesion, cecal failure, referring_dept, list[str], and merge resolved_full_name
        ("POST", "/api/cases", {**base_case, "index_lesion": {"anatomical_site": "Đại tràng lên 0901234567"}}),
        ("POST", "/api/cases", {**base_case, "cecal_failure_reason": "Bệnh nhân CCCD 079085001234 đau bụng"}),
        ("POST", "/api/cases", {**base_case, "referring_dept": "Liên hệ bs@bvbd.vn"}),
        (
            "POST",
            "/api/cases",
            {
                **base_case,
                "care_setting": "INPATIENT",
                "track": "ERCP",
                "ercp_detail": {"biliary_interventions": ["EST_0912345678"]},
            },
        ),
        (
            "POST",
            "/api/admin/patients/merge",
            {
                "source_patient_uid": pat_uids[0],
                "target_patient_uid": pat_uids[1],
                "expected_store_epoch": 1,
                "source_expected_version": 1,
                "target_expected_version": 1,
                "confirm_demographic_conflict": True,
                "resolved_full_name": "BN 0901234567",
                "reason": "Kiểm thử DLP trong tên gộp",
            },
        ),
        # F5: extra='forbid', non-integer birth_year, numeric range bounds, and invalid enum literals
        ("POST", "/api/cases", {**base_case, "unexpected_extra_key": "boom"}),
        ("POST", "/api/cases", {**base_case, "birth_year": 1980.5}),
        ("POST", "/api/cases", {**base_case, "bbps_right": 9}),
        ("POST", "/api/cases", {**base_case, "withdrawal_time_clean_min": -2.5}),
        ("POST", "/api/cases", {**base_case, "indication": "NOT_A_VALID_INDICATION"}),
        ("POST", "/api/cases", {**base_case, "index_lesion": {"size_mm": 999}}),
        ("PATCH", f"/api/cases/{first_case_id}", {"expected_version": 1, "rogue_field": 123}),
        ("PATCH", f"/api/cases/{first_case_id}", {"expected_version": 1, "bbps_left": 5}),
        ("PATCH", "/api/settings", {"kpi_min_sample_size": 9999}),
        ("PATCH", "/api/settings", {"unknown_setting": True}),
        # R2-F1: whitespace-only strings on full_name, procedure_start_at, ae_id, resolved_full_name, and reason -> 422
        ("POST", "/api/cases", {**base_case, "full_name": "   "}),
        ("POST", "/api/cases", {**base_case, "procedure_start_at": "    "}),
        (
            "POST",
            "/api/cases",
            {
                **base_case,
                "followup_30d_status": "COMPLETED_WITH_AE",
                "adverse_events": [{"ae_id": "   ", "event_type": "BLEEDING", "agree_grade": "II"}],
            },
        ),
        (
            "POST",
            "/api/admin/patients/merge",
            {
                "source_patient_uid": pat_uids[0],
                "target_patient_uid": pat_uids[1],
                "expected_store_epoch": 1,
                "source_expected_version": 1,
                "target_expected_version": 1,
                "confirm_demographic_conflict": True,
                "resolved_full_name": "   ",
                "reason": "Kiểm thử tên rỗng toàn khoảng trắng",
            },
        ),
        (
            "POST",
            "/api/admin/patients/merge",
            {
                "source_patient_uid": pat_uids[0],
                "target_patient_uid": pat_uids[1],
                "expected_store_epoch": 1,
                "source_expected_version": 1,
                "target_expected_version": 1,
                "reason": "   ",
            },
        ),
        (
            "POST",
            "/api/admin/episodes/reconcile",
            {
                "patient_uid": pat_uids[0],
                "source_episode_id": ep_ids[0],
                "target_episode_id": ep_ids[1],
                "expected_store_epoch": 1,
                "expected_case_ids": [],
                "resolved_prior_unrecorded_ercp_offset": 1,
                "reason": "   ",
            },
        ),
        (
            "POST",
            "/api/admin/episodes/reconcile",
            {
                "patient_uid": pat_uids[0],
                "source_episode_id": ep_ids[0],
                "target_episode_id": ep_ids[1],
                "expected_store_epoch": 1,
                "expected_case_ids": [],
                "resolved_prior_unrecorded_ercp_offset": 99,
                "reason": "Kiểm thử vượt ngưỡng offset ERCP",
            },
        ),
        # R3-F1: Invalid ISO calendar dates & whitespace on POST/PATCH procedure_start_at, admission_date, clinician_followup_due_date -> 422
        ("POST", "/api/cases", {**base_case, "procedure_start_at": "2026-99-99T08:00"}),
        ("POST", "/api/cases", {**base_case, "procedure_start_at": "2026-02-31T08:00"}),
        ("POST", "/api/cases", {**base_case, "procedure_start_at": "2026-10-30T99:99"}),
        ("POST", "/api/cases", {**base_case, "admission_date": "2026-02-29"}),
        ("POST", "/api/cases", {**base_case, "clinician_followup_due_date": "   "}),
        ("PATCH", f"/api/cases/{first_case_id}", {"expected_version": 1, "procedure_start_at": "   "}),
        ("PATCH", f"/api/cases/{first_case_id}", {"expected_version": 1, "procedure_start_at": "2026-02-31T09:00"}),
        ("PATCH", f"/api/cases/{first_case_id}", {"expected_version": 1, "clinician_followup_due_date": "   "}),
        ("PATCH", f"/api/cases/{first_case_id}", {"expected_version": 1, "operator_name": "   "}),
    ]

    for method, path, payload in parity_422_probes:
        py_resp = client.request(method, path, json=payload, headers=hdrs)
        assert py_resp.status_code == 422, f"Python expected 422 on {method} {path} {payload}, got {py_resp.status_code}"

    # R2-F3 + R3-F2 + R3-F3: Numeric coercion, explicit null clearing, and operator_name update parity on PATCH /api/cases/{id}
    coercion_patch_payload = {
        "expected_version": "1",
        "operator_name": "BSCKII. Vũ Khương An",
        "bbps_right": "2",
        "withdrawal_time_clean_min": "9.25",
        "prior_unrecorded_ercp_offset": "1",
        "clinician_followup_due_date": "2027-05-15",
        "index_lesion": {"anatomical_site": "Đại tràng sigma", "size_mm": "8"},
    }
    py_patch_num = client.patch(f"/api/cases/{first_case_id}", json=coercion_patch_payload, headers=hdrs)
    assert py_patch_num.status_code == 200
    py_patch_body = py_patch_num.json()
    assert py_patch_body["operator_name"] == "BSCKII. Vũ Khương An"
    assert py_patch_body["bbps_right"] == 2 and isinstance(py_patch_body["bbps_right"], int)
    assert py_patch_body["withdrawal_time_clean_min"] == 9.25 and isinstance(
        py_patch_body["withdrawal_time_clean_min"], float
    )
    assert py_patch_body["prior_unrecorded_ercp_offset"] == 1 and isinstance(
        py_patch_body["prior_unrecorded_ercp_offset"], int
    )
    assert py_patch_body["clinician_followup_due_date"] == "2027-05-15"
    assert py_patch_body["index_lesion"] is not None

    clear_null_payload = {
        "expected_version": 2,
        "withdrawal_time_clean_min": None,
        "clinician_followup_due_date": None,
        "bbps_right": None,
        "index_lesion": None,
    }
    py_clear = client.patch(f"/api/cases/{first_case_id}", json=clear_null_payload, headers=hdrs)
    assert py_clear.status_code == 200
    py_clear_body = py_clear.json()
    assert py_clear_body["withdrawal_time_clean_min"] is None
    assert py_clear_body["clinician_followup_due_date"] is None
    assert py_clear_body["bbps_right"] is None
    assert py_clear_body["index_lesion"] is None

    py_cfg_num = client.patch("/api/settings", json={"adr_min_age": "50", "kpi_min_sample_size": "15"}, headers=hdrs)
    assert py_cfg_num.status_code == 200
    assert py_cfg_num.json()["adr_min_age"] == 50 and isinstance(py_cfg_num.json()["adr_min_age"], int)
    assert py_cfg_num.json()["kpi_min_sample_size"] == 15

    node_script = """
    const fs = require('fs');
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const bundle = JSON.parse(fs.readFileSync(input.bundlePath, 'utf8'));
    const mod = require(input.adapterPath);
    const engine = mod.createSyntheticRamEngine(bundle, { initialPersonaKey: 'vukhuongan' });

    const statuses = input.probes.map(([m, p, body]) => engine.handleRequest(m, p, {}, body).status);
    const rRealOperator = engine.handleRequest('POST', '/api/cases', {}, Object.assign({}, input.baseCase, {
      operator_name: 'BS. Nguyễn Văn Bác Sĩ Thật'
    }));
    const rPatchRealOperator = engine.handleRequest('PATCH', '/api/cases/' + input.firstCaseId, {}, {
      expected_version: 1,
      operator_name: 'BS. Nguyễn Văn Bác Sĩ Thật'
    });
    const rMergeRealName = engine.handleRequest('POST', '/api/admin/patients/merge', {}, {
      source_patient_uid: input.patUids[0],
      target_patient_uid: input.patUids[1],
      expected_store_epoch: 1,
      source_expected_version: 1,
      target_expected_version: 1,
      confirm_demographic_conflict: true,
      resolved_full_name: 'Trần Thị Bệnh Nhân Thật',
      reason: 'Kiểm thử chặn tên thật khi gộp hồ sơ trên Sandbox'
    });
    const rPatchNum = engine.handleRequest('PATCH', '/api/cases/' + input.firstCaseId, {}, input.coercionPatchPayload);
    const rClearNull = engine.handleRequest('PATCH', '/api/cases/' + input.firstCaseId, {}, input.clearNullPayload);
    const rCfgNum = engine.handleRequest('PATCH', '/api/settings', {}, { adr_min_age: '50', kpi_min_sample_size: '15' });
    process.stdout.write(JSON.stringify({ statuses, rRealOperator, rPatchRealOperator, rMergeRealName, rPatchNum, rClearNull, rCfgNum }));
    """
    js_res = _run_node_json(
        node_bin,
        node_script,
        {
            "bundlePath": str(bundle_path),
            "adapterPath": str(adapter_path),
            "probes": parity_422_probes,
            "baseCase": base_case,
            "patUids": pat_uids,
            "firstCaseId": first_case_id,
            "coercionPatchPayload": coercion_patch_payload,
            "clearNullPayload": clear_null_payload,
        },
    )
    assert js_res["statuses"] == [422] * len(parity_422_probes)
    assert js_res["rRealOperator"]["status"] == 422
    assert js_res["rRealOperator"]["body"]["detail"]["code"] == "SYNTHETIC_OPERATOR_REQUIRED"
    assert js_res["rPatchRealOperator"]["status"] == 422
    assert js_res["rPatchRealOperator"]["body"]["detail"]["code"] == "SYNTHETIC_OPERATOR_REQUIRED"
    assert js_res["rMergeRealName"]["status"] == 422
    assert js_res["rMergeRealName"]["body"]["detail"]["code"] == "SYNTHETIC_IDENTITY_REQUIRED"
    assert js_res["rPatchNum"]["status"] == 200
    assert js_res["rPatchNum"]["body"]["operator_name"] == "BSCKII. Vũ Khương An"
    assert js_res["rPatchNum"]["body"]["bbps_right"] == 2 and isinstance(js_res["rPatchNum"]["body"]["bbps_right"], int)
    assert js_res["rPatchNum"]["body"]["withdrawal_time_clean_min"] == 9.25 and isinstance(
        js_res["rPatchNum"]["body"]["withdrawal_time_clean_min"], float
    )
    assert js_res["rPatchNum"]["body"]["prior_unrecorded_ercp_offset"] == 1 and isinstance(
        js_res["rPatchNum"]["body"]["prior_unrecorded_ercp_offset"], int
    )
    assert js_res["rClearNull"]["status"] == 200
    assert js_res["rClearNull"]["body"]["withdrawal_time_clean_min"] is None
    assert js_res["rClearNull"]["body"]["clinician_followup_due_date"] is None
    assert js_res["rClearNull"]["body"]["bbps_right"] is None
    assert js_res["rClearNull"]["body"]["index_lesion"] is None
    assert js_res["rCfgNum"]["status"] == 200
    assert js_res["rCfgNum"]["body"]["adr_min_age"] == 50 and isinstance(js_res["rCfgNum"]["body"]["adr_min_age"], int)
    assert js_res["rCfgNum"]["body"]["kpi_min_sample_size"] == 15
