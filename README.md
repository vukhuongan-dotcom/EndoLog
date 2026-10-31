# EndoLog — Gastrointestinal Endoscopy Registry & Quality Platform
## Dự Án: Hệ Thống Sổ Bộ Lâm Sàng & Đánh Giá Chất Lượng Nội Soi Tiêu Hóa
### Đơn vị công tác: Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân
### Nguồn tham chiếu: [version.md](version.md) (SSoT Phiên bản `0.2.1`) • [AGENTS.md](AGENTS.md) (Quy chuẩn dự án) • [BUG_FIX_REGISTRY.md](docs/BUG_FIX_REGISTRY.md) (Sổ lỗi & Tính năng) • [BRAND.md](docs/brand/BRAND.md) (Nhận diện `v1 · Chàm khói`)

**Phiên bản hiện tại:** `0.2.1` — Hoàn tất phát triển & kiểm chứng kỹ thuật **Gate B (Phase 1 → Phase 5 + Cụm diễn tiến 4 pha chuẩn SurgiLog)** trên dữ liệu giả lập cục bộ; **dừng tại biên giới Gate C** chờ nghiệm thu thực nghiệm lâm sàng — **ZERO-PHI & ZERO-IMAGE DESIGN**  
**Superadmin & Quản trị kỹ thuật:** **BSCKII. Vũ Khương An — Bệnh viện Bình Dân**  
**Người dùng chính (`Primary Endoscopist`):** **ThS. BSCKI. Nguyễn Bình An — Khoa Nội soi Tiêu hóa, Bệnh viện Bình Dân**

> [!IMPORTANT]
> **NGUYÊN TẮC BẢO VỆ DỮ LIỆU & PHÂN TÁCH QUYỀN HẠN (`CLEAN-ROOM PROTOCOL`):**
> 1. **Định hướng bảo vệ dữ liệu cá nhân y tế:** Thiết kế bám sát yêu cầu bảo vệ dữ liệu cá nhân của Luật Khám bệnh, chữa bệnh số 15/2023/QH15, Luật Bảo vệ Dữ liệu Cá nhân số 91/2025/QH15 và Nghị định số 356/2025/NĐ-CP. Thư mục dữ liệu (`data*/`) bị loại trừ khỏi Git qua `.gitignore` và kiểm soát bộ nhớ trình duyệt nghiêm ngặt ở cả 5 tầng (`Zero-PHI`).
> 2. **Không lưu trữ hình ảnh nội soi:** Hệ thống chỉ lưu trữ dữ liệu biến số cấu trúc (4 pha không khóa tuần tự cho `COL`, `EGD`, `ERCP`), không tải lên hay lưu trữ ảnh chụp hoặc video nội soi người bệnh.
> 3. **Phân tách 3 cổng phê duyệt độc lập (`Rule v2:R47` & `Rule v2:R01`):** Khởi tạo bộ khung (**Gate A** — đã đóng), Phát triển & kiểm định tính năng cục bộ (**Gate B** — chờ nghiệm thu) và Triển khai máy chủ sản xuất (**Gate C** — chưa mở).

---

## 1. Cấu Trúc Thư Mục Dự Án (`v0.2.1` — Profile `webapp` ISO 15489-1:2016)

```text
endolog/
├── AGENTS.md                                      # Quy chuẩn kỹ thuật, môi trường fail-closed & bảo mật cục bộ (CLS-03)
├── README.md                                      # Tổng quan dự án, cấu trúc & hướng dẫn kiểm chứng (CLS-02)
├── pyproject.toml                                 # Khai báo gói Python endolog v0.2.1
├── version.md                                     # Lịch sử phiên bản SemVer 2.0.0 (CLS-07)
├── .gitignore                                     # Chốt chặn bảo vệ dữ liệu lâm sàng & khóa bí mật
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
│   ├── core/                                      # Fail-closed config, Argon2id + HttpOnly 15m, DLP, AtomicJsonStore, SHA-256 Audit
│   ├── schemas/                                   # Hợp đồng dữ liệu Pydantic 4 pha cho COL / EGD / ERCP
│   ├── clinical/                                  # BBPS, USMSTF 2020 / ESGE 2020 / ESGE ESD 2022, KPI, QC-CUSUM, Export A/B/C
│   ├── api/                                       # EndoLogService, ETag/If-Match OCC 409, ghép đợt ERCP & 5 ca mẫu OD-05
│   └── static/                                    # PWA tự host (tokens.css, app.css, app.js, index.html, sw.js)
├── scripts/check_ssot.py                          # Công cụ kiểm chứng đồng bộ phiên bản & cặp Sổ lỗi Dual SSoT
├── tools/                                         # Công cụ kiểm toán tương phản WCAG, Phase 4A & Codex 8-Gate Phase 5
├── tests/                                         # Bộ kiểm thử tự động pytest (25 ca kiểm thử cô lập sandbox)
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

# 2. Chạy bộ kiểm thử đơn vị, động cơ y khoa, bảo mật fail-closed & hồi quy Phase 4A/4B
PYTHONPATH=src pytest -p no:cacheprovider -v

# 3. Kiểm chứng nhận diện thương hiệu Phase 4A & bộ Codex 8-Gate Phase 5 trên Chromium
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_brand_phase4a.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/verify_phase5_codex_8gate.py

# 4. Kiểm chứng đồng bộ phiên bản SemVer & mã băm SHA-256 cặp Sổ lỗi Dual SSoT
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_ssot.py
```
