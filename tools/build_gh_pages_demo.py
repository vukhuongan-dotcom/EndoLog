#!/usr/bin/env python3
"""Build Showcase-Only Synthetic Sandbox (Gate C · Phương án G1 / G06) into dist_pages/ for GitHub Pages (/endolog/).

Contract enforced:
- Leaves src/endolog/static/ untouched for FastAPI '/'.
- Generates dist_pages/data/od05_precomputed_bundle.json directly from Python clinical/KPI/CUSUM/audit engines via FastAPI TestClient.
- Strips 100% of input[type="password"] and input[type="file"] from dist_pages/index.html.
- Injects fixed top Vietnamese showcase warning banner and Zero-PHI write-lock modal.
- Intercepts 100% of /api/* calls in memory via dist_pages/js/demo-synthetic-adapter.js (0 /api/* network requests).
- Generates prefix-isolated dist_pages/sw-demo.js ({ scope: './' }, cache prefix 'endolog-ghpages-demo-') safe for shared github.io origins.
- Enforces Rule v2:R15 (Zero-RM): quarantines prior output directory into OS temp directory via shutil.move instead of deleting.
"""

from __future__ import annotations

import argparse
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
from endolog.core.security import create_access_token  # noqa: E402
from endolog.main import STATIC_DIR, create_app  # noqa: E402

SHOWCASE_BANNER_TEXT_VI = (
    "Bản trình diễn giao diện trên dữ liệu giả lập chuẩn OD-05 — "
    "Đã khóa chức năng nhập ca bệnh, mật khẩu và tệp sao lưu. "
    "Vui lòng sử dụng máy chủ EndoLog nội bộ khi làm việc lâm sàng."
)


def _normalize_base_path(raw: str) -> str:
    cleaned = (raw or "/endolog/").strip()
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

    bundle: dict[str, Any] = {
        "contract": "endolog.gh_pages_od05_precomputed_bundle.v1",
        "version": __version__,
        "static_demo": True,
        "zero_phi_policy": "SYNTHETIC_OD05_ONLY_READONLY_SHOWCASE",
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
    for forbidden_key in ("password_hash", "hospital_mrn_hash", "secondary_mrn_hashes", "jwt_secret", "argon2id$"):
        if forbidden_key in serialized:
            raise RuntimeError(f"Phát hiện trường nhạy cảm '{forbidden_key}' lọt vào gói dữ liệu tĩnh OD-05.")
    return bundle


def admin_patients_response_clean(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a clean copy of sanitized synthetic admin patient items (already masked by EndoLogService)."""
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _build_demo_showcase_css() -> str:
    """Build CSS for the showcase banner, passwordless persona card, and Zero-PHI lock modal (100% tokens.css vars)."""
    return """/* EndoLog Static Showcase Stylesheet (Gate C · Phương án G1 / G06)
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
  gap: var(--space-2);
  font-family: var(--font-sans);
  font-size: var(--text-xs);
  line-height: 1.35;
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
  color: var(--text-heading);
  font-weight: 500;
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
  .el-demo-showcase-banner-inner {
    font-size: var(--text-xs);
    line-height: 1.3;
  }
}
"""


def _build_demo_synthetic_adapter_js(base_path: str, version: str) -> str:
    """Build client-side fetch & write-action interceptor for the Showcase-Only Synthetic Sandbox."""
    bundle_url = f"{base_path}data/od05_precomputed_bundle.json?v={version}"
    return f"""/* EndoLog Showcase-Only Synthetic Adapter (Gate C · Phương án G1 / G06)
 * - Khóa cứng ENDOLOG_STATIC_DEMO = true; 0 request mạng tới /api/*.
 * - Mọi kết quả KPI (45/50) và QC-CUSUM đọc trực tiếp từ gói tính sẵn của động cơ Python (0 viết nhái toán học trên JS).
 * - Chặn ở pha capture toàn bộ thao tác nhập/sửa ca, đổi/đặt lại mật khẩu, sao lưu/khôi phục Hồ sơ A, xuất dữ liệu và gộp hồ sơ. */

(function () {{
  'use strict';

  window.ENDOLOG_STATIC_DEMO = true;
  const BASE_PATH = {json.dumps(base_path)};
  const BUNDLE_URL = {json.dumps(bundle_url)};

  const realFetch = window.fetch.bind(window);
  let bundlePromise = null;
  let activePersonaKey = (function () {{
    try {{
      const p = new URLSearchParams(window.location.search);
      return p.get('login') === '1' ? null : 'nguyenbinhan';
    }} catch (_e) {{
      return 'nguyenbinhan';
    }}
  }})();

  const demoAuditStats = {{
    staticDemo: true,
    basePath: BASE_PATH,
    interceptedApiCalls: 0,
    blockedWriteCalls: 0,
    lockModalOpenCount: 0,
    lastLockedActionLabel: ''
  }};

  function deepClone(obj) {{
    return JSON.parse(JSON.stringify(obj));
  }}

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

  function jsonResponse(payload, status) {{
    return new Response(JSON.stringify(payload), {{
      status: status || 200,
      headers: {{
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store'
      }}
    }});
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
      return {{ path: path, searchParams: parsed.searchParams }};
    }}
    return null;
  }}

  window.fetch = async function (input, init) {{
    const apiTarget = normalizeApiPath(input);
    if (!apiTarget) {{
      return realFetch(input, init);
    }}

    demoAuditStats.interceptedApiCalls += 1;
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    const path = apiTarget.path;
    const params = apiTarget.searchParams;
    const bundle = await loadBundle();

    if (method === 'GET' && path === '/api/health') {{
      return jsonResponse({{
        status: 'ok',
        version: bundle.version,
        env_mode: 'gh_pages_static_demo',
        local_bypass_candidate: true,
        static_demo: true
      }}, 200);
    }}

    if (method === 'GET' && path === '/api/auth/me') {{
      if (!activePersonaKey || !bundle.personas[activePersonaKey]) {{
        return jsonResponse({{
          detail: {{
            code: 'AUTH_REQUIRED',
            message: 'Chọn vai trò minh họa để mở bản trình diễn tĩnh.'
          }}
        }}, 401);
      }}
      return jsonResponse({{
        authenticated: true,
        user: deepClone(bundle.personas[activePersonaKey]),
        store_epoch: 1,
        remaining_seconds: 900,
        env_mode: 'gh_pages_static_demo'
      }}, 200);
    }}

    if (method === 'POST' && path === '/api/auth/local-bypass') {{
      let requestedUser = 'nguyenbinhan';
      try {{
        const parsedBody = init && init.body ? JSON.parse(String(init.body)) : null;
        if (parsedBody && parsedBody.target_username && bundle.personas[parsedBody.target_username]) {{
          requestedUser = parsedBody.target_username;
        }}
      }} catch (_err) {{
        requestedUser = 'nguyenbinhan';
      }}
      activePersonaKey = requestedUser;
      return jsonResponse({{
        authenticated: true,
        gate_code: 'STATIC_DEMO_SANDBOX',
        user: deepClone(bundle.personas[activePersonaKey]),
        store_epoch: 1,
        expires_in_seconds: 900,
        env_mode: 'gh_pages_static_demo'
      }}, 200);
    }}

    if (method === 'POST' && path === '/api/auth/logout') {{
      activePersonaKey = null;
      lockReturnFocusEl = null;
      lockOpenedFromLogin = false;
      closeDemoLockModal();
      return jsonResponse({{ authenticated: false }}, 200);
    }}

    if (method === 'GET' && path === '/api/cases') {{
      const cloned = deepClone(bundle.cases_response);
      const track = (params.get('track') || '').trim().toUpperCase();
      if (track && track !== 'ALL') {{
        cloned.items = (cloned.items || []).filter(function (c) {{ return c.track === track; }});
        cloned.total = cloned.items.length;
      }}
      return jsonResponse(cloned, 200);
    }}

    if (method === 'GET' && path === '/api/surveillance') {{
      return jsonResponse(deepClone(bundle.surveillance_response), 200);
    }}

    if (method === 'GET' && path === '/api/metrics/kpi') {{
      const ageKey = String(params.get('min_adr_age') || '45') === '50' ? '50' : '45';
      return jsonResponse(deepClone(bundle.kpi_by_age[ageKey]), 200);
    }}

    if (method === 'GET' && path === '/api/metrics/cusum') {{
      const metric = String(params.get('metric') || 'CIR').toUpperCase() === 'ERCP_NATIVE' ? 'ERCP_NATIVE' : 'CIR';
      const preset = String(params.get('preset') || 'DEFAULT_90').toUpperCase() === 'SCREENING_CIR_95'
        ? 'SCREENING_CIR_95'
        : 'DEFAULT_90';
      const key = metric + ':' + preset;
      return jsonResponse(deepClone(bundle.cusum_series[key] || bundle.cusum_series['CIR:DEFAULT_90']), 200);
    }}

    if (method === 'GET' && path === '/api/audit/verify') {{
      return jsonResponse(deepClone(bundle.audit_verify_response), 200);
    }}

    if (method === 'GET' && path === '/api/settings') {{
      return jsonResponse(deepClone(bundle.settings_response), 200);
    }}

    if (method === 'GET' && path === '/api/admin/patients') {{
      return jsonResponse(deepClone(bundle.admin_patients_response), 200);
    }}

    if (method === 'GET' && path === '/api/admin/users') {{
      return jsonResponse(deepClone(bundle.admin_users_response), 200);
    }}

    demoAuditStats.blockedWriteCalls += 1;
    return jsonResponse({{
      detail: {{
        code: 'STATIC_DEMO_READONLY_LOCKED',
        message: 'Bản trình diễn tĩnh trên GitHub Pages đã khóa mọi thao tác ghi dữ liệu, mật khẩu và trích xuất tệp nhằm tuân thủ chính sách Zero-PHI.'
      }}
    }}, 403);
  }};

  /* Hộp thoại thông báo khóa ghi dữ liệu chuẩn Zero-PHI */
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
      if (isLockedOpen) {{
        detailModalEl.setAttribute('inert', '');
      }} else {{
        detailModalEl.removeAttribute('inert');
      }}
    }}
    if (shellEl) {{
      const keepShellInert = !shellEl.hidden && (isLockedOpen || detailIsOpen);
      shellEl.inert = keepShellInert;
      if (keepShellInert) {{
        shellEl.setAttribute('inert', '');
      }} else {{
        shellEl.removeAttribute('inert');
      }}
    }}
    if (loginEl) {{
      const keepLoginInert = !loginEl.hidden && isLockedOpen;
      loginEl.inert = keepLoginInert;
      if (keepLoginInert) {{
        loginEl.setAttribute('inert', '');
      }} else {{
        loginEl.removeAttribute('inert');
      }}
    }}
  }}

  function openDemoLockModal(actionLabel, triggerEl) {{
    const backdrop = document.getElementById('el-demo-lock-modal-backdrop');
    const loginEl = document.getElementById('el-login-screen');
    const pill = document.getElementById('el-demo-lock-action-label');
    const closeBtn = document.getElementById('el-btn-demo-lock-close');
    if (!backdrop) return;

    /* Đóng menu 3 chấm trên thẻ ca nếu đang mở */
    document.querySelectorAll('.el-action-menu-dropdown').forEach(function (menu) {{
      menu.hidden = true;
    }});
    document.querySelectorAll('[data-case-more][aria-expanded="true"]').forEach(function (btn) {{
      btn.setAttribute('aria-expanded', 'false');
    }});
    document.querySelectorAll('.el-case-card--menu-open').forEach(function (card) {{
      card.classList.remove('el-case-card--menu-open');
    }});

    demoAuditStats.lockModalOpenCount += 1;
    demoAuditStats.lastLockedActionLabel = String(actionLabel || 'Thao tác ghi dữ liệu');
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

  /* Tự động đóng hộp thoại khóa nếu phiên kết thúc (đăng xuất / hết hạn 15 phút) chuyển về màn đăng nhập */
  const watchLoginTransitionForLockModal = function () {{
    const loginEl = document.getElementById('el-login-screen');
    if (!loginEl || typeof MutationObserver !== 'function') return;
    const loginObs = new MutationObserver(function () {{
      if (!loginEl.hidden && !lockOpenedFromLogin) {{
        lockReturnFocusEl = null;
        closeDemoLockModal();
      }}
    }});
    loginObs.observe(loginEl, {{ attributes: true, attributeFilter: ['hidden'] }});
  }};
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', watchLoginTransitionForLockModal, {{ once: true }});
  }} else {{
    watchLoginTransitionForLockModal();
  }}

  const LOCKED_BUTTON_LABELS = {{
    'el-btn-new-case': 'Thêm ca soi mới',
    'el-btn-save-settings': 'Lưu cấu hình chuyên môn & thống kê',
    'el-btn-change-password': 'Đổi mật khẩu xác thực cá nhân',
    'el-btn-pwd-submit': 'Cập nhật mật khẩu',
    'el-btn-open-vault-backup': 'Sao lưu kho mã hóa (Hồ sơ A · .endolog.enc)',
    'el-btn-vault-download': 'Tải tệp sao lưu mã hóa (Hồ sơ A)',
    'el-btn-export-csv': 'Xuất bảng nghiên cứu giả danh (Hồ sơ B · CSV)',
    'el-btn-export-xlsx': 'Xuất bảng nghiên cứu giả danh (Hồ sơ B · XLSX)',
    'el-btn-export-profile-c': 'Xuất báo cáo tổng hợp (Hồ sơ C)',
    'el-btn-pick-restore-file': 'Chọn tệp kho sao lưu mã hóa (.endolog.enc)',
    'el-btn-run-restore': 'Khôi phục kho dữ liệu nguyên tử (Hồ sơ A)',
    'el-btn-run-patient-merge': 'Gộp hồ sơ người bệnh trùng',
    'el-btn-run-episode-reconcile': 'Đối soát hợp nhất đợt điều trị nội trú',
    'el-btn-run-reset-password': 'Đặt lại mật khẩu xác thực tài khoản'
  }};

  function resolveLockedTrigger(target) {{
    if (!target || typeof target.closest !== 'function') return null;

    const closeBtn = target.closest('#el-btn-demo-lock-close, #el-btn-demo-lock-ok');
    if (closeBtn) return null;

    for (const id of Object.keys(LOCKED_BUTTON_LABELS)) {{
      const matchedById = target.closest('#' + id);
      if (matchedById) {{
        return {{ el: matchedById, label: LOCKED_BUTTON_LABELS[id] }};
      }}
    }}

    const editBtn = target.closest('[data-case-edit]');
    if (editBtn) {{
      const ph = String(editBtn.getAttribute('data-target-phase') || 'p2').toUpperCase();
      return {{ el: editBtn, label: 'Sửa diễn tiến hồ sơ ca soi (' + ph + ')' }};
    }}

    const jumpBtn = target.closest('[data-detail-jump-phase]');
    if (jumpBtn) {{
      const ph = String(jumpBtn.getAttribute('data-detail-jump-phase') || 'p1').toUpperCase();
      return {{ el: jumpBtn, label: 'Chỉnh sửa dữ liệu ca soi (' + ph + ')' }};
    }}

    const dangerBtn = target.closest('[data-danger-case]');
    if (dangerBtn) {{
      return {{ el: dangerBtn, label: 'Hủy hiệu lực hồ sơ ca soi' }};
    }}

    const linkBtn = target.closest('[data-create-linked]');
    if (linkBtn) {{
      return {{ el: linkBtn, label: 'Tạo ca nội soi liên kết lịch hẹn' }};
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

    const locked = resolveLockedTrigger(ev.target);
    if (locked) {{
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();
      openDemoLockModal(locked.label, locked.el);
    }}
  }}, true);

  document.addEventListener('submit', function (ev) {{
    const formEl = ev.target;
    if (formEl && (formEl.id === 'el-case-form' || formEl.id === 'el-login-form')) {{
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();
      openDemoLockModal('Gửi biểu mẫu dữ liệu lên máy chủ', formEl);
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

  /* Chốt chặn phòng thủ chiều sâu: xóa ngay nếu có bất kỳ thẻ input password/file nào bị chèn động */
  function purgeForbiddenInputs(root) {{
    if (!root || typeof root.querySelectorAll !== 'function') return;
    root.querySelectorAll('input[type="password"], input[type="file"]').forEach(function (inp) {{
      inp.remove();
    }});
  }}

  if (typeof MutationObserver !== 'undefined') {{
    const obs = new MutationObserver(function (mutations) {{
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
    obs.observe(document.documentElement, {{ childList: true, subtree: true }});
  }}

  document.addEventListener('DOMContentLoaded', function () {{
    purgeForbiddenInputs(document);
  }});

  window.__ENDOLOG_DEMO_AUDIT__ = {{
    getStats: function () {{
      return Object.assign({{}}, demoAuditStats, {{
        activePersonaKey: activePersonaKey,
        passwordInputCount: document.querySelectorAll('input[type="password"]').length,
        fileInputCount: document.querySelectorAll('input[type="file"]').length
      }});
    }},
    openDemoLockModal: openDemoLockModal,
    closeDemoLockModal: closeDemoLockModal
  }};
}})();
"""


def _transform_index_html(raw_html: str, base_path: str, version: str) -> str:
    """Transform src/endolog/static/index.html into dist_pages/index.html without password/file inputs."""
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

    # 2. Inject fixed top showcase warning banner immediately inside <body>
    banner_html = (
        '<body>\n'
        '  <div id="el-demo-showcase-banner" class="el-demo-showcase-banner" role="region" '
        'aria-label="Cảnh báo bản trình diễn giả lập tĩnh">\n'
        '    <div class="el-demo-showcase-banner-inner">\n'
        '      <span class="el-demo-showcase-badge">Bản trình diễn tĩnh · Zero-PHI</span>\n'
        f'      <p class="el-demo-showcase-text">{SHOWCASE_BANNER_TEXT_VI}</p>\n'
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
          Trang trình diễn tĩnh đã gỡ toàn bộ ô nhập mật khẩu để bảo đảm Zero-PHI. Chọn vai trò minh họa bên dưới để duyệt 5 ca giả lập chuẩn OD-05:
        </p>
        <div class="el-login-actions">
          <button type="button" id="el-btn-dev-bypass" class="el-btn el-btn--primary">
            <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
              <polyline points="10 17 15 12 10 7"/>
              <line x1="15" y1="12" x2="3" y2="12"/>
            </svg>
            <span>Mở phiên giả lập cục bộ (5 ca chuẩn OD-05)</span>
          </button>
          <button type="button" id="el-btn-dev-bypass-admin" class="el-btn el-btn--secondary">
            <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              <polyline points="9 12 11 14 15 10"/>
            </svg>
            <span>Mở phiên quản trị giả lập (BSCKII. Vũ Khương An)</span>
          </button>
        </div>
        <div id="el-login-error" class="el-error-banner" role="alert" hidden></div>
      </form>"""
    html = _assert_replace_once(html, old_login_form, new_login_form, "LOGIN_FORM_PASSWORDLESS")

    # 4. Update Superadmin readonly notice text for the static showcase & remove file + password inputs in Superadmin panel
    html = _assert_replace_once(
        html,
        """          <div id="el-superadmin-readonly-notice" class="el-admin-readonly-notice">
            Phân hệ quản trị dữ liệu gốc chỉ mở quyền thực thi cho tài khoản Superadmin (BSCKII. Vũ Khương An). Tài khoản bác sĩ nội soi có thể tự đổi mật khẩu trên thanh công cụ và xuất báo cáo nghiên cứu Hồ sơ B / Hồ sơ C.
          </div>""",
        """          <div id="el-superadmin-readonly-notice" class="el-admin-readonly-notice">
            Bố cục minh họa chỉ đọc của phân hệ Quản trị Superadmin (BSCKII. Vũ Khương An) trên 5 hồ sơ giả lập chuẩn OD-05. Toàn bộ ô tải tệp sao lưu (.endolog.enc), ô mật khẩu và lệnh ghi dữ liệu đã được khóa cứng theo chính sách Zero-PHI.
          </div>""",
        "SUPERADMIN_SHOWCASE_NOTICE",
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
                <div id="el-admin-restore-passphrase-locked" class="el-demo-locked-field" role="note">Đã gỡ ô nhập mật khẩu giải mã trên bản trình diễn tĩnh (Zero-PHI)</div>
              </div>""",
        "STRIP_ADMIN_RESTORE_PASSPHRASE",
    )

    html = _assert_replace_once(
        html,
        """                  <div class="el-form-field">
                  <label class="el-form-label" for="el-admin-reset-password">Mật khẩu mới (tối thiểu 12 ký tự)</label>
                  <input id="el-admin-reset-password" type="password" minlength="12" maxlength="128" autocomplete="new-password" class="el-form-input" placeholder="Tối thiểu 12 ký tự (Argon2id)">
                </div>""",
        """                  <div class="el-form-field">
                  <span class="el-form-label">Mật khẩu mới (tối thiểu 12 ký tự)</span>
                  <div id="el-admin-reset-password-locked" class="el-demo-locked-field" role="note">Đã gỡ ô đặt lại mật khẩu trên bản trình diễn tĩnh (Zero-PHI)</div>
                </div>""",
        "STRIP_ADMIN_RESET_PASSWORD",
    )

    # Mark admin free-text reason inputs readonly so users cannot type clinical text on github.io
    html = _assert_replace_once(
        html,
        '<input id="el-admin-merge-reason" type="text"',
        '<input id="el-admin-merge-reason" type="text" readonly',
        "READONLY_MERGE_REASON",
    )
    html = _assert_replace_once(
        html,
        '<input id="el-admin-reconcile-reason" type="text"',
        '<input id="el-admin-reconcile-reason" type="text" readonly',
        "READONLY_RECONCILE_REASON",
    )

    # 5. Strip vault passphrase input & personal password-change inputs from modal templates
    html = _assert_replace_once(
        html,
        """      <div id="el-vault-passphrase-box" class="el-form-field">
        <label class="el-form-label" for="el-vault-passphrase">Khóa mật khẩu mã hóa tập tin sao lưu (tối thiểu 12 ký tự)</label>
        <input id="el-vault-passphrase" type="password" minlength="12" maxlength="128" class="el-form-input" autocomplete="new-password" placeholder="Nhập cụm mật khẩu bảo vệ tệp .endolog.enc">
      </div>""",
        """      <div id="el-vault-passphrase-box" class="el-form-field">
        <span class="el-form-label">Khóa mật khẩu mã hóa tập tin sao lưu</span>
        <div class="el-demo-locked-field" role="note">Đã khóa trích xuất kho sao lưu trên bản trình diễn tĩnh (Zero-PHI)</div>
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
        <div class="el-demo-locked-field" role="note">Đã gỡ toàn bộ ô nhập mật khẩu cá nhân trên bản trình diễn tĩnh (Zero-PHI)</div>
      </div>""",
        "STRIP_PERSONAL_PASSWORD_INPUTS",
    )

    # 6. Inject Zero-PHI Demo Write-Lock Dialog + demo-synthetic-adapter.js + base_path app.js
    demo_lock_modal_and_scripts = f"""  <!-- HỘP THOẠI KHÓA GHI DỮ LIỆU & ZERO-PHI TRÊN BẢN TRÌNH DIỄN TĨNH (GATE C · G06) -->
  <div id="el-demo-lock-modal-backdrop" class="el-submodal-backdrop" hidden>
    <div id="el-demo-lock-modal" class="el-submodal" role="dialog" aria-modal="true" aria-labelledby="el-demo-lock-title">
      <div class="el-detail-head">
        <div>
          <span id="el-demo-lock-action-label" class="el-demo-lock-action-pill">Chức năng đang khóa</span>
          <h3 id="el-demo-lock-title" class="el-submodal-title">Bản trình diễn tĩnh đã khóa ghi dữ liệu (Zero-PHI)</h3>
        </div>
        <button type="button" id="el-btn-demo-lock-close" class="el-btn el-btn--secondary el-btn--icon" aria-label="Đóng thông báo bản trình diễn tĩnh">
          <svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <p class="el-submodal-desc">
        Trang web trên GitHub Pages chỉ phục vụ trình diễn giao diện và kiểm chứng thuật toán trên 5 ca giả lập chuẩn OD-05.
        Toàn bộ thao tác nhập/chỉnh sửa ca bệnh, nhập mật khẩu, tải tệp sao lưu mã hóa (.endolog.enc), gộp hồ sơ và xuất dữ liệu đều bị khóa cứng để ngăn ngừa tuyệt đối việc nhập nhầm thông tin bệnh nhân thật (Zero-PHI).
      </p>
      <p class="el-submodal-desc">
        Khi làm việc lâm sàng thực tế tại Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân, vui lòng sử dụng máy chủ EndoLog nội bộ chạy Python FastAPI.
      </p>
      <div class="el-submodal-actions">
        <button type="button" id="el-btn-demo-lock-ok" class="el-btn el-btn--primary">Đã hiểu — Quay lại xem bản trình diễn</button>
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
    """Transform copy of app.js in dist_pages/js/app.js for subpath SW scope and read-only Superadmin layout."""
    js = raw_js

    # 1. Register dedicated sw-demo.js under relative './' scope (/endolog/)
    js = _assert_replace_once(
        js,
        "navigator.serviceWorker.register('/sw.js').catch(() => {});",
        "navigator.serviceWorker.register('./sw-demo.js', { scope: './' }).catch(() => {});",
        "SW_REGISTER_SCOPE",
    )

    # 2. Load sanitized synthetic admin patients & users in static demo so the read-only Superadmin layout is visible
    old_admin_load = """      const isSuper = Boolean(state.user && state.user.role === 'superadmin');
      const fetchPromises = [
        apiFetch('/api/cases', null, reqEpoch),
        apiFetch('/api/surveillance', null, reqEpoch),
        apiFetch('/api/metrics/kpi?min_adr_age=' + encodeURIComponent(state.adrMinAge), null, reqEpoch),
        apiFetch('/api/audit/verify', null, reqEpoch)
      ];
      if (isSuper) {
        fetchPromises.push(apiFetch('/api/admin/patients', null, reqEpoch));
        fetchPromises.push(apiFetch('/api/admin/users', null, reqEpoch));
      }"""
    new_admin_load = """      const isSuper = Boolean((state.user && state.user.role === 'superadmin') || window.ENDOLOG_STATIC_DEMO);
      const fetchPromises = [
        apiFetch('/api/cases', null, reqEpoch),
        apiFetch('/api/surveillance', null, reqEpoch),
        apiFetch('/api/metrics/kpi?min_adr_age=' + encodeURIComponent(state.adrMinAge), null, reqEpoch),
        apiFetch('/api/audit/verify', null, reqEpoch)
      ];
      if (isSuper) {
        fetchPromises.push(apiFetch('/api/admin/patients', null, reqEpoch));
        fetchPromises.push(apiFetch('/api/admin/users', null, reqEpoch));
      }"""
    js = _assert_replace_once(js, old_admin_load, new_admin_load, "DEMO_LOAD_ADMIN_ILLUSTRATION")

    # 3. Render both the showcase read-only notice AND the 4-card Superadmin illustration layout in static demo
    old_super_render = """    if (noticeEl) noticeEl.hidden = isSuper;
    if (gridEl) gridEl.hidden = !isSuper;
    if (!isSuper) return;"""
    new_super_render = """    const showDemoAdminLayout = Boolean(isSuper || window.ENDOLOG_STATIC_DEMO);
    if (noticeEl) noticeEl.hidden = Boolean(isSuper && !window.ENDOLOG_STATIC_DEMO);
    if (gridEl) gridEl.hidden = !showDemoAdminLayout;
    if (!showDemoAdminLayout) return;"""
    js = _assert_replace_once(js, old_super_render, new_super_render, "DEMO_RENDER_ADMIN_ILLUSTRATION")

    return js


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
    return f"""/* EndoLog GitHub Pages Showcase Service Worker v{version}
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


def build_gh_pages_demo(output_dir: Path, base_path: str = "/endolog/") -> dict[str, Any]:
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

    # 5. Generate precomputed OD-05 JSON bundle directly from Python clinical/KPI/CUSUM/audit engines
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

    built_files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    return {
        "output_dir": str(out),
        "base_path": norm_base,
        "version": __version__,
        "case_count": len(bundle["cases_response"]["items"]),
        "file_count": len(built_files),
        "quarantined_previous_dir": str(quarantined) if quarantined else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build EndoLog Gate C Showcase-Only Synthetic Sandbox (Phương án G1) into dist_pages/."
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "dist_pages"),
        help="Output directory for GitHub Pages static bundle (default: dist_pages/).",
    )
    parser.add_argument(
        "--base-path",
        default="/endolog/",
        help="GitHub Pages project subpath (default: /endolog/).",
    )
    args = parser.parse_args()
    summary = build_gh_pages_demo(Path(args.output), base_path=args.base_path)
    print(f"GH_PAGES_DEMO_BUILD_OK: {json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
