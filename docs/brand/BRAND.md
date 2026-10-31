# Bộ Nhận Diện Thương Hiệu EndoLog v1 (`Phương Án B · Chàm Khói`)

- **Dự án:** EndoLog (`endolog`) — Hệ thống sổ bộ lâm sàng & đánh giá chất lượng nội soi tiêu hoá
- **Người chọn phương án (`31/10`):** `BSCKII. Vũ Khương An` — Phó Trưởng Khoa Phẫu thuật Đại trực tràng, Bệnh viện Bình Dân (`Superadmin`)
- **Chủ nhiệm chuyên môn (`Primary Endoscopist`):** `ThS. BSCKI. Nguyễn Bình An` — Khoa Nội soi Tiêu hóa, Bệnh viện Bình Dân
- **Phương án màu:** `Phương án B · Chàm khói` (tham chiếu artifact `"Nhận diện EndoLog"`)

---

## 1. Biểu Trưng (`Logo`), Tên Hệ Thống (`Wordmark`) & Phụ Đề

### A. Cấu trúc biểu trưng (`docs/brand/logo/`, `viewBox="0 0 64 64"`)

- **Ý niệm tạo hình:** Vòng sáng đầu ống soi nội soi kết hợp chữ `E`; không gắn logo hoặc tên bệnh viện lên biểu trưng.
- **Mã gốc hình học Mark (`viewBox="0 0 64 64"`):**

```xml
<path d="M48.09 18.5A21 21 0 1 0 48.09 45.5" fill="none" stroke="{MARK}" stroke-width="7" stroke-linecap="round"/>
<path d="M20 32H38" stroke="{MARK}" stroke-width="7" stroke-linecap="round"/>
<circle cx="50" cy="32" r="8.5" fill="{LIGHT}" opacity=".28"/>
<circle cx="50" cy="32" r="4.5" fill="{LIGHT}"/>
```

- **Bộ 4 tệp SVG chuẩn:**
  - `endolog-mark.svg`: `MARK = #475985`, `LIGHT = #90D8E9`
  - `endolog-mark-dark.svg`: `MARK = #B5C4E6`, `LIGHT = #8FD0E1`
  - `endolog-icon.svg`: `<rect width="64" height="64" rx="14" fill="#475985"/>` + biểu trưng đặt trong `<g transform="translate(9.6 9.6) scale(.7)">`, `MARK = #FFFFFF`, `LIGHT = #90D8E9`
  - `favicon.svg`: đồng nhất với `endolog-icon.svg`; ở kích thước `≤ 32 px` bỏ vòng hào quang (`circle r="8.5"`)
- **Bộ 4 tệp PNG xuất từ `endolog-icon.svg`:** `icon-192.png` (`192×192`), `icon-512.png` (`512×512`), `icon-maskable-512.png` (`512×512`, vùng an toàn trung tâm `80%`), `apple-touch-icon.png` (`180×180`).

### B. Wordmark & Dòng phụ đề tiếng Việt

- **Wordmark dựng bằng chữ thật (không vẽ thành ảnh):**
  - `"Endo"`: `Plus Jakarta Sans`, `800`, màu `var(--text-heading)`
  - `"Log"`: `Plus Jakarta Sans`, `800`, màu `var(--primary)`
- **Dòng phụ đề:** `"Hệ thống sổ bộ lâm sàng & đánh giá chất lượng nội soi tiêu hoá"` (`Noto Sans`, `12 px`, `var(--text-muted)`).
- **Quy tắc hiển thị theo thiết bị:**
  - Màn hình đăng nhập và tiêu đề trang trên máy tính: dùng tên đầy đủ kèm dòng phụ đề tiếng Việt.
  - Header điện thoại: chỉ hiện biểu trưng `28 px` (bỏ hào quang `r=8.5` do `≤ 32 px`) + `"EndoLog"`.

---

## 2. Hệ Thống Phông Chữ Tự Host (`100% Self-Hosted`, `OFL`)

- Sao chép trực tiếp từ bộ font variable đã kiểm định của SurgiLog (`6` tệp `*-var.woff2` + `3` giấy phép `OFL*.txt`), tuyệt đối không gọi `fonts.googleapis.com` hay `fonts.gstatic.com` (`CSP: default-src 'self'`).
- `--font-display`: `Plus Jakarta Sans` — chỉ dùng cho tiêu đề `≥ 15 px`, `word-spacing: .06em`.
- `--font-sans`: `Noto Sans` — mọi chữ giao diện, nhãn, bảng, ngày tháng và mã ca (`EGD-YYYY-xxxx`, `COL-YYYY-xxxx`, `ERCP-YYYY-xxxx`).
- `--font-mono`: `JetBrains Mono` — **chỉ** dùng cho chuỗi băm kiểm toán (`audit hash chain`).
- **Thang cỡ chữ:** `12 / 13 / 15 / 16 / 18 / 22 / 28 / 36 px`; ô nhập liệu trên điện thoại bắt buộc `16 px`.

---

## 3. Bảng Token Màu Duy Nhất (`src/endolog/static/css/tokens.css`)

### A. Nền, chữ, thương hiệu và đường viền

| Token | Sáng (`:root` — Mặc định) | Tối (`[data-theme="dark"]`) | Vai trò |
|---|---|---|---|
| `--bg-main` | `#F4F7FC` | `#0D0F15` | Nền trang chính |
| `--bg-card` | `#FFFFFF` | `#15181F` | Nền thẻ & bảng |
| `--bg-sunken` | `#EBEEF7` | `#11141A` | Nền vùng lõm / phụ |
| `--text-heading` | `#192135` | `#FFFFFF` | Tiêu đề & chữ `"Endo"` |
| `--text-main` | `#26292F` | `#E5E8ED` | Chữ giao diện chính & mã ca |
| `--text-muted` | `#60636A` | `#ADB1B9` | Chữ phụ & chú thích |
| `--primary` | `#475985` | `#B5C4E6` | Nhấn thương hiệu (chữ, gạch tab, `"Log"`) |
| `--primary-fill` | `#475985` | `#576B98` | Nền đặc cho nút hành động chính |
| `--on-primary` | `#FFFFFF` | `#FFFFFF` | Chữ trắng trên nền `--primary-fill` |
| `--primary-soft` | `#E2EBFF` | `#222D47` | Nền nhấn chàm nhạt |
| `--border` | `#D8DBE0` | `#30333A` | Đường chia & lưới biểu đồ |
| `--border-strong` | `#83868E` | `#6E7279` | Viền ô nhập (`≥ 3:1`) |
| `--accent-light` | `#90D8E9` | `#8FD0E1` | Chấm sáng logo & dấu vị trí tab đang chọn |
| `--focus-ring` | `#475985` | `#B5C4E6` | Vòng focus bàn phím |

### B. Phân hệ thủ thuật (`EGD / COL / ERCP`)

| Thủ thuật | `--proc-*` (Sáng / Tối) | `--proc-*-text` (Sáng / Tối) | `--proc-*-tint` (Sáng / Tối) |
|---|---|---|---|
| **Dạ dày (`EGD`)** | `#995EB2` / `#C18DD8` | `#6B3A7F` / `#DFBBEF` | `#F7EBFC` / `#2F1F36` |
| **Đại trực tràng (`COL`)** | `#008F90` / `#16BBBC` | `#006263` / `#8ADBDB` | `#DEF6F5` / `#012D2D` |
| **Mật tụy (`ERCP`)** | `#987600` / `#C0A241` | `#684F00` / `#DDCA8E` | `#F6F0DE` / `#2E2609` |

### C. Trạng thái lâm sàng (đồng bộ SurgiLog) & biểu đồ

| Token | Sáng (`:root`) | Tối (`[data-theme="dark"]`) | Ánh xạ nghiệp vụ EndoLog |
|---|---|---|---|
| `--clinical-ned` | `#00692D` | `#8ED69D` | Không biến cố / hoàn tất |
| `--clinical-due` | `#0054A7` | `#99C6FF` | Đến hạn soi lại / theo dõi `14–30` ngày |
| `--clinical-pending` | `#844200` | `#FEAD76` | Chờ GPB |
| `--clinical-urgent` | `#A1111D` | `#FFA8A0` | Cảnh báo hội chẩn Ngoại khoa, biến cố |
| `--clinical-neutral` | `#50585B` | `#B3C0C4` | Mất dấu / chưa đến hạn |
| `--chart-line` | `var(--primary-fill)` | `var(--primary)` | Đường biểu diễn `QC-CUSUM` / chất lượng |
| `--chart-threshold` | `var(--clinical-urgent)` | `var(--clinical-urgent)` | Ngưỡng cảnh báo $h$ |
| `--chart-grid` | `var(--border)` | `var(--border)` | Lưới biểu đồ |

---

## 4. Quy Tắc Áp Dụng Nghiêm Ngặt

- **Độc quyền mã màu:** Mọi màu chỉ được khai báo trong `src/endolog/static/css/tokens.css`; toàn bộ `app.css`, JS và HTML chỉ dùng `var(--…)` (`0` mã hex cứng ngoài `tokens.css`).
- **Không emoji; icon nét tròn:** Tuyệt đối `0` emoji; mọi biểu tượng giao diện là SVG nét (`viewBox="0 0 24 24"`, `stroke-width="2"`, `stroke-linecap="round"`). Viết hoa đầu câu, tiếng Việt đặt trước.
- **Chip thủ thuật & Mã ca:** Chip dùng nền `var(--proc-*-tint)`, chữ `var(--proc-*-text)`, chấm `7 px` màu `var(--proc-*)`, luôn in mã `EGD` / `COL` / `ERCP`. Mã ca (`EGD-YYYY-xxxx`…) dùng chữ `var(--text-main)`, không tô màu.
- **Giới hạn `--accent-light`:** Chỉ dùng cho chấm sáng trên biểu trưng và dấu vị trí dưới tab/mục đang mở; không bao giờ làm chữ hay trạng thái.
- **Ba dấu hiệu đồng thời cho tab/mục đang chọn:** Chữ `var(--primary)` đậm `600` + gạch dưới `2 px` `var(--primary)` + chấm `var(--accent-light)`.
- **Nút hành động chính:** Luôn tô nền đặc `var(--primary-fill)` (cả sáng và tối; không dùng nút viền cho hành động chính; ở nền tối tuyệt đối không dùng `--primary` làm nền nút).
- **Chống nhiễu & Zero-Image:** Không gradient, không `text-shadow` phát sáng, không dùng đỏ/hồng/cam làm màu thương hiệu; không chèn bất kỳ ảnh/video nội soi nào kể cả trang đăng nhập.
- **PWA Manifest & `theme-color`:** `manifest.json` khai báo `theme_color: "#475985"`, `background_color: "#F4F7FC"`; `<meta name="theme-color">` nhận `#475985` ở sáng và `#0D0F15` ở tối.
