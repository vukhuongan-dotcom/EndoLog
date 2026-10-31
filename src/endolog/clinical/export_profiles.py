"""EndoLog Export Contract v1.0 — Profiles A (Encrypted Vault), B (Longitudinal Pseudonymized), C (Aggregated KPI)."""

from __future__ import annotations

import base64
import copy
import csv
import datetime as dt
import hashlib
import hmac
import io
import json
import os
import re
import zlib
from pathlib import Path
from typing import Any

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from openpyxl import Workbook
from pydantic import ValidationError

from endolog.clinical.adverse_events import summarize_case_adverse_events
from endolog.clinical.bbps import evaluate_bbps, extract_bbps_segments
from endolog.clinical.quality_metrics import compute_ercp_session_indices, compute_kpi_snapshot
from endolog.core.audit import (
    RestoreLineageSignature,
    collect_audit_chain_restore_signatures,
    extract_restore_lineage_signature,
    verify_audit_chain,
)
from endolog.schemas.clinical import (
    StoredAuditLineageBridge,
    StoredCaseRecord,
    StoredEpisodeRecord,
    StoredLineageArtifactEntry,
    StoredPatientRecord,
    StoredSettingsRecord,
    StoredSurveillanceRecord,
    StoredUserRecord,
)

MAX_VAULT_BLOB_BYTES = 10_485_760  # 10 MiB strict pre-KDF ceiling (G02)
MAX_LINEAGE_BRIDGES = 128
MAX_SINGLE_LINEAGE_ARTIFACT_BYTES = 10_485_760  # 10 MiB uncompressed ceiling per pre_restore artifact (C02)
MAX_TOTAL_LINEAGE_ARTIFACTS_BYTES = 33_554_432  # 32 MiB total uncompressed ceiling across lineage bundle (C02)
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_CASE_CODE_RE = re.compile(r"^(EGD|COL|ERCP)-(\d{4})-(\d{4,})$")
_COUNTER_KEY_RE = re.compile(r"^(EGD|COL|ERCP)-(\d{4})$")
_ALLOWED_OUTER_KEYS = frozenset(
    {
        "contract",
        "kdf",
        "cipher",
        "salt_hex",
        "nonce_hex",
        "ciphertext_hex",
        "key_context_hint",
    }
)
_REQUIRED_OUTER_KEYS = frozenset(
    {
        "contract",
        "kdf",
        "cipher",
        "salt_hex",
        "nonce_hex",
        "ciphertext_hex",
    }
)
_ALLOWED_VAULT_ROOT_KEYS = frozenset(
    {
        "schema_version",
        "store_epoch",
        "settings",
        "users",
        "patients",
        "episodes",
        "cases",
        "surveillance",
        "counters",
        "audit_chain",
        "audit_lineage_bridges",
        "audit_lineage_artifacts",
        "revoked_jtis",
        "crypto_context",
    }
)
_REQUIRED_VAULT_ROOT_KEYS = frozenset(
    {
        "schema_version",
        "settings",
        "users",
        "patients",
        "episodes",
        "cases",
        "surveillance",
        "counters",
        "audit_chain",
    }
)


class VaultPayloadTooLargeError(ValueError):
    """Raised when uploaded or exported .endolog.enc blob exceeds 10 MiB before KDF (HTTP 413)."""

    def __init__(self, message: str = "Tệp sao lưu vượt giới hạn tối đa 10 MiB.") -> None:
        self.code = "VAULT_PAYLOAD_TOO_LARGE"
        self.message = message
        super().__init__(message)


class VaultSchemaValidationError(ValueError):
    """Raised on envelope/schema/referential integrity violations (HTTP 422)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class VaultDecryptError(ValueError):
    """Raised when AES-256-GCM decryption fails due to wrong passphrase or tag mismatch (HTTP 400)."""

    def __init__(self, message: str = "Sai mật khẩu giải mã hoặc tệp sao lưu Hồ sơ A đã bị biến đổi.") -> None:
        self.code = "VAULT_DECRYPT_FAILED"
        self.message = message
        super().__init__(message)


class LineageEvidenceExportError(ValueError):
    """Raised when exporting Profile A from a store whose local pre_restore lineage evidence is missing or tampered (HTTP 409)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def validate_profile_a_envelope_pre_kdf(blob: bytes) -> dict[str, Any]:
    """Layer 1 pre-KDF gate: verify byte limit and outer envelope fields before running Argon2id (G02)."""
    if len(blob) > MAX_VAULT_BLOB_BYTES:
        raise VaultPayloadTooLargeError()
    try:
        envelope = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VaultSchemaValidationError(
            "INVALID_VAULT_ENVELOPE_JSON",
            "Tệp sao lưu không đúng định dạng JSON phong bì Hồ sơ A.",
        ) from exc

    if not isinstance(envelope, dict):
        raise VaultSchemaValidationError(
            "INVALID_VAULT_ENVELOPE_TYPE",
            "Vỏ phong bì Hồ sơ A phải là một đối tượng JSON.",
        )

    env_keys = set(envelope.keys())
    if not _REQUIRED_OUTER_KEYS.issubset(env_keys) or not env_keys.issubset(_ALLOWED_OUTER_KEYS):
        raise VaultSchemaValidationError(
            "INVALID_VAULT_ENVELOPE_KEYS",
            "Vỏ phong bì Hồ sơ A thiếu trường bắt buộc hoặc chứa khóa lạ không hợp lệ.",
        )

    if (
        envelope.get("contract") not in ("EndoLog-Export-Profile-A-v1.0", "EndoLog-Export-Profile-A-v1.1")
        or envelope.get("kdf") != "argon2id"
        or envelope.get("cipher") != "aes-256-gcm"
    ):
        raise VaultSchemaValidationError(
            "UNSUPPORTED_VAULT_ENVELOPE_SPEC",
            "Không hỗ trợ phiên bản hợp đồng hoặc thuật toán mã hóa của tệp sao lưu này.",
        )

    salt_hex = envelope.get("salt_hex")
    nonce_hex = envelope.get("nonce_hex")
    ciphertext_hex = envelope.get("ciphertext_hex")
    if not isinstance(salt_hex, str) or len(salt_hex) != 32 or not _HEX_RE.match(salt_hex):
        raise VaultSchemaValidationError(
            "INVALID_VAULT_SALT",
            "Trường salt_hex trong tệp sao lưu phải gồm đúng 32 ký tự thập lục phân (16 byte).",
        )
    if not isinstance(nonce_hex, str) or len(nonce_hex) != 24 or not _HEX_RE.match(nonce_hex):
        raise VaultSchemaValidationError(
            "INVALID_VAULT_NONCE",
            "Trường nonce_hex trong tệp sao lưu phải gồm đúng 24 ký tự thập lục phân (12 byte).",
        )
    if (
        not isinstance(ciphertext_hex, str)
        or len(ciphertext_hex) < 34
        or len(ciphertext_hex) % 2 != 0
        or len(ciphertext_hex) > MAX_VAULT_BLOB_BYTES * 2
        or not _HEX_RE.match(ciphertext_hex)
    ):
        raise VaultSchemaValidationError(
            "INVALID_VAULT_CIPHERTEXT",
            "Trường ciphertext_hex không hợp lệ hoặc không đủ độ dài thẻ xác thực AES-GCM.",
        )

    hint = envelope.get("key_context_hint")
    if hint is not None:
        if not isinstance(hint, dict) or not set(hint.keys()).issubset(
            {"mrn_key_fp", "shift_key_fp", "export_dataset_epoch"}
        ):
            raise VaultSchemaValidationError(
                "INVALID_KEY_CONTEXT_HINT",
                "Siêu dữ liệu gợi ý khóa trong phong bì sao lưu không hợp lệ.",
            )

    return {
        "envelope": envelope,
        "salt": bytes.fromhex(salt_hex),
        "nonce": bytes.fromhex(nonce_hex),
        "ciphertext": bytes.fromhex(ciphertext_hex),
    }


def pack_lineage_artifacts_for_export(
    bridges: list[dict[str, Any]] | None,
    backup_dir: Path | None,
    *,
    audit_chain: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Bundle verified historical pre_restore_*.json artifacts inside encrypted Profile A vault for portable cross-machine lineage (C02)."""
    ok_root_sigs, root_restore_sigs = collect_audit_chain_restore_signatures(audit_chain)
    if not ok_root_sigs:
        raise LineageEvidenceExportError(
            "LINEAGE_EVIDENCE_CORRUPTED_ON_EXPORT",
            "Chuỗi kiểm toán trên máy chủ nguồn chứa sự kiện khôi phục sai cấu trúc siêu dữ liệu.",
        )

    items = bridges or []
    if not items:
        if root_restore_sigs:
            raise LineageEvidenceExportError(
                "LINEAGE_EVIDENCE_INCOMPLETE_ON_EXPORT",
                "Chuỗi kiểm toán ghi nhận lịch sử khôi phục nhưng thiếu danh sách cầu nối audit_lineage_bridges trên máy chủ nguồn.",
            )
        return {}
    if len(items) > MAX_LINEAGE_BRIDGES:
        raise LineageEvidenceExportError(
            "LINEAGE_BRIDGE_LIMIT_EXCEEDED",
            f"Số lượng cầu nối lịch sử khôi phục ({len(items)}) vượt ngưỡng an toàn {MAX_LINEAGE_BRIDGES}.",
        )
    if backup_dir is None:
        raise LineageEvidenceExportError(
            "LINEAGE_EVIDENCE_INCOMPLETE_ON_EXPORT",
            "Kho dữ liệu có lịch sử khôi phục nhưng chưa cung cấp thư mục backup_dir để đóng gói bằng chứng kế thừa kiểm toán.",
        )

    packed: dict[str, dict[str, Any]] = {}
    bridge_sigs: set[RestoreLineageSignature] = set()
    displaced_restore_sigs: set[RestoreLineageSignature] = set()
    nested_bridge_sigs: set[RestoreLineageSignature] = set()
    total_raw_bytes = 0
    for raw_br in items:
        try:
            br = StoredAuditLineageBridge.model_validate(raw_br)
        except ValidationError as exc:
            raise LineageEvidenceExportError(
                "INVALID_LINEAGE_BRIDGE_ON_EXPORT",
                "Siêu dữ liệu cầu nối kiểm toán trên máy chủ nguồn không hợp lệ.",
            ) from exc

        sig = extract_restore_lineage_signature(br.model_dump())
        if sig is None:
            raise LineageEvidenceExportError(
                "INVALID_LINEAGE_BRIDGE_ON_EXPORT",
                "Chữ ký cầu nối kiểm toán trên máy chủ nguồn không hợp lệ.",
            )
        bridge_sigs.add(sig)

        fname = br.pre_restore_filename
        if fname in packed:
            if packed[fname]["sha256"] != br.pre_restore_sha256.lower():
                raise LineageEvidenceExportError(
                    "LINEAGE_EVIDENCE_CORRUPTED_ON_EXPORT",
                    f"Phát hiện xung đột mã băm trên tệp bằng chứng lịch sử '{fname}'.",
                )
            continue

        artifact_path = backup_dir / fname
        if not artifact_path.is_file():
            raise LineageEvidenceExportError(
                "LINEAGE_EVIDENCE_INCOMPLETE_ON_EXPORT",
                f"Thiếu tệp bằng chứng lịch sử '{fname}' trên máy chủ nguồn; từ chối xuất bản sao lưu thiếu bằng chứng kiểm toán.",
            )
        try:
            raw_bytes = artifact_path.read_bytes()
        except OSError as exc:
            raise LineageEvidenceExportError(
                "LINEAGE_EVIDENCE_INCOMPLETE_ON_EXPORT",
                f"Không thể đọc tệp bằng chứng lịch sử '{fname}' trên máy chủ nguồn.",
            ) from exc

        if len(raw_bytes) > MAX_SINGLE_LINEAGE_ARTIFACT_BYTES:
            raise LineageEvidenceExportError(
                "LINEAGE_ARTIFACT_TOO_LARGE_ON_EXPORT",
                f"Tệp bằng chứng lịch sử '{fname}' vượt trần 10 MiB.",
            )
        total_raw_bytes += len(raw_bytes)
        if total_raw_bytes > MAX_TOTAL_LINEAGE_ARTIFACTS_BYTES:
            raise LineageEvidenceExportError(
                "LINEAGE_ARTIFACTS_TOTAL_TOO_LARGE_ON_EXPORT",
                "Tổng dung lượng giải nén các tệp bằng chứng lịch sử vượt trần 32 MiB.",
            )

        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha = br.pre_restore_sha256.lower()
        if actual_sha != expected_sha:
            raise LineageEvidenceExportError(
                "LINEAGE_EVIDENCE_CORRUPTED_ON_EXPORT",
                f"Tệp bằng chứng lịch sử '{fname}' trên máy chủ nguồn không khớp mã băm SHA-256 đã niêm phong.",
            )

        try:
            displaced_obj = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LineageEvidenceExportError(
                "LINEAGE_EVIDENCE_CORRUPTED_ON_EXPORT",
                f"Tệp bằng chứng lịch sử '{fname}' không phải JSON hợp lệ.",
            ) from exc
        if not isinstance(displaced_obj, dict) or not isinstance(displaced_obj.get("audit_chain"), list):
            raise LineageEvidenceExportError(
                "LINEAGE_EVIDENCE_CORRUPTED_ON_EXPORT",
                f"Tệp bằng chứng lịch sử '{fname}' thiếu chuỗi kiểm toán hợp lệ.",
            )
        d_ver = verify_audit_chain(displaced_obj["audit_chain"])
        ok_disp_sigs, disp_sigs = collect_audit_chain_restore_signatures(displaced_obj["audit_chain"])
        nested_raw = displaced_obj.get("audit_lineage_bridges") or []
        ok_nested = isinstance(nested_raw, list)
        if ok_nested:
            for nb in nested_raw:
                nb_sig = extract_restore_lineage_signature(nb)
                if nb_sig is None:
                    ok_nested = False
                    break
                nested_bridge_sigs.add(nb_sig)
        if (
            not d_ver.get("valid")
            or not ok_disp_sigs
            or not ok_nested
            or str(d_ver.get("head_hash") or "").lower() != br.displaced_live_head_hash.lower()
            or int(d_ver.get("checked_entries") or -1) != br.displaced_live_seq
        ):
            raise LineageEvidenceExportError(
                "LINEAGE_EVIDENCE_CORRUPTED_ON_EXPORT",
                f"Chuỗi kiểm toán trong tệp bằng chứng '{fname}' không khớp cầu nối kiểm toán trên máy chủ nguồn.",
            )
        displaced_restore_sigs |= disp_sigs

        comp_bytes = zlib.compress(raw_bytes, level=9)
        packed[fname] = {
            "encoding": "zlib+base64",
            "raw_size_bytes": len(raw_bytes),
            "sha256": expected_sha,
            "data_b64": base64.b64encode(comp_bytes).decode("ascii"),
        }

    if not nested_bridge_sigs.issubset(bridge_sigs):
        raise LineageEvidenceExportError(
            "LINEAGE_EVIDENCE_INCOMPLETE_ON_EXPORT",
            "Thiếu cầu nối kiểm toán tổ tiên được tham chiếu trong tệp bằng chứng lịch sử.",
        )
    if audit_chain is not None and bridge_sigs != (root_restore_sigs | displaced_restore_sigs):
        raise LineageEvidenceExportError(
            "LINEAGE_EVIDENCE_INCOMPLETE_ON_EXPORT",
            "Danh sách cầu nối kiểm toán không khớp toàn vẹn với các sự kiện khôi phục trong chuỗi kiểm toán.",
        )

    return packed


def export_profile_a_encrypted_vault(
    state_snapshot: dict[str, Any],
    passphrase: str,
    *,
    crypto_context: dict[str, Any] | None = None,
    backup_dir: Path | None = None,
) -> bytes:
    """Profile A: AES-256-GCM + Argon2id KDF full backup with portable lineage evidence bundle (Superadmin exclusive)."""
    if len(passphrase) < 12:
        raise ValueError("Mật khẩu mã hóa sao lưu Profile A phải có tối thiểu 12 ký tự.")
    snap_to_encrypt = copy.deepcopy(state_snapshot)
    if crypto_context is not None:
        snap_to_encrypt["crypto_context"] = dict(crypto_context)
    snap_to_encrypt["audit_lineage_artifacts"] = pack_lineage_artifacts_for_export(
        snap_to_encrypt.get("audit_lineage_bridges"),
        backup_dir,
        audit_chain=snap_to_encrypt.get("audit_chain"),
    )

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
    aesgcm = AESGCM(key)
    plaintext = json.dumps(snap_to_encrypt, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    aad = b"endolog-export-profile-a-v1"
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    envelope: dict[str, Any] = {
        "contract": "EndoLog-Export-Profile-A-v1.0",
        "kdf": "argon2id",
        "cipher": "aes-256-gcm",
        "salt_hex": salt.hex(),
        "nonce_hex": nonce.hex(),
        "ciphertext_hex": ciphertext.hex(),
    }
    if crypto_context is not None:
        envelope["key_context_hint"] = dict(crypto_context)
    encoded_envelope = json.dumps(envelope, indent=2).encode("utf-8")
    if len(encoded_envelope) > MAX_VAULT_BLOB_BYTES:
        raise VaultPayloadTooLargeError()
    return encoded_envelope


def decrypt_profile_a_vault(blob: bytes, passphrase: str) -> dict[str, Any]:
    parsed = validate_profile_a_envelope_pre_kdf(blob)
    key = hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=parsed["salt"],
        time_cost=2,
        memory_cost=65536,
        parallelism=2,
        hash_len=32,
        type=Type.ID,
    )
    try:
        plaintext = AESGCM(key).decrypt(parsed["nonce"], parsed["ciphertext"], b"endolog-export-profile-a-v1")
    except (InvalidTag, Exception) as exc:
        raise VaultDecryptError() from exc

    try:
        vault_obj = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VaultSchemaValidationError(
            "INVALID_VAULT_PLAINTEXT_JSON",
            "Nội dung kho sau giải mã không phải JSON hợp lệ.",
        ) from exc
    if not isinstance(vault_obj, dict):
        raise VaultSchemaValidationError(
            "INVALID_VAULT_ROOT_TYPE",
            "Gốc dữ liệu kho khôi phục phải là đối tượng JSON.",
        )
    return vault_obj


def _is_strict_int(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool)


def extract_and_validate_lineage_artifacts(vault_data: dict[str, Any]) -> dict[str, bytes]:
    """Validate audit_lineage_bridges, bundled pre_restore_*.json artifacts, and hash-chained restore event bijection (C02)."""
    if "audit_lineage_bridges" in vault_data and not isinstance(vault_data["audit_lineage_bridges"], list):
        raise VaultSchemaValidationError("INVALID_AUDIT_LINEAGE", "audit_lineage_bridges phải là danh sách.")
    if "audit_lineage_artifacts" in vault_data and vault_data["audit_lineage_artifacts"] is not None:
        if not isinstance(vault_data["audit_lineage_artifacts"], dict):
            raise VaultSchemaValidationError(
                "INVALID_AUDIT_LINEAGE_ARTIFACTS",
                "audit_lineage_artifacts phải là từ điển JSON.",
            )

    has_root_chain = "audit_chain" in vault_data and vault_data.get("audit_chain") is not None
    ok_root_sigs, root_restore_sigs = collect_audit_chain_restore_signatures(
        vault_data.get("audit_chain") if has_root_chain else None
    )
    if not ok_root_sigs:
        raise VaultSchemaValidationError(
            "INVALID_AUDIT_LINEAGE_CHAIN_EVENT",
            "Sự kiện khôi phục trong chuỗi kiểm toán của bản sao lưu sai cấu trúc siêu dữ liệu.",
        )

    raw_bridges: list[Any] = vault_data.get("audit_lineage_bridges") or []
    if len(raw_bridges) > MAX_LINEAGE_BRIDGES:
        raise VaultSchemaValidationError(
            "LINEAGE_BRIDGE_LIMIT_EXCEEDED",
            f"Số lượng cầu nối lịch sử khôi phục ({len(raw_bridges)}) vượt ngưỡng tối đa {MAX_LINEAGE_BRIDGES}.",
        )

    validated_bridges: list[StoredAuditLineageBridge] = []
    bridge_sigs: set[RestoreLineageSignature] = set()
    expected_sha_by_fname: dict[str, str] = {}
    for raw_br in raw_bridges:
        try:
            br = StoredAuditLineageBridge.model_validate(raw_br)
        except ValidationError as exc:
            raise VaultSchemaValidationError(
                "INVALID_AUDIT_LINEAGE_BRIDGE_SCHEMA",
                "Bản ghi cầu nối lịch sử kiểm toán trong bản sao lưu sai cấu trúc.",
            ) from exc
        if br.new_store_epoch <= br.previous_store_epoch:
            raise VaultSchemaValidationError(
                "INVALID_AUDIT_LINEAGE_EPOCH_ORDER",
                "Cầu nối lịch sử kiểm toán có thứ tự store_epoch không hợp lệ.",
            )
        sig = extract_restore_lineage_signature(br.model_dump())
        if sig is None:
            raise VaultSchemaValidationError(
                "INVALID_AUDIT_LINEAGE_BRIDGE_SCHEMA",
                "Chữ ký cầu nối lịch sử kiểm toán không hợp lệ.",
            )
        bridge_sigs.add(sig)
        sha_lc = br.pre_restore_sha256.lower()
        prev_sha = expected_sha_by_fname.get(br.pre_restore_filename)
        if prev_sha is not None and prev_sha != sha_lc:
            raise VaultSchemaValidationError(
                "CONFLICTING_LINEAGE_ARTIFACT_HASH",
                f"Phát hiện hai cầu nối cùng tên tệp '{br.pre_restore_filename}' nhưng khác mã băm SHA-256.",
            )
        expected_sha_by_fname[br.pre_restore_filename] = sha_lc
        validated_bridges.append(br)

    artifacts_map: dict[str, Any] = vault_data.get("audit_lineage_artifacts") or {}
    required_fnames = set(expected_sha_by_fname.keys())
    provided_fnames = set(artifacts_map.keys())

    missing_fnames = sorted(required_fnames - provided_fnames)
    if missing_fnames:
        raise VaultSchemaValidationError(
            "MISSING_LINEAGE_EVIDENCE_ARTIFACT",
            f"Bản sao lưu có lịch sử khôi phục nhưng thiếu tệp bằng chứng lịch sử đi kèm ({missing_fnames[0]}).",
        )

    extra_fnames = sorted(provided_fnames - required_fnames)
    if extra_fnames:
        raise VaultSchemaValidationError(
            "UNREFERENCED_LINEAGE_EVIDENCE_ARTIFACT",
            f"Bản sao lưu chứa tệp bằng chứng lịch sử không thuộc cầu nối kiểm toán nào ({extra_fnames[0]}).",
        )

    decompressed_by_fname: dict[str, bytes] = {}
    displaced_restore_sigs: set[RestoreLineageSignature] = set()
    nested_bridge_sigs: set[RestoreLineageSignature] = set()
    total_decompressed = 0
    for br in validated_bridges:
        fname = br.pre_restore_filename
        if fname in decompressed_by_fname:
            raw_bytes = decompressed_by_fname[fname]
        else:
            raw_entry = artifacts_map[fname]
            try:
                entry = StoredLineageArtifactEntry.model_validate(raw_entry)
            except ValidationError as exc:
                raise VaultSchemaValidationError(
                    "INVALID_LINEAGE_ARTIFACT_SCHEMA",
                    f"Cấu trúc tệp bằng chứng lịch sử '{fname}' trong bản sao lưu không hợp lệ.",
                ) from exc

            if entry.sha256.lower() != br.pre_restore_sha256.lower():
                raise VaultSchemaValidationError(
                    "TAMPERED_LINEAGE_EVIDENCE_ARTIFACT",
                    f"Mã băm khai báo của tệp bằng chứng '{fname}' không khớp cầu nối kiểm toán.",
                )

            try:
                comp_bytes = base64.b64decode(entry.data_b64.encode("ascii"), validate=True)
            except Exception as exc:
                raise VaultSchemaValidationError(
                    "INVALID_LINEAGE_ARTIFACT_BASE64",
                    f"Dữ liệu Base64 của tệp bằng chứng lịch sử '{fname}' không hợp lệ.",
                ) from exc

            try:
                dobj = zlib.decompressobj()
                head_chunk = dobj.decompress(comp_bytes, MAX_SINGLE_LINEAGE_ARTIFACT_BYTES + 1)
                if dobj.unconsumed_tail or len(head_chunk) > MAX_SINGLE_LINEAGE_ARTIFACT_BYTES:
                    raise VaultSchemaValidationError(
                        "LINEAGE_ARTIFACT_TOO_LARGE",
                        f"Tệp bằng chứng lịch sử '{fname}' vượt trần giải nén 10 MiB.",
                    )
                tail_chunk = dobj.flush(MAX_SINGLE_LINEAGE_ARTIFACT_BYTES + 1 - len(head_chunk))
                raw_bytes = head_chunk + tail_chunk
                if not dobj.eof or len(raw_bytes) > MAX_SINGLE_LINEAGE_ARTIFACT_BYTES:
                    raise VaultSchemaValidationError(
                        "LINEAGE_ARTIFACT_TOO_LARGE",
                        f"Luồng nén của tệp bằng chứng lịch sử '{fname}' không hợp lệ hoặc vượt trần 10 MiB.",
                    )
            except VaultSchemaValidationError:
                raise
            except zlib.error as exc:
                raise VaultSchemaValidationError(
                    "TAMPERED_LINEAGE_EVIDENCE_ARTIFACT",
                    f"Không thể giải nén tệp bằng chứng lịch sử '{fname}'; dữ liệu nén đã bị hỏng.",
                ) from exc

            total_decompressed += len(raw_bytes)
            if total_decompressed > MAX_TOTAL_LINEAGE_ARTIFACTS_BYTES:
                raise VaultSchemaValidationError(
                    "LINEAGE_ARTIFACTS_TOTAL_TOO_LARGE",
                    "Tổng dung lượng giải nén các tệp bằng chứng lịch sử vượt trần 32 MiB.",
                )

            if len(raw_bytes) != entry.raw_size_bytes:
                raise VaultSchemaValidationError(
                    "TAMPERED_LINEAGE_EVIDENCE_ARTIFACT",
                    f"Kích thước giải nén thực tế của '{fname}' không khớp trường raw_size_bytes.",
                )

            actual_sha = hashlib.sha256(raw_bytes).hexdigest()
            if actual_sha != br.pre_restore_sha256.lower():
                raise VaultSchemaValidationError(
                    "TAMPERED_LINEAGE_EVIDENCE_ARTIFACT",
                    f"Nội dung giải nén của tệp bằng chứng '{fname}' không khớp mã băm SHA-256 trong cầu nối kiểm toán.",
                )

            decompressed_by_fname[fname] = raw_bytes

        try:
            displaced_obj = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VaultSchemaValidationError(
                "INVALID_LINEAGE_DISPLACED_AUDIT_CHAIN",
                f"Nội dung tệp bằng chứng lịch sử '{fname}' không phải JSON hợp lệ.",
            ) from exc

        if not isinstance(displaced_obj, dict) or not isinstance(displaced_obj.get("audit_chain"), list):
            raise VaultSchemaValidationError(
                "INVALID_LINEAGE_DISPLACED_AUDIT_CHAIN",
                f"Tệp bằng chứng lịch sử '{fname}' không chứa bảng audit_chain hợp lệ.",
            )
        d_ver = verify_audit_chain(displaced_obj["audit_chain"])
        ok_disp_sigs, disp_sigs = collect_audit_chain_restore_signatures(displaced_obj["audit_chain"])
        nested_raw = displaced_obj.get("audit_lineage_bridges") or []
        ok_nested = isinstance(nested_raw, list)
        if ok_nested:
            for nb in nested_raw:
                nb_sig = extract_restore_lineage_signature(nb)
                if nb_sig is None:
                    ok_nested = False
                    break
                nested_bridge_sigs.add(nb_sig)
        if (
            not d_ver.get("valid")
            or not ok_disp_sigs
            or not ok_nested
            or str(d_ver.get("head_hash") or "").lower() != br.displaced_live_head_hash.lower()
            or int(d_ver.get("checked_entries") or -1) != br.displaced_live_seq
        ):
            raise VaultSchemaValidationError(
                "INVALID_LINEAGE_DISPLACED_AUDIT_CHAIN",
                f"Chuỗi kiểm toán bên trong tệp bằng chứng '{fname}' không khớp displaced_live_head_hash/seq của cầu nối.",
            )
        displaced_restore_sigs |= disp_sigs

    if not nested_bridge_sigs.issubset(bridge_sigs):
        raise VaultSchemaValidationError(
            "MISSING_LINEAGE_BRIDGE_FOR_AUDIT_EVENT",
            "Bản sao lưu thiếu cầu nối kiểm toán tổ tiên được tham chiếu trong tệp bằng chứng lịch sử.",
        )

    if has_root_chain:
        expected_all_restore_sigs = root_restore_sigs | displaced_restore_sigs
        if expected_all_restore_sigs - bridge_sigs:
            raise VaultSchemaValidationError(
                "MISSING_LINEAGE_BRIDGE_FOR_AUDIT_EVENT",
                "Chuỗi kiểm toán ghi nhận sự kiện khôi phục trước đó nhưng thiếu bản ghi cầu nối hoặc tệp bằng chứng tương ứng.",
            )
        if bridge_sigs - expected_all_restore_sigs:
            raise VaultSchemaValidationError(
                "UNBACKED_LINEAGE_BRIDGE",
                "Bản sao lưu chứa cầu nối lịch sử khôi phục không khớp bất kỳ sự kiện kiểm toán hợp lệ nào.",
            )

    return decompressed_by_fname


def validate_restored_vault_domain(
    vault_data: dict[str, Any],
    *,
    preserve_current_users: bool,
) -> dict[str, Any]:
    """Layer 2 strict Pydantic & cross-entity referential validator for restored Profile A snapshots (G02/C02)."""
    if not isinstance(vault_data, dict):
        raise VaultSchemaValidationError("UNSUPPORTED_VAULT_SCHEMA", "Dữ liệu kho không phải đối tượng hợp lệ.")

    root_keys = set(vault_data.keys())
    if not _REQUIRED_VAULT_ROOT_KEYS.issubset(root_keys) or not root_keys.issubset(_ALLOWED_VAULT_ROOT_KEYS):
        raise VaultSchemaValidationError(
            "UNSUPPORTED_VAULT_SCHEMA",
            "Kho sao lưu thiếu bảng dữ liệu bắt buộc hoặc chứa khóa gốc lạ không được hỗ trợ.",
        )

    schema_ver = vault_data.get("schema_version")
    if schema_ver not in ("1.0.0", "1.1.0"):
        raise VaultSchemaValidationError(
            "UNSUPPORTED_VAULT_SCHEMA",
            f"Phiên bản lược đồ kho '{schema_ver}' không được hỗ trợ (chỉ nhận 1.0.0 hoặc 1.1.0).",
        )

    if "store_epoch" in vault_data and (
        not _is_strict_int(vault_data["store_epoch"]) or int(vault_data["store_epoch"]) < 1
    ):
        raise VaultSchemaValidationError("INVALID_STORE_EPOCH", "Trường store_epoch trong kho không hợp lệ.")

    for dict_name in ("settings", "users", "patients", "episodes", "cases", "surveillance", "counters"):
        if not isinstance(vault_data.get(dict_name), dict):
            raise VaultSchemaValidationError(
                "INVALID_COLLECTION_TYPE",
                f"Bảng '{dict_name}' trong kho sao lưu phải là từ điển JSON.",
            )

    if not isinstance(vault_data.get("audit_chain"), list) or len(vault_data["audit_chain"]) < 1:
        raise VaultSchemaValidationError(
            "INVALID_VAULT_AUDIT_CHAIN",
            "Chuỗi kiểm toán trong kho sao lưu trống hoặc sai kiểu dữ liệu.",
        )
    audit_ver = verify_audit_chain(vault_data["audit_chain"])
    if not audit_ver.get("valid"):
        raise VaultSchemaValidationError(
            "INVALID_VAULT_AUDIT_CHAIN",
            f"Chuỗi băm kiểm toán SHA-256 của bản sao lưu không toàn vẹn ({audit_ver.get('reason')}).",
        )

    extract_and_validate_lineage_artifacts(vault_data)

    if "crypto_context" in vault_data and vault_data["crypto_context"] is not None:
        cctx = vault_data["crypto_context"]
        if not isinstance(cctx, dict) or not set(cctx.keys()).issubset(
            {"mrn_key_fp", "shift_key_fp", "export_dataset_epoch"}
        ):
            raise VaultSchemaValidationError("INVALID_CRYPTO_CONTEXT", "crypto_context trong kho sao lưu không hợp lệ.")

    try:
        StoredSettingsRecord.model_validate(vault_data["settings"])
    except ValidationError as exc:
        raise VaultSchemaValidationError("INVALID_SETTINGS_SCHEMA", "Cấu hình settings trong kho không hợp lệ.") from exc

    users_dict: dict[str, dict[str, Any]] = vault_data["users"]
    active_superadmins = 0
    for u_key, u_raw in users_dict.items():
        if not isinstance(u_raw, dict) or u_raw.get("username") != u_key:
            raise VaultSchemaValidationError(
                "USER_KEY_MISMATCH",
                f"Khóa từ điển người dùng '{u_key}' không khớp trường username bên trong.",
            )
        try:
            u_model = StoredUserRecord.model_validate(u_raw)
        except ValidationError as exc:
            raise VaultSchemaValidationError("INVALID_USER_RECORD", f"Hồ sơ tài khoản '{u_key}' sai cấu trúc.") from exc
        if not u_model.password_hash.startswith("$argon2id$"):
            raise VaultSchemaValidationError(
                "INVALID_PASSWORD_HASH_FORMAT",
                f"Tài khoản '{u_key}' không mang định dạng băm Argon2id hợp lệ.",
            )
        if u_model.role == "superadmin" and u_model.active:
            active_superadmins += 1

    if not preserve_current_users and active_superadmins < 1:
        raise VaultSchemaValidationError(
            "NO_ACTIVE_SUPERADMIN_IN_VAULT",
            "Bản sao lưu không còn tài khoản Superadmin đang hoạt động; từ chối khôi phục bảng người dùng để tránh khóa quyền quản trị.",
        )

    patients_dict: dict[str, dict[str, Any]] = vault_data["patients"]
    for p_key, p_raw in patients_dict.items():
        if not isinstance(p_raw, dict) or p_raw.get("patient_uid") != p_key:
            raise VaultSchemaValidationError(
                "PATIENT_KEY_MISMATCH",
                f"Khóa người bệnh '{p_key}' không khớp trường patient_uid bên trong.",
            )
        try:
            p_model = StoredPatientRecord.model_validate(p_raw)
        except ValidationError as exc:
            raise VaultSchemaValidationError(
                "INVALID_PATIENT_RECORD",
                f"Hồ sơ người bệnh '{p_key}' không đúng lược đồ.",
            ) from exc
        if p_model.status == "ACTIVE":
            if p_model.merged_into_patient_uid is not None:
                raise VaultSchemaValidationError(
                    "INVALID_ACTIVE_PATIENT_MERGE_POINTER",
                    f"Hồ sơ người bệnh đang hoạt động '{p_key}' không được mang con trỏ merged_into_patient_uid.",
                )
        elif p_model.status == "MERGED_SUPERSEDED":
            if (
                not p_model.merged_into_patient_uid
                or p_model.merged_into_patient_uid == p_key
                or p_model.merged_into_patient_uid not in patients_dict
            ):
                raise VaultSchemaValidationError(
                    "INVALID_MERGED_PATIENT_TARGET",
                    f"Hồ sơ người bệnh đã gộp '{p_key}' thiếu đích gộp hợp lệ.",
                )
            if patients_dict[p_model.merged_into_patient_uid].get("status", "ACTIVE") != "ACTIVE":
                raise VaultSchemaValidationError(
                    "NON_CANONICAL_MERGED_PATIENT_TARGET",
                    f"Hồ sơ người bệnh đã gộp '{p_key}' trỏ tới đích '{p_model.merged_into_patient_uid}' không ở trạng thái ACTIVE (phát hiện chu trình hoặc chuỗi gộp chưa làm phẳng).",
                )

    episodes_dict: dict[str, dict[str, Any]] = vault_data["episodes"]
    for e_key, e_raw in episodes_dict.items():
        if not isinstance(e_raw, dict) or e_raw.get("episode_id") != e_key:
            raise VaultSchemaValidationError(
                "EPISODE_KEY_MISMATCH",
                f"Khóa đợt điều trị '{e_key}' không khớp trường episode_id bên trong.",
            )
        try:
            e_model = StoredEpisodeRecord.model_validate(e_raw)
        except ValidationError as exc:
            raise VaultSchemaValidationError(
                "INVALID_EPISODE_RECORD",
                f"Đợt điều trị '{e_key}' không đúng lược đồ.",
            ) from exc
        if e_model.patient_uid not in patients_dict:
            raise VaultSchemaValidationError(
                "BROKEN_EPISODE_PATIENT_FK",
                f"Đợt điều trị '{e_key}' trỏ tới patient_uid '{e_model.patient_uid}' không tồn tại.",
            )
        if e_model.status == "ACTIVE":
            if e_model.merged_into_episode_id is not None:
                raise VaultSchemaValidationError(
                    "INVALID_ACTIVE_EPISODE_MERGE_POINTER",
                    f"Đợt điều trị đang hoạt động '{e_key}' không được mang con trỏ merged_into_episode_id.",
                )
        elif e_model.status == "MERGED_SUPERSEDED":
            if (
                not e_model.merged_into_episode_id
                or e_model.merged_into_episode_id == e_key
                or e_model.merged_into_episode_id not in episodes_dict
            ):
                raise VaultSchemaValidationError(
                    "INVALID_MERGED_EPISODE_TARGET",
                    f"Đợt điều trị đã hợp nhất '{e_key}' thiếu đợt đích hợp lệ.",
                )
            tgt_ep_raw = episodes_dict[e_model.merged_into_episode_id]
            if (
                tgt_ep_raw.get("status", "ACTIVE") != "ACTIVE"
                or tgt_ep_raw.get("patient_uid") != e_model.patient_uid
                or e_model.care_setting != "INPATIENT"
                or tgt_ep_raw.get("care_setting") != "INPATIENT"
            ):
                raise VaultSchemaValidationError(
                    "NON_CANONICAL_MERGED_EPISODE_TARGET",
                    f"Đợt điều trị đã hợp nhất '{e_key}' phải là đợt nội trú và trỏ trực tiếp tới đợt nội trú ACTIVE cùng người bệnh.",
                )

    counters_dict: dict[str, Any] = vault_data["counters"]
    for ck, cv in counters_dict.items():
        if not isinstance(ck, str) or not _COUNTER_KEY_RE.match(ck) or not _is_strict_int(cv) or int(cv) < 0:
            raise VaultSchemaValidationError(
                "INVALID_COUNTER_ENTRY",
                f"Bộ đếm mã ca '{ck}' không hợp lệ.",
            )

    cases_dict: dict[str, dict[str, Any]] = vault_data["cases"]
    seen_case_codes: set[str] = set()
    for c_key, c_raw in cases_dict.items():
        if not isinstance(c_raw, dict) or c_raw.get("case_id") != c_key:
            raise VaultSchemaValidationError(
                "CASE_KEY_MISMATCH",
                f"Khóa hồ sơ ca '{c_key}' không khớp trường case_id bên trong.",
            )
        try:
            c_model = StoredCaseRecord.model_validate(c_raw)
        except ValidationError as exc:
            raise VaultSchemaValidationError(
                "INVALID_CASE_RECORD",
                f"Hồ sơ ca nội soi '{c_key}' sai lược đồ dữ liệu.",
            ) from exc

        m_code = _CASE_CODE_RE.match(c_model.case_code)
        if not m_code or m_code.group(1) != c_model.track:
            raise VaultSchemaValidationError(
                "INVALID_CASE_CODE_FORMAT",
                f"Mã ca '{c_model.case_code}' không khớp phân hệ '{c_model.track}'.",
            )
        if c_model.case_code in seen_case_codes:
            raise VaultSchemaValidationError(
                "DUPLICATE_CASE_CODE",
                f"Phát hiện trùng mã ca '{c_model.case_code}' trong bản sao lưu.",
            )
        seen_case_codes.add(c_model.case_code)

        counter_bucket = f"{m_code.group(1)}-{m_code.group(2)}"
        seq_num = int(m_code.group(3))
        if int(counters_dict.get(counter_bucket, -1)) < seq_num:
            raise VaultSchemaValidationError(
                "COUNTER_MONOTONICITY_VIOLATION",
                f"Bộ đếm '{counter_bucket}' nhỏ hơn số thứ tự mã ca '{c_model.case_code}'.",
            )

        if c_model.patient_uid not in patients_dict:
            raise VaultSchemaValidationError(
                "BROKEN_CASE_PATIENT_FK",
                f"Ca nội soi '{c_key}' trỏ tới patient_uid '{c_model.patient_uid}' không tồn tại.",
            )
        if c_model.episode_id not in episodes_dict:
            raise VaultSchemaValidationError(
                "BROKEN_CASE_EPISODE_FK",
                f"Ca nội soi '{c_key}' trỏ tới episode_id '{c_model.episode_id}' không tồn tại.",
            )
        ep_owner = episodes_dict[c_model.episode_id].get("patient_uid")
        if ep_owner != c_model.patient_uid:
            raise VaultSchemaValidationError(
                "CASE_EPISODE_PATIENT_MISMATCH",
                f"Ca nội soi '{c_key}' có patient_uid khác với chủ sở hữu của đợt điều trị '{c_model.episode_id}'.",
            )

        if c_model.record_status == "ACTIVE":
            pat_obj = patients_dict[c_model.patient_uid]
            ep_obj = episodes_dict[c_model.episode_id]
            if pat_obj.get("status", "ACTIVE") == "MERGED_SUPERSEDED":
                raise VaultSchemaValidationError(
                    "ACTIVE_CASE_ON_SUPERSEDED_PATIENT",
                    f"Ca đang hoạt động '{c_key}' trỏ vào hồ sơ người bệnh đã gộp '{c_model.patient_uid}'.",
                )
            if ep_obj.get("status", "ACTIVE") == "MERGED_SUPERSEDED":
                raise VaultSchemaValidationError(
                    "ACTIVE_CASE_ON_SUPERSEDED_EPISODE",
                    f"Ca đang hoạt động '{c_key}' trỏ vào đợt điều trị đã hợp nhất '{c_model.episode_id}'.",
                )
            if c_model.care_setting == "INPATIENT":
                if ep_obj.get("care_setting") != "INPATIENT" or not (pat_obj.get("hospital_mrn") or "").strip():
                    raise VaultSchemaValidationError(
                        "INPATIENT_MRN_INVARIANT_VIOLATION",
                        f"Ca nội trú '{c_key}' thiếu mã hồ sơ bệnh viện hoặc gắn sai đợt ngoại trú.",
                    )

    surv_dict: dict[str, dict[str, Any]] = vault_data["surveillance"]
    for s_cid, s_raw in surv_dict.items():
        if s_cid not in cases_dict or not isinstance(s_raw, dict):
            raise VaultSchemaValidationError(
                "BROKEN_SURVEILLANCE_CASE_FK",
                f"Bản ghi hẹn soi lại '{s_cid}' không khớp ca gốc trong cases.",
            )
        try:
            s_model = StoredSurveillanceRecord.model_validate(s_raw)
        except ValidationError as exc:
            raise VaultSchemaValidationError(
                "INVALID_SURVEILLANCE_RECORD",
                f"Bản ghi hẹn soi lại '{s_cid}' sai lược đồ.",
            ) from exc
        if s_model.fulfilled_by_case_id:
            f_cid = s_model.fulfilled_by_case_id
            if (
                f_cid == s_cid
                or f_cid not in cases_dict
                or cases_dict[f_cid].get("patient_uid") != cases_dict[s_cid].get("patient_uid")
            ):
                raise VaultSchemaValidationError(
                    "INVALID_SURVEILLANCE_FULFILLMENT_LINK",
                    f"Liên kết hoàn tất hẹn soi lại của ca '{s_cid}' trỏ sai ca đích hoặc khác người bệnh.",
                )

    return copy.deepcopy(vault_data)


def build_profile_b_row(
    case: dict[str, Any],
    *,
    patients_by_id: dict[str, dict[str, Any]],
    ercp_indices: dict[str, int],
    master_key: bytes,
    shift_key: bytes,
    scope_id: str,
    export_dataset_epoch: int = 1,
    profile_b_lineage_seq: int = 1,
) -> dict[str, Any]:
    """Profile B: Patient-scoped HMAC + deterministic per-patient date shift in [-30, +30] days."""
    patient_uid = case["patient_uid"]
    episode_id = case.get("episode_id") or case["case_id"]
    pat = patients_by_id.get(patient_uid) or {}

    subj_msg = f"endolog_v1:{scope_id}:{patient_uid}".encode("utf-8")
    research_subject_id = hmac.new(master_key, subj_msg, hashlib.sha256).hexdigest()[:24]
    epi_msg = f"endolog_v1:{scope_id}:{episode_id}".encode("utf-8")
    research_episode_id = hmac.new(master_key, epi_msg, hashlib.sha256).hexdigest()[:24]

    shift_digest = hmac.new(shift_key, research_subject_id.encode("utf-8"), hashlib.sha256).digest()
    delta_days = (int.from_bytes(shift_digest[:8], "big") % 61) - 30
    proc_date = dt.date.fromisoformat((case["procedure_start_at"])[:10])
    shifted_date = (proc_date + dt.timedelta(days=delta_days)).isoformat()

    proc_year = proc_date.year
    raw_age = case.get("age")
    if raw_age is None:
        raw_age = max(0, proc_year - int(pat.get("birth_year") or proc_year))
    age_capped = "90+" if int(raw_age) >= 90 else str(int(raw_age))
    sex = case.get("sex") or pat.get("sex") or "O"

    segs = extract_bbps_segments(case)
    bbps_res = (
        evaluate_bbps(segs[0], segs[1], segs[2], cecal_intubation=case.get("cecal_intubation") or "NA")
        if segs
        else {"total": None, "adequate": False}
    )
    ae = summarize_case_adverse_events(case)
    idx = case.get("index_lesion") or {}
    wc = case.get("whole_case_summary") or {}
    ercp_det = case.get("ercp_detail") or {}

    return {
        "research_subject_id": research_subject_id,
        "research_episode_id": research_episode_id,
        "case_code": case["case_code"],
        "track": case["track"],
        "care_setting": case.get("care_setting") or "OUTPATIENT",
        "shifted_procedure_date": shifted_date,
        "age_years_capped": age_capped,
        "sex": sex,
        "indication": case.get("indication") or "",
        "cecal_intubation": case.get("cecal_intubation") or "NA",
        "bbps_total": bbps_res["total"],
        "bbps_adequate": "YES" if bbps_res["adequate"] else ("NO" if segs else "NA"),
        "macroscopic_polyp_count": wc.get("macroscopic_polyp_count"),
        "any_confirmed_adenoma": wc.get("any_confirmed_adenoma"),
        "any_confirmed_ssl": wc.get("any_confirmed_ssl"),
        "index_lesion_site": idx.get("anatomical_site") or "",
        "index_lesion_size_mm": idx.get("size_mm"),
        "index_lesion_resection": idx.get("resection_method") or "NONE",
        "index_lesion_histology": idx.get("histology_type") or "NONE",
        "pathology_completion_status": case.get("pathology_completion_status") or "NOT_APPLICABLE",
        "ercp_session_in_episode": ercp_indices.get(case["case_id"]) if case["track"] == "ERCP" else None,
        "ercp_papilla_status": ercp_det.get("papilla_status") if case["track"] == "ERCP" else None,
        "ercp_selective_cannulation": ercp_det.get("selective_cannulation") if case["track"] == "ERCP" else None,
        "followup_30d_status": ae["followup_30d_status"],
        "highest_agree_grade": ae["highest_agree_grade"],
        "highest_pep_severity": ae["highest_pep_severity"],
        "export_dataset_epoch": max(1, int(export_dataset_epoch)),
        "profile_b_lineage_seq": max(1, int(profile_b_lineage_seq)),
    }


def export_profile_b_rows(
    state_snapshot: dict[str, Any],
    *,
    master_key: bytes,
    shift_key: bytes,
    scope_id: str = "endolog_bvbd_v1",
    track_filter: str | None = None,
) -> list[dict[str, Any]]:
    cfg = state_snapshot.get("settings") or {}
    ds_epoch = max(1, int(cfg.get("export_dataset_epoch", 1) or 1))
    lineage_seq = max(1, int(cfg.get("profile_b_lineage_seq", 1) or 1))
    all_cases = [
        c for c in state_snapshot.get("cases", {}).values() if c.get("record_status", "ACTIVE") == "ACTIVE"
    ]
    ercp_idx = compute_ercp_session_indices(all_cases, state_snapshot.get("episodes"))
    filtered = [c for c in all_cases if not track_filter or c.get("track") == track_filter]
    filtered.sort(key=lambda x: (x.get("procedure_start_at") or "", x.get("case_code") or ""))
    return [
        build_profile_b_row(
            c,
            patients_by_id=state_snapshot.get("patients", {}),
            ercp_indices=ercp_idx,
            master_key=master_key,
            shift_key=shift_key,
            scope_id=scope_id,
            export_dataset_epoch=ds_epoch,
            profile_b_lineage_seq=lineage_seq,
        )
        for c in filtered
    ]


def rows_to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    if not rows:
        return b""
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def rows_to_xlsx_bytes(rows: list[dict[str, Any]], sheet_title: str = "EndoLog_Export") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _mask_small_cell(count: int, suppress: bool) -> int | str:
    if suppress and 0 < count < 5:
        return "<5"
    return count


def export_profile_c_summary(
    state_snapshot: dict[str, Any],
    *,
    min_adr_age: int = 45,
    suppress_small_cells: bool = True,
) -> dict[str, Any]:
    """Profile C: Aggregated KPI report with k < 5 small-cell suppression."""
    cases = list(state_snapshot.get("cases", {}).values())
    n_min_cfg = int((state_snapshot.get("settings") or {}).get("kpi_min_sample_size", 20))
    kpi = compute_kpi_snapshot(
        cases,
        patients_by_id=state_snapshot.get("patients", {}),
        min_adr_age=min_adr_age,
        n_min=n_min_cfg,
    )
    metrics_rows = []
    for key, label in [
        ("cir", "Tỷ lệ luồn tới manh tràng (CIR)"),
        ("bbps_adequate", "Tỷ lệ chuẩn bị đại tràng đạt (BBPS ≥ 6 & mỗi đoạn ≥ 2)"),
        ("pdr", f"Tỷ lệ phát hiện polyp đại thể (PDR ≥ {min_adr_age} tuổi)"),
        ("adr", f"Tỷ lệ phát hiện u tuyến (ADR ≥ {min_adr_age} tuổi, đã có GPB)"),
        ("ssldr", f"Tỷ lệ phát hiện polyp răng cưa không cuống (SSLDR ≥ {min_adr_age} tuổi)"),
        ("ercp_native_cannulation", "Tỷ lệ thông nhú chọn lọc trên nhú Vater nguyên vẹn (ERCP)"),
        ("ercp_pep", "Tỷ lệ viêm tụy cấp sau ERCP trên ca hoàn tất theo dõi"),
    ]:
        block = kpi[key]
        num = int(block["numerator"])
        den = int(block.get("denominator", block.get("completed_fu_denominator", 0)))
        masked_num = _mask_small_cell(num, suppress_small_cells)
        masked_den = _mask_small_cell(den, suppress_small_cells)
        rate = None if (suppress_small_cells and (0 < num < 5 or 0 < den < 5)) else block["rate_pct"]
        metrics_rows.append(
            {
                "metric_code": key,
                "metric_label_vi": label,
                "numerator": masked_num,
                "denominator": masked_den,
                "rate_pct": rate,
            }
        )
    return {
        "contract": "EndoLog-Export-Profile-C-v1.0",
        "suppress_small_cells_k_lt_5": suppress_small_cells,
        "min_adr_age": min_adr_age,
        "total_active_cases": _mask_small_cell(kpi["total_active_cases"], suppress_small_cells),
        "metrics": metrics_rows,
    }
