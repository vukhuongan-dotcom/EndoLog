"""Fail-closed Data Loss Prevention (DLP) scanner for free-text clinical notes."""

from __future__ import annotations

import re
from typing import Any

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("CCCD_12_DIGITS", re.compile(r"(?<!\d)0\d{11}(?!\d)")),
    ("CMND_9_DIGITS", re.compile(r"(?<!\d)\d{9}(?!\d)")),
    ("VN_PHONE_NUMBER", re.compile(r"(?<!\d)(?:0|\+84)(?:3|5|7|8|9)\d{8}(?!\d)")),
    ("BHYT_CARD_CODE", re.compile(r"\b[A-Z]{2}\d{13}\b")),
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

PROTECTED_NOTE_FIELDS = {
    "clinical_note",
    "indication_detail",
    "surgical_outcome_note",
    "complication_note",
    "ercp_procedure_note",
    "note",
}


class DlpViolationError(ValueError):
    def __init__(self, field_path: str, rule_code: str) -> None:
        self.field_path = field_path
        self.rule_code = rule_code
        super().__init__(
            f"Trường '{field_path}' chứa định danh cá nhân bị chặn bởi DLP ({rule_code}). "
            "Không nhập số CCCD/CMND, số điện thoại, mã thẻ BHYT hoặc email vào ô ghi chú tự do."
        )


def scan_text_for_pii(text: str, field_path: str = "note") -> None:
    if not text:
        return
    for rule_code, regex in PATTERNS:
        if regex.search(text):
            raise DlpViolationError(field_path=field_path, rule_code=rule_code)


def scan_payload_notes(payload: Any, path_prefix: str = "") -> None:
    if isinstance(payload, dict):
        for k, v in payload.items():
            sub_path = f"{path_prefix}.{k}" if path_prefix else k
            if k in PROTECTED_NOTE_FIELDS and isinstance(v, str):
                scan_text_for_pii(v, field_path=sub_path)
            elif isinstance(v, (dict, list)):
                scan_payload_notes(v, path_prefix=sub_path)
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            scan_payload_notes(item, path_prefix=f"{path_prefix}[{idx}]")
