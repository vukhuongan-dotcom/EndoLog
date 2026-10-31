# CaseCard

Thẻ một ca soi trong Nhật ký ca soi và Hẹn soi lại. Dữ liệu trong ví dụ là hư cấu.

- Dòng đầu: ProcedureChip · mã ca · ngày · nội/ngoại trú · một StatusPill (trạng thái nặng nhất) căn phải.
- Thân 3 cột (điện thoại: xếp dọc): Người bệnh & chỉ định · Thủ thuật & tổn thương đại diện · GPB & hướng xử trí. Nhãn cột `caption` in hoa.
- Người bệnh chỉ hiện chữ viết tắt + tuổi + giới + 4 số cuối mã hồ sơ.
- Nguồn khuyến cáo ghi tên ngắn (USMSTF 2020, ESGE 2020, Theo chỉ định bác sĩ), không mã nội bộ.
- Nền `bg-card`, viền `border`, bo `radius-lg`; không viền màu bên trái.
