"""Automated Gate C (Phương án G1 / G06) tests for the GitHub Pages Showcase-Only Synthetic Sandbox."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from endolog import __version__
from endolog.clinical.cusum import build_cusum_series_from_cases
from endolog.clinical.export_profiles import export_profile_a_encrypted_vault
from endolog.clinical.quality_metrics import compute_kpi_snapshot
from endolog.main import STATIC_DIR
from tools.build_gh_pages_demo import SHOWCASE_BANNER_TEXT_VI, build_gh_pages_demo
from tools.verify_gate_c_clean_room import verify_dist_pages_bundle, verify_git_clean_room

REPO_ROOT = Path(__file__).resolve().parents[1]


def _hash_tree(directory: Path) -> dict[str, str]:
    digest_map: dict[str, str] = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(directory))
            digest_map[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return digest_map


def test_g06_builder_creates_complete_subpath_bundle_without_mutating_fastapi_static(tmp_path: Path) -> None:
    before_hashes = _hash_tree(STATIC_DIR)
    out_dir = tmp_path / "dist_pages"

    summary_1 = build_gh_pages_demo(out_dir, base_path="/endolog/")
    after_hashes = _hash_tree(STATIC_DIR)

    assert before_hashes == after_hashes, "build_gh_pages_demo không được sửa bất kỳ byte nào trong src/endolog/static/"
    assert summary_1["version"] == __version__
    assert summary_1["base_path"] == "/endolog/"
    assert summary_1["case_count"] == 5
    assert summary_1["quarantined_previous_dir"] is None
    assert (out_dir / ".nojekyll").is_file()
    assert (out_dir / "data" / "od05_precomputed_bundle.json").is_file()

    # Rebuild into existing directory must quarantine prior build rather than calling rm/rmtree (Rule v2:R15)
    summary_2 = build_gh_pages_demo(out_dir, base_path="/endolog/")
    assert summary_2["quarantined_previous_dir"] is not None
    assert Path(summary_2["quarantined_previous_dir"]).is_dir()


def test_g06_precomputed_bundle_exact_parity_with_python_engines(tmp_path: Path) -> None:
    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir, base_path="/endolog/")

    bundle = json.loads((out_dir / "data" / "od05_precomputed_bundle.json").read_text(encoding="utf-8"))
    cases = bundle["cases_response"]["items"]
    assert len(cases) == 5

    # Reconstruct minimal patients_by_id from enriched cases to cross-check compute_kpi_snapshot directly
    patients_by_id = {
        c["patient_uid"]: {
            "patient_uid": c["patient_uid"],
            "birth_year": c["patient"]["birth_year"],
            "sex": c["patient"]["sex"],
        }
        for c in cases
    }

    for age_str, age_int in [("45", 45), ("50", 50)]:
        expected_kpi = compute_kpi_snapshot(
            cases,
            patients_by_id=patients_by_id,
            min_adr_age=age_int,
            n_min=20,
        )
        assert bundle["kpi_by_age"][age_str]["kpi"] == expected_kpi

    for metric, preset in [
        ("CIR", "DEFAULT_90"),
        ("CIR", "SCREENING_CIR_95"),
        ("ERCP_NATIVE", "DEFAULT_90"),
    ]:
        expected_cusum = build_cusum_series_from_cases(cases, metric=metric, preset=preset)
        assert bundle["cusum_series"][f"{metric}:{preset}"] == expected_cusum


def test_g06_html_strips_all_password_and_file_inputs_and_preserves_aria_labels(tmp_path: Path) -> None:
    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir, base_path="/endolog/")

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert not re.search(r'<input\b[^>]*\btype\s*=\s*["\']password["\']', html, flags=re.I)
    assert not re.search(r'<input\b[^>]*\btype\s*=\s*["\']file["\']', html, flags=re.I)
    assert SHOWCASE_BANNER_TEXT_VI in html
    assert f'src="/endolog/js/demo-synthetic-adapter.js?v={__version__}"' in html
    assert f'src="/endolog/js/app.js?v={__version__}"' in html
    assert 'href="/endolog/manifest.json"' in html

    present_ids = set(re.findall(r'\bid="([^"]+)"', html))
    dangling_for = [f for f in re.findall(r'<label\b[^>]*\bfor="([^"]+)"', html) if f not in present_ids]
    assert dangling_for == []


def test_g06_sw_demo_prefix_isolation_and_manifest_subpath_scope(tmp_path: Path) -> None:
    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir, base_path="/endolog/")

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["start_url"] == "/endolog/"
    assert manifest["scope"] == "/endolog/"
    assert all(icon["src"].startswith("/endolog/icons/") for icon in manifest["icons"])

    sw_text = (out_dir / "sw-demo.js").read_text(encoding="utf-8")
    assert '"endolog-ghpages-demo-"' in sw_text
    assert f'"endolog-ghpages-demo-v{__version__}"' in sw_text
    assert "k.startsWith(CACHE_PREFIX)" in sw_text
    assert not (out_dir / "sw.js").exists()

    # Verify case-sensitive GitHub repository subpath (/EndoLog/) parity as well
    out_camel = tmp_path / "dist_pages_camel"
    build_gh_pages_demo(out_camel, base_path="/EndoLog/")
    camel_errs, _ = verify_dist_pages_bundle(out_camel, base_path="/EndoLog/", require_gitleaks=False)
    assert camel_errs == []


def test_g06_clean_room_verifier_catches_regressions(tmp_path: Path) -> None:
    git_errs, git_metrics = verify_git_clean_room(REPO_ROOT, require_gitleaks=False)
    assert git_errs == []
    assert git_metrics["tracked_file_count"] > 50

    out_dir = tmp_path / "dist_pages"
    build_gh_pages_demo(out_dir, base_path="/endolog/")

    clean_errs, _ = verify_dist_pages_bundle(out_dir, base_path="/endolog/", require_gitleaks=False)
    assert clean_errs == []

    # Negative probe 1: inject password + file inputs into index.html
    tampered_dir = tmp_path / "dist_tampered"
    build_gh_pages_demo(tampered_dir, base_path="/endolog/")
    idx_path = tampered_dir / "index.html"
    idx_path.write_text(
        idx_path.read_text(encoding="utf-8").replace(
            "</body>",
            '<input type="password"><input type="file"></body>',
        ),
        encoding="utf-8",
    )
    # Negative probe 2: drop an encrypted vault file into dist_pages
    (tampered_dir / "accident.endolog.enc").write_text("{}", encoding="utf-8")

    tampered_errs, _ = verify_dist_pages_bundle(tampered_dir, base_path="/endolog/", require_gitleaks=False)
    joined = "\n".join(tampered_errs)
    assert "input[type=password]" in joined
    assert "input[type=file]" in joined
    assert "accident.endolog.enc" in joined


def test_g06_github_actions_workflow_contract() -> None:
    wf_path = REPO_ROOT / ".github" / "workflows" / "deploy-pages.yml"
    assert wf_path.is_file()
    wf_txt = wf_path.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in wf_txt
    assert "verify_gate_c_clean_room.py --check-git --require-gitleaks" in wf_txt
    assert "pytest -p no:cacheprovider -v" in wf_txt
    assert "tools/check_contrast.py" in wf_txt
    assert "scripts/check_ssot.py" in wf_txt
    assert "PAGES_BASE_PATH: /${{ github.event.repository.name }}/" in wf_txt
    assert 'tools/build_gh_pages_demo.py --output dist_pages --base-path "${PAGES_BASE_PATH}"' in wf_txt
    assert 'verify_gate_c_clean_room.py --check-dist --dist-dir dist_pages --base-path "${PAGES_BASE_PATH}" --require-gitleaks' in wf_txt
    assert 'verify_gh_pages_playwright_g06.py --dist-dir dist_pages --base-path "${PAGES_BASE_PATH}"' in wf_txt
    assert "actions/upload-pages-artifact@v3" in wf_txt
    assert "actions/deploy-pages@v4" in wf_txt
    assert "github.event_name != 'pull_request'" in wf_txt
    assert "group: pages" in wf_txt
    assert "cancel-in-progress: false" in wf_txt


def _init_temp_git_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / ".gitleaks.toml", repo_dir / ".gitleaks.toml")
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@endolog.local"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "EndoLog Test"], cwd=str(repo_dir), check=True, capture_output=True)


def test_gc01_profile_a_vault_ciphertext_caught_in_git_and_dist_pages(tmp_path: Path) -> None:
    vault_bytes = export_profile_a_encrypted_vault(
        state_snapshot={"cases": [], "patients": []},
        passphrase="TestVaultPassphrase!2026",
    )

    # 1. Temp Git repo with disguised .json Profile A vault envelope
    repo_dir = tmp_path / "repo_gc01"
    _init_temp_git_repo(repo_dir)
    (repo_dir / "docs").mkdir(parents=True, exist_ok=True)
    (repo_dir / "docs" / "accidental_vault_dump.json").write_bytes(vault_bytes)
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "accidental vault"], cwd=str(repo_dir), check=True, capture_output=True)

    git_errs, _ = verify_git_clean_room(repo_dir, require_gitleaks=False)
    joined_git = "\n".join(git_errs)
    assert "PROFILE_A_CIPHERTEXT_ENVELOPE" in joined_git

    # 2. Disguised .json Profile A vault inside dist_pages/data/
    dist_dir = tmp_path / "dist_gc01"
    build_gh_pages_demo(dist_dir, base_path="/endolog/")
    (dist_dir / "data" / "accidental_vault_dump.json").write_bytes(vault_bytes)

    dist_errs, _ = verify_dist_pages_bundle(dist_dir, base_path="/endolog/", require_gitleaks=False)
    joined_dist = "\n".join(dist_errs)
    assert "Profile A vault ciphertext" in joined_dist


def test_gc02_vietnamese_unicode_paths_and_research_exports_caught(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo_gc02"
    _init_temp_git_repo(repo_dir)

    (repo_dir / "data_real_clinical").mkdir(parents=True, exist_ok=True)
    (repo_dir / "data_real_clinical" / "bệnh_nhân.json").write_text("{}", encoding="utf-8")
    (repo_dir / "sao_lưu_kho.endolog.enc").write_text("{}", encoding="utf-8")
    (repo_dir / "02_DuLieu_Tho").mkdir(parents=True, exist_ok=True)
    (repo_dir / "02_DuLieu_Tho" / "cohort.csv").write_text("id,age\n1,55\n", encoding="utf-8")
    (repo_dir / "03_ThongKe").mkdir(parents=True, exist_ok=True)
    (repo_dir / "03_ThongKe" / "table1.xlsx").write_bytes(b"PK\x03\x04")

    subprocess.run(["git", "add", "-f", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "unicode & research files"], cwd=str(repo_dir), check=True, capture_output=True)

    git_errs, _ = verify_git_clean_room(repo_dir, require_gitleaks=False)
    joined = "\n".join(git_errs)
    assert "data_real_clinical/bệnh_nhân.json" in joined
    assert "sao_lưu_kho.endolog.enc" in joined
    assert "02_DuLieu_Tho/cohort.csv" in joined
    assert "03_ThongKe/table1.xlsx" in joined
