#!/usr/bin/env python3
"""Playwright Phase 4A Brand Identity v1, Multi-Viewport, Touch-Target, Dynamic KPI, Vietnamese Labels & 5-Layer Zero-PHI E2E Audit."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8765"
EXPECTED_NETLOC = urlparse(BASE_URL).netloc
REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = REPO_ROOT / "docs" / "brand" / "screenshots"
BRAIN_DIR = Path("/Users/khuonganvu/.gemini/antigravity/brain/5c360f0d-e4f4-4860-8e5e-8aa35a4b9a33")

VIEWS = [
    ("cases", "nhat_ky_ca_soi", "Nhật ký ca soi"),
    ("surveillance", "hen_soi_lai", "Hẹn soi lại"),
    ("quality", "chi_so_chat_luong", "Chỉ số chất lượng"),
]

AUDIT_WIDTHS = [320, 360, 375, 390, 414, 768, 1024, 1440]

ALLOWED_STATIC_PATH_PREFIXES = (
    "/index.html",
    "/manifest.json",
    "/sw.js",
    "/css/",
    "/js/",
    "/icons/",
    "/fonts/",
)

OD05_SENTINELS = (
    "COL-2026-0001",
    "COL-2026-0002",
    "EGD-2026-0001",
    "EGD-2026-0002",
    "ERCP-2026-0001",
    "L.T.M.T",
    "T.Q.B",
    "P.H.K",
    "Đ.V.H",
    "V.T.N.L",
)


def report_gate(gate_name: str, local_failures: list[str], detail: str, all_failures: list[str]) -> None:
    """Print PASS only when local_failures is empty; otherwise record into all_failures and print FAIL."""
    if local_failures:
        all_failures.extend(local_failures)
        print(f"FAIL {gate_name}: {len(local_failures)} lỗi ({local_failures[0]})")
    else:
        print(f"PASS {gate_name}: {detail}")


def switch_to_view(page, view_key: str, width: int) -> None:
    if width < 768:
        selector = f'.el-bottom-btn[data-nav-target="{view_key}"]'
    else:
        selector = f'.el-tab-btn[data-nav-target="{view_key}"]'
    page.locator(selector).click()
    page.locator(f"#el-view-{view_key}").wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(120)


def set_theme_if_needed(page, target_theme: str) -> None:
    current = page.evaluate("() => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'")
    if current != target_theme:
        page.locator("#el-theme-toggle").click()
        page.wait_for_timeout(120)
    after = page.evaluate("() => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'")
    if after != target_theme:
        raise AssertionError(f"Không chuyển được sang chế độ {target_theme} (hiện tại: {after})")


def is_allowed_static_cache_url(raw_url: str) -> bool:
    parsed = urlparse(raw_url)
    if parsed.scheme not in ("http", "https") or parsed.netloc != EXPECTED_NETLOC:
        return False
    path = parsed.path or "/"
    if path == "/":
        return True
    if path.startswith("/api/"):
        return False
    return any(path == p or path.startswith(p) for p in ALLOWED_STATIC_PATH_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify EndoLog Phase 4A Brand Identity v1 & Zero-PHI 5 Layers.")
    parser.add_argument(
        "--no-write-screenshots",
        action="store_true",
        help="Run all Playwright checks without overwriting PNG screenshots in docs/brand/screenshots/ or Brain.",
    )
    args = parser.parse_args()

    if not args.no_write_screenshots:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    http_errors: list[str] = []
    api_responses: list[dict[str, object]] = []
    allow_simulated_net_error = False
    allow_simulated_401 = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            device_scale_factor=2,
            locale="vi-VN",
        )
        page = context.new_page()

        def on_console(msg) -> None:
            if msg.type != "error":
                return
            if allow_simulated_net_error and ("ERR_FAILED" in msg.text or "Failed to fetch" in msg.text):
                return
            if allow_simulated_401 and "401" in msg.text:
                return
            console_errors.append(f"[{msg.type}] {msg.text}")

        def on_response(resp) -> None:
            parsed = urlparse(resp.url)
            if parsed.path.startswith("/api/"):
                if not (allow_simulated_401 and resp.status == 401):
                    api_responses.append(
                        {
                            "url": resp.url,
                            "path": parsed.path,
                            "status": resp.status,
                            "headers": {k.lower(): v for k, v in resp.headers.items()},
                        }
                    )
            if resp.status >= 400:
                if allow_simulated_401 and resp.status == 401:
                    return
                http_errors.append(f"{resp.status} {resp.url}")

        page.on("console", on_console)
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on("response", on_response)

        # 1. Verify Login Screen (?login=1) brand rules
        login_errs: list[str] = []
        page.goto(f"{BASE_URL}/?login=1", wait_until="domcontentloaded")
        page.locator("#el-login-screen").wait_for(state="visible", timeout=8000)
        page.evaluate("() => document.fonts.ready")
        login_info = page.evaluate(
            """() => {
                const sub = document.querySelector('#el-login-screen .el-brand-subtitle');
                const endo = document.querySelector('#el-login-screen .el-wordmark-endo');
                const log = document.querySelector('#el-login-screen .el-wordmark-log');
                return {
                    subtitleVisible: !!sub && getComputedStyle(sub).display !== 'none',
                    subtitleText: sub ? sub.textContent.trim() : '',
                    endoWeight: endo ? Number(getComputedStyle(endo).fontWeight) : 0,
                    endoColor: endo ? getComputedStyle(endo).color : '',
                    logColor: log ? getComputedStyle(log).color : '',
                    imgCount: document.querySelectorAll('img, video').length,
                };
            }"""
        )
        if not login_info["subtitleVisible"] or "Hệ thống sổ bộ lâm sàng" not in login_info["subtitleText"]:
            login_errs.append(f"Màn hình đăng nhập thiếu phụ đề tiếng Việt đầy đủ: {login_info}")
        if login_info["imgCount"] != 0:
            login_errs.append(f"Vi phạm Zero-Image: phát hiện {login_info['imgCount']} thẻ img/video")
        if login_info["endoWeight"] < 700 or login_info["endoColor"] == login_info["logColor"]:
            login_errs.append(f"Wordmark EndoLog sai quy cách hai màu/độ đậm: {login_info}")
        report_gate(
            "LOGIN_BRAND_CHECK",
            login_errs,
            f"subtitle='{login_info['subtitleText']}' · imgCount={login_info['imgCount']}",
            failures,
        )

        # 2. Authenticate via 1-click local-bypass button into main shell with 5 OD-05 clinical vignettes
        seed_errs: list[str] = []
        page.locator("#el-btn-dev-bypass").wait_for(state="visible", timeout=5000)
        page.locator("#el-btn-dev-bypass").click()
        page.locator("#el-app-shell").wait_for(state="visible", timeout=8000)
        page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=8000)
        page.evaluate("() => document.fonts.ready")
        page.evaluate("() => ('serviceWorker' in navigator) ? navigator.serviceWorker.ready.then(() => true) : false")

        case_count = page.locator("#el-case-list .el-case-card").count()
        if case_count != 5:
            seed_errs.append(f"Kỳ vọng đúng 5 ca lâm sàng chuẩn OD-05, thực tế={case_count}")
        report_gate("OD05_SEED_COUNT", seed_errs, f"{case_count}/5 ca chuẩn OD-05 đã hiển thị", failures)

        # 3. Verify Brand Identity v1 Invariants (meta theme-color, 3-cue active tabs, proc chips, mobile header)
        for theme_mode, expected_meta in [("light", "#475985"), ("dark", "#0d0f15")]:
            meta_errs: list[str] = []
            brand_errs: list[str] = []
            page.set_viewport_size({"width": 1440, "height": 960})
            set_theme_if_needed(page, theme_mode)
            meta_val = (page.locator("#el-meta-theme").get_attribute("content") or "").strip().lower()
            if meta_val != expected_meta:
                meta_errs.append(f"meta[name=theme-color] sai ở chế độ {theme_mode}: '{meta_val}' != '{expected_meta}'")
            report_gate(f"META_THEME_COLOR [{theme_mode}]", meta_errs, meta_val, failures)

            desktop_check = page.evaluate(
                """() => {
                    const activeTab = document.querySelector('.el-tab-btn[aria-selected="true"]');
                    const dot = activeTab.querySelector('.el-tab-dot');
                    const tabCs = getComputedStyle(activeTab);
                    const dotCs = getComputedStyle(dot);
                    const sub = document.querySelector('.el-brand-subtitle--header');
                    const moon = document.getElementById('el-icon-moon');
                    const sun = document.getElementById('el-icon-sun');
                    const chips = Array.from(document.querySelectorAll('#el-case-list .el-proc-chip')).map(ch => ({
                        text: ch.textContent.trim(),
                        hasDot: !!ch.querySelector('.el-proc-dot'),
                    }));
                    return {
                        fontWeight: Number(tabCs.fontWeight),
                        borderBottomWidth: parseFloat(tabCs.borderBottomWidth),
                        dotOpacity: parseFloat(dotCs.opacity),
                        headerSubVisible: getComputedStyle(sub).display !== 'none',
                        moonVisible: moon.getBoundingClientRect().width > 0,
                        sunVisible: sun.getBoundingClientRect().width > 0,
                        chips,
                    };
                }"""
            )
            expect_sun = theme_mode == "dark"
            if (
                desktop_check["fontWeight"] < 600
                or desktop_check["borderBottomWidth"] < 2.0
                or desktop_check["dotOpacity"] < 0.99
                or not desktop_check["headerSubVisible"]
                or desktop_check["sunVisible"] != expect_sun
                or desktop_check["moonVisible"] == expect_sun
            ):
                brand_errs.append(f"Desktop brand check trượt [{theme_mode}]: {desktop_check}")
            for chip in desktop_check["chips"]:
                if chip["text"] not in ("EGD", "COL", "ERCP") or not chip["hasDot"]:
                    brand_errs.append(f"Chip thủ thuật sai quy chuẩn [{theme_mode}]: {chip}")

            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(100)
            mobile_check = page.evaluate(
                """() => {
                    const mark = document.querySelector('.el-brand-mark--header');
                    const halo = document.querySelector('.el-brand-mark--header .el-brand-halo');
                    const sub = document.querySelector('.el-brand-subtitle--header');
                    const activeNav = document.querySelector('.el-bottom-btn[aria-selected="true"]');
                    const navCs = getComputedStyle(activeNav);
                    const dotCs = getComputedStyle(activeNav.querySelector('.el-tab-dot'));
                    const rect = mark.getBoundingClientRect();
                    return {
                        markW: Math.round(rect.width),
                        markH: Math.round(rect.height),
                        haloDisplay: getComputedStyle(halo).display,
                        subDisplay: getComputedStyle(sub).display,
                        navWeight: Number(navCs.fontWeight),
                        navBorderBottom: parseFloat(navCs.borderBottomWidth),
                        navDotOpacity: parseFloat(dotCs.opacity),
                    };
                }"""
            )
            if (
                mobile_check["markW"] != 28
                or mobile_check["markH"] != 28
                or mobile_check["haloDisplay"] != "none"
                or mobile_check["subDisplay"] != "none"
                or mobile_check["navWeight"] < 600
                or mobile_check["navBorderBottom"] < 2.0
                or mobile_check["navDotOpacity"] < 0.99
            ):
                brand_errs.append(f"Mobile 390px brand check trượt [{theme_mode}]: {mobile_check}")
            report_gate(
                f"BRAND_HEADER_AND_3_CUE_NAV [{theme_mode}]",
                brand_errs,
                f"mobile_mark={mobile_check['markW']}x{mobile_check['markH']}px · halo={mobile_check['haloDisplay']} · subtitle={mobile_check['subDisplay']}",
                failures,
            )

        # 4. Verify R2/B04 (0 raw machine enums in UI across all 3 screens) & R3/B01 (n_min=20 sample size guard, 0 'Đạt chuẩn')
        enum_errs: list[str] = []
        kpi_errs: list[str] = []
        page.set_viewport_size({"width": 1440, "height": 960})
        set_theme_if_needed(page, "light")
        view_texts: dict[str, str] = {}
        for view_key, _, _ in VIEWS:
            switch_to_view(page, view_key, 1440)
            view_texts[view_key] = page.locator(f"#el-view-{view_key}").inner_text()

        combined_text = "\n".join(view_texts.values())
        raw_snake = re.findall(r"\b[A-Z0-9]{2,}(?:_[A-Z0-9]+)+\b", combined_text)
        raw_pep = re.findall(r"\bPEP\s+(?:MILD|MODERATE|SEVERE|NONE)\b", combined_text)
        if raw_snake:
            enum_errs.append(f"Xuất hiện mã enum kỹ thuật thô trên giao diện: {raw_snake}")
        if raw_pep:
            enum_errs.append(f"Xuất hiện mức độ PEP tiếng Anh thô trên giao diện: {raw_pep}")
        for forbidden_phrase in (
            "COL · Đại tràng",
            "Trạng thái vòng lặp",
            "Đang mở theo dõi dọc",
        ):
            if forbidden_phrase in combined_text:
                enum_errs.append(f"Vẫn còn thuật ngữ nội bộ hoặc nhãn cũ trên giao diện: '{forbidden_phrase}'")
        for expected_phrase in (
            "COL · Đại trực tràng",
            "USMSTF 2020",
            "Theo chỉ định bác sĩ",
            "Viêm tụy sau ERCP mức nhẹ · AGREE II",
            "RA-CUSUM chưa bật (chưa có mô hình nguy cơ được thẩm định)",
            "Đang theo dõi",
        ):
            if expected_phrase not in combined_text:
                enum_errs.append(f"Thiếu nhãn tiếng Việt kỳ vọng trên giao diện: '{expected_phrase}'")
        report_gate(
            "UI_VIETNAMESE_LABELS_NO_RAW_ENUMS",
            enum_errs,
            "0 mã UPPER_SNAKE_CASE · 0 PEP tiếng Anh · chuẩn hóa đầy đủ COL · Đại trực tràng, USMSTF 2020, Theo chỉ định bác sĩ, Viêm tụy sau ERCP mức nhẹ · AGREE II, RA-CUSUM chưa bật, Đang theo dõi",
            failures,
        )

        if "Đạt chuẩn" in view_texts["quality"]:
            kpi_errs.append("Vẫn còn nhãn cố định 'Đạt chuẩn' trên màn Chỉ số chất lượng")
        if "Tách bạch GPB" in view_texts["quality"]:
            kpi_errs.append("Vẫn còn pill 'Tách bạch GPB' trên màn Chỉ số chất lượng")
        if view_texts["quality"].count("Chưa đủ cỡ mẫu (n < 20)") != 5:
            kpi_errs.append(
                f"5 thẻ tỷ lệ cá nhân trên 5 ca OD-05 (mẫu số 1–2 < n_min=20) phải hiện 'Chưa đủ cỡ mẫu (n < 20)', thực tế: {view_texts['quality']}"
            )
        if "Có biến cố nhẹ/vừa · 1 ca chờ cửa sổ" not in view_texts["quality"]:
            kpi_errs.append("Thẻ biến cố 30 ngày không phản ánh đúng viêm tụy nhẹ + 1 ca đang chờ cửa sổ 30 ngày")
        report_gate(
            "KPI_DYNAMIC_STATUS_BADGES",
            kpi_errs,
            "0 nhãn 'Đạt chuẩn' / 'Tách bạch GPB' · 5/5 thẻ tỷ lệ cá nhân gắn pill trung tính 'Chưa đủ cỡ mẫu (n < 20)' khi mẫu số 1–2 ca + 1 thẻ biến cố phản ánh dữ liệu thực",
            failures,
        )

        # 4B. Verify R4 (Primary CTA slot empty for Phase 4B, Export button demoted, 390x844 1-row 4-cell KPI & first case y <= 700 px)
        r4_errs: list[str] = []
        set_theme_if_needed(page, "light")
        page.set_viewport_size({"width": 390, "height": 844})
        switch_to_view(page, "cases", 390)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(120)
        r4_metrics = page.evaluate(
            """() => {
                const headBtns = Array.from(document.querySelectorAll('#el-view-cases .el-section-head button'));
                const headPrimaryBtns = headBtns.length;
                const headNewCaseOk = headBtns.length === 0 || (headBtns.length === 1 && headBtns[0].id === 'el-btn-new-case' && headBtns[0].classList.contains('el-btn--primary'));
                const anyPrimaryBtnsInCases = document.querySelectorAll('#el-view-cases .el-btn--primary').length;
                const exportBtn = document.getElementById('el-btn-export-csv');
                const exportInExportBar = !!(exportBtn && exportBtn.closest('.el-export-bar'));
                const exportIsOutlined = !!(exportBtn && !exportBtn.classList.contains('el-btn--primary'));
                const statCards = Array.from(document.querySelectorAll('#el-cases-summary .el-stat-card'));
                const statTops = statCards.map(el => Math.round(el.getBoundingClientRect().top));
                const distinctTops = Array.from(new Set(statTops));
                const subHidden = statCards.every(el => {
                    const sub = el.querySelector('.el-stat-sub');
                    return sub && getComputedStyle(sub).display === 'none';
                });
                const firstCard = document.querySelector('#el-case-list .el-case-card');
                const firstCardRect = firstCard ? firstCard.getBoundingClientRect() : null;
                const firstCaseY = firstCardRect ? Math.round((firstCardRect.top + window.scrollY) * 10) / 10 : 9999;
                return {
                    headPrimaryBtns,
                    headNewCaseOk,
                    anyPrimaryBtnsInCases,
                    exportInExportBar,
                    exportIsOutlined,
                    statCardCount: statCards.length,
                    distinctTopCount: distinctTops.length,
                    statTops,
                    subHidden,
                    firstCaseY,
                };
            }"""
        )
        if not r4_metrics["headNewCaseOk"] or r4_metrics["anyPrimaryBtnsInCases"] > 1:
            r4_errs.append(f"Đầu trang Nhật ký ca soi sai cấu trúc nút chính duy nhất (#el-btn-new-case): {r4_metrics}")
        if not r4_metrics["exportInExportBar"] or not r4_metrics["exportIsOutlined"]:
            r4_errs.append(f"Nút Xuất bảng nghiên cứu chưa chuyển thành nút phụ trong khu Xuất dữ liệu: {r4_metrics}")
        if r4_metrics["statCardCount"] != 4 or r4_metrics["distinctTopCount"] != 1 or not r4_metrics["subHidden"]:
            r4_errs.append(f"4 ô tóm tắt trên điện thoại 390px chưa gộp gọn 1 hàng ngang ẩn giải thích: {r4_metrics}")
        if r4_metrics["firstCaseY"] > 700.0:
            r4_errs.append(f"Ca đầu tiên ở 390x844 bắt đầu tại y={r4_metrics['firstCaseY']}px > mục tiêu 700px")
        report_gate(
            "MOBILE_390_FIRST_CASE_Y",
            r4_errs,
            f"firstCaseCardTopY={r4_metrics['firstCaseY']}px (<= 700px target, viewport=390x844) · 1-row 4-cell KPI (tops={r4_metrics['statTops']}) · headerPrimaryNewCase={r4_metrics['headPrimaryBtns']} · exportOutlinedInExportBar=True",
            failures,
        )

        # 5. Multi-Viewport Overflow Audit: 8 widths x 3 views x 2 themes = 48 combinations + Negative Probe
        overflow_errs: list[str] = []
        overflow_checks = 0
        for theme_mode in ("light", "dark"):
            set_theme_if_needed(page, theme_mode)
            for width in AUDIT_WIDTHS:
                height = 844 if width < 768 else 960
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(70)
                for view_key, _, _ in VIEWS:
                    switch_to_view(page, view_key, width)
                    metrics = page.evaluate(
                        """() => ({
                            scrollWidth: document.documentElement.scrollWidth,
                            innerWidth: window.innerWidth
                        })"""
                    )
                    overflow_checks += 1
                    if metrics["scrollWidth"] > metrics["innerWidth"]:
                        overflow_errs.append(
                            f"Tràn ngang tại {view_key} · {width}px · {theme_mode}: "
                            f"scrollWidth={metrics['scrollWidth']} > innerWidth={metrics['innerWidth']}"
                        )

        page.set_viewport_size({"width": 390, "height": 844})
        probe_detected = page.evaluate(
            """() => {
                const probe = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                probe.setAttribute('width', '640');
                probe.setAttribute('height', '4');
                document.body.appendChild(probe);
                const sw = document.documentElement.scrollWidth;
                const iw = window.innerWidth;
                probe.remove();
                return sw > iw;
            }"""
        )
        if not probe_detected:
            overflow_errs.append("Negative probe 640px không làm tăng scrollWidth (nghi ngờ có overflow-x: hidden toàn cục)")
        report_gate(
            "MULTI_VIEWPORT_OVERFLOW",
            overflow_errs,
            f"{overflow_checks}/{overflow_checks} tổ hợp (8 độ rộng 320–1440 px × 3 màn × 2 chế độ Sáng/Tối) = 0 tràn ngang · Negative probe 640px=DETECTED",
            failures,
        )

        # 6. Touch-Target Ergonomics Audit (>= 44x44 px) across (390, 1440) x 3 views x (light, dark)
        touch_errs: list[str] = []
        checked_targets = 0
        per_theme_counts: dict[str, int] = {"light": 0, "dark": 0}
        for theme_mode in ("light", "dark"):
            set_theme_if_needed(page, theme_mode)
            for width, height in [(390, 844), (1440, 960)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(90)
                for view_key, _, _ in VIEWS:
                    switch_to_view(page, view_key, width)
                    items = page.evaluate(
                        """() => {
                            const els = Array.from(document.querySelectorAll('#el-app-shell button, #el-app-shell a, #el-app-shell input, #el-app-shell select'));
                            return els.filter(el => {
                                if (el.hidden) return false;
                                const cs = getComputedStyle(el);
                                if (cs.display === 'none' || cs.visibility === 'hidden') return false;
                                const r = el.getBoundingClientRect();
                                return r.width > 0 && r.height > 0;
                            }).map(el => {
                                const r = el.getBoundingClientRect();
                                return {
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id || '',
                                    text: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 32),
                                    w: Math.round(r.width * 10) / 10,
                                    h: Math.round(r.height * 10) / 10,
                                };
                            });
                        }"""
                    )
                    for it in items:
                        checked_targets += 1
                        per_theme_counts[theme_mode] += 1
                        if it["w"] < 44 or it["h"] < 44:
                            touch_errs.append(
                                f"{theme_mode}/{width}px/{view_key} <{it['tag']}#{it['id']} '{it['text']}'> = {it['w']}x{it['h']}px"
                            )
        if per_theme_counts["light"] != per_theme_counts["dark"] or per_theme_counts["light"] < 58:
            touch_errs.append(f"Số lượng vùng chạm không đồng nhất giữa Sáng/Tối hoặc thiếu phần tử (<58): {per_theme_counts}")
        report_gate(
            "TOUCH_TARGETS_44PX",
            touch_errs,
            f"{per_theme_counts['light']}/{per_theme_counts['light']} vùng chạm Sáng + {per_theme_counts['dark']}/{per_theme_counts['dark']} vùng chạm Tối ({checked_targets}/{checked_targets} tổng lượt kiểm tra >= 44x44 px trên 390/1440 px × 3 màn)",
            failures,
        )

        # 7. Capture all 12 standardized screenshots: (3 views) x (390, 1440) x (light, dark)
        if not args.no_write_screenshots:
            shot_errs: list[str] = []
            captured_files: list[str] = []
            for theme_mode in ("light", "dark"):
                set_theme_if_needed(page, theme_mode)
                for width, height in [(390, 844), (1440, 960)]:
                    page.set_viewport_size({"width": width, "height": height})
                    page.wait_for_timeout(100)
                    for view_key, slug, _ in VIEWS:
                        switch_to_view(page, view_key, width)
                        page.evaluate("() => window.scrollTo(0, 0)")
                        page.wait_for_timeout(100)
                        fname = f"{slug}_{width}_{theme_mode}.png"
                        out_path = SCREENSHOT_DIR / fname
                        page.screenshot(path=str(out_path), full_page=(width >= 768))
                        if BRAIN_DIR.exists():
                            shutil.copy2(out_path, BRAIN_DIR / fname)
                        captured_files.append(fname)
            if len(captured_files) != 12:
                shot_errs.append(f"Chụp thiếu ảnh chuẩn: {len(captured_files)}/12")
            report_gate(
                "SCREENSHOTS_12",
                shot_errs,
                f"Đã xuất đủ {len(captured_files)}/12 ảnh chuẩn vào docs/brand/screenshots/ và Brain/",
                failures,
            )
            for fn in captured_files:
                print(f"  - {fn}")

        # 8. 5-Layer Zero-PHI Browser & HTTP Lifecycle Verification (AGENTS.md §3.3)
        page.set_viewport_size({"width": 1440, "height": 960})
        set_theme_if_needed(page, "light")
        switch_to_view(page, "quality", 1440)

        active_storage = page.evaluate(
            """async () => {
                const ls = {};
                for (const k of Object.keys(window.localStorage)) {
                    ls[k] = window.localStorage.getItem(k);
                }
                const ss = {};
                for (const k of Object.keys(window.sessionStorage)) {
                    ss[k] = window.sessionStorage.getItem(k);
                }
                const idbList = (window.indexedDB && window.indexedDB.databases) ? await window.indexedDB.databases() : [];
                const cacheUrls = [];
                if ('caches' in window) {
                    const cacheNames = await caches.keys();
                    for (const name of cacheNames) {
                        const c = await caches.open(name);
                        const reqs = await c.keys();
                        for (const r of reqs) {
                            cacheUrls.push(r.url);
                        }
                    }
                }
                return {
                    localStorage: ls,
                    sessionStorage: ss,
                    idbNames: idbList.map(db => db.name || ''),
                    cacheUrls,
                    documentCookie: document.cookie,
                };
            }"""
        )

        # Layer 1: localStorage allowlist keys & values
        l1_errs: list[str] = []
        ls_map: dict[str, str] = active_storage["localStorage"]
        for k, v in ls_map.items():
            if k != "endolog_theme" or v not in ("light", "dark"):
                l1_errs.append(f"localStorage chứa cặp key/value ngoài allowlist: {k}={v!r}")
        if "endolog_theme" not in ls_map:
            l1_errs.append("localStorage chưa ghi nhận endolog_theme sau khi chuyển đổi giao diện")
        report_gate("ZERO_PHI_L1_LOCALSTORAGE", l1_errs, f"entries={ls_map}", failures)

        # Layer 2 (active session): sessionStorage allowlist keys & values
        l2_errs: list[str] = []
        ss_map: dict[str, str] = active_storage["sessionStorage"]
        if set(ss_map.keys()) != {"endolog_active_view"} or ss_map.get("endolog_active_view") not in ("cases", "surveillance", "quality"):
            l2_errs.append(f"sessionStorage khi đang đăng nhập sai allowlist: {ss_map}")

        # Layer 3: IndexedDB 0 databases
        l3_errs: list[str] = []
        if len(active_storage["idbNames"]) != 0:
            l3_errs.append(f"IndexedDB phát hiện cơ sở dữ liệu trái phép: {active_storage['idbNames']}")
        report_gate("ZERO_PHI_L3_INDEXEDDB", l3_errs, "databases=0", failures)

        # Layer 4: Service Worker & Cache Storage same-origin static allowlist only, 0 /api/*
        l4_errs: list[str] = []
        cache_urls: list[str] = active_storage["cacheUrls"]
        if len(cache_urls) == 0:
            l4_errs.append("Cache Storage trống (Service Worker chưa nạp tài nguyên tĩnh để kiểm chứng allowlist)")
        bad_cache_urls = [u for u in cache_urls if not is_allowed_static_cache_url(u)]
        if bad_cache_urls:
            l4_errs.append(f"Cache Storage chứa URL ngoài danh mục tĩnh cùng nguồn cho phép: {bad_cache_urls}")
        report_gate(
            "ZERO_PHI_L4_SW_CACHE_STORAGE",
            l4_errs,
            f"sameOriginStaticCachedUrls={len(cache_urls)} · apiUrlsCached=0",
            failures,
        )

        # Layer 5a: HTTP Cache-Control (all 4 directives in AGENTS.md §3.3) on all observed /api/* responses + HttpOnly cookie in context
        l5_http_errs: list[str] = []
        if len(api_responses) < 5:
            l5_http_errs.append(f"Số phản hồi /api/* thu được quá ít ({len(api_responses)}) để kết luận HTTP cache")
        required_cc_tokens = ("no-store", "no-cache", "must-revalidate", "private")
        for item in api_responses:
            hdrs = item["headers"]
            cc = hdrs.get("cache-control", "")
            pragma = hdrs.get("pragma", "")
            expires = hdrs.get("expires", "")
            if any(tok not in cc for tok in required_cc_tokens) or pragma != "no-cache" or expires != "0":
                l5_http_errs.append(
                    f"Thiếu header chống lưu đệm đầy đủ trên {item['path']}: cc={cc!r}, pragma={pragma!r}, expires={expires!r}"
                )

        ctx_cookies = context.cookies(BASE_URL)
        session_cookies = [c for c in ctx_cookies if c["name"] == "endolog_session"]
        if len(session_cookies) != 1:
            l5_http_errs.append(f"Không tìm thấy cookie phiên endolog_session trong browser context: {ctx_cookies}")
        else:
            sc = session_cookies[0]
            if not sc.get("httpOnly") or sc.get("sameSite") != "Strict":
                l5_http_errs.append(f"Cookie endolog_session thiếu cờ bảo mật HttpOnly/SameSite=Strict: {sc}")
        if "endolog_session" in active_storage["documentCookie"]:
            l5_http_errs.append("document.cookie đọc được endolog_session (vi phạm HttpOnly)")
        report_gate(
            "ZERO_PHI_L5A_HTTP_NO_STORE_AND_COOKIE",
            l5_http_errs,
            f"apiResponsesChecked={len(api_responses)} (100% no-store,no-cache,must-revalidate,private) · cookieExistsInContext=True · httpOnly=True · sameSite=Strict · hiddenFromJs=True",
            failures,
        )

        # Layer 5b & Layer 2 post-logout: Logout 200 + Logout Net-Abort + Mid-Session 401 + Idle Timeout + Hard 15m JWT Expiry + Re-login Isolation
        l5_wipe_errs: list[str] = []

        def verify_clean_logged_out_dom(stage_label: str, extra_sentinel: str) -> dict[str, object]:
            snap = page.evaluate(
                """() => ({
                    html: document.documentElement.innerHTML,
                    searchVal: document.getElementById('el-case-search').value,
                    sessionKeys: Object.keys(window.sessionStorage),
                    loginVisible: !document.getElementById('el-login-screen').hidden,
                    shellHidden: document.getElementById('el-app-shell').hidden,
                    errHidden: document.getElementById('el-login-error').hidden,
                    errText: document.getElementById('el-login-error').textContent,
                    sanitizedState: window.__ENDOLOG_RUNTIME_AUDIT__.getSanitizedClientState(),
                })"""
            )
            if not snap["loginVisible"] or not snap["shellHidden"]:
                l5_wipe_errs.append(f"[{stage_label}] Chưa quay về màn hình đăng nhập hoặc chưa ẩn khung ứng dụng")
            if snap["searchVal"] != "":
                l5_wipe_errs.append(f"[{stage_label}] Ô tìm kiếm chưa xóa sạch: {snap['searchVal']!r}")
            if snap["sessionKeys"] != []:
                l2_errs.append(f"[{stage_label}] sessionStorage chưa xóa sạch: {snap['sessionKeys']}")
            st = snap["sanitizedState"]
            if (
                st["hasUser"]
                or st["casesCount"] != 0
                or st["surveillanceCount"] != 0
                or st["hasKpiBundle"]
                or st["hasCusumData"]
                or st["hasAuditStatus"]
                or st["searchQueryLength"] != 0
                or st["hasIdleTimer"]
                or st["hasHardExpiryTimer"]
            ):
                l5_wipe_errs.append(f"[{stage_label}] State bộ nhớ client chưa dọn sạch: {st}")
            for tok in (*OD05_SENTINELS, extra_sentinel):
                if tok in snap["html"]:
                    l5_wipe_errs.append(f"[{stage_label}] Dữ liệu ca bệnh/tìm kiếm '{tok}' còn sót trong DOM sau khi kết thúc phiên")
            return snap

        # Subtest A: Normal logout (200 OK) — await actual /api/auth/logout response before cookie check
        page.locator('[data-cusum-metric="ERCP_NATIVE"]').click()
        page.wait_for_timeout(120)
        switch_to_view(page, "cases", 1440)
        page.locator('[data-track-filter="ERCP"]').click()
        page.locator("#el-case-search").fill("SYNTHETIC_LOGOUT_OK_E2E")
        with page.expect_response("**/api/auth/logout") as logout_resp_info:
            page.locator("#el-btn-logout").click()
        assert logout_resp_info.value.status == 200
        page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
        verify_clean_logged_out_dom("logout_200", "SYNTHETIC_LOGOUT_OK_E2E")
        if any(c["name"] == "endolog_session" for c in context.cookies(BASE_URL)):
            l5_wipe_errs.append("[logout_200] Cookie endolog_session vẫn còn trong browser context sau khi đăng xuất")

        # Subtest B: Re-login isolation — verify prior ERCP filter, search query, and ERCP_NATIVE CUSUM did NOT carry over
        page.locator("#el-btn-dev-bypass").click()
        page.locator("#el-app-shell").wait_for(state="visible", timeout=5000)
        page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=5000)
        relogin_state = page.evaluate("() => window.__ENDOLOG_RUNTIME_AUDIT__.getSanitizedClientState()")
        if (
            relogin_state["trackFilter"] != "ALL"
            or relogin_state["cusumMetric"] != "CIR"
            or relogin_state["hasCusumData"]
            or page.locator("#el-case-list .el-case-card").count() != 5
        ):
            l5_wipe_errs.append(f"[relogin_isolation] Bộ lọc hoặc biểu đồ phiên cũ rò rỉ sang phiên mới: {relogin_state}")

        # Subtest C: Simulated network failure during logout (client wipes 100% + warns server revocation unconfirmed)
        page.locator("#el-case-search").fill("SYNTHETIC_LOGOUT_NETFAIL_E2E")
        allow_simulated_net_error = True
        context.route("**/api/auth/logout", lambda route: route.abort("failed"))
        page.locator("#el-btn-logout").click()
        page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
        page.locator("#el-login-error").wait_for(state="visible", timeout=5000)
        context.unroute("**/api/auth/logout")
        allow_simulated_net_error = False

        netfail_snap = verify_clean_logged_out_dom("logout_net_abort", "SYNTHETIC_LOGOUT_NETFAIL_E2E")
        if netfail_snap["errHidden"] or "chưa xác nhận hủy phiên trên máy chủ" not in str(netfail_snap["errText"]):
            l5_wipe_errs.append(f"[logout_net_abort] Thiếu cảnh báo chưa xác nhận hủy phiên server: {netfail_snap['errText']!r}")
        page.evaluate("() => fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' })")

        # Subtest D: Mid-session HTTP 401 on API request wipes DOM & state immediately
        page.locator("#el-btn-dev-bypass").click()
        page.locator("#el-app-shell").wait_for(state="visible", timeout=5000)
        page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=5000)
        page.locator("#el-case-search").fill("SYNTHETIC_401_WIPE_E2E")
        switch_to_view(page, "quality", 1440)
        allow_simulated_401 = True
        context.route(
            "**/api/metrics/kpi?min_adr_age=50",
            lambda route: route.fulfill(
                status=401,
                content_type="application/json",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, private",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
                body='{"detail":"Expired"}',
            ),
        )
        page.locator('[data-age-toggle="50"]').click()
        page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
        page.locator("#el-login-error").wait_for(state="visible", timeout=5000)
        context.unroute("**/api/metrics/kpi?min_adr_age=50")
        allow_simulated_401 = False
        s401_snap = verify_clean_logged_out_dom("api_401", "SYNTHETIC_401_WIPE_E2E")
        if s401_snap["errHidden"] or "hết hạn" not in str(s401_snap["errText"]):
            l5_wipe_errs.append(f"[api_401] Thiếu cảnh báo phiên hết hạn khi gặp HTTP 401: {s401_snap['errText']!r}")
        page.evaluate("() => fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' })")

        # Subtest E: Idle timeout auto-lock & server cookie revocation
        page.locator("#el-btn-dev-bypass").click()
        page.locator("#el-app-shell").wait_for(state="visible", timeout=5000)
        page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=5000)
        page.locator("#el-case-search").fill("SYNTHETIC_IDLE_TIMEOUT_E2E")
        with page.expect_response("**/api/auth/logout") as idle_logout_resp:
            page.evaluate("() => window.__ENDOLOG_RUNTIME_AUDIT__.setIdleTimeoutForTest(80)")
        assert idle_logout_resp.value.status == 200
        page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
        page.locator("#el-login-error").wait_for(state="visible", timeout=5000)
        idle_snap = verify_clean_logged_out_dom("idle_timeout", "SYNTHETIC_IDLE_TIMEOUT_E2E")
        if idle_snap["errHidden"] or "15 phút" not in str(idle_snap["errText"]):
            l5_wipe_errs.append(f"[idle_timeout] Thiếu thông báo tự động khóa sau 15 phút: {idle_snap['errText']!r}")
        if any(c["name"] == "endolog_session" for c in context.cookies(BASE_URL)):
            l5_wipe_errs.append("[idle_timeout] Cookie endolog_session vẫn còn sau khi tự động khóa phiên")
        page.evaluate("() => window.__ENDOLOG_RUNTIME_AUDIT__.setIdleTimeoutForTest(900000)")

        # Subtest F: Hard 15-minute non-sliding JWT session expiration wipes DOM & revokes cookie even without API calls
        page.locator("#el-btn-dev-bypass").click()
        page.locator("#el-app-shell").wait_for(state="visible", timeout=5000)
        page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=5000)
        page.locator("#el-case-search").fill("SYNTHETIC_HARD_JWT_EXP_E2E")
        with page.expect_response("**/api/auth/logout") as hard_logout_resp:
            page.evaluate("() => window.__ENDOLOG_RUNTIME_AUDIT__.setHardSessionExpiryForTest(80)")
        assert hard_logout_resp.value.status == 200
        page.locator("#el-login-screen").wait_for(state="visible", timeout=5000)
        page.locator("#el-login-error").wait_for(state="visible", timeout=5000)
        hard_snap = verify_clean_logged_out_dom("hard_jwt_expiry", "SYNTHETIC_HARD_JWT_EXP_E2E")
        if hard_snap["errHidden"] or "Phiên xác thực 15 phút đã hết hạn" not in str(hard_snap["errText"]):
            l5_wipe_errs.append(f"[hard_jwt_expiry] Thiếu thông báo hết hạn phiên xác thực 15 phút: {hard_snap['errText']!r}")
        if any(c["name"] == "endolog_session" for c in context.cookies(BASE_URL)):
            l5_wipe_errs.append("[hard_jwt_expiry] Cookie endolog_session vẫn còn sau khi hết hạn phiên cứng")

        report_gate(
            "ZERO_PHI_L2_SESSIONSTORAGE",
            l2_errs,
            f"active={ss_map} · afterAllSessionTerminations={{}}",
            failures,
        )
        report_gate(
            "ZERO_PHI_L5B_SESSION_TERMINATION_DOM_WIPE",
            l5_wipe_errs,
            "logout_200 + idle_timeout + hard_jwt_expiry xóa 100% DOM/state & thu hồi cookie; logout_net_abort xóa 100% DOM/state & cảnh báo chưa xác nhận server; api_401 xóa 100% DOM/state; re-login cách ly sạch",
            failures,
        )

        context.close()
        browser.close()

    runtime_errs: list[str] = []
    if console_errors:
        runtime_errs.extend([f"Console error: {e}" for e in console_errors])
    if page_errors:
        runtime_errs.extend([f"Page error: {e}" for e in page_errors])
    if http_errors:
        runtime_errs.extend([f"HTTP >=400: {e}" for e in http_errors])
    report_gate(
        "RUNTIME_CLEANLINESS",
        runtime_errs,
        "console.error=0 · pageerror=0 · HTTP_4xx_5xx=0",
        failures,
    )

    if failures:
        print("\nFAILED CHECKS:")
        for item in failures:
            print(f"  [FAIL] {item}")
        return 1

    print("\nALL PHASE 4A PLAYWRIGHT VERIFICATION GATES PASSED (0 FAILURES).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
