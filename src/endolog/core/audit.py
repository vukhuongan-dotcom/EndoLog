"""Server-authoritative Linear Hash Chain for clinical auditability."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64


def _canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_entry_hash(
    *,
    seq: int,
    timestamp_utc: str,
    actor_username: str,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict[str, Any],
    prev_hash: str,
) -> str:
    material = "|".join(
        [
            prev_hash,
            str(seq),
            timestamp_utc,
            actor_username,
            actor_role,
            action,
            entity_type,
            entity_id,
            _canonical_json(detail),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_audit_entry(
    existing_chain: list[dict[str, Any]],
    *,
    actor_username: str,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: str,
    detail: dict[str, Any] | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    seq = len(existing_chain) + 1
    prev_hash = existing_chain[-1]["entry_hash"] if existing_chain else GENESIS_HASH
    ts = now_utc or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    safe_detail = detail or {}
    entry_hash = compute_entry_hash(
        seq=seq,
        timestamp_utc=ts,
        actor_username=actor_username,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=safe_detail,
        prev_hash=prev_hash,
    )
    return {
        "seq": seq,
        "timestamp_utc": ts,
        "actor_username": actor_username,
        "actor_role": actor_role,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "detail": safe_detail,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
    }


def verify_audit_chain(chain: list[dict[str, Any]]) -> dict[str, Any]:
    expected_prev = GENESIS_HASH
    for idx, item in enumerate(chain, start=1):
        if item.get("seq") != idx:
            return {
                "valid": False,
                "checked_entries": idx - 1,
                "broken_at_seq": idx,
                "reason": "SEQ_GAP_OR_OUT_OF_ORDER",
            }
        if item.get("prev_hash") != expected_prev:
            return {
                "valid": False,
                "checked_entries": idx - 1,
                "broken_at_seq": idx,
                "reason": "PREV_HASH_MISMATCH",
            }
        recomputed = compute_entry_hash(
            seq=item["seq"],
            timestamp_utc=item["timestamp_utc"],
            actor_username=item["actor_username"],
            actor_role=item["actor_role"],
            action=item["action"],
            entity_type=item["entity_type"],
            entity_id=item["entity_id"],
            detail=item.get("detail", {}),
            prev_hash=expected_prev,
        )
        if recomputed != item.get("entry_hash"):
            return {
                "valid": False,
                "checked_entries": idx - 1,
                "broken_at_seq": idx,
                "reason": "ENTRY_HASH_TAMPERED",
            }
        expected_prev = recomputed

    return {
        "valid": True,
        "checked_entries": len(chain),
        "head_hash": expected_prev,
        "broken_at_seq": None,
        "reason": "OK",
    }


_PRE_RESTORE_NAME_RE_STR = "pre_restore_"

RestoreLineageSignature = tuple[str, str, str, int, str, int]


def _is_hex_64(val: str) -> bool:
    return len(val) == 64 and all(ch in "0123456789abcdef" for ch in val)


def _is_strict_positive_int(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool) and val >= 1


def _is_safe_pre_restore_filename(fname: str) -> bool:
    if not fname or Path(fname).name != fname:
        return False
    if not (fname.startswith(_PRE_RESTORE_NAME_RE_STR) and fname.endswith(".json")):
        return False
    stem_mid = fname[len(_PRE_RESTORE_NAME_RE_STR) : -5]
    return bool(stem_mid) and all(ch.isalnum() or ch == "_" for ch in stem_mid)


def extract_restore_lineage_signature(record: dict[str, Any] | None) -> RestoreLineageSignature | None:
    """Extract canonical 6-tuple signature shared by RESTORE_PROFILE_A_ENCRYPTED audit detail and StoredAuditLineageBridge."""
    if not isinstance(record, dict):
        return None
    fname = str(record.get("pre_restore_filename") or "").strip()
    expected_sha = str(record.get("pre_restore_sha256") or "").strip().lower()
    displaced_head = str(record.get("displaced_live_head_hash") or "").strip().lower()
    displaced_seq_raw = record.get("displaced_live_seq")
    backup_head = str(record.get("backup_pre_append_head_hash") or "").strip().lower()
    backup_seq_raw = record.get("backup_pre_append_seq")
    if (
        not _is_safe_pre_restore_filename(fname)
        or not _is_hex_64(expected_sha)
        or not _is_hex_64(displaced_head)
        or not _is_strict_positive_int(displaced_seq_raw)
        or not _is_hex_64(backup_head)
        or not _is_strict_positive_int(backup_seq_raw)
    ):
        return None
    return (
        fname,
        expected_sha,
        displaced_head,
        int(displaced_seq_raw),
        backup_head,
        int(backup_seq_raw),
    )


def collect_audit_chain_restore_signatures(
    chain: list[dict[str, Any]] | None,
) -> tuple[bool, set[RestoreLineageSignature]]:
    """Collect canonical signatures for every RESTORE_PROFILE_A_ENCRYPTED entry in a hash-chained audit_chain."""
    if chain is None:
        return True, set()
    if not isinstance(chain, list):
        return False, set()
    sigs: set[RestoreLineageSignature] = set()
    for item in chain:
        if not isinstance(item, dict):
            return False, set()
        if item.get("action") == "RESTORE_PROFILE_A_ENCRYPTED":
            sig = extract_restore_lineage_signature(item.get("detail"))
            if sig is None:
                return False, set()
            sigs.add(sig)
    return True, sigs


def verify_audit_lineage_bridges(
    bridges: list[dict[str, Any]] | None,
    *,
    backup_dir: Path | None = None,
    audit_chain: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify two-way cryptographic restore lineage bridges, displaced audit chains, and hash-chained restore event bijection (G04/C02)."""
    if bridges is not None and not isinstance(bridges, list):
        return {
            "valid": False,
            "bridge_count": 0,
            "audit_chain_consistency_valid": False,
            "items": [],
        }

    items = bridges or []
    verified_items: list[dict[str, Any]] = []
    all_valid = True
    bridge_sigs: set[RestoreLineageSignature] = set()
    seen_sha_by_fname: dict[str, str] = {}
    displaced_restore_sigs: set[RestoreLineageSignature] = set()
    nested_bridge_sigs: set[RestoreLineageSignature] = set()

    for idx, raw in enumerate(items, start=1):
        if not isinstance(raw, dict):
            all_valid = False
            continue
        fname = str(raw.get("pre_restore_filename") or "").strip()
        expected_sha = str(raw.get("pre_restore_sha256") or "").strip().lower()
        safe_basename = _is_safe_pre_restore_filename(fname)
        sig = extract_restore_lineage_signature(raw)
        valid_meta_hashes = sig is not None

        if sig is not None:
            if fname in seen_sha_by_fname and seen_sha_by_fname[fname] != expected_sha:
                all_valid = False
            seen_sha_by_fname[fname] = expected_sha
            bridge_sigs.add(sig)
        else:
            all_valid = False

        file_present = False
        sha256_matches = False
        displaced_chain_valid = False
        if safe_basename and backup_dir is not None:
            candidate_path = backup_dir / fname
            if candidate_path.is_file():
                file_present = True
                try:
                    raw_bytes = candidate_path.read_bytes()
                    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
                    sha256_matches = bool(expected_sha) and actual_sha == expected_sha
                    if sha256_matches and sig is not None:
                        displaced_obj = json.loads(raw_bytes.decode("utf-8"))
                        if isinstance(displaced_obj, dict) and isinstance(displaced_obj.get("audit_chain"), list):
                            d_ver = verify_audit_chain(displaced_obj["audit_chain"])
                            ok_disp_sigs, disp_sigs = collect_audit_chain_restore_signatures(
                                displaced_obj["audit_chain"]
                            )
                            nested_bridges_raw = displaced_obj.get("audit_lineage_bridges") or []
                            ok_nested = isinstance(nested_bridges_raw, list)
                            if ok_nested:
                                for nb in nested_bridges_raw:
                                    nb_sig = extract_restore_lineage_signature(nb)
                                    if nb_sig is None:
                                        ok_nested = False
                                        break
                                    nested_bridge_sigs.add(nb_sig)
                            displaced_chain_valid = bool(
                                d_ver.get("valid")
                                and ok_disp_sigs
                                and ok_nested
                                and str(d_ver.get("head_hash") or "").lower() == sig[2]
                                and int(d_ver.get("checked_entries") or -1) == sig[3]
                            )
                            if displaced_chain_valid:
                                displaced_restore_sigs |= disp_sigs
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                    sha256_matches = False
                    displaced_chain_valid = False

        bridge_ok = bool(
            safe_basename
            and valid_meta_hashes
            and (backup_dir is None or (file_present and sha256_matches and displaced_chain_valid))
        )
        if not bridge_ok:
            all_valid = False
        verified_items.append(
            {
                "bridge_index": idx,
                "restored_at_utc": raw.get("restored_at_utc"),
                "actor_username": raw.get("actor_username"),
                "previous_store_epoch": raw.get("previous_store_epoch", 1),
                "new_store_epoch": raw.get("new_store_epoch"),
                "vault_blob_sha256": raw.get("vault_blob_sha256"),
                "backup_pre_append_head_hash": raw.get("backup_pre_append_head_hash"),
                "backup_pre_append_seq": raw.get("backup_pre_append_seq"),
                "displaced_live_head_hash": raw.get("displaced_live_head_hash"),
                "displaced_live_seq": raw.get("displaced_live_seq"),
                "pre_restore_filename": fname if safe_basename else "INVALID_FILENAME",
                "pre_restore_sha256": expected_sha,
                "pre_restore_file_present": file_present,
                "pre_restore_sha256_valid": sha256_matches,
                "displaced_audit_chain_valid": displaced_chain_valid if backup_dir is not None else None,
                "preserve_current_users": bool(raw.get("preserve_current_users", True)),
                "key_mismatch_policy": raw.get("key_mismatch_policy", "REJECT"),
                "valid": bridge_ok,
            }
        )

    chain_consistency_ok = True
    if backup_dir is not None and not nested_bridge_sigs.issubset(bridge_sigs):
        chain_consistency_ok = False
    if audit_chain is not None:
        ok_root_sigs, root_restore_sigs = collect_audit_chain_restore_signatures(audit_chain)
        if not ok_root_sigs:
            chain_consistency_ok = False
        elif backup_dir is not None:
            expected_all_sigs = root_restore_sigs | displaced_restore_sigs
            if bridge_sigs != expected_all_sigs:
                chain_consistency_ok = False
        else:
            if not root_restore_sigs.issubset(bridge_sigs):
                chain_consistency_ok = False

    if not chain_consistency_ok:
        all_valid = False

    return {
        "valid": all_valid,
        "bridge_count": len(verified_items),
        "audit_chain_consistency_valid": chain_consistency_ok,
        "items": verified_items,
    }
