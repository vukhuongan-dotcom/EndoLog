# BẢNG TỔNG HỢP LỖI & TÍNH NĂNG MỚI (BUG & FEATURE REGISTRY SCHEMA V3.1)
## Hệ Thống / Dự Án: EndoLog (`endolog`) — Sổ Bộ Nội Soi Tiêu Hóa Bệnh Viện Bình Dân

> 📌 **Quy tắc Quản trị Vòng đời Sản phẩm (Rule v2:R45 [T3-QA] & Rule v2:R47 [T3-DEV]):**
> 1. Mỗi khi hoàn tất bất kỳ việc **SỬA LỖI (BUG)** hoặc **TRIỂN KHAI TÍNH NĂNG MỚI (FEAT)**, bắt buộc cập nhật vào bảng này kèm bằng chứng kiểm tra thực tế.
> 2. Sử dụng chung một chuỗi STT tăng dần liên tục: mã `BUG-xxx` cho sửa lỗi và `FEAT-xxx` cho tính năng mới.
> 3. Cập nhật đồng bộ song hành 100% mã băm SHA-256 giữa 2 tệp độc lập: `docs/BUG_FIX_REGISTRY.md` (Git repo) và `PROJECT_CONTEXT/BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md` (Brain SSoT). Tuyệt đối không dùng symlink.
> 4. Không ghi trạng thái `VERIFIED_CLOSED` hoặc điền ngày đóng / người duyệt khi sự kiện khởi tạo hoặc kiểm thử chưa diễn ra trên thực tế.

---

## 📊 1. THỐNG KÊ TỔNG QUAN

* **Tổng số sự cố & tính năng ghi nhận:** 5
* **Đang xử lý / Dự thảo chờ duyệt (`OPEN`):** 0
* **Đã phong tỏa an toàn (`CONTAINED`):** 0
* **Đã thực thi, chờ nghiệm thu (`FIXED_PENDING_VERIFY`):** 4
* **Đã xác minh hoàn tất (`VERIFIED_CLOSED`):** 1
* **Mở lại sau đóng (`REOPENED`):** 0

---

## 📋 2. MA TRẬN THEO DÕI SỰ CỐ & TÍNH NĂNG (SCHEMA V3.1 — 14 TRƯỜNG BẮT BUỘC)

| STT | Mã định danh (`incident_id`) | Ngày ghi nhận (`discovered_date`) | Commit Link (`fix_commit_hash`) | Phân hệ ảnh hưởng (`affected_scope`) | Tiêu đề tóm tắt | Hiện tượng / Bối cảnh (`symptom`) | Mức độ (`severity`) | Nguyên nhân & Trạng thái RCA (`root_cause` / `rca_status`) | Giải pháp & Build (`fix_action` / `build_version`) | Trạng thái kỹ thuật (`current_status`) | Biên lai xác minh (`evidence_refs`) | Rủi ro tồn dư (`residual_risk`) | Ngày đóng & Người duyệt |
|:---:|:---:|:---:|:---:|:---:|---|---|:---:|:---:|---|:---:|---|---|:---:|
| 1 | `FEAT-001` | 2026-10-31 | `ed22632ab437` | Khung hệ thống (`Scaffold`) | Khởi tạo bộ khung dự án EndoLog Day-0 | Khởi tạo không gian làm việc chuẩn hóa 3 trụ cột cho Sổ bộ Nội soi Tiêu hóa cá nhân của ThS. BSCKI. Nguyễn Bình An | N/A | N/A (`N/A`) | Tạo cây thư mục `webapp`, `AGENTS.md`, Ma trận ISO 15489, Sổ lỗi Dual SSoT Schema v3.1 và `version.md`; khớp 100% SHA-256 `creation_manifest` 9 tệp | `VERIFIED_CLOSED` | `ag_lint.py --check-scaffold` Exit Code `0`; biên lai `scaffolding_receipt_endolog.md` | Không còn rủi ro tầng khung Day-0 | `2026-10-31` · `BSCKII. Vũ Khương An` |
| 2 | `FEAT-002` | 2026-10-31 | `66d77322f26b` | Lõi bảo mật & Lưu trữ (`src/endolog/core/`) | Triển khai Phase 1: Bảo mật Fail-Closed, DLP, Kho JSON nguyên tử & Chuỗi băm kiểm toán | Cần tầng nền cô lập tuyệt đối dữ liệu giả lập với dữ liệu thật, chặn định danh nhạy cảm ở ghi chú tự do và chống hỏng dữ liệu khi mất điện | N/A | N/A (`N/A`) | Cài đặt `config.py` (3 chế độ fail-closed), `security.py` (Argon2id + cookie `HttpOnly` 15 phút + cổng bypass 5 chốt), `dlp.py`, `persistence.py` (`RLock` + `InterProcessLock` + `fsync` + rollback journal) và `audit.py` (`LinearHashChain`) (`0.1.0-alpha.1`) | `FIXED_PENDING_VERIFY` | `pytest tests/test_security_fail_closed.py -v` (`6/6 passed`) | Cần kiểm thử chịu tải sao lưu mã hóa trên thực địa trước Gate C | `PENDING` (chờ nghiệm thu) |
| 3 | `FEAT-003` | 2026-10-31 | `66d77322f26b` | Động cơ y khoa (`src/endolog/clinical/` & `schemas/`) | Triển khai Phase 2: Sơ đồ 4 pha, BBPS, Hẹn soi lại USMSTF/ESGE, KPI, QC-CUSUM & Export A/B/C | Cần tính toán chuẩn xác chỉ số nội soi tiêu hóa, tách riêng ca chờ GPB / chờ cửa sổ 30 ngày và xuất dữ liệu nghiên cứu giả danh dọc | N/A | N/A (`N/A`) | Cài đặt `bbps.py`, `adverse_events.py` (`AGREE 2022` & `PEP`), `surveillance_scheduler.py` (`USMSTF 2020` mặc định chính + đối chiếu `ESGE 2020` & `ESGE ESD 2022`), `quality_metrics.py`, `cusum.py` (`RA-CUSUM = DISABLED_UNVALIDATED_MODEL`) và `export_profiles.py` (`0.1.0-alpha.1`) | `FIXED_PENDING_VERIFY` | `pytest tests/test_clinical_engines.py -v` (`6/6 passed`) | Cần tiếp tục hoàn thiện hộp thoại nhập liệu 4 pha ở Phase 4B | `PENDING` (chờ nghiệm thu) |
| 4 | `FEAT-004` | 2026-10-31 | `66d77322f26b` | Tầng dịch vụ API (`src/endolog/api/` & `main.py`) | Triển khai Phase 3: REST API FastAPI, OCC ETag 409, Ghép đợt ERCP & Strict CSP | Cần giao diện lập trình chống ghi đè đồng thời giữa các pha, bắt buộc MRN nội trú và cấm lưu đệm dữ liệu lâm sàng trên trình duyệt | N/A | N/A (`N/A`) | Cài đặt `EndoLogService` & `main.py` với `ETag`/`If-Match` `409`, quy tắc `OD-04`, `CSP: default-src 'self'` và `Cache-Control: no-store` cho mọi `/api/*` (`0.1.0-alpha.1`) | `FIXED_PENDING_VERIFY` | `pytest tests/test_api_and_exports.py -v` (`2/2 passed`); Playwright `HTTP_4xx_5xx=0` | Chờ tích hợp luồng lưu từng pha trực tiếp trên giao diện ở Phase 4B | `PENDING` (chờ nghiệm thu) |
| 5 | `FEAT-005` | 2026-10-31 | `66d77322f26b` | Nhận diện & Giao diện PWA (`docs/brand/` & `static/`) | Triển khai Phase 4A: Bộ nhận diện EndoLog v1 (`Phương án B · Chàm khói`) & 3 màn hình lõi | Áp dụng hệ nhận diện thương hiệu tự host đồng bộ SurgiLog ở đầu Phase 4 kèm cổng dừng duyệt ảnh chụp trên 5 ca chuẩn `OD-05` | N/A | N/A (`N/A`) | Tạo `docs/brand/` (4 SVG, 4 PNG, 3 OFL, `BRAND.md`), `tokens.css` (`62/62` cặp WCAG đạt, `0` `#hex` ngoài `tokens.css`, `0` Google Fonts, `0` emoji) và 3 màn hình (`Nhật ký ca soi`, `Hẹn soi lại`, `Chỉ số chất lượng`) (`0.1.0-alpha.1`) | `FIXED_PENDING_VERIFY` | `tools/check_contrast.py` (`62/62`); `tools/verify_brand_phase4a.py` (`48/48` khung nhìn `0` tràn ngang, `58/58` vùng chạm `>=44px`, `12/12` ảnh chụp) | Đang dừng tại Cổng dừng Phase 4A chờ BS. Bình An & BS. Khương An duyệt giao diện trước khi làm Phase 4B | `PENDING` (chờ duyệt ảnh Phase 4A) |

---

## 📖 3. HƯỚNG DẪN ĐIỀN CHUẨN SCHEMA V3.1
* **Mức độ (`severity`):** `P0 - Critical` | `P1 - High` | `P2 - Medium` | `P3 - Low` | `N/A` (Dành cho `FEAT`).
* **Trạng thái RCA (`rca_status`):** `VERIFIED_ROOT_CAUSE` | `HYPOTHESIS_PENDING_VERIFY` | `UNVERIFIED_ROOT_CAUSE` | `N/A`.
* **Trạng thái kỹ thuật (`current_status`):** `OPEN` | `CONTAINED` | `FIXED_PENDING_VERIFY` | `VERIFIED_CLOSED` | `REOPENED` | `UNVERIFIED_HISTORICAL`.
* **Biên lai xác minh (`evidence_refs`) & Ngày đóng / Người duyệt:** Chỉ điền giá trị nghiệm thu thật sau khi có kết quả kiểm tra độc lập và xác nhận của người có thẩm quyền phê duyệt.
