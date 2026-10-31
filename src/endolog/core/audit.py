"""Server-authoritative Linear Hash Chain for clinical auditability."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
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
