"""Unadjusted Tabular Bernoulli QC-CUSUM (OD-03 locked; RA-CUSUM disabled in v1.0)."""

from __future__ import annotations

import math
from typing import Any

CUSUM_PRESETS: dict[str, tuple[float, float]] = {
    "DEFAULT_90": (0.10, 0.20),  # 90% target success (CIR general & ERCP native cannulation)
    "SCREENING_CIR_95": (0.05, 0.10),  # 95% target success (screening colonoscopy CIR)
}


def evaluate_tabular_qc_cusum(
    failure_outcomes: list[int],
    *,
    p0: float = 0.10,
    p1: float = 0.20,
    alpha: float = 0.05,
    beta: float = 0.10,
    case_codes: list[str] | None = None,
) -> dict[str, Any]:
    if not (0.0 < p0 < p1 < 1.0):
        raise ValueError("Tham số QC-CUSUM phải thỏa 0 < p0 < p1 < 1.")

    w_fail = math.log(p1 / p0)
    w_succ = math.log((1.0 - p1) / (1.0 - p0))
    h_limit = math.log((1.0 - beta) / alpha)

    s_cont = 0.0
    s_reset = 0.0
    trajectory: list[float] = [0.0]
    reset_trajectory: list[float] = [0.0]
    alarm_at: int | None = None
    points: list[dict[str, Any]] = []

    for idx, x_t in enumerate(failure_outcomes, start=1):
        w = w_fail if int(x_t) == 1 else w_succ
        s_cont = max(0.0, s_cont + w)
        s_reset = max(0.0, s_reset + w)
        triggered_now = False
        if s_cont >= h_limit and alarm_at is None:
            alarm_at = idx
        if s_reset >= h_limit:
            triggered_now = True
            trajectory_val = round(s_cont, 6)
            reset_val = round(s_reset, 6)
            s_reset = 0.0
        else:
            trajectory_val = round(s_cont, 6)
            reset_val = round(s_reset, 6)

        trajectory.append(trajectory_val)
        reset_trajectory.append(reset_val)
        points.append(
            {
                "index": idx,
                "case_code": case_codes[idx - 1] if case_codes and idx - 1 < len(case_codes) else f"CA-{idx:03d}",
                "failure": int(x_t),
                "s_continuous": trajectory_val,
                "s_reset_view": reset_val,
                "alarm_crossed": triggered_now,
            }
        )

    return {
        "ra_cusum_status": "DISABLED_UNVALIDATED_MODEL",
        "disclaimer_vi": (
            "Giám sát kiểm soát chất lượng cá nhân không hiệu chỉnh nguy cơ — chỉ dùng cho tự kiểm toán nội bộ, "
            "không dùng đánh giá thi đua hay kết luận năng lực pháp lý."
        ),
        "p0": p0,
        "p1": p1,
        "alpha": alpha,
        "beta": beta,
        "w_success": round(w_succ, 6),
        "w_failure": round(w_fail, 6),
        "h_limit": round(h_limit, 6),
        "trajectory": trajectory,
        "reset_trajectory": reset_trajectory,
        "alarm_case_number": alarm_at,
        "points": points,
    }


def build_cusum_series_from_cases(
    cases: list[dict[str, Any]],
    *,
    metric: str = "CIR",
    preset: str = "DEFAULT_90",
) -> dict[str, Any]:
    p0, p1 = CUSUM_PRESETS.get(preset, CUSUM_PRESETS["DEFAULT_90"])
    active = sorted(
        (c for c in cases if c.get("record_status", "ACTIVE") == "ACTIVE"),
        key=lambda x: (x.get("procedure_start_at") or "", x.get("case_code") or ""),
    )
    outcomes: list[int] = []
    codes: list[str] = []

    if metric == "ERCP_NATIVE":
        for c in active:
            if c.get("track") != "ERCP":
                continue
            det = c.get("ercp_detail") or c
            if (det.get("papilla_status") or "NATIVE_INTACT") == "NATIVE_INTACT" and not det.get(
                "duodenal_obstruction_or_altered", False
            ):
                outcomes.append(0 if det.get("selective_cannulation") == "SUCCESS" else 1)
                codes.append(c["case_code"])
    else:
        for c in active:
            if c.get("track") != "COL" or c.get("exclude_from_cir", False):
                continue
            if preset == "SCREENING_CIR_95" and c.get("indication") != "SCREENING":
                continue
            outcomes.append(0 if c.get("cecal_intubation") == "YES" else 1)
            codes.append(c["case_code"])

    res = evaluate_tabular_qc_cusum(outcomes, p0=p0, p1=p1, case_codes=codes)
    res["metric"] = metric
    res["preset"] = preset
    return res
