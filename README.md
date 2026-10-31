# EndoLog — Gastrointestinal Endoscopy Registry & Quality Platform
## Dự Án: Hệ Thống Sổ Bộ Lâm Sàng & Đánh Giá Chất Lượng Nội Soi Tiêu Hóa
### Đơn vị công tác: Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân
### Nguồn tham chiếu: [version.md](version.md) (SSoT Phiên bản `0.3.1`) • [AGENTS.md](AGENTS.md) (Quy chuẩn dự án) • [BUG_FIX_REGISTRY.md](docs/BUG_FIX_REGISTRY.md) (Sổ lỗi & Tính năng) • [BRAND.md](docs/brand/BRAND.md) (Nhận diện `Design System EndoLog v1 · Chàm khói`)

**Phiên bản hiện tại:** `0.3.1` — Hoàn tất **Gate A**, **Gate B (Phase 1 → Phase 5 + Cụm diễn tiến 4 pha chuẩn SurgiLog + Đồng bộ Design System EndoLog v1 + Phân hệ Quản trị Superadmin Phase 4C)** và **Gate C · Phương Án G1 (`G06` — Kho GitHub Sạch, Bản Trình Diễn Tĩnh `/endolog/` Khóa Nhập PHI & Đường Ống GitHub Actions Pages)** — **ZERO-PHI & ZERO-IMAGE DESIGN**
**Superadmin & Quản trị kỹ thuật:** **BSCKII. Vũ Khương An — Bệnh viện Bình Dân**  
**Người dùng chính (`Primary Endoscopist`):** **ThS. BSCKI. Nguyễn Bình An — Khoa Nội soi Tiêu hóa, Bệnh viện Bình Dân**

> [!IMPORTANT]
> **NGUYÊN TẮC BẢO VỆ DỮ LIỆU & PHÂN TÁCH MÔI TRƯỜNG (`CLEAN-ROOM PROTOCOL · PHƯƠNG ÁN G1`):**
> 1. **Định hướng bảo vệ dữ liệu cá nhân y tế:** Thiết kế bám sát yêu cầu bảo vệ dữ liệu cá nhân của Luật Khám bệnh, chữa bệnh số 15/2023/QH15, Luật Bảo vệ Dữ liệu Cá nhân số 91/2025/QH15 và Nghị định số 356/2025/NĐ-CP. Thư mục dữ liệu (`data*/`), tệp sao lưu mã hóa (`*.enc`) và thư mục đóng gói tạm (`dist_pages/`) bị loại trừ khỏi Git qua `.gitignore` và được kiểm toán tự động bằng `gitleaks` + `tools/verify_gate_c_clean_room.py`.
> 2. **Không lưu trữ hình ảnh nội soi:** Hệ thống chỉ lưu trữ dữ liệu biến số cấu trúc (4 pha không khóa tuần tự cho `COL`, `EGD`, `ERCP`), không tải lên hay lưu trữ ảnh chụp hoặc video nội soi người bệnh.
> 3. **Tách biệt tuyệt đối Bản trình diễn GitHub Pages (`/endolog/`) và Máy chủ lâm sàng nội bộ:** Bản tĩnh trên GitHub Pages chỉ trình diễn giao diện chỉ đọc trên `5` ca giả lập chuẩn `OD-05` (`0` ô nhập mật khẩu, `0` ô tải tệp, khóa toàn bộ thao tác ghi); mọi hoạt động ghi nhận ca bệnh thật bắt buộc chạy trên máy chủ FastAPI nội bộ (`local_clinical_phi` / `production`).

---

## 1. Cấu Trúc Thư Mục Dự Án (`v0.3.1` — Profile `webapp` ISO 15489-1:2016)

```text
endolog/
├── AGENTS.md                                      # Quy chuẩn kỹ thuật, môi trường fail-closed & bảo mật cục bộ (CLS-03)
├── README.md                                      # Tổng quan dự án, cấu trúc & hướng dẫn kiểm chứng (CLS-02)
├── pyproject.toml                                 # Khai báo gói Python endolog v0.3.1
├── version.md                                     # Lịch sử phiên bản SemVer 2.0.0 (CLS-07)
├── .gitignore                                     # Chốt chặn bảo vệ dữ liệu lâm sàng, khóa bí mật & dist_pages/
├── .gitleaks.toml                                 # Cấu hình quét rò rỉ khóa bí mật & dữ liệu nhạy cảm (Gate C)
├── .github/workflows/deploy-pages.yml             # Đường ống CI kiểm toán Clean-Room, Pytest, TC-G06 & GitHub Pages
├── PROJECT_CONTEXT/                               # Bộ não tri thức dự án (SSoT Brain — CLS-02/07)
│   ├── CONTEXT.md                                 # Hợp đồng đặc tả nghiệp vụ & dữ liệu sau Crosscheck vòng 1
│   ├── FILE_CLASSIFICATION_MATRIX.md              # Ma trận phân loại tệp ISO 15489-1:2016
│   └── BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md          # Sổ lỗi & tính năng SSoT #2 (Schema v3.1)
├── docs/                                          # Tài liệu kỹ thuật, thương hiệu & biên lai kiểm toán (CLS-02/06/07)
│   ├── brand/                                     # Bộ nhận diện EndoLog v1 (Phương án B · Chàm khói, SVG/PNG/Fonts tự host)
│   ├── verification/                              # Biên lai JSON thực nghiệm Phase 5 (measured_evidence.json, test_report.json)
│   ├── file_classification_matrix.md              # Ma trận phân loại tệp bản repo
│   ├── BUG_FIX_REGISTRY.md                        # Sổ lỗi & tính năng SSoT #1 (Schema v3.1)
│   └── scaffolding_receipt.md                     # Biên lai nghiệm thu bộ khung Day-0 (Gate A)
├── src/endolog/                                   # Mã nguồn ứng dụng FastAPI Backend & Vanilla PWA tự host 100%
│   ├── core/                                      # Fail-closed config, Argon2id + thu hồi JWT, DLP, AtomicJsonStore, SHA-256 Audit
│   ├── schemas/                                   # Hợp đồng dữ liệu Pydantic 4 pha & lược đồ kho nghiêm ngặt extra="forbid"
│   ├── clinical/                                  # BBPS, USMSTF/ESGE, KPI, QC-CUSUM, Export A/B/C & thẩm định khôi phục kho
│   ├── api/                                       # EndoLogService, W/"e{epoch}:v{ver}" OCC, gộp bệnh nhân/đợt nội trú & OD-05
│   └── static/                                    # PWA tự host cho FastAPI / (tokens.css, app.css, app.js, index.html, sw.js)
├── scripts/check_ssot.py                          # Công cụ kiểm chứng đồng bộ phiên bản & cặp Sổ lỗi Dual SSoT
├── tools/                                         # Công cụ WCAG, Phase 4A, Codex 8-Gate, đóng gói /endolog/ & Clean-Room Gate C
├── tests/                                         # Bộ kiểm thử tự động pytest (42 ca kiểm thử cô lập sandbox)
├── dist_pages/                                    # [Git-Ignored] Gói trình diễn tĩnh /endolog/ sinh bởi build_gh_pages_demo.py
├── data/                                          # [Git-Ignored] Lưu trữ AtomicJsonStore cục bộ (CLS-04)
└── data_backups/                                  # [Git-Ignored] Bản chụp sao lưu tự động (CLS-04)
```

---

## 2. Khởi Chạy Cục Bộ & Kiểm Chứng Tự Động (Dữ Liệu Giả Lập `local_dev_synthetic`)

```bash
# 1. Khởi chạy máy chủ phát triển cục bộ trên loopback 127.0.0.1:8765 (5 ca giả lập OD-05)
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 \
  ENDOLOG_ENV=local_dev_synthetic ENDOLOG_ENABLE_DEV_BYPASS=1 ENDOLOG_BIND_HOST=127.0.0.1 \
  python3 -m uvicorn endolog.main:create_default_app --factory --host 127.0.0.1 --port 8765

# 2. Chạy bộ kiểm thử đơn vị, động cơ y khoa, bảo mật fail-closed, Superadmin & Gate C G06 (42 ca)
PYTHONPATH=.:src PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider -v

# 3. Kiểm chứng nhận diện thương hiệu Phase 4A & bộ Codex 8-Gate Phase 5 trên Chromium
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_brand_phase4a.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_phase5_codex_8gate.py

# 4. Kiểm chứng đồng bộ phiên bản SemVer & mã băm SHA-256 cặp Sổ lỗi Dual SSoT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_ssot.py
```

---

## 3. Đóng Gói & Kiểm Chứng Gate C — Bản Trình Diễn Tĩnh `/EndoLog/` (`Phương Án G1` / `G06`)

- **Bản trình diễn tĩnh công khai (chỉ đọc, 5 ca chuẩn `OD-05`, khóa nhập PHI):** https://vukhuongan-dotcom.github.io/EndoLog/

```bash
# 1. Sinh gói trình diễn tĩnh chỉ đọc cho đường dẫn con /EndoLog/ (không sửa src/endolog/static/)
PYTHONDONTWRITEBYTECODE=1 python3 tools/build_gh_pages_demo.py --output dist_pages --base-path /EndoLog/

# 2. Quét Clean-Room lịch sử Git, Gitleaks & gói dist_pages/ (0 PHI, 0 input password/file, 0 khóa bí mật)
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_gate_c_clean_room.py --base-path /EndoLog/ --require-gitleaks

# 3. Chạy kiểm thử E2E Chromium TC-G06 trên máy chủ mô phỏng đường dẫn con http://127.0.0.1:<port>/EndoLog/
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_gh_pages_playwright_g06.py --dist-dir dist_pages --base-path /EndoLog/
```
