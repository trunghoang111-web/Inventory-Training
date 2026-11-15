# Yêu cầu xây ứng dụng đào tạo kiểm kê ASV

Bạn là kỹ sư sản phẩm triển khai app nội bộ cho Sản xuất Ajax Systems Vietnam. Hãy thực sự xây bản chạy được, lưu dữ liệu bền vững, chạy kiểm thử và hướng dẫn vận hành. Dùng toàn bộ bộ đầu vào này, không thay bằng nội dung mẫu.

## Đọc trước khi code

Đọc `00_BAT_DAU.md`, tất cả tài liệu `docs/`, `data/public/course.json`, `data/assessment_blueprint.json`, `data/role_catalog.json`, `data/hardware_rubrics.json`, `data/schedule.json`, `data/shift_calendar.json`, `data/asset_manifest.json`; sau đó đọc lessons/questions/simulations và khóa chấm trong `data/private/` từ môi trường máy chủ. Chạy `python3 scripts/validate_pack.py`. Đối chiếu SOP trong `references/` khi cần kỹ thuật.

## Kết quả cần xây

Ứng dụng web tiếng Việt, ưu tiên dễ dùng trên điện thoại/PDA và PC. Giao diện Ajax: nền đen/xám đậm, chữ trắng, điểm nhấn xanh; trạng thái có chữ/biểu tượng để không phụ thuộc màu. Mỗi màn hình học ưu tiên ảnh lớn +1 thẻ nội dung ngắn; có nút nghe văn bản nếu môi trường hỗ trợ nhưng không coi đó là điều kiện bắt buộc.

1. **Người học:** đăng nhập định danh, xem lịch theo kíp, tiếp tục 12 bài, trả câu kiểm tra cuối bài; luyện câu hỏi và 12 tình huống; thi lý thuyết20 câu, mô phỏng 10 tình huống; xem điều kiện còn thiếu và lịch thi lại.
2. **Người hướng dẫn/người chấm:** điểm danh buổi được giao, mở ca thi, quan sát PDA thật theo 20 tiêu chí, ghi lỗi và xác nhận riêng từng người; bài bổ sung A2/PC và Controller; không tự chấm bản thân.
3. **WCM/PM:** dashboard theo người/kíp/workcell/chức danh/vai kiểm kê; đủ điều kiện, chưa học, vắng, chưa đạt, lỗi critical, chờ PDA thật, chờ duyệt vai; danh sách hành động và báo cáo CSV/Excel. Mẫu số là toàn bộ học viên thật đang được yêu cầu đào tạo, gồm người chưa bắt đầu.
4. **Quản trị nội dung/Kho:** import danh sách có preview và kiểm lỗi; gán nhóm/lịch/người chấm; quản lý phiên bản và phê duyệt nội dung; ghi nhận duyệt vai theo scope. Không cấp quyền WMS, không kết nối ghi tồn 1C.

## Kiến trúc và dữ liệu

Nếu đã có repo, kiểm tra cấu trúc và làm theo stack đang dùng. Nếu tạo mới, chọn React+TypeScript cho giao diện, server có API xác thực và cơ sở dữ liệu quan hệ. Dùng SQLite để chạy nội bộ một máy trong bản thử nếu phù hợp; mô tả cách chuyển PostgreSQL khi triển khai nhiều người. Dùng thư viện đang được hỗ trợ và kiểm tài liệu chính thức khi cài. Không gắn khóa học vào một nền tảng hosting bắt buộc; không tự deploy.

Khóa chấm chỉ ở máy chủ. Không import `data/private` vào React, không copy cả kit vào public, không trả key/giải thích trong API đang thi. Dữ liệu official không chỉ lưu localStorage. Mọi điểm, thời hạn, phiên bản, chữ ký và quyền được kiểm server-side. Không có mật khẩu dùng chung hard-code. Có chế độ demo riêng ghi rõ DEMO; demo không tính dashboard thật.

Áp dụng toàn bộ `docs/03_QUY_TAC_DANH_GIA.md`. Thi chính thức 20 phút chọn 4 câu critical theo 4 pool +16 câu từ 8 pool thường;≥90 và đúng mọi câu critical mới đạt. Simulation≥90, không critical. PDA thật≥90, đủ 20 quan sát, không critical và có người chấm hợp lệ. Vai bổ sung theo rubric. Điểm cao không bù lỗi critical. Thử lại tạo lượt mới và giữ lịch sử. Đề đã bắt đầu phải lưu snapshot, không bị sửa khi admin đổi nội dung.

Triển khai mô phỏng theo `docs/04_MO_PHONG_PDA.md`; có event log và trạng thái. Bài đếm dùng token HTML chính xác, không chấm lượng bằng ảnh AI. Hỗ trợ nhập/quét bằng scanner bàn phím nếu thiết bị thực tế hỗ trợ; luôn có bàn phím dự phòng. Mô phỏng không giả vờ là WMS thật và không chứng nhận PDA thật.

Đọc mốc thời gian có timezone+07:00. Hạn chót là exclusive 2026-12-01T00:00:00+07:00. Chặn xếp trùng người/chấm/thiết bị, cảnh báo học vào ca nghỉ và buổi ca đêm qua 0 giờ. Chưa có nhân sự thật thì giữ slot là placeholder; không sinh tài khoản hoặc kết quả đạt từ 132 slot.

## Cách triển khai

Tạo bảng truy vết yêu cầu → chức năng → kiểm thử. Hoàn thành lần lượt: database/auth/import → học bằng ảnh → thi và chấm trên server → mô phỏng → checklist PDA thật/chữ ký → lịch/dashboard/export → kiểm thử. Sau mỗi phần chạy kiểm tra cần thiết; sửa lỗi rồi tiếp tục. Không dừng ở bản vẽ, danh sách TODO hay dashboard số giả.

Nạp seed nội dung một cách idempotent theo course_version và content_id. Các template chỉ là mẫu nhập. Không tạo học viên thật, kết quả đỗ, chữ ký hay chứng cứ giả. Có fixtures kiểm thử riêng biệt và bị loại khỏi báo cáo vận hành.

## Nghiệm thu bắt buộc

Thực hiện các ca trong `docs/08_NGHIEM_THU.md` và các golden cases trong `tests/golden_cases.json`. Kiểm soát học viên gọi API chấm/đổi điểm trái quyền, lộ đáp án, self-sign, thi lại, lịch qua 0 giờ, thiếu scope và mẫu số dashboard. Kiểm build client không có private keys. Chạy kiểm trên độ rộng 360px và màn hình PC; ảnh đúng xuất xứ, nội dung không bị tràn.

Cuối cùng trả: cách chạy frontend/server/database, account bootstrap an toàn cho quản trị, hướng dẫn import và khôi phục backup, báo cáo kiểm thử, phần nào cần Kho/IT xác nhận trên PDA thật. Có bản chạy local để xem. Chỉ dừng ở phụ thuộc thật sự không thể hoàn tất; nêu chính xác điểm chặn, không thay việc chưa làm bằng kết quả đạt.
