#!/usr/bin/env python3
"""Gate C Clean-Room & GitHub Pages Artifact Security Verifier (Phương án G1 / G06).

Verifies all 3 mandatory pre-publish boundaries from Section 4.B.3 of the approved plan:
  (a) Tracked files (`git ls-files`): 0 data*/, backups*/, dist_pages/, *.enc, .env*, keys, DBs, or caches.
  (b) Full Git history (`git log --all` + `gitleaks git`): 0 historical PHI/vault/secret commits.
  (c) Static Pages bundle (`dist_pages/` + `gitleaks dir`):
      - Required files (.nojekyll, index.html, manifest.json, sw-demo.js, precomputed OD-05 bundle, assets)
      - 0 input[type="password"] and 0 input[type="file"]
      - 0 broken label[for] references in dist_pages/index.html
      - Exact Vietnamese showcase warning banner text
      - Subpath-scoped manifest (/endolog/) & prefix-safe sw-demo.js ('endolog-ghpages-demo-')
      - Design System v1 immutability (0 hardcoded #hex/rgb/hsl/named colors, 0 emojis, 0 Google Fonts)
      - Precomputed bundle strictly limited to the 5 OD-05 synthetic cases with masked SYN-*** MRNs & 0 hashes
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from endolog.core.dlp import DlpViolationError, scan_payload_notes  # noqa: E402
from tools.build_gh_pages_demo import SHOWCASE_BANNER_TEXT_VI  # noqa: E402

NAMED_CSS_COLORS = (
    "aliceblue", "antiquewhite", "aqua", "aquamarine", "azure", "beige", "bisque", "black",
    "blanchedalmond", "blue", "blueviolet", "brown", "burlywood", "cadetblue", "chartreuse",
    "chocolate", "coral", "cornflowerblue", "cornsilk", "crimson", "cyan", "darkblue", "darkcyan",
    "darkgoldenrod", "darkgray", "darkgreen", "darkgrey", "darkkhaki", "darkmagenta", "darkolivegreen",
    "darkorange", "darkorchid", "darkred", "darksalmon", "darkseagreen", "darkslateblue",
    "darkslategray", "darkslategrey", "darkturquoise", "darkviolet", "deeppink", "deepskyblue",
    "dimgray", "dimgrey", "dodgerblue", "firebrick", "floralwhite", "forestgreen", "fuchsia",
    "gainsboro", "ghostwhite", "gold", "goldenrod", "gray", "green", "greenyellow", "grey",
    "honeydew", "hotpink", "indianred", "indigo", "ivory", "khaki", "lavender", "lavenderblush",
    "lawngreen", "lemonchiffon", "lightblue", "lightcoral", "lightcyan", "lightgoldenrodyellow",
    "lightgray", "lightgreen", "lightgrey", "lightpink", "lightsalmon", "lightseagreen",
    "lightskyblue", "lightslategray", "lightslategrey", "lightsteelblue", "lightyellow", "lime",
    "limegreen", "linen", "magenta", "maroon", "mediumaquamarine", "mediumblue", "mediumorchid",
    "mediumpurple", "mediumseagreen", "mediumslateblue", "mediumspringgreen", "mediumturquoise",
    "mediumvioletred", "midnightblue", "mintcream", "mistyrose", "moccasin", "navajowhite", "navy",
    "oldlace", "olive", "olivedrab", "orange", "orangered", "orchid", "palegoldenrod", "palegreen",
    "paleturquoise", "palevioletred", "papayawhip", "peachpuff", "peru", "pink", "plum",
    "powderblue", "purple", "rebeccapurple", "red", "rosybrown", "royalblue", "saddlebrown",
    "salmon", "sandybrown", "seagreen", "seashell", "sienna", "silver", "skyblue", "slateblue",
    "slategray", "slategrey", "snow", "springgreen", "steelblue", "tan", "teal", "thistle",
    "tomato", "turquoise", "violet", "wheat", "white", "whitesmoke", "yellow", "yellowgreen",
)

FORBIDDEN_GIT_PATH_PATTERNS = (
    re.compile(r"^data(?:_[^/]*)?/"),
    re.compile(r"^backups(?:_[^/]*)?/"),
    re.compile(r"^02_DuLieu_Tho/"),
    re.compile(r"^03_ThongKe/"),
    re.compile(r"^dist_pages/"),
    re.compile(r"(?:^|/)\.env(?:\..+)?$"),
    re.compile(r"\.(?:enc|db|sqlite|sqlite3|pem|key|p12|pfx|pyc|xlsx|xls|csv|parquet|arrow|dcm)$", re.I),
    re.compile(r"(?:^|/)\.phi_vault_marker$"),
    re.compile(r"(?:^|/)pre_restore_[^/]+\.json$"),
    re.compile(r"(?:^|/)__pycache__/"),
    re.compile(r"(?:^|/)\.pytest_cache/"),
)

PROFILE_A_CIPHERTEXT_ENVELOPE_RE = re.compile(
    r'(?:"contract"\s*:\s*"EndoLog-Export-Profile-A-v[0-9.]+"[\s\S]{0,360}?"ciphertext_hex"\s*:\s*"[0-9a-fA-F]{64,}"'
    r'|"ciphertext_hex"\s*:\s*"[0-9a-fA-F]{64,}"[\s\S]{0,360}?"contract"\s*:\s*"EndoLog-Export-Profile-A-v[0-9.]+")'
)

EXPECTED_OD05_CASE_CODES = {
    "COL-2026-0001",
    "COL-2026-0002",
    "EGD-2026-0001",
    "EGD-2026-0002",
    "ERCP-2026-0001",
}

EXPECTED_OD05_MASKED_MRNS = {
    "***2601",
    "***2602",
    "***2603",
    "***2604",
    "***2605",
}


def _find_gitleaks_bin() -> str | None:
    found = shutil.which("gitleaks")
    if found:
        return found
    brew_candidate = Path("/opt/homebrew/bin/gitleaks")
    if brew_candidate.is_file():
        return str(brew_candidate)
    return None


def verify_git_clean_room(repo_root: Path, *, require_gitleaks: bool = False) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []

    # 1. Active tracked files (`git -c core.quotepath=false ls-files -z` — unquoted UTF-8 for Vietnamese filenames)
    ls_proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files", "-z"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if ls_proc.returncode != 0:
        errors.append(f"git ls-files thất bại: {ls_proc.stderr.strip()}")
        tracked_files: list[str] = []
    else:
        tracked_files = [entry for entry in ls_proc.stdout.split("\0") if entry]

    for rel_path in tracked_files:
        if rel_path.endswith(".env.example"):
            continue
        for pat in FORBIDDEN_GIT_PATH_PATTERNS:
            if pat.search(rel_path):
                errors.append(f"[git ls-files] Tệp bị cấm xuất hiện trong kho theo dõi: {rel_path}")
                break

    # 2. Historical file paths across ALL commits (`git -c core.quotepath=false log --all --name-only -z`)
    hist_names_proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "log", "--all", "--pretty=format:", "--name-only", "-z"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if hist_names_proc.returncode != 0:
        errors.append(f"git log --name-only thất bại: {hist_names_proc.stderr.strip()}")
        historical_paths: set[str] = set()
    else:
        historical_paths = {entry.lstrip("\n\r") for entry in hist_names_proc.stdout.split("\0") if entry.strip()}

    for rel_path in sorted(historical_paths):
        if rel_path.endswith(".env.example"):
            continue
        for pat in FORBIDDEN_GIT_PATH_PATTERNS:
            if pat.search(rel_path):
                errors.append(f"[git history] Tệp nhạy cảm/tạm từng xuất hiện trong lịch sử commit: {rel_path}")
                break

    # 3. Full patch scan (`git log -p --all`) for raw private keys / tokens / Profile A ciphertext blobs
    patch_proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "log", "-p", "--all"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if patch_proc.returncode != 0:
        errors.append(f"git log -p --all thất bại: {patch_proc.stderr.strip()}")
        patch_text = ""
    else:
        patch_text = patch_proc.stdout

    high_risk_history_patterns = [
        ("PRIVATE_KEY_PEM", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("GITHUB_PAT", re.compile(r"\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,})\b")),
        ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
        ("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{20,}\b")),
        ("PROFILE_A_CIPHERTEXT_ENVELOPE", PROFILE_A_CIPHERTEXT_ENVELOPE_RE),
    ]
    for code, pat in high_risk_history_patterns:
        if pat.search(patch_text):
            errors.append(f"[git log -p --all] Phát hiện mẫu khóa bí mật '{code}' trong lịch sử Git")

    # 4. Gitleaks full history scan
    gitleaks_bin = _find_gitleaks_bin()
    gitleaks_ran = False
    if gitleaks_bin:
        gitleaks_ran = True
        cfg_args = ["--config", str(repo_root / ".gitleaks.toml")] if (repo_root / ".gitleaks.toml").exists() else []
        gl_proc = subprocess.run(
            [gitleaks_bin, "git", "--no-banner", *cfg_args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if gl_proc.returncode != 0:
            errors.append(f"[gitleaks git] Phát hiện nghi vấn rò rỉ bí mật: {(gl_proc.stdout + gl_proc.stderr).strip()}")
    elif require_gitleaks:
        errors.append("Không tìm thấy công cụ gitleaks khi chạy với cờ --require-gitleaks.")

    return errors, {
        "tracked_file_count": len(tracked_files),
        "historical_unique_paths": len(historical_paths),
        "gitleaks_git_scanned": gitleaks_ran,
    }


def verify_dist_pages_bundle(
    dist_dir: Path,
    *,
    base_path: str = "/EndoLog/",
    require_gitleaks: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    dist = dist_dir.resolve()
    if not dist.is_dir():
        return [f"Thư mục xuất bản tĩnh không tồn tại: {dist}"], {}

    required_rel_files = (
        ".nojekyll",
        "index.html",
        "manifest.json",
        "sw-demo.js",
        "css/tokens.css",
        "css/fonts.css",
        "css/app.css",
        "css/demo-showcase.css",
        "js/demo-synthetic-adapter.js",
        "js/app.js",
        "data/od05_precomputed_bundle.json",
        "icons/favicon.svg",
    )
    for rel in required_rel_files:
        if not (dist / rel).is_file():
            errors.append(f"[dist_pages] Thiếu tệp bắt buộc: {rel}")

    if errors:
        return errors, {}

    all_files = sorted(p for p in dist.rglob("*") if p.is_file())
    for p in all_files:
        rel = str(p.relative_to(dist))
        if p.name == "sw.js":
            errors.append("[dist_pages] Không được chứa sw.js phạm vi gốc '/' (phải dùng sw-demo.js).")
        if (
            re.search(r"\.(?:enc|db|sqlite|sqlite3|pem|key|p12|pfx|pyc|xlsx|xls|csv|parquet|arrow|dcm)$", rel, re.I)
            or ".phi_vault_marker" in rel
            or "pre_restore_" in rel
        ):
            errors.append(f"[dist_pages] Tệp nhạy cảm/cấm xuất hiện trong gói tĩnh: {rel}")
        try:
            raw_txt_probe = p.read_text(encoding="utf-8", errors="ignore")
            if PROFILE_A_CIPHERTEXT_ENVELOPE_RE.search(raw_txt_probe):
                errors.append(f"[dist_pages/{rel}] Phát hiện phong bì mã hóa Hồ sơ A (Profile A vault ciphertext)!")
        except OSError:
            pass

    # JS syntax check with node --check if available
    node_bin = shutil.which("node")
    if node_bin:
        for js_rel in ("js/demo-synthetic-adapter.js", "js/app.js", "sw-demo.js"):
            n_proc = subprocess.run([node_bin, "--check", str(dist / js_rel)], capture_output=True, text=True)
            if n_proc.returncode != 0:
                errors.append(f"[node --check] Lỗi cú pháp JS trong {js_rel}: {n_proc.stderr.strip()}")

    # HTML security & Zero-PHI input checks
    html_text = (dist / "index.html").read_text(encoding="utf-8")
    if re.search(r'<input\b[^>]*\btype\s*=\s*["\']password["\']', html_text, flags=re.I):
        errors.append("[dist_pages/index.html] Vẫn còn thẻ input[type=password]!")
    if re.search(r'<input\b[^>]*\btype\s*=\s*["\']file["\']', html_text, flags=re.I):
        errors.append("[dist_pages/index.html] Vẫn còn thẻ input[type=file]!")
    if SHOWCASE_BANNER_TEXT_VI not in html_text:
        errors.append("[dist_pages/index.html] Thiếu nguyên văn thông điệp cảnh báo đầu trang chuẩn Mục 4.B.1.")
    for ro_id in (
        "el-f-full-name",
        "el-f-hospital-mrn",
        "el-f-operator",
        "el-admin-merge-reason",
        "el-admin-reconcile-reason",
    ):
        tag_m = re.search(rf'<input\b[^>]*\bid="{ro_id}"[^>]*>', html_text)
        if not tag_m or not re.search(r"\breadonly\b", tag_m.group(0), flags=re.I):
            errors.append(f"[dist_pages/index.html] Ô nhập #{ro_id} chưa được khóa readonly bảo vệ Zero-PHI.")

    # Verify every <label for="..."> in dist_pages/index.html resolves to an existing id="..."
    present_ids = set(re.findall(r'\bid="([^"]+)"', html_text))
    for target_for in re.findall(r'<label\b[^>]*\bfor="([^"]+)"', html_text):
        if target_for not in present_ids:
            errors.append(f"[dist_pages/index.html] Nhãn <label for='{target_for}'> trỏ tới id đã gỡ hoặc không tồn tại.")

    # Verify asset paths in index.html do not point to root /css/, /js/, /icons/, /manifest.json
    for root_asset in ('href="/css/', 'src="/js/', 'href="/icons/', 'href="/manifest.json"'):
        if root_asset in html_text:
            errors.append(f"[dist_pages/index.html] Vẫn còn đường dẫn gốc chưa chuyển sang {base_path}: {root_asset}")

    # Verify manifest.json subpath scope
    manifest = json.loads((dist / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("start_url") != base_path or manifest.get("scope") != base_path:
        errors.append(
            f"[dist_pages/manifest.json] start_url/scope không khớp {base_path}: "
            f"start_url={manifest.get('start_url')!r}, scope={manifest.get('scope')!r}"
        )
    for icon in manifest.get("icons", []):
        if not str(icon.get("src", "")).startswith(f"{base_path}icons/"):
            errors.append(f"[dist_pages/manifest.json] Đường dẫn icon chưa trỏ vào {base_path}icons/: {icon}")

    # Verify sw-demo.js prefix isolation for shared github.io origin
    sw_text = (dist / "sw-demo.js").read_text(encoding="utf-8")
    if '"endolog-ghpages-demo-"' not in sw_text:
        errors.append("[dist_pages/sw-demo.js] Thiếu tiền tố khóa cache riêng 'endolog-ghpages-demo-'.")
    if "startsWith(CACHE_PREFIX)" not in sw_text:
        errors.append("[dist_pages/sw-demo.js] Hàm dọn cache activate chưa giới hạn theo CACHE_PREFIX (nguy cơ xóa nhầm Idea Agent).")
    if json.dumps(base_path) not in sw_text:
        errors.append(f"[dist_pages/sw-demo.js] Thiếu kiểm tra BASE_PATH {base_path}.")

    # Verify Design System v1 color, emoji, and Google Fonts immutability across dist_pages
    color_fn_pat = re.compile(r"(#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(|\boklch\s*\(|\boklab\s*\()", re.I)
    named_css_pat = re.compile(
        r":\s*(?:[0-9.]+px\s+[a-z]+\s+)?(" + "|".join(NAMED_CSS_COLORS) + r")\b",
        re.I,
    )
    emoji_pat = re.compile(r"[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")
    gfont_pat = re.compile(r"(fonts\.googleapis\.com|fonts\.gstatic\.com)", re.I)

    for p in all_files:
        if p.suffix not in {".html", ".css", ".js", ".json", ".svg"}:
            continue
        rel = str(p.relative_to(dist))
        txt = p.read_text(encoding="utf-8")
        if p.suffix in {".html", ".css", ".js"} and p.name != "tokens.css":
            c_hits = color_fn_pat.findall(txt)
            if c_hits:
                errors.append(f"[dist_pages/{rel}] Phát hiện mã màu/hàm màu cứng ngoài tokens.css: {c_hits[:3]}")
        if p.suffix == ".css" and p.name != "tokens.css":
            nc_hits = named_css_pat.findall(txt)
            if nc_hits:
                errors.append(f"[dist_pages/{rel}] Phát hiện từ khóa màu CSS đặt tên: {nc_hits[:3]}")
        if emoji_pat.search(txt):
            errors.append(f"[dist_pages/{rel}] Phát hiện ký tự emoji trái quy chuẩn Design System v1.")
        if gfont_pat.search(txt):
            errors.append(f"[dist_pages/{rel}] Phát hiện liên kết Google Fonts bên ngoài.")

    # Verify precomputed OD-05 bundle integrity & Zero-PHI invariants
    bundle_raw = (dist / "data" / "od05_precomputed_bundle.json").read_text(encoding="utf-8")
    bundle = json.loads(bundle_raw)
    for forbidden_tok in ("password_hash", "hospital_mrn_hash", "secondary_mrn_hashes", "argon2id$", "jwt_secret", "Bearer "):
        if forbidden_tok in bundle_raw:
            errors.append(f"[od05_precomputed_bundle.json] Rò rỉ chuỗi nhạy cảm '{forbidden_tok}'.")

    cases_items = (bundle.get("cases_response") or {}).get("items") or []
    case_codes = {str(c.get("case_code")) for c in cases_items}
    if case_codes != EXPECTED_OD05_CASE_CODES:
        errors.append(f"[od05_precomputed_bundle.json] Tập mã ca khác 5 ca chuẩn OD-05: {sorted(case_codes)}")

    admin_pats = (bundle.get("admin_patients_response") or {}).get("items") or []
    masked_mrns = {str(p.get("hospital_mrn_masked")) for p in admin_pats}
    if masked_mrns != EXPECTED_OD05_MASKED_MRNS:
        errors.append(f"[od05_precomputed_bundle.json] Mã hồ sơ ẩn danh khác chuẩn SYN-*** OD-05: {sorted(masked_mrns)}")

    for c in cases_items:
        try:
            scan_payload_notes(
                {
                    "clinical_note": c.get("clinical_note") or "",
                    "clinician_followup_note": c.get("clinician_followup_note") or "",
                }
            )
        except DlpViolationError as exc:
            errors.append(f"[od05_precomputed_bundle.json] Ghi chú ca mẫu vi phạm bộ quét DLP: {exc}")

    # Gitleaks directory scan on dist_pages/
    gitleaks_bin = _find_gitleaks_bin()
    gitleaks_dir_scanned = False
    if gitleaks_bin:
        gitleaks_dir_scanned = True
        cfg_args = ["--config", str(REPO_ROOT / ".gitleaks.toml")] if (REPO_ROOT / ".gitleaks.toml").exists() else []
        gl_proc = subprocess.run(
            [gitleaks_bin, "dir", str(dist), "--no-banner", *cfg_args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if gl_proc.returncode != 0:
            errors.append(f"[gitleaks dir dist_pages] Phát hiện nghi vấn bí mật: {(gl_proc.stdout + gl_proc.stderr).strip()}")
    elif require_gitleaks:
        errors.append("Không tìm thấy công cụ gitleaks khi chạy với cờ --require-gitleaks.")

    return errors, {
        "dist_file_count": len(all_files),
        "od05_case_count": len(cases_items),
        "password_or_file_inputs": 0,
        "gitleaks_dir_scanned": gitleaks_dir_scanned,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Gate C Clean-Room Git History & dist_pages/ Bundle.")
    parser.add_argument("--check-git", action="store_true", help="Check git ls-files + full git log + gitleaks git.")
    parser.add_argument("--check-dist", action="store_true", help="Check dist_pages/ static bundle + gitleaks dir.")
    parser.add_argument("--dist-dir", default=str(REPO_ROOT / "dist_pages"), help="Path to built Pages bundle.")
    parser.add_argument("--base-path", default="/EndoLog/", help="Expected Pages subpath (default: /EndoLog/).")
    parser.add_argument("--require-gitleaks", action="store_true", help="Fail if gitleaks binary is not installed.")
    args = parser.parse_args()

    run_git = args.check_git or (not args.check_git and not args.check_dist)
    run_dist = args.check_dist or (not args.check_git and not args.check_dist)

    all_errors: list[str] = []
    report: dict[str, Any] = {}

    if run_git:
        git_errs, git_metrics = verify_git_clean_room(REPO_ROOT, require_gitleaks=args.require_gitleaks)
        all_errors.extend(git_errs)
        report["git_clean_room"] = git_metrics

    if run_dist:
        dist_errs, dist_metrics = verify_dist_pages_bundle(
            Path(args.dist_dir),
            base_path=args.base_path,
            require_gitleaks=args.require_gitleaks,
        )
        all_errors.extend(dist_errs)
        report["dist_pages_bundle"] = dist_metrics

    if all_errors:
        print("GATE_C_CLEAN_ROOM_FAILED:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"GATE_C_CLEAN_ROOM_OK: {json.dumps(report, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
