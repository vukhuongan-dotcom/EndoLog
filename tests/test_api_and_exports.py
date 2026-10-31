"""Phase 3 integration tests: non-blocking 4-phase workflow, OCC ETag 409, OD-04 MRN rules, and Export Profiles A/B/C."""

from __future__ import annotations

import csv
import datetime as dt
import io
from pathlib import Path

from fastapi.testclient import TestClient

from endolog.clinical.export_profiles import decrypt_profile_a_vault
from endolog.core.config import EndoLogSettings
from endolog.main import create_app


def _build_client(tmp_path: Path) -> TestClient:
    d_dir = tmp_path / "data_synthetic_dev"
    b_dir = tmp_path / "data_backups"
    cfg = EndoLogSettings(
        env_mode="local_dev_synthetic",
        enable_dev_bypass=True,
        bind_host="127.0.0.1",
        data_dir=d_dir,
        backup_dir=b_dir,
        jwt_secret="integration-test-jwt-secret-key-32-chars",
        master_research_key=b"integration-master-key-32-bytes!",
        shift_key=b"integration-shift-key-32-bytes!!",
    )
    app = create_app(cfg, auto_seed_synthetic=False)
    return TestClient(app, client=("127.0.0.1", 52000), base_url="http://localhost")


def test_non_blocking_phase4_occ_conflict_and_od04_mrn_policy(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    r_auth = client.post("/api/auth/local-bypass", json={"target_username": "nguyenbinhan"})
    assert r_auth.status_code == 200

    # OD-04: INPATIENT without hospital_mrn -> 422
    r_bad_inp = client.post(
        "/api/cases",
        json={
            "full_name": "Nguyễn Văn Thử",
            "birth_year": 1965,
            "sex": "M",
            "care_setting": "INPATIENT",
            "track": "ERCP",
            "procedure_start_at": "2026-10-10T09:00:00",
        },
    )
    assert r_bad_inp.status_code == 422

    # Create OUTPATIENT COL without MRN -> succeeds (v1)
    r_c1 = client.post(
        "/api/cases",
        json={
            "full_name": "Trần Thị Mai",
            "birth_year": 1972,
            "sex": "F",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "indication": "SCREENING",
            "procedure_start_at": "2026-10-11T08:30:00",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 2,
            "cecal_intubation": "YES",
            "pathology_completion_status": "PENDING",
            "whole_case_summary": {"macroscopic_polyp_count": 1},
        },
    )
    assert r_c1.status_code == 201
    case_id = r_c1.json()["case_id"]

    # Second OUTPATIENT without MRN with same full_name + birth_year -> MUST NOT auto-merge, returns 409 prompt!
    r_dup = client.post(
        "/api/cases",
        json={
            "full_name": "Trần Thị Mai",
            "birth_year": 1972,
            "sex": "F",
            "care_setting": "OUTPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-15T09:00:00",
        },
    )
    assert r_dup.status_code == 409
    assert r_dup.json()["detail"]["code"] == "OUTPATIENT_POTENTIAL_DUPLICATE_CONFIRM_REQUIRED"

    # Non-blocking Phase 4: update GPB directly while followup_30d_status is still PENDING_WINDOW!
    r_p4 = client.patch(
        f"/api/cases/{case_id}",
        json={
            "expected_version": 1,
            "pathology_completion_status": "COMPLETE",
            "whole_case_summary": {
                "macroscopic_polyp_count": 1,
                "complete_resection_all_lesions": "ALL_RESECTED_COMPLETELY",
                "any_confirmed_adenoma": "YES",
                "confirmed_adenoma_count_bin": "1_2",
                "max_adenoma_size_mm": 6,
            },
        },
    )
    assert r_p4.status_code == 200
    assert r_p4.json()["version"] == 2
    assert r_p4.json()["surveillance"]["recommended_interval_code"] == "7_10Y"

    # Stale expected_version=1 -> 409 OCC_VERSION_CONFLICT
    r_stale = client.patch(
        f"/api/cases/{case_id}",
        json={"expected_version": 1, "followup_30d_status": "COMPLETED_NO_AE"},
    )
    assert r_stale.status_code == 409
    assert r_stale.json()["detail"]["code"] == "OCC_VERSION_CONFLICT"

    # Endoscopist cannot DELETE/supersede case (Superadmin exclusive)
    r_del_denied = client.delete(f"/api/cases/{case_id}")
    assert r_del_denied.status_code == 403


def test_longitudinal_exports_profile_a_b_c(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    # Login as Superadmin via local-bypass in synthetic mode
    client.post("/api/auth/local-bypass", json={"target_username": "vukhuongan"})

    # Two ERCPs for same inpatient 3 days apart
    for idx, dt_str in enumerate(["2026-06-10T09:00:00", "2026-06-13T10:30:00"], start=1):
        r = client.post(
            "/api/cases",
            json={
                "full_name": "Lý Minh Tâm",
                "birth_year": 1932,  # age 94 -> capped to 90+
                "sex": "M",
                "hospital_mrn": "BVBD-9901",
                "care_setting": "INPATIENT",
                "track": "ERCP",
                "procedure_start_at": dt_str,
                "followup_30d_status": "COMPLETED_NO_AE",
            },
        )
        assert r.status_code == 201
        assert r.json()["ercp_computed"]["ercp_session_index_in_episode"] == idx

    # Profile A encrypted round-trip
    r_a = client.post("/api/exports/profile-a", json={"passphrase": "StrongBackupPassword#2026"})
    assert r_a.status_code == 200
    decrypted = decrypt_profile_a_vault(r_a.content, "StrongBackupPassword#2026")
    assert len(decrypted["cases"]) == 2

    # Profile B CSV: preserves exact 3-day interval, caps age to 90+, strips raw name & MRN
    r_b = client.get("/api/exports/profile-b?fmt=csv")
    assert r_b.status_code == 200
    csv_text = r_b.content.decode("utf-8-sig")
    assert "Lý Minh Tâm" not in csv_text
    assert "BVBD-9901" not in csv_text
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 2
    assert rows[0]["research_subject_id"] == rows[1]["research_subject_id"]
    assert rows[0]["age_years_capped"] == "90+"
    d0 = dt.date.fromisoformat(rows[0]["shifted_procedure_date"])
    d1 = dt.date.fromisoformat(rows[1]["shifted_procedure_date"])
    assert (d1 - d0).days == 3

    # Profile C small-cell suppression (<5)
    r_c = client.get("/api/exports/profile-c?suppress_small_cells=true")
    assert r_c.status_code == 200
    assert r_c.json()["total_active_cases"] == "<5"

    # Audit chain valid
    r_aud = client.get("/api/audit/verify")
    assert r_aud.status_code == 200
    assert r_aud.json()["verification"]["valid"] is True
