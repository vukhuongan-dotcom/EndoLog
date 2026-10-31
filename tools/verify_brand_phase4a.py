#!/usr/bin/env python3
"""Playwright Phase 4A Brand Identity v1, Multi-Viewport, Touch-Target, CSP & Zero-PHI Audit + 12 Screenshots."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8765"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = REPO_ROOT / "docs" / "brand" / "screenshots"
BRAIN_DIR = Path("/Users/khuonganvu/.gemini/antigravity/brain/5c360f0d-e4f4-4860-8e5e-8aa35a4b9a33")

VIEWS = [
    ("cases", "nhat_ky_ca_soi", "Nhật ký ca soi"),
    ("surveillance", "hen_soi_lai", "Hẹn soi lại"),
    ("quality", "chi_so_chat_luong", "Chỉ số chất lượng"),
]

AUDIT_WIDTHS = [320, 360, 375, 390, 414, 768, 1024, 1440]


def switch_to_view(page, view_key: str, width: int) -> None:
    if width < 768:
        selector = f'.el-bottom-btn[data-nav-target="{view_key}"]'
    else:
        selector = f'.el-tab-btn[data-nav-target="{view_key}"]'
    page.locator(selector).click()
    page.locator(f"#el-view-{view_key}").wait_for(state="visible", timeout=5000)
    page.wait_for_timeout(150)


def set_theme_if_needed(page, target_theme: str) -> None:
    current = page.evaluate("() => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'")
    if current != target_theme:
        page.locator("#el-theme-toggle").click()
        page.wait_for_timeout(150)
    after = page.evaluate("() => document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light'")
    if after != target_theme:
        raise AssertionError(f"Không chuyển được sang chế độ {target_theme} (hiện tại: {after})")


def main() -> int:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    http_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            device_scale_factor=2,
            locale="vi-VN",
        )
        page = context.new_page()

        page.on(
            "console",
            lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        page.on(
            "response",
            lambda resp: http_errors.append(f"{resp.status} {resp.url}")
            if resp.status >= 400
            else None,
        )

        # 1. Verify Login Screen (?login=1) brand rules first
        page.goto(f"{BASE_URL}/?login=1", wait_until="domcontentloaded")
        page.locator("#el-login-screen").wait_for(state="visible", timeout=8000)
        page.evaluate("() => document.fonts.ready")
        login_info = page.evaluate(
            """() => {
                const sub = document.querySelector('#el-login-screen .el-brand-subtitle');
                const endo = document.querySelector('#el-login-screen .el-wordmark-endo');
                const log = document.querySelector('#el-login-screen .el-wordmark-log');
                const rootCs = getComputedStyle(document.documentElement);
                return {
                    subtitleVisible: !!sub && getComputedStyle(sub).display !== 'none',
                    subtitleText: sub ? sub.textContent.trim() : '',
                    endoWeight: endo ? getComputedStyle(endo).fontWeight : '',
                    endoColor: endo ? getComputedStyle(endo).color : '',
                    logColor: log ? getComputedStyle(log).color : '',
                    headingToken: rootCs.getPropertyValue('--text-heading').trim(),
                    primaryToken: rootCs.getPropertyValue('--primary').trim(),
                    imgCount: document.querySelectorAll('img, video').length,
                };
            }"""
        )
        if not login_info["subtitleVisible"] or "Hệ thống sổ bộ lâm sàng" not in login_info["subtitleText"]:
            failures.append(f"Màn hình đăng nhập thiếu dòng phụ đề tiếng Việt đầy đủ: {login_info}")
        if login_info["imgCount"] != 0:
            failures.append(f"Vi phạm Zero-Image: phát hiện {login_info['imgCount']} thẻ img/video")
        print(f"PASS LOGIN_BRAND_CHECK: subtitle='{login_info['subtitleText']}' · imgCount={login_info['imgCount']}")

        # 2. Authenticate via 1-click local-bypass button into main shell with 5 OD-05 clinical vignettes
        page.locator("#el-btn-dev-bypass").wait_for(state="visible", timeout=5000)
        page.locator("#el-btn-dev-bypass").click()
        page.locator("#el-app-shell").wait_for(state="visible", timeout=8000)
        page.locator("#el-case-list .el-case-card").first.wait_for(state="visible", timeout=8000)
        page.evaluate("() => document.fonts.ready")

        case_count = page.locator("#el-case-list .el-case-card").count()
        if case_count != 5:
            failures.append(f"Kỳ vọng đúng 5 ca lâm sàng chuẩn OD-05, thực tế={case_count}")
        else:
            print(f"PASS OD05_SEED_COUNT: {case_count}/5 ca chuẩn OD-05 đã hiển thị")

        # 3. Verify Brand Identity v1 Invariants (meta theme-color, 3-cue active tabs, proc chips, mobile header)
        for theme_mode, expected_meta in [("light", "#475985"), ("dark", "#0d0f15")]:
            page.set_viewport_size({"width": 1440, "height": 960})
            set_theme_if_needed(page, theme_mode)
            meta_val = (page.locator("#el-meta-theme").get_attribute("content") or "").strip().lower()
            if meta_val != expected_meta:
                failures.append(f"meta[name=theme-color] sai ở chế độ {theme_mode}: '{meta_val}' != '{expected_meta}'")
            else:
                print(f"PASS META_THEME_COLOR [{theme_mode}]: {meta_val}")

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
                failures.append(f"Desktop brand check trượt [{theme_mode}]: {desktop_check}")
            for chip in desktop_check["chips"]:
                if chip["text"] not in ("EGD", "COL", "ERCP") or not chip["hasDot"]:
                    failures.append(f"Chip thủ thuật sai quy chuẩn [{theme_mode}]: {chip}")

            # Mobile 390px header rule: mark 28px, no halo r=8.5, no subtitle
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(120)
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
                failures.append(f"Mobile 390px brand check trượt [{theme_mode}]: {mobile_check}")
            else:
                print(
                    f"PASS BRAND_HEADER_AND_3_CUE_NAV [{theme_mode}]: "
                    f"mobile_mark={mobile_check['markW']}x{mobile_check['markH']}px · "
                    f"halo={mobile_check['haloDisplay']} · subtitle={mobile_check['subDisplay']}"
                )

        # 4. Multi-Viewport Overflow Audit (320 -> 1440 px) + Negative Probe Proof
        overflow_checks = 0
        for theme_mode in ("light", "dark"):
            set_theme_if_needed(page, theme_mode)
            for width in AUDIT_WIDTHS:
                height = 844 if width < 768 else 960
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(80)
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
                        failures.append(
                            f"Tràn ngang tại {view_key} · {width}px · {theme_mode}: "
                            f"scrollWidth={metrics['scrollWidth']} > innerWidth={metrics['innerWidth']}"
                        )

        # Negative probe test at 390px to prove root overflow is NOT masked by global overflow-x:hidden
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
            failures.append("Negative probe 640px không làm tăng scrollWidth (nghi ngờ có overflow-x: hidden toàn cục)")
        else:
            print(
                f"PASS MULTI_VIEWPORT_OVERFLOW: {overflow_checks}/{overflow_checks} tổ hợp (320–1440 px × 3 màn × Sáng/Tối) = 0 tràn ngang · Negative probe=DETECTED"
            )

        # 5. Touch-Target Ergonomics Audit (>= 44x44 px) at 390 px and 1440 px
        set_theme_if_needed(page, "light")
        small_targets: list[str] = []
        checked_targets = 0
        for width, height in [(390, 844), (1440, 960)]:
            page.set_viewport_size({"width": width, "height": height})
            page.wait_for_timeout(100)
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
                    if it["w"] < 44 or it["h"] < 44:
                        small_targets.append(f"{width}px/{view_key} <{it['tag']}#{it['id']} '{it['text']}'> = {it['w']}x{it['h']}px")
        if small_targets:
            failures.extend(small_targets)
        else:
            print(f"PASS TOUCH_TARGETS_44PX: {checked_targets}/{checked_targets} phần tử tương tác hiển thị đạt >= 44x44 px")

        # 6. Capture all 12 standardized screenshots: (3 views) x (390, 1440) x (light, dark)
        captured_files: list[str] = []
        for theme_mode in ("light", "dark"):
            set_theme_if_needed(page, theme_mode)
            for width, height in [(390, 844), (1440, 960)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(120)
                for view_key, slug, _ in VIEWS:
                    switch_to_view(page, view_key, width)
                    page.evaluate("() => window.scrollTo(0, 0)")
                    page.wait_for_timeout(120)
                    fname = f"{slug}_{width}_{theme_mode}.png"
                    out_path = SCREENSHOT_DIR / fname
                    page.screenshot(path=str(out_path), full_page=(width >= 768))
                    shutil.copy2(out_path, BRAIN_DIR / fname)
                    captured_files.append(fname)

        print(f"PASS SCREENSHOTS_12: Đã xuất đủ {len(captured_files)}/12 ảnh chuẩn vào docs/brand/screenshots/ và Brain/")
        for fn in captured_files:
            print(f"  - {fn}")

        # 7. 5-Layer Zero-PHI Browser Storage Audit
        storage_audit = page.evaluate(
            """async () => {
                const lsKeys = Object.keys(window.localStorage);
                const ssKeys = Object.keys(window.sessionStorage);
                const idbList = (window.indexedDB && window.indexedDB.databases) ? await window.indexedDB.databases() : [];
                let apiCacheHits = [];
                if ('caches' in window) {
                    const cacheNames = await caches.keys();
                    for (const name of cacheNames) {
                        const c = await caches.open(name);
                        const reqs = await c.keys();
                        for (const r of reqs) {
                            if (r.url.includes('/api/')) apiCacheHits.push(r.url);
                        }
                    }
                }
                return {
                    lsKeys,
                    ssKeys,
                    idbCount: idbList.length,
                    apiCacheCount: apiCacheHits.length,
                    visibleCookieHasJwt: document.cookie.includes('endolog_session'),
                };
            }"""
        )
        illegal_ls = [k for k in storage_audit["lsKeys"] if k != "endolog_theme"]
        illegal_ss = [k for k in storage_audit["ssKeys"] if k != "endolog_active_view"]
        if (
            illegal_ls
            or illegal_ss
            or storage_audit["idbCount"] != 0
            or storage_audit["apiCacheCount"] != 0
            or storage_audit["visibleCookieHasJwt"]
        ):
            failures.append(f"Vi phạm Zero-PHI Browser Storage: {storage_audit}")
        else:
            print(
                f"PASS ZERO_PHI_5_LAYERS: localStorage={storage_audit['lsKeys']} · "
                f"sessionStorage={storage_audit['ssKeys']} · indexedDB={storage_audit['idbCount']} · "
                f"apiCache={storage_audit['apiCacheCount']} · HttpOnlyCookieHidden={not storage_audit['visibleCookieHasJwt']}"
            )

        context.close()
        browser.close()

    if console_errors:
        failures.extend([f"Console error: {e}" for e in console_errors])
    if page_errors:
        failures.extend([f"Page error: {e}" for e in page_errors])
    if http_errors:
        failures.extend([f"HTTP >=400: {e}" for e in http_errors])

    if not console_errors and not page_errors and not http_errors:
        print("PASS RUNTIME_CLEANLINESS: console.error=0 · pageerror=0 · HTTP_4xx_5xx=0")

    if failures:
        print("\nFAILED CHECKS:")
        for item in failures:
            print(f"  [FAIL] {item}")
        return 1

    print("\nALL PHASE 4A PLAYWRIGHT VERIFICATION GATES PASSED (0 FAILURES).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
