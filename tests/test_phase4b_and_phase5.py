"""Phase 4B & Phase 5 regression suite: linked follow-up surveillance loop closure, OCC If-Match ETag header guard, DLP multi-field rejection, clinical settings roundtrip, Superadmin RBAC, and open-drawer PHI wipe on logout/401/idle."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from endolog.core.config import EndoLogSettings
from endolog.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_JS_PATH = REPO_ROOT / "src" / "endolog" / "static" / "js" / "app.js"


def _build_client(tmp_path: Path, *, auto_seed: bool = False) -> TestClient:
    d_dir = tmp_path / "data_synthetic_dev"
    b_dir = tmp_path / "data_backups"
    cfg = EndoLogSettings(
        env_mode="local_dev_synthetic",
        enable_dev_bypass=True,
        bind_host="127.0.0.1",
        data_dir=d_dir,
        backup_dir=b_dir,
        jwt_secret="phase4b-test-jwt-secret-key-32-chars",
        master_research_key=b"phase4b-master-key-32-bytes!!!!!",
        shift_key=b"phase4b-shift-key-32-bytes!!!!!!",
    )
    app = create_app(cfg, auto_seed_synthetic=auto_seed)
    return TestClient(app, client=("127.0.0.1", 52200), base_url="http://localhost")


def _login_bypass(client: TestClient, username: str = "nguyenbinhan") -> dict[str, Any]:
    r = client.post("/api/auth/local-bypass", json={"target_username": username})
    assert r.status_code == 200, r.text
    return r.json()


def test_create_linked_followup_case_closes_origin_surveillance_loop(tmp_path: Path) -> None:
    client = _build_client(tmp_path, auto_seed=False)
    _login_bypass(client, "nguyenbinhan")

    # 1. Create origin COL case with 3 tubular adenomas (<10 mm, LGD) -> USMSTF 3-5y (36m)
    r_origin = client.post(
        "/api/cases",
        json={
            "full_name": "Phan Văn Hoàng",
            "birth_year": 1970,
            "sex": "M",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-01T08:30:00+07:00",
            "indication": "SCREENING",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 9.0,
            "pathology_completion_status": "COMPLETE",
            "followup_30d_status": "COMPLETED_NO_AE",
            "index_lesion": {
                "anatomical_site": "Đại tràng ngang",
                "size_mm": 7.0,
                "paris_class": "0-Is",
                "resection_method": "COLD_SNARE",
                "biopsy_jar_count": 1,
                "histology_type": "TUBULAR_ADENOMA",
                "dysplasia_grade": "LGD",
                "margins_status": "R0",
            },
            "whole_case_summary": {
                "macroscopic_polyp_count": 3,
                "complete_resection_all_lesions": "ALL_RESECTED_COMPLETELY",
                "any_piecemeal_ge_20mm": "NO",
                "any_confirmed_adenoma": "YES",
                "confirmed_adenoma_count_bin": "3_4",
                "max_adenoma_size_mm": 7.0,
                "any_villous_or_hgd_any_lesion": "NO",
                "any_hgd_any_lesion": "NO",
                "any_confirmed_ssl": "NO",
                "confirmed_ssl_count_bin": "0",
                "any_ssl_with_dysplasia_or_tsa": "NO",
                "any_invasive_cancer_or_noncurative_feature": "NO",
            },
        },
    )
    assert r_origin.status_code == 201, r_origin.text
    origin = r_origin.json()
    origin_case_id = origin["case_id"]
    origin_rec_id = origin["surveillance"]["rec_id"]
    patient_uid = origin["patient"]["patient_uid"]
    assert origin["surveillance"]["fulfilled_by_case_id"] is None
    assert origin["surveillance"]["is_divergent_guideline"] is True

    # 2. Create linked follow-up COL case passing patient_uid + fulfill_surveillance_rec_id
    r_followup = client.post(
        "/api/cases",
        json={
            "patient_uid": patient_uid,
            "full_name": "Phan Văn Hoàng",
            "birth_year": 1970,
            "sex": "M",
            "care_setting": "OUTPATIENT",
            "track": "COL",
            "procedure_start_at": "2026-10-31T09:15:00+07:00",
            "indication": "SURVEILLANCE",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "withdrawal_time_clean_min": 8.5,
            "pathology_completion_status": "NOT_APPLICABLE",
            "followup_30d_status": "PENDING_WINDOW",
            "fulfill_surveillance_rec_id": origin_rec_id,
        },
    )
    assert r_followup.status_code == 201, r_followup.text
    followup = r_followup.json()
    assert followup["patient"]["patient_uid"] == patient_uid

    # 3. Verify origin surveillance loop is closed and linked to followup["case_id"]
    surv_rows = client.get("/api/surveillance").json()["items"]
    origin_surv_row = next(item for item in surv_rows if item["case_id"] == origin_case_id)
    assert origin_surv_row["surveillance"]["fulfilled_by_case_id"] == followup["case_id"]
    assert origin_surv_row["surveillance"]["status"] == "COMPLETED_LINKED"
    assert origin_surv_row["urgency"]["tone"] == "ned"

    audit = client.get("/api/audit/verify").json()
    assert audit["verification"]["valid"] is True


def test_patch_if_match_header_occ_and_phase12_updates(tmp_path: Path) -> None:
    client = _build_client(tmp_path, auto_seed=False)
    _login_bypass(client, "nguyenbinhan")

    r_create = client.post(
        "/api/cases",
        json={
            "full_name": "Lê Hữu Nghĩa",
            "birth_year": 1966,
            "sex": "M",
            "hospital_mrn": "HS26-71001",
            "care_setting": "INPATIENT",
            "admission_date": "2026-10-28",
            "referring_dept": "Khoa Ngoại Gan Mật",
            "prior_unrecorded_ercp_offset": 1,
            "track": "COL",
            "procedure_start_at": "2026-10-29T10:00:00+07:00",
            "indication": "DIAGNOSTIC",
            "indication_detail": "Đi cầu phân máu đỏ tươi",
            "bbps_right": 2,
            "bbps_transverse": 2,
            "bbps_left": 2,
            "cecal_intubation": "NO",
            "cecal_failure_reason": "Gập góc đại tràng chậu hông",
        },
    )
    assert r_create.status_code == 201, r_create.text
    created = r_create.json()
    cid = created["case_id"]
    assert created["version"] == 1
    assert r_create.headers.get("etag") == 'W/"v1"'

    # Valid If-Match W/"v1" + expected_version=1 updating Phase 1 & Phase 2 fields -> 200
    r_patch_ok = client.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"v1"'},
        json={
            "expected_version": 1,
            "referring_dept": "Khoa Phẫu thuật Đại trực tràng",
            "indication": "THERAPEUTIC",
            "indication_detail": "Soi lại chuẩn bị đại tràng tích cực",
            "bbps_right": 3,
            "bbps_transverse": 3,
            "bbps_left": 3,
            "cecal_intubation": "YES",
            "cecal_failure_reason": "",
            "withdrawal_time_clean_min": 9.5,
        },
    )
    assert r_patch_ok.status_code == 200, r_patch_ok.text
    assert r_patch_ok.headers.get("etag") == 'W/"v2"'
    patched = r_patch_ok.json()
    assert patched["version"] == 2
    assert patched["episode"]["referring_dept"] == "Khoa Phẫu thuật Đại trực tràng"
    assert patched["cecal_intubation"] == "YES"
    assert patched["bbps"]["adequate"] is True

    # Stale If-Match W/"v1" even with expected_version=2 -> 409 OCC_VERSION_CONFLICT
    r_stale_hdr = client.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"v1"'},
        json={"expected_version": 2, "clinical_note": "Cập nhật từ tab cũ"},
    )
    assert r_stale_hdr.status_code == 409
    assert r_stale_hdr.json()["detail"]["code"] == "OCC_VERSION_CONFLICT"

    # Stale expected_version=1 even with If-Match W/"v2" -> 409 OCC_VERSION_CONFLICT
    r_stale_body = client.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"v2"'},
        json={"expected_version": 1, "clinical_note": "Cập nhật lệch body"},
    )
    assert r_stale_body.status_code == 409
    assert r_stale_body.json()["detail"]["code"] == "OCC_VERSION_CONFLICT"


def test_dlp_blocks_phi_in_clinical_ercp_and_ae_notes_with_422(tmp_path: Path) -> None:
    client = _build_client(tmp_path, auto_seed=False)
    _login_bypass(client, "nguyenbinhan")

    # 1. Phone number in clinical_note -> 422
    r_phone = client.post(
        "/api/cases",
        json={
            "full_name": "Trương Mỹ Linh",
            "birth_year": 1978,
            "sex": "F",
            "care_setting": "OUTPATIENT",
            "track": "EGD",
            "procedure_start_at": "2026-10-31T08:00:00+07:00",
            "indication": "DIAGNOSTIC",
            "clinical_note": "Gọi lại số 0909123456 khi có kết quả",
        },
    )
    assert r_phone.status_code == 422

    # 2. Valid clinical measurements in ERCP note pass 201; CCCD in AE note -> 422 on PATCH
    r_ercp_ok = client.post(
        "/api/cases",
        json={
            "full_name": "Đoàn Thanh Tùng",
            "birth_year": 1962,
            "sex": "M",
            "hospital_mrn": "HS26-90512",
            "care_setting": "INPATIENT",
            "track": "ERCP",
            "procedure_start_at": "2026-10-31T10:30:00+07:00",
            "indication": "BILIARY_STONE",
            "ercp_detail": {
                "papilla_status": "NATIVE_INTACT",
                "vater_papilla_type": "2",
                "target_duct": "CBD",
                "selective_cannulation": "SUCCESS",
                "cannulation_contacts_count": 6,
                "cannulation_time_min": 7.5,
                "total_procedure_time_min": 35.0,
                "unintended_pd_count": 1,
                "biliary_interventions": ["EST", "STONE_EXTRACTION"],
                "pep_prophylaxis": ["RECTAL_NSAID_100MG"],
                "ercp_procedure_note": "Lấy sỏi OMC 12 mm bằng bóng, Bilirubin 8.4 mg/dL, lưu thông tốt.",
            },
        },
    )
    assert r_ercp_ok.status_code == 201, r_ercp_ok.text
    cid = r_ercp_ok.json()["case_id"]

    r_ae_cccd = client.patch(
        f"/api/cases/{cid}",
        headers={"If-Match": 'W/"v1"'},
        json={
            "expected_version": 1,
            "followup_30d_status": "COMPLETED_WITH_AE",
            "adverse_events": [
                {
                    "ae_id": "ae_dlp_1",
                    "window": "INPATIENT_EARLY",
                    "event_type": "PEP",
                    "pep_severity": "MILD",
                    "agree_grade": "II",
                    "note": "CCCD người nhà 079088001234",
                }
            ],
        },
    )
    assert r_ae_cccd.status_code == 422


def test_settings_roundtrip_and_profile_a_rbac(tmp_path: Path) -> None:
    client = _build_client(tmp_path, auto_seed=True)
    _login_bypass(client, "nguyenbinhan")

    # Endoscopist updates clinical settings
    r_set = client.patch(
        "/api/settings",
        json={
            "colo_guideline_mode": "ESGE_2020",
            "kpi_min_sample_size": 15,
            "cusum_preset": "SCREENING_CIR_95",
        },
    )
    assert r_set.status_code == 200, r_set.text
    kpi_json = client.get("/api/metrics/kpi").json()
    assert kpi_json["kpi"]["n_min"] == 15
    assert kpi_json["cusum_cir"]["preset"] == "SCREENING_CIR_95"

    # Endoscopist cannot export Profile A or supersede a case (403)
    r_prof_a_forbidden = client.post(
        "/api/exports/profile-a", json={"passphrase": "MatKhauSaoLuuRatManh2026!"}
    )
    assert r_prof_a_forbidden.status_code == 403

    first_cid = client.get("/api/cases").json()["items"][0]["case_id"]
    assert client.delete(f"/api/cases/{first_cid}").status_code == 403

    # Superadmin (BSCKII. Vũ Khương An) succeeds on both Profile A backup and supersede
    _login_bypass(client, "vukhuongan")
    r_prof_a_ok = client.post(
        "/api/exports/profile-a", json={"passphrase": "MatKhauSaoLuuRatManh2026!"}
    )
    assert r_prof_a_ok.status_code == 200
    envelope = r_prof_a_ok.json()
    assert envelope["contract"] == "EndoLog-Export-Profile-A-v1.0"
    assert envelope["kdf"] == "argon2id"
    assert envelope["cipher"] == "aes-256-gcm"

    r_del_ok = client.delete(f"/api/cases/{first_cid}")
    assert r_del_ok.status_code == 200
    assert client.get("/api/audit/verify").json()["verification"]["valid"] is True


def test_node_vm_drawer_open_unsaved_phi_wiped_on_logout_401_and_idle() -> None:
    """Verify open Phase 4B Case Drawer with unsaved PHI & AE rows is 100% wiped on logout, 401, and idle timeout."""
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync(process.env.ENDOLOG_APP_JS, 'utf8');

class FakeElement {
  constructor(tag, id = '', attrs = {}) {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.attributes = Object.assign({}, attrs);
    this.hidden = Boolean(attrs.hidden);
    this.open = false;
    this.disabled = false;
    this.inert = false;
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
  replaceChildren() { this._innerHTML = ''; this._textContent = ''; }
  focus() {}
  reset() { this.value = ''; }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === 'hidden') this.hidden = true;
    if (k === 'inert') this.inert = true;
  }
  removeAttribute(k) {
    delete this.attributes[k];
    if (k === 'hidden') this.hidden = false;
    if (k === 'inert') this.inert = false;
  }
  getAttribute(k) {
    return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null;
  }
  addEventListener(type, fn) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(fn);
  }
  querySelectorAll() { return []; }
  async dispatch(type, ev = {}) {
    const fns = this.listeners[type] || [];
    for (const fn of fns) {
      await fn(Object.assign({ preventDefault() {}, target: this }, ev));
    }
  }
}

function makeStorage() {
  const s = Object.create(null);
  return {
    getItem(k) { return Object.prototype.hasOwnProperty.call(s, k) ? s[k] : null; },
    setItem(k, v) { s[String(k)] = String(v); },
    removeItem(k) { delete s[String(k)]; },
    clear() { for (const k of Object.keys(s)) delete s[k]; }
  };
}

const byIdMap = Object.create(null);
function reg(tag, id, attrs = {}) {
  const el = new FakeElement(tag, id, attrs);
  byIdMap[id] = el;
  return el;
}

[
  ['meta', 'el-meta-theme', {}],
  ['section', 'el-login-screen', { hidden: true }],
  ['div', 'el-app-shell', { hidden: true }],
  ['input', 'el-login-username', { value: 'nguyenbinhan' }],
  ['input', 'el-login-password', { value: '' }],
  ['form', 'el-login-form', {}],
  ['button', 'el-btn-dev-bypass', { hidden: true }],
  ['div', 'el-login-error', { hidden: true }],
  ['div', 'el-user-name', {}],
  ['div', 'el-user-dept', {}],
  ['button', 'el-theme-toggle', {}],
  ['svg', 'el-icon-moon', {}],
  ['svg', 'el-icon-sun', { hidden: true }],
  ['span', 'el-theme-label', { textContent: 'Nền tối' }],
  ['button', 'el-btn-logout', {}],
  ['section', 'el-view-cases', {}],
  ['section', 'el-view-surveillance', { hidden: true }],
  ['section', 'el-view-quality', { hidden: true }],
  ['button', 'el-btn-new-case', {}],
  ['button', 'el-btn-export-csv', {}],
  ['div', 'el-cases-summary', {}],
  ['input', 'el-case-search', {}],
  ['div', 'el-case-list', {}],
  ['div', 'el-surveillance-list', {}],
  ['div', 'el-kpi-grid', {}],
  ['p', 'el-cusum-disclaimer', {}],
  ['div', 'el-cusum-container', {}],
  ['div', 'el-audit-strip', {}],
  ['div', 'el-case-drawer-backdrop', { hidden: true }],
  ['div', 'el-case-drawer', {}],
  ['div', 'el-dirty-modal-backdrop', { hidden: true }],
  ['div', 'el-dup-modal-backdrop', { hidden: true }],
  ['div', 'el-vault-modal-backdrop', { hidden: true }],
  ['div', 'el-detail-modal-backdrop', { hidden: true }],
  ['div', 'el-detail-modal', {}],
  ['div', 'el-detail-modal-badges', {}],
  ['h3', 'el-detail-modal-title', {}],
  ['div', 'el-detail-modal-body', {}],
  ['button', 'el-btn-detail-close', {}],
  ['button', 'el-btn-detail-close-foot', {}],
  ['form', 'el-case-form', {}],
  ['input', 'el-f-full-name', {}],
  ['input', 'el-f-birth-year', {}],
  ['input', 'el-f-hospital-mrn', {}],
  ['input', 'el-f-clinical-note', {}],
  ['input', 'el-vault-passphrase', {}],
  ['button', 'el-btn-add-ae', {}],
  ['div', 'el-ae-list', {}],
  ['span', 'el-preview-initials', {}],
  ['span', 'el-preview-age', {}],
  ['div', 'el-drawer-alert', { hidden: true }],
  ['span', 'el-drawer-sync-badge', {}],
  ['button', 'el-btn-save-settings', {}]
].forEach(([t, id, a]) => reg(t, id, a));

let nextPatch401 = false;
let logoutOffline = false;

const fakeRes = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  async json() { return body; },
  async blob() { return new Blob([]); }
});

const emptyKpi = {
  kpi: {
    min_adr_age: 45, n_min: 20,
    cir: { numerator: 0, denominator: 0, rate_pct: null, target_pct: 90 },
    bbps_adequate: { numerator: 0, denominator: 0, rate_pct: null, target_pct: 90 },
    adr: { numerator: 0, denominator: 0, rate_pct: null, target_pct: 35, pending_gpb_excluded_count: 0 },
    pdr: { numerator: 0, denominator: 0, rate_pct: null },
    ssldr: { numerator: 0, denominator: 0, rate_pct: null, target_pct: 6 },
    ercp_native_cannulation: { numerator: 0, denominator: 0, rate_pct: null, target_pct: 90, difficult_esge2016_count: 0 },
    ercp_pep: { numerator: 0, completed_fu_denominator: 0 },
    adverse_events_all: { agree_severe_numerator: 0, completed_fu_denominator: 0, agree_severe_rate_pct: null, pending_window_count: 0, lost_to_followup_count: 0 }
  },
  cusum_cir: { points: [], trajectory: [0], h_limit: 2.89, disclaimer_vi: 'QC', ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL' },
  cusum_ercp: { points: [], trajectory: [0], h_limit: 2.89, disclaimer_vi: 'QC', ra_cusum_status: 'DISABLED_UNVALIDATED_MODEL' }
};

const docListeners = {};
const winListeners = {};
const doc = {
  documentElement: new FakeElement('html', 'root'),
  body: { appendChild() {} },
  activeElement: null,
  hidden: false,
  getElementById(id) { return byIdMap[id] || null; },
  querySelectorAll() { return []; },
  createElement(t) { return new FakeElement(t); },
  addEventListener(t, fn) { (docListeners[t] = docListeners[t] || []).push(fn); }
};

const win = {
  document: doc,
  location: { search: '?login=1', href: 'http://localhost/' },
  localStorage: makeStorage(),
  sessionStorage: makeStorage(),
  navigator: {},
  AbortController,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  matchMedia() { return { matches: false }; },
  getComputedStyle() { return { getPropertyValue() { return '#F4F7FC'; } }; },
  addEventListener(t, fn) { (winListeners[t] = winListeners[t] || []).push(fn); },
  async fetch(url) {
    if (url.startsWith('/api/health')) return fakeRes(200, { local_bypass_candidate: true });
    if (url.startsWith('/api/auth/local-bypass')) {
      return fakeRes(200, {
        user: { username: 'nguyenbinhan', display_name: 'ThS. BSCKI. Nguyễn Bình An', role: 'endoscopist' },
        expires_in_seconds: 900
      });
    }
    if (url.startsWith('/api/auth/logout')) {
      if (logoutOffline) throw new Error('Network offline');
      return fakeRes(200, { ok: true });
    }
    if (nextPatch401 && url.startsWith('/api/settings')) {
      return fakeRes(401, { detail: 'Expired' });
    }
    if (url.startsWith('/api/cases')) return fakeRes(200, { items: [], settings: { kpi_min_sample_size: 20 } });
    if (url.startsWith('/api/surveillance')) return fakeRes(200, { items: [] });
    if (url.startsWith('/api/metrics/kpi')) return fakeRes(200, emptyKpi);
    if (url.startsWith('/api/audit/verify')) return fakeRes(200, { verification: { valid: true, checked_entries: 1, head_hash: 'abc' } });
    return fakeRes(200, {});
  }
};
win.window = win;
vm.runInNewContext(code, Object.assign(win, {
  fetch: win.fetch.bind(win),
  getComputedStyle: win.getComputedStyle.bind(win),
  Date, Math, Number, String, Boolean, Array, Object, Promise, Error, JSON, encodeURIComponent, parseInt
}));

(async () => {
  for (const fn of (docListeners.DOMContentLoaded || [])) await fn();
  await new Promise(r => setTimeout(r, 20));

  async function seedOpenDirtyDrawer() {
    await byIdMap['el-btn-dev-bypass'].dispatch('click');
    await new Promise(r => setTimeout(r, 20));
    await byIdMap['el-btn-new-case'].dispatch('click');
    byIdMap['el-f-full-name'].value = 'Nguyễn Văn Thử Nghiệm';
    await byIdMap['el-f-full-name'].dispatch('input');
    byIdMap['el-f-birth-year'].value = '1968';
    byIdMap['el-f-hospital-mrn'].value = 'HS26-99999';
    byIdMap['el-f-clinical-note'].value = 'Ghi chú nháp đang nhập dở';
    byIdMap['el-vault-passphrase'].value = 'SecretPassphrase123!';
    await byIdMap['el-case-form'].dispatch('input', { target: byIdMap['el-f-full-name'] });
    await byIdMap['el-btn-add-ae'].dispatch('click');
  }

  // Case 1: Manual logout while offline with dirty drawer open
  await seedOpenDirtyDrawer();
  const beforeLogout = win.__ENDOLOG_RUNTIME_AUDIT__.getSanitizedClientState();
  const shellInertDuringDrawer = byIdMap['el-app-shell'].inert;
  logoutOffline = true;
  await byIdMap['el-btn-logout'].dispatch('click');
  logoutOffline = false;
  const afterLogout = {
    state: win.__ENDOLOG_RUNTIME_AUDIT__.getSanitizedClientState(),
    fullName: byIdMap['el-f-full-name'].value,
    mrn: byIdMap['el-f-hospital-mrn'].value,
    note: byIdMap['el-f-clinical-note'].value,
    vaultPass: byIdMap['el-vault-passphrase'].value,
    aeHtml: byIdMap['el-ae-list'].innerHTML,
    initialsPreview: byIdMap['el-preview-initials'].textContent,
    drawerHidden: byIdMap['el-case-drawer-backdrop'].hidden,
    shellInert: byIdMap['el-app-shell'].inert
  };

  // Case 2: 401 during authenticated request while dirty drawer is open
  await seedOpenDirtyDrawer();
  nextPatch401 = true;
  await byIdMap['el-btn-save-settings'].dispatch('click');
  nextPatch401 = false;
  const after401 = {
    state: win.__ENDOLOG_RUNTIME_AUDIT__.getSanitizedClientState(),
    fullName: byIdMap['el-f-full-name'].value,
    mrn: byIdMap['el-f-hospital-mrn'].value,
    drawerHidden: byIdMap['el-case-drawer-backdrop'].hidden,
    shellInert: byIdMap['el-app-shell'].inert
  };

  // Case 3: Idle timeout while dirty drawer is open
  await seedOpenDirtyDrawer();
  win.__ENDOLOG_RUNTIME_AUDIT__.setIdleTimeoutForTest(15);
  await new Promise(r => setTimeout(r, 40));
  const afterIdle = {
    state: win.__ENDOLOG_RUNTIME_AUDIT__.getSanitizedClientState(),
    fullName: byIdMap['el-f-full-name'].value,
    drawerHidden: byIdMap['el-case-drawer-backdrop'].hidden,
    shellInert: byIdMap['el-app-shell'].inert
  };

  process.stdout.write(JSON.stringify({ beforeLogout, shellInertDuringDrawer, afterLogout, after401, afterIdle }));
})();
"""
    proc = subprocess.run(
        ["node", "-e", node_script],
        env={"PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin", "ENDOLOG_APP_JS": str(APP_JS_PATH)},
        capture_output=True,
        text=True,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out["beforeLogout"]["isDrawerOpen"] is True
    assert out["beforeLogout"]["isDirty"] is True
    assert out["beforeLogout"]["aeDraftCount"] == 1
    assert out["shellInertDuringDrawer"] is True

    assert out["afterLogout"]["state"]["hasUser"] is False
    assert out["afterLogout"]["state"]["isDrawerOpen"] is False
    assert out["afterLogout"]["state"]["isDirty"] is False
    assert out["afterLogout"]["state"]["aeDraftCount"] == 0
    assert out["afterLogout"]["fullName"] == ""
    assert out["afterLogout"]["mrn"] == ""
    assert out["afterLogout"]["note"] == ""
    assert out["afterLogout"]["vaultPass"] == ""
    assert out["afterLogout"]["aeHtml"] == ""
    assert out["afterLogout"]["initialsPreview"] == ""
    assert out["afterLogout"]["drawerHidden"] is True
    assert out["afterLogout"]["shellInert"] is False

    assert out["after401"]["state"]["hasUser"] is False
    assert out["after401"]["state"]["isDrawerOpen"] is False
    assert out["after401"]["fullName"] == ""
    assert out["after401"]["mrn"] == ""
    assert out["after401"]["drawerHidden"] is True
    assert out["after401"]["shellInert"] is False

    assert out["afterIdle"]["state"]["hasUser"] is False
    assert out["afterIdle"]["state"]["isDrawerOpen"] is False
    assert out["afterIdle"]["fullName"] == ""
    assert out["afterIdle"]["drawerHidden"] is True
    assert out["afterIdle"]["shellInert"] is False


def test_surgilog_4phase_progression_states_unit() -> None:
    """Verify computeCasePhaseProgression maps all 5 states (done, pending, active, urgent, na) accurately."""
    node_script = r"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync(process.env.ENDOLOG_APP_JS, 'utf8');

class StubEl {
  constructor() { this.value = ''; this.textContent = ''; this.innerHTML = ''; this.hidden = false; }
  addEventListener() {}
  setAttribute() {}
  removeAttribute() {}
  querySelectorAll() { return []; }
}
const stub = new StubEl();
const doc = {
  documentElement: stub,
  body: { appendChild() {} },
  getElementById() { return stub; },
  querySelectorAll() { return []; },
  createElement() { return new StubEl(); },
  addEventListener() {}
};
const win = {
  document: doc,
  location: { search: '?login=1', href: 'http://localhost/' },
  localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  sessionStorage: { getItem() { return null; }, setItem() {}, clear() {} },
  navigator: {},
  URLSearchParams,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  getComputedStyle() { return { getPropertyValue() { return '#F4F7FC'; } }; },
  addEventListener() {},
  async fetch() { return { ok: true, status: 200, async json() { return {}; } }; }
};
win.window = win;
vm.runInNewContext(code, Object.assign(win, {
  fetch: win.fetch,
  getComputedStyle: win.getComputedStyle,
  Date, Math, Number, String, Boolean, Array, Object, Promise, Error, JSON, encodeURIComponent, parseInt
}));

const compute = win.__ENDOLOG_RUNTIME_AUDIT__.computeCasePhaseProgression;

// 1. Negative screening COL closed 30d -> P1=done, P2=done, P3=done, P4=na
const negCol = compute({
  track: 'COL',
  cecal_intubation: 'YES',
  bbps: { evaluable: true },
  followup_30d_status: 'COMPLETED_NO_AE',
  pathology_completion_status: 'NOT_APPLICABLE',
  surveillance: { recommended_interval_label: '10 năm', due_date: '2036-10-12' }
});

// 2. COL incomplete cecal without reason + pending GPB + pending 30d -> P1=done, P2=pending, P3=pending, P4=pending
const incompleteCol = compute({
  track: 'COL',
  cecal_intubation: 'NO',
  cecal_failure_reason: '',
  followup_30d_status: 'PENDING_WINDOW',
  pathology_completion_status: 'PENDING',
  surveillance: { status: 'PENDING_GPB' }
});

// 3. Multi-polyp COL with complete GPB & 3-5y surveillance -> P4=active, P3=pending
const activeSurvCol = compute({
  track: 'COL',
  cecal_intubation: 'YES',
  bbps: { evaluable: true },
  followup_30d_status: 'PENDING_WINDOW',
  pathology_completion_status: 'COMPLETE',
  surveillance: { recommended_interval_label: '3–5 năm', due_date: '2029-10-21' }
});

// 4. ERCP with PEP AE + fulfilled surveillance -> P1=done, P2=done, P3=urgent, P4=done
const ercpAeDone = compute({
  track: 'ERCP',
  ercp_detail: { selective_cannulation: 'SUCCESS' },
  followup_30d_status: 'COMPLETED_WITH_AE',
  adverse_events: [{ event_type: 'PEP', pep_severity: 'MILD', agree_grade: 'II' }],
  pathology_completion_status: 'COMPLETE',
  surveillance: { fulfilled_by_case_id: 'case_followup_01', recommended_interval_label: '3 tháng' }
});

// 5. EGD non-curative ESD -> P4=urgent (Surgical MDT)
const egdUrgent = compute({
  track: 'EGD',
  index_lesion: { anatomical_site: 'Hang vị', resection_method: 'ESD' },
  followup_30d_status: 'LOST_TO_FOLLOWUP',
  pathology_completion_status: 'COMPLETE',
  surveillance: { category: 'SURGICAL_MDT_CONSULT_ALERT' }
});

process.stdout.write(JSON.stringify({ negCol, incompleteCol, activeSurvCol, ercpAeDone, egdUrgent }));
"""
    proc = subprocess.run(
        ["node", "-e", node_script],
        env={"PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin", "ENDOLOG_APP_JS": str(APP_JS_PATH)},
        capture_output=True,
        text=True,
        check=True,
    )
    res = json.loads(proc.stdout)
    assert [p["state"] for p in res["negCol"]["phases"]] == ["done", "done", "done", "na"]
    assert [p["state"] for p in res["incompleteCol"]["phases"]] == ["done", "pending", "pending", "pending"]
    assert [p["state"] for p in res["activeSurvCol"]["phases"]] == ["done", "done", "pending", "active"]
    assert [p["state"] for p in res["ercpAeDone"]["phases"]] == ["done", "done", "urgent", "done"]
    assert [p["state"] for p in res["egdUrgent"]["phases"]] == ["done", "done", "na", "urgent"]
