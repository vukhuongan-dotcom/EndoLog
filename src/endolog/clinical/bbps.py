"""Boston Bowel Preparation Scale (BBPS) segment-aware evaluator."""

from __future__ import annotations

from typing import Any


def extract_bbps_segments(case: dict[str, Any]) -> list[int] | None:
    if case.get("bbps_segments") is not None:
        segs = case["bbps_segments"]
        if isinstance(segs, (list, tuple)) and len(segs) == 3 and all(s is not None for s in segs):
            return [int(segs[0]), int(segs[1]), int(segs[2])]
    r = case.get("bbps_right")
    t = case.get("bbps_transverse")
    l_seg = case.get("bbps_left")
    if r is None or t is None or l_seg is None:
        return None
    return [int(r), int(t), int(l_seg)]


def evaluate_bbps(
    right: int | None,
    transverse: int | None,
    left: int | None,
    *,
    cecal_intubation: str = "YES",
) -> dict[str, Any]:
    """BBPS adequacy requires cecal intubation = YES, all 3 segments scored, sum >= 6 AND each segment >= 2."""
    if cecal_intubation != "YES" or right is None or transverse is None or left is None:
        return {
            "evaluable": False,
            "segments": None,
            "total": None,
            "adequate": False,
        }
    segs = [int(right), int(transverse), int(left)]
    total = sum(segs)
    adequate = total >= 6 and all(s >= 2 for s in segs)
    return {
        "evaluable": True,
        "segments": segs,
        "total": total,
        "adequate": adequate,
    }
