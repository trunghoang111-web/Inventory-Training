# Vận hành và báo cáo

## Trước lớp

WCM chốt tên theo kíp/nhóm, người giữ dây chuyền và lịch thi lại. Kho/IT xác nhận lab và quyền. Trainer rà nội dung/đáp án phiên bản áp dụng. Quản trị kiểm số học viên thật, thiếu kíp/scope, lịch trùng và nguồn lực chưa chốt. Không xác nhận đã học hàng loạt chỉ theo số người có mặt.

## Sau mỗi buổi

Trainer chốt điểm danh và lý do vắng. Server tổng hợp điểm; giám khảo hoàn tất quan sát và chữ ký PDA thật. Người chưa đạt có nhiệm vụ học lại gắn với module/lỗi cụ thể và buổi thi lại. WCM xem từng người còn thiếu điều kiện, chủ trì xử lý và hạn. Lỗi critical chỉ được đóng về mặt năng lực khi lượt chính thức mới đạt, vẫn giữ lịch sử lỗi cũ.

## Báo cáo xuất

1. **Theo người:** ID,tên,kíp,workcell,chức danh,vai dự kiến,bản học,tiến độ bài,điểm danh,kết quả gần nhất của từng loại thi,lỗi critical,chữ ký,vai bổ sung,qualified,ngày đạt,đúng hạn,authorized,điều kiện thiếu,buổi kế tiếp,owner.
2. **Theo kíp/workcell:** kế hoạch,ghi danh thật,chưa bắt đầu,học xong,LT đạt,mô phỏng đạt,PDA đạt,qualified,authorized,đúng hạn,vắng,critical chưa đóng,thiếu scope. Không cộng các cột giai đoạn để suy số người.
3. **Học bù:** người,điều kiện thiếu,bài cần ôn,hạn,buổi dự kiến,người hướng dẫn/chấm,sức chứa,đã chốt hay chưa.
4. **Lịch sử:** mọi attempt và snapshot,người chấm,void/lý do,duyệt vai; xuất chỉ trong scope.

App chỉ cần dashboard và tải báo cáo. Không tự gửi email/Chat hoặc mời lịch; chỉ thêm kênh thông báo khi quản lý yêu cầu.

## Sao lưu và thay đổi

IT chốt lịch backup database và bằng chứng, kiểm restore trước lớp đầu và sau thay đổi quan trọng. Tách demo với dữ liệu thật. Để secret trong biến môi trường, không trong CSV/ZIP. Thu hồi tài khoản khi đổi vai/nghỉ việc, giữ lịch sử đã thi. Thời hạn lưu dữ liệu theo quy định ASV, không tự đặt một mốc trong kit.

Quản trị sửa thông tin nhân sự/lịch tương lai nhưng không sửa điểm đã ký để đạt chỉ tiêu. Chấm nhầm cần void có lý do và lượt mới; chỉ dùng cơ chế hiệu chỉnh khác nếu ASV đã chốt chính sách và audit log đầy đủ. Không có nút sửa điểm nhanh mặc định.
