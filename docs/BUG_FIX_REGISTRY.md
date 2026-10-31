# BẢNG TỔNG HỢP LỖI & TÍNH NĂNG MỚI (BUG & FEATURE REGISTRY SCHEMA V3.1)
## Hệ Thống / Dự Án: EndoLog (`endolog`) — Sổ Bộ Nội Soi Tiêu Hóa Bệnh Viện Bình Dân

> 📌 **Quy tắc Quản trị Vòng đời Sản phẩm (Rule v2:R45 [T3-QA] & Rule v2:R47 [T3-DEV]):**
> 1. Mỗi khi hoàn tất bất kỳ việc **SỬA LỖI (BUG)** hoặc **TRIỂN KHAI TÍNH NĂNG MỚI (FEAT)**, bắt buộc cập nhật vào bảng này kèm bằng chứng kiểm tra thực tế.
> 2. Sử dụng chung một chuỗi STT tăng dần liên tục: mã `BUG-xxx` cho sửa lỗi và `FEAT-xxx` cho tính năng mới.
> 3. Cập nhật đồng bộ song hành 100% mã băm SHA-256 giữa 2 tệp độc lập: `docs/BUG_FIX_REGISTRY.md` (Git repo) và `PROJECT_CONTEXT/BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md` (Brain SSoT). Tuyệt đối không dùng symlink.
> 4. Không ghi trạng thái `VERIFIED_CLOSED` hoặc điền ngày đóng / người duyệt khi sự kiện khởi tạo hoặc kiểm thử chưa diễn ra trên thực tế.

---

## 📊 1. THỐNG KÊ TỔNG QUAN

* **Tổng số sự cố & tính năng ghi nhận:** 1
* **Đang xử lý / Dự thảo chờ duyệt (`OPEN`):** 1
* **Đã phong tỏa an toàn (`CONTAINED`):** 0
* **Đã thực thi, chờ nghiệm thu (`FIXED_PENDING_VERIFY`):** 0
* **Đã xác minh hoàn tất (`VERIFIED_CLOSED`):** 0
* **Mở lại sau đóng (`REOPENED`):** 0

---

## 📋 2. MA TRẬN THEO DÕI SỰ CỐ & TÍNH NĂNG (SCHEMA V3.1 — 14 TRƯỜNG BẮT BUỘC)

| STT | Mã định danh (`incident_id`) | Ngày ghi nhận (`discovered_date`) | Commit Link (`fix_commit_hash`) | Phân hệ ảnh hưởng (`affected_scope`) | Tiêu đề tóm tắt | Hiện tượng / Bối cảnh (`symptom`) | Mức độ (`severity`) | Nguyên nhân & Trạng thái RCA (`root_cause` / `rca_status`) | Giải pháp & Build (`fix_action` / `build_version`) | Trạng thái kỹ thuật (`current_status`) | Biên lai xác minh (`evidence_refs`) | Rủi ro tồn dư (`residual_risk`) | Ngày đóng & Người duyệt |
|:---:|:---:|:---:|:---:|:---:|---|---|:---:|:---:|---|:---:|---|---|:---:|
| 1 | `FEAT-001` | 2026-10-31 | `PENDING_INIT` | Khung hệ thống (`Scaffold`) | Khởi tạo bộ khung dự án EndoLog Day-0 | Hạng mục dự thảo khởi tạo không gian làm việc chuẩn hóa 3 trụ cột cho Sổ bộ Nội soi Tiêu hóa cá nhân của ThS. BSCKI. Nguyễn Bình An | N/A | N/A (`N/A`) | Dự kiến tạo cây thư mục `webapp` (`src/`, `tests/`, `docs/`, `PROJECT_CONTEXT/`, `scripts/`, `data/`, `data_backups/`), `AGENTS.md`, Ma trận ISO 15489, Sổ lỗi Dual SSoT Schema v3.1 và `version.md` (`0.0.0-draft`) | `OPEN` | `PENDING_SCAFFOLD_APPROVAL` (chưa tạo thư mục đích; chờ lệnh Gate A & biên lai `docs/scaffolding_receipt.md`) | Chưa thẩm định runtime thực tế (đang ở giai đoạn đặc tả dự thảo Read-only) | `PENDING` (chưa nghiệm thu) |

---

## 📖 3. HƯỚNG DẪN ĐIỀN CHUẨN SCHEMA V3.1
* **Mức độ (`severity`):** `P0 - Critical` | `P1 - High` | `P2 - Medium` | `P3 - Low` | `N/A` (Dành cho `FEAT`).
* **Trạng thái RCA (`rca_status`):** `VERIFIED_ROOT_CAUSE` | `HYPOTHESIS_PENDING_VERIFY` | `UNVERIFIED_ROOT_CAUSE` | `N/A`.
* **Trạng thái kỹ thuật (`current_status`):** `OPEN` | `CONTAINED` | `FIXED_PENDING_VERIFY` | `VERIFIED_CLOSED` | `REOPENED` | `UNVERIFIED_HISTORICAL`.
* **Biên lai xác minh (`evidence_refs`) & Ngày đóng / Người duyệt:** Chỉ điền giá trị nghiệm thu thật sau khi có kết quả kiểm tra độc lập và xác nhận của người có thẩm quyền phê duyệt.
