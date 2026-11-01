#!/usr/bin/env python3
"""Playwright TC-G06 Subpath E2E Verifier & Local Preview Server for EndoLog GitHub Pages (Phương án G1+ · v0.3.2).

Serves `dist_pages/` strictly under `base_path` (e.g. `/endolog/` or `/EndoLog/`, returning 404 for `/`, `/api/*`,
`/css/*`, `/js/*`, etc.) to mirror `https://vukhuongan-dotcom.github.io/EndoLog/` with zero root fallback, and
verifies full interactive virtual-patient clinical + Superadmin workflows in browser RAM alongside Zero-PHI locks.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import mimetypes
import posixpath
import re
import shutil
import socket
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from endolog import __version__  # noqa: E402
from tools.build_gh_pages_demo import SHOWCASE_BANNER_TEXT_VI, build_gh_pages_demo  # noqa: E402

SCREENSHOT_DIR = REPO_ROOT / "docs" / "brand" / "screenshots"
BRAIN_DIR = Path("/Users/khuonganvu/.gemini/antigravity/brain/5c360f0d-e4f4-4860-8e5e-8aa35a4b9a33")


class _ReusableThreadingTCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class SubpathStaticHandler(http.server.BaseHTTPRequestHandler):
    """Serve files from dist_dir ONLY when request path starts with base_path (e.g., '/EndoLog/')."""

    def __init__(self, *args, dist_dir: Path, base_path: str = "/EndoLog/", **kwargs) -> None:
        self._dist_dir = dist_dir.resolve()
        self._base_path = base_path if base_path.endswith("/") else f"{base_path}/"
        self._bare_prefix = self._base_path.rstrip("/")
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(send_body=False)

    def do_GET(self) -> None:  # noqa: N802
        self._serve(send_body=True)

    def _serve(self, *, send_body: bool) -> None:
        parsed = urlparse(self.path)
        req_path = parsed.path or "/"

        if req_path == self._bare_prefix:
            self.send_response(301)
            redirect_target = self._base_path + (f"?{parsed.query}" if parsed.query else "")
            self.send_header("Location", redirect_target)
            self.end_headers()
            return

        if not req_path.startswith(self._base_path) or "/api/" in req_path or req_path.endswith("/api"):
            self._send_404()
            return

        rel_raw = unquote(req_path[len(self._base_path) :])
        rel_norm = posixpath.normpath("/" + rel_raw).lstrip("/")
        if rel_norm in ("", "."):
            rel_norm = "index.html"

        candidate = (self._dist_dir / rel_norm).resolve()
        try:
            candidate.relative_to(self._dist_dir)
        except ValueError:
            self._send_404()
            return

        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            self._send_404()
            return

        ctype, _ = mimetypes.guess_type(str(candidate))
        if candidate.suffix == ".woff2":
            ctype = "font/woff2"
        elif candidate.suffix == ".svg":
            ctype = "image/svg+xml"
        elif candidate.suffix == ".js":
            ctype = "application/javascript; charset=utf-8"
        elif candidate.suffix == ".css":
            ctype = "text/css; charset=utf-8"
        elif candidate.suffix in (".json", ".webmanifest"):
            ctype = "application/json; charset=utf-8"
        elif candidate.suffix == ".html":
            ctype = "text/html; charset=utf-8"

        payload = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if send_body:
            self.wfile.write(payload)

    def _send_404(self) -> None:
        body = b"404 Not Found (Outside static subpath scope)"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_subpath_server(dist_dir: Path, port: int, base_path: str = "/EndoLog/") -> _ReusableThreadingTCPServer:
    handler_cls = functools.partial(SubpathStaticHandler, dist_dir=dist_dir, base_path=base_path)
    httpd = _ReusableThreadingTCPServer(("127.0.0.1", port), handler_cls)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def run_playwright_g06(dist_dir: Path, *, base_path: str = "/EndoLog/", capture_screenshots: bool = False) -> int:
    from playwright.sync_api import sync_playwright

    norm_base = base_path if base_path.endswith("/") else f"{base_path}/"
    if not norm_base.startswith("/"):
        norm_base = "/" + norm_base

    if not (dist_dir / "index.html").is_file():
        build_gh_pages_demo(dist_dir, base_path=norm_base)

    port = _find_free_port()
    httpd = start_subpath_server(dist_dir, port=port, base_path=norm_base)
    origin = f"http://127.0.0.1:{port}"
    app_url = f"{origin}{norm_base}"

    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    http_errors: list[str] = []
    network_api_requests: list[str] = []

    def report_gate(name: str, local_errs: list[str], detail: str) -> None:
        if local_errs:
            failures.extend(f"[{name}] {e}" for e in local_errs)
            print(f"FAIL {name}: {local_errs[0]}")
        else:
            print(f"PASS {name}: {detail}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--accept-downloads"])
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
                locale="vi-VN",
                accept_downloads=True,
            )
            page = context.new_page()

            def on_request(req) -> None:
                parsed = urlparse(req.url)
                if "/api/" in parsed.path or parsed.path.endswith("/api"):
                    network_api_requests.append(f"{req.method} {req.url}")

            def on_response(resp) -> None:
                if resp.status >= 400:
                    http_errors.append(f"{resp.status} {resp.url}")

            def on_console(msg) -> None:
                if msg.type == "error":
                    console_errors.append(msg.text)

            page.on("request", on_request)
            page.on("response", on_response)
            page.on("console", on_console)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # 1. Verify strict subpath isolation (404 outside base_path) & passwordless login screen (?login=1)
            g1_errs: list[str] = []
            for outside_probe in ("/", "/api/health", "/css/tokens.css"):
                try:
                    with urllib.request.urlopen(f"{origin}{outside_probe}", timeout=2.0) as unexpected_resp:
                        g1_errs.append(f"Đường dẫn ngoài scope {outside_probe} không trả 404 (status={unexpected_resp.status})")
                except urllib.error.HTTPError as http_exc:
                    if http_exc.code != 404:
                        g1_errs.append(f"Đường dẫn ngoài scope {outside_probe} trả HTTP {http_exc.code} != 404")

            page.goto(f"{app_url}?login=1", wait_until="networkidle")
            page.locator("#el-login-screen").wait_for(state="visible", timeout=8000)
            page.evaluate("() => document.fonts.ready")

            # Seed sibling GitHub Pages cache to verify sw-demo.js NEVER deletes sibling app caches
            page.evaluate(
                """async () => {
                    const c = await caches.open('idea-agent-sibling-v1');
                    await c.put(new Request(window.location.pathname + '?sibling_probe=1'), new Response('ok'));
                }"""
            )

            login_dom = page.evaluate(
                """() => ({
                    staticDemoFlag: window.ENDOLOG_STATIC_DEMO === true,
                    bannerVisible: !!document.getElementById('el-demo-showcase-banner') &&
                        getComputedStyle(document.getElementById('el-demo-showcase-banner')).display !== 'none',
                    bannerText: (document.getElementById('el-demo-showcase-banner')?.innerText || '').trim(),
                    pwdInputs: document.querySelectorAll('input[type="password"]').length,
                    fileInputs: document.querySelectorAll('input[type="file"]').length,
                    bypassVisible: !document.getElementById('el-btn-dev-bypass')?.hidden,
                    bypassAdminVisible: !document.getElementById('el-btn-dev-bypass-admin')?.hidden
                })"""
            )
            if not login_dom["staticDemoFlag"]:
                g1_errs.append("window.ENDOLOG_STATIC_DEMO chưa bật true")
            if not login_dom["bannerVisible"] or SHOWCASE_BANNER_TEXT_VI not in login_dom["bannerText"]:
                g1_errs.append(f"Thanh cảnh báo đầu trang thiếu hoặc ẩn trên ?login=1: {login_dom}")
            if login_dom["pwdInputs"] != 0 or login_dom["fileInputs"] != 0:
                g1_errs.append(f"Còn sót input nhạy cảm trên ?login=1: {login_dom}")
            if not login_dom["bypassVisible"] or not login_dom["bypassAdminVisible"]:
                g1_errs.append(f"Nút chọn vai trò minh họa không hiển thị trên ?login=1: {login_dom}")

            # Verify MutationObserver strips dynamically injected password/file inputs
            injected_remaining = page.evaluate(
                """async () => {
                    const p = document.createElement('input');
                    p.setAttribute('type', 'password');
                    const f = document.createElement('input');
                    f.setAttribute('type', 'file');
                    document.body.appendChild(p);
                    document.body.appendChild(f);
                    await new Promise(r => setTimeout(r, 30));
                    return document.querySelectorAll('input[type="password"], input[type="file"]').length;
                }"""
            )
            if injected_remaining != 0:
                g1_errs.append(f"MutationObserver không tự gỡ input password/file chèn động (còn {injected_remaining})")

            report_gate(
                "TC_G06_1_SUBPATH_AND_ZERO_SENSITIVE_INPUTS",
                g1_errs,
                f"url={app_url} · passwordInputs=0 · fileInputs=0 · dynamicInjectionPurged=True",
            )

            # 2. Interactive Virtual Patient Picker, Dirty-Guard Safety, 2-Layer DLP, Create & 4-Phase Edit
            g2_errs: list[str] = []
            page.goto(app_url, wait_until="networkidle")
            page.locator("#el-app-shell").wait_for(state="visible", timeout=8000)
            page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=8000)
            page.evaluate("() => document.fonts.ready")

            if page.locator("#el-case-list .el-case-card").count() != 5:
                g2_errs.append(f"Số ca ban đầu khác 5: {page.locator('#el-case-list .el-case-card').count()}")

            for track_code, expected_cnt in [("EGD", 2), ("COL", 2), ("ERCP", 1), ("ALL", 5)]:
                page.locator(f'[data-track-filter="{track_code}"]').click()
                actual_cnt = page.locator("#el-case-list .el-case-card").count()
                if actual_cnt != expected_cnt:
                    g2_errs.append(f"Bộ lọc {track_code} kỳ vọng {expected_cnt} ca, thực tế={actual_cnt}")

            page.locator("#el-case-search").fill("ERCP-2026-0001")
            if page.locator("#el-case-list .el-case-card").count() != 1:
                g2_errs.append("Tìm kiếm mã ca ERCP-2026-0001 không lọc đúng 1 ca")
            page.locator("#el-case-search").fill("")

            # Open New Case Drawer -> verify Virtual Patient Picker & readonly identity fields & clean close (isDirty=false)
            page.locator("#el-btn-new-case").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="visible", timeout=5000)
            picker_info = page.evaluate(
                """() => {
                    const sel = document.getElementById('el-f-demo-patient-picker');
                    const fn = document.getElementById('el-f-full-name');
                    const mrn = document.getElementById('el-f-hospital-mrn');
                    const op = document.getElementById('el-f-operator');
                    return {
                        pickerExists: Boolean(sel),
                        optionCount: sel ? sel.querySelectorAll('option').length : 0,
                        fullNameReadonly: Boolean(fn && fn.readOnly),
                        mrnReadonly: Boolean(mrn && mrn.readOnly),
                        operatorReadonly: Boolean(op && op.readOnly),
                        fullNameVal: fn ? fn.value : '',
                        mrnVal: mrn ? mrn.value : ''
                    };
                }"""
            )
            if (
                not picker_info["pickerExists"]
                or picker_info["optionCount"] != 21
                or not picker_info["fullNameReadonly"]
                or not picker_info["mrnReadonly"]
                or not picker_info["operatorReadonly"]
                or picker_info["fullNameVal"] != "BN. Giả Lập 06"
                or picker_info["mrnVal"] != "SYN-DEMO-2606"
            ):
                g2_errs.append(f"Bộ chọn bệnh nhân ảo hoặc khóa chỉ đọc danh tính/bác sĩ chưa đúng chuẩn: {picker_info}")

            page.locator("#el-drawer-close").click()
            page.wait_for_timeout(80)
            if not page.locator("#el-dirty-modal-backdrop").is_hidden():
                g2_errs.append("Mở ngăn kéo ca mới rồi đóng ngay lại làm bật nhầm hộp thoại thay đổi chưa lưu (isDirty=true)!")
            if not page.locator("#el-case-drawer-backdrop").is_hidden():
                g2_errs.append("Ngăn kéo ca mới không đóng ngay khi chưa chỉnh sửa")

            # Re-open New Case Drawer -> test DLP block (real hospital MRN HS26-88412 & VN phone) -> then create COL-2026-0003
            page.locator("#el-btn-new-case").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="visible", timeout=5000)
            page.locator("#el-f-indication-detail").fill("Chuyển từ hồ sơ HS26-88412 SĐT 0901234567")
            page.locator("#el-btn-save-case").click()
            page.locator("#el-drawer-alert").wait_for(state="visible", timeout=5000)
            dlp_alert_txt = page.locator("#el-drawer-alert").inner_text()
            if "DLP" not in dlp_alert_txt and "định danh" not in dlp_alert_txt.lower():
                g2_errs.append(f"Bộ lọc DLP không hiển thị cảnh báo chặn PHI rõ ràng: {dlp_alert_txt!r}")
            if page.locator("#el-case-list .el-case-card").count() != 5:
                g2_errs.append("Ca chứa PHI trong ô ghi chú vẫn được lưu vào RAM!")

            page.locator("#el-f-indication-detail").fill("Tầm soát đại tràng giả lập trên Sandbox RAM")
            page.locator("#el-btn-preset-normal-col").click()
            page.locator("#el-btn-save-case").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="hidden", timeout=5000)

            if page.locator("#el-case-list .el-case-card").count() != 6:
                g2_errs.append(f"Tạo ca ảo mới không tăng danh sách lên 6 ca: {page.locator('#el-case-list .el-case-card').count()}")
            if "COL-2026-0003" not in page.locator("#el-case-list").inner_text():
                g2_errs.append("Danh sách ca trên RAM chưa hiển thị mã ca mới COL-2026-0003")
            if "6 ca trên RAM" not in page.locator("#el-btn-demo-reset-store").inner_text():
                g2_errs.append(f"Nhãn nút đặt lại trên thanh đầu trang chưa cập nhật '6 ca trên RAM': {page.locator('#el-btn-demo-reset-store').inner_text()!r}")

            # Open 4-Phase Detail Modal on COL-2026-0003 -> jump to Phase 3 -> close 30-day window -> verify version v2
            page.locator('[data-case-detail]').first.click()
            page.locator("#el-detail-modal-backdrop").wait_for(state="visible", timeout=5000)
            detail_txt = page.locator("#el-detail-modal").inner_text()
            for ph_lbl in ("Pha 1", "Pha 2", "Pha 3", "Pha 4"):
                if ph_lbl not in detail_txt:
                    g2_errs.append(f"Hộp thoại chi tiết 4 pha thiếu '{ph_lbl}'")
            page.locator('[data-detail-jump-phase="p3"]').first.click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="visible", timeout=5000)
            page.locator("#el-f-followup-30d").select_option("COMPLETED_NO_AE")
            page.locator("#el-btn-save-case").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="hidden", timeout=5000)

            report_gate(
                "TC_G06_2_VIRTUAL_PICKER_CREATE_EDIT_AND_DLP",
                g2_errs,
                "21 hồ sơ ảo · readonly họ tên/mã HS · đóng sạch isDirty=false · chặn DLP 422 · tạo COL-2026-0003 & cập nhật Pha 3 trên RAM",
            )
            # 3. Surveillance Linked Follow-Up, 409 Duplicate Outpatient, Superadmin Merge/Sim-Restore, CSV/JSON Exports & Zero-PHI Locks
            g3_errs: list[str] = []

            # 3a. Surveillance linked follow-up creation + synchronous #el-btn-clear-surv-link unlock verification
            page.locator('.el-tab-btn[data-nav-target="surveillance"]').click()
            page.locator("#el-view-surveillance").wait_for(state="visible", timeout=5000)
            linked_btn = page.locator("#el-surveillance-list button.action-btn-link-surv[data-create-linked]").first
            linked_btn.click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="visible", timeout=5000)
            linked_state = page.evaluate(
                """() => ({
                    bannerVisible: !document.getElementById('el-linked-surv-banner')?.hidden,
                    pickerDisabled: Boolean(document.getElementById('el-f-demo-patient-picker')?.disabled),
                    syncedMrn: document.getElementById('el-f-hospital-mrn')?.value || ''
                })"""
            )
            if (
                not linked_state["bannerVisible"]
                or not linked_state["pickerDisabled"]
                or not linked_state["syncedMrn"].startswith("SYN-")
            ):
                g3_errs.append(f"Tạo ca soi lại liên kết chưa đồng bộ mã HS giả lập của ca gốc: {linked_state}")

            # Verify synchronous unlock + sex sync right inside the same JS turn when #el-btn-clear-surv-link is clicked (F4 + R2-F2)
            clear_surv_sync = page.evaluate(
                """() => {
                    const btn = document.getElementById('el-btn-clear-surv-link');
                    if (btn) btn.click();
                    const sel = document.getElementById('el-f-demo-patient-picker');
                    const banner = document.getElementById('el-linked-surv-banner');
                    const activeSex = document.querySelector('[data-form-sex][aria-pressed="true"]')?.getAttribute('data-form-sex') || '';
                    return {
                        bannerHidden: Boolean(banner && banner.hidden),
                        pickerDisabledImmediately: Boolean(sel && sel.disabled),
                        freshMrn: document.getElementById('el-f-hospital-mrn')?.value || '',
                        activeSex
                    };
                }"""
            )
            if (
                not clear_surv_sync["bannerHidden"]
                or clear_surv_sync["pickerDisabledImmediately"]
                or not clear_surv_sync["freshMrn"].startswith("SYN-DEMO-")
                or clear_surv_sync["activeSex"] != "M"
            ):
                g3_errs.append(f"Nút #el-btn-clear-surv-link không mở khóa đồng bộ hoặc lệch giới tính hồ sơ ảo: {clear_surv_sync}")
            page.locator("#el-drawer-close").click()
            page.locator("#el-dirty-modal-backdrop").wait_for(state="visible", timeout=5000)
            page.locator("#el-btn-dirty-discard").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="hidden", timeout=5000)

            # Re-open linked follow-up and save to close the surveillance loop
            linked_btn.click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="visible", timeout=5000)
            page.locator("#el-btn-save-case").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="hidden", timeout=5000)
            if "Đã soi lại" not in page.locator("#el-surveillance-list").inner_text():
                g3_errs.append("Đóng vòng hẹn soi lại không cập nhật nhãn 'Đã soi lại' trên màn Hẹn soi lại")

            # 3b. Outpatient no-MRN duplicate detection (409) -> verify inpatient fallback sex sync (R2-F2) -> confirm new patient
            page.locator('.el-tab-btn[data-nav-target="cases"]').click()
            page.locator("#el-view-cases").wait_for(state="visible", timeout=5000)
            page.locator("#el-btn-new-case").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="visible", timeout=5000)
            page.locator("#el-f-demo-patient-picker").select_option("dup_out_2601")
            page.locator('[data-form-care="inpatient"]').click()
            page.wait_for_timeout(40)
            inpatient_fb = page.evaluate(
                """() => ({
                    pickerVal: document.getElementById('el-f-demo-patient-picker')?.value || '',
                    activeSex: document.querySelector('[data-form-sex][aria-pressed="true"]')?.getAttribute('data-form-sex') || ''
                })"""
            )
            if inpatient_fb["pickerVal"] != "syn_2610" or inpatient_fb["activeSex"] != "M":
                g3_errs.append(f"Chuyển Nội trú từ dup_out_2601 không đồng bộ giới tính Nam của syn_2610: {inpatient_fb}")
            page.locator("#el-f-demo-patient-picker").select_option("dup_out_2601")
            page.locator("#el-btn-preset-normal-col").click()
            page.locator("#el-btn-save-case").click()
            page.locator("#el-dup-modal-backdrop").wait_for(state="visible", timeout=5000)
            page.locator("#el-btn-dup-new-patient").click()
            page.locator("#el-case-drawer-backdrop").wait_for(state="hidden", timeout=5000)
            if page.locator("#el-case-list .el-case-card").count() != 8:
                g3_errs.append(f"Xác nhận ca ngoại trú trùng tên khác người không tăng danh sách lên 8 ca: {page.locator('#el-case-list .el-case-card').count()}")

            # 3c. Verify Profile B (CSV) & Profile C (JSON) research downloads work directly in browser RAM
            with page.expect_download(timeout=5000) as dl_csv_info:
                page.locator("#el-btn-export-csv").click()
            dl_csv = dl_csv_info.value
            csv_path = dl_csv.path()
            csv_txt = Path(csv_path).read_text(encoding="utf-8-sig") if csv_path else ""
            if (
                dl_csv.suggested_filename != "endolog_profile_b_longitudinal.csv"
                or "research_subject_id,research_episode_id,case_code" not in csv_txt
                or "profile_b_lineage_seq" not in csv_txt
            ):
                g3_errs.append(f"Tải Hồ sơ B CSV trên RAM chưa chuẩn: filename={dl_csv.suggested_filename}")

            with page.expect_download(timeout=5000) as dl_json_info:
                page.locator("#el-btn-export-profile-c").click()
            dl_json = dl_json_info.value
            json_path = dl_json.path()
            prof_c_obj = json.loads(Path(json_path).read_text(encoding="utf-8")) if json_path else {}
            if (
                not dl_json.suggested_filename.endswith(".json")
                or prof_c_obj.get("contract") != "EndoLog-Export-Profile-C-v1.0"
                or prof_c_obj.get("suppress_small_cells_k_lt_5") is not True
            ):
                g3_errs.append(f"Tải Hồ sơ C JSON trên RAM chưa chuẩn: filename={dl_json.suggested_filename}")

            # 3d. Quality KPI / CUSUM + genuine RBAC before switching to Superadmin
            page.locator('.el-tab-btn[data-nav-target="quality"]').click()
            page.locator("#el-view-quality").wait_for(state="visible", timeout=5000)
            page.locator('[data-age-toggle="50"]').click()
            page.wait_for_timeout(60)
            page.locator('[data-age-toggle="45"]').click()
            page.wait_for_timeout(60)
            page.locator('[data-cusum-metric="ERCP_NATIVE"]').click()
            page.wait_for_timeout(60)
            if "Thông nhú" not in page.locator("#el-view-quality").inner_text():
                g3_errs.append("Chuyển chỉ số CUSUM sang ERCP_NATIVE không cập nhật giao diện")
            page.locator('[data-cusum-metric="CIR"]').click()
            page.wait_for_timeout(60)

            endo_admin_vis = page.evaluate(
                """() => ({
                    noticeVisible: !document.getElementById('el-superadmin-readonly-notice')?.hidden,
                    gridHidden: Boolean(document.getElementById('el-superadmin-grid')?.hidden)
                })"""
            )
            if not endo_admin_vis["noticeVisible"] or not endo_admin_vis["gridHidden"]:
                g3_errs.append(f"Vai trò BS nội soi lại nhìn thấy lưới thực thi Superadmin: {endo_admin_vis}")

            # 3e. Switch to Superadmin -> verify 4 cards, settings update, patient merge & simulated atomic restore
            page.locator("#el-btn-demo-switch-role").click()
            page.wait_for_timeout(150)
            page.locator('.el-tab-btn[data-nav-target="quality"]').click()
            page.locator("#el-view-quality").wait_for(state="visible", timeout=5000)

            super_vis = page.evaluate(
                """() => ({
                    noticeHidden: Boolean(document.getElementById('el-superadmin-readonly-notice')?.hidden),
                    gridVisible: !document.getElementById('el-superadmin-grid')?.hidden,
                    cardCount: document.querySelectorAll('#el-superadmin-grid .el-admin-card').length,
                    userItemCount: document.querySelectorAll('#el-admin-user-list .el-admin-item').length
                })"""
            )
            if (
                not super_vis["noticeHidden"]
                or not super_vis["gridVisible"]
                or super_vis["cardCount"] != 4
                or super_vis["userItemCount"] != 2
            ):
                g3_errs.append(f"Chuyển sang Superadmin không mở đủ 4 thẻ quản trị / 2 tài khoản: {super_vis}")

            page.locator("#el-setting-guideline").select_option("ESGE_2020")
            page.locator("#el-btn-save-settings").click()
            page.wait_for_timeout(100)
            if not page.locator("#el-demo-lock-modal-backdrop").is_hidden():
                g3_errs.append("Lưu cấu hình chuyên môn trên Superadmin lại bị chặn bởi hộp thoại khóa!")
            page.locator("#el-setting-guideline").select_option("USMSTF_2020")
            page.locator("#el-btn-save-settings").click()
            page.wait_for_timeout(80)

            # Merge the newly created no-MRN Lê Thị Minh Thảo into canonical SYN-OUT-2601 Lê Thị Minh Thảo
            merge_pair = page.evaluate(
                """() => {
                    const srcSel = document.getElementById('el-admin-merge-source');
                    const tgtSel = document.getElementById('el-admin-merge-target');
                    if (!srcSel || !tgtSel) return null;
                    const opts = Array.from(srcSel.options).map(o => ({ val: o.value, txt: o.textContent || '' }));
                    const noMrn = opts.find(o => o.txt.includes('Lê Thị Minh Thảo') && o.txt.includes('Ngoại trú chưa mã HS'));
                    const withMrn = opts.find(o => o.txt.includes('Lê Thị Minh Thảo') && o.txt.includes('***2601'));
                    if (!noMrn || !withMrn) return { opts };
                    srcSel.value = noMrn.val;
                    tgtSel.value = withMrn.val;
                    return { ok: true, src: noMrn.val, tgt: withMrn.val };
                }"""
            )
            if not merge_pair or not merge_pair.get("ok"):
                g3_errs.append(f"Không tìm thấy cặp hồ sơ Lê Thị Minh Thảo để thử gộp trên Superadmin: {merge_pair}")
            else:
                page.locator("#el-btn-run-patient-merge").scroll_into_view_if_needed()
                page.locator("#el-btn-run-patient-merge").click()
                page.locator("#el-admin-merge-feedback").wait_for(state="visible", timeout=5000)
                if "el-admin-feedback--ok" not in (page.locator("#el-admin-merge-feedback").get_attribute("class") or ""):
                    g3_errs.append(f"Gộp hồ sơ người bệnh trùng thất bại: {page.locator('#el-admin-merge-feedback').inner_text()}")

            # Simulated atomic restore -> store_epoch becomes #2 + verified SHA-256 pre-restore bridge + preserves active toggles (F6)
            page.locator('[data-age-toggle="50"]').click()
            page.locator('[data-cusum-metric="ERCP_NATIVE"]').click()
            page.wait_for_timeout(60)
            page.locator("#el-btn-demo-sim-restore").scroll_into_view_if_needed()
            page.locator("#el-btn-demo-sim-restore").click()
            page.wait_for_timeout(200)
            post_restore_toggles = page.evaluate(
                """() => ({
                    qualityVisible: !document.getElementById('el-view-quality')?.hidden,
                    age50Pressed: document.querySelector('[data-age-toggle="50"]')?.getAttribute('aria-pressed') === 'true',
                    cusumErcpPressed: document.querySelector('[data-cusum-metric="ERCP_NATIVE"]')?.getAttribute('aria-pressed') === 'true'
                })"""
            )
            if not all(post_restore_toggles.values()):
                g3_errs.append(f"Mô phỏng khôi phục nguyên tử không giữ nguyên tab/bộ lọc đang chọn: {post_restore_toggles}")
            page.locator('[data-age-toggle="45"]').click()
            page.locator('[data-cusum-metric="CIR"]').click()
            page.wait_for_timeout(60)
            epoch_txt = page.locator("#el-superadmin-epoch-badge").inner_text()
            lineage_txt = page.locator("#el-admin-lineage-list").inner_text()
            if "#2" not in epoch_txt or "SHA-256" not in lineage_txt:
                g3_errs.append(f"Mô phỏng khôi phục nguyên tử không nâng kỷ nguyên #2 / cầu nối SHA-256: epoch={epoch_txt!r}, lineage={lineage_txt!r}")

            # Also verify preserve_current_users = false triggers relogin screen with explanatory banner (F6)
            page.locator("#el-sw-preserve-users").scroll_into_view_if_needed()
            page.locator("#el-sw-preserve-users").click()
            page.locator("#el-btn-demo-sim-restore").click()
            page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
            page.wait_for_timeout(120)
            relogin_banner_txt = page.locator("#el-login-error").inner_text() if not page.locator("#el-login-error").is_hidden() else ""
            if "khôi phục kho sao lưu nguyên tử" not in relogin_banner_txt.lower():
                g3_errs.append(f"Khôi phục kèm thay bảng tài khoản không hiển thị thông báo đăng nhập lại: {relogin_banner_txt!r}")
            page.locator("#el-btn-dev-bypass-admin").click()
            page.locator("#el-app-shell").wait_for(state="visible", timeout=5000)
            page.locator('.el-tab-btn[data-nav-target="quality"]').click()
            page.locator("#el-view-quality").wait_for(state="visible", timeout=5000)

            raw_enums = re.findall(r"\b[A-Z0-9]{2,}(?:_[A-Z0-9]+)+\b", page.locator("#el-view-quality").inner_text())
            if raw_enums:
                g3_errs.append(f"Xuất hiện mã enum kỹ thuật thô trên màn Chỉ số chất lượng / Superadmin: {raw_enums}")

            # 3f. Verify Zero-PHI locks on password / external .endolog.enc / binary XLSX
            page.locator('.el-tab-btn[data-nav-target="cases"]').click()
            page.locator("#el-view-cases").wait_for(state="visible", timeout=5000)
            for locked_case_sel in ("#el-btn-export-xlsx", "#el-btn-open-vault-backup", "#el-btn-change-password"):
                page.locator(locked_case_sel).scroll_into_view_if_needed()
                page.locator(locked_case_sel).click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
                page.locator("#el-btn-demo-lock-ok").click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="hidden", timeout=5000)

            page.locator('.el-tab-btn[data-nav-target="quality"]').click()
            page.locator("#el-view-quality").wait_for(state="visible", timeout=5000)
            for locked_admin_sel in ("#el-btn-pick-restore-file", "#el-btn-run-restore", "#el-btn-run-reset-password"):
                page.locator(locked_admin_sel).scroll_into_view_if_needed()
                page.locator(locked_admin_sel).click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
                page.locator("#el-btn-demo-lock-close").click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="hidden", timeout=5000)

            # 3g. GC-04 check + automatic RAM reset on logout
            page.locator("#el-btn-run-reset-password").scroll_into_view_if_needed()
            page.locator("#el-btn-run-reset-password").click()
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
            page.evaluate("() => document.getElementById('el-btn-logout').click()")
            page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
            if not page.locator("#el-demo-lock-modal-backdrop").is_hidden():
                g3_errs.append("GC-04: Hộp thoại khóa #el-demo-lock-modal-backdrop không tự đóng khi đăng xuất!")

            page.evaluate(
                "() => document.getElementById('el-login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))"
            )
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
            if not page.evaluate("() => Boolean(document.getElementById('el-login-screen')?.inert)"):
                g3_errs.append("GC-04: #el-login-screen chưa gắn inert khi mở hộp thoại khóa từ màn đăng nhập!")
            page.locator("#el-btn-demo-lock-ok").click()
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="hidden", timeout=5000)
            if page.evaluate("() => Boolean(document.getElementById('el-login-screen')?.inert)"):
                g3_errs.append("GC-04: #el-login-screen vẫn còn inert sau khi đóng hộp thoại khóa!")

            # Re-enter as endoscopist and verify logout wiped transient RAM back to 5 OD-05 cases & epoch #1, plus test Reset button
            page.locator("#el-btn-dev-bypass").click()
            page.locator("#el-app-shell").wait_for(state="visible", timeout=5000)
            post_logout_stats = page.evaluate("() => window.__ENDOLOG_DEMO_AUDIT__.getStats()")
            if post_logout_stats.get("activeCaseCount") != 5 or post_logout_stats.get("storeEpoch") != 1:
                g3_errs.append(f"Đăng xuất không tự động xóa sạch dữ liệu tạm trên RAM về 5 ca gốc OD-05: {post_logout_stats}")

            page.locator("#el-btn-demo-reset-store").click()
            page.wait_for_timeout(100)
            if page.locator("#el-case-list .el-case-card").count() != 5:
                g3_errs.append("Nút Đặt lại 5 ca gốc trên thanh đầu trang không khôi phục đúng 5 ca OD-05")

            report_gate(
                "TC_G06_3_SURVEILLANCE_SUPERADMIN_EXPORTS_AND_LOCKS",
                g3_errs,
                "Đóng vòng hẹn soi lại · 409 trùng ngoại trú · gộp BN · mô phỏng khôi phục epoch #2 · xuất CSV/JSON · khóa mật khẩu/tệp ngoài · tự xóa RAM khi đăng xuất",
            )

            # 4. Verify Service Worker scope, sibling cache preservation & Zero-PHI storage hygiene
            g4_errs: list[str] = []
            sw_and_storage = page.evaluate(
                """async () => {
                    const lsKeys = Object.keys(window.localStorage || {});
                    const ssKeys = Object.keys(window.sessionStorage || {});
                    let idbNames = [];
                    if (window.indexedDB && typeof window.indexedDB.databases === 'function') {
                        const dbs = await window.indexedDB.databases();
                        idbNames = (dbs || []).map(d => d.name).filter(Boolean);
                    }
                    if (!('serviceWorker' in navigator)) {
                        return { supported: false, lsKeys, ssKeys, idbNames };
                    }
                    const reg = await navigator.serviceWorker.ready;
                    await new Promise(r => setTimeout(r, 150));
                    const cacheKeys = await caches.keys();
                    const demoKey = cacheKeys.find(k => k.startsWith('endolog-ghpages-demo-')) || '';
                    let cachedPaths = [];
                    if (demoKey) {
                        const c = await caches.open(demoKey);
                        const reqs = await c.keys();
                        cachedPaths = reqs.map(r => new URL(r.url).pathname);
                    }
                    return {
                        supported: true,
                        scope: reg.scope,
                        scriptURL: reg.active ? reg.active.scriptURL : '',
                        cacheKeys,
                        demoKey,
                        siblingPreserved: cacheKeys.includes('idea-agent-sibling-v1'),
                        cachedPaths,
                        lsKeys,
                        ssKeys,
                        idbNames
                    };
                }"""
            )
            expected_scope = f"{origin}{norm_base}"
            if sw_and_storage.get("supported"):
                if sw_and_storage.get("scope") != expected_scope:
                    g4_errs.append(f"Service Worker scope sai: {sw_and_storage.get('scope')!r} != {expected_scope!r}")
                if not str(sw_and_storage.get("scriptURL", "")).endswith(f"{norm_base}sw-demo.js"):
                    g4_errs.append(f"Service Worker scriptURL sai: {sw_and_storage.get('scriptURL')!r}")
                if sw_and_storage.get("demoKey") != f"endolog-ghpages-demo-v{__version__}":
                    g4_errs.append(f"Tên khóa cache SW không khớp phiên bản: {sw_and_storage.get('demoKey')!r}")
                if not sw_and_storage.get("siblingPreserved"):
                    g4_errs.append("sw-demo.js đã xóa nhầm cache của ứng dụng anh em 'idea-agent-sibling-v1'!")
                outside_paths = [cp for cp in sw_and_storage.get("cachedPaths", []) if not cp.startswith(norm_base)]
                if outside_paths:
                    g4_errs.append(f"Cache chứa tài nguyên nằm ngoài {norm_base}: {outside_paths}")

            illegal_ls = [k for k in sw_and_storage.get("lsKeys", []) if k != "endolog_theme"]
            illegal_ss = [k for k in sw_and_storage.get("ssKeys", []) if k not in ("endolog_active_view", "endolog_active_tab")]
            if illegal_ls or illegal_ss or sw_and_storage.get("idbNames"):
                g4_errs.append(
                    f"Vi phạm Zero-PHI bộ nhớ trình duyệt: localStorage={illegal_ls}, sessionStorage={illegal_ss}, indexedDB={sw_and_storage.get('idbNames')}"
                )

            report_gate(
                "TC_G06_4_SW_SCOPE_STORAGE_ZERO_PHI_AND_CACHE_SAFETY",
                g4_errs,
                f"scope={sw_and_storage.get('scope')} · cache={sw_and_storage.get('demoKey')} · clinicalStorage=0 · siblingCachePreserved=True",
            )

            # 5. Verify responsive layout (320, 375, 390, 768, 1440 x Light/Dark x endoscopist & superadmin),
            #    0 horizontal overflow, 0 button text clipping, firstCaseCardTopY <= 700px & >= 44x44px touch targets
            g5_errs: list[str] = []
            mobile_first_case_y = 0.0
            for role_key in ("endoscopist", "superadmin"):
                target_persona = "vukhuongan" if role_key == "superadmin" else "nguyenbinhan"
                cur_persona = page.evaluate("() => window.__ENDOLOG_DEMO_AUDIT__.getStats().activePersonaKey")
                if cur_persona != target_persona:
                    page.locator("#el-btn-demo-switch-role").click()
                    page.wait_for_timeout(120)

                for theme_mode in ("light", "dark"):
                    cur_theme = page.evaluate(
                        "() => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'"
                    )
                    if cur_theme != theme_mode:
                        page.locator("#el-theme-toggle").click()
                        page.wait_for_timeout(80)

                    for vw, vh in [(320, 568), (375, 812), (390, 844), (768, 1024), (1440, 900)]:
                        page.set_viewport_size({"width": vw, "height": vh})
                        page.wait_for_timeout(80)
                        nav_sel = ".el-bottom-btn" if vw < 768 else ".el-tab-btn"
                        page.locator(f'{nav_sel}[data-nav-target="cases"]').click()
                        page.locator("#el-view-cases").wait_for(state="visible", timeout=5000)
                        page.evaluate("() => window.scrollTo(0, 0)")
                        page.wait_for_timeout(80)

                        metrics = page.evaluate(
                            """() => {
                                const fc = document.querySelector('#el-case-list .el-case-card');
                                const r = fc ? fc.getBoundingClientRect() : null;
                                const visibleEls = Array.from(document.querySelectorAll('button, input, select'))
                                    .filter(el => {
                                        if (el.hidden || el.disabled) return false;
                                        const cs = getComputedStyle(el);
                                        if (cs.display === 'none' || cs.visibility === 'hidden') return false;
                                        const rect = el.getBoundingClientRect();
                                        return rect.width > 0 && rect.height > 0;
                                    });
                                const controls = visibleEls.map(el => {
                                    const rect = el.getBoundingClientRect();
                                    return {
                                        id: el.id || el.className,
                                        w: Math.round(rect.width * 10) / 10,
                                        h: Math.round(rect.height * 10) / 10
                                    };
                                });
                                const clippedBtns = visibleEls
                                    .filter(el => el.tagName === 'BUTTON' && el.scrollWidth > el.clientWidth + 1)
                                    .map(el => ({
                                        id: el.id || el.className,
                                        sw: el.scrollWidth,
                                        cw: el.clientWidth
                                    }));
                                const undersized = controls.filter(b => b.w < 43.5 || b.h < 43.5);
                                return {
                                    scrollWidth: document.documentElement.scrollWidth,
                                    innerWidth: window.innerWidth,
                                    firstCaseY: r ? Math.round((r.top + window.scrollY) * 10) / 10 : 9999,
                                    undersized,
                                    clippedBtns
                                };
                            }"""
                        )
                        if metrics["scrollWidth"] > metrics["innerWidth"]:
                            g5_errs.append(f"Tràn ngang tại {vw}x{vh} [{theme_mode}/{role_key}]: {metrics}")
                        if metrics["clippedBtns"]:
                            g5_errs.append(f"Cắt cụt chữ nút bấm tại {vw}x{vh} [{theme_mode}/{role_key}]: {metrics['clippedBtns'][:3]}")
                        if metrics["undersized"]:
                            g5_errs.append(f"Vùng chạm < 44x44px tại {vw}x{vh} [{theme_mode}/{role_key}]: {metrics['undersized'][:3]}")
                        if vw == 390 and theme_mode == "light" and role_key == "endoscopist":
                            mobile_first_case_y = float(metrics["firstCaseY"])
                            if mobile_first_case_y > 700.0:
                                g5_errs.append(f"firstCaseCardTopY tại 390x844 = {mobile_first_case_y}px > 700px")

                        if capture_screenshots and vw == 1440 and theme_mode == "light" and role_key == "endoscopist":
                            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                            shot_path = SCREENSHOT_DIR / "gh_pages_demo_1440_light.png"
                            page.screenshot(path=str(shot_path), full_page=False)
                            if BRAIN_DIR.is_dir():
                                shutil.copy2(shot_path, BRAIN_DIR / "gh_pages_demo_1440_light.png")

            report_gate(
                "TC_G06_5_RESPONSIVE_FIRST_CASE_Y_AND_TOUCH",
                g5_errs,
                f"320..1440px (2 vai trò x Sáng/Tối) · mobile390_firstCaseCardTopY={mobile_first_case_y}px (<= 700px) · overflow=0 · clipped=0 · touch>=44x44px",
            )

            # 6. Network Zero-API & Runtime Cleanliness Gate
            g6_errs: list[str] = []
            if network_api_requests:
                g6_errs.append(f"Phát sinh request mạng tới /api/* từ bản tĩnh: {network_api_requests[:5]}")
            if http_errors:
                g6_errs.append(f"Phát sinh lỗi HTTP >= 400 (404/500): {http_errors[:5]}")
            if console_errors:
                g6_errs.append(f"Phát sinh console.error: {console_errors[:5]}")
            if page_errors:
                g6_errs.append(f"Phát sinh pageerror: {page_errors[:5]}")

            demo_stats = page.evaluate("() => window.__ENDOLOG_DEMO_AUDIT__.getStats()")
            report_gate(
                "TC_G06_6_ZERO_NETWORK_API_AND_CLEAN_RUNTIME",
                g6_errs,
                f"networkApiCalls=0 · inMemoryIntercepted={demo_stats.get('interceptedApiCalls')} · http4xx5xx=0 · consoleError=0",
            )

            context.close()
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    if failures:
        print("\nTC-G06 PLAYWRIGHT VERIFICATION FAILED:", file=sys.stderr)
        for item in failures:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print("\nALL TC-G06 GITHUB PAGES INTERACTIVE SANDBOX PLAYWRIGHT GATES PASSED (0 FAILURES).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or serve EndoLog Gate C GitHub Pages Interactive Sandbox.")
    parser.add_argument("--dist-dir", default=str(REPO_ROOT / "dist_pages"), help="Path to built dist_pages/ directory.")
    parser.add_argument("--base-path", default="/EndoLog/", help="Subpath prefix (default: /EndoLog/).")
    parser.add_argument("--capture-screenshots", action="store_true", help="Save 1440px Light showcase screenshot.")
    parser.add_argument("--serve-only", action="store_true", help="Run local static subpath server continuously.")
    parser.add_argument("--port", type=int, default=8766, help="Port when running with --serve-only (default: 8766).")
    args = parser.parse_args()

    dist_path = Path(args.dist_dir).resolve()
    if args.serve_only:
        if not (dist_path / "index.html").is_file():
            build_gh_pages_demo(dist_path, base_path=args.base_path)
        httpd = start_subpath_server(dist_path, port=args.port, base_path=args.base_path)
        print(f"SERVING_GH_PAGES_DEMO at http://127.0.0.1:{args.port}{args.base_path}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            httpd.shutdown()
            httpd.server_close()
            return 0

    return run_playwright_g06(
        dist_path,
        base_path=args.base_path,
        capture_screenshots=args.capture_screenshots,
    )


if __name__ == "__main__":
    raise SystemExit(main())
