# Yêu cầu sản phẩm

## Mục tiêu và phạm vi

Theo dõi từng người của132 slot dự kiến, cho phép tăng giảm theo danh sách thực tế.72Line leader+30Group leader+30 feeder là giả định tổng riêng biệt do yêu cầu trước; WCM/PM/Kho/IT/Audit là người hỗ trợ hoặc học thêm nếu được ghi danh. Không tự cộng những người này vào132. Việc app phục vụ cả GL/LL/feeder không có nghĩa mọi người được cấp mọi vai kiểm kê.

Tập trung3nhóm nội dung: chuẩn bị, tiến hành, rà kết quả. Bao phủ học, luyện, thi và theo dõi; không quản lý tồn kho chính thức. Nội dung và ngưỡng đề xuất được đưa sẵn để có thể xây ngay và cho Kho rà chuyên môn trước dùng thật.

## Các màn hình

| Màn hình | Hành vi và dữ liệu |
|---|---|
| Trang người học | Tên, kíp, workcell, phiên bản; tiến độ từng điều kiện; lịch kế tiếp; lỗi cần học lại |
| Bài học | Ảnh+caption, card ngắn, lời dẫn mở rộng, câu củng cố, tiếp tục từ card gần nhất |
| Luyện tập | Không giới hạn lần; giải thích ngay; không ghi thành điểm thi chính thức |
| Thi lý thuyết | Timer server,20 câu theoblueprint, đổi câu và lưu đáp án, xác nhận nộp, tự nộp khi hết giờ |
| Mô phỏng | Rõ PRACTICE/EXAM, mã SIM-ASV, các bước quét/dán/kiểm; ảnh chỉ minh họa; log sự kiện |
| PDA thật | Danh sách được giao, kiểm danh tính,5 trạm/20 mục, lỗi critical, ghi chú và xác nhận người chấm |
| Dashboard | Lọc kíp/workcell/vai; số người thật, không dùng số lượt; nhấp tới từng người thiếu điều kiện |
| Lịch | Buổi/nhóm, ca làm, capacity, người hướng dẫn/chấm, tài nguyên, trạng thái đã/chưa chốt |
| Quản trị | Import có preview, scope, nội dungversion, resetquyền tài khoản, xuất và backup, audit log |

Không tự gửi email/Chat, tạo lịch mời hoặc liên hệ nhân viên khi triển khai. Chỉ xuất danh sách và nội dung để quản lý quyết định nếu có nhu cầu sau.

## Dashboard chính xác

- `active_required_real`: người cóemployee_id hợp lệ,active=true,is_placeholder=false, được ghi danh bắt buộc vào phiên bản hiện hành. Bao gồm chưa học/vắng/chưa thi.
- `trained_qualified`: người trong mẫu số đạt mọi điều kiện ở bản hiện hành. `qualified_rate=trained_qualified/active_required_real`; mẫu số0hiển thịN/A.
- `role_authorized`: đã có duyệt WCM/Kho vềvai+scope+quyền hệ thống sau đào tạo. Đây là chỉ số riêng.
- Không cộng phần trăm điểm của các người. Tổng132chỉ là kế hoạch đối chiếu với số ghi danh thật, không làm mẫu số mặc định.
- Nhóm trạng thái loại trừ nhau để tổng bằngmẫu số: NOT_STARTED → LEARNING → THEORY_PENDING/FAILED → PRACTICE_PENDING → SIM_PENDING/FAILED → HARDWARE_PENDING/FAILED → SPECIAL_PENDING/FAILED → QUALIFIED. Tính theo điều kiện đầu tiên chưa đạt; chi tiết vẫn hiện mọi thiếu sót.
- AUTHORIZED hiển thị thêm nhãn riêng sau QUALIFIED, không cộng thành một người khác. Missing_scope,missing_crew,on_hold,expired_version là cờ cảnh báo, không phải nhóm để cộngtrùng.

Đăng xuất/đổi thiết bị giữ tiến độ trên server. Người mới/chuyển kíp có lịch sử ngày hiệu lực; thay đổi kíp không làm mất điểm cũ, nhưng làm lại lịch tương lai và phạm vi duyệt vai nếu cần.
