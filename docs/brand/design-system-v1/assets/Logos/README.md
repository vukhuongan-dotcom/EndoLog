# Logos

Biểu tượng EndoLog: vòng sáng đầu ống soi nhìn vào lòng ống tiêu hoá, mở bên phải để thành chữ E, thanh giữa là nét ngang của chữ E, điểm sáng ở chỗ hở là đèn đầu soi. Hình học gốc trên lưới 64 × 64; không vẽ lại, không kéo méo, không đổi màu ngoài các bản dưới đây.

- `endolog-mark.svg` — bản chính trên nền sáng. Mực `primary` #475985, chấm `accent-light` #90D8E9 kèm quầng sáng 28 %.
- `endolog-mark-dark.svg` — trên nền tối. Mực #B5C4E6, chấm #8FD0E1.
- `endolog-mark-small.svg` — dùng ở ≤ 32 px (header điện thoại 28 px): bỏ quầng sáng r = 8,5.
- `endolog-mark-mono.svg` — một màu `text-heading` #192135 cho in đen trắng, con dấu, văn bản hành chính.
- `endolog-icon.svg` — biểu tượng app (màn hình chính iPhone/iPad, PWA): nền `primary-fill` #475985 bo 14/64, mark trắng, chấm #90D8E9. Xuất PNG 180 / 192 / 512 và bản maskable 512 (vùng an toàn 80 %).
- `endolog-icon-dark.svg` — biểu tượng app khi hệ điều hành ở nền tối: nền #576B98.
- `favicon.svg` — như `endolog-icon.svg`, không quầng sáng.

Tất cả là SVG một lớp, màu viết cứng (không dùng currentColor) vì hiển thị qua `<img>`.
