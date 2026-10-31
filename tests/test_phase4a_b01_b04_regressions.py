"""Phase 4A B01–B04 regression suite: dynamic KPI badges, logout/401/timeout/stale-fetch DOM wipe, Zero-PHI HTTP/cookie contract, and Vietnamese enum mapping."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from endolog.clinical.quality_metrics import compute_kpi_snapshot
from endolog.core.config import EndoLogSettings
from endolog.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_JS_PATH = REPO_ROOT / "src" / "endolog" / "static" / "js" / "app.js"


def _build_seeded_client(tmp_path: Path, *, auto_seed: bool = True) -> TestClient:
    d_dir = tmp_path / "data_synthetic_dev"
    b_dir = tmp_path / "data_backups"
    cfg = EndoLogSettings(
        env_mode="local_dev_synthetic",
        enable_dev_bypass=True,
        bind_host="127.0.0.1",
        data_dir=d_dir,
        backup_dir=b_dir,
        jwt_secret="regression-test-jwt-secret-key-32-chars",
        master_research_key=b"regression-master-key-32-bytes!!",
        shift_key=b"regression-shift-key-32-bytes!!!",
    )
    app = create_app(cfg, auto_seed_synthetic=auto_seed)
    return TestClient(app, client=("127.0.0.1", 52100), base_url="http://localhost")


def _run_node_vm_harness(script_body: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute real src/endolog/static/js/app.js inside a minimal deterministic DOM VM harness."""
    harness = r"""
const fs = require('fs');
const vm = require('vm');

const appJsPath = process.env.ENDOLOG_APP_JS;
const payload = JSON.parse(process.env.ENDOLOG_TEST_PAYLOAD || '{}');
const code = fs.readFileSync(appJsPath, 'utf8');

class FakeElement {
  constructor(tag, id = '', attrs = {}) {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.attributes = Object.assign({}, attrs);
    this.hidden = Boolean(attrs.hidden);
    this.value = attrs.value || '';
    this.defaultValue = attrs.value || '';
    this._innerHTML = '';
    this._textContent = attrs.textContent || '';
    this.listeners = {};
  }
  get innerHTML() { return this._innerHTML; }
  set innerHTML(v) {
    this._innerHTML = String(v == null ? '' : v);
    this._textContent = this._innerHTML.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  }
  get textContent() { return this._textContent; }
  set textContent(v) {
    this._textContent = String(v == null ? '' : v);
    this._innerHTML = this._textContent;
  }
  replaceChildren() {
    this._innerHTML = '';
    this._textContent = '';
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === 'hidden') this.hidden = true;
  }
  removeAttribute(k) {
    delete this.attributes[k];
    if (k === 'hidden') this.hidden = false;
  }
  getAttribute(k) {
    return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null;
  }
  addEventListener(type, fn) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(fn);
  }
  async dispatch(type, ev = {}) {
    const fns = this.listeners[type] || [];
    for (const fn of fns) {
      await fn(Object.assign({ preventDefault() {} }, ev));
    }
  }
}

function makeStorage() {
  const store = Object.create(null);
  return {
    getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setItem(k, v) { store[String(k)] = String(v); },
    removeItem(k) { delete store[String(k)]; },
    clear() { for (const k of Object.keys(store)) delete store[k]; },
    _dump() { return Object.assign({}, store); }
  };
}
""" + """
const elementsById = Object.create(null);
function reg(tag, id, attrs = {}) {
  const el = new FakeElement(tag, id, attrs);
  if (id) elementsById[id] = el;
  return el;
}

reg('meta', 'el-meta-theme', { content: '' });
reg('section', 'el-login-screen', { hidden: true });
reg('div', 'el-app-shell', { hidden: true });
reg('input', 'el-login-username', { value: 'nguyenbinhan' });
reg('input', 'el-login-password', { value: '' });
reg('form', 'el-login-form');
reg('button', 'el-btn-dev-bypass', { hidden: true });
reg('div', 'el-login-error', { hidden: true });
reg('div', 'el-user-name');
reg('div', 'el-user-dept');
reg('button', 'el-theme-toggle');
reg('svg', 'el-icon-moon');
reg('svg', 'el-icon-sun', { hidden: true });
reg('span', 'el-theme-label', { textContent: 'Nền tối' });
reg('button', 'el-btn-logout');
reg('section', 'el-view-cases');
reg('section', 'el-view-surveillance', { hidden: true });
reg('section', 'el-view-quality', { hidden: true });
reg('button', 'el-btn-export-csv');
reg('div', 'el-cases-summary');
reg('input', 'el-case-search', { value: '' });
reg('div', 'el-case-list');
reg('div', 'el-surveillance-list');
reg('div', 'el-kpi-grid');
reg('p', 'el-cusum-disclaimer');
reg('div', 'el-cusum-container');
reg('div', 'el-audit-strip');

const navButtons = ['cases', 'surveillance', 'quality'].map((t, i) =>
  new FakeElement('button', '', { 'data-nav-target': t, 'aria-selected': i === 0 ? 'true' : 'false' })
);
const trackPills = ['ALL', 'EGD', 'COL', 'ERCP'].map((t, i) =>
  new FakeElement('button', '', { 'data-track-filter': t, 'aria-pressed': i === 0 ? 'true' : 'false' })
);
const survPills = ['ALL', 'urgent', 'due', 'pending'].map((t, i) =>
  new FakeElement('button', '', { 'data-surv-filter': t, 'aria-pressed': i === 0 ? 'true' : 'false' })
);
const agePills = ['45', '50'].map((t, i) =>
  new FakeElement('button', '', { 'data-age-toggle': t, 'aria-pressed': i === 0 ? 'true' : 'false' })
);
const cusumPills = ['CIR', 'ERCP_NATIVE'].map((t, i) =>
  new FakeElement('button', '', { 'data-cusum-metric': t, 'aria-pressed': i === 0 ? 'true' : 'false' })
);

const docEl = new FakeElement('html');
const domReadyListeners = [];
const winListeners = {};
const localStore = makeStorage();
const sessionStore = makeStorage();

const selectorMap = {
  '[data-nav-target]': navButtons,
  '[data-track-filter]': trackPills,
  '[data-surv-filter]': survPills,
  '[data-age-toggle]': agePills,
  '[data-cusum-metric]': cusumPills,
};

let fetchImpl = async () => ({ ok: true, status: 200, async json() { return {}; } });

const sandbox = {
  console,
  URLSearchParams,
  AbortController,
  setTimeout,
  clearTimeout,
  getComputedStyle: () => ({ getPropertyValue: () => '#475985' }),
  fetch: (...args) => fetchImpl(...args),
  navigator: {},
  document: {
    documentElement: docEl,
    getElementById: (id) => elementsById[id] || null,
    querySelectorAll: (sel) => selectorMap[sel] || [],
    addEventListener: (t, fn) => { if (t === 'DOMContentLoaded') domReadyListeners.push(fn); }
  },
  window: null,
};
sandbox.window = {
  location: { search: '?login=1', href: 'http://127.0.0.1:8765/?login=1' },
  localStorage: localStore,
  sessionStorage: sessionStore,
  setTimeout,
  clearTimeout,
  addEventListener: (t, fn) => {
    if (!winListeners[t]) winListeners[t] = [];
    winListeners[t].push(fn);
  },
  __ENDOLOG_RUNTIME_AUDIT__: null,
};
Object.defineProperty(sandbox.window.localStorage, '__keys_helper', { enumerable: false, value: true });

// Proxy Object.keys-friendly storages
function makeEnumerableStorage() {
  const obj = {};
  Object.defineProperty(obj, 'getItem', { enumerable: false, value: (k) => Object.prototype.hasOwnProperty.call(obj, k) ? obj[k] : null });
  Object.defineProperty(obj, 'setItem', { enumerable: false, value: (k, v) => { obj[String(k)] = String(v); } });
  Object.defineProperty(obj, 'removeItem', { enumerable: false, value: (k) => { delete obj[String(k)]; } });
  Object.defineProperty(obj, 'clear', { enumerable: false, value: () => { for (const k of Object.keys(obj)) delete obj[k]; } });
  return obj;
}
sandbox.window.localStorage = makeEnumerableStorage();
sandbox.window.sessionStorage = makeEnumerableStorage();

function dumpAllVisibleAndHiddenDom() {
  const parts = [];
  for (const [id, el] of Object.entries(elementsById)) {
    parts.push(id + ':' + el.value + ':' + el.innerHTML + ':' + el.textContent);
  }
  return parts.join('\\n');
}

(async () => {
""" + script_body + """
  process.exit(0);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
"""
    proc = subprocess.run(
        ["node", "-e", harness],
        env={
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "ENDOLOG_APP_JS": str(APP_JS_PATH),
            "ENDOLOG_TEST_PAYLOAD": json.dumps(payload or {}, ensure_ascii=False),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    return json.loads(lines[-1])


def test_b01_kpi_status_badges_below_exact_above_and_zero_denominator() -> None:
    empty_kpi = compute_kpi_snapshot([], patients_by_id={}, min_adr_age=45)

    res = _run_node_vm_harness(
        r"""
        fetchImpl = async (url) => {
          if (url === '/api/health') return { ok: true, status: 200, async json() { return { status: 'ok', local_bypass_candidate: true }; } };
          if (url === '/api/auth/local-bypass') return { ok: true, status: 200, async json() { return { user: { username: 'nguyenbinhan', display_name: 'ThS. BSCKI. Nguyễn Bình An', department: 'Khoa Nội soi Tiêu hóa' } }; } };
          if (url === '/api/cases') return { ok: true, status: 200, async json() { return { items: [] }; } };
          if (url === '/api/surveillance') return { ok: true, status: 200, async json() { return { items: [] }; } };
          if (url.startsWith('/api/metrics/kpi')) return { ok: true, status: 200, async json() { return currentKpiBundle; } };
          if (url === '/api/audit/verify') return { ok: true, status: 200, async json() { return { verification: { valid: true, checked_entries: 1, head_hash: 'abc' } }; } };
          return { ok: true, status: 200, async json() { return {}; } };
        };

        const zeroRatesBundle = {
          kpi: {
            min_adr_age: 45,
            cir: { numerator: 0, denominator: 10, rate_pct: 0.0, target_pct: 90.0 },
            bbps_adequate: { numerator: 0, denominator: 10, rate_pct: 0.0, target_pct: 90.0 },
            pdr: { numerator: 0, denominator: 10, rate_pct: 0.0 },
            adr: { numerator: 0, denominator: 10, rate_pct: 0.0, target_pct: 35.0, pending_gpb_excluded_count: 0 },
            ssldr: { numerator: 0, denominator: 10, rate_pct: 0.0, target_pct: 6.0, pending_gpb_excluded_count: 0 },
            ercp_native_cannulation: { numerator: 0, denominator: 10, rate_pct: 0.0, target_pct: 90.0, difficult_esge2016_count: 0 },
            adverse_events_all: { agree_any_numerator: 0, agree_severe_numerator: 0, completed_fu_denominator: 10, agree_severe_rate_pct: 0.0, missing_or_pending_fu_count: 0 },
            ercp_pep: { numerator: 0, completed_fu_denominator: 10, rate_pct: 0.0, missing_or_pending_fu_count: 0 },
          },
          cusum_cir: { disclaimer_vi: 'CUSUM cá nhân', ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL', h_limit: 2.89, points: [], trajectory: [0] },
          cusum_ercp: { disclaimer_vi: 'CUSUM cá nhân', ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL', h_limit: 2.89, points: [], trajectory: [0] },
        };

        let currentKpiBundle = zeroRatesBundle;
        vm.runInNewContext(code, sandbox);
        for (const fn of domReadyListeners) await fn();
        await elementsById['el-btn-dev-bypass'].dispatch('click');
        const zeroHtml = elementsById['el-kpi-grid'].innerHTML;

        currentKpiBundle = {
          kpi: payload.empty_kpi,
          cusum_cir: zeroRatesBundle.cusum_cir,
          cusum_ercp: zeroRatesBundle.cusum_ercp,
        };
        await agePills[0].dispatch('click');
        const emptyHtml = elementsById['el-kpi-grid'].innerHTML;

        const api = sandbox.window.__ENDOLOG_RUNTIME_AUDIT__;
        const below = [
          api.evaluateKpiRateBadge({ denominator: 10, rate_pct: 89.9, target_pct: 90.0 }),
          api.evaluateKpiRateBadge({ denominator: 10, rate_pct: 34.9, target_pct: 35.0 }),
          api.evaluateKpiRateBadge({ denominator: 10, rate_pct: 5.9, target_pct: 6.0 }),
        ];
        const exact = [
          api.evaluateKpiRateBadge({ denominator: 10, rate_pct: 90.0, target_pct: 90.0 }),
          api.evaluateKpiRateBadge({ denominator: 20, rate_pct: 35.0, target_pct: 35.0 }),
          api.evaluateKpiRateBadge({ denominator: 50, rate_pct: 6.0, target_pct: 6.0 }),
        ];
        const above = [
          api.evaluateKpiRateBadge({ denominator: 10, rate_pct: 95.0, target_pct: 90.0 }),
          api.evaluateKpiRateBadge({ denominator: 10, rate_pct: 50.0, target_pct: 35.0 }),
          api.evaluateKpiRateBadge({ denominator: 10, rate_pct: 12.0, target_pct: 6.0 }),
        ];
        const zeroWithPendingGpb = api.evaluateKpiRateBadge({
          denominator: 0,
          rate_pct: null,
          target_pct: 35.0,
          pending_gpb_excluded_count: 2,
        });
        const nullDenominator = api.evaluateKpiRateBadge({
          numerator: 0,
          denominator: null,
          rate_pct: null,
          target_pct: 90.0,
        });
        const roundingBoundary36Over103 = api.evaluateKpiRateBadge({
          numerator: 36,
          denominator: 103,
          rate_pct: 35.0,
          target_pct: 35.0,
        });
        const noTarget = api.evaluateKpiRateBadge({ denominator: 8, rate_pct: 50.0, target_pct: null });
        const aeSevere = api.evaluateAdverseEventKpiBadge(
          { completed_fu_denominator: 5, agree_severe_rate_pct: 20.0, agree_severe_numerator: 1, agree_any_numerator: 1, missing_or_pending_fu_count: 0 },
          { numerator: 0 }
        );
        const aePepSevereOnly = api.evaluateAdverseEventKpiBadge(
          { completed_fu_denominator: 5, agree_severe_rate_pct: 0.0, agree_severe_numerator: 0, agree_any_numerator: 1, pending_window_count: 0, lost_to_followup_count: 0 },
          { numerator: 1, pep_severe_numerator: 1 }
        );
        const aeLostToFollowupOnly = api.evaluateAdverseEventKpiBadge(
          { completed_fu_denominator: 4, agree_severe_rate_pct: 0.0, agree_severe_numerator: 0, agree_any_numerator: 0, pending_window_count: 0, lost_to_followup_count: 2 },
          { numerator: 0, pep_severe_numerator: 0 }
        );
        const aePendingWindowOnly = api.evaluateAdverseEventKpiBadge(
          { completed_fu_denominator: 0, agree_severe_rate_pct: null, agree_severe_numerator: 0, agree_any_numerator: 0, missing_or_pending_fu_count: 3 },
          { numerator: 0 }
        );

        console.log(JSON.stringify({
          zeroDatChuanCount: (zeroHtml.match(/Đạt chuẩn/g) || []).length,
          zeroDatNguongCount: (zeroHtml.match(/Đạt ngưỡng/g) || []).length,
          zeroChuaDatCount: (zeroHtml.match(/Chưa đạt ngưỡng/g) || []).length,
          emptyChuaDuDuLieuCount: (emptyHtml.match(/Chưa đủ dữ liệu/g) || []).length,
          emptyDatCount: (emptyHtml.match(/Đạt chuẩn|Đạt ngưỡng/g) || []).length,
          below,
          exact,
          above,
          zeroWithPendingGpb,
          nullDenominator,
          roundingBoundary36Over103,
          noTarget,
          aeSevere,
          aePepSevereOnly,
          aeLostToFollowupOnly,
          aePendingWindowOnly,
        }));
        """,
        payload={"empty_kpi": empty_kpi},
    )

    assert res["zeroDatChuanCount"] == 0
    assert res["zeroDatNguongCount"] == 0
    assert res["zeroChuaDatCount"] == 5
    assert res["emptyChuaDuDuLieuCount"] == 6
    assert res["emptyDatCount"] == 0

    assert all(b["tone"] == "urgent" and "Chưa đạt ngưỡng" in b["label"] for b in res["below"])
    assert all(b["tone"] == "ned" and "Đạt ngưỡng" in b["label"] for b in res["exact"])
    assert all(b["tone"] == "ned" and "Đạt ngưỡng" in b["label"] for b in res["above"])
    assert res["zeroWithPendingGpb"] == {"tone": "pending", "label": "Chưa đủ dữ liệu (2 ca chờ GPB)"}
    assert res["nullDenominator"] == {"tone": "neutral", "label": "Chưa đủ dữ liệu"}
    assert res["roundingBoundary36Over103"] == {"tone": "urgent", "label": "Chưa đạt ngưỡng (< 35%)"}
    assert res["noTarget"] == {"tone": "neutral", "label": "Chưa thiết lập ngưỡng"}
    assert res["aeSevere"]["tone"] == "urgent"
    assert "AGREE ≥ III" in res["aeSevere"]["label"]
    assert res["aePepSevereOnly"] == {"tone": "urgent", "label": "Có biến cố PEP mức độ nặng (1 ca)"}
    assert res["aeLostToFollowupOnly"] == {"tone": "neutral", "label": "0 biến cố đã đóng · 2 ca mất dấu theo dõi"}
    assert res["aePendingWindowOnly"] == {"tone": "due", "label": "Chưa đủ dữ liệu (3 ca chờ cửa sổ)"}


def test_b02_logout_200_network_error_500_401_idle_timeout_and_stale_request_isolation() -> None:
    res = _run_node_vm_harness(
        r"""
        let logoutMode = 'ok200';
        let forceAge401 = false;
        let deferredCusumResolve = null;
        let deferredLogoutResolve = null;
        let currentSessionTag = 'S1';
        const callOrder = [];

        function sampleBundleFor(tag) {
          return {
            cases: [{
              case_id: 'cas_' + tag,
              case_code: 'SYNTHETIC_CASE_' + tag,
              track: 'ERCP',
              care_setting: 'INPATIENT',
              procedure_start_at: '2026-10-27T11:05:00',
              indication: 'BILIARY_STONE',
              indication_detail: 'Sỏi ống mật chủ ' + tag,
              pathology_completion_status: 'COMPLETE',
              followup_30d_status: 'COMPLETED_NO_AE',
              patient: { privacy_initials: 'SYN.' + tag, age: 62, sex: 'F', hospital_mrn_masked: '***9999' },
              clinical_badge: { tone: 'ned', label: 'Không biến cố / hoàn tất' },
              ercp_computed: { papilla_status: 'NATIVE_INTACT', vater_papilla_type: '1', selective_cannulation: 'SUCCESS', difficult_cannulation_esge2016: 'NO', ercp_session_index_in_episode: 1 },
              surveillance: { guideline_id: 'CLINICIAN_DIRECTED_ERCP', category: 'NEEDS_PHYSICIAN_REVIEW', recommended_interval_label: 'Theo chỉ định lâm sàng' },
            }],
            surv: [{
              case_id: 'cas_' + tag,
              case_code: 'SYNTHETIC_CASE_' + tag,
              track: 'ERCP',
              procedure_date: '2026-10-27',
              indication_detail: 'Sỏi ống mật chủ ' + tag,
              patient: { privacy_initials: 'SYN.' + tag, age: 62, sex: 'F' },
              surveillance: { guideline_id: 'CLINICIAN_DIRECTED_ERCP', category: 'NEEDS_PHYSICIAN_REVIEW', recommended_interval_label: 'Theo chỉ định lâm sàng', reason: 'Theo dõi ' + tag },
              urgency: { tone: 'urgent', label: 'Cảnh báo ' + tag },
            }],
            kpi: {
              kpi: {
                min_adr_age: 45,
                cir: { numerator: 9, denominator: 10, rate_pct: 90.0, target_pct: 90.0 },
                bbps_adequate: { numerator: 9, denominator: 10, rate_pct: 90.0, target_pct: 90.0 },
                pdr: { numerator: 5, denominator: 10, rate_pct: 50.0 },
                adr: { numerator: 4, denominator: 10, rate_pct: 40.0, target_pct: 35.0, pending_gpb_excluded_count: 0 },
                ssldr: { numerator: 1, denominator: 10, rate_pct: 10.0, target_pct: 6.0, pending_gpb_excluded_count: 0 },
                ercp_native_cannulation: { numerator: 9, denominator: 10, rate_pct: 90.0, target_pct: 90.0, difficult_esge2016_count: 1 },
                adverse_events_all: { agree_any_numerator: 0, agree_severe_numerator: 0, completed_fu_denominator: 10, agree_severe_rate_pct: 0.0, missing_or_pending_fu_count: 0 },
                ercp_pep: { numerator: 0, completed_fu_denominator: 10, rate_pct: 0.0, missing_or_pending_fu_count: 0 },
              },
              cusum_cir: { disclaimer_vi: 'CUSUM ' + tag, ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL', h_limit: 2.89, points: [{ case_code: 'SYNTHETIC_CASE_' + tag }], trajectory: [0, 0.1] },
              cusum_ercp: { disclaimer_vi: 'CUSUM ' + tag, ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL', h_limit: 2.89, points: [{ case_code: 'SYNTHETIC_CASE_' + tag }], trajectory: [0, 0.1] },
            }
          };
        }

        fetchImpl = async (url) => {
          const data = sampleBundleFor(currentSessionTag);
          if (url === '/api/health') return { ok: true, status: 200, async json() { return { status: 'ok', local_bypass_candidate: true }; } };
          if (url === '/api/auth/local-bypass') {
            callOrder.push('bypass_start:' + currentSessionTag);
            return {
              ok: true,
              status: 200,
              async json() {
                return { user: { username: 'user_' + currentSessionTag, display_name: 'BS_' + currentSessionTag, department: 'KHOA_' + currentSessionTag } };
              }
            };
          }
          if (url === '/api/auth/logout') {
            callOrder.push('logout_start:' + currentSessionTag);
            if (deferredLogoutResolve) {
              const resp = await new Promise((resolve) => { deferredLogoutResolve = resolve; });
              callOrder.push('logout_end:' + currentSessionTag);
              return resp;
            }
            if (logoutMode === 'reject') throw new Error('Simulated offline network failure');
            if (logoutMode === 'http500') return { ok: false, status: 500, async json() { return {}; } };
            callOrder.push('logout_end:' + currentSessionTag);
            return { ok: true, status: 200, async json() { return { authenticated: false }; } };
          }
          if (url === '/api/cases') return { ok: true, status: 200, async json() { return { items: data.cases }; } };
          if (url === '/api/surveillance') return { ok: true, status: 200, async json() { return { items: data.surv }; } };
          if (url.startsWith('/api/metrics/kpi')) {
            if (forceAge401 && url.includes('min_adr_age=50')) {
              return { ok: false, status: 401, async json() { return { detail: 'Expired' }; } };
            }
            return { ok: true, status: 200, async json() { return data.kpi; } };
          }
          if (url.startsWith('/api/metrics/cusum')) {
            if (deferredCusumResolve) {
              return await new Promise((resolve) => { deferredCusumResolve = resolve; });
            }
            return {
              ok: true,
              status: 200,
              async json() {
                return {
                  disclaimer_vi: 'CUSUM_CUSTOM_' + currentSessionTag,
                  ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL',
                  h_limit: 2.89,
                  points: [{ case_code: 'SYNTHETIC_CUSUM_' + currentSessionTag }],
                  trajectory: [0, 0.5],
                };
              }
            };
          }
          if (url === '/api/audit/verify') return { ok: true, status: 200, async json() { return { verification: { valid: true, checked_entries: 3, head_hash: 'SYNTHETIC_HASH_' + currentSessionTag } }; } };
          return { ok: true, status: 200, async json() { return {}; } };
        };

        vm.runInNewContext(code, sandbox);
        for (const fn of domReadyListeners) await fn();
        const api = sandbox.window.__ENDOLOG_RUNTIME_AUDIT__;

        async function dirtySessionAndSnapshot(tag) {
          currentSessionTag = tag;
          await elementsById['el-btn-dev-bypass'].dispatch('click');
          await navButtons[2].dispatch('click');
          await trackPills[3].dispatch('click');
          await survPills[1].dispatch('click');
          await cusumPills[1].dispatch('click');
          elementsById['el-case-search'].value = 'SYNTHETIC_PATIENT_QUERY_' + tag;
          await elementsById['el-case-search'].dispatch('input');
        }

        // 1. Normal logout (200 OK)
        logoutMode = 'ok200';
        await dirtySessionAndSnapshot('S1');
        await elementsById['el-btn-logout'].dispatch('click');
        const afterNormalLogout = {
          state: api.getSanitizedClientState(),
          searchVal: elementsById['el-case-search'].value,
          sessionKeys: Object.keys(sandbox.window.sessionStorage),
          hasSyntheticInDom: dumpAllVisibleAndHiddenDom().includes('SYNTHETIC_') || dumpAllVisibleAndHiddenDom().includes('BS_S1'),
          errorHidden: elementsById['el-login-error'].hidden,
        };

        // 2. Network-error logout (fetch rejects)
        logoutMode = 'reject';
        await dirtySessionAndSnapshot('NETERR');
        await elementsById['el-btn-logout'].dispatch('click');
        const afterRejectLogout = {
          state: api.getSanitizedClientState(),
          searchVal: elementsById['el-case-search'].value,
          sessionKeys: Object.keys(sandbox.window.sessionStorage),
          hasSyntheticInDom: dumpAllVisibleAndHiddenDom().includes('SYNTHETIC_') || dumpAllVisibleAndHiddenDom().includes('BS_NETERR'),
          errorHidden: elementsById['el-login-error'].hidden,
          errorText: elementsById['el-login-error'].textContent,
        };

        // 3. HTTP 500 logout
        logoutMode = 'http500';
        await dirtySessionAndSnapshot('HTTP500');
        await elementsById['el-btn-logout'].dispatch('click');
        const after500Logout = {
          state: api.getSanitizedClientState(),
          hasSyntheticInDom: dumpAllVisibleAndHiddenDom().includes('SYNTHETIC_'),
          errorHidden: elementsById['el-login-error'].hidden,
          errorText: elementsById['el-login-error'].textContent,
        };

        // 4. Mid-session 401 on API call
        logoutMode = 'ok200';
        await dirtySessionAndSnapshot('EXP401');
        forceAge401 = true;
        await agePills[1].dispatch('click');
        forceAge401 = false;
        const after401 = {
          state: api.getSanitizedClientState(),
          searchVal: elementsById['el-case-search'].value,
          sessionKeys: Object.keys(sandbox.window.sessionStorage),
          hasSyntheticInDom: dumpAllVisibleAndHiddenDom().includes('SYNTHETIC_') || dumpAllVisibleAndHiddenDom().includes('BS_EXP401'),
          errorHidden: elementsById['el-login-error'].hidden,
          errorText: elementsById['el-login-error'].textContent,
        };

        // 5. Idle timeout auto-lock
        await dirtySessionAndSnapshot('IDLE');
        api.setIdleTimeoutForTest(25);
        await new Promise((r) => setTimeout(r, 70));
        const afterIdleTimeout = {
          state: api.getSanitizedClientState(),
          searchVal: elementsById['el-case-search'].value,
          sessionKeys: Object.keys(sandbox.window.sessionStorage),
          hasSyntheticInDom: dumpAllVisibleAndHiddenDom().includes('SYNTHETIC_') || dumpAllVisibleAndHiddenDom().includes('BS_IDLE'),
          errorHidden: elementsById['el-login-error'].hidden,
          errorText: elementsById['el-login-error'].textContent,
        };
        api.setIdleTimeoutForTest(900000);

        // 6. Stale in-flight request from Session STALE_OLD resolving AFTER re-login into Session FRESH_NEW
        currentSessionTag = 'STALE_OLD';
        await elementsById['el-btn-dev-bypass'].dispatch('click');
        deferredCusumResolve = () => {};
        const pendingClickPromise = cusumPills[1].dispatch('click');
        const resolveOldCusum = deferredCusumResolve;
        deferredCusumResolve = null;

        // Logout STALE_OLD and immediately login as FRESH_NEW while STALE_OLD's request is still unresolved
        await elementsById['el-btn-logout'].dispatch('click');
        currentSessionTag = 'FRESH_NEW';
        await elementsById['el-btn-dev-bypass'].dispatch('click');

        // Now resolve STALE_OLD's delayed response!
        resolveOldCusum({
          ok: true,
          status: 200,
          async json() {
            return {
              disclaimer_vi: 'LEAKED_OLD_DISCLAIMER',
              ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL',
              h_limit: 2.89,
              points: [{ case_code: 'LEAKED_STALE_CASE_CODE' }],
              trajectory: [0, 2.5],
            };
          }
        });
        await pendingClickPromise;

        const domAfterStaleResolve = dumpAllVisibleAndHiddenDom();
        const afterStaleRace = {
          state: api.getSanitizedClientState(),
          leakedOldIntoDom: domAfterStaleResolve.includes('LEAKED_') || domAfterStaleResolve.includes('STALE_OLD'),
          freshNewPresentInDom: domAfterStaleResolve.includes('SYNTHETIC_CASE_FRESH_NEW') && domAfterStaleResolve.includes('BS_FRESH_NEW'),
        };

        // 7. Slow /api/auth/logout: user typing credentials is NOT clobbered in finally, and immediate re-login waits for logout first
        deferredLogoutResolve = () => {};
        const slowLogoutPromise1 = elementsById['el-btn-logout'].dispatch('click');
        const resolveSlowLogout1 = deferredLogoutResolve;
        deferredLogoutResolve = null;
        const bypassDisabledDuringLogout = Boolean(elementsById['el-btn-dev-bypass'].disabled);
        elementsById['el-login-username'].value = 'bs_binh_an_typing';
        elementsById['el-login-password'].value = 'MatKhauMoi!';
        resolveSlowLogout1({ ok: false, status: 500, async json() { return {}; } });
        await slowLogoutPromise1;
        const typedInputsPreservedAfterSlowLogout = {
          bypassDisabledDuringLogout,
          bypassReenabledAfterLogout: Boolean(elementsById['el-btn-dev-bypass'].disabled) === false,
          usernameAfter: elementsById['el-login-username'].value,
          passwordAfter: elementsById['el-login-password'].value,
          errorText: elementsById['el-login-error'].textContent,
        };

        // Now verify fast re-login click awaits pendingLogoutPromise before issuing /api/auth/local-bypass
        currentSessionTag = 'SERIAL_OLD';
        await elementsById['el-btn-dev-bypass'].dispatch('click');
        callOrder.length = 0;
        deferredLogoutResolve = () => {};
        const slowLogoutPromise2 = elementsById['el-btn-logout'].dispatch('click');
        const resolveSlowLogout2 = deferredLogoutResolve;
        deferredLogoutResolve = null;
        currentSessionTag = 'SERIAL_NEW';
        const fastReloginPromise = elementsById['el-btn-dev-bypass'].dispatch('click');
        // Resolve slow logout after fastReloginPromise has already started waiting
        await new Promise((r) => setTimeout(r, 15));
        const orderBeforeLogoutResolves = callOrder.slice();
        resolveSlowLogout2({ ok: true, status: 200, async json() { return { authenticated: false }; } });
        await Promise.all([slowLogoutPromise2, fastReloginPromise]);
        const orderAfterRelogin = callOrder.slice();

        // 8. Non-sliding 15-minute hard JWT session expiration (idle timer kept long, hard timer expires)
        await dirtySessionAndSnapshot('HARD_EXP');
        api.setIdleTimeoutForTest(900000);
        api.setHardSessionExpiryForTest(25);
        await new Promise((r) => setTimeout(r, 70));
        const afterHardExpiry = {
          state: api.getSanitizedClientState(),
          hasSyntheticInDom: dumpAllVisibleAndHiddenDom().includes('SYNTHETIC_') || dumpAllVisibleAndHiddenDom().includes('BS_HARD_EXP'),
          errorHidden: elementsById['el-login-error'].hidden,
          errorText: elementsById['el-login-error'].textContent,
        };

        // 9. Intra-session out-of-order CUSUM click race (slow ERCP_NATIVE click followed by fast CIR click)
        currentSessionTag = 'INTRA_SEQ';
        await elementsById['el-btn-dev-bypass'].dispatch('click');
        deferredCusumResolve = () => {};
        const slowErcpClick = cusumPills[1].dispatch('click');
        const resolveSlowErcp = deferredCusumResolve;
        deferredCusumResolve = null;
        // Immediate second click on CIR (fast response)
        await cusumPills[0].dispatch('click');
        // Late resolution of ERCP_NATIVE must be discarded by cusumReqSeq
        resolveSlowErcp({
          ok: true,
          status: 200,
          async json() {
            return {
              disclaimer_vi: 'OUT_OF_ORDER_STALE_ERCP',
              ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL',
              h_limit: 2.89,
              points: [{ case_code: 'OUT_OF_ORDER_ERCP_PT' }],
              trajectory: [0, 1.8],
            };
          }
        });
        await slowErcpClick;
        const intraSeqDom = dumpAllVisibleAndHiddenDom();
        const afterIntraSeqRace = {
          cusumMetric: api.getSanitizedClientState().cusumMetric,
          staleErcpRendered: intraSeqDom.includes('OUT_OF_ORDER_'),
          fastCirRendered: intraSeqDom.includes('CUSUM_CUSTOM_INTRA_SEQ'),
        };

        console.log(JSON.stringify({
          afterNormalLogout,
          afterRejectLogout,
          after500Logout,
          after401,
          afterIdleTimeout,
          afterHardExpiry,
          afterStaleRace,
          typedInputsPreservedAfterSlowLogout,
          orderBeforeLogoutResolves,
          orderAfterRelogin,
          afterIntraSeqRace,
        }));
        """
    )

    for key in ("afterNormalLogout", "afterRejectLogout", "after500Logout", "after401", "afterIdleTimeout", "afterHardExpiry"):
        snap = res[key]
        st = snap["state"]
        assert st["hasUser"] is False, f"{key} failed hasUser"
        assert st["activeView"] == "cases", f"{key} failed activeView"
        assert st["trackFilter"] == "ALL", f"{key} failed trackFilter"
        assert st["survFilter"] == "ALL", f"{key} failed survFilter"
        assert st["searchQueryLength"] == 0, f"{key} failed searchQueryLength"
        assert st["adrMinAge"] == 45, f"{key} failed adrMinAge"
        assert st["cusumMetric"] == "CIR", f"{key} failed cusumMetric"
        assert st["casesCount"] == 0, f"{key} failed casesCount"
        assert st["surveillanceCount"] == 0, f"{key} failed surveillanceCount"
        assert st["hasKpiBundle"] is False, f"{key} failed hasKpiBundle"
        assert st["hasCusumData"] is False, f"{key} failed hasCusumData"
        assert st["hasAuditStatus"] is False, f"{key} failed hasAuditStatus"
        assert st["hasIdleTimer"] is False, f"{key} failed hasIdleTimer"
        assert st["hasHardExpiryTimer"] is False, f"{key} failed hasHardExpiryTimer"
        assert snap["hasSyntheticInDom"] is False, f"{key} leaked synthetic DOM content"

    assert res["afterNormalLogout"]["errorHidden"] is True
    assert res["afterNormalLogout"]["sessionKeys"] == []

    assert res["afterRejectLogout"]["errorHidden"] is False
    assert "chưa xác nhận hủy phiên trên máy chủ do lỗi kết nối mạng" in res["afterRejectLogout"]["errorText"]

    assert res["after500Logout"]["errorHidden"] is False
    assert "chưa xác nhận hủy phiên trên máy chủ do máy chủ phản hồi lỗi (HTTP 500)" in res["after500Logout"]["errorText"]

    assert res["after401"]["errorHidden"] is False
    assert "hết hạn" in res["after401"]["errorText"]

    assert res["afterIdleTimeout"]["errorHidden"] is False
    assert "15 phút không thao tác" in res["afterIdleTimeout"]["errorText"]

    assert res["afterHardExpiry"]["errorHidden"] is False
    assert "Phiên xác thực 15 phút đã hết hạn" in res["afterHardExpiry"]["errorText"]

    assert res["afterStaleRace"]["leakedOldIntoDom"] is False
    assert res["afterStaleRace"]["state"]["hasCusumData"] is False
    assert res["afterStaleRace"]["state"]["trackFilter"] == "ALL"
    assert res["afterStaleRace"]["freshNewPresentInDom"] is True

    assert res["typedInputsPreservedAfterSlowLogout"]["bypassDisabledDuringLogout"] is True
    assert res["typedInputsPreservedAfterSlowLogout"]["bypassReenabledAfterLogout"] is True
    assert res["typedInputsPreservedAfterSlowLogout"]["usernameAfter"] == "bs_binh_an_typing"
    assert res["typedInputsPreservedAfterSlowLogout"]["passwordAfter"] == "MatKhauMoi!"
    assert "HTTP 500" in res["typedInputsPreservedAfterSlowLogout"]["errorText"]

    assert res["orderBeforeLogoutResolves"] == ["logout_start:SERIAL_OLD"]
    assert res["orderAfterRelogin"] == ["logout_start:SERIAL_OLD", "logout_end:SERIAL_NEW", "bypass_start:SERIAL_NEW"]

    assert res["afterIntraSeqRace"] == {
        "cusumMetric": "CIR",
        "staleErcpRendered": False,
        "fastCirRendered": True,
    }


def test_b03_zero_phi_http_headers_and_httponly_cookie_contract(tmp_path: Path) -> None:
    client = _build_seeded_client(tmp_path, auto_seed=True)
    r_bypass = client.post("/api/auth/local-bypass", json={"target_username": "nguyenbinhan"})
    assert r_bypass.status_code == 200

    set_cookie_hdr = r_bypass.headers.get("set-cookie", "")
    assert "endolog_session=" in set_cookie_hdr
    assert "HttpOnly" in set_cookie_hdr
    assert "SameSite=strict" in set_cookie_hdr

    api_paths = [
        "/api/health",
        "/api/auth/me",
        "/api/cases",
        "/api/surveillance",
        "/api/metrics/kpi",
        "/api/metrics/cusum?metric=CIR&preset=DEFAULT_90",
        "/api/audit/verify",
        "/api/exports/profile-b?fmt=csv",
        "/api/exports/profile-c?suppress_small_cells=true",
    ]
    for path in api_paths:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
        cc = resp.headers.get("cache-control", "")
        assert "no-store" in cc and "no-cache" in cc and "must-revalidate" in cc and "private" in cc
        assert resp.headers.get("pragma") == "no-cache"
        assert resp.headers.get("expires") == "0"
        assert "default-src 'self'" in resp.headers.get("content-security-policy", "")

    r_logout = client.post("/api/auth/logout")
    assert r_logout.status_code == 200
    assert "Max-Age=0" in r_logout.headers.get("set-cookie", "")
    assert client.get("/api/auth/me").status_code == 401


def test_b04_vietnamese_ui_labels_while_preserving_api_machine_enums(tmp_path: Path) -> None:
    client = _build_seeded_client(tmp_path, auto_seed=True)
    assert client.post("/api/auth/local-bypass", json={"target_username": "nguyenbinhan"}).status_code == 200

    # Add synthetic edge cases: EGD ESD (R0), ERCP moderate PEP, negative diagnostic EGD, and COMPLETED_WITH_AE with agree_grade=NONE
    r_esd = client.post(
        "/api/cases",
        json={
            "full_name": "Ngô Thanh Tùng",
            "birth_year": 1966,
            "sex": "M",
            "hospital_mrn": "SYN-INP-2691",
            "care_setting": "INPATIENT",
            "track": "EGD",
            "indication": "EARLY_CANCER_WORKUP",
            "indication_detail": "",
            "procedure_start_at": "2026-10-28T08:00:00",
            "pathology_completion_status": "COMPLETE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "index_lesion": {
                "anatomical_site": "Thân vị",
                "size_mm": 18.0,
                "paris_class": "0-IIa",
                "resection_method": "ESD",
                "histology_type": "HGD_VIENNA_C4",
                "margins_status": "R0",
            },
        },
    )
    assert r_esd.status_code == 201
    esd_case_code = r_esd.json()["case_code"]

    r_ercp2 = client.post(
        "/api/cases",
        json={
            "full_name": "Bùi Văn Sơn",
            "birth_year": 1961,
            "sex": "M",
            "hospital_mrn": "SYN-INP-2692",
            "care_setting": "INPATIENT",
            "track": "ERCP",
            "indication": "MALIGNANT_STRICTURE",
            "indication_detail": "",
            "procedure_start_at": "2026-10-29T09:30:00",
            "pathology_completion_status": "NOT_APPLICABLE",
            "followup_30d_status": "COMPLETED_WITH_AE",
            "ercp_detail": {
                "papilla_status": "PRIOR_SPHINCTEROTOMY",
                "selective_cannulation": "SUCCESS",
            },
            "adverse_events": [
                {
                    "ae_id": "ae_syn_mod_pep",
                    "window": "INPATIENT_EARLY",
                    "event_type": "PEP",
                    "pep_severity": "MODERATE",
                    "agree_grade": "IIIa",
                }
            ],
        },
    )
    assert r_ercp2.status_code == 201

    r_egd_neg = client.post(
        "/api/cases",
        json={
            "full_name": "Lý Minh Khôi",
            "birth_year": 1984,
            "sex": "M",
            "care_setting": "OUTPATIENT",
            "track": "EGD",
            "indication": "DIAGNOSTIC",
            "indication_detail": "",
            "procedure_start_at": "2026-10-29T10:15:00",
            "pathology_completion_status": "NOT_APPLICABLE",
            "followup_30d_status": "COMPLETED_NO_AE",
        },
    )
    assert r_egd_neg.status_code == 201

    r_egd_emr = client.post(
        "/api/cases",
        json={
            "full_name": "Hoàng Quốc Bảo",
            "birth_year": 1969,
            "sex": "M",
            "hospital_mrn": "SYN-INP-2694",
            "care_setting": "INPATIENT",
            "track": "EGD",
            "indication": "EARLY_CANCER_WORKUP",
            "indication_detail": "",
            "procedure_start_at": "2026-10-29T11:00:00",
            "pathology_completion_status": "COMPLETE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "index_lesion": {
                "anatomical_site": "Tâm vị",
                "size_mm": 12.0,
                "paris_class": "0-IIa",
                "resection_method": "EMR_EN_BLOC",
                "histology_type": "LGD_VIENNA_C3",
                "margins_status": "R0",
            },
        },
    )
    assert r_egd_emr.status_code == 201

    r_egd_named_obs = client.post(
        "/api/cases",
        json={
            "full_name": "Võ Thị Thu",
            "birth_year": 1978,
            "sex": "F",
            "care_setting": "OUTPATIENT",
            "track": "EGD",
            "indication": "DIAGNOSTIC",
            "indication_detail": "",
            "procedure_start_at": "2026-10-29T11:45:00",
            "pathology_completion_status": "NOT_APPLICABLE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "index_lesion": {
                "anatomical_site": "Hang vị",
                "resection_method": "NONE",
                "biopsy_jar_count": 0,
            },
        },
    )
    assert r_egd_named_obs.status_code == 201

    r_ae_ungraded = client.post(
        "/api/cases",
        json={
            "full_name": "Đặng Thị Mai",
            "birth_year": 1972,
            "sex": "F",
            "hospital_mrn": "SYN-INP-2693",
            "care_setting": "INPATIENT",
            "track": "COL",
            "indication": "THERAPEUTIC",
            "indication_detail": "",
            "procedure_start_at": "2026-10-29T14:00:00",
            "cecal_intubation": "YES",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "withdrawal_time_clean_min": 8.0,
            "pathology_completion_status": "COMPLETE",
            "followup_30d_status": "COMPLETED_WITH_AE",
            "adverse_events": [
                {
                    "ae_id": "ae_syn_ungraded",
                    "window": "DELAYED_30D",
                    "event_type": "BLEEDING",
                    "pep_severity": "NONE",
                    "agree_grade": "NONE",
                }
            ],
        },
    )
    assert r_ae_ungraded.status_code == 201
    ae_ungraded_code = r_ae_ungraded.json()["case_code"]

    cases_json = client.get("/api/cases").json()
    surv_json = client.get("/api/surveillance").json()
    kpi_json = client.get("/api/metrics/kpi").json()
    audit_json = client.get("/api/audit/verify").json()

    # Verify COMPLETED_WITH_AE with agree_grade=NONE never produces 'Không biến cố / hoàn tất'
    ungraded_case = next(c for c in cases_json["items"] if c["case_code"] == ae_ungraded_code)
    assert ungraded_case["clinical_badge"]["tone"] == "urgent"
    assert "Không biến cố" not in ungraded_case["clinical_badge"]["label"]

    # 1. Verify API payloads preserve exact machine enum codes
    guideline_ids = {c["surveillance"]["guideline_id"] for c in cases_json["items"]}
    assert {
        "USMSTF_POST_POLYPECTOMY_2020",
        "CLINICIAN_DIRECTED_EGD",
        "CLINICIAN_DIRECTED_ERCP",
        "ESGE_ESD_2022",
    }.issubset(guideline_ids)
    pep_codes = {c["adverse_summary"]["highest_pep_severity"] for c in cases_json["items"]}
    assert {"MILD", "MODERATE"}.issubset(pep_codes)
    assert kpi_json["cusum_cir"]["ra_cusum_status"] == "DISABLED_UNVALIDATED_MODEL"

    # 2. Verify rendered UI across all 3 views emits natural Vietnamese labels with 0 raw machine enums, plus anatomical_site search
    rendered = _run_node_vm_harness(
        r"""
        fetchImpl = async (url) => {
          if (url === '/api/health') return { ok: true, status: 200, async json() { return { status: 'ok', local_bypass_candidate: true }; } };
          if (url === '/api/auth/local-bypass') return { ok: true, status: 200, async json() { return { user: { username: 'nguyenbinhan', display_name: 'ThS. BSCKI. Nguyễn Bình An', department: 'Khoa Nội soi Tiêu hóa' } }; } };
          if (url === '/api/cases') return { ok: true, status: 200, async json() { return payload.cases_json; } };
          if (url === '/api/surveillance') return { ok: true, status: 200, async json() { return payload.surv_json; } };
          if (url.startsWith('/api/metrics/kpi')) return { ok: true, status: 200, async json() { return payload.kpi_json; } };
          if (url === '/api/audit/verify') return { ok: true, status: 200, async json() { return payload.audit_json; } };
          return { ok: true, status: 200, async json() { return {}; } };
        };
        vm.runInNewContext(code, sandbox);
        for (const fn of domReadyListeners) await fn();
        await elementsById['el-btn-dev-bypass'].dispatch('click');

        const casesTextFull = elementsById['el-cases-summary'].textContent + '\n' + elementsById['el-case-list'].textContent;
        elementsById['el-case-search'].value = 'Thân vị';
        await elementsById['el-case-search'].dispatch('input');
        const searchThanViText = elementsById['el-case-list'].textContent;

        console.log(JSON.stringify({
          casesText: casesTextFull,
          searchThanViText,
          survText: elementsById['el-surveillance-list'].textContent,
          qualityText: [
            elementsById['el-kpi-grid'].textContent,
            elementsById['el-cusum-disclaimer'].textContent,
            elementsById['el-audit-strip'].textContent,
          ].join('\n'),
        }));
        """,
        payload={
            "cases_json": cases_json,
            "surv_json": surv_json,
            "kpi_json": kpi_json,
            "audit_json": audit_json,
        },
    )

    combined_ui_text = "\n".join([rendered["casesText"], rendered["survText"], rendered["qualityText"]])
    raw_snake_matches = re.findall(r"\b[A-Z0-9]{2,}(?:_[A-Z0-9]+)+\b", combined_ui_text)
    raw_pep_matches = re.findall(r"\bPEP\s+(?:MILD|MODERATE|SEVERE|NONE)\b", combined_ui_text)

    assert raw_snake_matches == [], f"Raw snake_case enums leaked into UI: {raw_snake_matches}"
    assert raw_pep_matches == [], f"Raw English PEP severity leaked into UI: {raw_pep_matches}"
    assert "Sinh thiết kìm 0 mảnh" not in combined_ui_text

    assert "USMSTF 2020 — hậu cắt polyp" in combined_ui_text
    assert "Hướng dẫn ESGE 2022 (sau cắt tách dưới niêm mạc ESD)" in combined_ui_text
    assert "Cắt tách dưới niêm mạc (ESD) (diện cắt R0)" in combined_ui_text
    assert "Cắt niêm mạc nguyên khối qua nội soi (EMR) (diện cắt R0)" in combined_ui_text
    assert "Quan sát chẩn đoán · Không bấm sinh thiết" in combined_ui_text
    assert "Không ghi nhận tổn thương khu trú" in combined_ui_text
    assert "Theo chỉ định bác sĩ — nội soi thực quản, dạ dày, tá tràng" in combined_ui_text
    assert "Theo chỉ định bác sĩ — nội soi mật tụy ngược dòng (ERCP)" in combined_ui_text
    assert "Biến cố PEP mức độ nhẹ · AGREE độ II" in combined_ui_text
    assert "Biến cố PEP mức độ trung bình · AGREE độ IIIa" in combined_ui_text
    assert "Có biến cố sau thủ thuật (chưa phân độ AGREE)" in combined_ui_text
    assert "Hẹp đường mật nghi ác tính" in combined_ui_text
    assert "Đang khóa hiệu chỉnh nguy cơ — chưa có mô hình ngoại kiểm tại đơn vị" in combined_ui_text
    assert esd_case_code in rendered["searchThanViText"]
