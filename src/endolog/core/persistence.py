"""Single v1.0 runtime storage engine: AtomicJsonStore with 2-tier lock + Write-Ahead Rollback Journal."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import secrets
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

import fasteners

from endolog.core.audit import build_audit_entry
from endolog.core.security import hash_password


def _chmod_safe(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _fsync_dir(directory: Path) -> None:
    try:
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def _strict_fsync_dir(directory: Path) -> None:
    fd = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def normalize_state_compat(
    state: dict[str, Any],
    *,
    default_kpi_min_sample_size: int = 20,
) -> dict[str, Any]:
    """Deterministic compatibility upgrade for v1.0.0 / v1.1.0 state snapshots."""
    state.setdefault("schema_version", "1.0.0")
    state["store_epoch"] = max(1, int(state.get("store_epoch", 1) or 1))
    if not isinstance(state.get("revoked_jtis"), dict):
        state["revoked_jtis"] = {}
    if not isinstance(state.get("audit_lineage_bridges"), list):
        state["audit_lineage_bridges"] = []

    cfg = state.setdefault("settings", {})
    cfg.setdefault("default_operator_name", "ThS. BSCKI. Nguyễn Bình An")
    cfg.setdefault("colo_guideline_mode", "USMSTF_2020")
    cfg.setdefault("adr_min_age", 45)
    cfg.setdefault("cusum_preset", "DEFAULT_90")
    cfg.setdefault("kpi_min_sample_size", max(1, int(default_kpi_min_sample_size)))
    cfg["export_dataset_epoch"] = max(1, int(cfg.get("export_dataset_epoch", 1) or 1))
    cfg["profile_b_lineage_seq"] = max(1, int(cfg.get("profile_b_lineage_seq", 1) or 1))

    for u_obj in (state.get("users") or {}).values():
        if isinstance(u_obj, dict):
            u_obj["auth_version"] = max(1, int(u_obj.get("auth_version", 1) or 1))

    for p_obj in (state.get("patients") or {}).values():
        if isinstance(p_obj, dict):
            p_obj["version"] = max(1, int(p_obj.get("version", 1) or 1))
            p_obj.setdefault("status", "ACTIVE")
            if not isinstance(p_obj.get("secondary_mrn_hashes"), list):
                p_obj["secondary_mrn_hashes"] = []
            if not isinstance(p_obj.get("secondary_mrns"), list):
                p_obj["secondary_mrns"] = []
            if not isinstance(p_obj.get("merged_from_aliases"), list):
                p_obj["merged_from_aliases"] = []

    for ep_obj in (state.get("episodes") or {}).values():
        if isinstance(ep_obj, dict):
            ep_obj.setdefault("status", "ACTIVE")

    return state


def default_initial_state(
    default_bootstrap_passwords: dict[str, str] | None = None,
    *,
    default_kpi_min_sample_size: int = 20,
) -> dict[str, Any]:
    pw_map = default_bootstrap_passwords or {
        "vukhuongan": "EndoLog!Superadmin#2026",
        "nguyenbinhan": "EndoLog!BinhAn#2026",
    }
    now_iso = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    users = {
        "vukhuongan": {
            "username": "vukhuongan",
            "display_name": "BSCKII. Vũ Khương An",
            "role": "superadmin",
            "department": "Khoa Phẫu thuật Đại trực tràng — Bệnh viện Bình Dân",
            "password_hash": hash_password(pw_map["vukhuongan"]),
            "active": True,
            "auth_version": 1,
            "created_at": now_iso,
        },
        "nguyenbinhan": {
            "username": "nguyenbinhan",
            "display_name": "ThS. BSCKI. Nguyễn Bình An",
            "role": "endoscopist",
            "department": "Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân",
            "password_hash": hash_password(pw_map["nguyenbinhan"]),
            "active": True,
            "auth_version": 1,
            "created_at": now_iso,
        },
    }
    chain: list[dict[str, Any]] = []
    chain.append(
        build_audit_entry(
            chain,
            actor_username="system",
            actor_role="system",
            action="STORE_BOOTSTRAP",
            entity_type="STORE",
            entity_id="endolog_state_v1",
            detail={"schema_version": "1.1.0"},
            now_utc=now_iso,
        )
    )
    return {
        "schema_version": "1.1.0",
        "store_epoch": 1,
        "revoked_jtis": {},
        "audit_lineage_bridges": [],
        "settings": {
            "default_operator_name": "ThS. BSCKI. Nguyễn Bình An",
            "colo_guideline_mode": "USMSTF_2020",
            "adr_min_age": 45,
            "cusum_preset": "DEFAULT_90",
            "kpi_min_sample_size": max(1, int(default_kpi_min_sample_size)),
            "export_dataset_epoch": 1,
            "profile_b_lineage_seq": 1,
        },
        "users": users,
        "patients": {},
        "episodes": {},
        "cases": {},
        "surveillance": {},
        "counters": {},
        "audit_chain": chain,
    }


class AtomicJsonStore:
    """Thread-safe and inter-process-safe JSON store with WAL rollback recovery and hourly snapshots."""

    def __init__(
        self,
        data_dir: Path,
        backup_dir: Path,
        *,
        bootstrap_passwords: dict[str, str] | None = None,
        default_kpi_min_sample_size: int = 20,
    ) -> None:
        self.data_dir = data_dir.resolve()
        self.backup_dir = backup_dir.resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        _chmod_safe(self.data_dir, 0o700)
        _chmod_safe(self.backup_dir, 0o700)

        self.state_path = self.data_dir / "endolog_state.json"
        self.wal_path = self.data_dir / "endolog_state.rollback.wal.json"
        self.lock_path = self.data_dir / "endolog_state.lock"
        self._thread_lock = threading.RLock()
        self._ipc_lock = fasteners.InterProcessLock(str(self.lock_path))
        self._bootstrap_passwords = bootstrap_passwords
        self._default_kpi_min_sample_size = max(1, int(default_kpi_min_sample_size))

        with self._exclusive_lock():
            self._recover_if_interrupted()
            if not self.state_path.exists():
                initial = default_initial_state(
                    self._bootstrap_passwords,
                    default_kpi_min_sample_size=self._default_kpi_min_sample_size,
                )
                self._atomic_write_json(self.state_path, initial)

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        with self._thread_lock:
            self._ipc_lock.acquire()
            try:
                yield
            finally:
                self._ipc_lock.release()

    def _recover_if_interrupted(self) -> None:
        if not self.wal_path.exists():
            return
        try:
            rollback_state = json.loads(self.wal_path.read_text(encoding="utf-8"))
            if not self.state_path.exists():
                self._atomic_write_json(self.state_path, rollback_state)
            else:
                # Verify main state parses cleanly; otherwise restore rollback WAL
                try:
                    json.loads(self.state_path.read_text(encoding="utf-8"))
                except Exception:
                    self._atomic_write_json(self.state_path, rollback_state)
        finally:
            quarantine = self.backup_dir / f"recovered_wal_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            shutil.move(str(self.wal_path), str(quarantine))
            _chmod_safe(quarantine, 0o600)

    def _atomic_write_json(self, target: Path, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(serialized)
                fh.flush()
                os.fsync(fh.fileno())
            _chmod_safe(tmp_path, 0o600)
            os.replace(str(tmp_path), str(target))
            _chmod_safe(target, 0o600)
            _fsync_dir(target.parent)
        except Exception:
            if tmp_path.exists():
                quarantine = self.backup_dir / f"failed_tmp_{tmp_path.name}"
                shutil.move(str(tmp_path), str(quarantine))
            raise

    def _maybe_hourly_snapshot(self) -> None:
        if not self.state_path.exists():
            return
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H")
        snap_path = self.backup_dir / f"snapshot_{stamp}.json"
        if not snap_path.exists():
            shutil.copy2(str(self.state_path), str(snap_path))
            _chmod_safe(snap_path, 0o600)

    def read_snapshot(self) -> dict[str, Any]:
        with self._exclusive_lock():
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return normalize_state_compat(
                copy.deepcopy(raw),
                default_kpi_min_sample_size=self._default_kpi_min_sample_size,
            )

    def transact(self, mutator: Callable[[dict[str, Any]], Any]) -> Any:
        with self._exclusive_lock():
            current = json.loads(self.state_path.read_text(encoding="utf-8"))
            working = normalize_state_compat(
                copy.deepcopy(current),
                default_kpi_min_sample_size=self._default_kpi_min_sample_size,
            )
            result = mutator(working)
            # Write rollback journal before replacing primary state
            self._atomic_write_json(self.wal_path, current)
            self._atomic_write_json(self.state_path, working)
            # Archive clean WAL by overwriting single latest_clean_wal marker (Zero-RM compliant)
            clean_wal_slot = self.backup_dir / "latest_committed_rollback.json"
            os.replace(str(self.wal_path), str(clean_wal_slot))
            _chmod_safe(clean_wal_slot, 0o600)
            self._maybe_hourly_snapshot()
            return result

    def restore_vault_atomic(
        self,
        prepare_restore: Callable[
            [dict[str, Any]],
            tuple[dict[str, Any], Callable[[dict[str, Any], str, str], Any]],
        ],
    ) -> Any:
        """Atomic vault restore holding _exclusive_lock end-to-end with O_EXCL pre_restore backup (G04)."""
        with self._exclusive_lock():
            current = json.loads(self.state_path.read_text(encoding="utf-8"))
            live_norm = normalize_state_compat(
                copy.deepcopy(current),
                default_kpi_min_sample_size=self._default_kpi_min_sample_size,
            )
            candidate_state, finalize_fn = prepare_restore(live_norm)

            utc_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            rand_hex = secrets.token_hex(4)
            pre_restore_filename = f"pre_restore_{utc_stamp}_{rand_hex}.json"
            pre_restore_path = self.backup_dir / pre_restore_filename
            pre_restore_bytes = json.dumps(current, ensure_ascii=False, indent=2).encode("utf-8")
            pre_restore_sha256 = hashlib.sha256(pre_restore_bytes).hexdigest()

            fd = os.open(str(pre_restore_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as fh:
                fh.write(pre_restore_bytes)
                fh.flush()
                os.fsync(fh.fileno())
            _chmod_safe(pre_restore_path, 0o600)
            _strict_fsync_dir(self.backup_dir)

            result = finalize_fn(candidate_state, pre_restore_filename, pre_restore_sha256)

            self._atomic_write_json(self.wal_path, current)
            self._atomic_write_json(self.state_path, candidate_state)
            clean_wal_slot = self.backup_dir / "latest_committed_rollback.json"
            os.replace(str(self.wal_path), str(clean_wal_slot))
            _chmod_safe(clean_wal_slot, 0o600)
            self._maybe_hourly_snapshot()
            return result
