"""Phase 1 negative security matrix: fail-closed ENDOLOG_ENV, 5-latch local bypass, DLP, and Linear Hash Chain."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from endolog.core.audit import build_audit_entry, verify_audit_chain
from endolog.core.config import DEV_JWT_FALLBACK, EndoLogSettings, load_settings
from endolog.core.dlp import DlpViolationError, scan_payload_notes
from endolog.main import create_app


def _make_settings(
    tmp_path: Path,
    *,
    env_mode: str = "local_dev_synthetic",
    enable_dev_bypass: bool = True,
    bind_host: str = "127.0.0.1",
    data_subdir: str = "data_synthetic_dev",
    phi_marker: bool = False,
) -> EndoLogSettings:
    d_dir = tmp_path / data_subdir
    d_dir.mkdir(parents=True, exist_ok=True)
    if phi_marker:
        (d_dir / ".phi_vault_marker").write_text("PHI_VAULT", encoding="utf-8")
    b_dir = tmp_path / "data_backups"
    b_dir.mkdir(parents=True, exist_ok=True)
    return EndoLogSettings(
        env_mode=env_mode,  # type: ignore[arg-type]
        enable_dev_bypass=enable_dev_bypass,
        bind_host=bind_host,
        data_dir=d_dir,
        backup_dir=b_dir,
        jwt_secret="test-jwt-secret-key-at-least-32-characters-long",
        master_research_key=b"test-master-research-key-32bytes!",
        shift_key=b"test-shift-research-key-32-bytes!",
    )


def test_startup_rejects_phi_marker_in_synthetic_dev(tmp_path: Path) -> None:
    cfg = _make_settings(tmp_path, phi_marker=True)
    with pytest.raises(RuntimeError, match="FAIL_CLOSED_STARTUP"):
        cfg.validate_startup_safety()


def test_startup_rejects_default_jwt_in_production(tmp_path: Path) -> None:
    d_dir = tmp_path / "data"
    b_dir = tmp_path / "data_backups"
    cfg = EndoLogSettings(
        env_mode="production",
        enable_dev_bypass=False,
        bind_host="127.0.0.1",
        data_dir=d_dir,
        backup_dir=b_dir,
        jwt_secret=DEV_JWT_FALLBACK,
        master_research_key=b"prod-unique-master-research-key-32b",
        shift_key=b"prod-unique-shift-research-key-32b!",
    )
    with pytest.raises(RuntimeError, match="FAIL_CLOSED_STARTUP"):
        cfg.validate_startup_safety()


def test_missing_env_defaults_to_unconfigured_fail_closed(tmp_path: Path) -> None:
    cfg = load_settings({"ENDOLOG_DATA_DIR": str(tmp_path / "data"), "ENDOLOG_BACKUP_DIR": str(tmp_path / "bak")})
    assert cfg.env_mode == "unconfigured_fail_closed"


def test_local_bypass_five_latch_negative_matrix(tmp_path: Path) -> None:
    # 1. Valid synthetic loopback -> 200 OK
    valid_cfg = _make_settings(tmp_path / "s1")
    app_ok = create_app(valid_cfg, auto_seed_synthetic=False)
    client_ok = TestClient(app_ok, client=("127.0.0.1", 51000), base_url="http://localhost")
    r_ok = client_ok.post("/api/auth/local-bypass")
    assert r_ok.status_code == 200
    assert r_ok.headers["Cache-Control"].startswith("no-store")
    assert "default-src 'self'" in r_ok.headers["Content-Security-Policy"]

    # 2. Proxy header present -> 403
    r_proxy = client_ok.post("/api/auth/local-bypass", headers={"X-Forwarded-For": "203.0.113.8"})
    assert r_proxy.status_code == 403
    assert r_proxy.json()["detail"]["code"] == "403_PROXY_HEADER_PRESENT"

    # 3. Untrusted .local mDNS Host header -> 403
    r_mdns = client_ok.post("/api/auth/local-bypass", headers={"Host": "macbook.local:8000"})
    assert r_mdns.status_code == 403
    assert r_mdns.json()["detail"]["code"] == "403_UNTRUSTED_HOST_HEADER"

    # 4. Non-loopback LAN client IP -> 403
    client_lan = TestClient(app_ok, client=("192.168.1.44", 51001), base_url="http://localhost")
    r_lan = client_lan.post("/api/auth/local-bypass")
    assert r_lan.status_code == 403
    assert r_lan.json()["detail"]["code"] == "403_NON_LOOPBACK_CLIENT"

    # 5. Bind 0.0.0.0 -> 403
    cfg_zero = _make_settings(tmp_path / "s2", bind_host="0.0.0.0")
    app_zero = create_app(cfg_zero, auto_seed_synthetic=False)
    r_zero = TestClient(app_zero, client=("127.0.0.1", 51002), base_url="http://localhost").post(
        "/api/auth/local-bypass"
    )
    assert r_zero.status_code == 403
    assert r_zero.json()["detail"]["code"] == "403_NON_LOOPBACK_BIND"

    # 6. local_clinical_phi mode -> 403
    cfg_phi = _make_settings(tmp_path / "s3", env_mode="local_clinical_phi", data_subdir="data_real_clinical")
    app_phi = create_app(cfg_phi, auto_seed_synthetic=False)
    r_phi = TestClient(app_phi, client=("127.0.0.1", 51003), base_url="http://localhost").post(
        "/api/auth/local-bypass"
    )
    assert r_phi.status_code == 403
    assert r_phi.json()["detail"]["code"] == "403_ENV_NOT_SYNTHETIC_DEV"


def test_dlp_blocks_cccd_phone_bhyt_and_email() -> None:
    with pytest.raises(DlpViolationError) as e1:
        scan_payload_notes({"clinical_note": "BN có CCCD 079085001234 cần lưu ý"})
    assert e1.value.rule_code == "CCCD_12_DIGITS"

    with pytest.raises(DlpViolationError) as e2:
        scan_payload_notes({"clinical_note": "Gọi số 0909123456 khi có GPB"})
    assert e2.value.rule_code == "VN_PHONE_NUMBER"

    with pytest.raises(DlpViolationError) as e3:
        scan_payload_notes({"ercp_detail": {"ercp_procedure_note": "Mã thẻ DN4797912345678"}})
    assert e3.value.rule_code == "BHYT_CARD_CODE"


def test_linear_hash_chain_detects_tampering() -> None:
    chain = []
    chain.append(
        build_audit_entry(
            chain,
            actor_username="vukhuongan",
            actor_role="superadmin",
            action="INIT",
            entity_type="STORE",
            entity_id="1",
            detail={"ok": True},
        )
    )
    chain.append(
        build_audit_entry(
            chain,
            actor_username="nguyenbinhan",
            actor_role="endoscopist",
            action="CASE_CREATE",
            entity_type="ENDOSCOPY_CASE",
            entity_id="cas_1",
            detail={"case_code": "COL-2026-0001"},
        )
    )
    assert verify_audit_chain(chain)["valid"] is True
    chain[1]["detail"]["case_code"] = "COL-2026-9999"
    tampered = verify_audit_chain(chain)
    assert tampered["valid"] is False
    assert tampered["reason"] == "ENTRY_HASH_TAMPERED"
