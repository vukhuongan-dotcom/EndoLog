# Lịch Sử Phiên Bản (Changelog) — EndoLog

Mọi thay đổi đáng chú ý của dự án **EndoLog** (*Hệ Thống Sổ Bộ Lâm Sàng & Đánh Giá Chất Lượng Nội Soi Tiêu Hóa — Bệnh Viện Bình Dân*) được ghi nhận tại tệp này.

Định dạng tuân thủ chuẩn [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) và quy tắc đánh số phiên bản theo [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) (`MAJOR.MINOR.PATCH`).
Các nhóm phân loại hợp lệ: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`.

## [0.3.0] - 2026-10-31

### Added
- Triển khai **Phase 4C (`v0.3.0` — Phân hệ Quản trị Superadmin & Bảo toàn Toàn vẹn Sổ bộ)** theo Kế hoạch `v2.1` đã được `BSCKII. Vũ Khương An` phê duyệt (`G01–G05`):
  - **Quản trị tài khoản & thu hồi phiên tức thì (`G01`):** bổ sung `POST /api/auth/change-password`, `GET /api/admin/users`, `POST /api/admin/users/{username}/reset-password`, nút chuyển phiên nhanh `BSCKII. Vũ Khương An` (`#el-btn-dev-bypass-admin`, chỉ mở trong `local_dev_synthetic`), hộp thoại đổi mật khẩu `#el-password-modal-backdrop`, và cơ chế đối chiếu phiên sống (`auth_ver`, `store_epoch`, `revoked_jtis`) thu hồi tức thì mọi JWT cũ khi đăng xuất, đổi mật khẩu, đặt lại mật khẩu hoặc khôi phục bảng người dùng.
  - **Khôi phục nguyên tử kho sao lưu mã hóa Hồ sơ A (`G02`, `G03`, `G04`):** bổ sung `POST /api/admin/restore-profile-a` với giới hạn luồng đọc `10 MiB` trước KDF, kiểm định lược đồ nghiêm ngặt `extra="forbid"` + toàn vẹn khóa ngoại + chuỗi băm kiểm toán bên trong kho, đối chiếu dấu vân tay khóa HMAC liên máy chủ (`mrn_key_fp`, `shift_key_fp`, chính sách `REJECT` mặc định hoặc `REKEY_AND_BUMP_DATASET_EPOCH` tăng `export_dataset_epoch`), giao dịch chụp ảnh an toàn `pre_restore_*.json` nguyên tử (`O_CREAT | O_EXCL` + `fsync` tệp & thư mục trước khi chạm kho sống), tăng `store_epoch` kèm `ETag` `W/"e{store_epoch}:v{version}"` chống ghi đè cũ, và cầu nối kiểm toán `audit_lineage_bridges` trên `GET /api/audit/verify`.
  - **Tách bạch gộp người bệnh với đối soát đợt nội trú (`G05`):** bổ sung `GET /api/admin/patients`, `POST /api/admin/patients/merge` (bảo toàn 100% ranh giới `episode_id` và chỉ số phiên `ERCP`, lưu vết `MERGED_SUPERSEDED` chuẩn Zero-RM, chặn ghi mới vào định danh cũ `409 PATIENT_MERGED_SUPERSEDED`, ánh xạ `secondary_mrn_hashes`) và `POST /api/admin/episodes/reconcile` (chỉ áp dụng cho `INPATIENT`, tính lại tất định thứ tự phiên `ERCP`, tăng `profile_b_lineage_seq` trên `Hồ sơ B`).
  - **Giao diện quản trị Superadmin (`#el-superadmin-panel`) & phân quyền cấu hình cấp khoa:** phân tách cấu hình cá nhân (`colo_guideline_mode`, `adr_min_age`) với cấu hình thống kê cấp khoa (`kpi_min_sample_size`, `cusum_preset` chỉ `superadmin` chỉnh sửa), 4 thẻ quản trị tiếng Việt tự nhiên (`0` mã `UPPER_SNAKE_CASE`, `100%` biến màu `tokens.css`, vùng chạm `>= 44×44 px`) và bộ kiểm thử `tests/test_superadmin_governance.py` ([FEAT-010]).

### Fixed
- Khắc phục 2 phát hiện crosscheck của **Phase 4C (`v0.3.0`)**:
  - **`C01` ([BUG-011]):** định nghĩa tường minh ranh giới commit nguyên tử tại đúng lệnh `os.replace` thay tệp kho chính `endolog_state.json`, tách biệt tuyệt đối lỗi trước điểm commit (`HTTP 500`, `committed=false`, bảo toàn kho & phiên hiện hành) khỏi lỗi vệ sinh hậu commit (`state_dir_fsync`, `wal_archive`, `hourly_snapshot` trả `HTTP 200`, `committed=true`, `commit_status="COMMITTED_WITH_POST_COMMIT_WARNING"` kèm xoay/thu hồi cookie phiên chuẩn xác và phục hồi an toàn khi mở lại kho).
  - **`C02` ([BUG-012]):** đóng gói các tệp bằng chứng lịch sử `pre_restore_*.json` nén `zlib+base64` có trần dung lượng vào bên trong phong bì mã hóa Hồ sơ A (`audit_lineage_artifacts`), giải nén vào `backup_dir` máy đích một cách nguyên tử khi khôi phục, và đối chiếu song ánh hai chiều giữa các sự kiện `RESTORE_PROFILE_A_ENCRYPTED` trong chuỗi băm `audit_chain` (cả chuỗi gốc lẫn các ảnh chụp lịch sử) với danh sách cầu nối `audit_lineage_bridges`.

## [0.2.3] - 2026-10-31

### Changed
- Đồng bộ toàn diện **EndoLog `v0.2.3`** với **Bộ nhận diện chính thức Design System v1 (`31/10/2026`, BSCKII. Vũ Khương An chốt)**:
  - Lưu trữ nguyên vẹn gói nguồn chuẩn chỉ đọc tại `docs/brand/design-system-v1/` (`42` tệp khớp 100% SHA-256 tệp nén gốc) và cập nhật `docs/brand/BRAND.md` với dòng đầu `"Nguồn chuẩn: Design System EndoLog v1 (31/10/2026), BSCKII. Vũ Khương An chốt."` kèm sao chép nguyên câu 3 mục `Nguyên tắc`, `Logo`, `Giọng văn`.
  - Bổ sung đủ 7 tệp SVG biểu trưng vào `docs/brand/logo/` (`endolog-mark-small.svg`, `endolog-mark-mono.svg`, `endolog-icon-dark.svg` chỉ lưu tại `docs/` do W3C Web App Manifest chuẩn chưa hỗ trợ chuyển biểu tượng sáng/tối theo `color_scheme`) và 6 tệp SVG vào `src/endolog/static/icons/`.
  - Bổ sung các biến kích thước & khoảng cách chuẩn vào `src/endolog/static/css/tokens.css` (`--touch-min: 44px`, `--mark-mobile: 28px`, `--mark-desktop: 40px`, `--proc-dot: 7px`, `--space-1..8`: `4/8/12/16/24/32px`, `--radius-pill: 999px`) trong khi bảo toàn 100% giá trị 62 biến màu (`62/62` cặp tương phản WCAG AA đạt).
  - Tinh chỉnh 6 thành phần giao diện (`Button`, `NavTab`, `ProcedureChip`, `StatusPill`, `KpiTile`, `CaseCard`) khớp đặc tả Design System v1 và giữ nguyên bộ biểu tượng **Feather / Lucide** nội tuyến (`24×24`, `stroke 2`, `round`) ([FEAT-009]).

## [0.2.2] - 2026-10-31

### Changed
- Tinh gọn chống trùng lặp trên chân thẻ ca soi (`src/endolog/static/js/app.js`, `src/endolog/static/css/app.css`):
  - Gỡ bỏ hoàn toàn 2 dòng chữ tóm tắt lặp thông tin (`.el-phase-summary-meta`) và gỡ các nút lặp pha (`Sửa P1`, `Thủ thuật P2`, `Mở Pha 4`) vốn đã có sẵn trên 4 phân đoạn màu `P1..P4`; trên máy tính (`>= 768 px`) gộp chân thẻ còn 1 hàng ngang duy nhất gồm thanh màu `P1..P4` bên trái và cụm `[Hành động bước tiếp theo (chỉ hiện khi đang chờ)]` · `[Chi tiết]` · `[•••]` bên phải.
  - Ở chế độ điện thoại (`<= 767 px`), ẩn hoàn toàn hàng nút phụ (`.el-action-buttons-row`) và **chỉ giữ duy nhất thanh biểu thị màu 4 giai đoạn (`P1 | P2 | P3 | P4`)** trải đều ngang thẻ để nhận diện nhanh giai đoạn ca soi ([BUG-010]).

## [0.2.1] - 2026-10-31

### Added
- Đồng bộ **Cụm diễn tiến theo dõi dọc 4 pha chuẩn SurgiLog Pro (`P1..P4`)** trên 100% thẻ ca nội soi tại cả 2 màn hình `Nhật ký ca soi` và `Hẹn soi lại` (`src/endolog/static/`):
  - Thanh 4 phân đoạn liền khối `P1`, `P2`, `P3`, `P4` bằng biểu tượng SVG nét 2 px tự host (`0` emoji Unicode, vùng chạm `>= 44×44 px`, `0` thay đổi `tokens.css`) phản ánh trực quan 5 trạng thái (`Hoàn tất`, `Đang chờ`, `Đang hẹn soi`, `Cảnh báo hội chẩn / biến cố`, `Thường quy`), cho phép nhấp trực tiếp mở ngăn kéo đúng pha tương ứng.
  - Hàng tác vụ ngữ cảnh phía trên (`Sửa P1` · nút hành động chính ưu tiên theo pha kế tiếp `Nhập GPB P4` / `Theo dõi P3` / `Soi lại P4` / `Thủ thuật P2` · `Chi tiết` · trình đơn tràn `•••` tự động bung ngược `.is-dropup` khi sát mép dưới màn hình).
  - Hộp thoại **Xem chi tiết diễn tiến 4 pha (`#el-detail-modal`)** hiển thị bảng tổng hợp 4 pha bằng tiếng Việt tự nhiên (`0` lộ mã `UPPER_SNAKE_CASE`), tích hợp khóa tiêu điểm `inert` và tự động xóa trắng DOM khi đăng xuất / `401` / hết hạn 15 phút ([FEAT-008]).

## [0.2.0] - 2026-10-31

### Added
- Triển khai **Phase 4B (`src/endolog/static/` & `api/`)**: ngăn kéo nhập liệu & cập nhật hồ sơ ca nội soi 4 pha không khóa tuần tự (`Pha 1 · Hành chính`, `Pha 2 · Thủ thuật`, `Pha 3 · Biến cố 30 ngày`, `Pha 4 · Giải phẫu bệnh`) cho 3 phân hệ `COL`, `EGD`, `ERCP` với hiển thị lũy tiến, mẫu 1 chạm đại tràng bình thường (`0 polyp`), bộ chấm điểm `BBPS` trực tiếp + đồng hồ bấm giờ rút ống sạch, chip chọn nhanh vị trí giải phẫu & can thiệp/dự phòng `ERCP` (huy hiệu `ESGE 2016 5-5-2` tự động + khung mở rộng 12 xét nghiệm trước `ERCP`), nút đồng bộ mô bệnh học toàn ca đại trực tràng, đóng vòng hẹn soi lại 1 chạm (`fulfill_surveillance_rec_id`), bảng cấu hình chuyên môn (`USMSTF 2020` / `ESGE 2020`, `n tối thiểu`, `QC-CUSUM`) và xuất dữ liệu đủ 3 chế độ `Hồ sơ A/B/C` ([FEAT-006]).
- Hoàn tất **Phase 5 (`tools/verify_phase5_codex_8gate.py`, `scripts/check_ssot.py`, `tests/test_phase4b_and_phase5.py`)**: bộ kiểm chứng tự động Codex 8-Gate (`Rule v2:R30`) + 30 tiêu chí `Med-Web`, kiểm toán ngân sách thao tác công thái học, ma trận 10 khung nhìn `320..1440 px` (cả khi mở ngăn kéo 4 pha), kiểm chứng đồng bộ phiên bản & Dual SSoT `check_ssot.py`, cùng biên lai JSON thực nghiệm `docs/verification/measured_evidence.json` và `docs/verification/test_report.json` ([FEAT-007]).
- Áp dụng và nghiệm thu **Bộ nhận diện thương hiệu EndoLog v1 (`Phase 4A` — `Phương án B · Chàm khói`)**: gói `docs/brand/` (`BRAND.md`, 4 biểu trưng SVG, 4 biểu tượng PNG PWA, 6 phông chữ biến thiên tự host đồng bộ SurgiLog, công cụ kiểm toán tương phản `62/62` cặp đạt), bảng màu độc quyền `tokens.css` (0 mã `#hex` cứng bên ngoài, 0 Google Fonts, 0 emoji) và 3 màn hình lõi (`Nhật ký ca soi`, `Hẹn soi lại`, `Chỉ số chất lượng`) hiển thị trên 5 ca lâm sàng giả lập chuẩn `OD-05` ([FEAT-005]).
- Triển khai tầng dịch vụ **Phase 3 (`api/` & `main.py`)**: hệ thống REST API FastAPI với kiểm soát đồng thời lạc quan (`ETag` / `If-Match` `409 Conflict`), bắt buộc `hospital_mrn` cho ca nội trú và gợi ý ghép đợt điều trị `ERCP`, tiêu đề bảo mật `CSP: default-src 'self'` và `Cache-Control: no-store` cho toàn bộ `/api/*` ([FEAT-004]).
- Triển khai động cơ nghiệp vụ y khoa **Phase 2 (`clinical/` & `schemas/`)**: mô hình ca nội soi 4 pha không khóa tuần tự (`EGD`, `COL`, `ERCP`) với 1 tổn thương đại diện lớn nhất kèm tổng hợp toàn ca; kiểm định BBPS (`tổng ≥ 6` và `mỗi đoạn ≥ 2`); khuyến cáo hẹn soi lại ưu tiên `USMSTF_POST_POLYPECTOMY_2020` làm mặc định chính kèm đối chiếu song song `ESGE 2020` & `ESGE ESD 2022` và cảnh báo hội chẩn Ngoại khoa; tính toán KPI tường minh tử số/mẫu số (`CIR`, `BBPS`, `PDR`, `ADR`/`SSLDR` `≥ 45`/`≥ 50` tuổi, thông nhú chọn lọc `ERCP`, biến cố `AGREE 2022` & `PEP` tách riêng ca đang chờ cửa sổ 30 ngày); biểu đồ `Tabular Bernoulli QC-CUSUM` cá nhân (`p0=0.10, p1=0.20, h=2.890372`, khóa `RA-CUSUM = DISABLED_UNVALIDATED_MODEL`); và 3 chế độ xuất dữ liệu `Profile A/B/C` ([FEAT-003]).
- Triển khai tầng lõi **Phase 1 (`core/`)**: cấu hình môi trường fail-closed 3 chế độ (`local_dev_synthetic`, `local_clinical_phi`, `production`), xác thực mật khẩu Argon2id RFC 9106 + cookie phiên `HttpOnly; SameSite=Strict` tự hết hạn 15 phút, cổng bypass 5 chốt an toàn chỉ mở cho dữ liệu giả lập cục bộ, bộ lọc DLP chặn CCCD/SĐT/BHYT/email ở ghi chú tự do, kho JSON nguyên tử (`RLock` + `InterProcessLock` + `fsync` + nhật ký rollback) và chuỗi băm kiểm toán tuyến tính SHA-256 ([FEAT-002]).
- Hoàn tất nghiệm thu bộ khung dự án Day-0 **EndoLog** (`endolog`) theo chuẩn Project Inception Gate (`Rule v2:R47`) với cấu trúc `webapp`, chính sách `Strict Zero-PHI` & `Zero-Image`, Ma trận phân loại tệp ISO 15489-1:2016 và Sổ theo dõi lỗi/tính năng Dual SSoT Schema v3.1 ([FEAT-001]).

### Fixed
- Khắc phục và nghiệm thu `B01`, `B03`, `B04` & `R1–R5` của **Phase 4A** ([BUG-001], [BUG-003]..[BUG-009]): tính động huy hiệu KPI theo cỡ mẫu tối thiểu `kpi_min_sample_size` (`n_min = 20`), chuẩn hóa 100% nhãn tiếng Việt lâm sàng không lộ mã `UPPER_SNAKE_CASE`, gom gọn bố cục điện thoại `390×844` (`firstCaseCardTopY <= 700 px`) và khóa kín bộ kiểm chứng tĩnh màu/emoji trên toàn bộ tệp tĩnh.

### Security
- Khắc phục và nghiệm thu `B02` ([BUG-002]) đồng thời mở rộng cho **Phase 4B**: dọn sạch tức thì toàn bộ DOM ca bệnh, ngăn kéo nhập liệu 4 pha đang mở (kể cả dữ liệu định danh nháp, dòng biến cố `AGREE` và khóa mật khẩu sao lưu), bẫy tiêu điểm `inert`, `sessionStorage` và bộ đếm giờ khi đăng xuất, gặp `401 Unauthorized`, tự khóa 15 phút không thao tác hoặc hết hạn cứng 15 phút; xác thực song song `If-Match` HTTP header và `expected_version` chống ghi đè đồng thời (`409 OCC_VERSION_CONFLICT`).
