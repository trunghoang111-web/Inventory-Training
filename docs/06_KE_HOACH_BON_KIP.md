# Kế hoạch bốn kíp trước 01/12/2026

Ngày giờ chính xác nằm trong `data/schedule.json`, lịch làm việc nằm trong `data/shift_calendar.json`. Đây là kế hoạch; tên người hướng dẫn/chấm và danh sách học viên còn phải chốt.

| Kíp | Lý thuyết và thi | Thực hành và thi mô phỏng | Thi PDA thật, thi lại, vai bổ sung |
|---|---|---|---|
| B |17/11|18/11|19/11|
| D |20/11|21/11|22/11|
| A |23/11|24/11|25/11|
| C |26/11|27/11|28/11|

Tạm tính33 người/kíp, N1=17,N2=16; thay bằng roster thật trước xếp lớp. Mỗi người học lý thuyết120 phút và thực hành180 phút theo nhóm; thi PDA thật gọi riêng theo slot25 phút. WCM bố trí người giữ dây chuyền, không rút cả kíp cùng lúc. Nếu phân bổ người lệch kíp, app kiểm lại sức chứa; không tự bỏ người khỏi danh sách. Mức22 người/lớp chỉ dùng khi đủ trạm và người hướng dẫn.

## Giờ chính

- Ngày1: N1 08:30–10:30; N2 14:00–16:00; ôn/thi lại lý thuyết16:15–16:45.
- Ngày2: N1 08:30–11:30; N2 13:30–16:30. Mở10 phút+4 trạm×35 phút+chuyển10 phút+thi mô phỏng15 phút+phản hồi5 phút.
- Ngày3 sáng:5 làn×8 lượt, tối đa40 người. Giờ bắt đầu:08:30,08:55,09:20,09:45,10:20,10:45,11:10,11:35.
- Ngày3 chiều13:30–18:00: thi lại và vai bổ sung. Có5 người chấm, nghỉ luân phiên, giữ1.200 phút-người hiệu dụng.

Tải chiều=25×người thi lại cơ bản+20×người A2/PC+15×người Controller. Tổng phút phù hợp mới là điều kiện đầu tiên; còn phải kiểm slot, người chấm và thiết bị không trùng. Không hiểu5 làn là5 người chấm chia mỗi người một trạm cho40 người cùng làm.

Ngày16/11: chuẩn hóa người hướng dẫn/chấm và chạy lab. Cần đủ người hỗ trợ cuối tuần21,22,28/11. Sau mỗi buổi, rà người thiếu điều kiện theo tên và xếp thi lại ngay ngày3của kíp, không dồn toàn bộ về30/11.

## Học bù29–30/11

Kíp B làm ngày, A làm đêm, C/D nghỉ. B có thể học bù ban ngày29/11 và thi30/11. Chỉ ghép C/D nếu đã thống nhất lịch cụ thể; không tự xếp học vào ngày nghỉ.

A có lịch bù ca đêm có điều kiện:29/11 học lý thuyết20:30–22:30; thực hành22:45–01:45ngày 30/11. Thi PDA thật30/11từ20:30–22:30, thi lại/vai bổ sung22:30–23:30. Chỉ kích hoạt khi có đủ đội hướng dẫn/chấm ca đêm. Nhóm bù tối đa20 người. AU-RE chỉ có250 phút-người hiệu dụng sau dự phòng; người thiếu bài chuyên sâu phải được xếp sớm, không ký đạt thay.

Mục tiêu xong đợt chính28/11. Hạn chót trước 00:00ngày 01/12 giờ Việt Nam. Ký ngày 01/12 vẫn trễ dù thuộc ca bắt đầu30/11.

Dashboard hằng ngày cần cho thấy: số ghi danh thật/kế hoạch, chưa bắt đầu, hoàn tất bài, LT đạt, mô phỏng đạt, PDA đạt, thiếu bài vai, fail critical, thiếu chữ ký, chưa có scope, trùng lịch/vượt sức chứa. Tháng12 có thể nhắc quy trình ngắn5–10 phút; không dời sát hạch bắt buộc sang tháng12.
