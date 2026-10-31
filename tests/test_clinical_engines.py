"""Phase 2 unit tests covering SYN-F01..F09 clinical algorithms, BBPS, KPIs, ERCP ESGE 2016, and QC-CUSUM."""

from __future__ import annotations

from endolog.clinical.bbps import evaluate_bbps
from endolog.clinical.cusum import evaluate_tabular_qc_cusum
from endolog.clinical.quality_metrics import (
    compute_ercp_session_indices,
    compute_kpi_snapshot,
    is_difficult_cannulation_esge_2016,
)
from endolog.clinical.surveillance_scheduler import (
    build_surveillance_recommendation,
    evaluate_single_guideline,
)


def test_bbps_segment_minimum_rule() -> None:
    # 3 + 2 + 1 = 6 total, but left segment = 1 < 2 -> MUST BE INADEQUATE
    inadequate = evaluate_bbps(3, 2, 1, cecal_intubation="YES")
    assert inadequate["total"] == 6
    assert inadequate["adequate"] is False

    # 2 + 2 + 2 = 6 total, all >= 2 -> ADEQUATE
    adequate = evaluate_bbps(2, 2, 2, cecal_intubation="YES")
    assert adequate["total"] == 6
    assert adequate["adequate"] is True


def test_multi_guideline_usmstf_default_and_esge_divergence() -> None:
    # 3-4 small adenomas (<10mm LGD): USMSTF 2020 -> 3_5Y vs ESGE 2020 -> 10Y_OR_SCREENING
    case_3_4_ad = {
        "case_id": "cas_div_1",
        "case_code": "COL-2026-0099",
        "track": "COL",
        "procedure_start_at": "2026-10-15T09:00:00",
        "cecal_intubation": "YES",
        "bbps_right": 2,
        "bbps_transverse": 3,
        "bbps_left": 3,
        "pathology_completion_status": "COMPLETE",
        "index_lesion": {
            "size_mm": 7,
            "histology_type": "TUBULAR_ADENOMA",
            "dysplasia_grade": "LGD",
            "resection_method": "COLD_SNARE",
        },
        "whole_case_summary": {
            "macroscopic_polyp_count": 3,
            "complete_resection_all_lesions": "ALL_RESECTED_COMPLETELY",
            "any_confirmed_adenoma": "YES",
            "confirmed_adenoma_count_bin": "3_4",
            "max_adenoma_size_mm": 7,
            "any_confirmed_ssl": "NO",
        },
    }
    rec = build_surveillance_recommendation(case_3_4_ad, primary_colo_mode="USMSTF_2020")
    assert rec["guideline_id"] == "USMSTF_POST_POLYPECTOMY_2020"
    assert rec["recommended_interval_code"] == "3_5Y"
    assert rec["reference_guideline_id"] == "ESGE_POST_POLYPECTOMY_2020"
    assert rec["reference_interval_code"] == "10Y_OR_SCREENING"
    assert rec["is_divergent_guideline"] is True


def test_esd_hm1_vs_vm1_and_egd_biopsy_never_curative_r0() -> None:
    case_egd_biopsy = {
        "track": "EGD",
        "pathology_completion_status": "COMPLETE",
        "index_lesion": {"resection_method": "BIOPSY_ONLY", "histology_type": "LGD_VIENNA_C3"},
    }
    res_biopsy = evaluate_single_guideline(case_egd_biopsy)
    assert res_biopsy["category"] == "NEEDS_PHYSICIAN_REVIEW"
    assert res_biopsy["interval"] is None

    case_esd_hm1 = {
        "track": "COL",
        "pathology_completion_status": "COMPLETE",
        "index_lesion": {
            "resection_method": "ESD",
            "margins_status": "HM1_ONLY",
            "sm_invasion_um": 350,
            "lvi_status": "NEGATIVE",
            "differentiation": "WELL_MOD",
            "budding_grade": "BD1",
        },
    }
    case_esd_vm1 = {
        "track": "COL",
        "pathology_completion_status": "COMPLETE",
        "index_lesion": {
            "resection_method": "ESD",
            "margins_status": "VM1_OR_R1",
            "sm_invasion_um": 1350,
            "lvi_status": "POSITIVE",
            "differentiation": "WELL_MOD",
            "budding_grade": "BD2_BD3",
        },
    }
    assert evaluate_single_guideline(case_esd_hm1)["category"] == "LOCAL_SCAR_SURVEILLANCE"
    assert evaluate_single_guideline(case_esd_vm1)["category"] == "SURGICAL_MDT_CONSULT_ALERT"


def test_kpi_pending_gpb_exclusion_and_age_45_vs_50_toggle() -> None:
    cases = [
        {
            "case_id": "c1",
            "track": "COL",
            "age": 47,
            "indication": "SCREENING",
            "cecal_intubation": "YES",
            "bbps_segments": [3, 3, 3],
            "pathology_completion_status": "COMPLETE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "whole_case_summary": {"macroscopic_polyp_count": 1, "any_confirmed_adenoma": "YES", "any_confirmed_ssl": "NO"},
        },
        {
            "case_id": "c2",
            "track": "COL",
            "age": 54,
            "indication": "SCREENING",
            "cecal_intubation": "YES",
            "bbps_segments": [2, 2, 2],
            "pathology_completion_status": "PENDING",
            "followup_30d_status": "PENDING_WINDOW",
            "whole_case_summary": {"macroscopic_polyp_count": 2, "any_confirmed_adenoma": "PENDING_UNKNOWN"},
        },
        {
            "case_id": "c3",
            "track": "COL",
            "age": 58,
            "indication": "DIAGNOSTIC",
            "cecal_intubation": "YES",
            "bbps_segments": [3, 2, 2],
            "pathology_completion_status": "NOT_APPLICABLE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "whole_case_summary": {"macroscopic_polyp_count": 0, "any_confirmed_adenoma": "NO", "any_confirmed_ssl": "NO"},
        },
    ]
    kpi_45 = compute_kpi_snapshot(cases, min_adr_age=45)
    assert kpi_45["pdr"]["numerator"] == 2 and kpi_45["pdr"]["denominator"] == 3
    assert kpi_45["adr"]["numerator"] == 1 and kpi_45["adr"]["denominator"] == 2
    assert kpi_45["adr"]["pending_gpb_excluded_count"] == 1

    kpi_50 = compute_kpi_snapshot(cases, min_adr_age=50)
    assert kpi_50["adr"]["numerator"] == 0 and kpi_50["adr"]["denominator"] == 1
    assert kpi_50["adr"]["pending_gpb_excluded_count"] == 1


def test_ercp_esge_2016_and_retrospective_session_reindexing() -> None:
    assert is_difficult_cannulation_esge_2016("NATIVE_INTACT", 5, 5.0, 1) == "NO"
    assert is_difficult_cannulation_esge_2016("NATIVE_INTACT", 6, 4.0, 0) == "YES"
    assert is_difficult_cannulation_esge_2016("PRIOR_SPHINCTEROTOMY", 9, 12.0, 3) == "NA_NON_NATIVE"

    ercp_cases = [
        {"case_id": "cas_2", "episode_id": "ep_1", "track": "ERCP", "procedure_start_at": "2026-05-12T14:00:00", "created_at": "2026-05-12T15:00:00"},
        {"case_id": "cas_1", "episode_id": "ep_1", "track": "ERCP", "procedure_start_at": "2026-05-10T09:00:00", "created_at": "2026-05-13T08:00:00"},
    ]
    assert compute_ercp_session_indices(ercp_cases) == {"cas_1": 1, "cas_2": 2}


def test_tabular_qc_cusum_wald_boundary_and_ra_disabled() -> None:
    res = evaluate_tabular_qc_cusum([0, 0, 1, 1, 1, 1, 1, 0])
    assert res["ra_cusum_status"] == "DISABLED_UNVALIDATED_MODEL"
    assert res["w_success"] == -0.117783
    assert res["w_failure"] == 0.693147
    assert res["h_limit"] == 2.890372
    assert res["alarm_case_number"] == 7
