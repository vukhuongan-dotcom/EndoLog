#!/usr/bin/env python3
"""Build Interactive Virtual-Patient Sandbox (Gate C · Phương án G1+ / v0.3.2) into dist_pages/ for GitHub Pages.

Contract enforced:
- Leaves src/endolog/static/ untouched for FastAPI '/' (only ?v=0.3.2 asset query string bumped).
- Generates dist_pages/data/od05_precomputed_bundle.json with sanitized initial_ram_store + synthetic_patient_catalog.
- Strips 100% of input[type="password"] and input[type="file"] from dist_pages/index.html.
- Locks #el-f-full-name and #el-f-hospital-mrn as readonly, populated from an inline Virtual Patient Picker.
- Runs 100% in-browser RAM clinical/KPI/CUSUM/surveillance/audit/Superadmin engine (0 /api/* network requests, 0 clinical storage).
- Exports createSyntheticRamEngine via UMD so Node.js differential parity tests verify 100% lockstep parity with Python FastAPI.
- Enforces Rule v2:R15 (Zero-RM): quarantines prior output directory into OS temp directory via shutil.move instead of deleting.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from endolog import __version__  # noqa: E402
from endolog.core.config import (  # noqa: E402
    DEV_JWT_FALLBACK,
    DEV_RESEARCH_FALLBACK,
    DEV_SHIFT_FALLBACK,
    EndoLogSettings,
)
from endolog.core.dlp import PROTECTED_NOTE_FIELDS  # noqa: E402
from endolog.core.security import create_access_token  # noqa: E402
from endolog.main import STATIC_DIR, create_app  # noqa: E402
from endolog.schemas.clinical import compute_privacy_initials  # noqa: E402

SHOWCASE_BANNER_TEXT_VI = (
    "Sandbox tương tác bệnh nhân ảo trên RAM (chuẩn OD-05) — "
    "Khóa gõ tên/mã HS tự do, mật khẩu và tệp ngoài (Zero-PHI)."
)

DEFAULT_MERGE_REASON_VI = "Đối chiếu minh họa trên sandbox: gộp hồ sơ người bệnh ảo trùng định danh"
DEFAULT_RECONCILE_REASON_VI = "Đối chiếu minh họa trên sandbox: hợp nhất đợt nội trú cùng lần nhập viện"


def _normalize_base_path(raw: str) -> str:
    cleaned = (raw or "/EndoLog/").strip()
    if not cleaned.startswith("/"):
        cleaned = "/" + cleaned
    if not cleaned.endswith("/"):
        cleaned = cleaned + "/"
    return cleaned


def _quarantine_existing_dir(target: Path) -> Path | None:
    """Move an existing build directory to OS temp quarantine instead of deleting (Rule v2:R15 Zero-RM)."""
    if not target.exists():
        return None
    quarantine_root = Path(tempfile.gettempdir()) / "endolog_ghpages_build_quarantine"
    quarantine_root.mkdir(parents=True, exist_ok=True)
    dest = quarantine_root / f"{target.name}_{int(time.time() * 1000)}_{os.getpid()}"
    shutil.move(str(target), str(dest))
    return dest


def _assert_replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"[{label}] Kỳ vọng tìm thấy đúng 1 khối mục tiêu để biến đổi, thực tế={count}")
    return source.replace(old, new, 1)


def _sanitize_initial_ram_store(raw_snap: dict[str, Any]) -> dict[str, Any]:
    """Strip password hashes, MRN HMAC digests, and crypto fingerprints before writing static JSON."""
    clean = copy.deepcopy(raw_snap)
    clean.pop("crypto_context", None)
    clean["revoked_jtis"] = {}
    for u_obj in clean.get("users", {}).values():
        if isinstance(u_obj, dict):
            u_obj.pop("password_hash", None)
    for p_obj in clean.get("patients", {}).values():
        if isinstance(p_obj, dict):
            p_obj.pop("hospital_mrn_hash", None)
            p_obj.pop("secondary_mrn_hashes", None)
    return clean


def _build_synthetic_patient_catalog(initial_store: dict[str, Any]) -> list[dict[str, Any]]:
    """Build deterministic catalog of 15 fresh virtual patients + 1 duplicate-test preset + 5 OD-05 patients."""
    catalog: list[dict[str, Any]] = []

    # 1. Fresh virtual patients BN. Giả Lập 06 .. BN. Giả Lập 20 (SYN-DEMO-2606 .. SYN-DEMO-2620)
    demo_specs = [
        (6, 1969, "M", "OUTPATIENT"),
        (7, 1972, "F", "OUTPATIENT"),
        (8, 1961, "M", "OUTPATIENT"),
        (9, 1976, "F", "OUTPATIENT"),
        (10, 1957, "M", "INPATIENT"),
        (11, 1965, "F", "INPATIENT"),
        (12, 1981, "M", "OUTPATIENT"),
        (13, 1954, "F", "INPATIENT"),
        (14, 1978, "M", "OUTPATIENT"),
        (15, 1960, "F", "OUTPATIENT"),
        (16, 1971, "M", "INPATIENT"),
        (17, 1984, "F", "OUTPATIENT"),
        (18, 1952, "M", "INPATIENT"),
        (19, 1967, "F", "OUTPATIENT"),
        (20, 1975, "M", "OUTPATIENT"),
    ]
    for num, byear, sex, pref_care in demo_specs:
        full_name = f"BN. Giả Lập {num:02d}"
        mrn = f"SYN-DEMO-26{num:02d}"
        sex_vi = "Nữ" if sex == "F" else "Nam"
        care_vi = "Nội trú" if pref_care == "INPATIENT" else "Ngoại trú"
        catalog.append(
            {
                "preset_id": f"syn_26{num:02d}",
                "group": "NEW_VIRTUAL",
                "label": f"{full_name} ({byear} · {sex_vi} · {mrn} · gợi ý {care_vi})",
                "full_name": full_name,
                "privacy_initials": compute_privacy_initials(full_name),
                "birth_year": byear,
                "sex": sex,
                "hospital_mrn": mrn,
                "default_care_setting": pref_care,
            }
        )

    # 2. Outpatient no-MRN preset matching OD-05 patient #1 to test 409 duplicate detection & Superadmin merge
    catalog.append(
        {
            "preset_id": "dup_out_2601",
            "group": "DUPLICATE_TEST",
            "label": "Thử cảnh báo trùng ngoại trú không mã HS · Lê Thị Minh Thảo (1974 · Nữ)",
            "full_name": "Lê Thị Minh Thảo",
            "privacy_initials": compute_privacy_initials("Lê Thị Minh Thảo"),
            "birth_year": 1974,
            "sex": "F",
            "hospital_mrn": "",
            "default_care_setting": "OUTPATIENT",
        }
    )

    # 3. Existing 5 OD-05 patients ordered by their initial case codes so clinicians can add longitudinal cases / 2nd ERCP
    cases_by_pat: dict[str, dict[str, Any]] = {}
    for c_obj in initial_store.get("cases", {}).values():
        cases_by_pat.setdefault(c_obj["patient_uid"], c_obj)

    ordered_pats = sorted(
        initial_store.get("patients", {}).values(),
        key=lambda p: (cases_by_pat.get(p["patient_uid"], {}).get("case_code") or "", p["patient_uid"]),
    )
    for idx, p_obj in enumerate(ordered_pats, start=1):
        c_ref = cases_by_pat.get(p_obj["patient_uid"], {})
        mrn = str(p_obj.get("hospital_mrn") or "")
        sex = str(p_obj.get("sex") or "M")
        sex_vi = "Nữ" if sex == "F" else "Nam"
        care = str(c_ref.get("care_setting") or "OUTPATIENT")
        catalog.append(
            {
                "preset_id": f"od05_{idx:02d}",
                "group": "EXISTING_OD05",
                "patient_uid": p_obj["patient_uid"],
                "label": f"Hồ sơ gốc OD-05 · {p_obj['full_name']} ({p_obj['birth_year']} · {sex_vi} · {mrn})",
                "full_name": p_obj["full_name"],
                "privacy_initials": p_obj["privacy_initials"],
                "birth_year": int(p_obj["birth_year"]),
                "sex": sex,
                "hospital_mrn": mrn,
                "default_care_setting": care,
            }
        )

    return catalog


def _generate_precomputed_od05_bundle() -> dict[str, Any]:
    """Run real FastAPI + Python clinical engines on an isolated synthetic store to produce exact API payloads."""
    scratch_root = Path(tempfile.mkdtemp(prefix="endolog_od05_bundle_seed_"))
    cfg = EndoLogSettings(
        env_mode="local_dev_synthetic",
        enable_dev_bypass=True,
        bind_host="127.0.0.1",
        data_dir=scratch_root / "data_synthetic_dev",
        backup_dir=scratch_root / "backups_synthetic_dev",
        jwt_secret=DEV_JWT_FALLBACK,
        master_research_key=DEV_RESEARCH_FALLBACK.encode("utf-8"),
        shift_key=DEV_SHIFT_FALLBACK.encode("utf-8"),
        session_timeout_seconds=900,
        kpi_min_sample_size=20,
    )
    cfg.validate_startup_safety()
    app = create_app(
        cfg,
        auto_seed_synthetic=True,
        bootstrap_passwords={
            "nguyenbinhan": "demo-ephemeral-pass-1",
            "vukhuongan": "demo-ephemeral-pass-2",
        },
    )
    snap = app.state.store.read_snapshot()
    super_user = snap["users"]["vukhuongan"]
    endo_user = snap["users"]["nguyenbinhan"]
    token, _ = create_access_token(
        cfg,
        username=super_user["username"],
        role=super_user["role"],
        display_name=super_user["display_name"],
        department=super_user["department"],
        auth_ver=int(super_user.get("auth_version", 1) or 1),
        store_epoch=int(snap.get("store_epoch", 1) or 1),
    )
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        cases_resp = client.get("/api/cases", headers=headers)
        surv_resp = client.get("/api/surveillance", headers=headers)
        kpi_45_resp = client.get("/api/metrics/kpi?min_adr_age=45", headers=headers)
        kpi_50_resp = client.get("/api/metrics/kpi?min_adr_age=50", headers=headers)
        cusum_cir_90 = client.get("/api/metrics/cusum?metric=CIR&preset=DEFAULT_90", headers=headers)
        cusum_cir_95 = client.get("/api/metrics/cusum?metric=CIR&preset=SCREENING_CIR_95", headers=headers)
        cusum_ercp_90 = client.get("/api/metrics/cusum?metric=ERCP_NATIVE&preset=DEFAULT_90", headers=headers)
        cusum_ercp_95 = client.get("/api/metrics/cusum?metric=ERCP_NATIVE&preset=SCREENING_CIR_95", headers=headers)
        audit_resp = client.get("/api/audit/verify", headers=headers)
        settings_resp = client.get("/api/settings", headers=headers)
        admin_patients_resp = client.get("/api/admin/patients", headers=headers)
        admin_users_resp = client.get("/api/admin/users", headers=headers)

    for name, resp in [
        ("cases", cases_resp),
        ("surveillance", surv_resp),
        ("kpi_45", kpi_45_resp),
        ("kpi_50", kpi_50_resp),
        ("cusum_cir_90", cusum_cir_90),
        ("cusum_cir_95", cusum_cir_95),
        ("cusum_ercp_90", cusum_ercp_90),
        ("cusum_ercp_95", cusum_ercp_95),
        ("audit_verify", audit_resp),
        ("settings", settings_resp),
        ("admin_patients", admin_patients_resp),
        ("admin_users", admin_users_resp),
    ]:
        if resp.status_code != 200:
            raise RuntimeError(f"Không thể trích xuất gói dữ liệu mẫu '{name}': HTTP {resp.status_code}")

    cases_json = cases_resp.json()
    audit_json = audit_resp.json()
    if len(cases_json.get("items", [])) != 5:
        raise RuntimeError(f"Kỳ vọng đúng 5 ca giả lập chuẩn OD-05, thực tế={len(cases_json.get('items', []))}")
    if not audit_json.get("verification", {}).get("valid"):
        raise RuntimeError("Chuỗi băm kiểm toán của gói dữ liệu mẫu OD-05 không hợp lệ.")

    sanitized_store = _sanitize_initial_ram_store(snap)
    patient_catalog = _build_synthetic_patient_catalog(sanitized_store)

    bundle: dict[str, Any] = {
        "contract": "endolog.gh_pages_od05_precomputed_bundle.v2",
        "version": __version__,
        "static_demo": True,
        "interactive_ram_sandbox": True,
        "zero_phi_policy": "SYNTHETIC_VIRTUAL_PATIENTS_RAM_ONLY_ZERO_PHI",
        "personas": {
            "nguyenbinhan": {
                "username": endo_user["username"],
                "display_name": endo_user["display_name"],
                "role": endo_user["role"],
                "department": endo_user["department"],
            },
            "vukhuongan": {
                "username": super_user["username"],
                "display_name": super_user["display_name"],
                "role": super_user["role"],
                "department": super_user["department"],
            },
        },
        "synthetic_patient_catalog": patient_catalog,
        "initial_ram_store": sanitized_store,
        "cases_response": cases_json,
        "surveillance_response": surv_resp.json(),
        "kpi_by_age": {
            "45": kpi_45_resp.json(),
            "50": kpi_50_resp.json(),
        },
        "cusum_series": {
            "CIR:DEFAULT_90": cusum_cir_90.json(),
            "CIR:SCREENING_CIR_95": cusum_cir_95.json(),
            "ERCP_NATIVE:DEFAULT_90": cusum_ercp_90.json(),
            "ERCP_NATIVE:SCREENING_CIR_95": cusum_ercp_95.json(),
        },
        "audit_verify_response": audit_json,
        "settings_response": settings_resp.json(),
        "admin_patients_response": admin_patients_response_clean(admin_patients_resp.json()),
        "admin_users_response": admin_users_resp.json(),
    }

    serialized = json.dumps(bundle, ensure_ascii=False)
    for forbidden_key in (
        "password_hash",
        "hospital_mrn_hash",
        "secondary_mrn_hashes",
        "jwt_secret",
        "argon2id$",
        "Bearer ",
    ):
        if forbidden_key in serialized:
            raise RuntimeError(f"Phát hiện trường nhạy cảm '{forbidden_key}' lọt vào gói dữ liệu tĩnh OD-05.")
    return bundle


def admin_patients_response_clean(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a clean copy of sanitized synthetic admin patient items (already masked by EndoLogService)."""
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _build_demo_showcase_css() -> str:
    """Build CSS for the interactive RAM sandbox banner, virtual patient picker, and Zero-PHI lock modal."""
    return """/* EndoLog Interactive Virtual-Patient Sandbox Stylesheet (Gate C · Phương án G1+ / v0.3.2)
 * 100% biến màu từ tokens.css; 0 mã màu cứng; 0 emoji; vùng chạm >= 44x44 px. */

.el-demo-showcase-banner {
  position: sticky;
  top: 0;
  z-index: 40;
  background-color: var(--primary-soft);
  color: var(--text-heading);
  border-bottom: 1px solid var(--border);
  padding: var(--space-1) var(--space-3);
}

.el-demo-showcase-banner-inner {
  max-width: 1320px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  line-height: 1.35;
}

.el-demo-showcase-lead {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  max-width: 100%;
  flex: 1 1 280px;
}

.el-demo-showcase-badge {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  padding: 2px var(--space-2);
  border-radius: var(--radius-pill);
  background-color: var(--primary-fill);
  color: var(--on-primary);
  font-weight: 600;
  font-size: var(--text-xs);
}

.el-demo-showcase-text {
  margin: 0;
  min-width: 0;
  color: var(--text-heading);
  font-weight: 500;
  overflow-wrap: anywhere;
}

.el-demo-showcase-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  max-width: 100%;
}

.el-demo-banner-btn {
  min-height: var(--touch-min);
  min-width: var(--touch-min);
  height: auto;
  max-width: 100%;
  padding: 6px var(--space-3);
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 1.25;
  white-space: normal;
  text-align: center;
  overflow-wrap: anywhere;
}

/* Khi có thanh cảnh báo cố định đầu trang, thanh công cụ bên dưới cuộn tự nhiên để không chồng 2 lớp sticky trên màn nhỏ */
.el-topbar {
  position: relative;
  top: auto;
}

.el-demo-login-note {
  margin: 0 0 var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background-color: var(--bg-sunken);
  border: 1px solid var(--border);
  color: var(--text-main);
  font-size: var(--text-sm);
  line-height: 1.5;
}

.el-demo-virtual-picker-box {
  margin: 0 0 var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background-color: var(--primary-soft);
  border: 1px solid var(--border);
}

.el-demo-virtual-picker-hint {
  margin: var(--space-1) 0 0;
  color: var(--text-muted);
  font-size: var(--text-xs);
  line-height: 1.4;
}

.el-form-input[readonly] {
  background-color: var(--bg-sunken);
  color: var(--text-muted);
  cursor: not-allowed;
}

.el-demo-locked-field {
  min-height: var(--touch-min);
  display: flex;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background-color: var(--bg-sunken);
  border: 1px dashed var(--border-strong);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.el-demo-elevate-row {
  margin-top: var(--space-2);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

#el-demo-lock-modal-backdrop {
  z-index: 95;
}

.el-demo-lock-action-pill {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) var(--space-3);
  margin-bottom: var(--space-3);
  border-radius: var(--radius-pill);
  background-color: var(--primary-soft);
  color: var(--primary);
  border: 1px solid var(--border);
  font-size: var(--text-xs);
  font-weight: 600;
}

@media (max-width: 767px) {
  .el-demo-showcase-banner {
    padding: var(--space-1) var(--space-2);
  }
  .el-demo-showcase-badge {
    display: none;
  }
  .el-demo-showcase-lead {
    flex: 1 1 100%;
  }
  .el-demo-showcase-text {
    font-size: var(--text-xs);
    line-height: 1.25;
  }
  .el-demo-showcase-actions {
    width: 100%;
    justify-content: space-between;
  }
  .el-demo-banner-btn {
    flex: 1 1 180px;
    padding: 6px var(--space-2);
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .el-demo-showcase-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .el-demo-banner-btn {
    flex: 1 1 auto;
    width: 100%;
  }
}
"""


_DEMO_ENGINE_CORE_JS = r"""
  /* =========================================================================
   * 1. PURE-JS UTF-8 SHA-256 & HMAC-SHA256 (0 external deps, Node + Browser)
   * ========================================================================= */
  const SHA256_K = [
    1116352408, 1899447441, 3049323471, 3921009573, 961987163, 1508970993, 2453635748, 2870763221,
    3624381080, 310598401, 607225278, 1426881987, 1925078388, 2162078206, 2614888103, 3248222580,
    3835390401, 4022224774, 264347078, 604807628, 770255983, 1249150122, 1555081692, 1996064986,
    2554220882, 2821834349, 2952996808, 3210313671, 3336571891, 3584528711, 113926993, 338241895,
    666307205, 773529912, 1294757372, 1396182291, 1695183700, 1986661051, 2177026350, 2456956037,
    2730485921, 2820302411, 3259730800, 3345764771, 3516065817, 3600352804, 4094571909, 275423344,
    430227734, 506948616, 659060556, 883997877, 958139571, 1322822218, 1537002063, 1747873779,
    1955562222, 2024104815, 2227730452, 2361852424, 2428436474, 2756734187, 3204031479, 3329325298
  ];
  const SHA256_H0 = [
    1779033703, 3144134277, 1013904242, 2773480762,
    1359893119, 2600822924, 528734635, 1541459225
  ];

  function utf8ToBytes(str) {
    if (typeof TextEncoder !== 'undefined') {
      return new TextEncoder().encode(String(str));
    }
    const out = [];
    const s = String(str);
    for (let i = 0; i < s.length; i += 1) {
      let c = s.charCodeAt(i);
      if (c < 128) {
        out.push(c);
      } else if (c < 2048) {
        out.push(192 | (c >> 6), 128 | (c & 63));
      } else if (c >= 55296 && c <= 56319 && i + 1 < s.length) {
        const c2 = s.charCodeAt(i + 1);
        const cp = 65536 + (((c & 1023) << 10) | (c2 & 1023));
        out.push(
          240 | (cp >> 18),
          128 | ((cp >> 12) & 63),
          128 | ((cp >> 6) & 63),
          128 | (cp & 63)
        );
        i += 1;
      } else {
        out.push(224 | (c >> 12), 128 | ((c >> 6) & 63), 128 | (c & 63));
      }
    }
    return new Uint8Array(out);
  }

  function rotr32(x, n) {
    return (x >>> n) | (x << (32 - n));
  }

  function sha256Bytes(msgInput) {
    const msg = msgInput instanceof Uint8Array ? msgInput : utf8ToBytes(msgInput);
    const bitLenHi = Math.floor((msg.length * 8) / 4294967296);
    const bitLenLo = (msg.length * 8) >>> 0;
    const totalLen = (((msg.length + 9 + 63) >> 6) << 6);
    const padded = new Uint8Array(totalLen);
    padded.set(msg, 0);
    padded[msg.length] = 128;
    const view = new DataView(padded.buffer);
    view.setUint32(totalLen - 8, bitLenHi, false);
    view.setUint32(totalLen - 4, bitLenLo, false);

    let h0 = SHA256_H0[0];
    let h1 = SHA256_H0[1];
    let h2 = SHA256_H0[2];
    let h3 = SHA256_H0[3];
    let h4 = SHA256_H0[4];
    let h5 = SHA256_H0[5];
    let h6 = SHA256_H0[6];
    let h7 = SHA256_H0[7];
    const w = new Uint32Array(64);

    for (let offset = 0; offset < totalLen; offset += 64) {
      for (let i = 0; i < 16; i += 1) {
        w[i] = view.getUint32(offset + i * 4, false);
      }
      for (let i = 16; i < 64; i += 1) {
        const s0 = rotr32(w[i - 15], 7) ^ rotr32(w[i - 15], 18) ^ (w[i - 15] >>> 3);
        const s1 = rotr32(w[i - 2], 17) ^ rotr32(w[i - 2], 19) ^ (w[i - 2] >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
      }

      let a = h0;
      let b = h1;
      let c = h2;
      let d = h3;
      let e = h4;
      let f = h5;
      let g = h6;
      let h = h7;

      for (let i = 0; i < 64; i += 1) {
        const S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
        const ch = (e & f) ^ ((~e) & g);
        const temp1 = (h + S1 + ch + SHA256_K[i] + w[i]) >>> 0;
        const S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const temp2 = (S0 + maj) >>> 0;

        h = g;
        g = f;
        f = e;
        e = (d + temp1) >>> 0;
        d = c;
        c = b;
        b = a;
        a = (temp1 + temp2) >>> 0;
      }

      h0 = (h0 + a) >>> 0;
      h1 = (h1 + b) >>> 0;
      h2 = (h2 + c) >>> 0;
      h3 = (h3 + d) >>> 0;
      h4 = (h4 + e) >>> 0;
      h5 = (h5 + f) >>> 0;
      h6 = (h6 + g) >>> 0;
      h7 = (h7 + h) >>> 0;
    }

    const digest = new Uint8Array(32);
    const outView = new DataView(digest.buffer);
    outView.setUint32(0, h0, false);
    outView.setUint32(4, h1, false);
    outView.setUint32(8, h2, false);
    outView.setUint32(12, h3, false);
    outView.setUint32(16, h4, false);
    outView.setUint32(20, h5, false);
    outView.setUint32(24, h6, false);
    outView.setUint32(28, h7, false);
    return digest;
  }

  function bytesToHex(bytes) {
    let out = '';
    for (let i = 0; i < bytes.length; i += 1) {
      out += bytes[i].toString(16).padStart(2, '0');
    }
    return out;
  }

  function sha256Hex(msgInput) {
    return bytesToHex(sha256Bytes(msgInput));
  }

  function hmacSha256Bytes(rawMaterialInput, msgInput) {
    let kBytes = rawMaterialInput instanceof Uint8Array ? rawMaterialInput : utf8ToBytes(rawMaterialInput);
    const mBytes = msgInput instanceof Uint8Array ? msgInput : utf8ToBytes(msgInput);
    if (kBytes.length > 64) {
      kBytes = sha256Bytes(kBytes);
    }
    const block = new Uint8Array(64);
    block.set(kBytes, 0);
    const ipad = new Uint8Array(64 + mBytes.length);
    const opad = new Uint8Array(64 + 32);
    for (let i = 0; i < 64; i += 1) {
      ipad[i] = block[i] ^ 54;
      opad[i] = block[i] ^ 92;
    }
    ipad.set(mBytes, 64);
    const inner = sha256Bytes(ipad);
    opad.set(inner, 64);
    return sha256Bytes(opad);
  }

  function hmacSha256Hex(rawMaterialInput, msgInput) {
    return bytesToHex(hmacSha256Bytes(rawMaterialInput, msgInput));
  }

  /* =========================================================================
   * 2. PYTHON PARITY HELPERS (Banker's Rounding, Dates, Canonical JSON, DLP)
   * ========================================================================= */
  function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  const _F64_BUF = new ArrayBuffer(8);
  const _F64_VIEW = new DataView(_F64_BUF);
  function pyRound(val, ndigits) {
    const d = typeof ndigits === 'number' ? Math.max(0, Math.trunc(ndigits)) : 0;
    const x = Number(val);
    if (!Number.isFinite(x) || x === 0) return 0;
    const neg = x < 0;
    _F64_VIEW.setFloat64(0, Math.abs(x), false);
    const hi = _F64_VIEW.getUint32(0, false);
    const lo = _F64_VIEW.getUint32(4, false);
    const rawExp = (hi >>> 20) & 2047;
    const hiMant = hi & 1048575;
    let mantBig;
    let binExp;
    if (rawExp === 0) {
      mantBig = (BigInt(hiMant) << 32n) | BigInt(lo);
      binExp = -1074;
    } else {
      mantBig = (1n << 52n) | (BigInt(hiMant) << 32n) | BigInt(lo);
      binExp = rawExp - 1075;
    }
    const pow10 = 10n ** BigInt(d);
    let num = mantBig * pow10;
    let den = 1n;
    if (binExp >= 0) {
      num = num << BigInt(binExp);
    } else {
      den = 1n << BigInt(-binExp);
    }
    let q = num / den;
    const twiceRem = (num % den) * 2n;
    if (twiceRem > den || (twiceRem === den && (q & 1n) === 1n)) {
      q += 1n;
    }
    if (q === 0n) return 0;
    if (d === 0) {
      const res0 = Number(q);
      return neg ? -res0 : res0;
    }
    const s = q.toString().padStart(d + 1, '0');
    const decStr = (neg ? '-' : '') + s.slice(0, s.length - d) + '.' + s.slice(s.length - d);
    const out = Number(decStr);
    return Object.is(out, -0) ? 0 : out;
  }

  function canonicalJson(val) {
    if (val === null || val === undefined) return 'null';
    if (typeof val === 'boolean' || typeof val === 'number' || typeof val === 'string') {
      return JSON.stringify(val);
    }
    if (Array.isArray(val)) {
      return '[' + val.map(canonicalJson).join(',') + ']';
    }
    if (typeof val === 'object') {
      const keys = Object.keys(val).filter(function (k) { return val[k] !== undefined; }).sort();
      return '{' + keys.map(function (k) { return JSON.stringify(k) + ':' + canonicalJson(val[k]); }).join(',') + '}';
    }
    return JSON.stringify(val);
  }

  function addCalendarDaysIso(isoDateStr, deltaDays) {
    const parts = String(isoDateStr).slice(0, 10).split('-').map(Number);
    const utcMs = Date.UTC(parts[0], parts[1] - 1, parts[2]) + (Number(deltaDays) * 86400000);
    return new Date(utcMs).toISOString().slice(0, 10);
  }

  function localDateIso(nowObj) {
    const d = nowObj || new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function nowUtcNoMicrosIso(fixedIso) {
    if (fixedIso) return String(fixedIso);
    return new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00');
  }

  function normalizeName(name) {
    return String(name || '').trim().toLowerCase().split(/\s+/).filter(Boolean).join(' ');
  }

  function computePrivacyInitials(fullName) {
    const tokens = String(fullName || '').trim().split(/\s+/).filter(Boolean);
    if (!tokens.length) return 'B.N';
    return tokens.slice(0, 4).map(function (t) { return t[0].toUpperCase(); }).join('.');
  }

  function maskMrn(rawMrn) {
    if (!rawMrn) return null;
    const s = String(rawMrn).trim();
    if (!s) return null;
    if (s.length <= 4) return s;
    return '***' + s.slice(-4);
  }

  const DLP_RULES = [
    ['CCCD_12_DIGITS', /(?<!\d)0\d{11}(?!\d)/],
    ['CMND_9_DIGITS', /(?<!\d)\d{9}(?!\d)/],
    ['VN_PHONE_NUMBER', /(?<!\d)(?:0|\+84)(?:3|5|7|8|9)\d{8}(?!\d)/],
    ['BHYT_CARD_CODE', /\b[A-Z]{2}\d{13}\b/],
    ['EMAIL_ADDRESS', /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/],
    ['REAL_HOSPITAL_MRN', /\b(?:HS\d{2}-\d+|BA\d{4,}|NV\d{4,})\b/i]
  ];

  function scanStringForDlp(strVal, fieldPath) {
    if (typeof strVal !== 'string' || !strVal) return null;
    for (let r = 0; r < DLP_RULES.length; r += 1) {
      if (DLP_RULES[r][1].test(strVal)) {
        const code = DLP_RULES[r][0];
        return {
          code: code,
          field: fieldPath,
          message: "Trường '" + fieldPath + "' chứa định danh cá nhân bị chặn bởi DLP (" + code + "). Không nhập số CCCD/CMND, số điện thoại, mã thẻ BHYT, mã hồ sơ thật hoặc email vào ô ghi chú tự do."
        };
      }
    }
    return null;
  }

  function scanPayloadNotes(payload, pathPrefix) {
    if (!payload) return null;
    if (Array.isArray(payload)) {
      for (let i = 0; i < payload.length; i += 1) {
        const hit = scanPayloadNotes(payload[i], (pathPrefix || '') + '[' + i + ']');
        if (hit) return hit;
      }
      return null;
    }
    if (typeof payload === 'object') {
      const keys = Object.keys(payload);
      for (let i = 0; i < keys.length; i += 1) {
        const k = keys[i];
        const v = payload[k];
        const subPath = pathPrefix ? (pathPrefix + '.' + k) : k;
        if (PROTECTED_NOTE_FIELDS[k]) {
          if (typeof v === 'string') {
            const hitStr = scanStringForDlp(v, subPath);
            if (hitStr) return hitStr;
          } else if (Array.isArray(v)) {
            for (let j = 0; j < v.length; j += 1) {
              const itemPath = subPath + '[' + j + ']';
              if (typeof v[j] === 'string') {
                const hitArr = scanStringForDlp(v[j], itemPath);
                if (hitArr) return hitArr;
              } else if (v[j] && typeof v[j] === 'object') {
                const hitNested = scanPayloadNotes(v[j], itemPath);
                if (hitNested) return hitNested;
              }
            }
          } else if (v && typeof v === 'object') {
            const hitObj = scanPayloadNotes(v, subPath);
            if (hitObj) return hitObj;
          }
        } else if (v && typeof v === 'object') {
          const hit = scanPayloadNotes(v, subPath);
          if (hit) return hit;
        }
      }
    }
    return null;
  }

  /* =========================================================================
   * 3. CLINICAL, KPI, CUSUM, SURVEILLANCE, AUDIT & EXPORT ENGINES
   * ========================================================================= */
  function extractBbpsSegments(c) {
    if (Array.isArray(c.bbps_segments) && c.bbps_segments.length === 3 && c.bbps_segments.every(function (x) { return x !== null && x !== undefined; })) {
      return [Number(c.bbps_segments[0]), Number(c.bbps_segments[1]), Number(c.bbps_segments[2])];
    }
    if (c.bbps_right === null || c.bbps_right === undefined || c.bbps_transverse === null || c.bbps_transverse === undefined || c.bbps_left === null || c.bbps_left === undefined) {
      return null;
    }
    return [Number(c.bbps_right), Number(c.bbps_transverse), Number(c.bbps_left)];
  }

  function evaluateBbps(right, transverse, left, cecalIntubation) {
    if (cecalIntubation !== 'YES' || right === null || right === undefined || transverse === null || transverse === undefined || left === null || left === undefined) {
      return { evaluable: false, segments: null, total: null, adequate: false };
    }
    const segs = [Number(right), Number(transverse), Number(left)];
    const total = segs[0] + segs[1] + segs[2];
    const adequate = total >= 6 && segs.every(function (s) { return s >= 2; });
    return { evaluable: true, segments: segs, total: total, adequate: adequate };
  }

  const AGREE_RANK = { NONE: 0, I: 1, II: 2, IIIa: 3, IIIb: 4, IVa: 5, IVb: 6, V: 7 };
  const PEP_RANK = { NONE: 0, MILD: 1, MODERATE: 2, SEVERE: 3 };
  const SEVERE_AGREE_MAP = { IIIa: true, IIIb: true, IVa: true, IVb: true, V: true };

  function summarizeCaseAdverseEvents(c) {
    const events = Array.isArray(c.adverse_events) ? c.adverse_events : [];
    let maxAgree = c.agree_grade || 'NONE';
    let maxPep = c.pep_severity || 'NONE';
    for (let i = 0; i < events.length; i += 1) {
      const ev = events[i] || {};
      const ag = ev.agree_grade || 'NONE';
      if ((AGREE_RANK[ag] || 0) > (AGREE_RANK[maxAgree] || 0)) maxAgree = ag;
      const pep = ev.pep_severity || 'NONE';
      if ((PEP_RANK[pep] || 0) > (PEP_RANK[maxPep] || 0)) maxPep = pep;
    }
    const fuStatus = c.followup_30d_status || c.followup_status || 'PENDING_WINDOW';
    const completed = fuStatus === 'COMPLETED_NO_AE' || fuStatus === 'COMPLETED_WITH_AE';
    return {
      highest_agree_grade: maxAgree,
      is_agree_any: (AGREE_RANK[maxAgree] || 0) >= 1,
      is_agree_severe_ge_iii: Boolean(SEVERE_AGREE_MAP[maxAgree]),
      highest_pep_severity: maxPep,
      has_pep: maxPep !== 'NONE',
      followup_30d_status: fuStatus,
      completed_followup: completed
    };
  }

  function isDifficultCannulationEsge2016(papillaStatus, contacts, timeMin, unintendedPd) {
    if (papillaStatus !== 'NATIVE_INTACT') return 'NA_NON_NATIVE';
    if (Number(contacts) > 5 || Number(timeMin) > 5.0 || Number(unintendedPd) > 1) return 'YES';
    return 'NO';
  }

  const INTERVAL_LABELS_VI = {
    '3_6M': '3–6 tháng',
    '6M': '6 tháng',
    'LE_12M': '≤ 12 tháng',
    '12M': '12 tháng',
    '1Y': '1 năm',
    '3Y': '3 năm',
    '3_5Y': '3–5 năm',
    '5_10Y': '5–10 năm',
    '7_10Y': '7–10 năm',
    '10Y': '10 năm',
    '10Y_OR_SCREENING': '10 năm / tầm soát'
  };
  const INTERVAL_DAYS = {
    '3_6M': 90,
    '6M': 182,
    'LE_12M': 365,
    '12M': 365,
    '1Y': 365,
    '3Y': 1095,
    '3_5Y': 1095,
    '5_10Y': 1825,
    '7_10Y': 2555,
    '10Y': 3650,
    '10Y_OR_SCREENING': 3650
  };

  function evaluateEsgeEsd2022(lesion, organ) {
    const margins = (lesion && lesion.margins_status) || 'PENDING';
    const targetDept = organ === 'GASTRIC' ? 'Khoa Ngoại Tiêu hóa' : 'Khoa Phẫu thuật Đại trực tràng';
    if (margins === 'PENDING') {
      return {
        guideline_id: 'ESGE_ESD_2022',
        guideline_version: '2022',
        category: 'PENDING_DATA',
        interval: null,
        surgical_consult_target_dept: null,
        reason: 'Đang chờ kết quả diện cắt giải phẫu bệnh sau ESD.'
      };
    }
    const smCutoff = organ === 'GASTRIC' ? 500 : 1000;
    const smUm = Number((lesion && lesion.sm_invasion_um) || 0);
    const highRisk = (
      margins === 'VM1_OR_R1' ||
      smUm > smCutoff ||
      (lesion && lesion.lvi_status) === 'POSITIVE' ||
      (lesion && lesion.differentiation) === 'POOR_UNDIFF' ||
      (lesion && lesion.budding_grade) === 'BD2_BD3'
    );
    if (highRisk) {
      return {
        guideline_id: 'ESGE_ESD_2022',
        guideline_version: '2022',
        category: 'SURGICAL_MDT_CONSULT_ALERT',
        interval: null,
        surgical_consult_target_dept: targetDept,
        reason: 'ESD không triệt căn / có yếu tố nguy cơ di căn hạch (ESGE ESD 2022) — cảnh báo hội chẩn ' + targetDept + '.'
      };
    }
    if (margins === 'HM1_ONLY' || margins === 'RX_PIECEMEAL') {
      return {
        guideline_id: 'ESGE_ESD_2022',
        guideline_version: '2022',
        category: 'LOCAL_SCAR_SURVEILLANCE',
        interval: '3_6M',
        surgical_consult_target_dept: null,
        reason: 'ESD chỉ dương tính hoặc chưa rõ diện ngang đơn độc (HM1/HMX), không có yếu tố nguy cơ di căn hạch.'
      };
    }
    return {
      guideline_id: 'ESGE_ESD_2022',
      guideline_version: '2022',
      category: 'CURATIVE_SURVEILLANCE',
      interval: '12M',
      surgical_consult_target_dept: null,
      reason: 'ESD đạt tiêu chuẩn cắt triệt căn tại chỗ R0 (ESGE ESD 2022).'
    };
  }

  function evaluateSingleGuideline(c, coloMode) {
    const track = c.track;
    const idx = c.index_lesion || {};
    const wc = c.whole_case_summary || {};
    if (track === 'ERCP') {
      return {
        guideline_id: 'CLINICIAN_DIRECTED_ERCP',
        guideline_version: '2020',
        category: 'NEEDS_PHYSICIAN_REVIEW',
        interval: null,
        surgical_consult_target_dept: null,
        reason: 'ERCP không thuộc phạm vi ESGE/USMSTF hậu cắt polyp; bác sĩ chỉ định lịch hẹn theo bệnh cảnh mật tụy.'
      };
    }
    if (track === 'EGD') {
      const resection = idx.resection_method || 'NONE';
      const gpb = c.pathology_completion_status || 'NOT_APPLICABLE';
      const hist = idx.histology_type || 'NONE';
      if (gpb === 'PENDING' || gpb === 'PARTIAL') {
        return {
          guideline_id: 'CLINICIAN_DIRECTED_EGD',
          guideline_version: '2022',
          category: 'PENDING_DATA',
          interval: null,
          surgical_consult_target_dept: null,
          reason: 'Đang chờ kết quả giải phẫu bệnh dạ dày — thực quản.'
        };
      }
      if (hist === 'ADENOCARCINOMA_INVASIVE' && (resection === 'BIOPSY_ONLY' || resection === 'UNRESECTED_REFERRED' || resection === 'NONE')) {
        return {
          guideline_id: 'CLINICIAN_DIRECTED_EGD',
          guideline_version: '2022',
          category: 'SURGICAL_MDT_CONSULT_ALERT',
          interval: null,
          surgical_consult_target_dept: 'Khoa Ngoại Tiêu hóa',
          reason: 'Sinh thiết dạ dày xác nhận ung thư biểu mô xâm lấn — cảnh báo hội chẩn Khoa Ngoại Tiêu hóa.'
        };
      }
      if (resection === 'ESD') return evaluateEsgeEsd2022(idx, 'GASTRIC');
      return {
        guideline_id: 'CLINICIAN_DIRECTED_EGD',
        guideline_version: '2022',
        category: 'NEEDS_PHYSICIAN_REVIEW',
        interval: null,
        surgical_consult_target_dept: null,
        reason: 'Sinh thiết kìm EGD hoặc can thiệp cầm máu XHTH trên — bác sĩ trực tiếp quyết định lịch hẹn kiểm tra.'
      };
    }

    const gpbStatus = c.pathology_completion_status || 'NOT_APPLICABLE';
    const gLabel = coloMode === 'ESGE_2020' ? 'ESGE_POST_POLYPECTOMY_2020' : 'USMSTF_POST_POLYPECTOMY_2020';
    if (gpbStatus === 'PENDING' || gpbStatus === 'PARTIAL') {
      return {
        guideline_id: gLabel,
        guideline_version: '2020',
        category: 'PENDING_DATA',
        interval: null,
        surgical_consult_target_dept: null,
        reason: 'Chưa đủ kết quả giải phẫu bệnh toàn ca đại trực tràng.'
      };
    }
    if (idx.resection_method === 'ESD') return evaluateEsgeEsd2022(idx, 'COLORECTAL');
    if (
      idx.histology_type === 'ADENOCARCINOMA_INVASIVE' ||
      wc.any_invasive_cancer_or_noncurative_feature === 'YES' ||
      idx.resection_method === 'UNRESECTED_REFERRED'
    ) {
      return {
        guideline_id: gLabel,
        guideline_version: '2020',
        category: 'SURGICAL_MDT_CONSULT_ALERT',
        interval: null,
        surgical_consult_target_dept: 'Khoa Phẫu thuật Đại trực tràng',
        reason: 'Phát hiện ung thư biểu mô xâm lấn hoặc tổn thương không cắt được qua nội soi — cảnh báo hội chẩn Khoa Phẫu thuật Đại trực tràng.'
      };
    }

    const segs = extractBbpsSegments(c);
    const cecalOk = c.cecal_intubation === 'YES';
    const bbpsOk = Boolean(cecalOk && segs && segs.length === 3 && (segs[0] + segs[1] + segs[2]) >= 6 && segs.every(function (s) { return s >= 2; }));
    if (!bbpsOk || wc.complete_resection_all_lesions === 'INCOMPLETE_OR_UNRESECTED') {
      return {
        guideline_id: gLabel,
        guideline_version: '2020',
        category: 'REPEAT_INADEQUATE_PREP_OR_INCOMPLETE',
        interval: 'LE_12M',
        surgical_consult_target_dept: null,
        reason: 'Chuẩn bị đại tràng không đạt chuẩn (BBPS < 6 hoặc có đoạn < 2) hoặc chưa tới manh tràng / chưa cắt trọn.'
      };
    }

    if (wc.any_piecemeal_ge_20mm === 'YES' || (idx.resection_method === 'EMR_PIECEMEAL' && Number(idx.size_mm || 0) >= 20)) {
      return {
        guideline_id: gLabel,
        guideline_version: '2020',
        category: 'LOCAL_SCAR_SURVEILLANCE',
        interval: coloMode === 'ESGE_2020' ? '3_6M' : '6M',
        surgical_consult_target_dept: null,
        reason: 'Cắt từng mảnh (Piecemeal EMR) tổn thương ≥ 20 mm — hẹn kiểm tra sẹo tại chỗ.'
      };
    }

    const isIdxAd = idx.histology_type === 'TUBULAR_ADENOMA' || idx.histology_type === 'TUBULOVILLOUS_ADENOMA' || idx.histology_type === 'VILLOUS_ADENOMA';
    const maxAdMm = Math.max(Number(wc.max_adenoma_size_mm || 0), isIdxAd ? Number(idx.size_mm || 0) : 0);
    const isIdxSsl = idx.histology_type === 'SSL_NO_DYSPLASIA' || idx.histology_type === 'SSL_WITH_DYSPLASIA';
    const maxSslMm = Math.max(Number(wc.max_ssl_size_mm || 0), isIdxSsl ? Number(idx.size_mm || 0) : 0);
    const anyHgdVillous = (
      wc.any_villous_or_hgd_any_lesion === 'YES' ||
      idx.dysplasia_grade === 'HGD' ||
      idx.histology_type === 'TUBULOVILLOUS_ADENOMA' ||
      idx.histology_type === 'VILLOUS_ADENOMA'
    );
    const anySslDysTsa = (
      wc.any_ssl_with_dysplasia_or_tsa === 'YES' ||
      idx.histology_type === 'SSL_WITH_DYSPLASIA' ||
      idx.histology_type === 'TSA'
    );
    const adBin = wc.confirmed_adenoma_count_bin || '0';
    const sslBin = wc.confirmed_ssl_count_bin || '0';

    if (coloMode === 'ESGE_2020') {
      const highRiskEsge = (
        maxAdMm >= 10 ||
        idx.dysplasia_grade === 'HGD' ||
        wc.any_hgd_any_lesion === 'YES' ||
        adBin === '5_10' ||
        adBin === 'GT_10' ||
        maxSslMm >= 10 ||
        anySslDysTsa
      );
      if (highRiskEsge) {
        return {
          guideline_id: 'ESGE_POST_POLYPECTOMY_2020',
          guideline_version: '2020',
          category: 'CURATIVE_SURVEILLANCE',
          interval: '3Y',
          surgical_consult_target_dept: null,
          reason: 'Có ≥ 1 tiêu chuẩn nguy cơ cao cần nội soi kiểm tra sau 3 năm theo ESGE 2020.'
        };
      }
      return {
        guideline_id: 'ESGE_POST_POLYPECTOMY_2020',
        guideline_version: '2020',
        category: 'CURATIVE_SURVEILLANCE',
        interval: '10Y_OR_SCREENING',
        surgical_consult_target_dept: null,
        reason: 'Không có tiêu chuẩn nguy cơ cao theo ESGE 2020 (1–4 u tuyến < 10 mm LGD / SSL < 10 mm không loạn sản / âm tính).'
      };
    }

    if (adBin === 'GT_10') {
      return {
        guideline_id: 'USMSTF_POST_POLYPECTOMY_2020',
        guideline_version: '2020',
        category: 'CURATIVE_SURVEILLANCE',
        interval: '1Y',
        surgical_consult_target_dept: null,
        reason: 'Hơn 10 u tuyến xác nhận GPB theo USMSTF 2020.'
      };
    }
    if (maxAdMm >= 10 || anyHgdVillous || adBin === '5_10' || maxSslMm >= 10 || anySslDysTsa || sslBin === 'GE_5') {
      return {
        guideline_id: 'USMSTF_POST_POLYPECTOMY_2020',
        guideline_version: '2020',
        category: 'CURATIVE_SURVEILLANCE',
        interval: '3Y',
        surgical_consult_target_dept: null,
        reason: 'Nhóm nguy cơ cao hẹn soi kiểm tra 3 năm theo USMSTF 2020.'
      };
    }
    if (adBin === '3_4' || sslBin === '3_4') {
      return {
        guideline_id: 'USMSTF_POST_POLYPECTOMY_2020',
        guideline_version: '2020',
        category: 'CURATIVE_SURVEILLANCE',
        interval: '3_5Y',
        surgical_consult_target_dept: null,
        reason: 'Có 3–4 u tuyến < 10 mm LGD hoặc 3–4 SSL < 10 mm không loạn sản theo USMSTF 2020.'
      };
    }
    if (adBin === '1_2') {
      return {
        guideline_id: 'USMSTF_POST_POLYPECTOMY_2020',
        guideline_version: '2020',
        category: 'CURATIVE_SURVEILLANCE',
        interval: '7_10Y',
        surgical_consult_target_dept: null,
        reason: 'Có 1–2 u tuyến ống < 10 mm loạn sản độ thấp theo USMSTF 2020.'
      };
    }
    if (sslBin === '1_2') {
      return {
        guideline_id: 'USMSTF_POST_POLYPECTOMY_2020',
        guideline_version: '2020',
        category: 'CURATIVE_SURVEILLANCE',
        interval: '5_10Y',
        surgical_consult_target_dept: null,
        reason: 'Có 1–2 polyp răng cưa không cuống (SSL) < 10 mm không loạn sản theo USMSTF 2020.'
      };
    }
    return {
      guideline_id: 'USMSTF_POST_POLYPECTOMY_2020',
      guideline_version: '2020',
      category: 'CURATIVE_SURVEILLANCE',
      interval: '10Y',
      surgical_consult_target_dept: null,
      reason: 'Nội soi đại trực tràng bình thường hoặc chỉ có polyp tăng sản < 10 mm trực tràng — đại tràng chậu hông.'
    };
  }

  function buildSurveillanceRecommendation(c, primaryColoMode) {
    const mode = primaryColoMode || 'USMSTF_2020';
    const primary = evaluateSingleGuideline(c, mode);
    const altMode = mode === 'USMSTF_2020' ? 'ESGE_2020' : 'USMSTF_2020';
    const ref = c.track === 'COL' ? evaluateSingleGuideline(c, altMode) : null;
    const interval = primary.interval;
    const refInterval = ref ? ref.interval : null;
    const isDivergent = Boolean(
      ref &&
      primary.guideline_id !== ref.guideline_id &&
      interval !== null &&
      refInterval !== null &&
      interval !== refInterval
    );
    const computedDue = (c.procedure_start_at && interval && INTERVAL_DAYS[interval])
      ? addCalendarDaysIso(c.procedure_start_at, INTERVAL_DAYS[interval])
      : null;
    const dueDate = c.clinician_followup_due_date || computedDue;
    let recStatus = 'ACTIVE_DUE';
    if (primary.category === 'PENDING_DATA') recStatus = 'PENDING_GPB';
    else if (primary.category === 'SURGICAL_MDT_CONSULT_ALERT') recStatus = 'CONSULT_ALERT';

    const reasonText = c.clinician_followup_note ? c.clinician_followup_note : primary.reason;
    return {
      origin_case_id: c.case_id,
      case_code: c.case_code,
      track: c.track,
      guideline_id: primary.guideline_id,
      guideline_version: primary.guideline_version,
      category: primary.category,
      recommended_interval_code: interval,
      recommended_interval_label: interval ? (INTERVAL_LABELS_VI[interval] || 'Bác sĩ chỉ định') : 'Theo chỉ định lâm sàng',
      reference_guideline_id: ref ? ref.guideline_id : null,
      reference_interval_code: refInterval,
      reference_interval_label: refInterval ? (INTERVAL_LABELS_VI[refInterval] || '') : null,
      is_divergent_guideline: isDivergent,
      due_date: dueDate,
      surgical_consult_target_dept: primary.surgical_consult_target_dept,
      reason: reasonText,
      status: recStatus,
      fulfilled_by_case_id: c.fulfilled_by_case_id || null
    };
  }

  function computeErcpSessionIndices(casesList, episodesById) {
    const byEp = {};
    for (let i = 0; i < casesList.length; i += 1) {
      const c = casesList[i];
      if (c.track === 'ERCP' && (c.record_status || 'ACTIVE') === 'ACTIVE') {
        const epId = c.episode_id || c.case_id;
        if (!byEp[epId]) byEp[epId] = [];
        byEp[epId].push(c);
      }
    }
    const result = {};
    const epKeys = Object.keys(byEp);
    for (let i = 0; i < epKeys.length; i += 1) {
      const epId = epKeys[i];
      const ordered = byEp[epId].slice().sort(function (a, b) {
        const pCmp = String(a.procedure_start_at || '').localeCompare(String(b.procedure_start_at || ''));
        if (pCmp !== 0) return pCmp;
        const cCmp = String(a.created_at || '').localeCompare(String(b.created_at || ''));
        if (cCmp !== 0) return cCmp;
        return String(a.case_id || '').localeCompare(String(b.case_id || ''));
      });
      const epObj = (episodesById && episodesById[epId]) || {};
      const epOffset = Number(epObj.prior_unrecorded_ercp_offset || 0);
      for (let idx = 0; idx < ordered.length; idx += 1) {
        const item = ordered[idx];
        const caseOffset = Number(item.prior_unrecorded_ercp_offset || epOffset || 0);
        result[item.case_id] = (idx + 1) + caseOffset;
      }
    }
    return result;
  }

  function pctRate(num, den) {
    if (den <= 0) return null;
    return pyRound((num * 100.0) / den, 1);
  }

  function rateStatus(num, den, targetPct, nMin) {
    if (den < nMin) return 'insufficient_n';
    if (targetPct === null || targetPct === undefined) return 'no_target';
    if ((num * 100.0) >= (targetPct * den - 1e-9)) return 'met';
    return 'below_target';
  }

  function computeMean(arr) {
    if (!arr.length) return null;
    let sum = 0;
    for (let i = 0; i < arr.length; i += 1) sum += arr[i];
    return pyRound(sum / arr.length, 2);
  }

  function computeMedian(arr) {
    if (!arr.length) return null;
    const sorted = arr.slice().sort(function (a, b) { return a - b; });
    const mid = Math.floor(sorted.length / 2);
    const med = (sorted.length % 2 === 1) ? sorted[mid] : ((sorted[mid - 1] + sorted[mid]) / 2.0);
    return pyRound(med, 2);
  }

  function computeKpiSnapshot(casesList, patientsById, minAdrAge, nMin) {
    const effectiveNMin = Math.max(1, Number(nMin || 20));
    const activeCases = casesList.filter(function (c) { return (c.record_status || 'ACTIVE') === 'ACTIVE'; });
    const coloCases = activeCases.filter(function (c) { return c.track === 'COL'; });
    const cirEligible = coloCases.filter(function (c) { return !c.exclude_from_cir; });
    const cirNum = cirEligible.filter(function (c) { return c.cecal_intubation === 'YES'; }).length;

    let bbpsEvalCount = 0;
    let bbpsAdeqNum = 0;
    for (let i = 0; i < cirEligible.length; i += 1) {
      const c = cirEligible[i];
      const segs = extractBbpsSegments(c);
      if (c.cecal_intubation === 'YES' && segs !== null) {
        bbpsEvalCount += 1;
        if (evaluateBbps(segs[0], segs[1], segs[2], 'YES').adequate) {
          bbpsAdeqNum += 1;
        }
      }
    }

    const adrCohortAll = coloCases.filter(function (c) {
      const procYear = Number(String(c.procedure_start_at || '2026').slice(0, 4));
      const pat = (patientsById && patientsById[c.patient_uid]) || {};
      const birthYear = Number(pat.birth_year || c.birth_year || procYear);
      const age = c.age !== null && c.age !== undefined ? Number(c.age) : Math.max(0, procYear - birthYear);
      const indOk = c.indication === 'SCREENING' || c.indication === 'DIAGNOSTIC' || c.indication === 'ABNORMAL_FECAL_TEST';
      return age >= minAdrAge && indOk && !c.has_ibd_or_polyposis && c.cecal_intubation === 'YES';
    });

    const pdrNum = adrCohortAll.filter(function (c) {
      return Number((c.whole_case_summary && c.whole_case_summary.macroscopic_polyp_count) || 0) >= 1;
    }).length;

    const adrPendingGpb = adrCohortAll.filter(function (c) {
      const polyCnt = Number((c.whole_case_summary && c.whole_case_summary.macroscopic_polyp_count) || 0);
      return polyCnt >= 1 && (c.pathology_completion_status === 'PENDING' || c.pathology_completion_status === 'PARTIAL');
    });
    const pendingSet = new Set(adrPendingGpb.map(function (c) { return c.case_id; }));
    const adrEvaluated = adrCohortAll.filter(function (c) { return !pendingSet.has(c.case_id); });
    const adrNum = adrEvaluated.filter(function (c) {
      return (c.whole_case_summary && c.whole_case_summary.any_confirmed_adenoma) === 'YES';
    }).length;
    const ssldrNum = adrEvaluated.filter(function (c) {
      return (c.whole_case_summary && c.whole_case_summary.any_confirmed_ssl) === 'YES';
    }).length;

    const cleanWtValues = coloCases.filter(function (c) {
      const mp = Number((c.whole_case_summary && c.whole_case_summary.macroscopic_polyp_count) || 0);
      const rm = (c.index_lesion && c.index_lesion.resection_method) || 'NONE';
      return c.cecal_intubation === 'YES' && mp === 0 && rm === 'NONE' && c.withdrawal_time_clean_min !== null && c.withdrawal_time_clean_min !== undefined;
    }).map(function (c) { return Number(c.withdrawal_time_clean_min); });

    const ercpCases = activeCases.filter(function (c) { return c.track === 'ERCP'; });
    let ercpNativeDen = 0;
    let ercpCannNum = 0;
    let ercpDiffNum = 0;
    for (let i = 0; i < ercpCases.length; i += 1) {
      const c = ercpCases[i];
      const det = c.ercp_detail || c;
      const papilla = det.papilla_status || 'NATIVE_INTACT';
      const obstructed = Boolean(det.duodenal_obstruction_or_altered);
      if (papilla === 'NATIVE_INTACT' && !obstructed) {
        ercpNativeDen += 1;
        if (det.selective_cannulation === 'SUCCESS') ercpCannNum += 1;
        if (isDifficultCannulationEsge2016(papilla, Number(det.cannulation_contacts_count || 0), Number(det.cannulation_time_min || 0), Number(det.unintended_pd_count || 0)) === 'YES') {
          ercpDiffNum += 1;
        }
      }
    }

    let allFuEvalDen = 0;
    let allFuMissing = 0;
    let allFuPendingWindow = 0;
    let allFuLost = 0;
    let agreeAnyNum = 0;
    let agreeSevereNum = 0;
    for (let i = 0; i < activeCases.length; i += 1) {
      const ae = summarizeCaseAdverseEvents(activeCases[i]);
      if (ae.completed_followup) {
        allFuEvalDen += 1;
        if (ae.is_agree_any || ae.has_pep || ae.followup_30d_status === 'COMPLETED_WITH_AE') agreeAnyNum += 1;
        if (ae.is_agree_severe_ge_iii) agreeSevereNum += 1;
      } else {
        allFuMissing += 1;
        if (ae.followup_30d_status === 'PENDING_WINDOW') allFuPendingWindow += 1;
        else if (ae.followup_30d_status === 'LOST_TO_FOLLOWUP') allFuLost += 1;
      }
    }

    let ercpFuEvalDen = 0;
    let ercpFuMissing = 0;
    let pepNum = 0;
    let pepSevereNum = 0;
    let ercpAgreeSevereNum = 0;
    for (let i = 0; i < ercpCases.length; i += 1) {
      const ae = summarizeCaseAdverseEvents(ercpCases[i]);
      if (ae.completed_followup) {
        ercpFuEvalDen += 1;
        if (ae.has_pep) {
          pepNum += 1;
          if (ae.highest_pep_severity === 'SEVERE') pepSevereNum += 1;
        }
        if (ae.is_agree_severe_ge_iii) ercpAgreeSevereNum += 1;
      } else {
        ercpFuMissing += 1;
      }
    }

    return {
      min_adr_age: minAdrAge,
      n_min: effectiveNMin,
      total_active_cases: activeCases.length,
      counts_by_track: {
        EGD: activeCases.filter(function (c) { return c.track === 'EGD'; }).length,
        COL: coloCases.length,
        ERCP: ercpCases.length
      },
      cir: {
        numerator: cirNum,
        denominator: cirEligible.length,
        rate_pct: pctRate(cirNum, cirEligible.length),
        target_pct: 90.0,
        n_min: effectiveNMin,
        status: rateStatus(cirNum, cirEligible.length, 90.0, effectiveNMin)
      },
      bbps_adequate: {
        numerator: bbpsAdeqNum,
        denominator: bbpsEvalCount,
        rate_pct: pctRate(bbpsAdeqNum, bbpsEvalCount),
        target_pct: 90.0,
        n_min: effectiveNMin,
        status: rateStatus(bbpsAdeqNum, bbpsEvalCount, 90.0, effectiveNMin)
      },
      pdr: {
        numerator: pdrNum,
        denominator: adrCohortAll.length,
        rate_pct: pctRate(pdrNum, adrCohortAll.length),
        n_min: effectiveNMin,
        status: rateStatus(pdrNum, adrCohortAll.length, null, effectiveNMin)
      },
      adr: {
        numerator: adrNum,
        denominator: adrEvaluated.length,
        rate_pct: pctRate(adrNum, adrEvaluated.length),
        target_pct: 35.0,
        n_min: effectiveNMin,
        status: rateStatus(adrNum, adrEvaluated.length, 35.0, effectiveNMin),
        pending_gpb_excluded_count: adrPendingGpb.length
      },
      ssldr: {
        numerator: ssldrNum,
        denominator: adrEvaluated.length,
        rate_pct: pctRate(ssldrNum, adrEvaluated.length),
        target_pct: 6.0,
        n_min: effectiveNMin,
        status: rateStatus(ssldrNum, adrEvaluated.length, 6.0, effectiveNMin),
        pending_gpb_excluded_count: adrPendingGpb.length
      },
      clean_withdrawal_time: {
        count: cleanWtValues.length,
        mean_min: computeMean(cleanWtValues),
        median_min: computeMedian(cleanWtValues),
        target_min: 6.0
      },
      ercp_native_cannulation: {
        numerator: ercpCannNum,
        denominator: ercpNativeDen,
        rate_pct: pctRate(ercpCannNum, ercpNativeDen),
        target_pct: 90.0,
        n_min: effectiveNMin,
        status: rateStatus(ercpCannNum, ercpNativeDen, 90.0, effectiveNMin),
        difficult_esge2016_count: ercpDiffNum
      },
      adverse_events_all: {
        agree_any_numerator: agreeAnyNum,
        agree_severe_numerator: agreeSevereNum,
        completed_fu_denominator: allFuEvalDen,
        agree_severe_rate_pct: pctRate(agreeSevereNum, allFuEvalDen),
        missing_or_pending_fu_count: allFuMissing,
        pending_window_count: allFuPendingWindow,
        lost_to_followup_count: allFuLost
      },
      ercp_pep: {
        numerator: pepNum,
        pep_severe_numerator: pepSevereNum,
        ercp_agree_severe_numerator: ercpAgreeSevereNum,
        completed_fu_denominator: ercpFuEvalDen,
        rate_pct: pctRate(pepNum, ercpFuEvalDen),
        missing_or_pending_fu_count: ercpFuMissing
      }
    };
  }

  function buildCusumSeriesFromCases(casesList, metric, preset) {
    const usePreset = preset === 'SCREENING_CIR_95' ? 'SCREENING_CIR_95' : 'DEFAULT_90';
    const useMetric = metric === 'ERCP_NATIVE' ? 'ERCP_NATIVE' : 'CIR';
    const p0 = usePreset === 'SCREENING_CIR_95' ? 0.05 : 0.10;
    const p1 = usePreset === 'SCREENING_CIR_95' ? 0.10 : 0.20;
    const alpha = 0.05;
    const beta = 0.10;
    const wFail = Math.log(p1 / p0);
    const wSucc = Math.log((1.0 - p1) / (1.0 - p0));
    const hLimit = Math.log((1.0 - beta) / alpha);

    const active = casesList.filter(function (c) { return (c.record_status || 'ACTIVE') === 'ACTIVE'; }).sort(function (a, b) {
      const pCmp = String(a.procedure_start_at || '').localeCompare(String(b.procedure_start_at || ''));
      if (pCmp !== 0) return pCmp;
      return String(a.case_code || '').localeCompare(String(b.case_code || ''));
    });

    const outcomes = [];
    const codes = [];
    if (useMetric === 'ERCP_NATIVE') {
      for (let i = 0; i < active.length; i += 1) {
        const c = active[i];
        if (c.track !== 'ERCP') continue;
        const det = c.ercp_detail || c;
        if ((det.papilla_status || 'NATIVE_INTACT') === 'NATIVE_INTACT' && !det.duodenal_obstruction_or_altered) {
          outcomes.push(det.selective_cannulation === 'SUCCESS' ? 0 : 1);
          codes.push(c.case_code);
        }
      }
    } else {
      for (let i = 0; i < active.length; i += 1) {
        const c = active[i];
        if (c.track !== 'COL' || c.exclude_from_cir) continue;
        if (usePreset === 'SCREENING_CIR_95' && c.indication !== 'SCREENING') continue;
        outcomes.push(c.cecal_intubation === 'YES' ? 0 : 1);
        codes.push(c.case_code);
      }
    }

    let sCont = 0.0;
    let sReset = 0.0;
    const trajectory = [0.0];
    const resetTrajectory = [0.0];
    let alarmAt = null;
    const points = [];
    for (let i = 0; i < outcomes.length; i += 1) {
      const idx = i + 1;
      const xT = Number(outcomes[i]);
      const w = xT === 1 ? wFail : wSucc;
      sCont = Math.max(0.0, sCont + w);
      sReset = Math.max(0.0, sReset + w);
      let triggeredNow = false;
      if (sCont >= hLimit && alarmAt === null) {
        alarmAt = idx;
      }
      const trajVal = pyRound(sCont, 6);
      const resetVal = pyRound(sReset, 6);
      if (sReset >= hLimit) {
        triggeredNow = true;
        sReset = 0.0;
      }
      trajectory.push(trajVal);
      resetTrajectory.push(resetVal);
      points.push({
        index: idx,
        case_code: codes[i] || ('CA-' + String(idx).padStart(3, '0')),
        failure: xT,
        s_continuous: trajVal,
        s_reset_view: resetVal,
        alarm_crossed: triggeredNow
      });
    }

    return {
      ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL',
      disclaimer_vi: 'Giám sát kiểm soát chất lượng cá nhân không hiệu chỉnh nguy cơ — chỉ dùng cho tự kiểm toán nội bộ, không dùng đánh giá thi đua hay kết luận năng lực pháp lý.',
      p0: p0,
      p1: p1,
      alpha: alpha,
      beta: beta,
      w_success: pyRound(wSucc, 6),
      w_failure: pyRound(wFail, 6),
      h_limit: pyRound(hLimit, 6),
      trajectory: trajectory,
      reset_trajectory: resetTrajectory,
      alarm_case_number: alarmAt,
      points: points,
      metric: metric || 'CIR',
      preset: preset || 'DEFAULT_90'
    };
  }

  const GENESIS_HASH = '0'.repeat(64);

  function computeEntryHash(seq, timestampUtc, actorUsername, actorRole, action, entityType, entityId, detail, prevHash) {
    const material = [
      prevHash,
      String(seq),
      timestampUtc,
      actorUsername,
      actorRole,
      action,
      entityType,
      entityId,
      canonicalJson(detail || {})
    ].join('|');
    return sha256Hex(material);
  }

  function buildAuditEntry(existingChain, actorUsername, actorRole, action, entityType, entityId, detail, nowUtc) {
    const seq = existingChain.length + 1;
    const prevHash = existingChain.length > 0 ? existingChain[existingChain.length - 1].entry_hash : GENESIS_HASH;
    const ts = nowUtcNoMicrosIso(nowUtc);
    const safeDetail = detail || {};
    const entryHash = computeEntryHash(seq, ts, actorUsername, actorRole, action, entityType, entityId, safeDetail, prevHash);
    return {
      seq: seq,
      timestamp_utc: ts,
      actor_username: actorUsername,
      actor_role: actorRole,
      action: action,
      entity_type: entityType,
      entity_id: entityId,
      detail: safeDetail,
      prev_hash: prevHash,
      entry_hash: entryHash
    };
  }

  function verifyAuditChain(chain) {
    let expectedPrev = GENESIS_HASH;
    for (let i = 0; i < chain.length; i += 1) {
      const idx = i + 1;
      const item = chain[i];
      if (!item || item.seq !== idx) {
        return { valid: false, checked_entries: idx - 1, broken_at_seq: idx, reason: 'SEQ_GAP_OR_OUT_OF_ORDER' };
      }
      if (item.prev_hash !== expectedPrev) {
        return { valid: false, checked_entries: idx - 1, broken_at_seq: idx, reason: 'PREV_HASH_MISMATCH' };
      }
      const recomputed = computeEntryHash(
        item.seq,
        item.timestamp_utc,
        item.actor_username,
        item.actor_role,
        item.action,
        item.entity_type,
        item.entity_id,
        item.detail || {},
        expectedPrev
      );
      if (recomputed !== item.entry_hash) {
        return { valid: false, checked_entries: idx - 1, broken_at_seq: idx, reason: 'ENTRY_HASH_TAMPERED' };
      }
      expectedPrev = recomputed;
    }
    return {
      valid: true,
      checked_entries: chain.length,
      head_hash: expectedPrev,
      broken_at_seq: null,
      reason: 'OK'
    };
  }

  function verifyVirtualLineageBridges(bridges, virtualBackupFiles, auditChain) {
    const list = Array.isArray(bridges) ? bridges : [];
    const items = [];
    let allValid = true;
    const bridgeSigs = new Set();
    const displacedRestoreSigs = new Set();

    function extractSig(rec) {
      if (!rec || typeof rec !== 'object') return null;
      const fn = String(rec.pre_restore_filename || '').trim();
      const sha = String(rec.pre_restore_sha256 || '').trim().toLowerCase();
      const dispH = String(rec.displaced_live_head_hash || '').trim().toLowerCase();
      const dispS = Number(rec.displaced_live_seq || 0);
      const bkpH = String(rec.backup_pre_append_head_hash || '').trim().toLowerCase();
      const bkpS = Number(rec.backup_pre_append_seq || 0);
      if (!/^pre_restore_[A-Za-z0-9_]+\.json$/.test(fn)) return null;
      if (!/^[0-9a-f]{64}$/.test(sha) || !/^[0-9a-f]{64}$/.test(dispH) || !/^[0-9a-f]{64}$/.test(bkpH)) return null;
      if (dispS < 1 || bkpS < 1) return null;
      return [fn, sha, dispH, dispS, bkpH, bkpS].join('|');
    }

    for (let i = 0; i < list.length; i += 1) {
      const raw = list[i] || {};
      const fname = String(raw.pre_restore_filename || '').trim();
      const expectedSha = String(raw.pre_restore_sha256 || '').trim().toLowerCase();
      const sig = extractSig(raw);
      const rawJsonText = virtualBackupFiles && Object.prototype.hasOwnProperty.call(virtualBackupFiles, fname)
        ? virtualBackupFiles[fname]
        : null;
      const filePresent = typeof rawJsonText === 'string';
      let shaMatches = false;
      let displacedValid = false;
      if (filePresent && sig) {
        const actualSha = sha256Hex(rawJsonText);
        shaMatches = actualSha === expectedSha;
        if (shaMatches) {
          try {
            const dispObj = JSON.parse(rawJsonText);
            const dVer = verifyAuditChain(dispObj.audit_chain || []);
            displacedValid = Boolean(
              dVer.valid &&
              String(dVer.head_hash || '').toLowerCase() === String(raw.displaced_live_head_hash || '').toLowerCase() &&
              Number(dVer.checked_entries) === Number(raw.displaced_live_seq)
            );
            if (displacedValid) {
              (dispObj.audit_chain || []).forEach(function (entry) {
                if (entry && entry.action === 'RESTORE_PROFILE_A_ENCRYPTED') {
                  const s = extractSig(entry.detail);
                  if (s) displacedRestoreSigs.add(s);
                }
              });
            }
          } catch (_err) {
            displacedValid = false;
          }
        }
      }
      if (sig) bridgeSigs.add(sig);
      const ok = Boolean(sig && filePresent && shaMatches && displacedValid);
      if (!ok) allValid = false;
      items.push({
        bridge_index: i + 1,
        restored_at_utc: raw.restored_at_utc,
        actor_username: raw.actor_username,
        previous_store_epoch: raw.previous_store_epoch || 1,
        new_store_epoch: raw.new_store_epoch,
        vault_blob_sha256: raw.vault_blob_sha256,
        backup_pre_append_head_hash: raw.backup_pre_append_head_hash,
        backup_pre_append_seq: raw.backup_pre_append_seq,
        displaced_live_head_hash: raw.displaced_live_head_hash,
        displaced_live_seq: raw.displaced_live_seq,
        pre_restore_filename: fname || 'INVALID_FILENAME',
        pre_restore_sha256: expectedSha,
        pre_restore_file_present: filePresent,
        pre_restore_sha256_valid: shaMatches,
        displaced_audit_chain_valid: displacedValid,
        preserve_current_users: raw.preserve_current_users !== false,
        key_mismatch_policy: raw.key_mismatch_policy || 'REJECT',
        valid: ok
      });
    }

    const rootSigs = new Set();
    let chainConsistencyOk = true;
    (auditChain || []).forEach(function (entry) {
      if (entry && entry.action === 'RESTORE_PROFILE_A_ENCRYPTED') {
        const s = extractSig(entry.detail);
        if (!s) chainConsistencyOk = false;
        else rootSigs.add(s);
      }
    });
    const expectedAll = new Set();
    rootSigs.forEach(function (s) { expectedAll.add(s); });
    displacedRestoreSigs.forEach(function (s) { expectedAll.add(s); });
    if (bridgeSigs.size !== expectedAll.size) {
      chainConsistencyOk = false;
    } else {
      expectedAll.forEach(function (s) {
        if (!bridgeSigs.has(s)) chainConsistencyOk = false;
      });
    }
    if (!chainConsistencyOk) allValid = false;

    return {
      valid: allValid,
      bridge_count: items.length,
      audit_chain_consistency_valid: chainConsistencyOk,
      items: items
    };
  }
"""

_DEMO_ENGINE_SERVICE_JS = r"""
  /* =========================================================================
   * 4. SCHEMA VALIDATION, DEFAULTS, EXPORTS & CREATE SYNTHETIC RAM ENGINE
   * ========================================================================= */
  function toSetMap(arr) {
    const m = {};
    for (let i = 0; i < arr.length; i += 1) m[arr[i]] = true;
    return m;
  }

  const ENUM_SETS = {
    track: toSetMap(['EGD', 'COL', 'ERCP']),
    care: toSetMap(['INPATIENT', 'OUTPATIENT']),
    sex: toSetMap(['M', 'F', 'O']),
    indication: toSetMap(['SCREENING', 'DIAGNOSTIC', 'ABNORMAL_FECAL_TEST', 'SURVEILLANCE', 'THERAPEUTIC', 'IBD_EVAL', 'GI_BLEEDING', 'EARLY_CANCER_WORKUP', 'BILIARY_STONE', 'MALIGNANT_STRICTURE', 'CHOLANGITIS', 'BILIARY_PANCREATITIS', 'STENT_EXCHANGE', 'OTHER']),
    pathology: toSetMap(['NOT_APPLICABLE', 'PENDING', 'PARTIAL', 'COMPLETE']),
    fu30: toSetMap(['PENDING_WINDOW', 'COMPLETED_NO_AE', 'COMPLETED_WITH_AE', 'LOST_TO_FOLLOWUP']),
    cecal: toSetMap(['NA', 'YES', 'NO']),
    tristate: toSetMap(['YES', 'NO', 'PENDING_UNKNOWN']),
    bleedSrc: toSetMap(['NONE', 'VARICEAL_ESOPHAGEAL', 'VARICEAL_GASTRIC', 'NON_VARICEAL_ULCER', 'NON_VARICEAL_OTHER']),
    hemoOk: toSetMap(['NA', 'YES', 'NO']),
    resect: toSetMap(['NONE', 'BIOPSY_ONLY', 'COLD_SNARE', 'HOT_SNARE', 'EMR_EN_BLOC', 'EMR_PIECEMEAL', 'ESD', 'HEMOSTASIS', 'UNRESECTED_REFERRED']),
    histology: toSetMap(['NONE', 'INFLAMMATORY_BENIGN', 'INTESTINAL_METAPLASIA', 'HYPERPLASTIC', 'TUBULAR_ADENOMA', 'TUBULOVILLOUS_ADENOMA', 'VILLOUS_ADENOMA', 'SSL_NO_DYSPLASIA', 'SSL_WITH_DYSPLASIA', 'TSA', 'LGD_VIENNA_C3', 'HGD_VIENNA_C4', 'ADENOCARCINOMA_INTRAMUCOSAL', 'ADENOCARCINOMA_INVASIVE', 'OTHER']),
    dysplasia: toSetMap(['NONE', 'LGD', 'HGD', 'INVASIVE']),
    margins: toSetMap(['NA', 'PENDING', 'R0', 'HM1_ONLY', 'VM1_OR_R1', 'RX_PIECEMEAL']),
    lvi: toSetMap(['NA', 'NEGATIVE', 'POSITIVE']),
    diff: toSetMap(['NA', 'WELL_MOD', 'POOR_UNDIFF']),
    budding: toSetMap(['NA', 'BD1', 'BD2_BD3']),
    completeRes: toSetMap(['NOT_APPLICABLE', 'ALL_RESECTED_COMPLETELY', 'INCOMPLETE_OR_UNRESECTED']),
    yesNo: toSetMap(['YES', 'NO']),
    adBin: toSetMap(['0', '1_2', '3_4', '5_10', 'GT_10']),
    sslBin: toSetMap(['0', '1_2', '3_4', 'GE_5']),
    altAnat: toSetMap(['NONE', 'BILLROTH_II', 'ROUX_EN_Y', 'OTHER']),
    papilla: toSetMap(['NATIVE_INTACT', 'PRIOR_SPHINCTEROTOMY', 'PRIOR_STENT_IN_SITU', 'SURGICAL_BILIARY_ENTERIC']),
    vater: toSetMap(['1', '2', '3a', '3b', '4']),
    duct: toSetMap(['CBD', 'PD', 'BOTH']),
    cannSel: toSetMap(['SUCCESS', 'FAILED']),
    aeWin: toSetMap(['INTRAPROCEDURAL', 'INPATIENT_EARLY', 'DELAYED_30D']),
    aeType: toSetMap(['PEP', 'BLEEDING', 'PERFORATION', 'CHOLANGITIS', 'CARDIOPULMONARY', 'OTHER']),
    pepSev: toSetMap(['NONE', 'MILD', 'MODERATE', 'SEVERE']),
    agree: toSetMap(['NONE', 'I', 'II', 'IIIa', 'IIIb', 'IVa', 'IVb', 'V']),
    mrnChoice: toSetMap(['TARGET', 'SOURCE'])
  };

  function makeValErr(fieldPath, msg) {
    return { code: 'VALIDATION_ERROR', field: fieldPath, message: msg };
  }

  const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
  const ISO_TS_OR_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?)?$/;

  function isValidCalendarYmd(yStr, mStr, dStr) {
    const y = Number(yStr);
    const m = Number(mStr);
    const d = Number(dStr);
    if (!Number.isInteger(y) || y < 1 || y > 9999 || m < 1 || m > 12 || d < 1 || d > 31) return false;
    const utcMs = Date.UTC(y, m - 1, d);
    const dtObj = new Date(utcMs);
    dtObj.setUTCFullYear(y);
    return dtObj.getUTCFullYear() === y && (dtObj.getUTCMonth() + 1) === m && dtObj.getUTCDate() === d;
  }

  function isValidIsoCalendarDate(strVal, allowTimeSuffix) {
    if (typeof strVal !== 'string') return false;
    if (!allowTimeSuffix) {
      const m = ISO_DATE_RE.exec(strVal);
      if (!m) return false;
      return isValidCalendarYmd(m[1], m[2], m[3]);
    }
    const m = ISO_TS_OR_DATE_RE.exec(strVal);
    if (!m) return false;
    if (!isValidCalendarYmd(m[1], m[2], m[3])) return false;
    if (m[4] !== undefined) {
      const hh = Number(m[4]);
      const mm = Number(m[5]);
      const ss = m[6] !== undefined ? Number(m[6]) : 0;
      if (hh < 0 || hh > 23 || mm < 0 || mm > 59 || ss < 0 || ss > 59) return false;
    }
    return true;
  }

  function validateFieldRule(parentObj, rk, rule, fieldPath) {
    const val = parentObj[rk];
    if (val === undefined) {
      if (rule.req) return makeValErr(fieldPath, 'Thiếu trường bắt buộc: ' + fieldPath + '.');
      return null;
    }
    if (val === null) {
      if (rule.nullable) return null;
      return makeValErr(fieldPath, 'Trường ' + fieldPath + ' không được phép để null.');
    }
    if (rule.t === 'str') {
      if (typeof val !== 'string') return makeValErr(fieldPath, 'Trường ' + fieldPath + ' phải là chuỗi ký tự.');
      const normStr = rule.trim ? val.trim() : val;
      if (rule.minLen !== undefined && normStr.length < rule.minLen) return makeValErr(fieldPath, 'Trường ' + fieldPath + ' quá ngắn.');
      if (rule.maxLen !== undefined && normStr.length > rule.maxLen) return makeValErr(fieldPath, 'Trường ' + fieldPath + ' vượt quá độ dài tối đa.');
      if (rule.isoDate && !isValidIsoCalendarDate(normStr, false)) return makeValErr(fieldPath, 'Ngày lịch không hợp lệ tại ' + fieldPath + ' (bắt buộc chuẩn YYYY-MM-DD).');
      if (rule.isoTimestamp && !isValidIsoCalendarDate(normStr, true)) return makeValErr(fieldPath, 'Thời điểm không hợp lệ tại ' + fieldPath + ' (bắt buộc chuẩn ISO YYYY-MM-DD[THH:MM]).');
      if (rule.enumSet && !rule.enumSet[normStr]) return makeValErr(fieldPath, 'Giá trị danh mục không hợp lệ tại ' + fieldPath + '.');
      if (rule.trim) parentObj[rk] = normStr;
      return null;
    }
    if (rule.t === 'bool') {
      if (typeof val !== 'boolean') return makeValErr(fieldPath, 'Trường ' + fieldPath + ' phải là kiểu logic đúng/sai.');
      return null;
    }
    if (rule.t === 'int') {
      let n = null;
      if (typeof val === 'number' && Number.isInteger(val)) n = val;
      else if (typeof val === 'string' && /^-?\d+$/.test(val.trim())) {
        const parsed = Number(val.trim());
        if (Number.isSafeInteger(parsed)) n = parsed;
      }
      if (n === null) return makeValErr(fieldPath, 'Trường ' + fieldPath + ' phải là số nguyên hợp lệ.');
      if (rule.min !== undefined && n < rule.min) return makeValErr(fieldPath, 'Giá trị ' + fieldPath + ' nhỏ hơn ngưỡng cho phép.');
      if (rule.max !== undefined && n > rule.max) return makeValErr(fieldPath, 'Giá trị ' + fieldPath + ' vượt quá ngưỡng cho phép.');
      parentObj[rk] = n;
      return null;
    }
    if (rule.t === 'float') {
      let f = null;
      if (typeof val === 'number' && Number.isFinite(val)) f = val;
      else if (typeof val === 'string' && val.trim() !== '') {
        const pf = Number(val.trim());
        if (Number.isFinite(pf)) f = pf;
      }
      if (f === null) return makeValErr(fieldPath, 'Trường ' + fieldPath + ' phải là số thực hợp lệ.');
      if (rule.min !== undefined && f < rule.min) return makeValErr(fieldPath, 'Giá trị ' + fieldPath + ' nhỏ hơn ngưỡng cho phép.');
      if (rule.max !== undefined && f > rule.max) return makeValErr(fieldPath, 'Giá trị ' + fieldPath + ' vượt quá ngưỡng cho phép.');
      parentObj[rk] = f;
      return null;
    }
    if (rule.t === 'str_list') {
      if (!Array.isArray(val)) return makeValErr(fieldPath, 'Trường ' + fieldPath + ' phải là danh sách chuỗi.');
      for (let i = 0; i < val.length; i += 1) {
        if (typeof val[i] !== 'string') return makeValErr(fieldPath + '[' + i + ']', 'Phần tử phải là chuỗi.');
      }
      return null;
    }
    if (rule.t === 'obj') {
      return validateModelObject(val, rule.schema, fieldPath);
    }
    if (rule.t === 'obj_list') {
      if (!Array.isArray(val)) return makeValErr(fieldPath, 'Trường ' + fieldPath + ' phải là danh sách đối tượng.');
      for (let i = 0; i < val.length; i += 1) {
        const subErr = validateModelObject(val[i], rule.schema, fieldPath + '[' + i + ']');
        if (subErr) return subErr;
      }
      return null;
    }
    return null;
  }

  function validateModelObject(obj, schemaMap, pathPrefix) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) {
      return makeValErr(pathPrefix || 'body', 'Dữ liệu gửi lên phải là đối tượng JSON hợp lệ.');
    }
    const keys = Object.keys(obj);
    for (let i = 0; i < keys.length; i += 1) {
      const k = keys[i];
      if (!Object.prototype.hasOwnProperty.call(schemaMap, k)) {
        const extraPath = pathPrefix ? (pathPrefix + '.' + k) : k;
        return makeValErr(extraPath, 'Trường không được phép trong hợp đồng dữ liệu (extra=forbid): ' + extraPath + '.');
      }
    }
    const ruleKeys = Object.keys(schemaMap);
    for (let i = 0; i < ruleKeys.length; i += 1) {
      const rk = ruleKeys[i];
      const fPath = pathPrefix ? (pathPrefix + '.' + rk) : rk;
      const err = validateFieldRule(obj, rk, schemaMap[rk], fPath);
      if (err) return err;
    }
    return null;
  }

  const SCHEMA_INDEX_LESION = {
    anatomical_site: { t: 'str' },
    size_mm: { t: 'float', nullable: true, min: 0, max: 250 },
    paris_class: { t: 'str' },
    surface_pattern: { t: 'str' },
    bleeding_source_type: { t: 'str', enumSet: ENUM_SETS.bleedSrc },
    forrest_class: { t: 'str' },
    hemostasis_modality: { t: 'str' },
    hemostasis_initial_success: { t: 'str', enumSet: ENUM_SETS.hemoOk },
    biopsy_jar_count: { t: 'int', min: 0, max: 20 },
    resection_method: { t: 'str', enumSet: ENUM_SETS.resect },
    histology_type: { t: 'str', enumSet: ENUM_SETS.histology },
    dysplasia_grade: { t: 'str', enumSet: ENUM_SETS.dysplasia },
    margins_status: { t: 'str', enumSet: ENUM_SETS.margins },
    sm_invasion_um: { t: 'int', nullable: true, min: 0, max: 50000 },
    lvi_status: { t: 'str', enumSet: ENUM_SETS.lvi },
    differentiation: { t: 'str', enumSet: ENUM_SETS.diff },
    budding_grade: { t: 'str', enumSet: ENUM_SETS.budding }
  };

  const SCHEMA_WHOLE_CASE = {
    macroscopic_polyp_count: { t: 'int', min: 0, max: 200 },
    complete_resection_all_lesions: { t: 'str', enumSet: ENUM_SETS.completeRes },
    any_piecemeal_ge_20mm: { t: 'str', enumSet: ENUM_SETS.yesNo },
    any_confirmed_adenoma: { t: 'str', enumSet: ENUM_SETS.tristate },
    confirmed_adenoma_count_bin: { t: 'str', enumSet: ENUM_SETS.adBin },
    max_adenoma_size_mm: { t: 'float', nullable: true, min: 0, max: 250 },
    any_villous_or_hgd_any_lesion: { t: 'str', enumSet: ENUM_SETS.tristate },
    any_hgd_any_lesion: { t: 'str', enumSet: ENUM_SETS.tristate },
    any_confirmed_ssl: { t: 'str', enumSet: ENUM_SETS.tristate },
    confirmed_ssl_count_bin: { t: 'str', enumSet: ENUM_SETS.sslBin },
    max_ssl_size_mm: { t: 'float', nullable: true, min: 0, max: 250 },
    any_ssl_with_dysplasia_or_tsa: { t: 'str', enumSet: ENUM_SETS.tristate },
    any_invasive_cancer_or_noncurative_feature: { t: 'str', enumSet: ENUM_SETS.tristate }
  };

  const SCHEMA_ERCP_LABS = {
    bili_total_mg_dl: { t: 'float', nullable: true },
    bili_direct_mg_dl: { t: 'float', nullable: true },
    ast_u_l: { t: 'float', nullable: true },
    alt_u_l: { t: 'float', nullable: true },
    ggt_u_l: { t: 'float', nullable: true },
    alp_u_l: { t: 'float', nullable: true },
    amylase_u_l: { t: 'float', nullable: true },
    lipase_u_l: { t: 'float', nullable: true },
    wbc_g_l: { t: 'float', nullable: true },
    crp_mg_l: { t: 'float', nullable: true },
    plt_g_l: { t: 'float', nullable: true },
    inr: { t: 'float', nullable: true }
  };

  const SCHEMA_ERCP_DETAIL = {
    history_flags: { t: 'str_list' },
    altered_anatomy: { t: 'str', enumSet: ENUM_SETS.altAnat },
    antithrombotic_status: { t: 'str' },
    imaging_modality: { t: 'str' },
    imaging_cbd_mm: { t: 'float', nullable: true, min: 0, max: 60 },
    imaging_stone_count: { t: 'int', min: 0, max: 50 },
    imaging_stone_max_mm: { t: 'float', nullable: true, min: 0, max: 60 },
    stricture_site: { t: 'str' },
    labs: { t: 'obj', schema: SCHEMA_ERCP_LABS },
    papilla_status: { t: 'str', enumSet: ENUM_SETS.papilla },
    duodenal_obstruction_or_altered: { t: 'bool' },
    vater_papilla_type: { t: 'str', enumSet: ENUM_SETS.vater },
    pad_diverticulum: { t: 'bool' },
    target_duct: { t: 'str', enumSet: ENUM_SETS.duct },
    selective_cannulation: { t: 'str', enumSet: ENUM_SETS.cannSel },
    cannulation_contacts_count: { t: 'int', min: 0, max: 50 },
    cannulation_time_min: { t: 'float', min: 0, max: 240 },
    total_procedure_time_min: { t: 'float', min: 0, max: 480 },
    unintended_pd_count: { t: 'int', min: 0, max: 20 },
    cannulation_technique: { t: 'str' },
    biliary_interventions: { t: 'str_list' },
    pep_prophylaxis: { t: 'str_list' },
    ercp_procedure_note: { t: 'str' }
  };

  const SCHEMA_ADVERSE_EVENT = {
    ae_id: { t: 'str', req: true, minLen: 1, trim: true },
    window: { t: 'str', enumSet: ENUM_SETS.aeWin },
    event_type: { t: 'str', enumSet: ENUM_SETS.aeType },
    pep_severity: { t: 'str', enumSet: ENUM_SETS.pepSev },
    agree_grade: { t: 'str', enumSet: ENUM_SETS.agree },
    readmission_required: { t: 'bool' },
    surgical_rescue_required: { t: 'bool' },
    note: { t: 'str' }
  };

  const SCHEMA_CASE_CREATE = {
    patient_uid: { t: 'str', nullable: true },
    confirm_outpatient_new_patient: { t: 'bool' },
    full_name: { t: 'str', req: true, minLen: 2, maxLen: 120, trim: true },
    birth_year: { t: 'int', req: true, min: 1900, max: 2026 },
    sex: { t: 'str', enumSet: ENUM_SETS.sex },
    hospital_mrn: { t: 'str', nullable: true, maxLen: 40 },
    care_setting: { t: 'str', enumSet: ENUM_SETS.care },
    episode_id: { t: 'str', nullable: true },
    admission_date: { t: 'str', nullable: true, minLen: 10, maxLen: 10, trim: true, isoDate: true },
    referring_dept: { t: 'str' },
    prior_unrecorded_ercp_offset: { t: 'int', min: 0, max: 20 },
    track: { t: 'str', req: true, enumSet: ENUM_SETS.track },
    procedure_start_at: { t: 'str', req: true, minLen: 10, maxLen: 64, trim: true, isoTimestamp: true },
    operator_name: { t: 'str', minLen: 2, maxLen: 120, trim: true },
    indication: { t: 'str', enumSet: ENUM_SETS.indication },
    indication_detail: { t: 'str' },
    has_ibd_or_polyposis: { t: 'bool' },
    exclude_from_cir: { t: 'bool' },
    bbps_right: { t: 'int', nullable: true, min: 0, max: 3 },
    bbps_transverse: { t: 'int', nullable: true, min: 0, max: 3 },
    bbps_left: { t: 'int', nullable: true, min: 0, max: 3 },
    cecal_intubation: { t: 'str', enumSet: ENUM_SETS.cecal },
    cecal_failure_reason: { t: 'str' },
    withdrawal_time_clean_min: { t: 'float', nullable: true, min: 0, max: 180 },
    pathology_completion_status: { t: 'str', enumSet: ENUM_SETS.pathology },
    followup_30d_status: { t: 'str', enumSet: ENUM_SETS.fu30 },
    clinician_followup_due_date: { t: 'str', nullable: true, minLen: 10, maxLen: 10, trim: true, isoDate: true },
    clinician_followup_note: { t: 'str' },
    index_lesion: { t: 'obj', nullable: true, schema: SCHEMA_INDEX_LESION },
    whole_case_summary: { t: 'obj', nullable: true, schema: SCHEMA_WHOLE_CASE },
    ercp_detail: { t: 'obj', nullable: true, schema: SCHEMA_ERCP_DETAIL },
    adverse_events: { t: 'obj_list', schema: SCHEMA_ADVERSE_EVENT },
    clinical_note: { t: 'str' },
    fulfill_surveillance_rec_id: { t: 'str', nullable: true }
  };

  const SCHEMA_CASE_PATCH = {
    expected_version: { t: 'int', req: true, min: 1 },
    expected_store_epoch: { t: 'int', nullable: true, min: 1 },
    procedure_start_at: { t: 'str', nullable: true, minLen: 10, maxLen: 64, trim: true, isoTimestamp: true },
    operator_name: { t: 'str', nullable: true, minLen: 2, maxLen: 120, trim: true },
    referring_dept: { t: 'str', nullable: true },
    prior_unrecorded_ercp_offset: { t: 'int', nullable: true, min: 0, max: 20 },
    indication: { t: 'str', nullable: true, enumSet: ENUM_SETS.indication },
    indication_detail: { t: 'str', nullable: true },
    has_ibd_or_polyposis: { t: 'bool', nullable: true },
    exclude_from_cir: { t: 'bool', nullable: true },
    pathology_completion_status: { t: 'str', nullable: true, enumSet: ENUM_SETS.pathology },
    followup_30d_status: { t: 'str', nullable: true, enumSet: ENUM_SETS.fu30 },
    clinician_followup_due_date: { t: 'str', nullable: true, minLen: 10, maxLen: 10, trim: true, isoDate: true },
    clinician_followup_note: { t: 'str', nullable: true },
    bbps_right: { t: 'int', nullable: true, min: 0, max: 3 },
    bbps_transverse: { t: 'int', nullable: true, min: 0, max: 3 },
    bbps_left: { t: 'int', nullable: true, min: 0, max: 3 },
    cecal_intubation: { t: 'str', nullable: true, enumSet: ENUM_SETS.cecal },
    cecal_failure_reason: { t: 'str', nullable: true },
    withdrawal_time_clean_min: { t: 'float', nullable: true, min: 0, max: 180 },
    index_lesion: { t: 'obj', nullable: true, schema: SCHEMA_INDEX_LESION },
    whole_case_summary: { t: 'obj', nullable: true, schema: SCHEMA_WHOLE_CASE },
    ercp_detail: { t: 'obj', nullable: true, schema: SCHEMA_ERCP_DETAIL },
    adverse_events: { t: 'obj_list', nullable: true, schema: SCHEMA_ADVERSE_EVENT },
    clinical_note: { t: 'str', nullable: true },
    fulfill_surveillance_rec_id: { t: 'str', nullable: true }
  };

  const SCHEMA_PATIENT_MERGE = {
    source_patient_uid: { t: 'str', req: true, minLen: 4, maxLen: 80, trim: true },
    target_patient_uid: { t: 'str', req: true, minLen: 4, maxLen: 80, trim: true },
    expected_store_epoch: { t: 'int', req: true, min: 1 },
    source_expected_version: { t: 'int', req: true, min: 1 },
    target_expected_version: { t: 'int', req: true, min: 1 },
    expected_source_case_ids: { t: 'str_list' },
    confirm_demographic_conflict: { t: 'bool' },
    resolved_full_name: { t: 'str', nullable: true, minLen: 2, maxLen: 120, trim: true },
    resolved_birth_year: { t: 'int', nullable: true, min: 1900, max: 2026 },
    resolved_sex: { t: 'str', nullable: true, enumSet: ENUM_SETS.sex },
    confirm_distinct_mrn_override: { t: 'bool' },
    primary_mrn_choice: { t: 'str', enumSet: ENUM_SETS.mrnChoice },
    reason: { t: 'str', minLen: 3, maxLen: 300, trim: true }
  };

  const SCHEMA_EPISODE_RECONCILE = {
    patient_uid: { t: 'str', req: true, minLen: 4, maxLen: 80, trim: true },
    source_episode_id: { t: 'str', req: true, minLen: 4, maxLen: 80, trim: true },
    target_episode_id: { t: 'str', req: true, minLen: 4, maxLen: 80, trim: true },
    expected_store_epoch: { t: 'int', req: true, min: 1 },
    expected_case_ids: { t: 'str_list' },
    resolved_prior_unrecorded_ercp_offset: { t: 'int', req: true, min: 0, max: 20 },
    reason: { t: 'str', minLen: 3, maxLen: 300, trim: true }
  };

  const SCHEMA_SETTINGS_PATCH = {
    colo_guideline_mode: { t: 'str', nullable: true },
    adr_min_age: { t: 'int', nullable: true },
    cusum_preset: { t: 'str', nullable: true },
    kpi_min_sample_size: { t: 'int', nullable: true, min: 1, max: 500 }
  };

  function normalizeIndexLesion(raw) {
    if (!raw || typeof raw !== 'object') return null;
    return {
      anatomical_site: raw.anatomical_site !== undefined ? String(raw.anatomical_site) : '',
      size_mm: raw.size_mm !== undefined && raw.size_mm !== null ? Number(raw.size_mm) : null,
      paris_class: raw.paris_class !== undefined ? String(raw.paris_class) : '',
      surface_pattern: raw.surface_pattern !== undefined ? String(raw.surface_pattern) : '',
      bleeding_source_type: raw.bleeding_source_type || 'NONE',
      forrest_class: raw.forrest_class !== undefined ? String(raw.forrest_class) : '',
      hemostasis_modality: raw.hemostasis_modality !== undefined ? String(raw.hemostasis_modality) : '',
      hemostasis_initial_success: raw.hemostasis_initial_success || 'NA',
      biopsy_jar_count: raw.biopsy_jar_count !== undefined ? Number(raw.biopsy_jar_count) : 0,
      resection_method: raw.resection_method || 'NONE',
      histology_type: raw.histology_type || 'NONE',
      dysplasia_grade: raw.dysplasia_grade || 'NONE',
      margins_status: raw.margins_status || 'NA',
      sm_invasion_um: raw.sm_invasion_um !== undefined && raw.sm_invasion_um !== null ? Number(raw.sm_invasion_um) : null,
      lvi_status: raw.lvi_status || 'NA',
      differentiation: raw.differentiation || 'NA',
      budding_grade: raw.budding_grade || 'NA'
    };
  }

  function normalizeWholeCaseSummary(raw) {
    const r = (raw && typeof raw === 'object') ? raw : {};
    return {
      macroscopic_polyp_count: r.macroscopic_polyp_count !== undefined ? Number(r.macroscopic_polyp_count) : 0,
      complete_resection_all_lesions: r.complete_resection_all_lesions || 'NOT_APPLICABLE',
      any_piecemeal_ge_20mm: r.any_piecemeal_ge_20mm || 'NO',
      any_confirmed_adenoma: r.any_confirmed_adenoma || 'NO',
      confirmed_adenoma_count_bin: r.confirmed_adenoma_count_bin || '0',
      max_adenoma_size_mm: r.max_adenoma_size_mm !== undefined && r.max_adenoma_size_mm !== null ? Number(r.max_adenoma_size_mm) : null,
      any_villous_or_hgd_any_lesion: r.any_villous_or_hgd_any_lesion || 'NO',
      any_hgd_any_lesion: r.any_hgd_any_lesion || 'NO',
      any_confirmed_ssl: r.any_confirmed_ssl || 'NO',
      confirmed_ssl_count_bin: r.confirmed_ssl_count_bin || '0',
      max_ssl_size_mm: r.max_ssl_size_mm !== undefined && r.max_ssl_size_mm !== null ? Number(r.max_ssl_size_mm) : null,
      any_ssl_with_dysplasia_or_tsa: r.any_ssl_with_dysplasia_or_tsa || 'NO',
      any_invasive_cancer_or_noncurative_feature: r.any_invasive_cancer_or_noncurative_feature || 'NO'
    };
  }

  function normalizeErcpDetail(raw) {
    const r = (raw && typeof raw === 'object') ? raw : {};
    const lb = (r.labs && typeof r.labs === 'object') ? r.labs : {};
    function optNum(v) { return v !== undefined && v !== null ? Number(v) : null; }
    return {
      history_flags: Array.isArray(r.history_flags) ? r.history_flags.map(String) : [],
      altered_anatomy: r.altered_anatomy || 'NONE',
      antithrombotic_status: r.antithrombotic_status !== undefined ? String(r.antithrombotic_status) : 'NONE',
      imaging_modality: r.imaging_modality !== undefined ? String(r.imaging_modality) : 'MRCP',
      imaging_cbd_mm: optNum(r.imaging_cbd_mm),
      imaging_stone_count: r.imaging_stone_count !== undefined ? Number(r.imaging_stone_count) : 0,
      imaging_stone_max_mm: optNum(r.imaging_stone_max_mm),
      stricture_site: r.stricture_site !== undefined ? String(r.stricture_site) : '',
      labs: {
        bili_total_mg_dl: optNum(lb.bili_total_mg_dl),
        bili_direct_mg_dl: optNum(lb.bili_direct_mg_dl),
        ast_u_l: optNum(lb.ast_u_l),
        alt_u_l: optNum(lb.alt_u_l),
        ggt_u_l: optNum(lb.ggt_u_l),
        alp_u_l: optNum(lb.alp_u_l),
        amylase_u_l: optNum(lb.amylase_u_l),
        lipase_u_l: optNum(lb.lipase_u_l),
        wbc_g_l: optNum(lb.wbc_g_l),
        crp_mg_l: optNum(lb.crp_mg_l),
        plt_g_l: optNum(lb.plt_g_l),
        inr: optNum(lb.inr)
      },
      papilla_status: r.papilla_status || 'NATIVE_INTACT',
      duodenal_obstruction_or_altered: Boolean(r.duodenal_obstruction_or_altered),
      vater_papilla_type: r.vater_papilla_type || '1',
      pad_diverticulum: Boolean(r.pad_diverticulum),
      target_duct: r.target_duct || 'CBD',
      selective_cannulation: r.selective_cannulation || 'SUCCESS',
      cannulation_contacts_count: r.cannulation_contacts_count !== undefined ? Number(r.cannulation_contacts_count) : 1,
      cannulation_time_min: r.cannulation_time_min !== undefined ? Number(r.cannulation_time_min) : 2.0,
      total_procedure_time_min: r.total_procedure_time_min !== undefined ? Number(r.total_procedure_time_min) : 25.0,
      unintended_pd_count: r.unintended_pd_count !== undefined ? Number(r.unintended_pd_count) : 0,
      cannulation_technique: r.cannulation_technique || 'STANDARD_SPHINCTEROTOME_GUIDEWIRE',
      biliary_interventions: Array.isArray(r.biliary_interventions) ? r.biliary_interventions.map(String) : [],
      pep_prophylaxis: Array.isArray(r.pep_prophylaxis) ? r.pep_prophylaxis.map(String) : [],
      ercp_procedure_note: r.ercp_procedure_note !== undefined ? String(r.ercp_procedure_note) : ''
    };
  }

  function normalizeAdverseEvent(raw) {
    const r = raw || {};
    return {
      ae_id: String(r.ae_id || ('ae_' + Date.now())),
      window: r.window || 'INPATIENT_EARLY',
      event_type: r.event_type || 'OTHER',
      pep_severity: r.pep_severity || 'NONE',
      agree_grade: r.agree_grade || 'I',
      readmission_required: Boolean(r.readmission_required),
      surgical_rescue_required: Boolean(r.surgical_rescue_required),
      note: r.note !== undefined ? String(r.note) : ''
    };
  }

  function sanitizeUser(u) {
    return {
      username: u.username,
      display_name: u.display_name,
      role: u.role,
      department: u.department,
      active: u.active !== false,
      auth_version: Number(u.auth_version || 1),
      created_at: u.created_at || null,
      password_updated_at: u.password_updated_at || null
    };
  }

  function enrichCaseRecord(c, state, precomputedErcpMap) {
    const storeEpoch = Number(state.store_epoch || 1);
    const pat = (state.patients && state.patients[c.patient_uid]) || {};
    const epi = (state.episodes && state.episodes[c.episode_id]) || {};
    const ercpMap = precomputedErcpMap || computeErcpSessionIndices(
      Object.values(state.cases || {}).filter(function (x) { return (x.record_status || 'ACTIVE') === 'ACTIVE'; }),
      state.episodes
    );

    const segs = extractBbpsSegments(c);
    const bbpsInfo = segs
      ? evaluateBbps(segs[0], segs[1], segs[2], c.cecal_intubation || 'NA')
      : { evaluable: false, segments: null, total: null, adequate: false };
    const aeInfo = summarizeCaseAdverseEvents(c);
    const primaryMode = (state.settings && state.settings.colo_guideline_mode) || 'USMSTF_2020';
    const surv = buildSurveillanceRecommendation(c, primaryMode);
    const storedSurv = (state.surveillance && state.surveillance[c.case_id]) || {};
    if (storedSurv.fulfilled_by_case_id) {
      surv.fulfilled_by_case_id = storedSurv.fulfilled_by_case_id;
      surv.status = 'COMPLETED_LINKED';
    }
    surv.rec_id = storedSurv.rec_id || ('rec_' + c.case_id);

    let ercpExtra = null;
    if (c.track === 'ERCP' && c.ercp_detail) {
      const det = c.ercp_detail;
      const diff = isDifficultCannulationEsge2016(
        det.papilla_status || 'NATIVE_INTACT',
        Number(det.cannulation_contacts_count || 0),
        Number(det.cannulation_time_min || 0),
        Number(det.unintended_pd_count || 0)
      );
      ercpExtra = Object.assign({}, deepClone(det), {
        difficult_cannulation_esge2016: diff,
        ercp_session_index_in_episode: ercpMap[c.case_id] || 1
      });
    }

    const procYear = Number(String(c.procedure_start_at || '2026').slice(0, 4));
    const birthYear = Number(pat.birth_year || procYear);
    const age = Math.max(0, procYear - birthYear);

    const pepSevVi = { MILD: 'mức nhẹ', MODERATE: 'mức vừa', SEVERE: 'mức nặng' };
    const hasRecordedAe = Boolean(
      aeInfo.is_agree_any ||
      aeInfo.has_pep ||
      aeInfo.followup_30d_status === 'COMPLETED_WITH_AE'
    );
    let badgeTone = 'ned';
    let badgeLabel = 'Không biến cố / hoàn tất';
    if (surv.category === 'SURGICAL_MDT_CONSULT_ALERT' || hasRecordedAe) {
      badgeTone = 'urgent';
      if (surv.category === 'SURGICAL_MDT_CONSULT_ALERT') {
        badgeLabel = 'Cảnh báo hội chẩn ' + surv.surgical_consult_target_dept;
      } else if (aeInfo.highest_agree_grade !== 'NONE') {
        if (aeInfo.has_pep) {
          const pTxt = pepSevVi[String(aeInfo.highest_pep_severity)] || 'ghi nhận';
          badgeLabel = 'Viêm tụy sau ERCP ' + pTxt + ' · AGREE ' + aeInfo.highest_agree_grade;
        } else {
          badgeLabel = 'Biến cố AGREE ' + aeInfo.highest_agree_grade;
        }
      } else if (aeInfo.has_pep) {
        const pTxt2 = pepSevVi[String(aeInfo.highest_pep_severity)] || 'ghi nhận';
        badgeLabel = 'Viêm tụy sau ERCP ' + pTxt2 + ' (chưa phân độ AGREE)';
      } else {
        badgeLabel = 'Có biến cố sau thủ thuật (chưa phân độ AGREE)';
      }
    } else if (c.pathology_completion_status === 'PENDING' || c.pathology_completion_status === 'PARTIAL') {
      badgeTone = 'pending';
      badgeLabel = 'Chờ GPB';
    } else if (aeInfo.followup_30d_status === 'PENDING_WINDOW') {
      badgeTone = 'due';
      badgeLabel = 'Theo dõi 14–30 ngày';
    } else if (aeInfo.followup_30d_status === 'LOST_TO_FOLLOWUP') {
      badgeTone = 'neutral';
      badgeLabel = 'Mất dấu theo dõi';
    }

    return Object.assign({}, deepClone(c), {
      store_epoch: storeEpoch,
      etag: 'W/"e' + storeEpoch + ':v' + c.version + '"',
      patient: {
        patient_uid: pat.patient_uid || null,
        full_name: pat.full_name || null,
        privacy_initials: pat.privacy_initials || null,
        birth_year: birthYear,
        age: age,
        sex: pat.sex || null,
        hospital_mrn_masked: pat.hospital_mrn_masked || null
      },
      episode: {
        episode_id: epi.episode_id || null,
        care_setting: epi.care_setting || null,
        admission_date: epi.admission_date || null,
        referring_dept: epi.referring_dept || null,
        prior_unrecorded_ercp_offset: epi.prior_unrecorded_ercp_offset !== undefined
          ? epi.prior_unrecorded_ercp_offset
          : (c.prior_unrecorded_ercp_offset || 0)
      },
      bbps: bbpsInfo,
      adverse_summary: aeInfo,
      ercp_computed: ercpExtra,
      surveillance: surv,
      clinical_badge: { tone: badgeTone, label: badgeLabel }
    });
  }

  function listEnrichedCasesFromState(state, trackFilter) {
    const activeCases = Object.values(state.cases || {}).filter(function (c) {
      return (c.record_status || 'ACTIVE') === 'ACTIVE';
    });
    const ercpMap = computeErcpSessionIndices(activeCases, state.episodes);
    const out = [];
    for (let i = 0; i < activeCases.length; i += 1) {
      const c = activeCases[i];
      if (trackFilter && trackFilter !== 'ALL' && c.track !== trackFilter) continue;
      out.push(enrichCaseRecord(c, state, ercpMap));
    }
    out.sort(function (a, b) {
      const pCmp = String(b.procedure_start_at || '').localeCompare(String(a.procedure_start_at || ''));
      if (pCmp !== 0) return pCmp;
      return String(b.case_code || '').localeCompare(String(a.case_code || ''));
    });
    return out;
  }

  function exportProfileBRowsFromState(state, researchMaterial, shiftMaterial, scopeId, trackFilter) {
    const cfg = state.settings || {};
    const dsEpoch = Math.max(1, Number(cfg.export_dataset_epoch || 1));
    const lineageSeq = Math.max(1, Number(cfg.profile_b_lineage_seq || 1));
    const allCases = Object.values(state.cases || {}).filter(function (c) {
      return (c.record_status || 'ACTIVE') === 'ACTIVE';
    });
    const ercpIdx = computeErcpSessionIndices(allCases, state.episodes);
    const filtered = allCases.filter(function (c) {
      return !trackFilter || c.track === trackFilter;
    }).sort(function (a, b) {
      const pCmp = String(a.procedure_start_at || '').localeCompare(String(b.procedure_start_at || ''));
      if (pCmp !== 0) return pCmp;
      return String(a.case_code || '').localeCompare(String(b.case_code || ''));
    });

    return filtered.map(function (c) {
      const pUid = c.patient_uid;
      const epId = c.episode_id || c.case_id;
      const pat = (state.patients && state.patients[pUid]) || {};
      const researchSubjectId = hmacSha256Hex(researchMaterial, 'endolog_v1:' + scopeId + ':' + pUid).slice(0, 24);
      const researchEpisodeId = hmacSha256Hex(researchMaterial, 'endolog_v1:' + scopeId + ':' + epId).slice(0, 24);
      const shiftHex = hmacSha256Hex(shiftMaterial, researchSubjectId);
      const deltaDays = Number((BigInt('0x' + shiftHex.slice(0, 16)) % 61n) - 30n);
      const procDate = String(c.procedure_start_at).slice(0, 10);
      const shiftedDate = addCalendarDaysIso(procDate, deltaDays);
      const procYear = Number(procDate.slice(0, 4));
      const rawAge = c.age !== undefined && c.age !== null
        ? Number(c.age)
        : Math.max(0, procYear - Number(pat.birth_year || procYear));
      const ageCapped = rawAge >= 90 ? '90+' : String(Math.trunc(rawAge));
      const sex = c.sex || pat.sex || 'O';

      const segs = extractBbpsSegments(c);
      const bbpsRes = segs
        ? evaluateBbps(segs[0], segs[1], segs[2], c.cecal_intubation || 'NA')
        : { total: null, adequate: false };
      const ae = summarizeCaseAdverseEvents(c);
      const idx = c.index_lesion || {};
      const wc = c.whole_case_summary || {};
      const ercpDet = c.ercp_detail || {};

      return {
        research_subject_id: researchSubjectId,
        research_episode_id: researchEpisodeId,
        case_code: c.case_code,
        track: c.track,
        care_setting: c.care_setting || 'OUTPATIENT',
        shifted_procedure_date: shiftedDate,
        age_years_capped: ageCapped,
        sex: sex,
        indication: c.indication || '',
        cecal_intubation: c.cecal_intubation || 'NA',
        bbps_total: bbpsRes.total,
        bbps_adequate: bbpsRes.adequate ? 'YES' : (segs ? 'NO' : 'NA'),
        macroscopic_polyp_count: wc.macroscopic_polyp_count !== undefined ? wc.macroscopic_polyp_count : null,
        any_confirmed_adenoma: wc.any_confirmed_adenoma !== undefined ? wc.any_confirmed_adenoma : null,
        any_confirmed_ssl: wc.any_confirmed_ssl !== undefined ? wc.any_confirmed_ssl : null,
        index_lesion_site: idx.anatomical_site || '',
        index_lesion_size_mm: (idx.size_mm !== undefined && idx.size_mm !== null)
          ? (Number.isInteger(Number(idx.size_mm)) ? (String(Number(idx.size_mm)) + '.0') : String(Number(idx.size_mm)))
          : null,
        index_lesion_resection: idx.resection_method || 'NONE',
        index_lesion_histology: idx.histology_type || 'NONE',
        pathology_completion_status: c.pathology_completion_status || 'NOT_APPLICABLE',
        ercp_session_in_episode: c.track === 'ERCP' ? (ercpIdx[c.case_id] || null) : null,
        ercp_papilla_status: c.track === 'ERCP' ? (ercpDet.papilla_status || null) : null,
        ercp_selective_cannulation: c.track === 'ERCP' ? (ercpDet.selective_cannulation || null) : null,
        followup_30d_status: ae.followup_30d_status,
        highest_agree_grade: ae.highest_agree_grade,
        highest_pep_severity: ae.highest_pep_severity,
        export_dataset_epoch: dsEpoch,
        profile_b_lineage_seq: lineageSeq
      };
    });
  }

  function csvEscapeCell(val) {
    if (val === null || val === undefined) return '';
    const s = String(val);
    if (/[",\r\n]/.test(s)) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function rowsToCsvTextWithBom(rows) {
    if (!rows || !rows.length) return '';
    const headers = Object.keys(rows[0]);
    const lines = [headers.map(csvEscapeCell).join(',')];
    for (let i = 0; i < rows.length; i += 1) {
      const row = rows[i];
      lines.push(headers.map(function (h) { return csvEscapeCell(row[h]); }).join(','));
    }
    return '\uFEFF' + lines.join('\r\n') + '\r\n';
  }

  function maskSmallCell(count, suppress) {
    if (suppress && count > 0 && count < 5) return '<5';
    return count;
  }

  function exportProfileCSummaryFromState(state, minAdrAge, suppressSmallCells) {
    const casesList = Object.values(state.cases || {});
    const nMinCfg = Number((state.settings && state.settings.kpi_min_sample_size) || 20);
    const kpi = computeKpiSnapshot(casesList, state.patients || {}, minAdrAge, nMinCfg);
    const defs = [
      ['cir', 'Tỷ lệ luồn tới manh tràng (CIR)'],
      ['bbps_adequate', 'Tỷ lệ chuẩn bị đại tràng đạt (BBPS ≥ 6 & mỗi đoạn ≥ 2)'],
      ['pdr', 'Tỷ lệ phát hiện polyp đại thể (PDR ≥ ' + minAdrAge + ' tuổi)'],
      ['adr', 'Tỷ lệ phát hiện u tuyến (ADR ≥ ' + minAdrAge + ' tuổi, đã có GPB)'],
      ['ssldr', 'Tỷ lệ phát hiện polyp răng cưa không cuống (SSLDR ≥ ' + minAdrAge + ' tuổi)'],
      ['ercp_native_cannulation', 'Tỷ lệ thông nhú chọn lọc trên nhú Vater nguyên vẹn (ERCP)'],
      ['ercp_pep', 'Tỷ lệ viêm tụy cấp sau ERCP trên ca hoàn tất theo dõi']
    ];
    const metricsRows = defs.map(function (pair) {
      const k = pair[0];
      const label = pair[1];
      const blk = kpi[k];
      const num = Number(blk.numerator);
      const den = Number(blk.denominator !== undefined ? blk.denominator : (blk.completed_fu_denominator || 0));
      const rate = (suppressSmallCells && ((num > 0 && num < 5) || (den > 0 && den < 5))) ? null : blk.rate_pct;
      return {
        metric_code: k,
        metric_label_vi: label,
        numerator: maskSmallCell(num, suppressSmallCells),
        denominator: maskSmallCell(den, suppressSmallCells),
        rate_pct: rate
      };
    });
    return {
      contract: 'EndoLog-Export-Profile-C-v1.0',
      suppress_small_cells_k_lt_5: Boolean(suppressSmallCells),
      min_adr_age: minAdrAge,
      total_active_cases: maskSmallCell(kpi.total_active_cases, suppressSmallCells),
      metrics: metricsRows
    };
  }

  function parseIfMatchHeader(rawIfMatch, expectedVersion) {
    const cleaned = String(rawIfMatch || '').trim();
    if (!cleaned || cleaned === '*') return { epoch: null, version: null, error: null };
    const mNew = cleaned.match(/^(?:W\/)?"?e(\d+):v(\d+)"?$/);
    if (mNew) {
      const hdrEpoch = Number(mNew[1]);
      const hdrVer = Number(mNew[2]);
      if (expectedVersion !== null && expectedVersion !== undefined && hdrVer !== Number(expectedVersion)) {
        return {
          epoch: null,
          version: null,
          error: {
            code: 'OCC_VERSION_CONFLICT',
            message: 'Header If-Match (' + cleaned + ') không khớp với expected_version (v' + expectedVersion + ').'
          }
        };
      }
      return { epoch: hdrEpoch, version: hdrVer, error: null };
    }
    const mLegacy = cleaned.match(/^(?:W\/)?"?v?(\d+)"?$/);
    if (!mLegacy) {
      return {
        epoch: null,
        version: null,
        error: {
          code: 'OCC_VERSION_CONFLICT',
          message: 'Định dạng header If-Match (' + cleaned + ') không hợp lệ.'
        }
      };
    }
    const verLegacy = Number(mLegacy[1]);
    if (expectedVersion !== null && expectedVersion !== undefined && verLegacy !== Number(expectedVersion)) {
      return {
        epoch: null,
        version: null,
        error: {
          code: 'OCC_VERSION_CONFLICT',
          message: 'Header If-Match (' + cleaned + ') không khớp với expected_version (v' + expectedVersion + ').'
        }
      };
    }
    return { epoch: 1, version: verLegacy, error: null };
  }

  function createSyntheticRamEngine(bundle, options) {
    const opts = options || {};
    const DEFAULT_RESEARCH_MATERIAL = ['endolog', 'local', 'dev', 'only', 'research', 'hmac', 'key', '32bytes'].join('-');
    const DEFAULT_SHIFT_MATERIAL = ['endolog', 'local', 'dev', 'only', 'date', 'shift', 'hmac', 'key', '32b'].join('-');
    const researchMaterial = opts.researchMaterial || DEFAULT_RESEARCH_MATERIAL;
    const shiftMaterial = opts.shiftMaterial || DEFAULT_SHIFT_MATERIAL;

    let activePersonaKey = opts.initialPersonaKey !== undefined ? opts.initialPersonaKey : 'nguyenbinhan';
    let uidSeq = 1;
    let ramStore = null;
    let cleanSeedSnapshot = null;
    let virtualBackupFiles = {};
    const allowedSyntheticNames = new Set();

    function mrnHmac(rawMrn) {
      return hmacSha256Hex(researchMaterial, 'mrn:' + String(rawMrn).trim().toUpperCase());
    }

    function nextUid(prefix) {
      if (typeof opts.uidProvider === 'function') {
        return opts.uidProvider(prefix, uidSeq++);
      }
      const msHex = Date.now().toString(16).padStart(12, '0');
      const seqHex = (uidSeq++).toString(16).padStart(8, '0');
      return prefix + '_' + msHex + seqHex;
    }

    function currentUtcIso() {
      if (typeof opts.nowIsoProvider === 'function') {
        return nowUtcNoMicrosIso(opts.nowIsoProvider());
      }
      return nowUtcNoMicrosIso();
    }

    function currentLocalDateIso() {
      if (typeof opts.todayIsoProvider === 'function') {
        return String(opts.todayIsoProvider()).slice(0, 10);
      }
      return localDateIso();
    }

    function hydrateStoreHashes(rawState) {
      const cloned = deepClone(rawState);
      cloned.store_epoch = Number(cloned.store_epoch || 1);
      cloned.audit_lineage_bridges = Array.isArray(cloned.audit_lineage_bridges) ? cloned.audit_lineage_bridges : [];
      cloned.patients = cloned.patients || {};
      cloned.episodes = cloned.episodes || {};
      cloned.cases = cloned.cases || {};
      cloned.surveillance = cloned.surveillance || {};
      cloned.counters = cloned.counters || {};
      cloned.users = cloned.users || {};
      cloned.settings = Object.assign({
        colo_guideline_mode: 'USMSTF_2020',
        adr_min_age: 45,
        cusum_preset: 'DEFAULT_90',
        kpi_min_sample_size: 20,
        export_dataset_epoch: 1,
        profile_b_lineage_seq: 1
      }, cloned.settings || {});

      Object.values(cloned.patients).forEach(function (p) {
        const rawMrn = String(p.hospital_mrn || '').trim();
        if (rawMrn) {
          p.hospital_mrn = rawMrn;
          p.hospital_mrn_masked = maskMrn(rawMrn);
          p.hospital_mrn_hash = mrnHmac(rawMrn);
        } else {
          p.hospital_mrn = null;
          p.hospital_mrn_masked = null;
          p.hospital_mrn_hash = null;
        }
        const secMrns = Array.isArray(p.secondary_mrns) ? p.secondary_mrns : [];
        p.secondary_mrns = secMrns.map(function (m) { return String(m).trim(); }).filter(Boolean);
        p.secondary_mrn_hashes = p.secondary_mrns.map(mrnHmac);
        p.merged_from_aliases = Array.isArray(p.merged_from_aliases) ? p.merged_from_aliases : [];
        p.status = p.status || 'ACTIVE';
        p.version = Number(p.version || 1);
        if (p.full_name) allowedSyntheticNames.add(normalizeName(p.full_name));
      });
      return cloned;
    }

    (bundle.synthetic_patient_catalog || []).forEach(function (item) {
      if (item && item.full_name) allowedSyntheticNames.add(normalizeName(item.full_name));
    });
    const allowedOperatorNames = new Set([
      normalizeName('ThS. BSCKI. Nguyễn Bình An'),
      normalizeName('BSCKII. Vũ Khương An')
    ]);
    if (bundle.initial_ram_store && bundle.initial_ram_store.users) {
      Object.values(bundle.initial_ram_store.users).forEach(function (u) {
        if (u && u.display_name) allowedOperatorNames.add(normalizeName(u.display_name));
      });
    }

    function resetToInitialOd05() {
      ramStore = hydrateStoreHashes(bundle.initial_ram_store);
      cleanSeedSnapshot = deepClone(ramStore);
      virtualBackupFiles = {};
      return {
        store_epoch: ramStore.store_epoch,
        active_cases: Object.values(ramStore.cases).filter(function (c) { return (c.record_status || 'ACTIVE') === 'ACTIVE'; }).length
      };
    }

    resetToInitialOd05();

    function findActivePatientByMrnHash(patientsMap, targetHash) {
      const keys = Object.keys(patientsMap);
      for (let i = 0; i < keys.length; i += 1) {
        const uid = keys[i];
        const p = patientsMap[uid];
        if ((p.status || 'ACTIVE') !== 'ACTIVE') continue;
        if (p.hospital_mrn_hash === targetHash || (Array.isArray(p.secondary_mrn_hashes) && p.secondary_mrn_hashes.indexOf(targetHash) !== -1)) {
          return uid;
        }
      }
      return null;
    }

    function getActiveUser() {
      if (!activePersonaKey) return null;
      const u = ramStore.users && ramStore.users[activePersonaKey];
      if (!u || u.active === false) return null;
      return u;
    }

    function makeResult(status, body, headers, isRawText) {
      return {
        status: status,
        headers: Object.assign({ 'Cache-Control': 'no-store' }, headers || {}),
        body: body,
        isRawText: Boolean(isRawText)
      };
    }

    function handleRequest(methodRaw, rawPathWithQuery, rawHeaders, rawBody) {
      const method = String(methodRaw || 'GET').toUpperCase();
      const parsedUrl = new URL(rawPathWithQuery, 'https://endolog-sandbox.local');
      const path = parsedUrl.pathname;
      const params = parsedUrl.searchParams;
      const headers = {};
      if (rawHeaders && typeof rawHeaders === 'object') {
        Object.keys(rawHeaders).forEach(function (k) {
          headers[k.toLowerCase()] = String(rawHeaders[k]);
        });
      }

      let bodyObj = null;
      if (rawBody !== undefined && rawBody !== null && rawBody !== '') {
        if (typeof rawBody === 'string') {
          try {
            bodyObj = JSON.parse(rawBody);
          } catch (_err) {
            return makeResult(422, { detail: { code: 'INVALID_JSON', message: 'Nội dung JSON không hợp lệ.' } });
          }
        } else if (typeof rawBody === 'object') {
          bodyObj = deepClone(rawBody);
        }
      }

      /* 1. Public / Auth endpoints */
      if (method === 'GET' && path === '/api/health') {
        return makeResult(200, {
          status: 'ok',
          version: bundle.version,
          env_mode: 'gh_pages_static_demo',
          local_bypass_candidate: true,
          static_demo: true,
          interactive_ram_sandbox: true
        });
      }

      if (method === 'GET' && path === '/api/auth/me') {
        const u = getActiveUser();
        if (!u) {
          return makeResult(401, {
            detail: { code: 'AUTH_REQUIRED', message: 'Chọn vai trò minh họa để mở sandbox bệnh nhân ảo.' }
          });
        }
        return makeResult(200, {
          authenticated: true,
          user: sanitizeUser(u),
          store_epoch: ramStore.store_epoch,
          remaining_seconds: 900,
          env_mode: 'gh_pages_static_demo'
        });
      }

      if (method === 'POST' && path === '/api/auth/local-bypass') {
        let targetUser = 'nguyenbinhan';
        if (bodyObj && bodyObj.target_username && ramStore.users[bodyObj.target_username]) {
          targetUser = bodyObj.target_username;
        }
        activePersonaKey = targetUser;
        const u = getActiveUser();
        return makeResult(200, {
          authenticated: true,
          gate_code: 'STATIC_DEMO_SANDBOX',
          user: sanitizeUser(u),
          store_epoch: ramStore.store_epoch,
          expires_in_seconds: 900,
          env_mode: 'gh_pages_static_demo'
        });
      }

      if (method === 'POST' && path === '/api/auth/logout') {
        activePersonaKey = null;
        if (opts.resetOnLogout !== false) {
          resetToInitialOd05();
        }
        return makeResult(200, { authenticated: false });
      }

      /* Require authenticated session for all clinical & admin endpoints */
      const actor = getActiveUser();
      if (!actor) {
        return makeResult(401, {
          detail: { code: 'AUTH_REQUIRED', message: 'Phiên làm việc đã kết thúc hoặc chưa đăng nhập.' }
        });
      }

      /* 2. GET /api/cases */
      if (method === 'GET' && path === '/api/cases') {
        const track = (params.get('track') || '').trim().toUpperCase();
        const items = listEnrichedCasesFromState(ramStore, track || null);
        return makeResult(200, {
          items: items,
          total: items.length,
          store_epoch: ramStore.store_epoch,
          settings: deepClone(ramStore.settings)
        });
      }

      /* 3. POST /api/cases */
      if (method === 'POST' && path === '/api/cases') {
        if (!bodyObj || typeof bodyObj !== 'object' || Array.isArray(bodyObj)) {
          return makeResult(422, { detail: { code: 'INVALID_PAYLOAD', message: 'Dữ liệu tạo ca soi không hợp lệ.' } });
        }
        const schemaCreateErr = validateModelObject(bodyObj, SCHEMA_CASE_CREATE, '');
        if (schemaCreateErr) {
          return makeResult(422, { detail: schemaCreateErr });
        }
        const dlpHit = scanPayloadNotes(bodyObj, '');
        if (dlpHit) {
          return makeResult(422, { detail: dlpHit });
        }

        const fullName = String(bodyObj.full_name || '').trim();
        const birthYear = Number(bodyObj.birth_year || 0);
        const sex = bodyObj.sex || 'M';
        const careSetting = bodyObj.care_setting || 'OUTPATIENT';
        const mrnClean = String(bodyObj.hospital_mrn || '').trim() || null;
        const track = bodyObj.track;

        if (fullName.length < 2 || birthYear < 1900 || birthYear > 2026 || !track) {
          return makeResult(422, { detail: { code: 'VALIDATION_ERROR', message: 'Thiếu thông tin định danh bệnh nhân ảo hoặc phân nhóm thủ thuật.' } });
        }
        if (opts.enforceSyntheticIdentity !== false) {
          if (!allowedSyntheticNames.has(normalizeName(fullName))) {
            return makeResult(422, {
              detail: {
                code: 'SYNTHETIC_IDENTITY_REQUIRED',
                message: 'Sandbox GitHub Pages chỉ chấp nhận danh tính bệnh nhân ảo có sẵn để bảo đảm Zero-PHI.'
              }
            });
          }
          if (mrnClean && !/^SYN-(?:OUT|INP|DEMO)-\d{4}$/.test(mrnClean)) {
            return makeResult(422, {
              detail: {
                code: 'SYNTHETIC_MRN_REQUIRED',
                message: 'Mã hồ sơ trên Sandbox bắt buộc thuộc dải mã giả lập SYN-OUT/INP/DEMO-xxxx (Zero-PHI).'
              }
            });
          }
          if (bodyObj.operator_name !== undefined && bodyObj.operator_name !== null) {
            const opClean = normalizeName(bodyObj.operator_name);
            if (!opClean || !allowedOperatorNames.has(opClean)) {
              return makeResult(422, {
                detail: {
                  code: 'SYNTHETIC_OPERATOR_REQUIRED',
                  message: 'Sandbox GitHub Pages chỉ cho phép danh tính bác sĩ giả lập có sẵn (Zero-PHI).'
                }
              });
            }
          }
        }
        if (careSetting === 'INPATIENT' && !mrnClean) {
          return makeResult(422, {
            detail: {
              code: 'INPATIENT_MRN_REQUIRED',
              message: 'OD-04: Ca nội trú (INPATIENT) bắt buộc nhập mã hồ sơ bệnh viện (hospital_mrn).'
            }
          });
        }

        const nowIso = currentUtcIso();
        const patients = ramStore.patients;
        const episodes = ramStore.episodes;
        const cases = ramStore.cases;
        const surveillance = ramStore.surveillance;
        const counters = ramStore.counters;
        const primaryMode = ramStore.settings.colo_guideline_mode || 'USMSTF_2020';
        const mrnHash = mrnClean ? mrnHmac(mrnClean) : null;

        let patientUid = bodyObj.patient_uid || null;
        let mutatedExistingPat = null;
        let patPrevBackup = null;
        if (patientUid) {
          if (!patients[patientUid]) {
            return makeResult(422, { detail: { code: 'PATIENT_NOT_FOUND', message: 'Không tìm thấy hồ sơ người bệnh ' + patientUid + '.' } });
          }
          const pEx = patients[patientUid];
          if ((pEx.status || 'ACTIVE') !== 'ACTIVE') {
            return makeResult(409, {
              detail: {
                code: 'PATIENT_MERGED_SUPERSEDED',
                message: 'Hồ sơ người bệnh này đã được gộp sang hồ sơ chính; không thể thêm ca mới vào định danh cũ.',
                canonical_patient_uid: pEx.merged_into_patient_uid || null,
                merged_into_patient_uid: pEx.merged_into_patient_uid || null
              }
            });
          }
          if (mrnClean && mrnHash) {
            const ownerUid = findActivePatientByMrnHash(patients, mrnHash);
            if (ownerUid && ownerUid !== patientUid) {
              return makeResult(409, {
                detail: {
                  code: 'MRN_BELONGS_TO_OTHER_PATIENT',
                  message: 'Mã hồ sơ bệnh viện đã gắn với một người bệnh đang hoạt động khác.',
                  conflicting_patient_uid: ownerUid
                }
              });
            }
            if (!pEx.hospital_mrn_hash) {
              patPrevBackup = deepClone(pEx);
              mutatedExistingPat = patientUid;
              pEx.hospital_mrn = mrnClean;
              pEx.hospital_mrn_masked = maskMrn(mrnClean);
              pEx.hospital_mrn_hash = mrnHash;
              pEx.version = Number(pEx.version || 1) + 1;
              pEx.updated_at = nowIso;
            }
          }
        } else if (mrnHash) {
          patientUid = findActivePatientByMrnHash(patients, mrnHash);
        } else {
          const normTarget = normalizeName(fullName);
          const collisions = Object.values(patients).filter(function (p) {
            return (p.status || 'ACTIVE') === 'ACTIVE' &&
              normalizeName(p.full_name || '') === normTarget &&
              Number(p.birth_year || 0) === birthYear;
          }).map(function (p) {
            return {
              patient_uid: p.patient_uid,
              privacy_initials: p.privacy_initials,
              birth_year: p.birth_year,
              sex: p.sex
            };
          });
          if (collisions.length > 0 && !bodyObj.confirm_outpatient_new_patient) {
            return makeResult(409, {
              detail: {
                code: 'OUTPATIENT_POTENTIAL_DUPLICATE_CONFIRM_REQUIRED',
                candidates: collisions
              }
            });
          }
        }

        let createdNewPatient = false;
        if (!patientUid) {
          patientUid = nextUid('pat');
          createdNewPatient = true;
          patients[patientUid] = {
            patient_uid: patientUid,
            full_name: fullName,
            privacy_initials: computePrivacyInitials(fullName),
            birth_year: birthYear,
            sex: sex,
            hospital_mrn: mrnClean,
            hospital_mrn_masked: maskMrn(mrnClean),
            hospital_mrn_hash: mrnHash,
            status: 'ACTIVE',
            version: 1,
            secondary_mrn_hashes: [],
            secondary_mrns: [],
            merged_from_aliases: [],
            created_at: nowIso
          };
          allowedSyntheticNames.add(normalizeName(fullName));
        }

        function rollbackPatientIfAborted() {
          if (createdNewPatient) delete patients[patientUid];
          if (mutatedExistingPat && patPrevBackup) patients[mutatedExistingPat] = patPrevBackup;
        }

        const procStart = String(bodyObj.procedure_start_at);
        const procDate = procStart.slice(0, 10);
        let episodeId = bodyObj.episode_id || null;
        let createdNewEpisode = false;
        if (episodeId) {
          if (!episodes[episodeId]) {
            rollbackPatientIfAborted();
            return makeResult(422, { detail: { code: 'EPISODE_NOT_FOUND', message: 'Không tìm thấy đợt điều trị ' + episodeId + '.' } });
          }
          const epEx = episodes[episodeId];
          if ((epEx.status || 'ACTIVE') !== 'ACTIVE') {
            rollbackPatientIfAborted();
            return makeResult(409, {
              detail: {
                code: 'EPISODE_SUPERSEDED',
                message: 'Đợt điều trị này đã được hợp nhất sang đợt đích; không thể gắn ca mới vào đợt cũ.',
                canonical_episode_id: epEx.merged_into_episode_id || null,
                merged_into_episode_id: epEx.merged_into_episode_id || null
              }
            });
          }
          if (epEx.patient_uid !== patientUid) {
            rollbackPatientIfAborted();
            return makeResult(422, { detail: { code: 'EPISODE_PATIENT_MISMATCH', message: 'Đợt điều trị được chọn thuộc về một người bệnh khác.' } });
          }
          if (epEx.care_setting !== careSetting) {
            rollbackPatientIfAborted();
            return makeResult(422, { detail: { code: 'EPISODE_CARE_SETTING_MISMATCH', message: 'Loại hình điều trị của ca không khớp với đợt điều trị được chọn.' } });
          }
        } else if (careSetting === 'INPATIENT') {
          const admDate = bodyObj.admission_date || procDate;
          const epIds = Object.keys(episodes);
          for (let i = 0; i < epIds.length; i += 1) {
            const epObj = episodes[epIds[i]];
            if (
              (epObj.status || 'ACTIVE') === 'ACTIVE' &&
              epObj.patient_uid === patientUid &&
              epObj.care_setting === 'INPATIENT' &&
              (epObj.discharge_date === null || epObj.discharge_date === undefined)
            ) {
              episodeId = epIds[i];
              break;
            }
          }
          if (!episodeId) {
            episodeId = nextUid('epi');
            createdNewEpisode = true;
            episodes[episodeId] = {
              episode_id: episodeId,
              patient_uid: patientUid,
              care_setting: 'INPATIENT',
              admission_date: admDate,
              discharge_date: null,
              referring_dept: bodyObj.referring_dept || 'Khoa Nội soi Tiêu hóa',
              prior_unrecorded_ercp_offset: Number(bodyObj.prior_unrecorded_ercp_offset || 0),
              status: 'ACTIVE',
              created_at: nowIso
            };
          }
        } else {
          episodeId = nextUid('epi');
          createdNewEpisode = true;
          episodes[episodeId] = {
            episode_id: episodeId,
            patient_uid: patientUid,
            care_setting: 'OUTPATIENT',
            admission_date: procDate,
            discharge_date: procDate,
            referring_dept: bodyObj.referring_dept || 'Khoa Nội soi Tiêu hóa',
            prior_unrecorded_ercp_offset: 0,
            status: 'ACTIVE',
            created_at: nowIso
          };
        }

        let matchedSurvOriginCid = null;
        if (bodyObj.fulfill_surveillance_rec_id) {
          const sKeys = Object.keys(surveillance);
          for (let i = 0; i < sKeys.length; i += 1) {
            const originCid = sKeys[i];
            const sObj = surveillance[originCid];
            if (sObj.rec_id === bodyObj.fulfill_surveillance_rec_id || originCid === bodyObj.fulfill_surveillance_rec_id) {
              const originCase = cases[originCid];
              if (!originCase || originCase.patient_uid !== patientUid) {
                if (createdNewEpisode) delete episodes[episodeId];
                rollbackPatientIfAborted();
                return makeResult(422, { detail: { code: 'SURVEILLANCE_PATIENT_MISMATCH', message: 'Lịch hẹn soi lại được liên kết không thuộc cùng người bệnh.' } });
              }
              matchedSurvOriginCid = originCid;
              break;
            }
          }
          if (!matchedSurvOriginCid) {
            if (createdNewEpisode) delete episodes[episodeId];
            rollbackPatientIfAborted();
            return makeResult(422, { detail: { code: 'SURVEILLANCE_REC_NOT_FOUND', message: 'Không tìm thấy bản ghi hẹn soi lại cần liên kết.' } });
          }
        }

        const procYear = procStart.slice(0, 4);
        const counterKey = track + '-' + procYear;
        const nextNum = Number(counters[counterKey] || 0) + 1;
        counters[counterKey] = nextNum;
        const caseCode = counterKey + '-' + String(nextNum).padStart(4, '0');
        const caseId = nextUid('cas');

        let cecalIntub = bodyObj.cecal_intubation || 'NA';
        if (track === 'COL' && cecalIntub === 'NA') cecalIntub = 'YES';
        const wcNorm = (bodyObj.whole_case_summary !== undefined && bodyObj.whole_case_summary !== null)
          ? normalizeWholeCaseSummary(bodyObj.whole_case_summary)
          : (track === 'COL' ? normalizeWholeCaseSummary({}) : null);
        const ercpNorm = (bodyObj.ercp_detail !== undefined && bodyObj.ercp_detail !== null)
          ? normalizeErcpDetail(bodyObj.ercp_detail)
          : (track === 'ERCP' ? normalizeErcpDetail({}) : null);

        const caseRecord = {
          case_id: caseId,
          case_code: caseCode,
          patient_uid: patientUid,
          episode_id: episodeId,
          track: track,
          care_setting: careSetting,
          procedure_start_at: procStart,
          created_at: nowIso,
          updated_at: nowIso,
          operator_name: bodyObj.operator_name || 'ThS. BSCKI. Nguyễn Bình An',
          indication: bodyObj.indication || 'DIAGNOSTIC',
          indication_detail: bodyObj.indication_detail !== undefined ? String(bodyObj.indication_detail) : '',
          has_ibd_or_polyposis: Boolean(bodyObj.has_ibd_or_polyposis),
          exclude_from_cir: Boolean(bodyObj.exclude_from_cir),
          prior_unrecorded_ercp_offset: Number(bodyObj.prior_unrecorded_ercp_offset || 0),
          bbps_right: bodyObj.bbps_right !== undefined && bodyObj.bbps_right !== null ? Number(bodyObj.bbps_right) : null,
          bbps_transverse: bodyObj.bbps_transverse !== undefined && bodyObj.bbps_transverse !== null ? Number(bodyObj.bbps_transverse) : null,
          bbps_left: bodyObj.bbps_left !== undefined && bodyObj.bbps_left !== null ? Number(bodyObj.bbps_left) : null,
          cecal_intubation: cecalIntub,
          cecal_failure_reason: bodyObj.cecal_failure_reason !== undefined ? String(bodyObj.cecal_failure_reason) : '',
          withdrawal_time_clean_min: bodyObj.withdrawal_time_clean_min !== undefined && bodyObj.withdrawal_time_clean_min !== null ? Number(bodyObj.withdrawal_time_clean_min) : null,
          pathology_completion_status: bodyObj.pathology_completion_status || 'NOT_APPLICABLE',
          followup_30d_status: bodyObj.followup_30d_status || 'PENDING_WINDOW',
          clinician_followup_due_date: bodyObj.clinician_followup_due_date || null,
          clinician_followup_note: bodyObj.clinician_followup_note !== undefined ? String(bodyObj.clinician_followup_note) : '',
          index_lesion: normalizeIndexLesion(bodyObj.index_lesion),
          whole_case_summary: wcNorm,
          ercp_detail: ercpNorm,
          adverse_events: Array.isArray(bodyObj.adverse_events) ? bodyObj.adverse_events.map(normalizeAdverseEvent) : [],
          clinical_note: bodyObj.clinical_note !== undefined ? String(bodyObj.clinical_note) : '',
          version: 1,
          record_status: 'ACTIVE'
        };
        cases[caseId] = caseRecord;

        const survRec = buildSurveillanceRecommendation(caseRecord, primaryMode);
        survRec.rec_id = 'rec_' + caseId;
        surveillance[caseId] = survRec;
        if (matchedSurvOriginCid && matchedSurvOriginCid !== caseId) {
          surveillance[matchedSurvOriginCid].fulfilled_by_case_id = caseId;
          surveillance[matchedSurvOriginCid].status = 'COMPLETED_LINKED';
        }

        ramStore.audit_chain.push(
          buildAuditEntry(
            ramStore.audit_chain,
            actor.username,
            actor.role,
            'CASE_CREATE',
            'ENDOSCOPY_CASE',
            caseId,
            { case_code: caseCode, track: track, version: 1 },
            nowIso
          )
        );
        const enriched = enrichCaseRecord(caseRecord, ramStore);
        return makeResult(201, enriched, { ETag: enriched.etag });
      }

      /* 4. PATCH /api/cases/{case_id} & DELETE /api/cases/{case_id} */
      const caseMatch = path.match(/^\/api\/cases\/([^/]+)$/);
      if (caseMatch) {
        const caseId = decodeURIComponent(caseMatch[1]);
        if (method === 'PATCH') {
          if (!bodyObj || typeof bodyObj !== 'object' || Array.isArray(bodyObj) || bodyObj.expected_version === undefined) {
            return makeResult(422, { detail: { code: 'INVALID_PATCH', message: 'Thiếu expected_version khi cập nhật hồ sơ.' } });
          }
          const schemaPatchErr = validateModelObject(bodyObj, SCHEMA_CASE_PATCH, '');
          if (schemaPatchErr) return makeResult(422, { detail: schemaPatchErr });
          const dlpHit = scanPayloadNotes(bodyObj, '');
          if (dlpHit) return makeResult(422, { detail: dlpHit });
          if (opts.enforceSyntheticIdentity !== false && bodyObj.operator_name !== undefined && bodyObj.operator_name !== null) {
            const opPatchClean = normalizeName(bodyObj.operator_name);
            if (!opPatchClean || !allowedOperatorNames.has(opPatchClean)) {
              return makeResult(422, {
                detail: {
                  code: 'SYNTHETIC_OPERATOR_REQUIRED',
                  message: 'Sandbox GitHub Pages chỉ cho phép danh tính bác sĩ giả lập có sẵn (Zero-PHI).'
                }
              });
            }
          }

          const parsedHdr = parseIfMatchHeader(headers['if-match'] || '', Number(bodyObj.expected_version));
          if (parsedHdr.error) return makeResult(409, { detail: parsedHdr.error });

          const stateEpoch = ramStore.store_epoch;
          if (stateEpoch > 1 && parsedHdr.epoch === null && (bodyObj.expected_store_epoch === null || bodyObj.expected_store_epoch === undefined)) {
            return makeResult(409, {
              detail: {
                code: 'OCC_STORE_EPOCH_MISMATCH',
                message: 'Kho dữ liệu đang ở thế hệ e' + stateEpoch + '; yêu cầu cập nhật bắt buộc gửi kèm ETag hoặc expected_store_epoch.',
                current_store_epoch: stateEpoch
              }
            });
          }
          if (parsedHdr.epoch !== null && Number(parsedHdr.epoch) !== stateEpoch) {
            return makeResult(409, {
              detail: {
                code: 'OCC_STORE_EPOCH_MISMATCH',
                message: 'Xung đột thế hệ kho OCC: máy chủ đang ở e' + stateEpoch + ', header If-Match gửi e' + parsedHdr.epoch + '.',
                current_store_epoch: stateEpoch
              }
            });
          }
          if (bodyObj.expected_store_epoch !== null && bodyObj.expected_store_epoch !== undefined && Number(bodyObj.expected_store_epoch) !== stateEpoch) {
            return makeResult(409, {
              detail: {
                code: 'OCC_STORE_EPOCH_MISMATCH',
                message: 'Xung đột thế hệ kho OCC: máy chủ đang ở e' + stateEpoch + ', yêu cầu gửi e' + bodyObj.expected_store_epoch + '.',
                current_store_epoch: stateEpoch
              }
            });
          }

          const recCase = ramStore.cases[caseId];
          if (!recCase || recCase.record_status !== 'ACTIVE') {
            return makeResult(404, { detail: 'Không tìm thấy hồ sơ ca nội soi ' + caseId + '.' });
          }
          const patObj = ramStore.patients[recCase.patient_uid];
          if (!patObj || (patObj.status || 'ACTIVE') !== 'ACTIVE') {
            return makeResult(409, {
              detail: {
                code: 'PATIENT_MERGED_SUPERSEDED',
                message: 'Hồ sơ người bệnh của ca này đã chuyển trạng thái gộp; vui lòng tải lại danh sách.',
                canonical_patient_uid: (patObj && patObj.merged_into_patient_uid) || null,
                merged_into_patient_uid: (patObj && patObj.merged_into_patient_uid) || null
              }
            });
          }
          const epiObj = ramStore.episodes[recCase.episode_id];
          if (!epiObj || (epiObj.status || 'ACTIVE') !== 'ACTIVE') {
            return makeResult(409, {
              detail: {
                code: 'EPISODE_SUPERSEDED',
                message: 'Đợt điều trị của ca này đã chuyển trạng thái hợp nhất; vui lòng tải lại danh sách.',
                canonical_episode_id: (epiObj && epiObj.merged_into_episode_id) || null,
                merged_into_episode_id: (epiObj && epiObj.merged_into_episode_id) || null
              }
            });
          }
          if (Number(recCase.version) !== Number(bodyObj.expected_version)) {
            return makeResult(409, {
              detail: {
                code: 'OCC_VERSION_CONFLICT',
                message: 'Xung đột phiên bản OCC: máy chủ đang ở v' + recCase.version + ', yêu cầu gửi v' + bodyObj.expected_version + '.'
              }
            });
          }

          let matchedSurvOriginCid = null;
          if (bodyObj.fulfill_surveillance_rec_id) {
            const sKeys = Object.keys(ramStore.surveillance);
            for (let i = 0; i < sKeys.length; i += 1) {
              const originCid = sKeys[i];
              const sObj = ramStore.surveillance[originCid];
              if (sObj.rec_id === bodyObj.fulfill_surveillance_rec_id || originCid === bodyObj.fulfill_surveillance_rec_id) {
                const originCase = ramStore.cases[originCid];
                if (originCid === caseId || !originCase || originCase.patient_uid !== recCase.patient_uid) {
                  return makeResult(422, { detail: { code: 'SURVEILLANCE_PATIENT_MISMATCH', message: 'Liên kết hẹn soi lại không hợp lệ hoặc khác người bệnh.' } });
                }
                matchedSurvOriginCid = originCid;
                break;
              }
            }
            if (!matchedSurvOriginCid) {
              return makeResult(422, { detail: { code: 'SURVEILLANCE_REC_NOT_FOUND', message: 'Không tìm thấy bản ghi hẹn soi lại cần liên kết.' } });
            }
          }

          const nowIso = currentUtcIso();
          const nullableScalarSet = {
            clinician_followup_due_date: true,
            bbps_right: true,
            bbps_transverse: true,
            bbps_left: true,
            withdrawal_time_clean_min: true
          };
          const numericScalarSet = {
            prior_unrecorded_ercp_offset: true,
            bbps_right: true,
            bbps_transverse: true,
            bbps_left: true,
            withdrawal_time_clean_min: true
          };
          const boolScalarSet = {
            has_ibd_or_polyposis: true,
            exclude_from_cir: true
          };
          const scalarFields = [
            'procedure_start_at', 'operator_name', 'prior_unrecorded_ercp_offset', 'indication', 'indication_detail',
            'has_ibd_or_polyposis', 'exclude_from_cir', 'pathology_completion_status', 'followup_30d_status',
            'clinician_followup_due_date', 'clinician_followup_note', 'bbps_right', 'bbps_transverse',
            'bbps_left', 'cecal_intubation', 'cecal_failure_reason', 'withdrawal_time_clean_min', 'clinical_note'
          ];
          const changedFields = [];
          for (let i = 0; i < scalarFields.length; i += 1) {
            const fName = scalarFields[i];
            const hasExplicitKey = Object.prototype.hasOwnProperty.call(bodyObj, fName) && bodyObj[fName] !== undefined;
            if (nullableScalarSet[fName]) {
              if (hasExplicitKey) {
                if (bodyObj[fName] === null) recCase[fName] = null;
                else if (numericScalarSet[fName]) recCase[fName] = Number(bodyObj[fName]);
                else recCase[fName] = String(bodyObj[fName]);
                changedFields.push(fName);
              }
            } else if (hasExplicitKey && bodyObj[fName] !== null) {
              if (numericScalarSet[fName]) recCase[fName] = Number(bodyObj[fName]);
              else if (boolScalarSet[fName]) recCase[fName] = Boolean(bodyObj[fName]);
              else recCase[fName] = String(bodyObj[fName]);
              changedFields.push(fName);
            }
          }
          if (bodyObj.referring_dept !== undefined && bodyObj.referring_dept !== null) {
            epiObj.referring_dept = bodyObj.referring_dept;
            changedFields.push('referring_dept');
          }
          if (bodyObj.prior_unrecorded_ercp_offset !== undefined && bodyObj.prior_unrecorded_ercp_offset !== null && epiObj.care_setting === 'INPATIENT') {
            epiObj.prior_unrecorded_ercp_offset = Number(bodyObj.prior_unrecorded_ercp_offset);
          }
          if (Object.prototype.hasOwnProperty.call(bodyObj, 'index_lesion') && bodyObj.index_lesion !== undefined) {
            recCase.index_lesion = bodyObj.index_lesion !== null ? normalizeIndexLesion(bodyObj.index_lesion) : null;
            changedFields.push('index_lesion');
          }
          if (bodyObj.whole_case_summary !== undefined && bodyObj.whole_case_summary !== null) {
            recCase.whole_case_summary = normalizeWholeCaseSummary(bodyObj.whole_case_summary);
            changedFields.push('whole_case_summary');
          }
          if (bodyObj.ercp_detail !== undefined && bodyObj.ercp_detail !== null) {
            recCase.ercp_detail = normalizeErcpDetail(bodyObj.ercp_detail);
            changedFields.push('ercp_detail');
          }
          if (bodyObj.adverse_events !== undefined && bodyObj.adverse_events !== null) {
            recCase.adverse_events = bodyObj.adverse_events.map(normalizeAdverseEvent);
            changedFields.push('adverse_events');
          }

          recCase.version = Number(recCase.version) + 1;
          recCase.updated_at = nowIso;

          const primaryMode = ramStore.settings.colo_guideline_mode || 'USMSTF_2020';
          const existingSurv = ramStore.surveillance[caseId] || {};
          const rebuilt = buildSurveillanceRecommendation(recCase, primaryMode);
          rebuilt.rec_id = existingSurv.rec_id || ('rec_' + caseId);
          if (existingSurv.fulfilled_by_case_id) {
            rebuilt.fulfilled_by_case_id = existingSurv.fulfilled_by_case_id;
            rebuilt.status = 'COMPLETED_LINKED';
          }
          ramStore.surveillance[caseId] = rebuilt;

          if (matchedSurvOriginCid) {
            ramStore.surveillance[matchedSurvOriginCid].fulfilled_by_case_id = caseId;
            ramStore.surveillance[matchedSurvOriginCid].status = 'COMPLETED_LINKED';
            changedFields.push('fulfill_surveillance_link');
          }

          ramStore.audit_chain.push(
            buildAuditEntry(
              ramStore.audit_chain,
              actor.username,
              actor.role,
              'CASE_PATCH_PHASE',
              'ENDOSCOPY_CASE',
              caseId,
              {
                case_code: recCase.case_code,
                new_version: recCase.version,
                changed_fields: changedFields
              },
              nowIso
            )
          );
          const updated = enrichCaseRecord(recCase, ramStore);
          return makeResult(200, updated, { ETag: updated.etag });
        }

        if (method === 'DELETE') {
          if (actor.role !== 'superadmin') {
            return makeResult(403, { detail: 'Chỉ Superadmin (BSCKII. Vũ Khương An) có thẩm quyền hủy hiệu lực hồ sơ ca soi.' });
          }
          const parsedHdr = parseIfMatchHeader(headers['if-match'] || '', null);
          if (parsedHdr.error) return makeResult(409, { detail: parsedHdr.error });
          const stateEpoch = ramStore.store_epoch;
          if (stateEpoch > 1 && parsedHdr.epoch === null) {
            return makeResult(409, {
              detail: {
                code: 'OCC_STORE_EPOCH_MISMATCH',
                message: 'Kho dữ liệu đang ở thế hệ e' + stateEpoch + '; yêu cầu hủy hiệu lực bắt buộc gửi kèm header If-Match.',
                current_store_epoch: stateEpoch
              }
            });
          }
          if (parsedHdr.epoch !== null && Number(parsedHdr.epoch) !== stateEpoch) {
            return makeResult(409, {
              detail: {
                code: 'OCC_STORE_EPOCH_MISMATCH',
                message: 'Xung đột thế hệ kho OCC: máy chủ đang ở e' + stateEpoch + ', header If-Match gửi e' + parsedHdr.epoch + '.',
                current_store_epoch: stateEpoch
              }
            });
          }
          const cObj = ramStore.cases[caseId];
          if (!cObj) return makeResult(404, { detail: caseId });
          if (parsedHdr.version !== null && Number(parsedHdr.version) !== Number(cObj.version)) {
            return makeResult(409, {
              detail: {
                code: 'OCC_VERSION_CONFLICT',
                message: 'Xung đột phiên bản OCC khi hủy hiệu lực: máy chủ đang ở v' + cObj.version + ', header If-Match gửi v' + parsedHdr.version + '.'
              }
            });
          }
          const nowIso = currentUtcIso();
          cObj.record_status = 'SUPERSEDED';
          cObj.version = Number(cObj.version) + 1;
          cObj.updated_at = nowIso;
          ramStore.audit_chain.push(
            buildAuditEntry(
              ramStore.audit_chain,
              actor.username,
              actor.role,
              'CASE_SUPERSEDE',
              'ENDOSCOPY_CASE',
              caseId,
              { case_code: cObj.case_code, store_epoch: stateEpoch },
              nowIso
            )
          );
          return makeResult(200, {
            case_id: caseId,
            record_status: 'SUPERSEDED',
            store_epoch: stateEpoch,
            version: cObj.version
          });
        }
      }

      /* 5. GET /api/surveillance */
      if (method === 'GET' && path === '/api/surveillance') {
        const cases = listEnrichedCasesFromState(ramStore, null);
        const todayIso = currentLocalDateIso();
        const soonIso = addCalendarDaysIso(todayIso, 30);
        const rows = cases.map(function (c) {
          const surv = c.surveillance;
          const due = surv.due_date;
          let tone = 'neutral';
          let label = 'Chưa đến hạn';
          if (surv.category === 'SURGICAL_MDT_CONSULT_ALERT') {
            tone = 'urgent';
            label = 'Cảnh báo hội chẩn ' + surv.surgical_consult_target_dept;
          } else if (surv.status === 'PENDING_GPB') {
            tone = 'pending';
            label = 'Chờ GPB';
          } else if (surv.status === 'COMPLETED_LINKED') {
            tone = 'ned';
            label = 'Không biến cố / hoàn tất';
          } else if (due && due <= soonIso) {
            tone = 'due';
            label = due < todayIso ? 'Quá hạn hẹn soi lại' : 'Đến hạn soi lại';
          }
          return {
            case_id: c.case_id,
            case_code: c.case_code,
            track: c.track,
            procedure_date: c.procedure_start_at.slice(0, 10),
            patient: c.patient,
            indication_detail: c.indication_detail || c.indication,
            pathology_completion_status: c.pathology_completion_status,
            surveillance: surv,
            urgency: { tone: tone, label: label }
          };
        });
        const prio = { urgent: 0, due: 1, pending: 2, neutral: 3, ned: 4 };
        /* Python list.sort is stable; preserve original enriched order when priority & due_date tie */
        const indexed = rows.map(function (r, idx) { return { r: r, idx: idx }; });
        indexed.sort(function (a, b) {
          const pa = prio[a.r.urgency.tone] !== undefined ? prio[a.r.urgency.tone] : 9;
          const pb = prio[b.r.urgency.tone] !== undefined ? prio[b.r.urgency.tone] : 9;
          if (pa !== pb) return pa - pb;
          const da = a.r.surveillance.due_date || '9999';
          const db = b.r.surveillance.due_date || '9999';
          const dCmp = da.localeCompare(db);
          if (dCmp !== 0) return dCmp;
          return a.idx - b.idx;
        });
        const sortedRows = indexed.map(function (x) { return x.r; });
        return makeResult(200, { items: sortedRows, total: sortedRows.length });
      }

      /* 6. GET /api/metrics/kpi */
      if (method === 'GET' && path === '/api/metrics/kpi') {
        const rawAge = params.get('min_adr_age');
        const effectiveAge = Number(rawAge || ramStore.settings.adr_min_age || 45);
        if (effectiveAge !== 45 && effectiveAge !== 50) {
          return makeResult(422, { detail: 'Ngưỡng tuổi ADR chỉ hỗ trợ 45 hoặc 50.' });
        }
        const effectiveNMin = Math.max(1, Number(ramStore.settings.kpi_min_sample_size || 20));
        const casesList = Object.values(ramStore.cases);
        const kpi = computeKpiSnapshot(casesList, ramStore.patients, effectiveAge, effectiveNMin);
        const cusumCir = buildCusumSeriesFromCases(casesList, 'CIR', ramStore.settings.cusum_preset || 'DEFAULT_90');
        const cusumErcp = buildCusumSeriesFromCases(casesList, 'ERCP_NATIVE', 'DEFAULT_90');
        return makeResult(200, {
          kpi: kpi,
          cusum_cir: cusumCir,
          cusum_ercp: cusumErcp,
          colo_guideline_mode: ramStore.settings.colo_guideline_mode || 'USMSTF_2020',
          kpi_min_sample_size: effectiveNMin
        });
      }

      /* 7. GET /api/metrics/cusum */
      if (method === 'GET' && path === '/api/metrics/cusum') {
        const metric = params.get('metric') || 'CIR';
        const preset = params.get('preset') || 'DEFAULT_90';
        return makeResult(200, buildCusumSeriesFromCases(Object.values(ramStore.cases), metric, preset));
      }

      /* 8. GET /api/audit/verify */
      if (method === 'GET' && path === '/api/audit/verify') {
        const verification = verifyAuditChain(ramStore.audit_chain);
        const lineageVer = verifyVirtualLineageBridges(ramStore.audit_lineage_bridges, virtualBackupFiles, ramStore.audit_chain);
        const recent = ramStore.audit_chain.slice(-20).reverse();
        return makeResult(200, {
          store_epoch: ramStore.store_epoch,
          verification: verification,
          audit_lineage_bridges: lineageVer.items,
          lineage_verification: {
            valid: lineageVer.valid,
            bridge_count: lineageVer.bridge_count,
            audit_chain_consistency_valid: lineageVer.audit_chain_consistency_valid
          },
          recent_entries: deepClone(recent)
        });
      }

      /* 9. GET & PATCH /api/settings */
      if (method === 'GET' && path === '/api/settings') {
        return makeResult(200, Object.assign({}, deepClone(ramStore.settings), { store_epoch: ramStore.store_epoch }));
      }

      if (method === 'PATCH' && path === '/api/settings') {
        const patch = bodyObj || {};
        const schemaSettingsErr = validateModelObject(patch, SCHEMA_SETTINGS_PATCH, '');
        if (schemaSettingsErr) return makeResult(422, { detail: schemaSettingsErr });
        if (actor.role !== 'superadmin' && (patch.kpi_min_sample_size !== undefined && patch.kpi_min_sample_size !== null || patch.cusum_preset !== undefined && patch.cusum_preset !== null)) {
          return makeResult(403, {
            detail: {
              code: 'SUPERADMIN_REQUIRED_FOR_STATISTICAL_SETTINGS',
              message: 'Chỉ Superadmin (BSCKII. Vũ Khương An) được hiệu chỉnh ngưỡng cỡ mẫu tối thiểu và tham số CUSUM.'
            }
          });
        }
        if (patch.colo_guideline_mode === 'USMSTF_2020' || patch.colo_guideline_mode === 'ESGE_2020') {
          ramStore.settings.colo_guideline_mode = patch.colo_guideline_mode;
        }
        const adrAge = (patch.adr_min_age !== undefined && patch.adr_min_age !== null) ? Number(patch.adr_min_age) : null;
        if (adrAge === 45 || adrAge === 50) {
          ramStore.settings.adr_min_age = adrAge;
        }
        if (actor.role === 'superadmin') {
          if (patch.cusum_preset === 'DEFAULT_90' || patch.cusum_preset === 'SCREENING_CIR_95') {
            ramStore.settings.cusum_preset = patch.cusum_preset;
          }
          if (patch.kpi_min_sample_size !== undefined && patch.kpi_min_sample_size !== null) {
            ramStore.settings.kpi_min_sample_size = Number(patch.kpi_min_sample_size);
          }
        }
        const nowIso = currentUtcIso();
        ramStore.audit_chain.push(
          buildAuditEntry(
            ramStore.audit_chain,
            actor.username,
            actor.role,
            'SETTINGS_UPDATE',
            'SETTINGS',
            'global',
            deepClone(ramStore.settings),
            nowIso
          )
        );
        return makeResult(200, Object.assign({}, deepClone(ramStore.settings), { store_epoch: ramStore.store_epoch }));
      }

      /* 10. GET /api/exports/profile-b & GET /api/exports/profile-c */
      if (method === 'GET' && path === '/api/exports/profile-b') {
        const fmt = (params.get('fmt') || 'csv').toLowerCase();
        if (fmt === 'xlsx') {
          return makeResult(403, {
            detail: {
              code: 'STATIC_DEMO_XLSX_LOCKED',
              message: 'Sandbox trình duyệt hỗ trợ xuất trực tiếp Hồ sơ B dạng CSV chuẩn UTF-8 BOM; xuất XLSX nhị phân chỉ chạy trên máy chủ Python nội bộ.'
            }
          });
        }
        const track = params.get('track') || null;
        const scopeId = params.get('scope_id') || 'endolog_bvbd_v1';
        const dsEpoch = Math.max(1, Number(ramStore.settings.export_dataset_epoch || 1));
        const lineageSeq = Math.max(1, Number(ramStore.settings.profile_b_lineage_seq || 1));
        const rows = exportProfileBRowsFromState(ramStore, researchMaterial, shiftMaterial, scopeId, track);
        ramStore.audit_chain.push(
          buildAuditEntry(
            ramStore.audit_chain,
            actor.username,
            actor.role,
            'EXPORT_PROFILE_B_PSEUDONYMIZED',
            'EXPORT',
            'profile_b',
            {
              fmt: fmt,
              row_count: rows.length,
              scope_id: scopeId,
              export_dataset_epoch: dsEpoch,
              profile_b_lineage_seq: lineageSeq
            },
            currentUtcIso()
          )
        );
        const csvText = rowsToCsvTextWithBom(rows);
        return makeResult(200, csvText, {
          'Content-Type': 'text/csv; charset=utf-8',
          'Content-Disposition': 'attachment; filename="endolog_profile_b_longitudinal.csv"',
          'X-EndoLog-Dataset-Epoch': String(dsEpoch),
          'X-EndoLog-Lineage-Seq': String(lineageSeq)
        }, true);
      }

      if (method === 'GET' && path === '/api/exports/profile-c') {
        const rawSup = params.get('suppress_small_cells');
        const suppress = rawSup === null ? true : !(rawSup === 'false' || rawSup === '0');
        const minAge = Number(ramStore.settings.adr_min_age || 45);
        const summary = exportProfileCSummaryFromState(ramStore, minAge, suppress);
        ramStore.audit_chain.push(
          buildAuditEntry(
            ramStore.audit_chain,
            actor.username,
            actor.role,
            'EXPORT_PROFILE_C_AGGREGATE',
            'EXPORT',
            'profile_c',
            { suppress_small_cells: suppress },
            currentUtcIso()
          )
        );
        return makeResult(200, summary, {
          'Content-Disposition': 'attachment; filename="endolog_profile_c_summary.json"'
        });
      }

      /* 11. Superadmin endpoints */
      if (path.startsWith('/api/admin/')) {
        if (actor.role !== 'superadmin') {
          return makeResult(403, { detail: 'Chỉ tài khoản Superadmin (BSCKII. Vũ Khương An) được phép thực hiện tác vụ quản trị hệ thống.' });
        }

        if (method === 'GET' && path === '/api/admin/users') {
          const items = Object.values(ramStore.users).map(sanitizeUser).sort(function (a, b) {
            const ra = a.role === 'superadmin' ? 0 : 1;
            const rb = b.role === 'superadmin' ? 0 : 1;
            if (ra !== rb) return ra - rb;
            return String(a.username).localeCompare(String(b.username));
          });
          return makeResult(200, {
            store_epoch: ramStore.store_epoch,
            items: items,
            total: items.length
          });
        }

        if (method === 'GET' && path === '/api/admin/patients') {
          const activeCasesByPat = {};
          const activeCasesByEp = {};
          Object.values(ramStore.cases).forEach(function (c) {
            if ((c.record_status || 'ACTIVE') !== 'ACTIVE') return;
            if (!activeCasesByPat[c.patient_uid]) activeCasesByPat[c.patient_uid] = [];
            activeCasesByPat[c.patient_uid].push(c);
            if (!activeCasesByEp[c.episode_id]) activeCasesByEp[c.episode_id] = [];
            activeCasesByEp[c.episode_id].push(c);
          });

          const epsByPat = {};
          Object.values(ramStore.episodes).forEach(function (ep) {
            if ((ep.status || 'ACTIVE') !== 'ACTIVE') return;
            const epCases = (activeCasesByEp[ep.episode_id] || []).slice().sort(function (a, b) {
              const pCmp = String(a.procedure_start_at || '').localeCompare(String(b.procedure_start_at || ''));
              if (pCmp !== 0) return pCmp;
              return String(a.case_code || '').localeCompare(String(b.case_code || ''));
            });
            if (!epsByPat[ep.patient_uid]) epsByPat[ep.patient_uid] = [];
            epsByPat[ep.patient_uid].push({
              episode_id: ep.episode_id,
              care_setting: ep.care_setting || 'OUTPATIENT',
              admission_date: ep.admission_date || null,
              discharge_date: ep.discharge_date !== undefined ? ep.discharge_date : null,
              referring_dept: ep.referring_dept || null,
              prior_unrecorded_ercp_offset: Number(ep.prior_unrecorded_ercp_offset || 0),
              status: ep.status || 'ACTIVE',
              active_case_ids: epCases.map(function (c) { return c.case_id; }),
              case_codes: epCases.map(function (c) { return c.case_code; }),
              ercp_case_count: epCases.filter(function (c) { return c.track === 'ERCP'; }).length
            });
          });

          const activeItems = [];
          let supersededCount = 0;
          const dupBuckets = {};
          const dupOrder = [];
          Object.keys(ramStore.patients).forEach(function (pUid) {
            const pObj = ramStore.patients[pUid];
            if ((pObj.status || 'ACTIVE') !== 'ACTIVE') {
              supersededCount += 1;
              return;
            }
            const pCases = (activeCasesByPat[pUid] || []).slice().sort(function (a, b) {
              const pCmp = String(a.procedure_start_at || '').localeCompare(String(b.procedure_start_at || ''));
              if (pCmp !== 0) return pCmp;
              return String(a.case_code || '').localeCompare(String(b.case_code || ''));
            });
            const pEps = (epsByPat[pUid] || []).slice().sort(function (a, b) {
              const aCmp = String(a.admission_date || '').localeCompare(String(b.admission_date || ''));
              if (aCmp !== 0) return aCmp;
              return String(a.episode_id).localeCompare(String(b.episode_id));
            });
            activeItems.push({
              patient_uid: pUid,
              full_name: pObj.full_name,
              privacy_initials: pObj.privacy_initials,
              birth_year: Number(pObj.birth_year || 0),
              sex: pObj.sex,
              hospital_mrn_masked: pObj.hospital_mrn_masked || null,
              has_hospital_mrn: Boolean(pObj.hospital_mrn_hash),
              secondary_mrn_count: (pObj.secondary_mrn_hashes || []).length,
              merged_alias_count: (pObj.merged_from_aliases || []).length,
              version: Number(pObj.version || 1),
              status: 'ACTIVE',
              active_case_ids: pCases.map(function (c) { return c.case_id; }),
              case_codes: pCases.map(function (c) { return c.case_code; }),
              episodes: pEps,
              inpatient_episode_count: pEps.filter(function (e) { return e.care_setting === 'INPATIENT'; }).length
            });
            const bKey = normalizeName(pObj.full_name || '') + '|' + pObj.birth_year;
            if (!dupBuckets[bKey]) {
              dupBuckets[bKey] = [];
              dupOrder.push(bKey);
            }
            dupBuckets[bKey].push(pUid);
          });

          activeItems.sort(function (a, b) {
            /* Match Python tuple string sort by Unicode code point on full_name */
            const na = a.full_name || '';
            const nb = b.full_name || '';
            if (na < nb) return -1;
            if (na > nb) return 1;
            if (a.birth_year !== b.birth_year) return a.birth_year - b.birth_year;
            return a.patient_uid < b.patient_uid ? -1 : (a.patient_uid > b.patient_uid ? 1 : 0);
          });
          const duplicateGroups = [];
          dupOrder.forEach(function (bKey, idx) {
            if (dupBuckets[bKey].length >= 2) {
              duplicateGroups.push({ group_key: idx + 1, patient_uids: dupBuckets[bKey] });
            }
          });

          return makeResult(200, {
            store_epoch: ramStore.store_epoch,
            profile_b_lineage_seq: Number(ramStore.settings.profile_b_lineage_seq || 1),
            items: activeItems,
            total_active: activeItems.length,
            superseded_count: supersededCount,
            duplicate_groups: duplicateGroups
          });
        }

        if (method === 'POST' && path === '/api/admin/patients/merge') {
          const req = bodyObj || {};
          const schemaMergeErr = validateModelObject(req, SCHEMA_PATIENT_MERGE, '');
          if (schemaMergeErr) return makeResult(422, { detail: schemaMergeErr });
          const dlpHit = scanPayloadNotes(req, '');
          if (dlpHit) return makeResult(422, { detail: dlpHit });
          if (opts.enforceSyntheticIdentity !== false && req.resolved_full_name !== undefined && req.resolved_full_name !== null) {
            const normResName = normalizeName(req.resolved_full_name);
            if (!normResName || !allowedSyntheticNames.has(normResName)) {
              return makeResult(422, {
                detail: {
                  code: 'SYNTHETIC_IDENTITY_REQUIRED',
                  message: 'Sandbox GitHub Pages chỉ cho phép gộp sang danh tính bệnh nhân ảo có sẵn (Zero-PHI).'
                }
              });
            }
          }
          if (req.source_patient_uid === req.target_patient_uid) {
            return makeResult(422, { detail: { code: 'SAME_PATIENT_MERGE_INVALID', message: 'Hồ sơ nguồn và hồ sơ đích phải là hai bản ghi người bệnh khác nhau.' } });
          }
          if (Number(req.expected_store_epoch) !== ramStore.store_epoch) {
            return makeResult(409, {
              detail: {
                code: 'OCC_STORE_EPOCH_MISMATCH',
                message: 'Kho dữ liệu đang ở thế hệ e' + ramStore.store_epoch + ', yêu cầu gửi e' + req.expected_store_epoch + '.',
                current_store_epoch: ramStore.store_epoch
              }
            });
          }
          const src = ramStore.patients[req.source_patient_uid];
          const tgt = ramStore.patients[req.target_patient_uid];
          if (!src || !tgt) return makeResult(404, { detail: 'Không tìm thấy hồ sơ người bệnh nguồn hoặc đích.' });
          if ((src.status || 'ACTIVE') !== 'ACTIVE' || (tgt.status || 'ACTIVE') !== 'ACTIVE') {
            return makeResult(409, { detail: { code: 'MERGE_PATIENT_NOT_ACTIVE', message: 'Một trong hai hồ sơ người bệnh đã được gộp trước đó.' } });
          }
          const srcVer = Number(src.version || 1);
          const tgtVer = Number(tgt.version || 1);
          const actualSrcCaseIds = Object.keys(ramStore.cases).filter(function (cid) {
            const c = ramStore.cases[cid];
            return c.patient_uid === req.source_patient_uid && (c.record_status || 'ACTIVE') === 'ACTIVE';
          }).sort();
          const expectedSrcCaseIds = Array.from(new Set(req.expected_source_case_ids || [])).sort();
          if (srcVer !== Number(req.source_expected_version) || tgtVer !== Number(req.target_expected_version) || JSON.stringify(actualSrcCaseIds) !== JSON.stringify(expectedSrcCaseIds)) {
            return makeResult(409, {
              detail: {
                code: 'MERGE_PRECONDITION_CONFLICT',
                message: 'Trạng thái phiên bản người bệnh hoặc danh sách ca thuộc hồ sơ nguồn đã thay đổi trước khi gộp.',
                actual_source_version: srcVer,
                actual_target_version: tgtVer,
                actual_source_case_ids: actualSrcCaseIds
              }
            });
          }

          const hasDemoConflict = (
            normalizeName(src.full_name || '') !== normalizeName(tgt.full_name || '') ||
            Number(src.birth_year || 0) !== Number(tgt.birth_year || 0) ||
            src.sex !== tgt.sex
          );
          if (hasDemoConflict && !req.confirm_demographic_conflict) {
            return makeResult(409, {
              detail: {
                code: 'DEMOGRAPHIC_CONFLICT_CONFIRM_REQUIRED',
                message: 'Hai hồ sơ lệch họ tên, năm sinh hoặc giới tính; cần xác nhận tường minh thông tin giữ lại.'
              }
            });
          }

          const srcMrn = String(src.hospital_mrn || '').trim() || null;
          const srcHash = src.hospital_mrn_hash || null;
          const tgtMrn = String(tgt.hospital_mrn || '').trim() || null;
          const tgtHash = tgt.hospital_mrn_hash || null;
          const hadDistinctMrn = Boolean(srcHash && tgtHash && srcHash !== tgtHash);
          if (hadDistinctMrn && !req.confirm_distinct_mrn_override) {
            return makeResult(409, {
              detail: {
                code: 'DISTINCT_HOSPITAL_MRN_CONFLICT',
                message: 'Hai hồ sơ có hai mã hồ sơ bệnh viện khác nhau; mặc định từ chối gộp trừ khi xác nhận ghi đè tường minh.'
              }
            });
          }

          const nowIso = currentUtcIso();
          const tgtAliases = (tgt.merged_from_aliases || []).slice();
          tgtAliases.push({
            source_patient_uid: req.source_patient_uid,
            merged_at_utc: nowIso,
            privacy_initials: src.privacy_initials,
            full_name: src.full_name,
            birth_year: src.birth_year,
            sex: src.sex,
            hospital_mrn_masked: src.hospital_mrn_masked || null
          });
          (src.merged_from_aliases || []).forEach(function (al) { tgtAliases.push(al); });
          tgt.merged_from_aliases = tgtAliases;

          if (hasDemoConflict) {
            if (req.resolved_full_name && String(req.resolved_full_name).trim()) {
              tgt.full_name = String(req.resolved_full_name).trim();
              tgt.privacy_initials = computePrivacyInitials(tgt.full_name);
            }
            if (req.resolved_birth_year !== null && req.resolved_birth_year !== undefined) {
              tgt.birth_year = Number(req.resolved_birth_year);
            }
            if (req.resolved_sex) tgt.sex = req.resolved_sex;
          }

          const secHashes = (tgt.secondary_mrn_hashes || []).slice();
          const secMrns = (tgt.secondary_mrns || []).slice();
          function normM(v) { return String(v || '').trim().toUpperCase(); }
          function addSec(mRaw, mHash) {
            if (mHash && mHash !== tgt.hospital_mrn_hash && secHashes.indexOf(mHash) === -1) secHashes.push(mHash);
            const mClean = String(mRaw || '').trim();
            if (mClean && normM(mClean) !== normM(tgt.hospital_mrn) && secMrns.every(function (x) { return normM(x) !== normM(mClean); })) {
              secMrns.push(mClean);
            }
          }
          if (hadDistinctMrn) {
            if (req.primary_mrn_choice === 'SOURCE' && srcMrn && srcHash) {
              tgt.hospital_mrn = srcMrn;
              tgt.hospital_mrn_masked = maskMrn(srcMrn);
              tgt.hospital_mrn_hash = srcHash;
              addSec(tgtMrn, tgtHash);
            } else {
              addSec(srcMrn, srcHash);
            }
          } else if (srcHash && !tgtHash && srcMrn) {
            tgt.hospital_mrn = srcMrn;
            tgt.hospital_mrn_masked = maskMrn(srcMrn);
            tgt.hospital_mrn_hash = srcHash;
          }
          (src.secondary_mrn_hashes || []).forEach(function (h) { addSec(null, h); });
          (src.secondary_mrns || []).forEach(function (m) { addSec(m, mrnHmac(m)); });
          tgt.secondary_mrn_hashes = secHashes.filter(function (h) { return h !== tgt.hospital_mrn_hash; });
          tgt.secondary_mrns = secMrns.filter(function (m) { return normM(m) !== normM(tgt.hospital_mrn); });

          const movedEpIds = [];
          Object.keys(ramStore.episodes).forEach(function (epId) {
            const ep = ramStore.episodes[epId];
            if (ep.patient_uid === req.source_patient_uid) {
              ep.patient_uid = req.target_patient_uid;
              ep.updated_at = nowIso;
              movedEpIds.push(epId);
            }
          });
          const movedCaseIds = [];
          Object.keys(ramStore.cases).forEach(function (cId) {
            const c = ramStore.cases[cId];
            if (c.patient_uid === req.source_patient_uid) {
              c.patient_uid = req.target_patient_uid;
              c.version = Number(c.version || 1) + 1;
              c.updated_at = nowIso;
              movedCaseIds.push(cId);
            }
          });
          Object.values(ramStore.patients).forEach(function (otherP) {
            if (otherP.merged_into_patient_uid === req.source_patient_uid) {
              otherP.merged_into_patient_uid = req.target_patient_uid;
            }
          });

          src.status = 'MERGED_SUPERSEDED';
          src.merged_into_patient_uid = req.target_patient_uid;
          src.version = srcVer + 1;
          src.updated_at = nowIso;
          tgt.version = tgtVer + 1;
          tgt.updated_at = nowIso;

          const newLineageSeq = Number(ramStore.settings.profile_b_lineage_seq || 1) + 1;
          ramStore.settings.profile_b_lineage_seq = newLineageSeq;
          ramStore.audit_chain.push(
            buildAuditEntry(
              ramStore.audit_chain,
              actor.username,
              actor.role,
              'SUPERADMIN_PATIENT_MERGE',
              'PATIENT',
              req.target_patient_uid,
              {
                source_patient_uid: req.source_patient_uid,
                target_patient_uid: req.target_patient_uid,
                moved_episode_count: movedEpIds.length,
                moved_case_count: movedCaseIds.length,
                had_demographic_conflict: hasDemoConflict,
                had_distinct_mrn_override: hadDistinctMrn,
                profile_b_lineage_seq: newLineageSeq
              },
              nowIso
            )
          );
          return makeResult(200, {
            merged: true,
            source_patient_uid: req.source_patient_uid,
            target_patient_uid: req.target_patient_uid,
            target_version: tgt.version,
            moved_episode_ids: movedEpIds.slice().sort(),
            moved_case_ids: movedCaseIds.slice().sort(),
            store_epoch: ramStore.store_epoch,
            profile_b_lineage_seq: newLineageSeq
          });
        }

        if (method === 'POST' && path === '/api/admin/episodes/reconcile') {
          const req = bodyObj || {};
          const schemaRecErr = validateModelObject(req, SCHEMA_EPISODE_RECONCILE, '');
          if (schemaRecErr) return makeResult(422, { detail: schemaRecErr });
          const dlpHit = scanPayloadNotes(req, '');
          if (dlpHit) return makeResult(422, { detail: dlpHit });
          if (req.source_episode_id === req.target_episode_id) {
            return makeResult(422, { detail: { code: 'SAME_EPISODE_RECONCILE_INVALID', message: 'Đợt điều trị nguồn và đợt đích phải khác nhau.' } });
          }
          if (Number(req.expected_store_epoch) !== ramStore.store_epoch) {
            return makeResult(409, {
              detail: {
                code: 'OCC_STORE_EPOCH_MISMATCH',
                message: 'Kho dữ liệu đang ở thế hệ e' + ramStore.store_epoch + ', yêu cầu gửi e' + req.expected_store_epoch + '.',
                current_store_epoch: ramStore.store_epoch
              }
            });
          }
          const pat = ramStore.patients[req.patient_uid];
          if (!pat) return makeResult(404, { detail: req.patient_uid });
          if ((pat.status || 'ACTIVE') !== 'ACTIVE') {
            return makeResult(409, { detail: { code: 'PATIENT_MERGED_SUPERSEDED', message: 'Hồ sơ người bệnh đã ở trạng thái gộp.' } });
          }
          const srcEp = ramStore.episodes[req.source_episode_id];
          const tgtEp = ramStore.episodes[req.target_episode_id];
          if (!srcEp || !tgtEp) return makeResult(404, { detail: 'Không tìm thấy đợt điều trị nguồn hoặc đợt đích.' });
          if ((srcEp.status || 'ACTIVE') !== 'ACTIVE' || (tgtEp.status || 'ACTIVE') !== 'ACTIVE') {
            return makeResult(409, { detail: { code: 'EPISODE_SUPERSEDED', message: 'Một trong hai đợt điều trị đã được hợp nhất trước đó.' } });
          }
          if (srcEp.patient_uid !== req.patient_uid || tgtEp.patient_uid !== req.patient_uid) {
            return makeResult(422, { detail: { code: 'EPISODE_PATIENT_MISMATCH', message: 'Hai đợt điều trị phải cùng thuộc một người bệnh trước khi đối soát hợp nhất.' } });
          }
          if (srcEp.care_setting !== 'INPATIENT' || tgtEp.care_setting !== 'INPATIENT') {
            return makeResult(422, { detail: { code: 'EPISODE_RECONCILE_INPATIENT_ONLY', message: 'Chỉ cho phép đối soát hợp nhất các đợt điều trị nội trú (INPATIENT) cùng lần nhập viện.' } });
          }

          const actualCaseIds = Object.keys(ramStore.cases).filter(function (cid) {
            const c = ramStore.cases[cid];
            return (c.episode_id === req.source_episode_id || c.episode_id === req.target_episode_id) && (c.record_status || 'ACTIVE') === 'ACTIVE';
          }).sort();
          const expectedCaseIds = Array.from(new Set(req.expected_case_ids || [])).sort();
          if (JSON.stringify(actualCaseIds) !== JSON.stringify(expectedCaseIds)) {
            return makeResult(409, {
              detail: {
                code: 'EPISODE_RECONCILE_PRECONDITION_CONFLICT',
                message: 'Danh sách ca trong hai đợt điều trị đã thay đổi trước khi hợp nhất; vui lòng tải lại để xem trước.',
                actual_case_ids: actualCaseIds
              }
            });
          }

          const nowIso = currentUtcIso();
          const resolvedOffset = Number(req.resolved_prior_unrecorded_ercp_offset || 0);
          const reassignedCaseIds = [];
          Object.keys(ramStore.cases).forEach(function (cid) {
            const c = ramStore.cases[cid];
            if (c.episode_id === req.source_episode_id || c.episode_id === req.target_episode_id) {
              if (c.episode_id === req.source_episode_id) {
                c.episode_id = req.target_episode_id;
                reassignedCaseIds.push(cid);
              }
              if (c.track === 'ERCP') c.prior_unrecorded_ercp_offset = resolvedOffset;
              c.version = Number(c.version || 1) + 1;
              c.updated_at = nowIso;
            }
          });

          const srcAdm = srcEp.admission_date || '';
          const tgtAdm = tgtEp.admission_date || '';
          if (srcAdm && (!tgtAdm || srcAdm < tgtAdm)) tgtEp.admission_date = srcAdm;
          tgtEp.prior_unrecorded_ercp_offset = resolvedOffset;
          tgtEp.updated_at = nowIso;

          Object.values(ramStore.episodes).forEach(function (otherEp) {
            if (otherEp.merged_into_episode_id === req.source_episode_id) {
              otherEp.merged_into_episode_id = req.target_episode_id;
            }
          });
          srcEp.status = 'MERGED_SUPERSEDED';
          srcEp.merged_into_episode_id = req.target_episode_id;
          srcEp.updated_at = nowIso;

          const newLineageSeq = Number(ramStore.settings.profile_b_lineage_seq || 1) + 1;
          ramStore.settings.profile_b_lineage_seq = newLineageSeq;
          const activeCases = Object.values(ramStore.cases).filter(function (c) { return (c.record_status || 'ACTIVE') === 'ACTIVE'; });
          const ercpIndices = computeErcpSessionIndices(activeCases, ramStore.episodes);
          const epErcpSessions = {};
          actualCaseIds.forEach(function (cid) {
            if (ercpIndices[cid] !== undefined) epErcpSessions[cid] = ercpIndices[cid];
          });

          ramStore.audit_chain.push(
            buildAuditEntry(
              ramStore.audit_chain,
              actor.username,
              actor.role,
              'SUPERADMIN_EPISODE_RECONCILE',
              'EPISODE',
              req.target_episode_id,
              {
                patient_uid: req.patient_uid,
                source_episode_id: req.source_episode_id,
                target_episode_id: req.target_episode_id,
                reassigned_case_count: reassignedCaseIds.length,
                resolved_prior_unrecorded_ercp_offset: resolvedOffset,
                profile_b_lineage_seq: newLineageSeq
              },
              nowIso
            )
          );
          return makeResult(200, {
            reconciled: true,
            patient_uid: req.patient_uid,
            source_episode_id: req.source_episode_id,
            target_episode_id: req.target_episode_id,
            reassigned_case_ids: reassignedCaseIds.slice().sort(),
            ercp_session_indices: epErcpSessions,
            store_epoch: ramStore.store_epoch,
            profile_b_lineage_seq: newLineageSeq
          });
        }

        /* Simulated in-memory atomic restore (0 file input, 0 passphrase input) */
        if (method === 'POST' && path === '/api/admin/demo-simulate-restore') {
          const req = bodyObj || {};
          const preserveUsers = req.preserve_current_users !== false;
          const keyPolicy = req.key_mismatch_policy === 'REKEY_AND_BUMP_DATASET_EPOCH' ? 'REKEY_AND_BUMP_DATASET_EPOCH' : 'REJECT';
          const liveVer = verifyAuditChain(ramStore.audit_chain);
          if (!liveVer.valid) {
            return makeResult(409, { detail: { code: 'LIVE_AUDIT_CHAIN_BROKEN', message: 'Chuỗi kiểm toán hiện hành không toàn vẹn.' } });
          }
          const backupCand = deepClone(cleanSeedSnapshot);
          const backupVer = verifyAuditChain(backupCand.audit_chain);
          const nowIso = currentUtcIso();
          const liveEpoch = ramStore.store_epoch;
          const newStoreEpoch = Math.max(liveEpoch, Number(backupCand.store_epoch || 1)) + 1;
          const liveDsEpoch = Number(ramStore.settings.export_dataset_epoch || 1);
          const newDsEpoch = keyPolicy === 'REKEY_AND_BUMP_DATASET_EPOCH' ? (liveDsEpoch + 1) : liveDsEpoch;

          const displacedJson = JSON.stringify(ramStore);
          const preRestoreSha = sha256Hex(displacedJson);
          const tsSlug = nowIso.replace(/[^0-9]/g, '').slice(0, 14) || '20261101000000';
          const preRestoreFilename = 'pre_restore_e' + liveEpoch + '_' + tsSlug + '.json';
          virtualBackupFiles[preRestoreFilename] = displacedJson;

          const vaultSyntheticBlobSha = sha256Hex('endolog_demo_virtual_vault:' + canonicalJson(backupCand.audit_chain));
          if (preserveUsers) {
            const preservedUsers = deepClone(ramStore.users);
            Object.values(preservedUsers).forEach(function (u) {
              u.auth_version = Number(u.auth_version || 1) + 1;
            });
            backupCand.users = preservedUsers;
          }

          backupCand.store_epoch = newStoreEpoch;
          backupCand.settings.export_dataset_epoch = newDsEpoch;
          backupCand.settings.profile_b_lineage_seq = Math.max(
            Number(ramStore.settings.profile_b_lineage_seq || 1),
            Number(backupCand.settings.profile_b_lineage_seq || 1)
          );
          backupCand.audit_lineage_bridges = (ramStore.audit_lineage_bridges || []).slice();

          const bridgeRecord = {
            restored_at_utc: nowIso,
            actor_username: actor.username,
            vault_blob_sha256: vaultSyntheticBlobSha,
            backup_pre_append_head_hash: backupVer.head_hash,
            backup_pre_append_seq: backupCand.audit_chain.length,
            displaced_live_head_hash: liveVer.head_hash,
            displaced_live_seq: ramStore.audit_chain.length,
            pre_restore_filename: preRestoreFilename,
            pre_restore_sha256: preRestoreSha,
            previous_store_epoch: liveEpoch,
            new_store_epoch: newStoreEpoch,
            preserve_current_users: preserveUsers,
            key_mismatch_policy: keyPolicy
          };
          backupCand.audit_lineage_bridges.push(bridgeRecord);
          backupCand.audit_chain.push(
            buildAuditEntry(
              backupCand.audit_chain,
              actor.username,
              actor.role,
              'RESTORE_PROFILE_A_ENCRYPTED',
              'STORE',
              'endolog_state_v1',
              {
                vault_blob_sha256: vaultSyntheticBlobSha,
                backup_pre_append_head_hash: backupVer.head_hash,
                backup_pre_append_seq: bridgeRecord.backup_pre_append_seq,
                displaced_live_head_hash: liveVer.head_hash,
                displaced_live_seq: bridgeRecord.displaced_live_seq,
                pre_restore_filename: preRestoreFilename,
                pre_restore_sha256: preRestoreSha,
                imported_lineage_artifact_count: 0,
                new_store_epoch: newStoreEpoch,
                export_dataset_epoch: newDsEpoch,
                preserve_current_users: preserveUsers,
                key_mismatch_policy: keyPolicy
              },
              nowIso
            )
          );

          ramStore = backupCand;
          if (!preserveUsers) activePersonaKey = null;
          return makeResult(200, {
            restored: true,
            new_store_epoch: newStoreEpoch,
            export_dataset_epoch: newDsEpoch,
            preserve_current_users: preserveUsers,
            reauthentication_required: !preserveUsers,
            pre_restore_filename: preRestoreFilename,
            pre_restore_sha256: preRestoreSha,
            imported_lineage_artifact_count: 0,
            restored_case_count: Object.values(ramStore.cases).filter(function (c) { return (c.record_status || 'ACTIVE') === 'ACTIVE'; }).length,
            actor_user: preserveUsers ? sanitizeUser(ramStore.users[actor.username]) : null,
            expires_in_seconds: 900
          });
        }
      }

      /* Remaining locked endpoints (password change/reset, Profile A file upload/download) */
      return makeResult(403, {
        detail: {
          code: 'STATIC_DEMO_ZERO_PHI_LOCKED',
          message: 'Chức năng mật khẩu và tệp sao lưu mã hóa ngoài (.endolog.enc) bị khóa cứng trên GitHub Pages nhằm bảo đảm Zero-PHI.'
        }
      });
    }

    return {
      handleRequest: handleRequest,
      resetToInitialOd05: resetToInitialOd05,
      getActivePersonaKey: function () { return activePersonaKey; },
      setActivePersonaKey: function (k) { activePersonaKey = k; },
      setPersona: function (k) { activePersonaKey = k; },
      getStoreSnapshot: function () { return deepClone(ramStore); },
      getPatientCatalog: function () { return deepClone(bundle.synthetic_patient_catalog || []); }
    };
  }
"""


def _build_demo_synthetic_adapter_js(base_path: str, version: str) -> str:
    """Build UMD Synthetic RAM Engine + Browser UI Controller for dist_pages/js/demo-synthetic-adapter.js."""
    bundle_url = f"{base_path}data/od05_precomputed_bundle.json?v={version}"
    protected_note_map_json = json.dumps({k: True for k in sorted(PROTECTED_NOTE_FIELDS)}, ensure_ascii=False)
    header_js = f"""/* EndoLog Interactive Virtual-Patient Sandbox Adapter (Gate C · Phương án G1+ / v{version})
 * - Chạy 100% trên bộ nhớ RAM trình duyệt; 0 request mạng tới /api/*; 0 lưu dữ liệu lâm sàng vào Web Storage / IndexedDB.
 * - Khóa cứng #el-f-full-name, #el-f-hospital-mrn và #el-f-operator ở chế độ readonly; chọn bệnh nhân ảo từ danh mục chuẩn hóa.
 * - Xuất UMD createSyntheticRamEngine cho kiểm thử đối chiếu vi phân 100% Python FastAPI <-> Node.js. */

(function (root) {{
  'use strict';
  const PROTECTED_NOTE_FIELDS = {protected_note_map_json};
"""
    browser_controller_js = f"""
  /* =========================================================================
   * 5. UMD EXPORT FOR NODE.JS DIFFERENTIAL PARITY TESTS
   * ========================================================================= */
  if (typeof module !== 'undefined' && module.exports) {{
    module.exports = {{
      createSyntheticRamEngine: createSyntheticRamEngine,
      sha256Hex: sha256Hex,
      hmacSha256Hex: hmacSha256Hex,
      pyRound: pyRound,
      canonicalJson: canonicalJson
    }};
  }}

  if (typeof window === 'undefined' || typeof document === 'undefined') {{
    return;
  }}

  /* =========================================================================
   * 6. BROWSER INTERACTIVE SANDBOX CONTROLLER (GITHUB PAGES)
   * ========================================================================= */
  window.ENDOLOG_STATIC_DEMO = true;
  window.ENDOLOG_INTERACTIVE_SANDBOX = true;
  const BASE_PATH = {json.dumps(base_path)};
  const BUNDLE_URL = {json.dumps(bundle_url)};
  const DEFAULT_MERGE_REASON = {json.dumps(DEFAULT_MERGE_REASON_VI, ensure_ascii=False)};
  const DEFAULT_RECONCILE_REASON = {json.dumps(DEFAULT_RECONCILE_REASON_VI, ensure_ascii=False)};

  const realFetch = window.fetch.bind(window);
  let bundlePromise = null;
  let enginePromise = null;
  let liveEngine = null;

  const initialPersonaFromUrl = (function () {{
    try {{
      const p = new URLSearchParams(window.location.search);
      if (p.get('login') === '1') return null;
      if (p.get('role') === 'superadmin') return 'vukhuongan';
      return 'nguyenbinhan';
    }} catch (_e) {{
      return 'nguyenbinhan';
    }}
  }})();

  const demoAuditStats = {{
    staticDemo: true,
    interactiveSandbox: true,
    basePath: BASE_PATH,
    interceptedApiCalls: 0,
    mutatedApiCalls: 0,
    blockedWriteCalls: 0,
    lockModalOpenCount: 0,
    resetStoreCount: 0,
    simulatedRestoreCount: 0,
    csvDownloadCount: 0,
    lastLockedActionLabel: ''
  }};

  function loadBundle() {{
    if (!bundlePromise) {{
      bundlePromise = realFetch(BUNDLE_URL, {{ credentials: 'same-origin' }}).then(function (resp) {{
        if (!resp.ok) {{
          throw new Error('DEMO_BUNDLE_LOAD_FAILED_' + resp.status);
        }}
        return resp.json();
      }});
    }}
    return bundlePromise;
  }}

  function ensureEngine() {{
    if (!enginePromise) {{
      enginePromise = loadBundle().then(function (bundle) {{
        liveEngine = createSyntheticRamEngine(bundle, {{
          initialPersonaKey: initialPersonaFromUrl,
          resetOnLogout: true,
          enforceSyntheticIdentity: true
        }});
        populateVirtualPatientSelect(liveEngine.getPatientCatalog());
        updateBannerRoleUi();
        return liveEngine;
      }});
    }}
    return enginePromise;
  }}

  function normalizeApiPath(rawInput) {{
    const rawUrl = typeof rawInput === 'string'
      ? rawInput
      : (rawInput && typeof rawInput.url === 'string' ? rawInput.url : String(rawInput || ''));
    let parsed;
    try {{
      parsed = new URL(rawUrl, window.location.origin);
    }} catch (_err) {{
      return null;
    }}
    if (parsed.origin !== window.location.origin) {{
      return null;
    }}
    let path = parsed.pathname || '/';
    const strippedPrefix = BASE_PATH.endsWith('/') ? BASE_PATH.slice(0, -1) : BASE_PATH;
    if (strippedPrefix && path.startsWith(strippedPrefix + '/api/')) {{
      path = path.slice(strippedPrefix.length);
    }}
    if (path === '/api' || path.startsWith('/api/')) {{
      return path + (parsed.search || '');
    }}
    return null;
  }}

  function extractHeadersMap(input, init) {{
    const map = {{}};
    const src = (init && init.headers) || (input && input.headers) || null;
    if (!src) return map;
    if (typeof Headers !== 'undefined' && src instanceof Headers) {{
      src.forEach(function (v, k) {{ map[String(k).toLowerCase()] = String(v); }});
    }} else if (Array.isArray(src)) {{
      src.forEach(function (pair) {{
        if (pair && pair.length >= 2) map[String(pair[0]).toLowerCase()] = String(pair[1]);
      }});
    }} else if (typeof src === 'object') {{
      Object.keys(src).forEach(function (k) {{ map[String(k).toLowerCase()] = String(src[k]); }});
    }}
    return map;
  }}

  function ensureReadonlyAdminReasons() {{
    const mEl = document.getElementById('el-admin-merge-reason');
    if (mEl && !mEl.value) {{
      mEl.value = DEFAULT_MERGE_REASON;
    }}
    const rEl = document.getElementById('el-admin-reconcile-reason');
    if (rEl && !rEl.value) {{
      rEl.value = DEFAULT_RECONCILE_REASON;
    }}
  }}

  function updateBannerRoleUi() {{
    const roleBtn = document.getElementById('el-btn-demo-switch-role');
    const resetBtn = document.getElementById('el-btn-demo-reset-store');
    const persona = liveEngine ? liveEngine.getActivePersonaKey() : initialPersonaFromUrl;
    if (roleBtn) {{
      if (persona === 'vukhuongan') {{
        roleBtn.textContent = 'Vai trò: Superadmin · Đổi sang BS nội soi';
      }} else if (persona === 'nguyenbinhan') {{
        roleBtn.textContent = 'Vai trò: BS nội soi · Đổi sang Superadmin';
      }} else {{
        roleBtn.textContent = 'Mở nhanh quyền Superadmin';
      }}
    }}
    if (resetBtn && liveEngine) {{
      const snap = liveEngine.getStoreSnapshot();
      const cnt = Object.values(snap.cases || {{}}).filter(function (c) {{ return (c.record_status || 'ACTIVE') === 'ACTIVE'; }}).length;
      resetBtn.textContent = 'Đặt lại 5 ca gốc (' + cnt + ' ca trên RAM)';
    }}
  }}

  window.fetch = async function (input, init) {{
    const apiPathWithQuery = normalizeApiPath(input);
    if (!apiPathWithQuery) {{
      return realFetch(input, init);
    }}

    demoAuditStats.interceptedApiCalls += 1;
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    const hdrs = extractHeadersMap(input, init);
    const bodyRaw = (init && init.body !== undefined) ? init.body : undefined;
    const eng = await ensureEngine();

    if (method !== 'GET') {{
      demoAuditStats.mutatedApiCalls += 1;
    }}
    if (method === 'POST' && apiPathWithQuery.startsWith('/api/auth/logout')) {{
      lockReturnFocusEl = null;
      lockOpenedFromLogin = false;
      closeDemoLockModal();
    }}

    const result = eng.handleRequest(method, apiPathWithQuery, hdrs, bodyRaw);
    if (result.status === 403 && result.body && result.body.detail && result.body.detail.code === 'STATIC_DEMO_ZERO_PHI_LOCKED') {{
      demoAuditStats.blockedWriteCalls += 1;
    }}
    if (apiPathWithQuery.startsWith('/api/admin/patients') && result.status === 200) {{
      window.setTimeout(ensureReadonlyAdminReasons, 0);
    }}
    window.setTimeout(updateBannerRoleUi, 0);

    const respHeaders = Object.assign({{}}, result.headers || {{}});
    if (!result.isRawText && !respHeaders['Content-Type']) {{
      respHeaders['Content-Type'] = 'application/json; charset=utf-8';
    }}
    const payloadStr = result.isRawText ? String(result.body) : JSON.stringify(result.body);
    return new Response(payloadStr, {{
      status: result.status,
      headers: respHeaders
    }});
  }};

  /* =========================================================================
   * 7. VIRTUAL PATIENT PICKER & DRAWER / ROLE / RESTORE UI SYNC
   * ========================================================================= */
  let catalogById = {{}};
  let catalogList = [];

  function populateVirtualPatientSelect(catalog) {{
    catalogList = Array.isArray(catalog) ? catalog : [];
    catalogById = {{}};
    catalogList.forEach(function (item) {{
      catalogById[item.preset_id] = item;
    }});
    const sel = document.getElementById('el-f-demo-patient-picker');
    if (!sel) return;
    sel.replaceChildren();

    const groups = [
      ['NEW_VIRTUAL', 'Bệnh nhân ảo mới (BN. Giả Lập 06–20 · sẵn mã HS giả lập)'],
      ['DUPLICATE_TEST', 'Kiểm thử phát hiện trùng ngoại trú (không mã HS)'],
      ['EXISTING_OD05', 'Hồ sơ gốc chuẩn OD-05 (thêm ca dọc / ERCP nội trú lần 2)']
    ];
    groups.forEach(function (gPair) {{
      const gCode = gPair[0];
      const gLabel = gPair[1];
      const items = catalogList.filter(function (x) {{ return x.group === gCode; }});
      if (!items.length) return;
      const optGroup = document.createElement('optgroup');
      optGroup.label = gLabel;
      items.forEach(function (it) {{
        const opt = document.createElement('option');
        opt.value = it.preset_id;
        opt.textContent = it.label;
        optGroup.appendChild(opt);
      }});
      sel.appendChild(optGroup);
    }});
  }}

  function setInputSilent(id, val, fireNonBubblingInput) {{
    const el = document.getElementById(id);
    if (!el) return;
    el.value = String(val === null || val === undefined ? '' : val);
    if (fireNonBubblingInput) {{
      el.dispatchEvent(new Event('input', {{ bubbles: false }}));
    }}
  }}

  function applyVirtualPresetToForm(preset, isManualUserChange) {{
    if (!preset) return;
    setInputSilent('el-f-full-name', preset.full_name, true);
    setInputSilent('el-f-birth-year', preset.birth_year, true);
    setInputSilent('el-f-hospital-mrn', preset.hospital_mrn || '', false);

    const sexBtn = document.querySelector('[data-form-sex="' + preset.sex + '"]');
    if (sexBtn && sexBtn.getAttribute('aria-pressed') !== 'true') {{
      sexBtn.click();
    }}

    if (isManualUserChange) {{
      const activeTrackBtn = document.querySelector('[data-form-track][aria-pressed="true"]');
      const currentTrack = activeTrackBtn ? activeTrackBtn.getAttribute('data-form-track') : 'COL';
      const targetCare = currentTrack === 'ERCP' ? 'inpatient' : (preset.default_care_setting === 'INPATIENT' ? 'inpatient' : 'outpatient');
      const careBtn = document.querySelector('[data-form-care="' + targetCare + '"]');
      if (careBtn && careBtn.getAttribute('aria-pressed') !== 'true') {{
        careBtn.click();
      }}
    }}
  }}

  function pickDefaultFreshVirtualPreset() {{
    const snap = liveEngine ? liveEngine.getStoreSnapshot() : null;
    const usedMrns = new Set();
    if (snap && snap.patients) {{
      Object.values(snap.patients).forEach(function (p) {{
        if (p && p.hospital_mrn) usedMrns.add(String(p.hospital_mrn).trim().toUpperCase());
      }});
    }}
    /* On auto-open, prefer sex === 'M' so drawerState.sex ('M') matches without clicking [data-form-sex] (keeps isDirty = false) */
    const unusedMale = catalogList.find(function (it) {{
      return it.group === 'NEW_VIRTUAL' && it.sex === 'M' && !usedMrns.has(String(it.hospital_mrn).toUpperCase());
    }});
    if (unusedMale) return unusedMale;
    const anyMale = catalogList.find(function (it) {{ return it.group === 'NEW_VIRTUAL' && it.sex === 'M'; }});
    return anyMale || catalogList[0] || null;
  }}

  function syncDrawerVirtualIdentityOnOpen() {{
    const patEditBox = document.getElementById('el-patient-edit-fields');
    if (!patEditBox || patEditBox.hidden) return;
    const sel = document.getElementById('el-f-demo-patient-picker');
    const linkedBanner = document.getElementById('el-linked-surv-banner');
    const isLinkedSurv = Boolean(linkedBanner && !linkedBanner.hidden);

    if (isLinkedSurv && liveEngine) {{
      const fnVal = (document.getElementById('el-f-full-name') && document.getElementById('el-f-full-name').value) || '';
      const byVal = Number((document.getElementById('el-f-birth-year') && document.getElementById('el-f-birth-year').value) || 0);
      const snap = liveEngine.getStoreSnapshot();
      const matchedPat = Object.values(snap.patients || {{}}).find(function (p) {{
        return (p.status || 'ACTIVE') === 'ACTIVE' &&
          normalizeName(p.full_name || '') === normalizeName(fnVal) &&
          Number(p.birth_year || 0) === byVal;
      }});
      if (matchedPat) {{
        setInputSilent('el-f-hospital-mrn', matchedPat.hospital_mrn || '', false);
      }}
      if (sel) {{
        const matchedPreset = catalogList.find(function (it) {{
          return normalizeName(it.full_name) === normalizeName(fnVal) && Number(it.birth_year) === byVal && Boolean(it.hospital_mrn) === Boolean(matchedPat && matchedPat.hospital_mrn);
        }});
        if (matchedPreset) sel.value = matchedPreset.preset_id;
        sel.disabled = true;
      }}
      return;
    }}

    if (sel) sel.disabled = false;
    const chosen = pickDefaultFreshVirtualPreset();
    if (chosen) {{
      if (sel) sel.value = chosen.preset_id;
      applyVirtualPresetToForm(chosen, false);
    }}
  }}

  function closeOpenOverlaysBeforeGlobalAction() {{
    closeDemoLockModal();
    const dupCancel = document.getElementById('el-btn-dup-cancel');
    const dupWrap = document.getElementById('el-dup-modal-backdrop');
    if (dupWrap && !dupWrap.hidden && dupCancel) dupCancel.click();

    const detailClose = document.getElementById('el-btn-detail-close');
    const detailWrap = document.getElementById('el-detail-modal-backdrop');
    if (detailWrap && !detailWrap.hidden && detailClose) detailClose.click();

    const vaultClose = document.getElementById('el-btn-vault-close');
    const vaultWrap = document.getElementById('el-vault-modal-backdrop');
    if (vaultWrap && !vaultWrap.hidden && vaultClose) vaultClose.click();

    const drawerWrap = document.getElementById('el-case-drawer-backdrop');
    if (drawerWrap && !drawerWrap.hidden) {{
      const drawerClose = document.getElementById('el-drawer-close');
      if (drawerClose) drawerClose.click();
      const dirtyWrap = document.getElementById('el-dirty-modal-backdrop');
      const dirtyDiscard = document.getElementById('el-btn-dirty-discard');
      if (dirtyWrap && !dirtyWrap.hidden && dirtyDiscard) dirtyDiscard.click();
    }}
  }}

  async function switchSandboxRole(forcedTargetKey) {{
    await ensureEngine();
    closeOpenOverlaysBeforeGlobalAction();
    const cur = liveEngine ? liveEngine.getActivePersonaKey() : null;
    const nextKey = forcedTargetKey || (cur === 'vukhuongan' ? 'nguyenbinhan' : 'vukhuongan');
    const btnId = nextKey === 'vukhuongan' ? 'el-btn-dev-bypass-admin' : 'el-btn-dev-bypass';
    const trigger = document.getElementById(btnId);
    if (trigger) trigger.click();
  }}

  async function resetSandboxToInitialOd05() {{
    const eng = await ensureEngine();
    closeOpenOverlaysBeforeGlobalAction();
    eng.resetToInitialOd05();
    demoAuditStats.resetStoreCount += 1;
    const cur = eng.getActivePersonaKey();
    if (cur) {{
      const btnId = cur === 'vukhuongan' ? 'el-btn-dev-bypass-admin' : 'el-btn-dev-bypass';
      const trigger = document.getElementById(btnId);
      if (trigger) trigger.click();
    }}
    updateBannerRoleUi();
  }}

  async function runSimulatedAtomicRestore() {{
    const eng = await ensureEngine();
    if (eng.getActivePersonaKey() !== 'vukhuongan') return;
    const sw = document.getElementById('el-sw-preserve-users');
    const polSel = document.getElementById('el-admin-key-policy');
    const preserveUsers = !sw || sw.getAttribute('aria-pressed') !== 'false';
    const keyPolicy = (polSel && polSel.value) || 'REJECT';
    const prevAgeEl = document.querySelector('[data-age-toggle][aria-pressed="true"]');
    const prevAgeVal = prevAgeEl ? prevAgeEl.getAttribute('data-age-toggle') : null;
    const prevCusumEl = document.querySelector('[data-cusum-metric][aria-pressed="true"]');
    const prevCusumVal = prevCusumEl ? prevCusumEl.getAttribute('data-cusum-metric') : null;

    const resp = await window.fetch('/api/admin/demo-simulate-restore', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        preserve_current_users: preserveUsers,
        key_mismatch_policy: keyPolicy
      }})
    }});
    const data = await resp.json().catch(function () {{ return null; }});
    if (!resp.ok || !data) return;
    demoAuditStats.simulatedRestoreCount += 1;

    if (data.reauthentication_required) {{
      /* Trigger 401 clean transition to login screen while preserving the newly restored store_epoch in RAM */
      const saveBtn = document.getElementById('el-btn-save-settings');
      if (saveBtn) saveBtn.click();
      window.setTimeout(function () {{
        const errBanner = document.getElementById('el-login-error');
        if (errBanner) {{
          errBanner.hidden = false;
          errBanner.className = 'el-error-banner';
          errBanner.textContent = 'Đã khôi phục kho sao lưu nguyên tử kèm bảng tài khoản trong bản sao lưu (kỷ nguyên kho #' + data.new_store_epoch + '). Vui lòng chọn lại vai trò để mở phiên mới.';
        }}
      }}, 80);
      return;
    }}

    const bypassAdmin = document.getElementById('el-btn-dev-bypass-admin');
    if (bypassAdmin) {{
      bypassAdmin.click();
      window.setTimeout(function () {{
        if (prevAgeVal) {{
          const ageBtn = document.querySelector('[data-age-toggle="' + prevAgeVal + '"]');
          if (ageBtn && ageBtn.getAttribute('aria-pressed') !== 'true') ageBtn.click();
        }}
        if (prevCusumVal) {{
          const cusumBtn = document.querySelector('[data-cusum-metric="' + prevCusumVal + '"]');
          if (cusumBtn && cusumBtn.getAttribute('aria-pressed') !== 'true') cusumBtn.click();
        }}
        const fb = document.getElementById('el-admin-restore-feedback');
        if (fb) {{
          fb.hidden = false;
          fb.className = 'el-admin-feedback el-admin-feedback--ok';
          fb.textContent = 'Đã mô phỏng khôi phục nguyên tử sang kỷ nguyên kho #' + data.new_store_epoch + ' (' + data.pre_restore_filename + ') và xác minh cầu nối SHA-256 trên RAM.';
        }}
      }}, 80);
    }}
  }}

  async function downloadProfileBCsvBlob() {{
    const resp = await window.fetch('/api/exports/profile-b?fmt=csv', {{ credentials: 'same-origin' }});
    if (!resp.ok) return;
    const csvText = await resp.text();
    const blob = new Blob([csvText], {{ type: 'text/csv;charset=utf-8' }});
    const objUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objUrl;
    link.download = 'endolog_profile_b_longitudinal.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {{ URL.revokeObjectURL(objUrl); }}, 1000);
    demoAuditStats.csvDownloadCount += 1;
  }}

  /* =========================================================================
   * 8. ZERO-PHI WRITE-LOCK MODAL FOR PASSWORD / VAULT FILE / XLSX
   * ========================================================================= */
  let lockReturnFocusEl = null;
  let lockOpenedFromLogin = false;

  function setBackgroundInertForLockModal(isLockedOpen) {{
    const shellEl = document.getElementById('el-app-shell');
    const loginEl = document.getElementById('el-login-screen');
    const detailModalEl = document.getElementById('el-detail-modal');
    const detailBackdropEl = document.getElementById('el-detail-modal-backdrop');
    const detailIsOpen = Boolean(detailBackdropEl && !detailBackdropEl.hidden);

    if (detailModalEl && detailIsOpen) {{
      detailModalEl.inert = isLockedOpen;
      if (isLockedOpen) detailModalEl.setAttribute('inert', '');
      else detailModalEl.removeAttribute('inert');
    }}
    if (shellEl) {{
      const keepShellInert = !shellEl.hidden && (isLockedOpen || detailIsOpen);
      shellEl.inert = keepShellInert;
      if (keepShellInert) shellEl.setAttribute('inert', '');
      else shellEl.removeAttribute('inert');
    }}
    if (loginEl) {{
      const keepLoginInert = !loginEl.hidden && isLockedOpen;
      loginEl.inert = keepLoginInert;
      if (keepLoginInert) loginEl.setAttribute('inert', '');
      else loginEl.removeAttribute('inert');
    }}
  }}

  function openDemoLockModal(actionLabel, triggerEl) {{
    const backdrop = document.getElementById('el-demo-lock-modal-backdrop');
    const loginEl = document.getElementById('el-login-screen');
    const pill = document.getElementById('el-demo-lock-action-label');
    const closeBtn = document.getElementById('el-btn-demo-lock-close');
    if (!backdrop) return;

    demoAuditStats.lockModalOpenCount += 1;
    demoAuditStats.lastLockedActionLabel = String(actionLabel || 'Thao tác khóa bảo mật Zero-PHI');
    lockReturnFocusEl = triggerEl || document.activeElement;
    lockOpenedFromLogin = Boolean(loginEl && !loginEl.hidden);

    if (pill) {{
      pill.textContent = 'Chức năng đang khóa: ' + demoAuditStats.lastLockedActionLabel;
    }}
    backdrop.hidden = false;
    setBackgroundInertForLockModal(true);
    if (closeBtn && typeof closeBtn.focus === 'function') {{
      closeBtn.focus();
    }}
  }}

  function closeDemoLockModal() {{
    const backdrop = document.getElementById('el-demo-lock-modal-backdrop');
    if (!backdrop || backdrop.hidden) return;
    backdrop.hidden = true;
    lockOpenedFromLogin = false;
    setBackgroundInertForLockModal(false);
    const loginEl = document.getElementById('el-login-screen');
    if (
      lockReturnFocusEl &&
      lockReturnFocusEl.isConnected &&
      (!lockReturnFocusEl.closest || !lockReturnFocusEl.closest('[hidden]')) &&
      !lockReturnFocusEl.disabled &&
      typeof lockReturnFocusEl.focus === 'function'
    ) {{
      try {{
        lockReturnFocusEl.focus();
      }} catch (_err) {{
        /* ignore */
      }}
    }} else if (loginEl && !loginEl.hidden) {{
      const bypassBtn = document.getElementById('el-btn-dev-bypass');
      if (bypassBtn && !bypassBtn.disabled && typeof bypassBtn.focus === 'function') {{
        try {{
          bypassBtn.focus();
        }} catch (_err) {{
          /* ignore */
        }}
      }}
    }}
    lockReturnFocusEl = null;
  }}

  const LOCKED_BUTTON_LABELS = {{
    'el-btn-change-password': 'Đổi mật khẩu xác thực cá nhân',
    'el-btn-pwd-submit': 'Cập nhật mật khẩu',
    'el-btn-open-vault-backup': 'Sao lưu kho mã hóa ngoại tuyến (Hồ sơ A · .endolog.enc)',
    'el-btn-vault-download': 'Tải tệp sao lưu mã hóa (Hồ sơ A)',
    'el-btn-export-xlsx': 'Xuất tệp nhị phân XLSX (vui lòng dùng nút Hồ sơ B · CSV ngay bên cạnh)',
    'el-btn-pick-restore-file': 'Tải tệp sao lưu ngoài (.endolog.enc) — dùng nút Mô phỏng khôi phục nguyên tử',
    'el-btn-run-restore': 'Khôi phục từ tệp ngoài (.endolog.enc) — dùng nút Mô phỏng khôi phục nguyên tử bên cạnh',
    'el-btn-run-reset-password': 'Đặt lại mật khẩu xác thực tài khoản'
  }};

  function resolveLockedTrigger(target) {{
    if (!target || typeof target.closest !== 'function') return null;
    if (target.closest('#el-btn-demo-lock-close, #el-btn-demo-lock-ok')) return null;
    const ids = Object.keys(LOCKED_BUTTON_LABELS);
    for (let i = 0; i < ids.length; i += 1) {{
      const matched = target.closest('#' + ids[i]);
      if (matched) return {{ el: matched, label: LOCKED_BUTTON_LABELS[ids[i]] }};
    }}
    return null;
  }}

  document.addEventListener('click', function (ev) {{
    const backdrop = document.getElementById('el-demo-lock-modal-backdrop');
    if (backdrop && !backdrop.hidden) {{
      if (ev.target === backdrop || (ev.target && ev.target.closest && ev.target.closest('#el-btn-demo-lock-close, #el-btn-demo-lock-ok'))) {{
        ev.preventDefault();
        ev.stopPropagation();
        closeDemoLockModal();
        return;
      }}
    }}

    if (ev.target && typeof ev.target.closest === 'function') {{
      if (ev.target.closest('#el-btn-demo-switch-role')) {{
        ev.preventDefault();
        switchSandboxRole(null);
        return;
      }}
      if (ev.target.closest('#el-btn-demo-elevate-superadmin')) {{
        ev.preventDefault();
        switchSandboxRole('vukhuongan');
        return;
      }}
      if (ev.target.closest('#el-btn-demo-reset-store')) {{
        ev.preventDefault();
        resetSandboxToInitialOd05();
        return;
      }}
      if (ev.target.closest('#el-btn-demo-sim-restore')) {{
        ev.preventDefault();
        runSimulatedAtomicRestore();
        return;
      }}
      if (ev.target.closest('#el-btn-export-csv')) {{
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
        downloadProfileBCsvBlob();
        return;
      }}
      /* If user switches to Inpatient or ERCP while on the no-MRN duplicate preset, auto-fill a synthetic MRN preset */
      const careInpatientBtn = ev.target.closest('[data-form-care="inpatient"], [data-form-track="ERCP"]');
      if (careInpatientBtn) {{
        window.setTimeout(function () {{
          const mrnInp = document.getElementById('el-f-hospital-mrn');
          const patEditBox = document.getElementById('el-patient-edit-fields');
          if (patEditBox && !patEditBox.hidden && mrnInp && !mrnInp.value.trim()) {{
            const fallback = catalogById['syn_2610'] || pickDefaultFreshVirtualPreset();
            const sel = document.getElementById('el-f-demo-patient-picker');
            if (fallback) {{
              if (sel) sel.value = fallback.preset_id;
              setInputSilent('el-f-full-name', fallback.full_name, true);
              setInputSilent('el-f-birth-year', fallback.birth_year, true);
              setInputSilent('el-f-hospital-mrn', fallback.hospital_mrn, false);
              const fbSexBtn = document.querySelector('[data-form-sex="' + fallback.sex + '"]');
              if (fbSexBtn && fbSexBtn.getAttribute('aria-pressed') !== 'true') {{
                fbSexBtn.click();
              }}
            }}
          }}
        }}, 0);
      }}
      if (ev.target.closest('#el-btn-clear-surv-link')) {{
        window.setTimeout(syncDrawerVirtualIdentityOnOpen, 0);
      }}
    }}

    const locked = resolveLockedTrigger(ev.target);
    if (locked) {{
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();
      openDemoLockModal(locked.label, locked.el);
    }}
  }}, true);

  document.addEventListener('click', function (ev) {{
    if (ev.target && typeof ev.target.closest === 'function' && ev.target.closest('#el-btn-clear-surv-link')) {{
      syncDrawerVirtualIdentityOnOpen();
    }}
  }}, false);

  document.addEventListener('change', function (ev) {{
    if (ev.target && ev.target.id === 'el-f-demo-patient-picker') {{
      const preset = catalogById[ev.target.value];
      if (preset) {{
        applyVirtualPresetToForm(preset, true);
      }}
    }}
  }}, true);

  document.addEventListener('submit', function (ev) {{
    const formEl = ev.target;
    if (formEl && formEl.id === 'el-login-form') {{
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();
      openDemoLockModal('Đăng nhập bằng mật khẩu (đã gỡ trên Sandbox Zero-PHI)', formEl);
    }}
  }}, true);

  window.addEventListener('keydown', function (ev) {{
    const backdrop = document.getElementById('el-demo-lock-modal-backdrop');
    if (!backdrop || backdrop.hidden) return;
    if (ev.key === 'Escape') {{
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();
      closeDemoLockModal();
      return;
    }}
    if (ev.key === 'Tab') {{
      const modal = document.getElementById('el-demo-lock-modal');
      if (!modal) return;
      const focusable = Array.from(modal.querySelectorAll('button:not([disabled])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (ev.shiftKey && document.activeElement === first) {{
        ev.preventDefault();
        last.focus();
      }} else if (!ev.shiftKey && document.activeElement === last) {{
        ev.preventDefault();
        first.focus();
      }}
    }}
  }}, true);

  function purgeForbiddenInputs(rootNode) {{
    if (!rootNode || typeof rootNode.querySelectorAll !== 'function') return;
    rootNode.querySelectorAll('input[type="password"], input[type="file"]').forEach(function (inp) {{
      inp.remove();
    }});
  }}

  function initDomObservers() {{
    purgeForbiddenInputs(document);
    ensureEngine().catch(function () {{}});

    const loginEl = document.getElementById('el-login-screen');
    if (loginEl && typeof MutationObserver === 'function') {{
      const loginObs = new MutationObserver(function () {{
        if (!loginEl.hidden && !lockOpenedFromLogin) {{
          lockReturnFocusEl = null;
          closeDemoLockModal();
        }}
      }});
      loginObs.observe(loginEl, {{ attributes: true, attributeFilter: ['hidden'] }});
    }}

    const drawerBackdrop = document.getElementById('el-case-drawer-backdrop');
    if (drawerBackdrop && typeof MutationObserver === 'function') {{
      let wasOpen = !drawerBackdrop.hidden;
      const drawerObs = new MutationObserver(function () {{
        const nowOpen = !drawerBackdrop.hidden;
        if (nowOpen && !wasOpen) {{
          syncDrawerVirtualIdentityOnOpen();
        }}
        wasOpen = nowOpen;
      }});
      drawerObs.observe(drawerBackdrop, {{ attributes: true, attributeFilter: ['hidden'] }});
    }}

    const linkedSurvBanner = document.getElementById('el-linked-surv-banner');
    if (linkedSurvBanner && typeof MutationObserver === 'function') {{
      const survBannerObs = new MutationObserver(function () {{
        if (linkedSurvBanner.hidden && drawerBackdrop && !drawerBackdrop.hidden) {{
          syncDrawerVirtualIdentityOnOpen();
        }}
      }});
      survBannerObs.observe(linkedSurvBanner, {{ attributes: true, attributeFilter: ['hidden'] }});
    }}

    if (typeof MutationObserver === 'function') {{
      const bodyObs = new MutationObserver(function (mutations) {{
        for (let i = 0; i < mutations.length; i += 1) {{
          const added = mutations[i].addedNodes;
          for (let j = 0; j < added.length; j += 1) {{
            const node = added[j];
            if (node && node.nodeType === 1) {{
              if (node.tagName === 'INPUT') {{
                const t = String(node.getAttribute('type') || '').toLowerCase();
                if (t === 'password' || t === 'file') {{
                  node.remove();
                  continue;
                }}
              }}
              purgeForbiddenInputs(node);
            }}
          }}
        }}
      }});
      bodyObs.observe(document.documentElement, {{ childList: true, subtree: true }});
    }}
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initDomObservers, {{ once: true }});
  }} else {{
    initDomObservers();
  }}

  window.__ENDOLOG_DEMO_AUDIT__ = {{
    getStats: function () {{
      const snap = liveEngine ? liveEngine.getStoreSnapshot() : null;
      return Object.assign({{}}, demoAuditStats, {{
        activePersonaKey: liveEngine ? liveEngine.getActivePersonaKey() : initialPersonaFromUrl,
        storeEpoch: snap ? snap.store_epoch : 1,
        activeCaseCount: snap ? Object.values(snap.cases || {{}}).filter(function (c) {{ return (c.record_status || 'ACTIVE') === 'ACTIVE'; }}).length : 5,
        passwordInputCount: document.querySelectorAll('input[type="password"]').length,
        fileInputCount: document.querySelectorAll('input[type="file"]').length,
        fullNameReadonly: Boolean(document.getElementById('el-f-full-name') && document.getElementById('el-f-full-name').readOnly),
        hospitalMrnReadonly: Boolean(document.getElementById('el-f-hospital-mrn') && document.getElementById('el-f-hospital-mrn').readOnly),
        operatorReadonly: Boolean(document.getElementById('el-f-operator') && document.getElementById('el-f-operator').readOnly)
      }});
    }},
    resetToInitialOd05: resetSandboxToInitialOd05,
    switchSandboxRole: switchSandboxRole,
    openDemoLockModal: openDemoLockModal,
    closeDemoLockModal: closeDemoLockModal
  }};
}})(typeof globalThis !== 'undefined' ? globalThis : this);
"""
    return header_js + _DEMO_ENGINE_CORE_JS + _DEMO_ENGINE_SERVICE_JS + browser_controller_js


def _transform_index_html(raw_html: str, base_path: str, version: str) -> str:
    """Transform src/endolog/static/index.html into dist_pages/index.html with Virtual Patient Picker & Zero-PHI locks."""
    html = raw_html

    # 1. Rewrite head asset URLs to base_path & inject demo-showcase.css
    html = _assert_replace_once(
        html,
        '  <link rel="icon" type="image/svg+xml" href="/icons/favicon.svg">\n'
        '  <link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">\n'
        '  <link rel="manifest" href="/manifest.json">\n'
        f'  <link rel="stylesheet" href="/css/fonts.css?v={version}">\n'
        f'  <link rel="stylesheet" href="/css/tokens.css?v={version}">\n'
        f'  <link rel="stylesheet" href="/css/app.css?v={version}">',
        f'  <link rel="icon" type="image/svg+xml" href="{base_path}icons/favicon.svg">\n'
        f'  <link rel="apple-touch-icon" href="{base_path}icons/apple-touch-icon.png">\n'
        f'  <link rel="manifest" href="{base_path}manifest.json">\n'
        f'  <link rel="stylesheet" href="{base_path}css/fonts.css?v={version}">\n'
        f'  <link rel="stylesheet" href="{base_path}css/tokens.css?v={version}">\n'
        f'  <link rel="stylesheet" href="{base_path}css/app.css?v={version}">\n'
        f'  <link rel="stylesheet" href="{base_path}css/demo-showcase.css?v={version}">',
        "HEAD_ASSETS",
    )

    # 2. Inject sticky top Sandbox banner with Role Switcher + Reset 5 OD-05 Cases button
    banner_html = (
        '<body>\n'
        '  <div id="el-demo-showcase-banner" class="el-demo-showcase-banner" role="region" '
        'aria-label="Thanh điều khiển sandbox bệnh nhân ảo trên RAM">\n'
        '    <div class="el-demo-showcase-banner-inner">\n'
        '      <div class="el-demo-showcase-lead">\n'
        '        <span class="el-demo-showcase-badge">Sandbox RAM · Zero-PHI</span>\n'
        f'        <p class="el-demo-showcase-text">{SHOWCASE_BANNER_TEXT_VI}</p>\n'
        '      </div>\n'
        '      <div class="el-demo-showcase-actions">\n'
        '        <button type="button" id="el-btn-demo-switch-role" class="el-btn el-btn--secondary el-demo-banner-btn">'
        'Vai trò: BS nội soi · Đổi sang Superadmin</button>\n'
        '        <button type="button" id="el-btn-demo-reset-store" class="el-btn el-btn--secondary el-demo-banner-btn">'
        'Đặt lại 5 ca gốc (5 ca trên RAM)</button>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>'
    )
    html = _assert_replace_once(html, "<body>", banner_html, "SHOWCASE_BANNER")

    # 3. Replace login credential inputs with passwordless synthetic persona launcher buttons
    old_login_form = """      <form id="el-login-form" novalidate>
        <div class="el-form-field">
          <label class="el-form-label" for="el-login-username">Tài khoản bác sĩ</label>
          <input id="el-login-username" name="username" type="text" autocomplete="username" class="el-form-input" value="nguyenbinhan" required>
        </div>
        <div class="el-form-field">
          <label class="el-form-label" for="el-login-password">Mật khẩu xác thực</label>
          <input id="el-login-password" name="password" type="password" autocomplete="current-password" class="el-form-input" required>
        </div>
        <div class="el-login-actions">
          <button type="submit" class="el-btn el-btn--primary">
            <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="3" y="11" width="18" height="11" rx="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            <span>Đăng nhập sổ bộ</span>
          </button>
          <button type="button" id="el-btn-dev-bypass" class="el-btn el-btn--secondary" hidden>
            <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
              <polyline points="10 17 15 12 10 7"/>
              <line x1="15" y1="12" x2="3" y2="12"/>
            </svg>
            <span>Mở phiên giả lập cục bộ (5 ca chuẩn OD-05)</span>
          </button>
          <button type="button" id="el-btn-dev-bypass-admin" class="el-btn el-btn--secondary" hidden>
            <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <polyline points="9 12 11 14 15 10"/>
            </svg>
            <span>Mở phiên quản trị giả lập (BSCKII. Vũ Khương An)</span>
          </button>
        </div>
        <div id="el-login-error" class="el-error-banner" role="alert" hidden></div>
      </form>"""

    new_login_form = """      <form id="el-login-form" novalidate>
        <p class="el-demo-login-note">
          Sandbox tương tác trên bộ nhớ RAM trình duyệt: đã gỡ ô mật khẩu để bảo đảm Zero-PHI. Chọn vai trò bên dưới để thêm/sửa ca bệnh nhân ảo, kiểm thử KPI/CUSUM và quản trị dữ liệu:
        </p>
        <div class="el-login-actions">
          <button type="button" id="el-btn-dev-bypass" class="el-btn el-btn--primary">
            <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
              <polyline points="10 17 15 12 10 7"/>
              <line x1="15" y1="12" x2="3" y2="12"/>
            </svg>
            <span>Mở phiên bác sĩ nội soi (ThS. BSCKI. Nguyễn Bình An)</span>
          </button>
          <button type="button" id="el-btn-dev-bypass-admin" class="el-btn el-btn--secondary">
            <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <polyline points="9 12 11 14 15 10"/>
            </svg>
            <span>Mở phiên quản trị Superadmin (BSCKII. Vũ Khương An)</span>
          </button>
        </div>
        <div id="el-login-error" class="el-error-banner" role="alert" hidden></div>
      </form>"""
    html = _assert_replace_once(html, old_login_form, new_login_form, "LOGIN_FORM_PASSWORDLESS")

    # 4. Inject Virtual Patient Picker & lock #el-f-full-name and #el-f-hospital-mrn as readonly
    old_identity_block = """          <div id="el-patient-edit-fields" class="el-form-block">
            <div class="el-block-label">Định danh người bệnh &amp; loại hình tiếp nhận</div>
            <div class="el-field-grid el-field-grid--2">
              <div class="el-form-field">
                <label class="el-form-label" for="el-f-full-name">Họ và tên người bệnh <span id="el-preview-initials" class="el-label-hint"></span></label>
                <input id="el-f-full-name" type="text" class="el-form-input" placeholder="Ví dụ: Nguyễn Văn Minh" autocomplete="off">
              </div>"""

    new_identity_block = """          <div id="el-patient-edit-fields" class="el-form-block">
            <div class="el-block-label">Định danh người bệnh ảo &amp; loại hình tiếp nhận (Zero-PHI)</div>
            <div class="el-demo-virtual-picker-box">
              <label class="el-form-label" for="el-f-demo-patient-picker">Chọn hồ sơ bệnh nhân ảo có sẵn để thử nghiệm</label>
              <select id="el-f-demo-patient-picker" class="el-form-input"></select>
              <p class="el-demo-virtual-picker-hint">
                Ô họ tên và mã hồ sơ bệnh viện được khóa chỉ đọc trên GitHub Pages nhằm ngăn nhập nhầm danh tính bệnh nhân thật.
              </p>
            </div>
            <div class="el-field-grid el-field-grid--2">
              <div class="el-form-field">
                <label class="el-form-label" for="el-f-full-name">Họ và tên người bệnh ảo <span id="el-preview-initials" class="el-label-hint"></span></label>
                <input id="el-f-full-name" type="text" readonly class="el-form-input" autocomplete="off">
              </div>"""
    html = _assert_replace_once(html, old_identity_block, new_identity_block, "VIRTUAL_PATIENT_PICKER_AND_READONLY_NAME")

    html = _assert_replace_once(
        html,
        '<input id="el-f-hospital-mrn" type="text" class="el-form-input" placeholder="Ví dụ: HS26-88412" autocomplete="off">',
        '<input id="el-f-hospital-mrn" type="text" readonly class="el-form-input" placeholder="Tự động điền mã SYN-DEMO-xxxx" autocomplete="off">',
        "READONLY_HOSPITAL_MRN",
    )

    html = _assert_replace_once(
        html,
        '<input id="el-f-operator" type="text" class="el-form-input" value="ThS. BSCKI. Nguyễn Bình An">',
        '<input id="el-f-operator" type="text" readonly class="el-form-input" value="ThS. BSCKI. Nguyễn Bình An">',
        "READONLY_OPERATOR_NAME",
    )

    # 5. Enhance Superadmin notice (role-switch button when viewing as endoscopist) & Card 1 simulated atomic restore button
    html = _assert_replace_once(
        html,
        """          <div id="el-superadmin-readonly-notice" class="el-admin-readonly-notice">
            Phân hệ quản trị dữ liệu gốc chỉ mở quyền thực thi cho tài khoản Superadmin (BSCKII. Vũ Khương An). Tài khoản bác sĩ nội soi có thể tự đổi mật khẩu trên thanh công cụ và xuất báo cáo nghiên cứu Hồ sơ B / Hồ sơ C.
          </div>""",
        """          <div id="el-superadmin-readonly-notice" class="el-admin-readonly-notice">
            <div>Phân hệ quản trị dữ liệu gốc (gộp hồ sơ người bệnh trùng, đối soát đợt nội trú, mô phỏng khôi phục nguyên tử và hủy hiệu lực ca soi) chỉ mở cho vai trò Superadmin (BSCKII. Vũ Khương An).</div>
            <div class="el-demo-elevate-row">
              <button type="button" id="el-btn-demo-elevate-superadmin" class="el-btn el-btn--secondary">Chuyển sang vai trò Superadmin để thử nghiệm quản trị</button>
            </div>
          </div>""",
        "SUPERADMIN_ELEVATE_NOTICE",
    )

    html = _assert_replace_once(
        html,
        '                <input id="el-admin-restore-file" type="file" accept=".enc,.json" hidden>\n',
        "",
        "STRIP_ADMIN_RESTORE_FILE_INPUT",
    )

    html = _assert_replace_once(
        html,
        """              <div class="el-form-field">
                <label class="el-form-label" for="el-admin-restore-passphrase">Khóa mật khẩu giải mã tệp sao lưu</label>
                <input id="el-admin-restore-passphrase" type="password" minlength="12" maxlength="128" autocomplete="off" class="el-form-input" placeholder="Nhập cụm mật khẩu bảo vệ tệp .endolog.enc">
              </div>""",
        """              <div class="el-form-field">
                <span class="el-form-label">Khóa mật khẩu giải mã tệp sao lưu</span>
                <div id="el-admin-restore-passphrase-locked" class="el-demo-locked-field" role="note">Đã gỡ ô mật khẩu &amp; tệp ngoài trên Sandbox — dùng nút Mô phỏng khôi phục nguyên tử bên dưới</div>
              </div>""",
        "STRIP_ADMIN_RESTORE_PASSPHRASE",
    )

    html = _assert_replace_once(
        html,
        """              <div class="el-admin-card-foot">
                <button type="button" id="el-btn-run-restore" class="el-btn el-btn--danger">
                  <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="1 4 1 10 7 10"/>
                    <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                  </svg>
                  <span>Khôi phục kho dữ liệu nguyên tử</span>
                </button>
              </div>""",
        """              <div class="el-admin-card-foot">
                <button type="button" id="el-btn-demo-sim-restore" class="el-btn el-btn--primary">
                  <span>Mô phỏng khôi phục nguyên tử sang kỷ nguyên mới</span>
                </button>
                <button type="button" id="el-btn-run-restore" class="el-btn el-btn--secondary">
                  <span>Tệp .enc ngoài (Đã khóa)</span>
                </button>
              </div>""",
        "INJECT_SIMULATED_ATOMIC_RESTORE_BUTTON",
    )

    html = _assert_replace_once(
        html,
        """                  <div class="el-form-field">
                  <label class="el-form-label" for="el-admin-reset-password">Mật khẩu mới (tối thiểu 12 ký tự)</label>
                  <input id="el-admin-reset-password" type="password" minlength="12" maxlength="128" autocomplete="new-password" class="el-form-input" placeholder="Tối thiểu 12 ký tự (Argon2id)">
                </div>""",
        """                  <div class="el-form-field">
                  <span class="el-form-label">Mật khẩu mới (tối thiểu 12 ký tự)</span>
                  <div id="el-admin-reset-password-locked" class="el-demo-locked-field" role="note">Đã gỡ ô đặt lại mật khẩu trên Sandbox (Zero-PHI)</div>
                </div>""",
        "STRIP_ADMIN_RESET_PASSWORD",
    )

    # Mark admin free-text reason inputs readonly with pre-filled standard audit rationale
    html = _assert_replace_once(
        html,
        '<input id="el-admin-merge-reason" type="text"',
        f'<input id="el-admin-merge-reason" type="text" readonly value="{DEFAULT_MERGE_REASON_VI}"',
        "READONLY_MERGE_REASON",
    )
    html = _assert_replace_once(
        html,
        '<input id="el-admin-reconcile-reason" type="text"',
        f'<input id="el-admin-reconcile-reason" type="text" readonly value="{DEFAULT_RECONCILE_REASON_VI}"',
        "READONLY_RECONCILE_REASON",
    )

    # 6. Strip vault passphrase input & personal password-change inputs from modal templates
    html = _assert_replace_once(
        html,
        """      <div id="el-vault-passphrase-box" class="el-form-field">
        <label class="el-form-label" for="el-vault-passphrase">Khóa mật khẩu mã hóa tập tin sao lưu (tối thiểu 12 ký tự)</label>
        <input id="el-vault-passphrase" type="password" minlength="12" maxlength="128" class="el-form-input" autocomplete="new-password" placeholder="Nhập cụm mật khẩu bảo vệ tệp .endolog.enc">
      </div>""",
        """      <div id="el-vault-passphrase-box" class="el-form-field">
        <span class="el-form-label">Khóa mật khẩu mã hóa tập tin sao lưu</span>
        <div class="el-demo-locked-field" role="note">Đã khóa trích xuất kho sao lưu mã hóa ngoài trên Sandbox (Zero-PHI)</div>
      </div>""",
        "STRIP_VAULT_PASSPHRASE",
    )

    html = _assert_replace_once(
        html,
        """      <div class="el-form-field">
        <label class="el-form-label" for="el-pwd-current">Mật khẩu hiện tại</label>
        <input id="el-pwd-current" type="password" autocomplete="current-password" class="el-form-input" placeholder="Nhập mật khẩu đang sử dụng">
      </div>
      <div class="el-form-field">
        <label class="el-form-label" for="el-pwd-new">Mật khẩu mới (tối thiểu 12 ký tự)</label>
        <input id="el-pwd-new" type="password" minlength="12" maxlength="128" autocomplete="new-password" class="el-form-input" placeholder="Nhập mật khẩu mới tối thiểu 12 ký tự">
      </div>
      <div class="el-form-field">
        <label class="el-form-label" for="el-pwd-confirm">Nhập lại mật khẩu mới</label>
        <input id="el-pwd-confirm" type="password" minlength="12" maxlength="128" autocomplete="new-password" class="el-form-input" placeholder="Xác nhận lại mật khẩu mới">
      </div>""",
        """      <div class="el-form-field">
        <div class="el-demo-locked-field" role="note">Đã gỡ toàn bộ ô nhập mật khẩu cá nhân trên Sandbox (Zero-PHI)</div>
      </div>""",
        "STRIP_PERSONAL_PASSWORD_INPUTS",
    )

    # 7. Inject Zero-PHI Demo Lock Dialog (for password/vault/XLSX) + demo-synthetic-adapter.js + base_path app.js
    demo_lock_modal_and_scripts = f"""  <!-- HỘP THOẠI KHÓA MẬT KHẨU & TỆP NGOÀI TRÊN SANDBOX TƯƠNG TÁC (GATE C · G1+) -->
  <div id="el-demo-lock-modal-backdrop" class="el-submodal-backdrop" hidden>
    <div id="el-demo-lock-modal" class="el-submodal" role="dialog" aria-modal="true" aria-labelledby="el-demo-lock-title">
      <div class="el-detail-head">
        <div>
          <span id="el-demo-lock-action-label" class="el-demo-lock-action-pill">Chức năng đang khóa</span>
          <h3 id="el-demo-lock-title" class="el-submodal-title">Đã khóa mật khẩu &amp; tệp sao lưu ngoài trên GitHub Pages (Zero-PHI)</h3>
        </div>
        <button type="button" id="el-btn-demo-lock-close" class="el-btn el-btn--secondary el-btn--icon" aria-label="Đóng thông báo khóa bảo mật Zero-PHI">
          <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <p class="el-submodal-desc">
        Sandbox trên GitHub Pages cho phép tương tác đầy đủ luồng thêm/sửa ca bệnh nhân ảo trên RAM, tính động KPI/CUSUM, đóng vòng hẹn soi lại, gộp hồ sơ trùng, đối soát đợt nội trú, mô phỏng khôi phục nguyên tử và tải Hồ sơ B (CSV) / Hồ sơ C (JSON).
      </p>
      <p class="el-submodal-desc">
        Riêng các ô mật khẩu, tải lên/xuất tệp kho mã hóa (.endolog.enc) và xuất XLSX nhị phân được khóa cứng để bảo đảm tuyệt đối không tiếp nhận mật khẩu thật hoặc tệp dữ liệu bệnh viện lên trình duyệt công cộng.
      </p>
      <div class="el-submodal-actions">
        <button type="button" id="el-btn-demo-lock-ok" class="el-btn el-btn--primary">Đã hiểu — Tiếp tục thử nghiệm Sandbox</button>
      </div>
    </div>
  </div>

  <script src="{base_path}js/demo-synthetic-adapter.js?v={version}"></script>
  <script src="{base_path}js/app.js?v={version}"></script>"""

    html = _assert_replace_once(
        html,
        f'  <script src="/js/app.js?v={version}"></script>',
        demo_lock_modal_and_scripts,
        "FOOTER_SCRIPTS_AND_LOCK_MODAL",
    )

    if re.search(r'<input\b[^>]*\btype\s*=\s*["\'](?:password|file)["\']', html, flags=re.I):
        raise RuntimeError("Vẫn còn sót thẻ input[type=password|file] trong dist_pages/index.html sau khi đóng gói!")

    return html


def _transform_app_js_for_demo(raw_js: str) -> str:
    """Transform copy of app.js in dist_pages/js/app.js for subpath SW scope while keeping genuine RBAC."""
    return _assert_replace_once(
        raw_js,
        "navigator.serviceWorker.register('/sw.js').catch(() => {});",
        "navigator.serviceWorker.register('./sw-demo.js', { scope: './' }).catch(() => {});",
        "SW_REGISTER_SCOPE",
    )


def _build_sw_demo_js(base_path: str, version: str) -> str:
    """Build isolated Service Worker for /endolog/ that never touches caches outside 'endolog-ghpages-demo-'."""
    cache_prefix = "endolog-ghpages-demo-"
    cache_name = f"{cache_prefix}v{version}"
    allowlist = [
        f"{base_path}",
        f"{base_path}index.html",
        f"{base_path}manifest.json",
        f"{base_path}css/fonts.css?v={version}",
        f"{base_path}css/tokens.css?v={version}",
        f"{base_path}css/app.css?v={version}",
        f"{base_path}css/demo-showcase.css?v={version}",
        f"{base_path}js/demo-synthetic-adapter.js?v={version}",
        f"{base_path}js/app.js?v={version}",
        f"{base_path}data/od05_precomputed_bundle.json?v={version}",
        f"{base_path}icons/favicon.svg",
        f"{base_path}fonts/noto-sans-latin-var.woff2",
        f"{base_path}fonts/noto-sans-vietnamese-var.woff2",
        f"{base_path}fonts/plus-jakarta-sans-latin-var.woff2",
        f"{base_path}fonts/plus-jakarta-sans-vietnamese-var.woff2",
        f"{base_path}fonts/jetbrains-mono-latin-var.woff2",
        f"{base_path}fonts/jetbrains-mono-vietnamese-var.woff2",
    ]
    allowlist_json = json.dumps(allowlist, indent=2, ensure_ascii=False)
    return f"""/* EndoLog GitHub Pages Interactive Sandbox Service Worker v{version}
 * - Scope cô lập dưới {base_path}; khóa cache riêng '{cache_name}'.
 * - Chỉ dọn dẹp các cache bắt đầu bằng '{cache_prefix}' để bảo vệ tuyệt đối các ứng dụng anh em trên cùng github.io. */

const CACHE_PREFIX = {json.dumps(cache_prefix)};
const CACHE_NAME = {json.dumps(cache_name)};
const BASE_PATH = {json.dumps(base_path)};
const STATIC_ALLOWLIST = {allowlist_json};

self.addEventListener('install', (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ALLOWLIST)).then(() => self.skipWaiting())
  );
}});

self.addEventListener('activate', (event) => {{
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith(CACHE_PREFIX) && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
}});

self.addEventListener('fetch', (event) => {{
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) {{
    return;
  }}
  if (!url.pathname.startsWith(BASE_PATH) || url.pathname.includes('/api/')) {{
    return;
  }}
  if (event.request.method !== 'GET') {{
    return;
  }}
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
}});
"""


def build_gh_pages_demo(output_dir: Path, base_path: str = "/EndoLog/") -> dict[str, Any]:
    norm_base = _normalize_base_path(base_path)
    out = output_dir.resolve()
    quarantined = _quarantine_existing_dir(out)

    (out / "css").mkdir(parents=True, exist_ok=True)
    (out / "js").mkdir(parents=True, exist_ok=True)
    (out / "fonts").mkdir(parents=True, exist_ok=True)
    (out / "icons").mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(parents=True, exist_ok=True)

    # 1. Copy fonts, icons, tokens.css, app.css
    for font_file in sorted((STATIC_DIR / "fonts").glob("*")):
        if font_file.is_file():
            shutil.copy2(font_file, out / "fonts" / font_file.name)

    for icon_file in sorted((STATIC_DIR / "icons").glob("*")):
        if icon_file.is_file():
            shutil.copy2(icon_file, out / "icons" / icon_file.name)

    shutil.copy2(STATIC_DIR / "css" / "tokens.css", out / "css" / "tokens.css")
    shutil.copy2(STATIC_DIR / "css" / "app.css", out / "css" / "app.css")

    # 2. Rewrite fonts.css to explicit base_path
    fonts_css = (STATIC_DIR / "css" / "fonts.css").read_text(encoding="utf-8")
    rewritten_fonts_css = fonts_css.replace("url('../fonts/", f"url('{norm_base}fonts/")
    if f"url('{norm_base}fonts/" not in rewritten_fonts_css:
        raise RuntimeError("Không viết lại được đường dẫn phông chữ trong fonts.css")
    (out / "css" / "fonts.css").write_text(rewritten_fonts_css, encoding="utf-8")

    # 3. Write demo-showcase.css
    (out / "css" / "demo-showcase.css").write_text(_build_demo_showcase_css(), encoding="utf-8")

    # 4. Rewrite manifest.json for /endolog/
    manifest = json.loads((STATIC_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["start_url"] = norm_base
    manifest["scope"] = norm_base
    for icon in manifest.get("icons", []):
        src = str(icon.get("src", "")).lstrip("/")
        icon["src"] = f"{norm_base}{src}"
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # 5. Generate precomputed OD-05 JSON bundle + sanitized RAM seed from Python engines
    bundle = _generate_precomputed_od05_bundle()
    bundle_path = out / "data" / "od05_precomputed_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # 6. Write demo-synthetic-adapter.js, transformed app.js, transformed index.html, sw-demo.js, and .nojekyll
    (out / "js" / "demo-synthetic-adapter.js").write_text(
        _build_demo_synthetic_adapter_js(norm_base, __version__),
        encoding="utf-8",
    )
    raw_app_js = (STATIC_DIR / "js" / "app.js").read_text(encoding="utf-8")
    (out / "js" / "app.js").write_text(_transform_app_js_for_demo(raw_app_js), encoding="utf-8")

    raw_index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(
        _transform_index_html(raw_index_html, norm_base, __version__),
        encoding="utf-8",
    )

    (out / "sw-demo.js").write_text(_build_sw_demo_js(norm_base, __version__), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    # 7. Build-time Design System color literal check outside tokens.css
    color_fn_pat = re.compile(r"(#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(|\boklch\s*\(|\boklab\s*\()", re.I)
    for rel_check in ("index.html", "css/demo-showcase.css", "js/demo-synthetic-adapter.js", "sw-demo.js"):
        txt = (out / rel_check).read_text(encoding="utf-8")
        m = color_fn_pat.search(txt)
        if m:
            raise RuntimeError(f"Phát hiện mã màu cứng '{m.group(0)}' trong {rel_check}!")

    built_files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    return {
        "output_dir": str(out),
        "base_path": norm_base,
        "version": __version__,
        "case_count": len(bundle["cases_response"]["items"]),
        "virtual_patient_count": len(bundle["synthetic_patient_catalog"]),
        "file_count": len(built_files),
        "quarantined_previous_dir": str(quarantined) if quarantined else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build EndoLog Gate C Interactive Virtual-Patient Sandbox (Phương án G1+) into dist_pages/."
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "dist_pages"),
        help="Output directory for GitHub Pages static bundle (default: dist_pages/).",
    )
    parser.add_argument(
        "--base-path",
        default="/EndoLog/",
        help="GitHub Pages project subpath (default: /EndoLog/).",
    )
    args = parser.parse_args()
    summary = build_gh_pages_demo(Path(args.output), base_path=args.base_path)
    print(f"GH_PAGES_DEMO_BUILD_OK: {json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
