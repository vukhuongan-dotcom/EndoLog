#!/usr/bin/env python3
"""Kiểm toán tương phản WCAG 2.1 trực tiếp từ src/endolog/static/css/tokens.css (Phương án B · Chàm khói).

Đo đủ 31 cặp ngữ nghĩa × 2 chế độ (Sáng + Tối) = 62 cặp:
- Mọi cặp chữ / nền >= 4.5:1
- Chữ trắng (--on-primary) trên --primary-fill >= 4.5:1 ở cả sáng và tối
- Viền ô nhập (--border-strong), vòng focus (--focus-ring), chấm thủ thuật (--proc-*) >= 3.0:1
Thoát mã 1 nếu có bất kỳ cặp nào trượt.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TEXT_MIN = 4.5
UI_MIN = 3.0

PAIRS: list[tuple[str, str, float, str]] = [
    # 1-9: Hệ chữ trên 3 tầng nền (9 cặp)
    ("--text-heading", "--bg-main", TEXT_MIN, "Tiêu đề / nền trang"),
    ("--text-heading", "--bg-card", TEXT_MIN, "Tiêu đề / nền thẻ"),
    ("--text-heading", "--bg-sunken", TEXT_MIN, "Tiêu đề / vùng lõm"),
    ("--text-main", "--bg-main", TEXT_MIN, "Chữ chính & mã ca / nền trang"),
    ("--text-main", "--bg-card", TEXT_MIN, "Chữ chính & mã ca / nền thẻ"),
    ("--text-main", "--bg-sunken", TEXT_MIN, "Chữ chính & mã ca / vùng lõm"),
    ("--text-muted", "--bg-main", TEXT_MIN, "Chữ phụ / nền trang"),
    ("--text-muted", "--bg-card", TEXT_MIN, "Chữ phụ / nền thẻ"),
    ("--text-muted", "--bg-sunken", TEXT_MIN, "Chữ phụ / vùng lõm"),
    # 10-13: Màu nhấn thương hiệu & nút hành động chính (4 cặp)
    ("--primary", "--bg-main", TEXT_MIN, "Chữ primary (tab, Log) / nền trang"),
    ("--primary", "--bg-card", TEXT_MIN, "Chữ primary (tab, Log) / nền thẻ"),
    ("--primary", "--primary-soft", TEXT_MIN, "Chữ primary / nền primary-soft"),
    ("--on-primary", "--primary-fill", TEXT_MIN, "Chữ trắng trên nút chính (--primary-fill)"),
    # 14-17: Viền ô nhập & vòng focus bàn phím SC 1.4.11 (4 cặp)
    ("--border-strong", "--bg-main", UI_MIN, "Viền ô nhập / nền trang"),
    ("--border-strong", "--bg-card", UI_MIN, "Viền ô nhập / nền thẻ"),
    ("--focus-ring", "--bg-main", UI_MIN, "Vòng focus / nền trang"),
    ("--focus-ring", "--bg-card", UI_MIN, "Vòng focus / nền thẻ"),
    # 18-26: Chip & chấm 7 px của 3 phân hệ thủ thuật EGD / COL / ERCP (9 cặp)
    ("--proc-egd-text", "--proc-egd-tint", TEXT_MIN, "Chữ chip EGD / nền chip EGD"),
    ("--proc-egd", "--proc-egd-tint", UI_MIN, "Chấm 7px EGD / nền chip EGD"),
    ("--proc-egd", "--bg-card", UI_MIN, "Chấm 7px EGD / nền thẻ"),
    ("--proc-col-text", "--proc-col-tint", TEXT_MIN, "Chữ chip COL / nền chip COL"),
    ("--proc-col", "--proc-col-tint", UI_MIN, "Chấm 7px COL / nền chip COL"),
    ("--proc-col", "--bg-card", UI_MIN, "Chấm 7px COL / nền thẻ"),
    ("--proc-ercp-text", "--proc-ercp-tint", TEXT_MIN, "Chữ chip ERCP / nền chip ERCP"),
    ("--proc-ercp", "--proc-ercp-tint", UI_MIN, "Chấm 7px ERCP / nền chip ERCP"),
    ("--proc-ercp", "--bg-card", UI_MIN, "Chấm 7px ERCP / nền thẻ"),
    # 27-31: 5 trạng thái lâm sàng chuẩn trên nền thẻ (5 cặp)
    ("--clinical-ned", "--bg-card", TEXT_MIN, "Trạng thái Không biến cố (ned) / nền thẻ"),
    ("--clinical-due", "--bg-card", TEXT_MIN, "Trạng thái Đến hạn soi lại (due) / nền thẻ"),
    ("--clinical-pending", "--bg-card", TEXT_MIN, "Trạng thái Chờ GPB (pending) / nền thẻ"),
    ("--clinical-urgent", "--bg-card", TEXT_MIN, "Trạng thái Cảnh báo Ngoại & biến cố (urgent) / nền thẻ"),
    ("--clinical-neutral", "--bg-card", TEXT_MIN, "Trạng thái Mất dấu & chưa đến hạn (neutral) / nền thẻ"),
]


def _find_tokens_css(cli_arg: str | None) -> Path:
    if cli_arg:
        return Path(cli_arg).resolve()
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "src" / "endolog" / "static" / "css" / "tokens.css"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Không tìm thấy src/endolog/static/css/tokens.css")


def parse_tokens_css(css_path: Path) -> dict[str, dict[str, str]]:
    text = css_path.read_text(encoding="utf-8")
    text_no_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    root_match = re.search(r":root\s*\{([^}]*)\}", text_no_comments)
    dark_match = re.search(r'\[data-theme="dark"\]\s*\{([^}]*)\}', text_no_comments)
    if not root_match or not dark_match:
        raise ValueError("tokens.css thiếu khối :root hoặc [data-theme=\"dark\"].")

    def _extract_vars(block: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for m in re.finditer(r"(--[a-zA-Z0-9-]+)\s*:\s*([^;]+);", block):
            out[m.group(1).strip()] = m.group(2).strip()
        return out

    light_raw = _extract_vars(root_match.group(1))
    dark_raw = {**light_raw, **_extract_vars(dark_match.group(1))}

    def _resolve_all(raw_map: dict[str, str]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for k, v in raw_map.items():
            cur = v
            for _ in range(5):
                vm = re.fullmatch(r"var\((--[a-zA-Z0-9-]+)\)", cur)
                if not vm:
                    break
                cur = raw_map.get(vm.group(1), cur)
            resolved[k] = cur
        return resolved

    return {"light": _resolve_all(light_raw), "dark": _resolve_all(dark_raw)}


def rel_luminance(hex_code: str) -> float:
    h = hex_code.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        raise ValueError(f"Mã màu không phải hex 6 ký tự: {hex_code}")
    channels = []
    for idx in (0, 2, 4):
        c = int(h[idx : idx + 2], 16) / 255.0
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = rel_luminance(fg_hex)
    l2 = rel_luminance(bg_hex)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def main() -> int:
    css_path = _find_tokens_css(sys.argv[1] if len(sys.argv) > 1 else None)
    themes = parse_tokens_css(css_path)
    total = 0
    passed = 0
    failed = 0

    print(f"Nguồn đọc trực tiếp: {css_path}")
    print(f"{'TT':<4} {'Chế độ':<6} {'Tỷ lệ':>8} {'Ngưỡng':>7}  {'FG / BG':<19} {'Cặp token & Vai trò'}")
    print("-" * 102)

    for mode_key, mode_label in [("light", "SÁNG"), ("dark", "TỐI")]:
        tmap = themes[mode_key]
        for fg_tok, bg_tok, min_req, desc in PAIRS:
            fg_hex = tmap[fg_tok]
            bg_hex = tmap[bg_tok]
            ratio = contrast_ratio(fg_hex, bg_hex)
            ok = ratio >= min_req
            total += 1
            if ok:
                passed += 1
            else:
                failed += 1
            status = "PASS" if ok else "FAIL"
            print(
                f"{status:<4} {mode_label:<6} {ratio:>6.2f}:1  >={min_req:<4.1f}  "
                f"{fg_hex} / {bg_hex}  {fg_tok} on {bg_tok} — {desc}"
            )

    print("-" * 102)
    print(f"KẾT QUẢ KIỂM CHỨNG: {passed}/{total} cặp đạt (Sáng + Tối) · Số cặp trượt: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
