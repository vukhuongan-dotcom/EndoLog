"""Independent AGREE 2022 and Post-ERCP Pancreatitis (PEP) adverse event grading."""

from __future__ import annotations

from typing import Any

AGREE_RANK: dict[str, int] = {
    "NONE": 0,
    "I": 1,
    "II": 2,
    "IIIa": 3,
    "IIIb": 4,
    "IVa": 5,
    "IVb": 6,
    "V": 7,
}

PEP_RANK: dict[str, int] = {
    "NONE": 0,
    "MILD": 1,
    "MODERATE": 2,
    "SEVERE": 3,
}

SEVERE_AGREE_SET = {"IIIa", "IIIb", "IVa", "IVb", "V"}


def summarize_case_adverse_events(case: dict[str, Any]) -> dict[str, Any]:
    """Summarize highest AGREE 2022 grade and PEP severity independently without forced 1:1 mapping."""
    events = case.get("adverse_events") or []
    max_agree = case.get("agree_grade") or "NONE"
    max_pep = case.get("pep_severity") or "NONE"

    for ev in events:
        ag = ev.get("agree_grade") or "NONE"
        if AGREE_RANK.get(ag, 0) > AGREE_RANK.get(max_agree, 0):
            max_agree = ag
        pep = ev.get("pep_severity") or "NONE"
        if PEP_RANK.get(pep, 0) > PEP_RANK.get(max_pep, 0):
            max_pep = pep

    fu_status = case.get("followup_30d_status") or case.get("followup_status") or "PENDING_WINDOW"
    completed_followup = fu_status in ("COMPLETED_NO_AE", "COMPLETED_WITH_AE")

    return {
        "highest_agree_grade": max_agree,
        "is_agree_any": AGREE_RANK.get(max_agree, 0) >= 1,
        "is_agree_severe_ge_iii": max_agree in SEVERE_AGREE_SET,
        "highest_pep_severity": max_pep,
        "has_pep": max_pep != "NONE",
        "followup_30d_status": fu_status,
        "completed_followup": completed_followup,
    }
