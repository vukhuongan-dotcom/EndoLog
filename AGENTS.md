# AGENTS.md — QUY CHUẨN KỸ THUẬT & QUY TẮC NỘI BỘ DỰ ÁN ENDOLOG
> 📌 **Nguyên tắc nạp quy tắc tự động:** Tệp này được Antigravity tự động phát hiện và nạp khi hoạt động bên trong thư mục dự án (theo tài liệu hệ thống `agy-customizations/docs/rules.md`). Tệp áp dụng cho thư mục gốc và toàn bộ các thư mục con của dự án.
> ⚖️ **Thứ tự ưu tiên bất biến:** Mọi quy tắc trong tệp này thuộc cấp độ Cục bộ Dự án (Local Project Rules). Nếu có bất kỳ xung đột nào với Bộ Quy tắc Toàn cục của Antigravity (`rules.md` Tầng 1–5: Approval Gate `v2:R01`, Rule Auto-Audit Gate `v2:R02`, Local-First `v2:R03`, Performance Policy Tầng 4, Runtime Primitives Tầng 5), **quy tắc toàn cục luôn có giá trị tối thượng**.

---

## 1. MỤC TIÊU, ĐỊNH DANH, BỐ CỤC MÃ NGUỒN & MÔ HÌNH NGƯỜI DÙNG
* **Tên dự án:** **EndoLog** (`endolog`) — Hệ Thống Sổ Bộ Lâm Sàng & Đánh Giá Chất Lượng Nội Soi Tiêu Hóa
* **Đơn vị ứng dụng:** Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân
* **Mô hình người dùng & Phân quyền cốt lõi:**
  - **Superadmin & Thẩm quyền phê duyệt hệ thống:** `BSCKII. Vũ Khương An` — Phó Trưởng Khoa Phẫu thuật Đại trực tràng, Bệnh viện Bình Dân (quản trị hệ thống, cấu hình, kiểm toán, sao lưu/xuất dữ liệu và độc quyền xóa/gộp hồ sơ bảo vệ dữ liệu).
  - **Người dùng chính (`Primary Endoscopist`):** `ThS. BSCKI. Nguyễn Bình An` — Bác sĩ Khoa Nội soi Tiêu hóa, Bệnh viện Bình Dân (sổ bộ thiết kế phục vụ riêng cho `ThS. BSCKI. Nguyễn Bình An` ghi nhận cuốn chiếu 4 pha không khóa tuần tự và theo dõi chất lượng nội soi cá nhân).
* **Công nghệ & Bố cục chuẩn trong `src/`:** Python 3.12, FastAPI, Pydantic v2, lưu trữ runtime v1.0 duy nhất bằng `AtomicJsonStore` (`src/endolog/core/persistence.py`, 2-tier RWLock + Write-Ahead Rollback Journal; không duy trì runtime PostgreSQL song song ở v1.0), giao diện Vanilla JS ES6+ PWA đặt tại `src/endolog/static/` theo chuẩn `med-web v2.0`.

---

## 2. QUY CHUẨN LƯU TRỮ, MA TRẬN MÔI TRƯỜNG FAIL-CLOSED & ĐỒNG BỘ SSoT
1. **Tuân thủ Bảng Ma Trận Phân Loại Tệp Tin (`docs/file_classification_matrix.md` & `PROJECT_CONTEXT/FILE_CLASSIFICATION_MATRIX.md`):**
   - Mọi tệp tin tạo mới trong dự án bắt buộc nằm trong đúng thư mục được phân loại theo chuẩn ISO 15489-1:2016 (`CLS-01` đến `CLS-07`).
   - Tuyệt đối nghiêm cấm đặt tệp dữ liệu tạm hoặc tệp nghiệp vụ rời rạc ở thư mục gốc (Root Hygiene).
2. **Ma trận 3 Chế độ Môi trường & Ranh giới Fail-Closed cho Local Bypass (`Rule v2:R41 [T3-DEV]` kết hợp Bảo vệ PHI):**
   - **Mặc định Fail-Closed:** Nếu biến môi trường `ENDOLOG_ENV` bị thiếu, rỗng hoặc sai giá trị hợp lệ, ứng dụng từ chối bật cơ chế tự đăng nhập và yêu cầu xác thực đầy đủ.
   - **Chế độ 1 — `local_dev_synthetic` (Phát triển & Kiểm thử Playwright trên dữ liệu giả lập):** Chỉ cho phép `/api/auth/local-bypass` khi thỏa đồng thời cả 5 điều kiện: (a) `ENDOLOG_ENV=local_dev_synthetic` kèm cờ opt-in tường minh `ENDOLOG_ENABLE_DEV_BYPASS=1`; (b) thư mục dữ liệu bị khóa cứng vào `data_synthetic_dev/` (từ chối khởi chạy nếu trỏ vào thư mục có dấu `.phi_vault_marker` hoặc `data_real_clinical/`); (c) tiến trình chỉ lắng nghe trên loopback `127.0.0.1` / `::1` (từ chối nếu bind `0.0.0.0`); (d) địa chỉ socket trực tiếp của client là `127.0.0.1` / `::1` và không có bất kỳ header chuyển tiếp proxy nào (`X-Forwarded-For`, `Forwarded`, `X-Real-IP`); (e) `Host`/`Origin` chỉ nhận `localhost` hoặc `127.0.0.1` (từ chối `.local` mDNS và IP LAN với `HTTP 403 Forbidden`).
   - **Chế độ 2 — `local_clinical_phi` (Sử dụng dữ liệu lâm sàng thật trên máy cục bộ):** Trỏ vào `data_real_clinical/` (`chmod 0700`), khóa cứng `/api/auth/local-bypass` (`HTTP 403 Forbidden`), bắt buộc đăng nhập Argon2id + JWT HS256 và tự ngắt phiên sau 15 phút không thao tác.
   - **Chế độ 3 — `production` (Triển khai máy chủ):** Bắt buộc HTTPS/TLS, từ chối khởi chạy nếu còn khóa mặc định dev, kích hoạt đầy đủ Argon2id RFC 9106, JWT HS256, RBAC, phiên 15 phút và khóa chặt `/api/auth/local-bypass` (`HTTP 403 Forbidden`).
3. **Chuẩn Danh xưng Y khoa & Tên Khoa Phòng (`Rule v2:R37`, `v2:R38`, `v2:R39`):**
   - 100% học vị bác sĩ chuyên khoa dùng số La Mã và có dấu cách sau dấu chấm học vị trước (`BSCKII. Vũ Khương An`, `ThS. BSCKI. Nguyễn Bình An`), nghiêm cấm dùng số Ả Rập (`CK1`, `CK2`) hoặc viết dính liền không dấu cách.
   - Luôn ghi đầy đủ tên chính thức: `Khoa Nội soi Tiêu hóa`, `Khoa Ngoại Tiêu hóa`, `Khoa Phẫu thuật Đại trực tràng`.

---

## 3. CHÍNH SÁCH BẢO VỆ DỮ LIỆU CÁ NHÂN (ZERO-PHI TRÊN 5 TẦNG TRÌNH DUYỆT) & KHÔNG LƯU ẢNH
1. **Định hướng tuân thủ pháp lý:** Thiết kế hướng tới đáp ứng các yêu cầu bảo vệ dữ liệu cá nhân nhạy cảm của Luật Khám bệnh, chữa bệnh số 15/2023/QH15, Luật Bảo vệ Dữ liệu Cá nhân số 91/2025/QH15 và Nghị định số 356/2025/NĐ-CP.
2. **Chính sách Không lưu trữ hình ảnh (`Strict Zero-Image Policy`):**
   - Hệ thống **EndoLog** chỉ lưu trữ biến số cấu trúc; không tải lên hay lưu trữ ảnh chụp hoặc video nội soi nhằm triệt tiêu nguy cơ lộ định danh bệnh nhân in trên khung hình máy soi.
3. **Kiểm soát PHI trên toàn bộ 5 tầng lưu trữ trình duyệt & PWA:**
   - `localStorage`: Chỉ lưu cấu hình giao diện (`theme`, `font_scale`), `0` trường bệnh nhân hoặc token.
   - `sessionStorage`: Chỉ lưu bộ lọc enum tạm thời của phiên giao diện, xóa sạch khi đăng xuất, `0` trường PHI.
   - `IndexedDB`: Cấm khởi tạo (`0` object stores) ở phiên bản v1.0.
   - `Service Worker & Cache Storage`: Chỉ cache tĩnh theo allowlist (`/fonts/*.woff2`, `/css/*.css`, `/js/*.js`, `/icons/*.svg`); mọi đường dẫn `/api/*` bắt buộc đi qua `NetworkOnly`, cấm ghi vào Cache Storage.
   - `HTTP Cache`: Mọi phản hồi `/api/*` bắt buộc gắn `Cache-Control: no-store, no-cache, must-revalidate, private`, `Pragma: no-cache`, `Expires: 0`; khi đăng xuất hoặc hết hạn phiên 15 phút phải xóa sạch DOM chứa dữ liệu ca bệnh trên màn hình.
4. **Bảo vệ mã khóa & Hạ tầng tự chủ (`Self-Hosted Mandate`):**
   - Nghiêm cấm commit dữ liệu thật (`data*/`), khóa bí mật hoặc tệp `.env` vào Git. Tự host 100% phông chữ `.woff2` và tài nguyên tĩnh kèm `Content-Security-Policy: default-src 'self'`.

---

## 4. QUY CHUẨN GHI NHẬN SỰ CỐ, TÍNH NĂNG MỚI & PHIÊN BẢN SẢN PHẨM (RULE v2:R45 & v2:R47)
1. **Ranh giới Phê duyệt 3 Cổng độc lập (`Rule v2:R01` & `Rule v2:R47 §3`):**
   - Phê duyệt tạo bộ khung (Gate A — Scaffold) chỉ cho phép tạo cây thư mục và các tệp quản trị Day-0, xuất biên lai `docs/scaffolding_receipt.md` rồi dừng lại; việc viết mã tính năng (Gate B) và triển khai máy chủ (Gate C) đều phải có lệnh phê duyệt riêng biệt.
2. **Ghi nhận trung thực theo bằng chứng thật trong cặp Sổ lỗi Dual SSoT (Cấm symlink):**
   - Duy trì đồng bộ SHA-256 giữa `docs/BUG_FIX_REGISTRY.md` và `PROJECT_CONTEXT/BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md` theo Schema v3.1 (14 trường).
   - Tuyệt đối không ghi trạng thái `VERIFIED_CLOSED` hoặc điền ngày đóng / tên người duyệt khi chưa có bằng chứng kiểm tra thực tế và nghiệm thu thật.
3. **Duy trì Sổ Lịch sử Phiên bản Sản phẩm (`version.md`):**
   - Tuân thủ Keep a Changelog 1.1.0 & SemVer 2.0.0 (`MAJOR.MINOR.PATCH`), giai đoạn khởi tạo mở mục `## [Unreleased]`.
