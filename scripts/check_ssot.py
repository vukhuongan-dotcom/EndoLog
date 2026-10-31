#!/usr/bin/env python3
"""EndoLog SSoT & Version Synchronization Verifier (Rule v2:R45 & Synchronous Change Principle).

Checks:
1. Exact version synchronization across pyproject.toml, src/endolog/__init__.py,
   src/endolog/static/index.html (?v=...), src/endolog/static/sw.js (CACHE_NAME & ?v=...),
   and version.md (latest ## [x.y.z] release header).
2. Byte-for-byte SHA-256 identity (and non-symlink independence) between
   docs/BUG_FIX_REGISTRY.md and PROJECT_CONTEXT/BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md.
3. SSoT status honesty: zero VERIFIED_CLOSED rows with PENDING / missing approver or empty evidence.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []

    pyproject_txt = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m_pyproj = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_txt, re.M)
    v_pyproj = m_pyproj.group(1) if m_pyproj else None

    init_txt = (REPO_ROOT / "src" / "endolog" / "__init__.py").read_text(encoding="utf-8")
    m_init = re.search(r'^__version__\s*=\s*"([^"]+)"', init_txt, re.M)
    v_init = m_init.group(1) if m_init else None

    html_txt = (REPO_ROOT / "src" / "endolog" / "static" / "index.html").read_text(encoding="utf-8")
    html_vers = sorted(set(re.findall(r"\?v=([0-9A-Za-z.\-]+)", html_txt)))

    sw_txt = (REPO_ROOT / "src" / "endolog" / "static" / "sw.js").read_text(encoding="utf-8")
    m_sw_cache = re.search(r"CACHE_NAME\s*=\s*'endolog-static-v([^']+)'", sw_txt)
    v_sw_cache = m_sw_cache.group(1) if m_sw_cache else None
    sw_asset_vers = sorted(set(re.findall(r"\?v=([0-9A-Za-z.\-]+)", sw_txt)))

    ver_md_txt = (REPO_ROOT / "version.md").read_text(encoding="utf-8")
    m_ver_md = re.search(r"^##\s*\[([0-9]+\.[0-9]+\.[0-9]+[^\]]*)\]", ver_md_txt, re.M)
    v_ver_md = m_ver_md.group(1) if m_ver_md else None

    if not v_pyproj:
        errors.append("Không tìm thấy version trong pyproject.toml")
    if v_init != v_pyproj:
        errors.append(f"Lệch phiên bản __init__.py ({v_init}) vs pyproject.toml ({v_pyproj})")
    if html_vers != [v_pyproj]:
        errors.append(f"Lệch ?v= trong index.html ({html_vers}) vs pyproject.toml ({v_pyproj})")
    if v_sw_cache != v_pyproj or sw_asset_vers != [v_pyproj]:
        errors.append(
            f"Lệch phiên bản sw.js (CACHE_NAME={v_sw_cache}, assets={sw_asset_vers}) vs pyproject.toml ({v_pyproj})"
        )
    if v_ver_md != v_pyproj:
        errors.append(f"Lệch phiên bản mới nhất trong version.md ({v_ver_md}) vs pyproject.toml ({v_pyproj})")

    reg_a = REPO_ROOT / "docs" / "BUG_FIX_REGISTRY.md"
    reg_b = REPO_ROOT / "PROJECT_CONTEXT" / "BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md"
    if not reg_a.exists() or not reg_b.exists():
        errors.append("Thiếu một trong hai tệp Dual SSoT BUG_FIX_REGISTRY")
    else:
        if reg_a.is_symlink() or reg_b.is_symlink():
            errors.append("Vi phạm Dual SSoT: Cấm dùng symlink giữa docs/BUG_FIX_REGISTRY.md và PROJECT_CONTEXT/")
        sha_a = _sha256(reg_a)
        sha_b = _sha256(reg_b)
        if sha_a != sha_b:
            errors.append(f"Lệch SHA-256 Dual SSoT: {sha_a} != {sha_b}")

        # Verify Schema v3.1 row honesty & counts
        txt = reg_a.read_text(encoding="utf-8")
        table_rows = [
            ln for ln in txt.splitlines()
            if ln.startswith("| ") and not ln.startswith("| STT |") and not ln.startswith("|:---:")
        ]
        closed_count = 0
        pending_count = 0
        open_count = 0
        for row in table_rows:
            cols = [c.strip() for c in row.strip("|").split("|")]
            if len(cols) != 14:
                errors.append(f"Dòng SSoT không đủ 14 cột Schema v3.1 ({len(cols)} cột): {cols[:2]}")
                continue
            inc_id = cols[1]
            status = cols[10].strip("` ")
            evidence = cols[11]
            approver = cols[13]
            if status == "VERIFIED_CLOSED":
                closed_count += 1
                if not evidence or evidence in ("-", "N/A"):
                    errors.append(f"{inc_id} ở trạng thái VERIFIED_CLOSED nhưng thiếu evidence_refs")
                if "PENDING" in approver.upper() or not approver or approver == "-":
                    errors.append(f"{inc_id} ở trạng thái VERIFIED_CLOSED nhưng cột Ngày đóng & Người duyệt còn PENDING")
            elif status == "FIXED_PENDING_VERIFY":
                pending_count += 1
            elif status == "OPEN":
                open_count += 1

        m_total = re.search(r"\*\*Tổng số sự cố & tính năng ghi nhận:\*\*\s*(\d+)", txt)
        m_fpv = re.search(r"\(`FIXED_PENDING_VERIFY`\):\*\*\s*(\d+)", txt)
        m_vc = re.search(r"\(`VERIFIED_CLOSED`\):\*\*\s*(\d+)", txt)
        if m_total and int(m_total.group(1)) != len(table_rows):
            errors.append(f"Thống kê tổng số ({m_total.group(1)}) != số dòng thực tế ({len(table_rows)})")
        if m_fpv and int(m_fpv.group(1)) != pending_count:
            errors.append(f"Thống kê FIXED_PENDING_VERIFY ({m_fpv.group(1)}) != thực tế ({pending_count})")
        if m_vc and int(m_vc.group(1)) != closed_count:
            errors.append(f"Thống kê VERIFIED_CLOSED ({m_vc.group(1)}) != thực tế ({closed_count})")

    if errors:
        print("SSOT_CHECK_FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"SSOT_CHECK_OK: version={v_pyproj} · dual_ssot_sha256={_sha256(reg_a)} · "
        f"rows={len(table_rows)} (VERIFIED_CLOSED={closed_count}, FIXED_PENDING_VERIFY={pending_count}, OPEN={open_count})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
