#!/usr/bin/env python3
"""Playwright TC-G06 Subpath E2E Verifier & Local Preview Server for EndoLog GitHub Pages (/endolog/).

Serves `dist_pages/` strictly under `/endolog/` (returning 404 for `/`, `/api/*`, `/css/*`, `/js/*`, etc.)
to mirror `https://vukhuongan-dotcom.github.io/endolog/` with zero root fallback.
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
    """Serve files from dist_dir ONLY when request path starts with base_path (e.g., '/endolog/')."""

    def __init__(self, *args, dist_dir: Path, base_path: str = "/endolog/", **kwargs) -> None:
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
        body = b"404 Not Found (Outside /endolog/ static scope)"
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


def start_subpath_server(dist_dir: Path, port: int, base_path: str = "/endolog/") -> _ReusableThreadingTCPServer:
    handler_cls = functools.partial(SubpathStaticHandler, dist_dir=dist_dir, base_path=base_path)
    httpd = _ReusableThreadingTCPServer(("127.0.0.1", port), handler_cls)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def run_playwright_g06(dist_dir: Path, *, base_path: str = "/endolog/", capture_screenshots: bool = False) -> int:
    from playwright.sync_api import sync_playwright

    if not (dist_dir / "index.html").is_file():
        build_gh_pages_demo(dist_dir, base_path=base_path)

    port = _find_free_port()
    httpd = start_subpath_server(dist_dir, port=port, base_path=base_path)
    origin = f"http://127.0.0.1:{port}"
    app_url = f"{origin}{base_path}"

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
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
                locale="vi-VN",
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

            # 1. Verify strict subpath isolation (404 outside /endolog/) & passwordless login showcase (?login=1)
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

            # 2. Auto-enter showcase at /endolog/ and verify 5 OD-05 cases, filters, search, Light/Dark, KPI 45/50 & CUSUM
            g2_errs: list[str] = []
            page.goto(app_url, wait_until="networkidle")
            page.locator("#el-app-shell").wait_for(state="visible", timeout=8000)
            page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=8000)
            page.evaluate("() => document.fonts.ready")

            if page.locator("#el-case-list .el-case-card").count() != 5:
                g2_errs.append(f"Số ca hiển thị khác 5: {page.locator('#el-case-list .el-case-card').count()}")

            for track_code, expected_cnt in [("EGD", 2), ("COL", 2), ("ERCP", 1), ("ALL", 5)]:
                page.locator(f'[data-track-filter="{track_code}"]').click()
                actual_cnt = page.locator("#el-case-list .el-case-card").count()
                if actual_cnt != expected_cnt:
                    g2_errs.append(f"Bộ lọc {track_code} kỳ vọng {expected_cnt} ca, thực tế={actual_cnt}")

            page.locator("#el-case-search").fill("ERCP-2026-0001")
            if page.locator("#el-case-list .el-case-card").count() != 1:
                g2_errs.append("Tìm kiếm mã ca ERCP-2026-0001 không lọc đúng 1 ca")
            page.locator("#el-case-search").fill("")
            if page.locator("#el-case-list .el-case-card").count() != 5:
                g2_errs.append("Xóa ô tìm kiếm không khôi phục đủ 5 ca OD-05")

            # Switch across Surveillance and Quality, toggle ADR 45/50 & CUSUM CIR/ERCP_NATIVE
            page.locator('.el-tab-btn[data-nav-target="surveillance"]').click()
            page.locator("#el-view-surveillance").wait_for(state="visible", timeout=5000)
            if page.locator("#el-surveillance-list .el-case-card").count() != 5:
                g2_errs.append("Màn Hẹn soi lại không hiển thị đủ 5 ca chuẩn OD-05")

            page.locator('.el-tab-btn[data-nav-target="quality"]').click()
            page.locator("#el-view-quality").wait_for(state="visible", timeout=5000)
            page.locator('[data-age-toggle="50"]').click()
            page.wait_for_timeout(80)
            page.locator('[data-age-toggle="45"]').click()
            page.wait_for_timeout(80)
            page.locator('[data-cusum-metric="ERCP_NATIVE"]').click()
            page.wait_for_timeout(80)
            if "Thông nhú" not in page.locator("#el-view-quality").inner_text():
                g2_errs.append("Chuyển chỉ số CUSUM sang ERCP_NATIVE không cập nhật giao diện từ gói tính sẵn")
            page.locator('[data-cusum-metric="CIR"]').click()
            page.wait_for_timeout(80)

            all_views_text = "\n".join(
                [
                    page.locator("#el-view-quality").inner_text(),
                ]
            )
            raw_enums = re.findall(r"\b[A-Z0-9]{2,}(?:_[A-Z0-9]+)+\b", all_views_text)
            if raw_enums:
                g2_errs.append(f"Xuất hiện mã enum kỹ thuật thô trên màn Chỉ số chất lượng: {raw_enums}")

            # Open 4-Phase Detail Modal on first case & verify read-only view + locked phase edit jump
            page.locator('.el-tab-btn[data-nav-target="cases"]').click()
            page.locator("#el-view-cases").wait_for(state="visible", timeout=5000)
            page.locator("[data-case-detail]").first.click()
            page.locator("#el-detail-modal-backdrop").wait_for(state="visible", timeout=5000)
            detail_txt = page.locator("#el-detail-modal").inner_text()
            for ph_lbl in ("Pha 1", "Pha 2", "Pha 3", "Pha 4"):
                if ph_lbl not in detail_txt:
                    g2_errs.append(f"Hộp thoại chi tiết 4 pha thiếu '{ph_lbl}'")
            page.locator("[data-detail-jump-phase]").first.click()
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
            if not page.locator("#el-case-drawer-backdrop").is_hidden():
                g2_errs.append("Ngăn kéo chỉnh sửa ca bị mở thay vì bị khóa bởi hộp thoại Zero-PHI!")
            page.keyboard.press("Escape")
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="hidden", timeout=5000)
            page.locator("#el-btn-detail-close").click()
            page.locator("#el-detail-modal-backdrop").wait_for(state="hidden", timeout=5000)

            report_gate(
                "TC_G06_2_OD05_INTERACTIONS_AND_DETAIL_MODAL",
                g2_errs,
                "5/5 ca OD-05 · lọc EGD/COL/ERCP · ADR 45/50 · CUSUM CIR/ERCP · Chi tiết 4 pha hoạt động mượt với 0 /api/* mạng",
            )

            # 3. Verify read-only Superadmin layout & Zero-PHI lock modal on all write/export/admin buttons
            g3_errs: list[str] = []
            locked_selectors_cases = [
                "#el-btn-new-case",
                "[data-case-edit]",
                "#el-btn-export-csv",
                "#el-btn-open-vault-backup",
                "#el-btn-change-password",
            ]
            for sel in locked_selectors_cases:
                page.locator(sel).first.click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
                if not page.locator("#el-case-drawer-backdrop").is_hidden():
                    g3_errs.append(f"Ngăn kéo nhập ca bị mở khi bấm '{sel}'")
                page.locator("#el-btn-demo-lock-ok").click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="hidden", timeout=5000)

            page.locator('.el-tab-btn[data-nav-target="quality"]').click()
            page.locator("#el-view-quality").wait_for(state="visible", timeout=5000)

            admin_vis = page.evaluate(
                """() => ({
                    noticeVisible: !document.getElementById('el-superadmin-readonly-notice')?.hidden,
                    gridVisible: !document.getElementById('el-superadmin-grid')?.hidden,
                    cardCount: document.querySelectorAll('#el-superadmin-grid .el-admin-card').length,
                    userItemCount: document.querySelectorAll('#el-admin-user-list .el-admin-item').length,
                    mergeOptionCount: document.querySelectorAll('#el-admin-merge-source option').length
                })"""
            )
            if (
                not admin_vis["noticeVisible"]
                or not admin_vis["gridVisible"]
                or admin_vis["cardCount"] != 4
                or admin_vis["userItemCount"] != 2
                or admin_vis["mergeOptionCount"] != 5
            ):
                g3_errs.append(f"Bố cục minh họa chỉ đọc của Superadmin chưa hiển thị đủ 4 thẻ / 5 BN mẫu / 2 tài khoản: {admin_vis}")

            for admin_sel in (
                "#el-btn-save-settings",
                "#el-btn-pick-restore-file",
                "#el-btn-run-restore",
                "#el-btn-run-patient-merge",
                "#el-btn-run-reset-password",
            ):
                page.locator(admin_sel).scroll_into_view_if_needed()
                page.locator(admin_sel).click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
                page.locator("#el-btn-demo-lock-close").click()
                page.locator("#el-demo-lock-modal-backdrop").wait_for(state="hidden", timeout=5000)

            # GC-04 check: opening lock modal inside shell then expiring/logging out must auto-dismiss lock modal cleanly,
            # and opening lock modal from #el-login-screen must mark #el-login-screen inert until dismissed.
            page.locator("#el-btn-save-settings").scroll_into_view_if_needed()
            page.locator("#el-btn-save-settings").click()
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
            page.evaluate("() => document.getElementById('el-btn-logout').click()")
            page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
            if not page.locator("#el-demo-lock-modal-backdrop").is_hidden():
                g3_errs.append("GC-04: Hộp thoại khóa #el-demo-lock-modal-backdrop không tự đóng khi đăng xuất/hết phiên!")

            page.evaluate(
                "() => document.getElementById('el-login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))"
            )
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="visible", timeout=5000)
            login_inert_while_locked = page.evaluate("() => Boolean(document.getElementById('el-login-screen')?.inert)")
            if not login_inert_while_locked:
                g3_errs.append("GC-04: #el-login-screen chưa gắn inert khi mở hộp thoại khóa từ màn đăng nhập!")
            page.locator("#el-btn-demo-lock-ok").click()
            page.locator("#el-demo-lock-modal-backdrop").wait_for(state="hidden", timeout=5000)
            login_inert_after_close = page.evaluate("() => Boolean(document.getElementById('el-login-screen')?.inert)")
            if login_inert_after_close:
                g3_errs.append("GC-04: #el-login-screen vẫn còn inert sau khi đóng hộp thoại khóa!")

            # Re-enter showcase shell as primary endoscopist for subsequent gates
            page.locator("#el-btn-dev-bypass").click()
            page.locator("#el-app-shell").wait_for(state="visible", timeout=5000)

            report_gate(
                "TC_G06_3_SUPERADMIN_READONLY_AND_WRITE_LOCKS",
                g3_errs,
                "4/4 thẻ Superadmin chỉ đọc + 10/10 nút ghi/xuất/mật khẩu/khôi phục/gộp + GC-04 đóng/inert chuẩn xác",
            )

            # 4. Verify Service Worker scope '/endolog/' & sibling cache preservation ('idea-agent-sibling-v1')
            g4_errs: list[str] = []
            sw_audit = page.evaluate(
                """async () => {
                    if (!('serviceWorker' in navigator)) return { supported: false };
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
                        cachedPaths
                    };
                }"""
            )
            expected_scope = f"{origin}{base_path}"
            if sw_audit.get("supported"):
                if sw_audit.get("scope") != expected_scope:
                    g4_errs.append(f"Service Worker scope sai: {sw_audit.get('scope')!r} != {expected_scope!r}")
                if not str(sw_audit.get("scriptURL", "")).endswith(f"{base_path}sw-demo.js"):
                    g4_errs.append(f"Service Worker scriptURL sai: {sw_audit.get('scriptURL')!r}")
                if sw_audit.get("demoKey") != f"endolog-ghpages-demo-v{__version__}":
                    g4_errs.append(f"Tên khóa cache SW không khớp phiên bản: {sw_audit.get('demoKey')!r}")
                if not sw_audit.get("siblingPreserved"):
                    g4_errs.append("sw-demo.js đã xóa nhầm cache của ứng dụng anh em 'idea-agent-sibling-v1'!")
                outside_paths = [cp for cp in sw_audit.get("cachedPaths", []) if not cp.startswith(base_path)]
                if outside_paths:
                    g4_errs.append(f"Cache chứa tài nguyên nằm ngoài {base_path}: {outside_paths}")

            report_gate(
                "TC_G06_4_SW_SCOPE_AND_SIBLING_CACHE_SAFETY",
                g4_errs,
                f"scope={sw_audit.get('scope')} · cache={sw_audit.get('demoKey')} · siblingCachePreserved=True",
            )

            # 5. Verify responsive layout (390x844 & 1440x900 x Light/Dark), firstCaseCardTopY <= 700px & >= 44x44px touch targets
            g5_errs: list[str] = []
            mobile_first_case_y = 0.0
            for theme_mode in ("light", "dark"):
                cur_theme = page.evaluate("() => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'")
                if cur_theme != theme_mode:
                    page.locator("#el-theme-toggle").click()
                    page.wait_for_timeout(80)

                for vw, vh in [(390, 844), (1440, 900)]:
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
                            const bannerBtns = Array.from(document.querySelectorAll('button, input, select'))
                                .filter(el => {
                                    if (el.hidden || el.disabled) return false;
                                    const cs = getComputedStyle(el);
                                    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
                                    const rect = el.getBoundingClientRect();
                                    return rect.width > 0 && rect.height > 0;
                                })
                                .map(el => {
                                    const rect = el.getBoundingClientRect();
                                    return {
                                        id: el.id || el.className,
                                        w: Math.round(rect.width * 10) / 10,
                                        h: Math.round(rect.height * 10) / 10
                                    };
                                });
                            const undersized = bannerBtns.filter(b => b.w < 43.5 || b.h < 43.5);
                            return {
                                scrollWidth: document.documentElement.scrollWidth,
                                innerWidth: window.innerWidth,
                                firstCaseY: r ? Math.round((r.top + window.scrollY) * 10) / 10 : 9999,
                                undersized
                            };
                        }"""
                    )
                    if metrics["scrollWidth"] > metrics["innerWidth"]:
                        g5_errs.append(f"Tràn ngang tại {vw}x{vh} [{theme_mode}]: {metrics}")
                    if metrics["undersized"]:
                        g5_errs.append(f"Vùng chạm < 44x44px tại {vw}x{vh} [{theme_mode}]: {metrics['undersized'][:3]}")
                    if vw == 390 and theme_mode == "light":
                        mobile_first_case_y = float(metrics["firstCaseY"])
                        if mobile_first_case_y > 700.0:
                            g5_errs.append(f"firstCaseCardTopY tại 390x844 = {mobile_first_case_y}px > 700px")

                    if capture_screenshots and vw == 1440 and theme_mode == "light":
                        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                        shot_path = SCREENSHOT_DIR / "gh_pages_demo_1440_light.png"
                        page.screenshot(path=str(shot_path), full_page=False)
                        if BRAIN_DIR.is_dir():
                            shutil.copy2(shot_path, BRAIN_DIR / "gh_pages_demo_1440_light.png")

            report_gate(
                "TC_G06_5_RESPONSIVE_FIRST_CASE_Y_AND_TOUCH",
                g5_errs,
                f"mobile390_firstCaseCardTopY={mobile_first_case_y}px (<= 700px) · overflow=0 · touch>=44x44px",
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

    print("\nALL TC-G06 GITHUB PAGES SUBPATH PLAYWRIGHT GATES PASSED (0 FAILURES).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or serve EndoLog Gate C GitHub Pages static bundle (/endolog/).")
    parser.add_argument("--dist-dir", default=str(REPO_ROOT / "dist_pages"), help="Path to built dist_pages/ directory.")
    parser.add_argument("--base-path", default="/endolog/", help="Subpath prefix (default: /endolog/).")
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
