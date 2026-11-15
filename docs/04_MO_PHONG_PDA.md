# Đặc tả mô phỏng PDA trong app

Đây là bộ máy tình huống đào tạo, không phải WMS thay thế. Luôn hiển thị “MÔ PHỎNG · không ghi dữ liệu tồn thật”. Giao diện được dựng theo chức năng; các ảnh menu trong SOP chỉ là tham chiếu, không tuyên bố giống chính xác phiên bản ASV đang dùng.

## Cách đọc dữ liệu

`public/simulations.json` cung cấp task, dữ kiện, các điều khiển và trường nhập. `private/simulation_grading.json` cung cấp các bước kỳ vọng, cách khớp và sự kiện critical; chỉ đọc phía server. `expected_steps` là luồng đúng, không được hiển thị thành hướng dẫn lúc đang thi. Các nút chính và nút hành động sai cần thiết để phân biệt lựa chọn có thể đưa ra theo bối cảnh, nhưng không gắn nhãn “đúng/sai” trước khi nộp.

Mọi event được lưu với attempt_id,case_id,event_id,seq,idempotency_key,actor,payload,server_at. Máy chủ là nguồn trạng thái. Gửi lại cùng idempotency_key và cùng payload trả cùng kết quả, không tính thêm bước; cùng key nhưng payload khác trả lỗi409. Từ chối stale seq để một tab cũ không ghi đè kết quả tab mới. Khi kết nối lại truy vấn trạng thái đã lưu rồi mới tiếp tục.

### State và điểm

- Mỗi case: NOT_STARTED → ACTIVE → COMPLETED_CORRECT/COMPLETED_INCORRECT/CRITICAL_FAILED. Case đúng cần đủ các bước hợp lệ, đúng payload; chưa đủ không tự đạt. Mỗi case được final-submit một lần trong thi chính thức; mode luyện được reset tạo log mới.
- Các hành động thay đổi trạng thái có thứ tự theo key. `SCAN_PREVIEW` chỉ đưa mã vào vùng tạm: sai loại/mã thì cảnh báo và không tiến bước, không critical nếu chưa commit. Sai giá trị được xác nhận nộp như qty, route hoặc quyết định không thể âm thầm đổi lại để lấy trọn điểm trong cùng case; kết thúc case với lỗi và giữ log.
- Commit mapping sai trong môi trường ảo ghi sự kiện chuẩn hóa `COMMIT_WRONG_MAPPING` và case CRITICAL_FAILED; ngoài môi trường ảo không có giao dịch kho nào. Dán tem sai trước kiểm hoặc che dữ liệu chuẩn hóa về đúng terminal event đã liệt kê. Người học không thể né bằng tự đặt event_type khác qua API.
- Các event critical là kết quả phân tích từ trạng thái+payload phía server. Ví dụ `APPLY_STICKER1` khi chưa VERIFY_BOX phải phát sinh `APPLY_STICKER1_BEFORE_CHECK`, kể cả client không gửi tên lỗi đó.
- Không nhận `success=true`, điểm hoặc role từ client làm bằng chứng. Server tự tính từ dữ liệu case và quyền của người học. Không cho sửa context, actual_qty,sticker1 hoặc assigned_cell của đề.
- Mỗi case assessed đúng được10 điểm, sai/chưa xong0. Không chấm một phần theo số nút bấm. Critical làm trượt cả bài. Đề cố định10 case SIM01–SIM10, thứ tự có thể xáo trộn; P01/P02 chỉ luyện.
- SIM03 chấp nhận mọi cách chia lượt hợp lệ, không chỉ5+1: mỗi lượt1–5 dòng, đúng thread, mỗi hộp một dòng, đúng mã/lượng, đủ6 hộp một lần, giữ thứ tự. Ví dụ3+3 cũng đạt. Expected path trongkey là ví dụ cho giao diện, không phải giới hạn chấm.
- SIM09 cho phép phân loại ô A/B theo thứ tự bất kỳ sau xác nhận kỳ/phạm vi. SIM10 cho phép kiểm ô A/B thứ tự bất kỳ, nhưng phải đủ cả hai trước chốt tổng. P01 tương tự cho các tình huống. Không cho lặp một ô thay cho ô còn thiếu.
- Timeout: chỉ server tự nộp/khóa. Kết quả dựa các case đã final-submit, case còn lại0; không cho gửi event sau hạn để bổ sung điểm.

## Những trường hợp cần dựng rõ

| Case | Điều người học tự thao tác |
|---|---|
| SIM01 | Đếm18token PCB, nhập pcs, chọn tuyến người có quyền, kiểm nhãn và bỏ nhãn cũ, dấu A |
| SIM02 | Chọn đơn vị và đổi3 gói×5 pcs thành15 pcs |
| SIM03 | Kéo/chọn dòng theo hộp để gửi các lượt ≤5, không gộp hai hộp cùng mã |
| SIM04 | Chọn người B khác A, kiểm mã/lượng, dán tem 1 đúng vị trí |
| SIM05 | Nhập/quét Box,pallet,ô; xác nhận hai tầng và phản hồi; dán tem 2 chồng lệch |
| SIM06 | Dừng hộp thiếu tem 1 và báo GL/Controller |
| SIM07 | Sắp đúng bước PC/PDT; đóng cửa sổ sau tạo khác Completed cuối; tem 3 lên ô |
| SIM08 | Truy vấn trạng thái sau timeout, thấy đã ghi và không tạo giao dịch mới |
| SIM09 | Chọn kỳ/ô, đếm bổ sung ô đang dùng; xác minh rồi loại ô không dùng đúng quy trình |
| SIM10 | Kiểm mọi ô cùng mã, ghi40,42,−2 và tuyến báo lỗi |

Số lượng ở SIM01 phải được dựng bằng18phần tử DOM từ `count_tokens`, không lấy từ ảnh PCB. Ảnh AI không phải chứng cứ số lượng hay cách dán tem thực tế. Các tem trong mô phỏng phải vẽ bằng DOM với tên Tem 1/2/3 rõ ràng, màu có thể cấu hình; không dùng màu ngẫu nhiên trong ảnh minh họa làm chuẩn chấm.

Hỗ trợ scanner kiểu bàn phím nếu PDA đã được IT cấu hình đúng: input focus rõ, terminator Enter cấu hình được, debounce chống hai lần gửi, hiển thị mã vừa đọc và kết quả. Manual input luôn có. Chưa biết model PDA và app WMS hiện hành nên không khẳng định browser đọc được camera/barcode phần cứng tự động.

Mode PRACTICE hiển thị lỗi và giải thích ngay. Mode EXAM không có key/hint; lưu câu trả lời đến server, chỉ hiện phản hồi sau nộp theo chính sách. Các asset và dữ kiện đầu bài có thể public trong app; khóa chấm và đường đi đúng không nằm trong bundle public.
