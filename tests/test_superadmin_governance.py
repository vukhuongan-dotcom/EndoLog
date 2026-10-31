"""Phase 4C (v0.3.0) Superadmin Governance Suite adversarial tests (TC-G01 .. TC-G05)."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

import pytest
from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from endolog.core.config import EndoLogSettings
from endolog.core.security import hash_password
from endolog.main import COOKIE_NAME, create_app


DEV_ENDOSCOPIST_PWD = "EndoscopistStrongPass2026!"
DEV_SUPERADMIN_PWD = "SuperadminStrongPass2026!"
VAULT_PASSPHRASE = "KhoaSaoLuuMaHoaEndoLog2026!"


def _build_test_app(
    data_dir: Path,
    *,
    auto_seed: bool = False,
    mrn_key: str = "dev-mrn-hmac-secret-key-2026-server-a-0001",
    shift_key: str = "dev-date-shift-secret-key-2026-server-a-0001",
) -> tuple[EndoLogSettings, Any]:
    cfg = EndoLogSettings(
        env_mode="local_dev_synthetic",
        enable_dev_bypass=True,
        bind_host="127.0.0.1",
        data_dir=data_dir / "data_synthetic_dev",
        backup_dir=data_dir / "data_backups",
        jwt_secret="test-jwt-secret-phase4c-superadmin-governance-2026",
        master_research_key=mrn_key.encode("utf-8"),
        shift_key=shift_key.encode("utf-8"),
        session_timeout_seconds=900,
        kpi_min_sample_size=20,
    )
    app = create_app(
        cfg,
        auto_seed_synthetic=auto_seed,
        bootstrap_passwords={
            "nguyenbinhan": DEV_ENDOSCOPIST_PWD,
            "vukhuongan": DEV_SUPERADMIN_PWD,
        },
    )
    return cfg, app


def _client(app: Any) -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000))


def _find_case(client: TestClient, case_id: str) -> dict[str, Any]:
    items = client.get("/api/cases").json()["items"]
    return next(item for item in items if item["case_id"] == case_id)


def _reencrypt_vault_plaintext(vault_obj: dict[str, Any], passphrase: str) -> str:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=2,
        memory_cost=65536,
        parallelism=2,
        hash_len=32,
        type=Type.ID,
    )
    plaintext = json.dumps(vault_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, b"endolog-export-profile-a-v1")
    envelope = {
        "contract": "EndoLog-Export-Profile-A-v1.0",
        "kdf": "argon2id",
        "cipher": "aes-256-gcm",
        "salt_hex": salt.hex(),
        "nonce_hex": nonce.hex(),
        "ciphertext_hex": ciphertext.hex(),
    }
    return json.dumps(envelope, indent=2)


def test_tc_g01_rbac_25_route_matrix_and_session_jwt_revocation(tmp_path: Path) -> None:
    cfg, app = _build_test_app(tmp_path / "g01_store", auto_seed=True)

    anon = _client(app)
    assert anon.get("/api/health").status_code == 200
    assert anon.post("/api/auth/logout").status_code == 200

    # All protected endpoints must reject unauthenticated access with 401
    unauth_checks = [
        ("GET", "/api/auth/me", None),
        ("POST", "/api/auth/change-password", {"current_password": DEV_ENDOSCOPIST_PWD, "new_password": "NewValidPassword2026!"}),
        ("GET", "/api/cases", None),
        ("POST", "/api/cases", {"full_name": "Nguyễn Văn A", "birth_year": 1970, "sex": "M", "care_setting": "OUTPATIENT", "track": "EGD", "procedure_start_at": "2026-10-31T08:00:00+07:00", "indication": "DIAGNOSTIC"}),
        ("PATCH", "/api/cases/nonexistent", {"expected_version": 1}),
        ("DELETE", "/api/cases/nonexistent", None),
        ("GET", "/api/surveillance", None),
        ("GET", "/api/metrics/kpi", None),
        ("GET", "/api/metrics/cusum", None),
        ("GET", "/api/audit/verify", None),
        ("GET", "/api/settings", None),
        ("PATCH", "/api/settings", {"colo_guideline_mode": "USMSTF_2020"}),
        ("POST", "/api/exports/profile-a", {"passphrase": VAULT_PASSPHRASE}),
        ("GET", "/api/exports/profile-b", None),
        ("GET", "/api/exports/profile-c", None),
        ("POST", "/api/admin/restore-profile-a", {"vault_text": "{}", "passphrase": VAULT_PASSPHRASE}),
        ("GET", "/api/admin/patients", None),
        ("POST", "/api/admin/patients/merge", {"source_patient_uid": "p1", "target_patient_uid": "p2", "expected_store_epoch": 1, "source_expected_version": 1, "target_expected_version": 1, "expected_source_case_ids": [], "reason": "Kiểm thử RBAC"}),
        ("POST", "/api/admin/episodes/reconcile", {"patient_uid": "p1", "source_episode_id": "e1", "target_episode_id": "e2", "expected_store_epoch": 1, "expected_case_ids": [], "reason": "Kiểm thử RBAC"}),
        ("GET", "/api/admin/users", None),
        ("POST", "/api/admin/users/nguyenbinhan/reset-password", {"new_password": "ResetPasswordStrong2026!"}),
    ]
    for method, path, payload in unauth_checks:
        resp = anon.request(method, path, json=payload)
        assert resp.status_code == 401, f"Expected 401 on {method} {path}, got {resp.status_code}"

    # Endoscopist RBAC boundaries: 403 on all Superadmin-only routes
    endo_a = _client(app)
    endo_b = _client(app)
    assert endo_a.post("/api/auth/login", json={"username": "nguyenbinhan", "password": DEV_ENDOSCOPIST_PWD}).status_code == 200
    assert endo_b.post("/api/auth/login", json={"username": "nguyenbinhan", "password": DEV_ENDOSCOPIST_PWD}).status_code == 200

    first_cid = endo_a.get("/api/cases").json()["items"][0]["case_id"]
    endo_forbidden = [
        ("DELETE", f"/api/cases/{first_cid}", None),
        ("PATCH", "/api/settings", {"kpi_min_sample_size": 10}),
        ("PATCH", "/api/settings", {"cusum_preset": "SCREENING_CIR_95"}),
        ("POST", "/api/exports/profile-a", {"passphrase": VAULT_PASSPHRASE}),
        ("POST", "/api/admin/restore-profile-a", {"vault_text": "{}", "passphrase": VAULT_PASSPHRASE}),
        ("GET", "/api/admin/patients", None),
        ("POST", "/api/admin/patients/merge", {"source_patient_uid": "p1", "target_patient_uid": "p2", "expected_store_epoch": 1, "source_expected_version": 1, "target_expected_version": 1, "expected_source_case_ids": [], "reason": "Kiểm thử RBAC"}),
        ("POST", "/api/admin/episodes/reconcile", {"patient_uid": "p1", "source_episode_id": "e1", "target_episode_id": "e2", "expected_store_epoch": 1, "expected_case_ids": [], "reason": "Kiểm thử RBAC"}),
        ("GET", "/api/admin/users", None),
        ("POST", "/api/admin/users/vukhuongan/reset-password", {"new_password": "ResetPasswordStrong2026!"}),
    ]
    for method, path, payload in endo_forbidden:
        resp = endo_a.request(method, path, json=payload)
        assert resp.status_code == 403, f"Expected 403 for endoscopist on {method} {path}, got {resp.status_code}"

    # Self password change on endo_a -> rotates endo_a token (200), immediately revokes endo_b (401)
    new_pwd_1 = "EndoUpdatedPass2026#A"
    assert endo_a.post(
        "/api/auth/change-password",
        json={"current_password": "WrongOldPassword123!", "new_password": new_pwd_1},
    ).status_code == 400

    r_chg = endo_a.post(
        "/api/auth/change-password",
        json={"current_password": DEV_ENDOSCOPIST_PWD, "new_password": new_pwd_1},
    )
    assert r_chg.status_code == 200, r_chg.text
    assert endo_a.get("/api/auth/me").status_code == 200
    assert endo_b.get("/api/auth/me").status_code == 401

    # Superadmin resets endoscopist password -> revokes endo_a immediately
    admin_c = _client(app)
    assert admin_c.post("/api/auth/login", json={"username": "vukhuongan", "password": DEV_SUPERADMIN_PWD}).status_code == 200

    users_resp = admin_c.get("/api/admin/users")
    assert users_resp.status_code == 200
    raw_users_txt = users_resp.text
    assert "password_hash" not in raw_users_txt
    assert "$argon2id$" not in raw_users_txt

    reset_pwd_2 = "AdminResetEndoPass2026#B"
    r_rst = admin_c.post(
        "/api/admin/users/nguyenbinhan/reset-password",
        json={"new_password": reset_pwd_2, "reason": "Đặt lại mật khẩu định kỳ theo quy trình khoa"},
    )
    assert r_rst.status_code == 200, r_rst.text
    assert endo_a.get("/api/auth/me").status_code == 401

    # Old password fails 401; new reset password logs in 200; explicit logout revokes jti replay
    endo_c = _client(app)
    assert endo_c.post("/api/auth/login", json={"username": "nguyenbinhan", "password": new_pwd_1}).status_code == 401
    assert endo_c.post("/api/auth/login", json={"username": "nguyenbinhan", "password": reset_pwd_2}).status_code == 200
    captured_jwt = endo_c.cookies.get(COOKIE_NAME)
    assert captured_jwt
    assert endo_c.post("/api/auth/logout").status_code == 200

    replay_client = _client(app)
    replay_client.cookies.set(COOKIE_NAME, captured_jwt)
    assert replay_client.get("/api/auth/me").status_code == 401

    audit_txt = admin_c.get("/api/audit/verify").text
    for forbidden_secret in (
        "password_hash",
        "$argon2id$",
        cfg.jwt_secret,
        cfg.master_research_key.decode("utf-8"),
        cfg.shift_key.decode("utf-8"),
    ):
        assert forbidden_secret not in audit_txt


def test_tc_g02_restore_pre_kdf_guard_and_strict_domain_validation(tmp_path: Path) -> None:
    _cfg, app = _build_test_app(tmp_path / "g02_store", auto_seed=True)
    admin = _client(app)
    assert admin.post("/api/auth/local-bypass", json={"target_username": "vukhuongan"}).status_code == 200

    baseline_cases = admin.get("/api/cases").json()["total"]
    assert baseline_cases >= 5

    # 1. > 10 MiB payload rejected with 413 BEFORE KDF
    oversized_vault = "A" * 10_485_761
    r_413 = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": oversized_vault, "passphrase": VAULT_PASSPHRASE, "expected_store_epoch": 1},
    )
    assert r_413.status_code == 413
    assert r_413.json()["detail"]["code"] == "VAULT_PAYLOAD_TOO_LARGE"

    # 2. Invalid KDF / contract envelope rejected with 422 BEFORE KDF
    bad_env = json.dumps(
        {
            "contract": "Unsupported-Contract-v9.9",
            "kdf": "pbkdf2",
            "cipher": "aes-256-gcm",
            "salt_hex": "00" * 16,
            "nonce_hex": "11" * 12,
            "ciphertext_hex": "22" * 32,
        }
    )
    r_bad_env = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": bad_env, "passphrase": VAULT_PASSPHRASE, "expected_store_epoch": 1},
    )
    assert r_bad_env.status_code == 422

    # Export a valid Profile A backup and grab raw snapshot to craft adversarial mutations
    r_exp = admin.post("/api/exports/profile-a", json={"passphrase": VAULT_PASSPHRASE})
    assert r_exp.status_code == 200
    valid_vault_text = r_exp.content.decode("utf-8")

    # 3. Wrong passphrase -> 400
    r_wrong_pass = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": valid_vault_text, "passphrase": "SaiMatKhauHoanToan2026!", "expected_store_epoch": 1},
    )
    assert r_wrong_pass.status_code == 400
    assert r_wrong_pass.json()["detail"]["code"] == "VAULT_DECRYPT_FAILED"

    base_snap = app.state.store.read_snapshot()

    # 4a. Broken audit chain hash -> 422 INVALID_VAULT_AUDIT_CHAIN
    mut_audit = json.loads(json.dumps(base_snap))
    mut_audit["audit_chain"][0]["entry_hash"] = "f" * 64
    r_mut_audit = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_audit, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_mut_audit.status_code == 422
    assert r_mut_audit.json()["detail"]["code"] == "INVALID_VAULT_AUDIT_CHAIN"

    # 4b. Dangling patient_uid on case -> 422 BROKEN_CASE_PATIENT_FK
    mut_fk = json.loads(json.dumps(base_snap))
    any_cid = next(iter(mut_fk["cases"]))
    mut_fk["cases"][any_cid]["patient_uid"] = "pat_dangling_missing"
    r_mut_fk = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_fk, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_mut_fk.status_code == 422
    assert r_mut_fk.json()["detail"]["code"] == "BROKEN_CASE_PATIENT_FK"

    # 4c. Episode belongs to a different patient_uid than case -> 422 CASE_EPISODE_PATIENT_MISMATCH
    mut_ep_mismatch = json.loads(json.dumps(base_snap))
    c_iter = iter(mut_ep_mismatch["cases"].values())
    c1 = next(c_iter)
    other_pat_uid = next(uid for uid in mut_ep_mismatch["patients"] if uid != c1["patient_uid"])
    mut_ep_mismatch["episodes"][c1["episode_id"]]["patient_uid"] = other_pat_uid
    r_mut_ep = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_ep_mismatch, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_mut_ep.status_code == 422
    assert r_mut_ep.json()["detail"]["code"] == "CASE_EPISODE_PATIENT_MISMATCH"

    # 4d. Counter smaller than existing case sequence -> 422 COUNTER_MONOTONICITY_VIOLATION
    mut_ctr = json.loads(json.dumps(base_snap))
    col_counter_key = next(k for k in mut_ctr["counters"] if mut_ctr["counters"][k] >= 1)
    mut_ctr["counters"][col_counter_key] = 0
    r_mut_ctr = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_ctr, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_mut_ctr.status_code == 422
    assert r_mut_ctr.json()["detail"]["code"] == "COUNTER_MONOTONICITY_VIOLATION"

    # 4e. Missing active superadmin when preserve_current_users=False -> 422 NO_ACTIVE_SUPERADMIN_IN_VAULT
    mut_nosuper = json.loads(json.dumps(base_snap))
    mut_nosuper["users"]["vukhuongan"]["active"] = False
    r_mut_nosuper = admin.post(
        "/api/admin/restore-profile-a",
        json={
            "vault_text": _reencrypt_vault_plaintext(mut_nosuper, VAULT_PASSPHRASE),
            "passphrase": VAULT_PASSPHRASE,
            "preserve_current_users": False,
        },
    )
    assert r_mut_nosuper.status_code == 422
    assert r_mut_nosuper.json()["detail"]["code"] == "NO_ACTIVE_SUPERADMIN_IN_VAULT"

    # 4f. Unknown field injected into stored case record (extra="forbid") -> 422 INVALID_CASE_RECORD
    mut_extra = json.loads(json.dumps(base_snap))
    mut_extra["cases"][any_cid]["unexpected_injected_field"] = "forbidden"
    r_mut_extra = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_extra, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_mut_extra.status_code == 422
    assert r_mut_extra.json()["detail"]["code"] == "INVALID_CASE_RECORD"

    # Live store remains at store_epoch=1 with baseline cases intact
    after_check = admin.get("/api/cases").json()
    assert after_check["store_epoch"] == 1
    assert after_check["total"] == baseline_cases


def test_tc_g03_cross_machine_hmac_key_fingerprint_and_rekey_dataset_epoch(tmp_path: Path) -> None:
    _cfg_1, app_1 = _build_test_app(
        tmp_path / "server_1",
        auto_seed=False,
        mrn_key="server-1-mrn-hmac-secret-key-2026-alpha",
        shift_key="server-1-date-shift-secret-key-2026-alpha",
    )
    c1 = _client(app_1)
    assert c1.post("/api/auth/local-bypass", json={"target_username": "vukhuongan"}).status_code == 200

    # Create two inpatient records with distinct MRNs and merge them so both primary & secondary MRNs exist
    r_p1 = c1.post(
        "/api/cases",
        json={
            "full_name": "Lê Hoàng Nam",
            "birth_year": 1968,
            "sex": "M",
            "hospital_mrn": "HS26-10001",
            "care_setting": "INPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-10T08:30:00+07:00",
            "indication": "SCREENING",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 9.0,
        },
    )
    assert r_p1.status_code == 201
    p1_uid = r_p1.json()["patient_uid"]

    r_p2 = c1.post(
        "/api/cases",
        json={
            "full_name": "Lê Hoàng Nam",
            "birth_year": 1968,
            "sex": "M",
            "hospital_mrn": "HS26-20002",
            "care_setting": "INPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-12T09:00:00+07:00",
            "indication": "DIAGNOSTIC",
        },
    )
    assert r_p2.status_code == 201
    p2_uid = r_p2.json()["patient_uid"]
    p2_cid = r_p2.json()["case_id"]

    r_merge = c1.post(
        "/api/admin/patients/merge",
        json={
            "source_patient_uid": p2_uid,
            "target_patient_uid": p1_uid,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [p2_cid],
            "confirm_distinct_mrn_override": True,
            "primary_mrn_choice": "TARGET",
            "reason": "Gộp mã hồ sơ ngoại viện cũ vào mã hồ sơ nội trú chuẩn",
        },
    )
    assert r_merge.status_code == 200, r_merge.text

    vault_bytes = c1.post("/api/exports/profile-a", json={"passphrase": VAULT_PASSPHRASE}).content
    vault_text = vault_bytes.decode("utf-8")

    # Server 2 has different HMAC keys
    _cfg_2, app_2 = _build_test_app(
        tmp_path / "server_2",
        auto_seed=False,
        mrn_key="server-2-mrn-hmac-secret-key-2026-bravo",
        shift_key="server-2-date-shift-secret-key-2026-bravo",
    )
    c2 = _client(app_2)
    assert c2.post("/api/auth/local-bypass", json={"target_username": "vukhuongan"}).status_code == 200

    # Policy REJECT -> 409 CRYPTO_KEY_FINGERPRINT_MISMATCH
    r_reject = c2.post(
        "/api/admin/restore-profile-a",
        json={
            "vault_text": vault_text,
            "passphrase": VAULT_PASSPHRASE,
            "expected_store_epoch": 1,
            "key_mismatch_policy": "REJECT",
        },
    )
    assert r_reject.status_code == 409
    assert r_reject.json()["detail"]["code"] == "CRYPTO_KEY_FINGERPRINT_MISMATCH"

    # Policy REKEY_AND_BUMP_DATASET_EPOCH -> 200, dataset_epoch=2, both primary & secondary MRNs match on Server 2
    r_rekey = c2.post(
        "/api/admin/restore-profile-a",
        json={
            "vault_text": vault_text,
            "passphrase": VAULT_PASSPHRASE,
            "expected_store_epoch": 1,
            "key_mismatch_policy": "REKEY_AND_BUMP_DATASET_EPOCH",
        },
    )
    assert r_rekey.status_code == 200, r_rekey.text
    rekey_body = r_rekey.json()
    assert rekey_body["export_dataset_epoch"] == 2
    assert rekey_body["new_store_epoch"] == 2

    # Posting new cases on Server 2 with primary MRN ("HS26-10001") AND secondary MRN ("HS26-20002") both match p1_uid!
    r_match_primary = c2.post(
        "/api/cases",
        json={
            "full_name": "Lê Hoàng Nam",
            "birth_year": 1968,
            "sex": "M",
            "hospital_mrn": "HS26-10001",
            "care_setting": "INPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-20T08:00:00+07:00",
            "indication": "SURVEILLANCE",
        },
    )
    assert r_match_primary.status_code == 201
    assert r_match_primary.json()["patient_uid"] == p1_uid

    r_match_secondary = c2.post(
        "/api/cases",
        json={
            "full_name": "Lê Hoàng Nam",
            "birth_year": 1968,
            "sex": "M",
            "hospital_mrn": "HS26-20002",
            "care_setting": "INPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-25T09:00:00+07:00",
            "indication": "SURVEILLANCE",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 8.5,
        },
    )
    assert r_match_secondary.status_code == 201
    assert r_match_secondary.json()["patient_uid"] == p1_uid

    # Profile B CSV exposes export_dataset_epoch == 2 and profile_b_lineage_seq == 2
    r_csv = c2.get("/api/exports/profile-b?fmt=csv")
    assert r_csv.status_code == 200
    assert r_csv.headers.get("x-endolog-dataset-epoch") == "2"
    assert r_csv.headers.get("x-endolog-lineage-seq") == "2"
    rows = list(csv.DictReader(io.StringIO(r_csv.content.decode("utf-8-sig"))))
    assert len(rows) == 4
    assert all(r["export_dataset_epoch"] == "2" for r in rows)
    assert all(r["profile_b_lineage_seq"] == "2" for r in rows)


def test_tc_g04_store_epoch_occ_atomic_pre_restore_and_audit_lineage_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, app = _build_test_app(tmp_path / "g04_store", auto_seed=False)

    admin = _client(app)
    endo = _client(app)
    assert admin.post("/api/auth/login", json={"username": "vukhuongan", "password": DEV_SUPERADMIN_PWD}).status_code == 200
    assert endo.post("/api/auth/login", json={"username": "nguyenbinhan", "password": DEV_ENDOSCOPIST_PWD}).status_code == 200

    # Create case -> e1:v1, then patch -> e1:v2
    r_c = endo.post(
        "/api/cases",
        json={
            "full_name": "Phạm Thị Thu Thảo",
            "birth_year": 1975,
            "sex": "F",
            "hospital_mrn": "HS26-44001",
            "care_setting": "INPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-15T08:00:00+07:00",
            "indication": "SCREENING",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 8.0,
        },
    )
    assert r_c.status_code == 201
    cid = r_c.json()["case_id"]

    r_v2 = endo.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"e1:v1"'},
        json={"expected_version": 1, "expected_store_epoch": 1, "clinical_note": "Ghi chú ở thế hệ e1:v2"},
    )
    assert r_v2.status_code == 200
    assert r_v2.headers.get("etag") == 'W/"e1:v2"'

    # Export backup at e1:v2
    vault_e1_v2 = admin.post("/api/exports/profile-a", json={"passphrase": VAULT_PASSPHRASE}).content.decode("utf-8")

    # Mutate live state to e1:v3 AND change superadmin password on live so we can also test preserve_current_users=False later
    r_v3 = endo.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"e1:v2"'},
        json={"expected_version": 2, "expected_store_epoch": 1, "clinical_note": "Ghi chú mới ở e1:v3 trước khôi phục"},
    )
    assert r_v3.status_code == 200
    assert r_v3.headers.get("etag") == 'W/"e1:v3"'

    # Simulate pre_restore OSError -> must abort cleanly (500) BEFORE modifying e1:v3
    real_os_open = os.open

    def _fail_pre_restore_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if "pre_restore_" in str(path):
            raise OSError("Simulated disk full during pre_restore snapshot")
        return real_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _fail_pre_restore_open)
    r_io_err = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": vault_e1_v2, "passphrase": VAULT_PASSPHRASE, "expected_store_epoch": 1},
    )
    assert r_io_err.status_code == 500
    assert r_io_err.json()["detail"]["code"] == "PRE_RESTORE_BACKUP_IO_ERROR"
    monkeypatch.undo()

    # Verify live state was NOT touched by aborted restore
    still_v3 = _find_case(admin, cid)
    assert still_v3["version"] == 3
    assert still_v3["store_epoch"] == 1
    assert still_v3["clinical_note"] == "Ghi chú mới ở e1:v3 trước khôi phục"

    # Perform Restore #1 (preserve_current_users=True) -> state becomes e2:v2
    r_res1 = admin.post(
        "/api/admin/restore-profile-a",
        json={
            "vault_text": vault_e1_v2,
            "passphrase": VAULT_PASSPHRASE,
            "expected_store_epoch": 1,
            "preserve_current_users": True,
        },
    )
    assert r_res1.status_code == 200, r_res1.text
    assert r_res1.json()["new_store_epoch"] == 2
    assert r_res1.json()["reauthentication_required"] is False

    # Old endoscopist token from e1 is immediately rejected (401)
    assert endo.get("/api/auth/me").status_code == 401

    # Re-login endoscopist at e2; verify stale e1:v2 ETag AND legacy W/"v2" ETag both fail with 409 OCC_STORE_EPOCH_MISMATCH!
    assert endo.post("/api/auth/login", json={"username": "nguyenbinhan", "password": DEV_ENDOSCOPIST_PWD}).status_code == 200

    r_stale_epoch = endo.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"e1:v2"'},
        json={"expected_version": 2, "expected_store_epoch": 1, "clinical_note": "Ghi đè từ tab cũ e1:v2"},
    )
    assert r_stale_epoch.status_code == 409
    assert r_stale_epoch.json()["detail"]["code"] == "OCC_STORE_EPOCH_MISMATCH"

    r_legacy_etag = endo.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"v2"'},
        json={"expected_version": 2, "clinical_note": "Ghi đè không có store_epoch"},
    )
    assert r_legacy_etag.status_code == 409
    assert r_legacy_etag.json()["detail"]["code"] == "OCC_STORE_EPOCH_MISMATCH"

    # Perform Restore #2 immediately (preserve_current_users=False) -> creates 2nd distinct pre_restore_*.json and requires re-login!
    new_super_pwd = "ChangedAfterBackupSuperPass2026!"
    assert admin.post(
        "/api/auth/change-password",
        json={"current_password": DEV_SUPERADMIN_PWD, "new_password": new_super_pwd},
    ).status_code == 200

    r_res2 = admin.post(
        "/api/admin/restore-profile-a",
        json={
            "vault_text": vault_e1_v2,
            "passphrase": VAULT_PASSPHRASE,
            "expected_store_epoch": 2,
            "preserve_current_users": False,
        },
    )
    assert r_res2.status_code == 200, r_res2.text
    assert r_res2.json()["new_store_epoch"] == 3
    assert r_res2.json()["reauthentication_required"] is True
    assert admin.get("/api/auth/me").status_code == 401

    # Post-restore login requires the backup's password (DEV_SUPERADMIN_PWD), NOT new_super_pwd!
    assert admin.post("/api/auth/login", json={"username": "vukhuongan", "password": new_super_pwd}).status_code == 401
    assert admin.post("/api/auth/login", json={"username": "vukhuongan", "password": DEV_SUPERADMIN_PWD}).status_code == 200

    pre_files = sorted(cfg.backup_dir.glob("pre_restore_*.json"))
    assert len(pre_files) == 2
    assert pre_files[0].name != pre_files[1].name

    audit_ok = admin.get("/api/audit/verify").json()
    assert audit_ok["verification"]["valid"] is True
    assert audit_ok["lineage_verification"]["valid"] is True
    assert audit_ok["lineage_verification"]["bridge_count"] == 2

    # Tampering a byte in pre_restore file flips lineage_verification.valid to False
    orig_bytes = pre_files[0].read_bytes()
    pre_files[0].write_bytes(orig_bytes + b" ")
    audit_tampered = admin.get("/api/audit/verify").json()
    assert audit_tampered["lineage_verification"]["valid"] is False
    pre_files[0].write_bytes(orig_bytes)
    assert admin.get("/api/audit/verify").json()["lineage_verification"]["valid"] is True


def test_tc_g05_patient_merge_vs_episode_reconciliation_and_superseded_guards(tmp_path: Path) -> None:
    _cfg, app = _build_test_app(tmp_path / "g05_store", auto_seed=False)
    admin = _client(app)
    assert admin.post("/api/auth/local-bypass", json={"target_username": "vukhuongan"}).status_code == 200

    # Create two inpatient ERCP cases under two separate patients (different MRNs + slight birth year typo)
    r_ercp_1 = admin.post(
        "/api/cases",
        json={
            "full_name": "Võ Minh Quân",
            "birth_year": 1964,
            "sex": "M",
            "hospital_mrn": "HS26-77001",
            "care_setting": "INPATIENT",
            "admission_date": "2026-10-01",
            "referring_dept": "Khoa Ngoại Tiêu hóa",
            "track": "ERCP",
            "procedure_start_at": "2026-10-02T09:00:00+07:00",
            "indication": "BILIARY_STONE",
            "ercp_detail": {
                "papilla_status": "NATIVE_INTACT",
                "target_duct": "CBD",
                "selective_cannulation": "SUCCESS",
                "biliary_interventions": ["EST", "PLASTIC_STENT"],
            },
        },
    )
    assert r_ercp_1.status_code == 201
    c1_json = r_ercp_1.json()
    pat_target = c1_json["patient_uid"]
    ep_target = c1_json["episode_id"]
    cid_1 = c1_json["case_id"]

    r_ercp_2 = admin.post(
        "/api/cases",
        json={
            "full_name": "Võ Minh Quân",
            "birth_year": 1965,  # typo birth year to trigger demographic conflict guard
            "sex": "M",
            "hospital_mrn": "HS26-77002",  # distinct MRN to trigger distinct MRN guard
            "care_setting": "INPATIENT",
            "admission_date": "2026-10-03",
            "referring_dept": "Khoa Nội soi Tiêu hóa",
            "track": "ERCP",
            "procedure_start_at": "2026-10-05T10:30:00+07:00",
            "indication": "STENT_EXCHANGE",
            "ercp_detail": {
                "papilla_status": "PRIOR_SPHINCTEROTOMY",
                "target_duct": "CBD",
                "selective_cannulation": "SUCCESS",
                "biliary_interventions": ["STONE_EXTRACTION"],
            },
        },
    )
    assert r_ercp_2.status_code == 201
    c2_json = r_ercp_2.json()
    pat_source = c2_json["patient_uid"]
    ep_source = c2_json["episode_id"]
    cid_2 = c2_json["case_id"]

    # Create a 3rd unrelated patient with a surveillance record to test SURVEILLANCE_PATIENT_MISMATCH
    r_third = admin.post(
        "/api/cases",
        json={
            "full_name": "Đặng Thu Hà",
            "birth_year": 1971,
            "sex": "F",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-06T08:00:00+07:00",
            "indication": "SCREENING",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 9.0,
            "pathology_completion_status": "COMPLETE",
            "index_lesion": {
                "anatomical_site": "Đại tràng chậu hông",
                "size_mm": 12.0,
                "paris_class": "0-Is",
                "resection_method": "COLD_SNARE",
                "histology_type": "TUBULAR_ADENOMA",
                "dysplasia_grade": "LGD",
            },
            "whole_case_summary": {
                "macroscopic_polyp_count": 1,
                "complete_resection_all_lesions": "ALL_RESECTED_COMPLETELY",
                "any_confirmed_adenoma": "YES",
                "confirmed_adenoma_count_bin": "1_2",
                "max_adenoma_size_mm": 12.0,
            },
        },
    )
    assert r_third.status_code == 201
    third_surv_id = r_third.json()["surveillance"]["rec_id"]

    # 1. Stale expected_source_case_ids -> 409 MERGE_PRECONDITION_CONFLICT
    r_precond_fail = admin.post(
        "/api/admin/patients/merge",
        json={
            "source_patient_uid": pat_source,
            "target_patient_uid": pat_target,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [],
            "reason": "Kiểm thử xung đột danh sách ca",
        },
    )
    assert r_precond_fail.status_code == 409
    assert r_precond_fail.json()["detail"]["code"] == "MERGE_PRECONDITION_CONFLICT"

    # 2. Demographic conflict without confirmation -> 409 DEMOGRAPHIC_CONFLICT_CONFIRM_REQUIRED
    r_demo_fail = admin.post(
        "/api/admin/patients/merge",
        json={
            "source_patient_uid": pat_source,
            "target_patient_uid": pat_target,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [cid_2],
            "confirm_demographic_conflict": False,
            "reason": "Kiểm thử lệch năm sinh",
        },
    )
    assert r_demo_fail.status_code == 409
    assert r_demo_fail.json()["detail"]["code"] == "DEMOGRAPHIC_CONFLICT_CONFIRM_REQUIRED"

    # 3. Distinct MRN without override -> 409 DISTINCT_HOSPITAL_MRN_CONFLICT
    r_mrn_fail = admin.post(
        "/api/admin/patients/merge",
        json={
            "source_patient_uid": pat_source,
            "target_patient_uid": pat_target,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [cid_2],
            "confirm_demographic_conflict": True,
            "confirm_distinct_mrn_override": False,
            "reason": "Kiểm thử khác mã hồ sơ bệnh viện",
        },
    )
    assert r_mrn_fail.status_code == 409
    assert r_mrn_fail.json()["detail"]["code"] == "DISTINCT_HOSPITAL_MRN_CONFLICT"

    # 4. Authorized Patient Merge -> moves cases & episodes WITHOUT merging episodes!
    r_merge_ok = admin.post(
        "/api/admin/patients/merge",
        json={
            "source_patient_uid": pat_source,
            "target_patient_uid": pat_target,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [cid_2],
            "confirm_demographic_conflict": True,
            "resolved_birth_year": 1964,
            "confirm_distinct_mrn_override": True,
            "primary_mrn_choice": "TARGET",
            "reason": "Hợp nhất hồ sơ trùng do nhập lệch năm sinh và mã tạm cấp cứu",
        },
    )
    assert r_merge_ok.status_code == 200, r_merge_ok.text
    assert r_merge_ok.json()["profile_b_lineage_seq"] == 2

    # Zero-RM check: pat_source is still in state with status=MERGED_SUPERSEDED
    raw_state = app.state.store.read_snapshot()
    assert raw_state["patients"][pat_source]["status"] == "MERGED_SUPERSEDED"
    assert raw_state["patients"][pat_source]["merged_into_patient_uid"] == pat_target

    # G05 invariant: Patient merge MUST keep EP_1 and EP_2 separate, so both ERCP cases still have session index 1!
    c1_after_merge = _find_case(admin, cid_1)
    c2_after_merge = _find_case(admin, cid_2)
    assert c1_after_merge["episode_id"] == ep_target
    assert c2_after_merge["episode_id"] == ep_source
    assert c1_after_merge["ercp_computed"]["ercp_session_index_in_episode"] == 1
    assert c2_after_merge["ercp_computed"]["ercp_session_index_in_episode"] == 1

    # Post-merge guard: explicit patient_uid=pat_source on POST /api/cases -> 409 PATIENT_MERGED_SUPERSEDED
    r_write_merged_pat = admin.post(
        "/api/cases",
        json={
            "patient_uid": pat_source,
            "full_name": "Võ Minh Quân",
            "birth_year": 1964,
            "sex": "M",
            "care_setting": "OUTPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-08T08:00:00+07:00",
            "indication": "DIAGNOSTIC",
        },
    )
    assert r_write_merged_pat.status_code == 409
    assert r_write_merged_pat.json()["detail"]["code"] == "PATIENT_MERGED_SUPERSEDED"
    assert r_write_merged_pat.json()["detail"]["canonical_patient_uid"] == pat_target

    # Cross-patient surveillance fulfillment guard -> 422 SURVEILLANCE_PATIENT_MISMATCH
    r_surv_mismatch = admin.post(
        "/api/cases",
        json={
            "patient_uid": pat_target,
            "full_name": "Võ Minh Quân",
            "birth_year": 1964,
            "sex": "M",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-09T08:00:00+07:00",
            "indication": "SURVEILLANCE",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 8.0,
            "fulfill_surveillance_rec_id": third_surv_id,
        },
    )
    assert r_surv_mismatch.status_code == 422
    assert r_surv_mismatch.json()["detail"]["code"] == "SURVEILLANCE_PATIENT_MISMATCH"

    # Secondary MRN lookup: posting with old MRN "HS26-77002" (without explicit patient_uid) resolves to pat_target!
    r_sec_lookup = admin.post(
        "/api/cases",
        json={
            "full_name": "Võ Minh Quân",
            "birth_year": 1964,
            "sex": "M",
            "hospital_mrn": "HS26-77002",
            "care_setting": "OUTPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-10T08:30:00+07:00",
            "indication": "DIAGNOSTIC",
        },
    )
    assert r_sec_lookup.status_code == 201
    assert r_sec_lookup.json()["patient_uid"] == pat_target
    outpatient_ep = r_sec_lookup.json()["episode_id"]

    # Attempting to reconcile an OUTPATIENT episode -> 422 EPISODE_RECONCILE_INPATIENT_ONLY
    r_out_rec_fail = admin.post(
        "/api/admin/episodes/reconcile",
        json={
            "patient_uid": pat_target,
            "source_episode_id": outpatient_ep,
            "target_episode_id": ep_target,
            "expected_store_epoch": 1,
            "expected_case_ids": [cid_1, r_sec_lookup.json()["case_id"]],
            "resolved_prior_unrecorded_ercp_offset": 0,
            "reason": "Kiểm thử chặn gộp đợt ngoại trú",
        },
    )
    assert r_out_rec_fail.status_code == 422
    assert r_out_rec_fail.json()["detail"]["code"] == "EPISODE_RECONCILE_INPATIENT_ONLY"

    # 5. Episode Reconciliation on the two INPATIENT episodes (with resolved_prior_unrecorded_ercp_offset=1)
    r_rec_ok = admin.post(
        "/api/admin/episodes/reconcile",
        json={
            "patient_uid": pat_target,
            "source_episode_id": ep_source,
            "target_episode_id": ep_target,
            "expected_store_epoch": 1,
            "expected_case_ids": [cid_1, cid_2],
            "resolved_prior_unrecorded_ercp_offset": 1,
            "reason": "Cùng một đợt nhập viện chuyển từ Khoa Ngoại Tiêu hóa sang Khoa Nội soi Tiêu hóa",
        },
    )
    assert r_rec_ok.status_code == 200, r_rec_ok.text
    rec_body = r_rec_ok.json()
    assert rec_body["profile_b_lineage_seq"] == 3
    assert rec_body["ercp_session_indices"][cid_1] == 2  # 1st recorded + offset 1 = 2
    assert rec_body["ercp_session_indices"][cid_2] == 3  # 2nd recorded + offset 1 = 3

    # Verify ep_source is MERGED_SUPERSEDED (not deleted) and re-reconciling fails with 409 EPISODE_SUPERSEDED
    raw_after_rec = app.state.store.read_snapshot()
    assert raw_after_rec["episodes"][ep_source]["status"] == "MERGED_SUPERSEDED"
    assert raw_after_rec["episodes"][ep_source]["merged_into_episode_id"] == ep_target

    r_rec_again = admin.post(
        "/api/admin/episodes/reconcile",
        json={
            "patient_uid": pat_target,
            "source_episode_id": ep_source,
            "target_episode_id": ep_target,
            "expected_store_epoch": 1,
            "expected_case_ids": [cid_1, cid_2],
            "resolved_prior_unrecorded_ercp_offset": 1,
            "reason": "Thử gộp lại đợt đã đóng",
        },
    )
    assert r_rec_again.status_code == 409
    assert r_rec_again.json()["detail"]["code"] == "EPISODE_SUPERSEDED"
    assert r_rec_again.json()["detail"]["canonical_episode_id"] == ep_target


def test_tc_frontend_superadmin_and_password_modal_hooks() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    index_html = (repo_root / "src/endolog/static/index.html").read_text(encoding="utf-8")
    app_js = (repo_root / "src/endolog/static/js/app.js").read_text(encoding="utf-8")
    sw_js = (repo_root / "src/endolog/static/sw.js").read_text(encoding="utf-8")

    for required_id in (
        'id="el-btn-dev-bypass-admin"',
        'id="el-btn-change-password"',
        'id="el-superadmin-panel"',
        'id="el-superadmin-grid"',
        'id="el-password-modal-backdrop"',
        'id="el-admin-restore-file"',
        'id="el-admin-merge-source"',
        'id="el-admin-reconcile-patient"',
    ):
        assert required_id in index_html, f"Missing {required_id} in index.html"

    assert "?v=0.3.0" in index_html
    assert "v0.3.0" in sw_js
    assert "'W/\"e' + drawerState.expectedStoreEpoch + ':v' + drawerState.expectedVersion + '\"'" in app_js
    assert "expected_store_epoch" in app_js
    assert "/api/admin/restore-profile-a" in app_js
    assert "/api/admin/patients/merge" in app_js
    assert "/api/admin/episodes/reconcile" in app_js


def test_tc_adversarial_p1_regressions_delete_occ_cycles_and_mrn_hashes(tmp_path: Path) -> None:
    """Adversarial regression suite for P1-01 (DELETE OCC), P1-02 (merge pointer cycles), and P1-03 (MRN hash integrity)."""
    from endolog.clinical.export_profiles import decrypt_profile_a_vault

    _cfg, app = _build_test_app(tmp_path / "p1_adv_store", auto_seed=False)
    admin = _client(app)
    assert admin.post("/api/auth/local-bypass", json={"target_username": "vukhuongan"}).status_code == 200

    # Create two patients with mixed-case identical MRNs on separate records? Note: active MRN is deduplicated on POST,
    # so create pat_1 with lowercase MRN "hs26-9001" and pat_2 with distinct MRN "hs26-9002", plus pat_3 without MRN.
    r_c1 = admin.post(
        "/api/cases",
        json={
            "full_name": "Phạm Gia Bảo",
            "birth_year": 1972,
            "sex": "M",
            "hospital_mrn": "hs26-9001",
            "care_setting": "INPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-15T08:00:00+07:00",
            "indication": "DIAGNOSTIC",
        },
    )
    assert r_c1.status_code == 201
    pat_1 = r_c1.json()["patient_uid"]
    cid_1 = r_c1.json()["case_id"]

    r_c2 = admin.post(
        "/api/cases",
        json={
            "full_name": "Phạm Gia Bảo",
            "birth_year": 1972,
            "sex": "M",
            "hospital_mrn": "HS26-9002",
            "care_setting": "INPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-16T08:30:00+07:00",
            "indication": "DIAGNOSTIC",
        },
    )
    assert r_c2.status_code == 201
    pat_2 = r_c2.json()["patient_uid"]
    cid_2 = r_c2.json()["case_id"]

    r_c3 = admin.post(
        "/api/cases",
        json={
            "full_name": "Trần Thanh Trúc",
            "birth_year": 1984,
            "sex": "F",
            "care_setting": "OUTPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-17T09:00:00+07:00",
            "indication": "DIAGNOSTIC",
        },
    )
    assert r_c3.status_code == 201
    pat_3 = r_c3.json()["patient_uid"]

    # Merge pat_2 -> pat_1 so pat_1 acquires a secondary MRN ("HS26-9002")
    r_merge = admin.post(
        "/api/admin/patients/merge",
        json={
            "source_patient_uid": pat_2,
            "target_patient_uid": pat_1,
            "expected_store_epoch": 1,
            "source_expected_version": 1,
            "target_expected_version": 1,
            "expected_source_case_ids": [cid_2],
            "confirm_distinct_mrn_override": True,
            "primary_mrn_choice": "TARGET",
            "reason": "Hợp nhất hồ sơ kiểm thử đối kháng P1-03",
        },
    )
    assert r_merge.status_code == 200

    # Export valid Profile A backup (with crypto_context matching current server)
    r_exp = admin.post("/api/exports/profile-a", json={"passphrase": VAULT_PASSPHRASE})
    assert r_exp.status_code == 200
    vault_bytes = r_exp.content
    vault_plain = decrypt_profile_a_vault(vault_bytes, VAULT_PASSPHRASE)

    # [P1-02] 2-node MERGED_SUPERSEDED cycle (pat_1 <-> pat_2) -> 422 NON_CANONICAL_MERGED_PATIENT_TARGET
    mut_cycle = json.loads(json.dumps(vault_plain))
    mut_cycle["patients"][pat_1]["status"] = "MERGED_SUPERSEDED"
    mut_cycle["patients"][pat_1]["merged_into_patient_uid"] = pat_2
    mut_cycle["patients"][pat_2]["status"] = "MERGED_SUPERSEDED"
    mut_cycle["patients"][pat_2]["merged_into_patient_uid"] = pat_1
    r_cycle = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_cycle, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_cycle.status_code == 422
    assert r_cycle.json()["detail"]["code"] == "NON_CANONICAL_MERGED_PATIENT_TARGET"

    # [P1-02] ACTIVE patient carrying non-null merged_into_patient_uid -> 422 INVALID_ACTIVE_PATIENT_MERGE_POINTER
    mut_active_ptr = json.loads(json.dumps(vault_plain))
    mut_active_ptr["patients"][pat_1]["merged_into_patient_uid"] = pat_3
    r_active_ptr = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_active_ptr, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_active_ptr.status_code == 422
    assert r_active_ptr.json()["detail"]["code"] == "INVALID_ACTIVE_PATIENT_MERGE_POINTER"

    # [P1-03] Tampered secondary_mrn_hashes when keys_match=True -> 422 SECONDARY_MRN_HASH_INTEGRITY_MISMATCH
    mut_sec_hash = json.loads(json.dumps(vault_plain))
    mut_sec_hash["patients"][pat_1]["secondary_mrn_hashes"] = ["a" * 64]
    r_sec_hash = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_sec_hash, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_sec_hash.status_code == 422
    assert r_sec_hash.json()["detail"]["code"] == "SECONDARY_MRN_HASH_INTEGRITY_MISMATCH"

    # [P1-03] Orphan hospital_mrn_hash when hospital_mrn is None -> 422 MRN_HASH_INTEGRITY_MISMATCH
    mut_orphan_hash = json.loads(json.dumps(vault_plain))
    mut_orphan_hash["patients"][pat_3]["hospital_mrn"] = None
    mut_orphan_hash["patients"][pat_3]["hospital_mrn_hash"] = "b" * 64
    r_orphan_hash = admin.post(
        "/api/admin/restore-profile-a",
        json={"vault_text": _reencrypt_vault_plaintext(mut_orphan_hash, VAULT_PASSPHRASE), "passphrase": VAULT_PASSPHRASE},
    )
    assert r_orphan_hash.status_code == 422
    assert r_orphan_hash.json()["detail"]["code"] == "MRN_HASH_INTEGRITY_MISMATCH"

    # [P1-01] Restore valid backup to advance store_epoch -> 2, then verify DELETE /api/cases/{id} enforces If-Match OCC
    r_restore_ok = admin.post(
        "/api/admin/restore-profile-a",
        json={
            "vault_text": vault_bytes.decode("utf-8"),
            "passphrase": VAULT_PASSPHRASE,
            "expected_store_epoch": 1,
            "preserve_current_users": True,
        },
    )
    assert r_restore_ok.status_code == 200
    assert r_restore_ok.json()["new_store_epoch"] == 2

    # Missing If-Match at store_epoch=2 -> 409 OCC_STORE_EPOCH_MISMATCH
    r_del_no_etag = admin.delete(f"/api/cases/{cid_1}")
    assert r_del_no_etag.status_code == 409
    assert r_del_no_etag.json()["detail"]["code"] == "OCC_STORE_EPOCH_MISMATCH"

    # Stale epoch W/"e1:v1" -> 409 OCC_STORE_EPOCH_MISMATCH
    r_del_stale_epoch = admin.delete(f"/api/cases/{cid_1}", headers={"If-Match": 'W/"e1:v1"'})
    assert r_del_stale_epoch.status_code == 409
    assert r_del_stale_epoch.json()["detail"]["code"] == "OCC_STORE_EPOCH_MISMATCH"

    # Stale version W/"e2:v99" -> 409 OCC_VERSION_CONFLICT
    r_del_stale_ver = admin.delete(f"/api/cases/{cid_1}", headers={"If-Match": 'W/"e2:v99"'})
    assert r_del_stale_ver.status_code == 409
    assert r_del_stale_ver.json()["detail"]["code"] == "OCC_VERSION_CONFLICT"

    # Matching W/"e2:v1" -> 200 SUPERSEDED
    r_del_ok = admin.delete(f"/api/cases/{cid_1}", headers={"If-Match": 'W/"e2:v1"'})
    assert r_del_ok.status_code == 200
    assert r_del_ok.json()["record_status"] == "SUPERSEDED"

