# PROJECT CONTEXT — TỪ ĐIỂN NGHIỆP VỤ & HỢP ĐỒNG ĐẶC TẢ DỰ ÁN ENDOLOG

## 1. Thông Số Quản Trị, Phân Quyền & Trạng Thái Hiện Tại (Cập Nhật 31/10/2026)
* **Tên chính thức dự án:** **EndoLog** (`endolog`)
* **Thư mục gốc dự kiến (`project_root`):** `/Users/khuonganvu/.gemini/antigravity/scratch/endolog` (liên kết tiện ích khi được duyệt: `/Users/khuonganvu/Projects/endolog`)
* **Bố cục mã nguồn chuẩn (`webapp` profile):** Backend Python đặt tại `src/endolog/`; giao diện PWA đặt tại `src/endolog/static/`; lưu trữ runtime v1.0 duy nhất bằng `AtomicJsonStore` (không chạy song song PostgreSQL ở v1.0).
* **Superadmin & Quản trị kỹ thuật:** `BSCKII. Vũ Khương An` — Phó Trưởng Khoa Phẫu thuật Đại trực tràng, Bệnh viện Bình Dân
* **Người dùng chính (`Primary Endoscopist`):** `ThS. BSCKI. Nguyễn Bình An` — Bác sĩ Khoa Nội soi Tiêu hóa, Bệnh viện Bình Dân
* **Chính sách Hình ảnh & Quyền hạn:** Không lưu hình ảnh nội soi (`Zero-Image`). Duyệt bộ khung (Gate A), duyệt viết mã tính năng (Gate B) và duyệt triển khai (Gate C) là 3 cổng phê duyệt tách biệt hoàn toàn.

---

## 2. Đặc Tả Lâm Sàng & Hợp Đồng Dữ Liệu Đã Hiệu Đính Sau Crosscheck Vòng 1

1. **Liên kết Dọc 3 Tầng (`patient_uid` → `episode_id` → `case_id`):**
   - Định danh nội bộ ổn định `patient_uid` (UUIDv7, không bao giờ tự động gộp đơn thuần từ họ tên + năm sinh); trường mã hồ sơ bệnh viện `hospital_mrn` là bắt buộc trên 100% ca nội trú (`INPATIENT`) để ghép đợt nhập viện `ERCP` và là tùy chọn có hộp thoại gợi ý xác nhận thủ công trên ca ngoại trú (`OUTPATIENT`).
   - Thứ tự lần thực hiện ERCP trong cùng 1 đợt nhập viện (`ercp_session_index_in_episode`) được tính tất định theo thời điểm thủ thuật `(procedure_start_at, created_at, case_id)` để không bị lệch số khi nhập hồi cứu hoặc sửa ngày giờ.
   - Bản ghi hẹn soi lại (`SURVEILLANCE_RECOMMENDATION`) liên kết hai chiều từ `origin_case_id` sang `fulfilled_by_case_id` khi người bệnh quay lại soi.
2. **Phạm vi 3 Phân nhóm & Tổng hợp Toàn ca Đi kèm 1 `Index Lesion`:**
   - **EGD trọng điểm (`EGD-`):** (a) Ca nghi ngờ ung thư sớm đã bấm sinh thiết hoặc cắt niêm mạc (lưu ý: sinh thiết kìm đơn thuần không bao giờ được coi là cắt triệt căn `Curative R0`, luôn trả trạng thái `NEEDS_PHYSICIAN_REVIEW` để bác sĩ quyết định hướng xử trí); (b) Ca can thiệp cầm máu xuất huyết tiêu hóa trên tách rõ **do vỡ giãn** và **không do vỡ giãn** (Forrest Ia–III).
   - **Đại trực tràng (`COL-`):** Giữ đúng 1 tổn thương chi tiết đại diện (`index_lesion` chọn theo bậc nguy cơ mô học cao nhất, cùng bậc lấy kích thước lớn nhất) kết hợp khối trường phẳng **tổng hợp toàn ca (`whole_case_polyp_summary`)** phân biệt rõ đếm polyp lúc soi (`macroscopic_polyp_count` cho PDR) với kết quả sau GPB đầy đủ (`pathology_completion_status`, `any_confirmed_adenoma`, `confirmed_adenoma_count_bin`, `any_villous_or_hgd_any_lesion`, `any_confirmed_ssl`, `confirmed_ssl_count_bin`, `max_ssl_size_mm`, `any_ssl_with_dysplasia_or_tsa` theo kiểu 3 trạng thái `YES | NO | PENDING_UNKNOWN`).
   - **ERCP chuyên sâu (`ERCP-`):** Tiền căn, CĐHA, xét nghiệm, chỉ định, tình trạng nhú nguyên vẹn (`NATIVE_INTACT` vs đã cắt cơ vòng/stent cũ), tường trình thủ thuật (tách rõ tổng thời gian thủ thuật và thời gian cố gắng thông nhú, phân loại Type nhú Vater, kết quả thông nhú chọn lọc thành công/thất bại, tiêu chuẩn thông nhú khó theo ESGE 2016: > 5 lần chạm nhú, > 5 phút hoặc > 1 lần vào/bơm cản quang ống tụy ngoài ý muốn, kỹ thuật thông nhú/can thiệp), biến chứng sau ERCP và số lần ERCP trong đợt nhập viện.
3. **Tách Bạch Guideline, KPI, Xuất Nghiên Cứu, CUSUM & Đo Công Thái Học:**
   - **Guideline hẹn soi lại:** Tách bảng quyết định riêng cho `USMSTF_POST_POLYPECTOMY_2020` (mặc định chính theo quyết định đã chốt, kèm hiển thị dòng tham chiếu `ESGE_POST_POLYPECTOMY_2020` ở nhóm phân kỳ và cho phép chuyển đổi trong Cấu hình), `ESGE_ESD_2022` (phân biệt `HM1_ONLY` theo dõi tại chỗ với `HIGH_RISK_NON_CURATIVE` bật cảnh báo hội chẩn Ngoại khoa) và `CLINICIAN_DIRECTED` cho EGD sinh thiết / ERCP.
   - **Đoàn hệ ADR / SSLDR & Biến cố bất lợi:** Mặc định lọc đoàn hệ tầm soát/chẩn đoán từ `≥ 45 tuổi` (`ASGE/ACG 2024`, kèm bộ lọc chuyển đổi `≥ 50 tuổi`) và loại ca chờ GPB khỏi mẫu số đã đánh giá. Lưu độc lập phân độ `AGREE 2022` (theo mức can thiệp xử trí) và phân độ viêm tụy sau ERCP `PEP` (ESGE 2020 / Cotton-Atlanta), không tự quy đổi tương đương 1-1; tách rõ `LOST_TO_FOLLOWUP` / `PENDING_WINDOW` khỏi `NO_AE`.
   - **Hợp đồng Export mới (`EndoLog Export Contract v1.0`):** Khai báo tường minh thay đổi có chủ đích so với `surgilog-pro-v2`: Profile A (sao lưu mã hóa AES-256-GCM raw PHI), Profile B (bảng phẳng từng ca đã giả danh hóa dọc bằng khóa HMAC theo `patient_uid` bảo toàn khoảng cách ngày giữa các lần ERCP/soi lại cho SPSS/R — giảm rủi ro tái định danh nhưng không đồng nghĩa ẩn danh tuyệt đối), Profile C (bảng tổng hợp KPI ẩn ô nhỏ `k < 5`).
   - **CUSUM & Công thái học Phase 4:** Phiên bản v1.0 chỉ kích hoạt `Tabular Bernoulli QC-CUSUM` không hiệu chỉnh nguy cơ (chiều thất bại $X_t \in \{0,1\}$, mặc định $p_0=0.10, p_1=0.20, h=\ln(18)\approx 2.890$ cho `CIR` chung và thông nhú chọn lọc `ERCP` nhú nguyên vẹn, kèm preset tầm soát $p_0=0.05, p_1=0.10$); khóa `RA-CUSUM` (`DISABLED_UNVALIDATED_MODEL`). Tốc độ nhập liệu người thật được nghiệm thu trên bộ 5 ca lâm sàng mẫu chuẩn hóa ở cuối Phase 4, tách biệt với ngân sách thao tác chạm của Playwright.
