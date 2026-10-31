"""Single v1.0 runtime storage engine: AtomicJsonStore with 2-tier lock + Write-Ahead Rollback Journal."""

from __future__ import annotations

import copy
import datetime as dt
import json
import os
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


def default_initial_state(default_bootstrap_passwords: dict[str, str] | None = None) -> dict[str, Any]:
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
            "created_at": now_iso,
        },
        "nguyenbinhan": {
            "username": "nguyenbinhan",
            "display_name": "ThS. BSCKI. Nguyễn Bình An",
            "role": "endoscopist",
            "department": "Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân",
            "password_hash": hash_password(pw_map["nguyenbinhan"]),
            "active": True,
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
            detail={"schema_version": "1.0.0"},
            now_utc=now_iso,
        )
    )
    return {
        "schema_version": "1.0.0",
        "settings": {
            "default_operator_name": "ThS. BSCKI. Nguyễn Bình An",
            "colo_guideline_mode": "USMSTF_2020",
            "adr_min_age": 45,
            "cusum_preset": "DEFAULT_90",
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

        with self._exclusive_lock():
            self._recover_if_interrupted()
            if not self.state_path.exists():
                initial = default_initial_state(self._bootstrap_passwords)
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
            return copy.deepcopy(raw)

    def transact(self, mutator: Callable[[dict[str, Any]], Any]) -> Any:
        with self._exclusive_lock():
            current = json.loads(self.state_path.read_text(encoding="utf-8"))
            working = copy.deepcopy(current)
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
