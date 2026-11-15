# Tiêu chí nghiệm thu ứng dụng

Từng ca cần kết quả và bằng chứng chạy thực tế. `validate_pack.py` chỉ kiểm bộ dữ liệu; chưa chứng minh app đã chạy hoặc người học dùng được PDA thật.

| ID | Ca kiểm | Kết quả bắt buộc |
|---|---|---|
| U01 | Nhập132 placeholder | Không tạo tài khoản hoặc kết quả thật; kế hoạch 132hiển thị riêng |
| U02 | ID trùng, tên trùng khácID, kíp không hợp lệ | ID trùng bị chặn/upsert rõ; không gộp theo tên; báo dòng lỗi |
| U03 |10 người thật,2qualified,3chưa học | Mẫu số10, tỷ lệ20%; chưa học vẫn trong mẫu số |
| U04 | Mẫu số0 | Hiển thị N/A, không100% |
| U05 | Làm đề 20 câu rồi refresh/đổi máy | Đề, thứ tự, timer và đáp án đã lưu không đổi |
| U06 |90 điểm sai một critical;90 điểm mọi critical đúng | Trường hợp đầu fail, trường hợp sau pass |
| U07 | Lý thuyết/mô phỏng đạt nhưng thiếu PDA thật | Chưa qualified |
| U08 | PDA95 điểm nhưng một critical sai hoặc một mục null | Fail hoặc chưa được nộp hoàn tất |
| U09 | Học viên tự gọi API chấm/ký hoặc đọc người khác/key | Bị chặn; không ghi điểm hoặc lộ dữ liệu |
| U10 | WCM khuA xin dữ liệu khuB | Chặn API và export ngoài scope |
| U11 | A2/PC45/50; Controller25/30 | Đạt khi critical đúng; critical sai vẫn fail |
| U12 | Pass → luyện trượt → thi chính thức trượt | Luyện không hủy pass; official fail mới nhất làm chưa đạt |
| U13 | Phiên bản mới hoặc lượt chính thức đang mở | Không dùng điểm cũ để tự qualified |
| U14 | SIM05 quét tạm sai rồi sửa; xác nhận gán sai | Quét tạm không critical; commit sai thì critical |
| U15 | SIM03 chia3+3; gộp hai hộp; lặp hộp |3+3đúng được pass; gộp/lặp không pass |
| U16 | SIM10 kiểmB trướcA; kiểmA hai lần bỏB | Đổi thứ tự được; thiếuB chưa đạt |
| U17 | Gửi lại cùng key, mở hai tab, timeout sau ghi | Không trùng sự kiện; stale event bị chặn; khôi phục đúng state |
| U18 | Hết giờ lúc mất mạng; gửi event sau hạn | Tự nộp phần đã lưu; event muộn không đổi điểm |
| U19 | Ca đêm29/11qua 00:00; nộp đúng00:00ngày 01/12 | Ngày/ca đúng; đúng00:00là trễ; chặn mở đề quá muộn |
| U20 | Người/PDA/người chấm trùng giờ hoặc vượt capacity | Chặn và chỉ rõ xung đột |
| U21 | Ca đêm thiếu người chấm; C/D đang nghỉ | Cảnh báo chưa đủ điều kiện, không coi là lịch đã chốt |
| U22 | Thiết bị hỏng, người chấm void | Giữ lý do, không pass giả; xếp lượt mới được |
| U23 | Qualified nhưng chưa duyệt vai; tự duyệt | Chưa authorized; tự duyệt bị chặn |
| U24 | Tìm key/expected_steps trong build và API đang thi | Không có; chỉ ở server |
| U25 | Admin sửa nội dung khi đề đang mở | Snapshot giữ nguyên; thay đổi xuất bản phiên bản mới |
| U26 | Màn hình360px, PC, ảnh lỗi, người khó phân màu | Không tràn; có caption/alt/text; trạng thái và tem có chữ |
| U27 | Text xuất CSV bắt đầu=,+,-,@ | Không chạy formula; số âm thật vẫn là số |
| U28 | Backup/restore và seed lần hai | Khôi phục đủ lịch sử/chữ ký; seed không nhân đôi |
| U29 | Client gửi score=100 dù trả sai | Server chấm từ key/state, không tin score client |
| U30 | Người chấm khác học viên nhưng chưa được giao | Bị chặn; phải đúng assignment, scope và phiên bản |

Kho/WMS chạy thử năm trạm trên thiết bị thật để xác nhận UI, quyền và mã lab. WCM chạy pilot năm người có LL/GL/feeder và vai chuyên sâu. Dữ liệu thử gắn DEMO và không cộng vào báo cáo thật. Không cần kết nối ghi tồn WMS hay deploy production để nghiệm thu bản local.
