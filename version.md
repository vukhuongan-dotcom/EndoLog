# Lịch Sử Phiên Bản (Changelog) — EndoLog

Mọi thay đổi đáng chú ý của dự án **EndoLog** (*Hệ Thống Sổ Bộ Lâm Sàng & Đánh Giá Chất Lượng Nội Soi Tiêu Hóa — Bệnh Viện Bình Dân*) được ghi nhận tại tệp này.

Định dạng tuân thủ chuẩn [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) và quy tắc đánh số phiên bản theo [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) (`MAJOR.MINOR.PATCH`).
Các nhóm phân loại hợp lệ: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

## [Unreleased]

### Added
- Hoàn tất nghiệm thu bộ khung dự án Day-0 **EndoLog** (`endolog`) theo chuẩn Project Inception Gate (`Rule v2:R47`) với cấu trúc `webapp`, chính sách `Strict Zero-PHI` & `Zero-Image`, Ma trận phân loại tệp ISO 15489-1:2016 và Sổ theo dõi lỗi/tính năng Dual SSoT Schema v3.1 ([FEAT-001]).
- Triển khai tầng lõi **Phase 1 (`core/`)**: cấu hình môi trường fail-closed 3 chế độ (`local_dev_synthetic`, `local_clinical_phi`, `production`), xác thực mật khẩu Argon2id RFC 9106 + cookie phiên `HttpOnly; SameSite=Strict` tự hết hạn 15 phút, cổng bypass 5 chốt an toàn chỉ mở cho dữ liệu giả lập cục bộ, bộ lọc DLP chặn CCCD/SĐT/BHYT/email ở ghi chú tự do, kho JSON nguyên tử (`RLock` + `InterProcessLock` + `fsync` + nhật ký rollback) và chuỗi băm kiểm toán tuyến tính SHA-256 ([FEAT-002]).
- Triển khai động cơ nghiệp vụ y khoa **Phase 2 (`clinical/` & `schemas/`)**: mô hình ca nội soi 4 pha không khóa tuần tự (`EGD`, `COL`, `ERCP`) với 1 tổn thương đại diện lớn nhất kèm tổng hợp toàn ca; kiểm định BBPS (`tổng ≥ 6` và `mỗi đoạn ≥ 2`); khuyến cáo hẹn soi lại ưu tiên `USMSTF_POST_POLYPECTOMY_2020` làm mặc định chính kèm đối chiếu song song `ESGE 2020` & `ESGE ESD 2022` và cảnh báo hội chẩn Ngoại khoa; tính toán KPI tường minh tử số/mẫu số (`CIR`, `BBPS`, `PDR`, `ADR`/`SSLDR` `≥ 45`/`≥ 50` tuổi, thông nhú chọn lọc `ERCP`, biến cố `AGREE 2022` & `PEP` tách riêng ca đang chờ cửa sổ 30 ngày); biểu đồ `Tabular Bernoulli QC-CUSUM` cá nhân (`p0=0.10, p1=0.20, h=2.890372`, khóa `RA-CUSUM = DISABLED_UNVALIDATED_MODEL`); và 3 chế độ xuất dữ liệu `Profile A/B/C` ([FEAT-003]).
- Triển khai tầng dịch vụ **Phase 3 (`api/` & `main.py`)**: hệ thống REST API FastAPI với kiểm soát đồng thời lạc quan (`ETag` / `If-Match` `409 Conflict`), bắt buộc `hospital_mrn` cho ca nội trú và gợi ý ghép đợt điều trị `ERCP`, tiêu đề bảo mật `CSP: default-src 'self'` và `Cache-Control: no-store` cho toàn bộ `/api/*` ([FEAT-004]).
- Áp dụng **Bộ nhận diện thương hiệu EndoLog v1 (`Phase 4A` — `Phương án B · Chàm khói`)**: gói `docs/brand/` (`BRAND.md`, 4 biểu trưng SVG, 4 biểu tượng PNG PWA, 6 phông chữ biến thiên tự host đồng bộ SurgiLog, công cụ kiểm toán tương phản `62/62` cặp đạt), bảng màu độc quyền `tokens.css` (0 mã `#hex` cứng bên ngoài, 0 Google Fonts, 0 emoji) và 3 màn hình lõi (`Nhật ký ca soi`, `Hẹn soi lại`, `Chỉ số chất lượng`) hiển thị trên 5 ca lâm sàng giả lập chuẩn `OD-05` ([FEAT-005]).
