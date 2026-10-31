"""Multi-guideline surveillance scheduler & surgical MDT alert engine (OD-01 locked: USMSTF 2020 primary)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from endolog.clinical.bbps import extract_bbps_segments

INTERVAL_LABELS_VI: dict[str, str] = {
    "3_6M": "3–6 tháng",
    "6M": "6 tháng",
    "LE_12M": "≤ 12 tháng",
    "12M": "12 tháng",
    "1Y": "1 năm",
    "3Y": "3 năm",
    "3_5Y": "3–5 năm",
    "5_10Y": "5–10 năm",
    "7_10Y": "7–10 năm",
    "10Y": "10 năm",
    "10Y_OR_SCREENING": "10 năm / tầm soát",
}

INTERVAL_DAYS: dict[str, int] = {
    "3_6M": 90,
    "6M": 182,
    "LE_12M": 365,
    "12M": 365,
    "1Y": 365,
    "3Y": 1095,
    "3_5Y": 1095,
    "5_10Y": 1825,
    "7_10Y": 2555,
    "10Y": 3650,
    "10Y_OR_SCREENING": 3650,
}


def compute_due_date_iso(procedure_start_at: str | None, interval_code: str | None) -> str | None:
    if not procedure_start_at or not interval_code or interval_code not in INTERVAL_DAYS:
        return None
    base_date = dt.date.fromisoformat(procedure_start_at[:10])
    return (base_date + dt.timedelta(days=INTERVAL_DAYS[interval_code])).isoformat()


def evaluate_esge_esd_2022(lesion: dict[str, Any], *, organ: str) -> dict[str, Any]:
    margins = lesion.get("margins_status") or "PENDING"
    target_dept = "Khoa Ngoại Tiêu hóa" if organ == "GASTRIC" else "Khoa Phẫu thuật Đại trực tràng"
    if margins == "PENDING":
        return {
            "guideline_id": "ESGE_ESD_2022",
            "guideline_version": "2022",
            "category": "PENDING_DATA",
            "interval": None,
            "surgical_consult_target_dept": None,
            "reason": "Đang chờ kết quả diện cắt giải phẫu bệnh sau ESD.",
        }
    sm_cutoff = 500 if organ == "GASTRIC" else 1000
    sm_um = lesion.get("sm_invasion_um") or 0
    high_risk = (
        margins == "VM1_OR_R1"
        or sm_um > sm_cutoff
        or lesion.get("lvi_status") == "POSITIVE"
        or lesion.get("differentiation") == "POOR_UNDIFF"
        or lesion.get("budding_grade") == "BD2_BD3"
    )
    if high_risk:
        return {
            "guideline_id": "ESGE_ESD_2022",
            "guideline_version": "2022",
            "category": "SURGICAL_MDT_CONSULT_ALERT",
            "interval": None,
            "surgical_consult_target_dept": target_dept,
            "reason": f"ESD không triệt căn / có yếu tố nguy cơ di căn hạch (ESGE ESD 2022) — cảnh báo hội chẩn {target_dept}.",
        }
    if margins in ("HM1_ONLY", "RX_PIECEMEAL"):
        return {
            "guideline_id": "ESGE_ESD_2022",
            "guideline_version": "2022",
            "category": "LOCAL_SCAR_SURVEILLANCE",
            "interval": "3_6M",
            "surgical_consult_target_dept": None,
            "reason": "ESD chỉ dương tính hoặc chưa rõ diện ngang đơn độc (HM1/HMX), không có yếu tố nguy cơ di căn hạch.",
        }
    return {
        "guideline_id": "ESGE_ESD_2022",
        "guideline_version": "2022",
        "category": "CURATIVE_SURVEILLANCE",
        "interval": "12M",
        "surgical_consult_target_dept": None,
        "reason": "ESD đạt tiêu chuẩn cắt triệt căn tại chỗ R0 (ESGE ESD 2022).",
    }


def evaluate_single_guideline(
    case: dict[str, Any],
    colo_guideline_mode: str = "USMSTF_2020",
) -> dict[str, Any]:
    track = case["track"]
    idx = case.get("index_lesion") or {}
    wc = case.get("whole_case_summary") or {}

    if track == "ERCP":
        return {
            "guideline_id": "CLINICIAN_DIRECTED_ERCP",
            "guideline_version": "2020",
            "category": "NEEDS_PHYSICIAN_REVIEW",
            "interval": None,
            "surgical_consult_target_dept": None,
            "reason": "ERCP không thuộc phạm vi ESGE/USMSTF hậu cắt polyp; bác sĩ chỉ định lịch hẹn theo bệnh cảnh mật tụy.",
        }

    if track == "EGD":
        resection = idx.get("resection_method") or "NONE"
        gpb_status = case.get("pathology_completion_status") or "NOT_APPLICABLE"
        hist = idx.get("histology_type") or "NONE"
        if gpb_status in ("PENDING", "PARTIAL"):
            return {
                "guideline_id": "CLINICIAN_DIRECTED_EGD",
                "guideline_version": "2022",
                "category": "PENDING_DATA",
                "interval": None,
                "surgical_consult_target_dept": None,
                "reason": "Đang chờ kết quả giải phẫu bệnh dạ dày — thực quản.",
            }
        if hist == "ADENOCARCINOMA_INVASIVE" and resection in ("BIOPSY_ONLY", "UNRESECTED_REFERRED", "NONE"):
            return {
                "guideline_id": "CLINICIAN_DIRECTED_EGD",
                "guideline_version": "2022",
                "category": "SURGICAL_MDT_CONSULT_ALERT",
                "interval": None,
                "surgical_consult_target_dept": "Khoa Ngoại Tiêu hóa",
                "reason": "Sinh thiết dạ dày xác nhận ung thư biểu mô xâm lấn — cảnh báo hội chẩn Khoa Ngoại Tiêu hóa.",
            }
        if resection == "ESD":
            return evaluate_esge_esd_2022(idx, organ="GASTRIC")
        return {
            "guideline_id": "CLINICIAN_DIRECTED_EGD",
            "guideline_version": "2022",
            "category": "NEEDS_PHYSICIAN_REVIEW",
            "interval": None,
            "surgical_consult_target_dept": None,
            "reason": "Sinh thiết kìm EGD hoặc can thiệp cầm máu XHTH trên — bác sĩ trực tiếp quyết định lịch hẹn kiểm tra.",
        }

    # Track == COL
    gpb_status = case.get("pathology_completion_status") or "NOT_APPLICABLE"
    g_label = "ESGE_POST_POLYPECTOMY_2020" if colo_guideline_mode == "ESGE_2020" else "USMSTF_POST_POLYPECTOMY_2020"
    if gpb_status in ("PENDING", "PARTIAL"):
        return {
            "guideline_id": g_label,
            "guideline_version": "2020",
            "category": "PENDING_DATA",
            "interval": None,
            "surgical_consult_target_dept": None,
            "reason": "Chưa đủ kết quả giải phẫu bệnh toàn ca đại trực tràng.",
        }

    if idx.get("resection_method") == "ESD":
        return evaluate_esge_esd_2022(idx, organ="COLORECTAL")

    if (
        idx.get("histology_type") == "ADENOCARCINOMA_INVASIVE"
        or wc.get("any_invasive_cancer_or_noncurative_feature") == "YES"
        or idx.get("resection_method") == "UNRESECTED_REFERRED"
    ):
        return {
            "guideline_id": g_label,
            "guideline_version": "2020",
            "category": "SURGICAL_MDT_CONSULT_ALERT",
            "interval": None,
            "surgical_consult_target_dept": "Khoa Phẫu thuật Đại trực tràng",
            "reason": "Phát hiện ung thư biểu mô xâm lấn hoặc tổn thương không cắt được qua nội soi — cảnh báo hội chẩn Khoa Phẫu thuật Đại trực tràng.",
        }

    segs = extract_bbps_segments(case)
    cecal_ok = case.get("cecal_intubation") == "YES"
    bbps_ok = cecal_ok and segs is not None and len(segs) == 3 and sum(segs) >= 6 and all(s >= 2 for s in segs)

    if not bbps_ok or wc.get("complete_resection_all_lesions") == "INCOMPLETE_OR_UNRESECTED":
        return {
            "guideline_id": g_label,
            "guideline_version": "2020",
            "category": "REPEAT_INADEQUATE_PREP_OR_INCOMPLETE",
            "interval": "LE_12M",
            "surgical_consult_target_dept": None,
            "reason": "Chuẩn bị đại tràng không đạt chuẩn (BBPS < 6 hoặc có đoạn < 2) hoặc chưa tới manh tràng / chưa cắt trọn.",
        }

    if wc.get("any_piecemeal_ge_20mm") == "YES" or (
        idx.get("resection_method") == "EMR_PIECEMEAL" and (idx.get("size_mm") or 0) >= 20
    ):
        return {
            "guideline_id": g_label,
            "guideline_version": "2020",
            "category": "LOCAL_SCAR_SURVEILLANCE",
            "interval": "3_6M" if colo_guideline_mode == "ESGE_2020" else "6M",
            "surgical_consult_target_dept": None,
            "reason": "Cắt từng mảnh (Piecemeal EMR) tổn thương ≥ 20 mm — hẹn kiểm tra sẹo tại chỗ.",
        }

    max_ad_mm = max(
        wc.get("max_adenoma_size_mm") or 0,
        (idx.get("size_mm") or 0)
        if idx.get("histology_type") in ("TUBULAR_ADENOMA", "TUBULOVILLOUS_ADENOMA", "VILLOUS_ADENOMA")
        else 0,
    )
    max_ssl_mm = max(
        wc.get("max_ssl_size_mm") or 0,
        (idx.get("size_mm") or 0)
        if idx.get("histology_type") in ("SSL_NO_DYSPLASIA", "SSL_WITH_DYSPLASIA")
        else 0,
    )
    any_hgd_villous = (
        wc.get("any_villous_or_hgd_any_lesion") == "YES"
        or idx.get("dysplasia_grade") == "HGD"
        or idx.get("histology_type") in ("TUBULOVILLOUS_ADENOMA", "VILLOUS_ADENOMA")
    )
    any_ssl_dys_tsa = wc.get("any_ssl_with_dysplasia_or_tsa") == "YES" or idx.get("histology_type") in (
        "SSL_WITH_DYSPLASIA",
        "TSA",
    )
    ad_bin = wc.get("confirmed_adenoma_count_bin") or "0"
    ssl_bin = wc.get("confirmed_ssl_count_bin") or "0"

    if colo_guideline_mode == "ESGE_2020":
        high_risk_esge = (
            max_ad_mm >= 10
            or idx.get("dysplasia_grade") == "HGD"
            or wc.get("any_hgd_any_lesion") == "YES"
            or ad_bin in ("5_10", "GT_10")
            or max_ssl_mm >= 10
            or any_ssl_dys_tsa
        )
        if high_risk_esge:
            return {
                "guideline_id": "ESGE_POST_POLYPECTOMY_2020",
                "guideline_version": "2020",
                "category": "CURATIVE_SURVEILLANCE",
                "interval": "3Y",
                "surgical_consult_target_dept": None,
                "reason": "Có ≥ 1 tiêu chuẩn nguy cơ cao cần nội soi kiểm tra sau 3 năm theo ESGE 2020.",
            }
        return {
            "guideline_id": "ESGE_POST_POLYPECTOMY_2020",
            "guideline_version": "2020",
            "category": "CURATIVE_SURVEILLANCE",
            "interval": "10Y_OR_SCREENING",
            "surgical_consult_target_dept": None,
            "reason": "Không có tiêu chuẩn nguy cơ cao theo ESGE 2020 (1–4 u tuyến < 10 mm LGD / SSL < 10 mm không loạn sản / âm tính).",
        }

    if colo_guideline_mode == "USMSTF_2020":
        if ad_bin == "GT_10":
            return {
                "guideline_id": "USMSTF_POST_POLYPECTOMY_2020",
                "guideline_version": "2020",
                "category": "CURATIVE_SURVEILLANCE",
                "interval": "1Y",
                "surgical_consult_target_dept": None,
                "reason": "Hơn 10 u tuyến xác nhận GPB theo USMSTF 2020.",
            }
        if (
            max_ad_mm >= 10
            or any_hgd_villous
            or ad_bin == "5_10"
            or max_ssl_mm >= 10
            or any_ssl_dys_tsa
            or ssl_bin == "GE_5"
        ):
            return {
                "guideline_id": "USMSTF_POST_POLYPECTOMY_2020",
                "guideline_version": "2020",
                "category": "CURATIVE_SURVEILLANCE",
                "interval": "3Y",
                "surgical_consult_target_dept": None,
                "reason": "Nhóm nguy cơ cao hẹn soi kiểm tra 3 năm theo USMSTF 2020.",
            }
        if ad_bin == "3_4" or ssl_bin == "3_4":
            return {
                "guideline_id": "USMSTF_POST_POLYPECTOMY_2020",
                "guideline_version": "2020",
                "category": "CURATIVE_SURVEILLANCE",
                "interval": "3_5Y",
                "surgical_consult_target_dept": None,
                "reason": "Có 3–4 u tuyến < 10 mm LGD hoặc 3–4 SSL < 10 mm không loạn sản theo USMSTF 2020.",
            }
        if ad_bin == "1_2":
            return {
                "guideline_id": "USMSTF_POST_POLYPECTOMY_2020",
                "guideline_version": "2020",
                "category": "CURATIVE_SURVEILLANCE",
                "interval": "7_10Y",
                "surgical_consult_target_dept": None,
                "reason": "Có 1–2 u tuyến ống < 10 mm loạn sản độ thấp theo USMSTF 2020.",
            }
        if ssl_bin == "1_2":
            return {
                "guideline_id": "USMSTF_POST_POLYPECTOMY_2020",
                "guideline_version": "2020",
                "category": "CURATIVE_SURVEILLANCE",
                "interval": "5_10Y",
                "surgical_consult_target_dept": None,
                "reason": "Có 1–2 polyp răng cưa không cuống (SSL) < 10 mm không loạn sản theo USMSTF 2020.",
            }
        return {
            "guideline_id": "USMSTF_POST_POLYPECTOMY_2020",
            "guideline_version": "2020",
            "category": "CURATIVE_SURVEILLANCE",
            "interval": "10Y",
            "surgical_consult_target_dept": None,
            "reason": "Nội soi đại trực tràng bình thường hoặc chỉ có polyp tăng sản < 10 mm trực tràng — đại tràng chậu hông.",
        }

    raise ValueError(f"Unsupported colo_guideline_mode: {colo_guideline_mode}")


def build_surveillance_recommendation(
    case: dict[str, Any],
    *,
    primary_colo_mode: str = "USMSTF_2020",
) -> dict[str, Any]:
    """Evaluate primary recommendation + side-by-side reference guideline (OD-01)."""
    primary = evaluate_single_guideline(case, colo_guideline_mode=primary_colo_mode)
    alt_mode = "ESGE_2020" if primary_colo_mode == "USMSTF_2020" else "USMSTF_2020"
    ref = evaluate_single_guideline(case, colo_guideline_mode=alt_mode) if case["track"] == "COL" else None

    interval = primary["interval"]
    ref_interval = ref["interval"] if ref else None
    is_divergent = bool(
        ref
        and primary["guideline_id"] != ref["guideline_id"]
        and interval is not None
        and ref_interval is not None
        and interval != ref_interval
    )

    due_date = case.get("clinician_followup_due_date") or compute_due_date_iso(
        case.get("procedure_start_at"),
        interval,
    )
    if primary["category"] == "PENDING_DATA":
        rec_status = "PENDING_GPB"
    elif primary["category"] == "SURGICAL_MDT_CONSULT_ALERT":
        rec_status = "CONSULT_ALERT"
    else:
        rec_status = "ACTIVE_DUE"

    reason_text = primary["reason"]
    if case.get("clinician_followup_note"):
        reason_text = case["clinician_followup_note"]

    return {
        "origin_case_id": case["case_id"],
        "case_code": case["case_code"],
        "track": case["track"],
        "guideline_id": primary["guideline_id"],
        "guideline_version": primary["guideline_version"],
        "category": primary["category"],
        "recommended_interval_code": interval,
        "recommended_interval_label": INTERVAL_LABELS_VI.get(interval, "Bác sĩ chỉ định") if interval else "Theo chỉ định lâm sàng",
        "reference_guideline_id": ref["guideline_id"] if ref else None,
        "reference_interval_code": ref_interval,
        "reference_interval_label": INTERVAL_LABELS_VI.get(ref_interval, "") if ref_interval else None,
        "is_divergent_guideline": is_divergent,
        "due_date": due_date,
        "surgical_consult_target_dept": primary["surgical_consult_target_dept"],
        "reason": reason_text,
        "status": rec_status,
        "fulfilled_by_case_id": case.get("fulfilled_by_case_id"),
    }
