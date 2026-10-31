Nguồn chuẩn: Design System EndoLog v1 (31/10/2026), BSCKII. Vũ Khương An chốt.

- **Link tham chiếu nguồn chuẩn:** https://claude.ai/artifact/FDfuaKSAeLBwSv32zy4GrW
- **Gói tệp chuẩn lưu trữ nguyên bản:** `docs/brand/design-system-v1/` (không chỉnh sửa)
- **Dự án:** EndoLog (`endolog`) — **Hệ thống sổ bộ lâm sàng & đánh giá chất lượng nội soi tiêu hoá**
- **Người chọn phương án (`31/10/2026`):** `BSCKII. Vũ Khương An` — Phó Trưởng Khoa Phẫu thuật Đại trực tràng, Bệnh viện Bình Dân (`Superadmin`)
- **Chủ nhiệm chuyên môn (`Primary Endoscopist`):** `ThS. BSCKI. Nguyễn Bình An` — Khoa Nội soi Tiêu hóa, Bệnh viện Bình Dân
- **Phương án màu:** **B · Chàm khói** (cùng họ font & trạng thái lâm sàng với SurgiLog Pro, màu thương hiệu riêng)

---

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

### Danh mục 7 tệp SVG & 4 tệp PNG chính thức

- `endolog-mark.svg` (`docs/brand/logo/` & `src/endolog/static/icons/`) — bản chính trên nền sáng (`#475985`, chấm `#90D8E9` kèm quầng sáng `r=8.5`, `opacity=.28`).
- `endolog-mark-dark.svg` (`docs/brand/logo/` & `src/endolog/static/icons/`) — trên nền tối (`#B5C4E6`, chấm `#8FD0E1`).
- `endolog-mark-small.svg` (`docs/brand/logo/` & `src/endolog/static/icons/`) — dùng ở `≤ 32 px` (header điện thoại `28 px`): bỏ quầng sáng `r=8.5`.
- `endolog-mark-mono.svg` (`docs/brand/logo/` & `src/endolog/static/icons/`) — một màu `#192135` không quầng cho in đen trắng, con dấu, văn bản hành chính.
- `endolog-icon.svg` (`docs/brand/logo/` & `src/endolog/static/icons/`) — biểu tượng ứng dụng nền `#475985` bo `rx="14"`, mark `#FFFFFF`, chấm `#90D8E9` (xuất 4 PNG: `apple-touch-icon.png` `180×180`, `icon-192.png` `192×192`, `icon-512.png` `512×512`, `icon-maskable-512.png` `512×512` vùng an toàn `80%`).
- `endolog-icon-dark.svg` (`docs/brand/logo/`) — biểu tượng ứng dụng khi hệ điều hành ở nền tối (nền `#576B98`, chấm `#8FD0E1`). Do đặc tả W3C Web App Manifest hiện hành trên Chromium/Safari chưa hỗ trợ khóa `color_scheme: "dark"` trên từng phần tử `"icons"`, tệp được lưu chuẩn tại `docs/brand/logo/endolog-icon-dark.svg` mà không chèn trường phi chuẩn vào `src/endolog/static/manifest.json`.
- `favicon.svg` (`docs/brand/logo/` & `src/endolog/static/icons/`) — như `endolog-icon.svg`, bỏ quầng sáng `r=8.5`.

## Màu

### A. Nền, chữ, thương hiệu và đường viền (`src/endolog/static/css/tokens.css`)

| Token | Sáng (`:root` — Mặc định) | Tối (`[data-theme="dark"]`) | Vai trò |
|---|---|---|---|
| `--bg-main` | `#F4F7FC` | `#0D0F15` | Nền trang chính |
| `--bg-card` | `#FFFFFF` | `#15181F` | Nền thẻ, bảng, header |
| `--bg-sunken` | `#EBEEF7` | `#11141A` | Vùng lõm: tiêu đề cột bảng, ô phụ, khu lọc |
| `--text-heading` | `#192135` | `#FFFFFF` | Tiêu đề, số KPI, phần `"Endo"` |
| `--text-main` | `#26292F` | `#E5E8ED` | Chữ giao diện chính & mã ca |
| `--text-muted` | `#60636A` | `#ADB1B9` | Chữ phụ, dòng mô tả, nhãn trường |
| `--primary` | `#475985` | `#B5C4E6` | Chàm khói — chữ tab đang chọn, liên kết, gạch tab, `"Log"`, nét logo (không làm nền nút ở tối) |
| `--primary-fill` | `#475985` | `#576B98` | Nền đặc nút hành động chính, đường biểu đồ (sáng), nền biểu tượng app |
| `--on-primary` | `#FFFFFF` | `#FFFFFF` | Chữ và icon trên `--primary-fill` |
| `--primary-soft` | `#E2EBFF` | `#222D47` | Nền nhấn chàm nhạt (lọc đang chọn) |
| `--border` | `#D8DBE0` | `#30333A` | Đường chia, viền thẻ, lưới biểu đồ |
| `--border-strong` | `#83868E` | `#6E7279` | Viền ô nhập, nút phụ (`≥ 3:1`) |
| `--accent-light` | `#90D8E9` | `#8FD0E1` | Chỉ cho chấm sáng logo và chấm vị trí dưới tab/mục đang mở |
| `--focus-ring` | `#475985` | `#B5C4E6` | Vòng focus bàn phím `2 px`, cách `2 px` |

### B. Phân hệ thủ thuật (`EGD / COL / ERCP`)

| Mã | Thủ thuật | `--proc-*` (Sáng / Tối) | `--proc-*-text` (Sáng / Tối) | `--proc-*-tint` (Sáng / Tối) |
|---|---|---|---|---|
| `EGD` | Nội soi dạ dày | `#995EB2` / `#C18DD8` | `#6B3A7F` / `#DFBBEF` | `#F7EBFC` / `#2F1F36` |
| `COL` | Nội soi đại trực tràng | `#008F90` / `#16BBBC` | `#006263` / `#8ADBDB` | `#DEF6F5` / `#012D2D` |
| `ERCP` | Nội soi mật tụy ngược dòng | `#987600` / `#C0A241` | `#684F00` / `#DDCA8E` | `#F6F0DE` / `#2E2609` |

### C. Trạng thái lâm sàng (đồng bộ SurgiLog) & biểu đồ

| Token | Sáng (`:root`) | Tối (`[data-theme="dark"]`) | Nghĩa trên EndoLog | Icon |
|---|---|---|---|---|
| `--clinical-ned` | `#00692D` | `#8ED69D` | Không biến cố / hoàn tất | `check` |
| `--clinical-due` | `#0054A7` | `#99C6FF` | Đến hạn soi lại · theo dõi 14–30 ngày | `calendar` |
| `--clinical-pending` | `#844200` | `#FEAD76` | Chờ GPB | `clock` |
| `--clinical-urgent` | `#A1111D` | `#FFA8A0` | Cảnh báo hội chẩn Ngoại khoa · có biến cố | `alert` |
| `--clinical-neutral` | `#50585B` | `#B3C0C4` | Mất dấu · chưa đến hạn · chưa đủ cỡ mẫu | `clock` |
| `--chart-line` | `var(--primary-fill)` | `var(--primary)` | Đường chính biểu đồ chất lượng / QC-CUSUM | — |
| `--chart-threshold` | `var(--clinical-urgent)` | `var(--clinical-urgent)` | Ngưỡng cảnh báo $h$ (nét đứt) | — |
| `--chart-grid` | `var(--border)` | `var(--border)` | Lưới tọa độ biểu đồ | — |

## Chữ

- **Plus Jakarta Sans** (`--font-display`): tiêu đề, số KPI, wordmark. Chỉ từ `15 px`, `word-spacing: .06em`.
- **Noto Sans** (`--font-sans`): mọi chữ giao diện, bảng, biểu mẫu, ngày, mã ca (`tabular-nums`).
- **JetBrains Mono** (`--font-mono`): chỉ chuỗi băm kiểm toán (`audit hash chain`).
- Thang cỡ chữ: `12 / 13 / 15 / 16 / 18 / 22 / 28 / 36 px`; ô nhập trên điện thoại bắt buộc `16 px`.
- Tự host `100%` (`6` tệp `*-var.woff2` giấy phép `OFL` sao từ SurgiLog); không gọi Google Fonts (`CSP: default-src 'self'`).

## Bố cục và thành phần

- **Khoảng cách (`spacing`):** `--space-1: 4px` · `--space-2: 8px` · `--space-3: 12px` · `--space-4: 16px` · `--space-6: 24px` · `--space-8: 32px`.
- **Bo góc (`radius`):** `--radius-sm: 6px` (chip thủ thuật) · `--radius-md: 10px` (nút, ô nhập, thẻ KPI) · `--radius-lg: 14px` (thẻ ca, biểu tượng app) · `--radius-pill: 999px` (pill trạng thái).
- **Kích thước chuẩn (`size`):** `--touch-min: 44px` · `--mark-mobile: 28px` · `--mark-desktop: 40px` · `--proc-dot: 7px`.
- Không gradient, không `text-shadow` phát sáng, không viền màu bên trái thẻ. Bóng nhẹ chỉ dùng cho lớp nổi (ngăn kéo, hộp thoại, trình đơn thả).
- Tab/mục đang chọn có đủ 3 dấu: chữ `primary` `600` + gạch dưới `2 px` `primary` + chấm `5 px` `accent-light`, kèm `aria-current="page"`.
- Mỗi màn hình chỉ một nút đặc (`--primary-fill`): trên Nhật ký ca soi đó là **Thêm ca soi**; xuất dữ liệu và tác vụ phụ trên thẻ dùng nút viền (`el-btn--secondary`) hoặc nút nhẹ (`el-btn--ghost`).

## Giọng văn

- Viết hoa đầu câu, không Viết Hoa Mọi Từ. Tiếng Việt trước; giữ viết tắt chuẩn: EGD, COL, ERCP, GPB, BBPS, CIR, ADR, SSLDR, PDR, PEP, AGREE, QC-CUSUM, USMSTF, ESGE.
- Không hiện mã nội bộ cho người dùng: `CLINICIAN_DIRECTED_EGD` → "Theo chỉ định bác sĩ"; `USMSTF_POST_POLYPECTOMY_2020` → "USMSTF 2020"; "PEP MILD" → "Viêm tụy sau ERCP mức nhẹ".
- Gọi tên theo việc bác sĩ làm: "Thêm ca soi", "Nhập kết quả GPB", "Hẹn soi lại" — không "Tạo bản ghi", "Submit".
- Chỉ số chất lượng dưới cỡ mẫu tối thiểu ghi "Chưa đủ cỡ mẫu (n < 20)", không "Đạt chuẩn".
- Không hứa kết quả, không ngôn ngữ thi đua: biểu đồ QC-CUSUM luôn kèm câu "Chỉ dùng tự kiểm toán nội bộ, không dùng đánh giá thi đua hay kết luận năng lực."
- Người bệnh hiển thị bằng chữ viết tắt tên + tuổi + giới + 4 số cuối mã hồ sơ (`P.H.K · 63 tuổi (Nam) · ***2603`).
- Không emoji.

## Icon

- Bộ biểu tượng nhúng inline SVG trong ứng dụng: **Feather / Lucide** chuẩn hóa `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `stroke-width="2"`, `stroke-linecap="round"`, `stroke-linejoin="round"` (đúng quy cách `24 / stroke 2 / round` của Design System v1).
- Mỗi pill trạng thái (`StatusPill`) gắn đúng cặp trạng thái + icon cố định: `urgent + alert` · `pending + clock` · `due + calendar` · `ned + check` · `neutral + clock`.
