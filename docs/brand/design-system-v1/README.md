EndoLog là sổ bộ lâm sàng và đánh giá chất lượng nội soi tiêu hoá của Khoa Nội soi Tiêu hóa – Bệnh viện Bình Dân. Tên đầy đủ: **Hệ thống sổ bộ lâm sàng & đánh giá chất lượng nội soi tiêu hoá**. Người dùng là bác sĩ nội soi, nhập ca ngay sau thủ thuật trên điện thoại, iPad hoặc máy trạm, nên mọi quyết định thiết kế ưu tiên: đọc nhanh, bấm trúng, dịu mắt khi nhìn lâu.

Phương án màu **B · Chàm khói**, BSCKII. Vũ Khương An chốt ngày 31/10/2026. EndoLog cùng họ với SurgiLog Pro (cùng font, cùng màu trạng thái lâm sàng) nhưng có màu thương hiệu riêng.

## Nguyên tắc

1. **Dữ liệu trước, trang trí sau.** Mã ca, ngày, kết quả GPB và hướng xử trí luôn là thứ nổi nhất trên màn hình.
2. **Màu có nghĩa cố định.** Chàm khói = thương hiệu và thao tác. Ba màu thủ thuật = loại thủ thuật. Năm màu `clinical-*` = trạng thái lâm sàng. Không dùng chéo.
3. **Không bao giờ chỉ dựa vào màu.** Chip thủ thuật luôn ghi EGD / COL / ERCP; pill trạng thái luôn có chữ và icon.
4. **Zero-Image.** Không ảnh, không video nội soi ở bất kỳ đâu, kể cả trang đăng nhập và tài liệu giới thiệu.

## Logo

- Biểu tượng: vòng sáng đầu ống soi lồng chữ E (xem nhóm tài sản **Logos**). Dùng nguyên tệp, không vẽ lại.
- Wordmark dựng bằng chữ, không vẽ thành ảnh: `Endo` Plus Jakarta Sans 800 màu `text-heading` + `Log` cùng font màu `primary`. Không dấu cách giữa hai phần.
- Bộ ghép chuẩn (máy tính, đăng nhập): biểu tượng 40 px · wordmark 26–36 px · dòng phụ "Hệ thống sổ bộ lâm sàng & đánh giá chất lượng nội soi tiêu hoá" kiểu `caption` không in hoa, màu `text-muted`.
- Header điện thoại: `endolog-mark-small.svg` 28 px (`mark-mobile`) + "EndoLog", không dòng phụ.
- Khoảng trống quanh biểu tượng ≥ đường kính chấm sáng × 2. Kích thước nhỏ nhất 16 px (favicon).
- Không gắn logo hay tên Bệnh viện Bình Dân vào biểu tượng. Tên khoa/bệnh viện chỉ xuất hiện ở dòng mô tả trang và chân trang.
- Không: đổi màu ngoài các bản có sẵn, thêm bóng, gradient, viền, đặt bản sáng lên nền tối, xoay, kéo méo.

## Màu

**Thương hiệu.** `primary` (#475985 sáng / #B5C4E6 tối) cho chữ tab đang chọn, liên kết, nét logo, phần "Log". Nền nút chính luôn là `primary-fill` với chữ `on-primary`; ở nền tối `primary` quá sáng để làm nền chữ trắng.

**Ánh sáng đầu soi.** `accent-light` chỉ có hai chỗ: chấm sáng trong logo và chấm vị trí dưới tab hoặc mục thanh dưới đang mở. Không làm chữ, không làm trạng thái, không làm nền.

**Nền và chữ.** Trang `bg-main`, thẻ `bg-card`, vùng lõm `bg-sunken`. Chữ `text-heading` / `text-main` / `text-muted`. Viền ô nhập và nút phụ `border-strong`; đường chia `border`.

**Thủ thuật.** Mỗi thủ thuật một bộ 3: `proc-*` (chấm 7 px, đường biểu đồ), `proc-*-text` (chữ chip), `proc-*-tint` (nền chip).

| Mã | Thủ thuật | Sắc |
| --- | --- | --- |
| EGD | Nội soi dạ dày | tím mận |
| COL | Nội soi đại trực tràng | xanh mòng két |
| ERCP | Nội soi mật tụy ngược dòng | vàng mật |

Ba sắc tránh đỏ/hồng (gợi xuất huyết) và tránh 4 sắc trạng thái. Cặp gần nhất khi mô phỏng mù màu lam–vàng là EGD–ERCP (ΔE 5,1), nên chữ mã luôn đi kèm.

**Trạng thái lâm sàng** (giá trị giống SurgiLog):

| Token | Nghĩa trên EndoLog | Icon |
| --- | --- | --- |
| `clinical-ned` | Không biến cố / hoàn tất | check |
| `clinical-due` | Đến hạn soi lại · theo dõi 14–30 ngày | calendar |
| `clinical-pending` | Chờ GPB | clock |
| `clinical-urgent` | Cảnh báo hội chẩn Ngoại khoa · có biến cố | alert |
| `clinical-neutral` | Mất dấu · chưa đến hạn · chưa đủ cỡ mẫu | clock |

**Biểu đồ.** Đường `chart-line`, ngưỡng h `chart-threshold` (nét đứt), lưới `chart-grid`. Biểu đồ theo thủ thuật dùng `proc-*`.

**Tương phản.** 62/62 cặp đạt ở cả hai nền: chữ ≥ 4,5:1 trên mọi nền ghi trong ghi chú token; viền ô nhập, chấm thủ thuật, vòng focus ≥ 3:1.

**Nền tối.** Mặc định nền sáng. Nền tối chỉ bật khi người dùng chọn (`[data-theme="dark"]`), nhớ lựa chọn theo thiết bị.

## Chữ

- **Plus Jakarta Sans** (`font-display`): tiêu đề, số KPI, wordmark. Chỉ từ 15 px, `word-spacing: .06em`.
- **Noto Sans** (`font-sans`): mọi chữ giao diện, bảng, biểu mẫu, ngày, mã ca. Chữ số đều độ rộng nên không cần font mono cho số.
- **JetBrains Mono** (`font-mono`): chỉ chuỗi băm kiểm toán.
- Thang 12 / 13 / 15 / 16 / 18 / 22 / 28 / 36 px. Ô nhập trên điện thoại 16 px (tránh iOS tự phóng to).
- Trong ứng dụng, font tự host (sao từ SurgiLog: 6 tệp woff2 variable latin + vietnamese, giấy phép OFL); không gọi Google Fonts.

## Bố cục và thành phần

- Lề trang 16 px (`space-4`); khoảng giữa khối 24 px; vùng chạm tối thiểu 44 × 44 (`touch-min`).
- Bo góc: chip 6 px, nút/ô nhập/KPI 10 px, thẻ ca và biểu tượng app 14 px, pill 999 px.
- Không gradient, không `text-shadow` phát sáng, không viền màu bên trái thẻ. Bóng chỉ rất nhẹ cho lớp nổi (ngăn kéo, hộp thoại).
- Tab/mục đang chọn có đủ 3 dấu: chữ `primary` 600 + gạch dưới 2 px `primary` + chấm `accent-light`. Chàm khói có độ bão hoà thấp nên một dấu không đủ.
- Mỗi màn hình chỉ một nút đặc (`primary-fill`): hành động chính của màn đó. Trên Nhật ký ca soi đó là **Thêm ca soi**; xuất dữ liệu là nút viền.
- Điện thoại: thanh dưới 3 mục (Nhật ký ca soi · Hẹn soi lại · Chỉ số chất lượng); KPI gọn một hàng để ca đầu tiên nằm trong màn hình đầu.
- Focus bàn phím: vòng `focus-ring` 2 px, cách 2 px.

## Giọng văn

- Viết hoa đầu câu, không Viết Hoa Mọi Từ. Tiếng Việt trước; giữ viết tắt chuẩn: EGD, COL, ERCP, GPB, BBPS, CIR, ADR, SSLDR, PDR, PEP, AGREE, QC-CUSUM, USMSTF, ESGE.
- Không hiện mã nội bộ cho người dùng: `CLINICIAN_DIRECTED_EGD` → "Theo chỉ định bác sĩ"; `USMSTF_POST_POLYPECTOMY_2020` → "USMSTF 2020"; "PEP MILD" → "Viêm tụy sau ERCP mức nhẹ".
- Gọi tên theo việc bác sĩ làm: "Thêm ca soi", "Nhập kết quả GPB", "Hẹn soi lại" — không "Tạo bản ghi", "Submit".
- Chỉ số chất lượng dưới cỡ mẫu tối thiểu ghi "Chưa đủ cỡ mẫu (n < 20)", không "Đạt chuẩn".
- Không hứa kết quả, không ngôn ngữ thi đua: biểu đồ QC-CUSUM luôn kèm câu "Chỉ dùng tự kiểm toán nội bộ, không dùng đánh giá thi đua hay kết luận năng lực."
- Người bệnh hiển thị bằng chữ viết tắt tên + tuổi + giới + 4 số cuối mã hồ sơ (`P.H.K · 63 tuổi (Nam) · ***2603`).
- Không emoji.

## Icon

Icon nét 24 px, stroke 2, đầu tròn (nhóm **Icons**). Trong ứng dụng nhúng inline với `stroke="currentColor"`. Mỗi pill trạng thái có đúng icon ghi ở bảng trạng thái.
