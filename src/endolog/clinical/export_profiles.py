"""EndoLog Export Contract v1.0 — Profiles A (Encrypted Vault), B (Longitudinal Pseudonymized), C (Aggregated KPI)."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import hmac
import io
import json
import os
from typing import Any

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from openpyxl import Workbook

from endolog.clinical.adverse_events import summarize_case_adverse_events
from endolog.clinical.bbps import evaluate_bbps, extract_bbps_segments
from endolog.clinical.quality_metrics import compute_ercp_session_indices, compute_kpi_snapshot


def export_profile_a_encrypted_vault(state_snapshot: dict[str, Any], passphrase: str) -> bytes:
    """Profile A: AES-256-GCM + Argon2id KDF full backup (Superadmin exclusive)."""
    if len(passphrase) < 12:
        raise ValueError("Mật khẩu mã hóa sao lưu Profile A phải có tối thiểu 12 ký tự.")
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=2,
        memory_cost=65536,
        parallelism=2,
        hash_len=32,
        type=Type.ID,
    )
    aesgcm = AESGCM(key)
    plaintext = json.dumps(state_snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    aad = b"endolog-export-profile-a-v1"
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    envelope = {
        "contract": "EndoLog-Export-Profile-A-v1.0",
        "kdf": "argon2id",
        "cipher": "aes-256-gcm",
        "salt_hex": salt.hex(),
        "nonce_hex": nonce.hex(),
        "ciphertext_hex": ciphertext.hex(),
    }
    return json.dumps(envelope, indent=2).encode("utf-8")


def decrypt_profile_a_vault(blob: bytes, passphrase: str) -> dict[str, Any]:
    envelope = json.loads(blob.decode("utf-8"))
    salt = bytes.fromhex(envelope["salt_hex"])
    nonce = bytes.fromhex(envelope["nonce_hex"])
    ciphertext = bytes.fromhex(envelope["ciphertext_hex"])
    key = hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=2,
        memory_cost=65536,
        parallelism=2,
        hash_len=32,
        type=Type.ID,
    )
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, b"endolog-export-profile-a-v1")
    return json.loads(plaintext.decode("utf-8"))


def build_profile_b_row(
    case: dict[str, Any],
    *,
    patients_by_id: dict[str, dict[str, Any]],
    ercp_indices: dict[str, int],
    master_key: bytes,
    shift_key: bytes,
    scope_id: str,
) -> dict[str, Any]:
    """Profile B: Patient-scoped HMAC + deterministic per-patient date shift in [-30, +30] days."""
    patient_uid = case["patient_uid"]
    episode_id = case.get("episode_id") or case["case_id"]
    pat = patients_by_id.get(patient_uid) or {}

    subj_msg = f"endolog_v1:{scope_id}:{patient_uid}".encode("utf-8")
    research_subject_id = hmac.new(master_key, subj_msg, hashlib.sha256).hexdigest()[:24]
    epi_msg = f"endolog_v1:{scope_id}:{episode_id}".encode("utf-8")
    research_episode_id = hmac.new(master_key, epi_msg, hashlib.sha256).hexdigest()[:24]

    shift_digest = hmac.new(shift_key, research_subject_id.encode("utf-8"), hashlib.sha256).digest()
    delta_days = (int.from_bytes(shift_digest[:8], "big") % 61) - 30
    proc_date = dt.date.fromisoformat((case["procedure_start_at"])[:10])
    shifted_date = (proc_date + dt.timedelta(days=delta_days)).isoformat()

    proc_year = proc_date.year
    raw_age = case.get("age")
    if raw_age is None:
        raw_age = max(0, proc_year - int(pat.get("birth_year") or proc_year))
    age_capped = "90+" if int(raw_age) >= 90 else str(int(raw_age))
    sex = case.get("sex") or pat.get("sex") or "O"

    segs = extract_bbps_segments(case)
    bbps_res = (
        evaluate_bbps(segs[0], segs[1], segs[2], cecal_intubation=case.get("cecal_intubation") or "NA")
        if segs
        else {"total": None, "adequate": False}
    )
    ae = summarize_case_adverse_events(case)
    idx = case.get("index_lesion") or {}
    wc = case.get("whole_case_summary") or {}
    ercp_det = case.get("ercp_detail") or {}

    return {
        "research_subject_id": research_subject_id,
        "research_episode_id": research_episode_id,
        "case_code": case["case_code"],
        "track": case["track"],
        "care_setting": case.get("care_setting") or "OUTPATIENT",
        "shifted_procedure_date": shifted_date,
        "age_years_capped": age_capped,
        "sex": sex,
        "indication": case.get("indication") or "",
        "cecal_intubation": case.get("cecal_intubation") or "NA",
        "bbps_total": bbps_res["total"],
        "bbps_adequate": "YES" if bbps_res["adequate"] else ("NO" if segs else "NA"),
        "macroscopic_polyp_count": wc.get("macroscopic_polyp_count"),
        "any_confirmed_adenoma": wc.get("any_confirmed_adenoma"),
        "any_confirmed_ssl": wc.get("any_confirmed_ssl"),
        "index_lesion_site": idx.get("anatomical_site") or "",
        "index_lesion_size_mm": idx.get("size_mm"),
        "index_lesion_resection": idx.get("resection_method") or "NONE",
        "index_lesion_histology": idx.get("histology_type") or "NONE",
        "pathology_completion_status": case.get("pathology_completion_status") or "NOT_APPLICABLE",
        "ercp_session_in_episode": ercp_indices.get(case["case_id"]) if case["track"] == "ERCP" else None,
        "ercp_papilla_status": ercp_det.get("papilla_status") if case["track"] == "ERCP" else None,
        "ercp_selective_cannulation": ercp_det.get("selective_cannulation") if case["track"] == "ERCP" else None,
        "followup_30d_status": ae["followup_30d_status"],
        "highest_agree_grade": ae["highest_agree_grade"],
        "highest_pep_severity": ae["highest_pep_severity"],
    }


def export_profile_b_rows(
    state_snapshot: dict[str, Any],
    *,
    master_key: bytes,
    shift_key: bytes,
    scope_id: str = "endolog_bvbd_v1",
    track_filter: str | None = None,
) -> list[dict[str, Any]]:
    all_cases = [
        c for c in state_snapshot.get("cases", {}).values() if c.get("record_status", "ACTIVE") == "ACTIVE"
    ]
    ercp_idx = compute_ercp_session_indices(all_cases, state_snapshot.get("episodes"))
    filtered = [c for c in all_cases if not track_filter or c.get("track") == track_filter]
    filtered.sort(key=lambda x: (x.get("procedure_start_at") or "", x.get("case_code") or ""))
    return [
        build_profile_b_row(
            c,
            patients_by_id=state_snapshot.get("patients", {}),
            ercp_indices=ercp_idx,
            master_key=master_key,
            shift_key=shift_key,
            scope_id=scope_id,
        )
        for c in filtered
    ]


def rows_to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    if not rows:
        return b""
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def rows_to_xlsx_bytes(rows: list[dict[str, Any]], sheet_title: str = "EndoLog_Export") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _mask_small_cell(count: int, suppress: bool) -> int | str:
    if suppress and 0 < count < 5:
        return "<5"
    return count


def export_profile_c_summary(
    state_snapshot: dict[str, Any],
    *,
    min_adr_age: int = 45,
    suppress_small_cells: bool = True,
) -> dict[str, Any]:
    """Profile C: Aggregated KPI report with k < 5 small-cell suppression."""
    cases = list(state_snapshot.get("cases", {}).values())
    n_min_cfg = int((state_snapshot.get("settings") or {}).get("kpi_min_sample_size", 20))
    kpi = compute_kpi_snapshot(
        cases,
        patients_by_id=state_snapshot.get("patients", {}),
        min_adr_age=min_adr_age,
        n_min=n_min_cfg,
    )
    metrics_rows = []
    for key, label in [
        ("cir", "Tỷ lệ luồn tới manh tràng (CIR)"),
        ("bbps_adequate", "Tỷ lệ chuẩn bị đại tràng đạt (BBPS ≥ 6 & mỗi đoạn ≥ 2)"),
        ("pdr", f"Tỷ lệ phát hiện polyp đại thể (PDR ≥ {min_adr_age} tuổi)"),
        ("adr", f"Tỷ lệ phát hiện u tuyến (ADR ≥ {min_adr_age} tuổi, đã có GPB)"),
        ("ssldr", f"Tỷ lệ phát hiện polyp răng cưa không cuống (SSLDR ≥ {min_adr_age} tuổi)"),
        ("ercp_native_cannulation", "Tỷ lệ thông nhú chọn lọc trên nhú Vater nguyên vẹn (ERCP)"),
        ("ercp_pep", "Tỷ lệ viêm tụy cấp sau ERCP trên ca hoàn tất theo dõi"),
    ]:
        block = kpi[key]
        num = int(block["numerator"])
        den = int(block.get("denominator", block.get("completed_fu_denominator", 0)))
        masked_num = _mask_small_cell(num, suppress_small_cells)
        masked_den = _mask_small_cell(den, suppress_small_cells)
        rate = None if (suppress_small_cells and (0 < num < 5 or 0 < den < 5)) else block["rate_pct"]
        metrics_rows.append(
            {
                "metric_code": key,
                "metric_label_vi": label,
                "numerator": masked_num,
                "denominator": masked_den,
                "rate_pct": rate,
            }
        )
    return {
        "contract": "EndoLog-Export-Profile-C-v1.0",
        "suppress_small_cells_k_lt_5": suppress_small_cells,
        "min_adr_age": min_adr_age,
        "total_active_cases": _mask_small_cell(kpi["total_active_cases"], suppress_small_cells),
        "metrics": metrics_rows,
    }
