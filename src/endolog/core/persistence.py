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


class RestorePreCommitIOError(OSError):
    """Raised when an I/O fault occurs strictly BEFORE replacing endolog_state.json (committed=False, C01)."""

    def __init__(self, *, code: str, stage: str, message: str) -> None:
        self.code = code
        self.stage = stage
        self.committed = False
        self.message = message
        super().__init__(message)


class LineageArtifactCollisionError(ValueError):
    """Raised when backup_dir already contains a pre_restore_*.json with a conflicting SHA-256 (HTTP 409, C02)."""

    def __init__(self, filename: str) -> None:
        self.code = "LINEAGE_ARTIFACT_COLLISION"
        self.filename = filename
        self.message = (
            f"Tệp bằng chứng lịch sử '{filename}' trên máy chủ đích đã tồn tại nhưng mang mã băm SHA-256 khác; "
            "đã hủy giao dịch trước điểm commit để bảo toàn bằng chứng hiện có."
        )
        super().__init__(self.message)


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

    def _quarantine_best_effort(self, path: Path, prefix: str) -> None:
        if not path.exists():
            return
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        q_path = self.backup_dir / f"{prefix}_{stamp}_{secrets.token_hex(4)}_{path.name}"
        try:
            shutil.move(str(path), str(q_path))
            _chmod_safe(q_path, 0o600)
        except OSError:
            pass

    def _recover_if_interrupted(self) -> None:
        if not self.wal_path.exists():
            return
        try:
            state_valid = False
            if self.state_path.exists():
                try:
                    parsed_main = json.loads(self.state_path.read_text(encoding="utf-8"))
                    state_valid = isinstance(parsed_main, dict)
                except Exception:
                    state_valid = False
            if not state_valid:
                rollback_state = json.loads(self.wal_path.read_text(encoding="utf-8"))
                self._atomic_write_json(self.state_path, rollback_state)
        finally:
            self._quarantine_best_effort(self.wal_path, "recovered_wal")

    def _stage_temp_bytes(self, directory: Path, *, prefix: str, raw_bytes: bytes) -> Path:
        fd, tmp_name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=str(directory))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw_bytes)
                fh.flush()
                os.fsync(fh.fileno())
            _chmod_safe(tmp_path, 0o600)
            return tmp_path
        except Exception:
            if tmp_path.exists():
                self._quarantine_best_effort(tmp_path, "failed_tmp")
            raise

    def _stage_temp_json(self, target: Path, payload: dict[str, Any]) -> Path:
        raw_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self._stage_temp_bytes(target.parent, prefix=f".{target.name}.", raw_bytes=raw_bytes)

    def _atomic_write_json(self, target: Path, payload: dict[str, Any]) -> None:
        tmp_path = self._stage_temp_json(target, payload)
        try:
            os.replace(str(tmp_path), str(target))
        except Exception:
            if tmp_path.exists():
                self._quarantine_best_effort(tmp_path, "failed_tmp")
            raise
        _chmod_safe(target, 0o600)
        _fsync_dir(target.parent)

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
            if self.wal_path.exists():
                self._quarantine_best_effort(self.wal_path, "stale_wal")
            working = normalize_state_compat(
                copy.deepcopy(current),
                default_kpi_min_sample_size=self._default_kpi_min_sample_size,
            )
            result = mutator(working)
            # Write rollback journal before replacing primary state
            self._atomic_write_json(self.wal_path, current)
            self._atomic_write_json(self.state_path, working)
            # Post-commit housekeeping (Zero-RM compliant; state_path is already committed)
            clean_wal_slot = self.backup_dir / "latest_committed_rollback.json"
            try:
                os.replace(str(self.wal_path), str(clean_wal_slot))
                _chmod_safe(clean_wal_slot, 0o600)
            except OSError:
                pass
            try:
                self._maybe_hourly_snapshot()
            except OSError:
                pass
            return result

    def restore_vault_atomic(
        self,
        prepare_restore: Callable[
            [dict[str, Any]],
            tuple[dict[str, Any], Callable[[dict[str, Any], str, str], Any]],
        ],
        *,
        imported_lineage_files: dict[str, bytes] | None = None,
    ) -> Any:
        """Atomic vault restore with explicit pre-commit vs post-commit boundary & portable lineage materialization (G04, C01, C02)."""
        with self._exclusive_lock():
            try:
                current = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RestorePreCommitIOError(
                    code="RESTORE_STATE_READ_ABORTED",
                    stage="live_state_read",
                    message="Không thể đọc trạng thái kho hiện hành trước khôi phục; đã hủy giao dịch trước điểm commit.",
                ) from exc

            if self.wal_path.exists():
                self._quarantine_best_effort(self.wal_path, "stale_wal")

            live_norm = normalize_state_compat(
                copy.deepcopy(current),
                default_kpi_min_sample_size=self._default_kpi_min_sample_size,
            )
            candidate_state, finalize_fn = prepare_restore(live_norm)

            newly_materialized: list[Path] = []
            pre_restore_path: Path | None = None
            wal_written = False

            def _cleanup_pre_commit() -> None:
                if pre_restore_path is not None:
                    self._quarantine_best_effort(pre_restore_path, "aborted_pre_restore")
                for mat_path in newly_materialized:
                    self._quarantine_best_effort(mat_path, "aborted_imported")
                if wal_written and self.wal_path.exists():
                    self._quarantine_best_effort(self.wal_path, "aborted_wal")

            # Pre-commit Step 1: Materialize imported portable lineage pre_restore_*.json files atomically (C02, R2-03)
            for fname, raw_bytes in (imported_lineage_files or {}).items():
                dest_path = self.backup_dir / fname
                expected_sha = hashlib.sha256(raw_bytes).hexdigest()
                if dest_path.exists():
                    try:
                        existing_bytes = dest_path.read_bytes()
                    except OSError as exc:
                        _cleanup_pre_commit()
                        raise RestorePreCommitIOError(
                            code="PRE_RESTORE_BACKUP_IO_ERROR",
                            stage="imported_lineage_verify",
                            message="Không thể xác minh tệp bằng chứng lịch sử trên máy chủ đích; đã hủy giao dịch trước điểm commit để bảo toàn dữ liệu hiện hành.",
                        ) from exc
                    if hashlib.sha256(existing_bytes).hexdigest() != expected_sha:
                        _cleanup_pre_commit()
                        raise LineageArtifactCollisionError(fname)
                else:
                    staged_imp: Path | None = None
                    try:
                        staged_imp = self._stage_temp_bytes(
                            self.backup_dir,
                            prefix=f".{fname}.",
                            raw_bytes=raw_bytes,
                        )
                        if dest_path.exists():
                            raise FileExistsError(f"Destination {fname} appeared concurrently")
                        os.replace(str(staged_imp), str(dest_path))
                        newly_materialized.append(dest_path)
                        _chmod_safe(dest_path, 0o600)
                    except OSError as exc:
                        if staged_imp is not None and staged_imp.exists():
                            self._quarantine_best_effort(staged_imp, "failed_tmp")
                        _cleanup_pre_commit()
                        raise RestorePreCommitIOError(
                            code="PRE_RESTORE_BACKUP_IO_ERROR",
                            stage="imported_lineage_write",
                            message="Không thể lưu tệp bằng chứng lịch sử đi kèm bản sao lưu trước khôi phục; đã hủy giao dịch trước điểm commit để bảo toàn dữ liệu hiện hành.",
                        ) from exc

            # Pre-commit Step 2: Stage & atomically publish live pre_restore_<UTC>_<rand>.json snapshot & fsync backup_dir
            utc_stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            rand_hex = secrets.token_hex(4)
            pre_restore_filename = f"pre_restore_{utc_stamp}_{rand_hex}.json"
            pre_restore_path = self.backup_dir / pre_restore_filename
            pre_restore_bytes = json.dumps(current, ensure_ascii=False, indent=2).encode("utf-8")
            pre_restore_sha256 = hashlib.sha256(pre_restore_bytes).hexdigest()

            staged_pre: Path | None = None
            try:
                staged_pre = self._stage_temp_bytes(
                    self.backup_dir,
                    prefix=f".{pre_restore_filename}.",
                    raw_bytes=pre_restore_bytes,
                )
                if pre_restore_path.exists():
                    raise FileExistsError(f"Destination {pre_restore_filename} already exists")
                os.replace(str(staged_pre), str(pre_restore_path))
                _chmod_safe(pre_restore_path, 0o600)
                _strict_fsync_dir(self.backup_dir)
            except OSError as exc:
                if staged_pre is not None and staged_pre.exists():
                    self._quarantine_best_effort(staged_pre, "failed_tmp")
                _cleanup_pre_commit()
                raise RestorePreCommitIOError(
                    code="PRE_RESTORE_BACKUP_IO_ERROR",
                    stage="pre_restore_backup",
                    message="Không thể ghi bản sao lưu dự phòng pre_restore trước khôi phục; đã hủy giao dịch trước điểm commit để bảo toàn dữ liệu hiện hành.",
                ) from exc

            result = finalize_fn(candidate_state, pre_restore_filename, pre_restore_sha256)
            candidate_state.pop("audit_lineage_artifacts", None)

            # Pre-commit Step 3: Write WAL rollback journal & fsync data_dir before touching primary state
            staged_wal: Path | None = None
            try:
                staged_wal = self._stage_temp_json(self.wal_path, current)
                os.replace(str(staged_wal), str(self.wal_path))
                wal_written = True
                _chmod_safe(self.wal_path, 0o600)
                _strict_fsync_dir(self.data_dir)
            except OSError as exc:
                if staged_wal is not None and staged_wal.exists():
                    self._quarantine_best_effort(staged_wal, "failed_tmp")
                _cleanup_pre_commit()
                raise RestorePreCommitIOError(
                    code="RESTORE_STATE_WRITE_ABORTED",
                    stage="wal_journal_write",
                    message="Không thể ghi nhật ký hoàn tác WAL trước khôi phục; đã hủy giao dịch trước điểm commit, dữ liệu và phiên hiện hành được giữ nguyên.",
                ) from exc

            # Commit Point Step 4: Stage candidate JSON, then execute single-syscall POSIX os.replace (R2-01)
            staged_state: Path | None = None
            try:
                staged_state = self._stage_temp_json(self.state_path, candidate_state)
                os.replace(str(staged_state), str(self.state_path))
            except OSError as exc:
                if staged_state is not None and staged_state.exists():
                    self._quarantine_best_effort(staged_state, "failed_tmp")
                _cleanup_pre_commit()
                raise RestorePreCommitIOError(
                    code="RESTORE_STATE_WRITE_ABORTED",
                    stage="state_commit_write",
                    message="Không thể ghi nguyên tử trạng thái kho mới; đã hủy giao dịch trước điểm commit, dữ liệu và phiên hiện hành được giữ nguyên.",
                ) from exc

            # =================================================================================
            # COMMIT POINT PASSED: candidate_state IS NOW LIVE ON DISK (committed = True)
            # _cleanup_pre_commit() MUST NEVER BE CALLED PAST THIS POINT! (C01, R2-01)
            # =================================================================================
            _chmod_safe(self.state_path, 0o600)
            post_commit_warnings: list[dict[str, str]] = []
            try:
                _strict_fsync_dir(self.data_dir)
            except OSError as exc:
                post_commit_warnings.append(
                    {
                        "stage": "state_dir_fsync",
                        "code": "POST_COMMIT_STATE_DIR_FSYNC_IO_WARNING",
                        "message": (
                            "Kho dữ liệu mới đã được commit sang thế hệ kho tiếp theo, nhưng bước đồng bộ thư mục dữ liệu hậu commit "
                            f"gặp lỗi I/O ({exc.__class__.__name__})."
                        ),
                    }
                )

            clean_wal_slot = self.backup_dir / "latest_committed_rollback.json"
            try:
                os.replace(str(self.wal_path), str(clean_wal_slot))
                _chmod_safe(clean_wal_slot, 0o600)
            except OSError as exc:
                post_commit_warnings.append(
                    {
                        "stage": "wal_archive",
                        "code": "POST_COMMIT_WAL_ARCHIVE_IO_WARNING",
                        "message": (
                            "Kho dữ liệu mới đã được commit sang thế hệ kho tiếp theo, nhưng bước lưu trữ nhật ký WAL hậu commit "
                            f"gặp lỗi I/O ({exc.__class__.__name__}); hệ thống sẽ tự thu dọn an toàn khi mở lại kho hoặc ở giao dịch tiếp theo."
                        ),
                    }
                )

            try:
                self._maybe_hourly_snapshot()
            except OSError as exc:
                post_commit_warnings.append(
                    {
                        "stage": "hourly_snapshot",
                        "code": "POST_COMMIT_SNAPSHOT_IO_WARNING",
                        "message": (
                            "Kho dữ liệu mới đã được commit sang thế hệ kho tiếp theo, nhưng không thể tạo bản chụp định kỳ theo giờ "
                            f"({exc.__class__.__name__})."
                        ),
                    }
                )

            if isinstance(result, dict):
                result["committed"] = True
                result["commit_status"] = (
                    "COMMITTED_WITH_POST_COMMIT_WARNING" if post_commit_warnings else "COMMITTED_CLEAN"
                )
                result["post_commit_warnings"] = post_commit_warnings
            return result
