# Bộ đầu vào Antigravity · Đào tạo kiểm kê Sản xuất ASV 2026

Bộ tài liệu để Antigravity xây ứng dụng đào tạo, kiểm tra và theo dõi năng lực từng người. Đây là dữ liệu và đặc tả xây app, chưa phải ứng dụng đã vận hành.

## Anh làm 3 bước

1. Giải nén toàn bộ ZIP. Tạo/mở project trong Antigravity và thêm thư mục `ASV_Antigravity_Training_Kit` để tác nhân đọc được các file và ảnh.
2. Mở `01_PROMPT_ANTIGRAVITY.md`, sao chép toàn bộ vào yêu cầu xây app. Yêu cầu tác nhân đọc các tài liệu được liệt kê rồi triển khai và chạy kiểm thử. Không chỉ tải riêng prompt mà bỏ dữ liệu.
3. Sau khi có bản chạy thử: nhập danh sách thật qua `templates/employee_import.csv`; Kho/IT kiểm thao tác và môi trường PDA; WCM chốt kíp/nhóm/người chấm; chạy một lớp thử trước khi mở thi chính thức. Xem danh sách cần chốt ở `docs/10_KIEM_TRA_TRUOC_TRIEN_KHAI.md`.

Hướng dẫn Antigravity chính thức: https://antigravity.google/docs/getting-started . Không cần plugin nhập khóa học riêng; tác nhân đọc các file trong thư mục dự án.

## Bộ này có gì?

| Phần | Số lượng / công dụng |
|---|---|
| Bài học lý thuyết | 12 bài, tổng 90 phút, 48 thẻ nội dung ngắn + lời dẫn giảng viên |
| Ảnh | 18 ảnh lấy từ Word +12 minh họa đã tạo cho bộ đào tạo; có mô tả và xuất xứ |
| Thi lý thuyết | 60 câu MCQ; mỗi đề 20 câu/20 phút; đáp án riêng phía máy chủ |
| Thực hành mô phỏng | 10 tình huống chấm điểm +2 tình huống luyện thêm |
| PDA thật | 5 trạm, 20 mục quan sát; có bài A2/PC10 mục và Controller6 mục |
| Kế hoạch 4 kíp | 39 buổi chuẩn bị/học/thi/rà soát/dự phòng; ngày 17–30/11/2026 |
| Danh sách học viên | Mẫu nhập và132 slot dự kiến:72 LL+30 GL+30 feeder; chưa có tên/kíp thật |
| Kiểm soát chất lượng | Đặc tả trạng thái, phân quyền, mô hình dữ liệu, tiêu chí nghiệm thu và script kiểm gói |
| Tài liệu tham chiếu | SOP gốc dạng text, hướng dẫn 2 trang, slide ảnh và file lịch4 kíp |

## Cách hiểu “đạt”

**Học xong → thi đạt lý thuyết → thi đạt mô phỏng → giám khảo xác nhận PDA thật → đạt vai bổ sung nếu cần → WCM/Kho xác nhận phân vai.** App phải cho thấy rõ đang thiếu điều kiện nào, không quy đổi xem bài thành đủ năng lực.

Mục tiêu hoàn tất đợt chính28/11. Hạn chót: trước 00:00 ngày 01/12/2026 giờ Việt Nam. Kiểm kê dự kiến18–27/12; mở lại vẫn phải theo xác nhận Audit Team.

## Nguồn và phần cần chốt

Kỹ thuật kiểm kê bám AG03-WH-092_A người dùng cung cấp (ngày tạo trong nguồn 13/11/2025). Ngưỡng90 điểm, ngân hàng câu hỏi, mô phỏng và thiết kế app là đề xuất triển khai. Không khẳng định đây là bản SOP mới nhất trên hệ thống công ty. Các link tài liệu con trong SOP chưa được cung cấp nội dung nên không giả lập chính xác từng nút WMS.

Lịch và điều kiện thi trong JSON/đặc tả mới này thay các lịch cũ trong ghi chú slide. Không dùng dòng “thi vai chuyên sâu 14/12” từ tài liệu cũ. Toàn bộ đào tạo và sát hạch bắt buộc phải xong trước 01/12.

Thư mục `data/private/` chỉ cho máy chủ và người quản lý nội dung; tuyệt đối không phục vụ như tài nguyên tải xuống của học viên. `references/` cũng không tự động công khai cho mọi tài khoản. Không có dữ liệu tồn thật, mật khẩu hay kết quả đỗ giả trong bộ này.

Kiểm tra dữ liệu trước xây app: `python3 scripts/validate_pack.py` từ thư mục gốc. Hướng dẫn chi tiết các luồng ở `docs/`.
