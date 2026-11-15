# Quy tắc đánh giá và trạng thái năng lực

Đây là ngưỡng đào tạo đề xuất cho ASV 2026, không phải ngưỡng ghi trong SOP. Chính sách đã xuất bản phải được áp dụng nhất quán; thay đổi tạo phiên bản mới.

## Các điều kiện theo thứ tự

1. **Học lý thuyết:** xem đủ các thẻ của 12 bài và trả đúng câu củng cố. Trả sai được ôn lại; kết quả củng cố không thay điểm thi. Học tập trung có điểm danh do người hướng dẫn xác nhận.
2. **Thi lý thuyết:**20 câu/20 phút,5 điểm/câu. Chọn một câu từ mỗi pool CR_FREEZE, CR_INDEPENDENCE, CR_STICKER, CR_RELEASE; chọn hai câu từ mỗi trong tám pool G_*. Tổng20 câu. Đạt khi điểm≥90 và cả bốn câu critical đều đúng. Không trả lời tính0.
3. **Thực hành có hướng dẫn:** hoàn tất bốn trạm và được điểm danh. Có thể luyện mô phỏng trước; thi mô phỏng chính thức chỉ mở sau lý thuyết đạt và buổi thực hành hoàn tất.
4. **Thi mô phỏng:**10 case/15 phút,10 điểm/case. Đạt khi≥90 và không có lỗi critical. P01/P02 chỉ luyện thêm, không tính điểm. Mô phỏng đánh giá quyết định và luồng thao tác, không chứng nhận kỹ năng cầm máy thật.
5. **PDA thật:**25 phút/người;20 mục×5 điểm. Đạt khi≥90, mọi mục critical đúng, không còn mục chưa quan sát, có người chấm hợp lệ và chữ ký/biên bản quan sát. Bộ dữ liệu của bước B/C phải do người khác chuẩn bị, không tự kiểm dữ liệu mình vừa tạo.
6. **Vai bổ sung:** A2 hoặc PC cần bài A2_PC,10 mục×5 điểm, đạt≥45 và đúng mọi critical. Controller cần6 mục×5 điểm, đạt≥25 và đúng mọi critical. Chưa đạt bài tương ứng thì chưa đủ điều kiện giao vai.
7. **Kết luận:** QUALIFIED khi đạt mọi điều kiện của phiên bản hiện hành, đủ bài và buổi bắt buộc. ROLE_AUTHORIZED là nhãn riêng sau khi WCM/Kho xác nhận vai, phạm vi và quyền hệ thống. App ghi nhận phê duyệt, không cấp quyền WMS.

Người học từ xa vẫn cần buổi thực hành thật được xác nhận. Có thể tạo buổi bù cá nhân; không bỏ điều kiện thực hành chỉ vì điểm quiz cao.

## Bài viết tùy chọn

`data/private/optional_written_exam.json` có10 câu thi giấy, mặc định tắt. Nếu chọn thay MCQ, chốt chính sách trước đợt: chấm0/5/10, câu critical phải10, tổng≥90 và có người chấm ký. Không mặc định bắt thi cả hai; không chọn điểm cao hơn giữa hai kiểu để né lỗi.

## Lượt thi và thời gian

Luồng trạng thái: CREATED → IN_PROGRESS → SUBMITTED → GRADED; VOIDED dùng cho lượt bị hủy có lý do. Chỉ một lượt chính thức đang mở cho mỗi người/loại/bản học. Đề, thứ tự lựa chọn, đáp án, rubric và chính sách được lưu snapshot lúc bắt đầu.

Hết giờ, server tự nộp phần đã lưu; câu hoặc case chưa làm=0. Mất mạng ở client không dừng thời gian server. Không nhận sự kiện bổ sung sau hạn. Hỏng môi trường khiến không thể sát hạch phải void có lý do và xếp lượt mới, không tự đổi thành pass.

Thời hạn là exclusive `2026-12-01T00:00:00+07:00`. Nộp23:59:59ngày 30/11 là trước hạn; nộp đúng00:00ngày 01/12 là trễ. Lưu UTC, hiển thị giờ Việt Nam. Không cho mở đề khi không còn đủ thời lượng chuẩn trước hạn. Với đề đang mở, `expires_at=min(start+duration,deadline_exclusive)` và không âm thầm kéo dài sang ngày 01/12. PDA thật và chữ ký cũng phải hoàn tất trước hạn.

Luyện không giới hạn số lần. Thi lại chính thức cần học lại theo lỗi và buổi được phân công, tạo attempt mới, giữ toàn bộ lịch sử. Ưu tiên câu ít gặp nhưng vẫn đủ blueprint; không hứa đề hoàn toàn khác khi mỗi pool critical chỉ có ba biến thể.

## Kết quả hiện hành

- Dùng lượt chính thức đã chấm gần nhất, không void, của đúng người/loại/phiên bản. Không ghép điểm cao nhất hoặc các câu critical từ nhiều lượt.
- Pass rồi luyện trượt: giữ pass. Pass rồi thi lại chính thức và trượt: chưa đạt đến khi có lượt mới pass.
- Có lượt chính thức đang mở hoặc chờ chấm: chờ kết luận năng lực; không dùng pass cũ để phê duyệt vai trong lúc này.
- Đổi phiên bản bắt buộc: giữ lịch sử bản cũ nhưng không tự công nhận bản mới. Mặc định không có cơ chế miễn thi chuyển tiếp.
- Thu hồi vai không xóa lịch sử đào tạo; chỉ gỡ nhãn authorized và giữ lý do/thời điểm.
- Nộp trễ vẫn giữ lịch sử và nhãn LATE, không tính đạt đúng hạn.

## Lỗi critical

Theory có bốn nhóm critical trong blueprint. PDA thật dùng cờ critical của từng mục rubric. Mô phỏng dùng trạng thái và payload để phát hiện: giả số lượng; tự kiểm; bỏ tem1; xác nhận mapping sai; dán tem trước điều kiện hoặc che dữ liệu; Completed quá sớm; tạo giao dịch mới trùng khi đã ghi; xóa mù ô tồn; sửa số để khớp.

Quét tạm nhầm được chặn và sửa trước khi xác nhận không được coi là đã commit mapping sai. Một case chính thức đã fail critical không được reset trong cùng attempt để xóa lỗi. Client không được tự gửi điểm hoặc `critical=false` làm căn cứ chấm. Server lưu điểm, lỗi, phiên bản chấm, thời gian và người xác nhận.
