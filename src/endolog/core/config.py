"""Fail-closed environment configuration for EndoLog (Rule v2:R41 + Zero-PHI Isolation)."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ValidEnvMode = Literal[
    "local_dev_synthetic",
    "local_clinical_phi",
    "production",
    "unconfigured_fail_closed",
]

DEV_JWT_FALLBACK = "endolog-local-dev-only-jwt-secret-not-for-prod-32b"
DEV_RESEARCH_FALLBACK = "endolog-local-dev-only-research-hmac-key-32bytes"
DEV_SHIFT_FALLBACK = "endolog-local-dev-only-date-shift-hmac-key-32b"
SESSION_TIMEOUT_SECONDS = 15 * 60  # 15 minutes strict idle/token lifetime
DEFAULT_KPI_MIN_SAMPLE_SIZE = 20  # Default minimum denominator n_min for personal KPI proportions


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class EndoLogSettings:
    env_mode: ValidEnvMode
    enable_dev_bypass: bool
    bind_host: str
    data_dir: Path
    backup_dir: Path
    jwt_secret: str
    master_research_key: bytes
    shift_key: bytes
    session_timeout_seconds: int = SESSION_TIMEOUT_SECONDS
    kpi_min_sample_size: int = DEFAULT_KPI_MIN_SAMPLE_SIZE

    @property
    def has_phi_vault_marker(self) -> bool:
        return (self.data_dir / ".phi_vault_marker").exists()

    @property
    def mrn_key_fp(self) -> str:
        return hmac.new(self.master_research_key, b"endolog-fp:mrn:v1", hashlib.sha256).hexdigest()[:16]

    @property
    def shift_key_fp(self) -> str:
        return hmac.new(self.shift_key, b"endolog-fp:shift:v1", hashlib.sha256).hexdigest()[:16]

    def build_crypto_context(self, export_dataset_epoch: int = 1) -> dict[str, Any]:
        return {
            "mrn_key_fp": self.mrn_key_fp,
            "shift_key_fp": self.shift_key_fp,
            "export_dataset_epoch": max(1, int(export_dataset_epoch)),
        }

    def validate_startup_safety(self) -> None:
        """Enforce fail-closed isolation invariants before serving requests."""
        if self.env_mode == "local_dev_synthetic":
            if self.data_dir.name != "data_synthetic_dev":
                raise RuntimeError(
                    "FAIL_CLOSED_STARTUP: local_dev_synthetic bắt buộc trỏ vào thư mục tên 'data_synthetic_dev'."
                )
            if self.has_phi_vault_marker:
                raise RuntimeError(
                    "FAIL_CLOSED_STARTUP: Phát hiện '.phi_vault_marker' trong kho dữ liệu khi chạy local_dev_synthetic."
                )

        if self.env_mode == "production":
            if self.enable_dev_bypass:
                raise RuntimeError("FAIL_CLOSED_STARTUP: Cấm bật ENDOLOG_ENABLE_DEV_BYPASS trên production.")
            if self.jwt_secret == DEV_JWT_FALLBACK or len(self.jwt_secret) < 32:
                raise RuntimeError("FAIL_CLOSED_STARTUP: Production yêu cầu ENDOLOG_JWT_SECRET riêng >= 32 ký tự.")
            if (
                self.master_research_key == DEV_RESEARCH_FALLBACK.encode("utf-8")
                or len(self.master_research_key) < 32
            ):
                raise RuntimeError(
                    "FAIL_CLOSED_STARTUP: Production yêu cầu ENDOLOG_MASTER_RESEARCH_KEY riêng >= 32 byte."
                )


def load_settings(environ: dict[str, str] | None = None) -> EndoLogSettings:
    env_map = os.environ if environ is None else environ
    raw_env = (env_map.get("ENDOLOG_ENV") or "").strip()
    if raw_env in ("local_dev_synthetic", "local_clinical_phi", "production"):
        env_mode: ValidEnvMode = raw_env  # type: ignore[assignment]
    else:
        env_mode = "unconfigured_fail_closed"

    root = repo_root()
    raw_data_dir = (env_map.get("ENDOLOG_DATA_DIR") or "").strip()
    if raw_data_dir:
        data_dir = Path(raw_data_dir).expanduser().resolve()
    elif env_mode == "local_dev_synthetic":
        data_dir = (root / "data_synthetic_dev").resolve()
    elif env_mode == "local_clinical_phi":
        data_dir = (root / "data_real_clinical").resolve()
    else:
        data_dir = (root / "data").resolve()

    raw_backup_dir = (env_map.get("ENDOLOG_BACKUP_DIR") or "").strip()
    backup_dir = (
        Path(raw_backup_dir).expanduser().resolve()
        if raw_backup_dir
        else (root / "data_backups").resolve()
    )

    enable_dev_bypass = (env_map.get("ENDOLOG_ENABLE_DEV_BYPASS") or "").strip() == "1"
    bind_host = (env_map.get("ENDOLOG_BIND_HOST") or "127.0.0.1").strip()
    jwt_secret = (env_map.get("ENDOLOG_JWT_SECRET") or DEV_JWT_FALLBACK).strip()
    research_key = (env_map.get("ENDOLOG_MASTER_RESEARCH_KEY") or DEV_RESEARCH_FALLBACK).encode("utf-8")
    shift_key = (env_map.get("ENDOLOG_SHIFT_KEY") or DEV_SHIFT_FALLBACK).encode("utf-8")
    raw_n_min = (env_map.get("ENDOLOG_KPI_MIN_SAMPLE_SIZE") or "").strip()
    kpi_min_sample_size = max(1, int(raw_n_min)) if raw_n_min.isdigit() else DEFAULT_KPI_MIN_SAMPLE_SIZE

    settings = EndoLogSettings(
        env_mode=env_mode,
        enable_dev_bypass=enable_dev_bypass,
        bind_host=bind_host,
        data_dir=data_dir,
        backup_dir=backup_dir,
        jwt_secret=jwt_secret,
        master_research_key=research_key,
        shift_key=shift_key,
        kpi_min_sample_size=kpi_min_sample_size,
    )
    settings.validate_startup_safety()
    return settings
