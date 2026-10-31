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


def verify_audit_lineage_bridges(
    bridges: list[dict[str, Any]] | None,
    *,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    """Verify two-way cryptographic restore lineage bridges without exposing OS paths or PHI (G04)."""
    items = bridges or []
    verified_items: list[dict[str, Any]] = []
    all_valid = True

    for idx, raw in enumerate(items, start=1):
        fname = str(raw.get("pre_restore_filename") or "").strip()
        expected_sha = str(raw.get("pre_restore_sha256") or "").strip().lower()
        safe_basename = bool(
            fname
            and Path(fname).name == fname
            and fname.startswith("pre_restore_")
            and fname.endswith(".json")
        )
        file_present = False
        sha256_matches = False
        if safe_basename and backup_dir is not None:
            candidate_path = backup_dir / fname
            if candidate_path.is_file():
                file_present = True
                try:
                    actual_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
                    sha256_matches = bool(expected_sha) and actual_sha == expected_sha
                except OSError:
                    sha256_matches = False
        bridge_ok = bool(
            safe_basename
            and len(expected_sha) == 64
            and (backup_dir is None or (file_present and sha256_matches))
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
                "preserve_current_users": bool(raw.get("preserve_current_users", True)),
                "key_mismatch_policy": raw.get("key_mismatch_policy", "REJECT"),
                "valid": bridge_ok,
            }
        )

    return {
        "valid": all_valid,
        "bridge_count": len(verified_items),
        "items": verified_items,
    }
