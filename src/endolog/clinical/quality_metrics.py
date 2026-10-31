"""Quality KPI denominator/numerator engine (ASGE/ACG 2024 + ESGE 2016/2020) & ERCP session re-indexing."""

from __future__ import annotations

import statistics
from typing import Any

from endolog.clinical.adverse_events import summarize_case_adverse_events
from endolog.clinical.bbps import evaluate_bbps, extract_bbps_segments


def is_difficult_cannulation_esge_2016(
    papilla_status: str,
    contacts: int,
    time_min: float,
    unintended_pd: int,
) -> str:
    if papilla_status != "NATIVE_INTACT":
        return "NA_NON_NATIVE"
    if contacts > 5 or time_min > 5.0 or unintended_pd > 1:
        return "YES"
    return "NO"


def compute_ercp_session_indices(
    cases: list[dict[str, Any]],
    episodes_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Deterministic ordering (procedure_start_at, created_at, case_id) + prior_unrecorded_ercp_offset per episode."""
    by_episode: dict[str, list[dict[str, Any]]] = {}
    for c in cases:
        if c.get("track") == "ERCP" and c.get("record_status", "ACTIVE") == "ACTIVE":
            epi_id = c.get("episode_id") or c["case_id"]
            by_episode.setdefault(epi_id, []).append(c)

    result: dict[str, int] = {}
    for epi_id, epi_cases in by_episode.items():
        ordered = sorted(
            epi_cases,
            key=lambda x: (
                x.get("procedure_start_at") or "",
                x.get("created_at") or "",
                x.get("case_id") or "",
            ),
        )
        epi_obj = (episodes_by_id or {}).get(epi_id) or {}
        epi_offset = int(epi_obj.get("prior_unrecorded_ercp_offset") or 0)
        for idx, item in enumerate(ordered, start=1):
            case_offset = int(item.get("prior_unrecorded_ercp_offset") or epi_offset)
            result[item["case_id"]] = idx + case_offset
    return result


def _resolve_case_age(case: dict[str, Any], patients_by_id: dict[str, dict[str, Any]] | None) -> int:
    if "age" in case and case["age"] is not None:
        return int(case["age"])
    proc_year = int((case.get("procedure_start_at") or "2026")[:4])
    pat = (patients_by_id or {}).get(case.get("patient_uid") or "") or {}
    birth_year = int(pat.get("birth_year") or case.get("birth_year") or proc_year)
    return max(0, proc_year - birth_year)


def _pct(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round((num * 100.0) / den, 1)


def compute_kpi_snapshot(
    cases: list[dict[str, Any]],
    *,
    patients_by_id: dict[str, dict[str, Any]] | None = None,
    min_adr_age: int = 45,
) -> dict[str, Any]:
    """Compute personal endoscopy quality metrics with explicit numerators, denominators, and pending exclusions."""
    active_cases = [c for c in cases if c.get("record_status", "ACTIVE") == "ACTIVE"]

    colo_cases = [c for c in active_cases if c.get("track") == "COL"]
    cir_eligible = [c for c in colo_cases if not c.get("exclude_from_cir", False)]
    cir_num = sum(1 for c in cir_eligible if c.get("cecal_intubation") == "YES")

    bbps_eval: list[dict[str, Any]] = []
    bbps_adequate_num = 0
    for c in cir_eligible:
        segs = extract_bbps_segments(c)
        if c.get("cecal_intubation") == "YES" and segs is not None:
            bbps_eval.append(c)
            ev = evaluate_bbps(segs[0], segs[1], segs[2], cecal_intubation="YES")
            if ev["adequate"]:
                bbps_adequate_num += 1

    adr_cohort_all = [
        c
        for c in colo_cases
        if _resolve_case_age(c, patients_by_id) >= min_adr_age
        and c.get("indication") in ("SCREENING", "DIAGNOSTIC", "ABNORMAL_FECAL_TEST")
        and not c.get("has_ibd_or_polyposis", False)
        and c.get("cecal_intubation") == "YES"
    ]
    pdr_num = sum(
        1 for c in adr_cohort_all if ((c.get("whole_case_summary") or {}).get("macroscopic_polyp_count") or 0) >= 1
    )

    adr_pending_gpb = [
        c
        for c in adr_cohort_all
        if ((c.get("whole_case_summary") or {}).get("macroscopic_polyp_count") or 0) >= 1
        and c.get("pathology_completion_status") in ("PENDING", "PARTIAL")
    ]
    adr_evaluated = [c for c in adr_cohort_all if c not in adr_pending_gpb]
    adr_num = sum(
        1 for c in adr_evaluated if (c.get("whole_case_summary") or {}).get("any_confirmed_adenoma") == "YES"
    )
    ssldr_num = sum(
        1 for c in adr_evaluated if (c.get("whole_case_summary") or {}).get("any_confirmed_ssl") == "YES"
    )

    clean_wt_values = [
        float(c["withdrawal_time_clean_min"])
        for c in colo_cases
        if c.get("cecal_intubation") == "YES"
        and ((c.get("whole_case_summary") or {}).get("macroscopic_polyp_count") or 0) == 0
        and ((c.get("index_lesion") or {}).get("resection_method") or "NONE") == "NONE"
        and c.get("withdrawal_time_clean_min") is not None
    ]

    # ERCP KPIs
    ercp_cases = [c for c in active_cases if c.get("track") == "ERCP"]
    ercp_native = []
    ercp_cann_num = 0
    ercp_diff_num = 0
    for c in ercp_cases:
        det = c.get("ercp_detail") or c
        papilla = det.get("papilla_status") or "NATIVE_INTACT"
        obstructed = bool(det.get("duodenal_obstruction_or_altered", False))
        if papilla == "NATIVE_INTACT" and not obstructed:
            ercp_native.append(c)
            if det.get("selective_cannulation") == "SUCCESS":
                ercp_cann_num += 1
            diff = is_difficult_cannulation_esge_2016(
                papilla,
                int(det.get("cannulation_contacts_count") or 0),
                float(det.get("cannulation_time_min") or 0.0),
                int(det.get("unintended_pd_count") or 0),
            )
            if diff == "YES":
                ercp_diff_num += 1

    # Adverse event rates on completed 30-day follow-up
    all_fu_eval = []
    all_fu_missing = []
    agree_any_num = 0
    agree_severe_num = 0
    for c in active_cases:
        ae_sum = summarize_case_adverse_events(c)
        if ae_sum["completed_followup"]:
            all_fu_eval.append(c)
            if ae_sum["is_agree_any"]:
                agree_any_num += 1
            if ae_sum["is_agree_severe_ge_iii"]:
                agree_severe_num += 1
        else:
            all_fu_missing.append(c)

    ercp_fu_eval = []
    ercp_fu_missing = []
    pep_num = 0
    ercp_agree_severe_num = 0
    for c in ercp_cases:
        ae_sum = summarize_case_adverse_events(c)
        if ae_sum["completed_followup"]:
            ercp_fu_eval.append(c)
            if ae_sum["has_pep"]:
                pep_num += 1
            if ae_sum["is_agree_severe_ge_iii"]:
                ercp_agree_severe_num += 1
        else:
            ercp_fu_missing.append(c)

    return {
        "min_adr_age": min_adr_age,
        "total_active_cases": len(active_cases),
        "counts_by_track": {
            "EGD": sum(1 for c in active_cases if c.get("track") == "EGD"),
            "COL": len(colo_cases),
            "ERCP": len(ercp_cases),
        },
        "cir": {
            "numerator": cir_num,
            "denominator": len(cir_eligible),
            "rate_pct": _pct(cir_num, len(cir_eligible)),
            "target_pct": 90.0,
        },
        "bbps_adequate": {
            "numerator": bbps_adequate_num,
            "denominator": len(bbps_eval),
            "rate_pct": _pct(bbps_adequate_num, len(bbps_eval)),
            "target_pct": 90.0,
        },
        "pdr": {
            "numerator": pdr_num,
            "denominator": len(adr_cohort_all),
            "rate_pct": _pct(pdr_num, len(adr_cohort_all)),
        },
        "adr": {
            "numerator": adr_num,
            "denominator": len(adr_evaluated),
            "rate_pct": _pct(adr_num, len(adr_evaluated)),
            "target_pct": 35.0,
            "pending_gpb_excluded_count": len(adr_pending_gpb),
        },
        "ssldr": {
            "numerator": ssldr_num,
            "denominator": len(adr_evaluated),
            "rate_pct": _pct(ssldr_num, len(adr_evaluated)),
            "target_pct": 6.0,
            "pending_gpb_excluded_count": len(adr_pending_gpb),
        },
        "clean_withdrawal_time": {
            "count": len(clean_wt_values),
            "mean_min": round(statistics.mean(clean_wt_values), 2) if clean_wt_values else None,
            "median_min": round(statistics.median(clean_wt_values), 2) if clean_wt_values else None,
            "target_min": 6.0,
        },
        "ercp_native_cannulation": {
            "numerator": ercp_cann_num,
            "denominator": len(ercp_native),
            "rate_pct": _pct(ercp_cann_num, len(ercp_native)),
            "target_pct": 90.0,
            "difficult_esge2016_count": ercp_diff_num,
        },
        "adverse_events_all": {
            "agree_any_numerator": agree_any_num,
            "agree_severe_numerator": agree_severe_num,
            "completed_fu_denominator": len(all_fu_eval),
            "agree_severe_rate_pct": _pct(agree_severe_num, len(all_fu_eval)),
            "missing_or_pending_fu_count": len(all_fu_missing),
        },
        "ercp_pep": {
            "numerator": pep_num,
            "ercp_agree_severe_numerator": ercp_agree_severe_num,
            "completed_fu_denominator": len(ercp_fu_eval),
            "rate_pct": _pct(pep_num, len(ercp_fu_eval)),
            "missing_or_pending_fu_count": len(ercp_fu_missing),
        },
    }
