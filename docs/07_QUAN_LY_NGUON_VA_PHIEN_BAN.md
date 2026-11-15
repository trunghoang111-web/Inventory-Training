# Nguồn, phiên bản và xử lý khác biệt

## Thứ tự áp dụng

1. Kỹ thuật nghiệp vụ: SOP AG03-WH-092_A người dùng cung cấp. Filetext trongreferences giữ nguyên ngôn ngữ nguồn. Bản dịch/bài học là nội dung biên soạn, không thay văn bản kiểm soát của công ty.
2. Ngày đào tạo: lịch4 kíp mới, hoàn tất trước 01/12/2026; dùng `data/schedule.json`. Ngày kiểm kê18–27/12/2026 theo yêu cầu người dùng. Đây là ngày kế hoạch, không phải tín hiệu mở lại.
3. Ngân hàng đề, rubric và policy version trong kit: đề xuất triển khai trên app; Kho/Audit Team/WCM rà một lần trước mở đợt chính thức. Chưa có tên thật, modelPDA, tài khoảnlab, màu tem và phạm vi kho/ô chính thức 2026.
4. Slide/hướng dẫn cũ chỉ là tài liệu tham chiếu hình ảnh. Nếu ghi chú slide nói6lớp hoặc các mốc thi cũ thì JSONlịch mới thay thế. Không lấy lịch từ PowerPoint làm seed. Bài thi cũ có mốc14/12đã không đưa vào bộ kit.

## Hồ sơ nguồn

`PACKAGE_MANIFEST.json` ghi hash nguồn và tất cả file. Nguồn gốc gồm Word export đã cung cấp, slide trực quan hiện có, file lịch4 kíp và dữ liệu rubric đã biên soạn. Word gốc cóảnh rất lớn nên kit đưa text nguồn và18ảnh được tối ưu riêng. Ảnh AI đã có từ lần làm slide trước được dùng lại và ghi `kind=ai_illustration`; không tạo chứng cứ ảnh hiện trường giả.

Tài liệu nguồn có các liên kết WMS chức năng và master kho/REF. Kit không đọc được nội dung những tài liệu con chưa cung cấp; do đó không tự phát minh nút bấm, API, trườngbarcode hay quyền WMS. Trước khi dùng PDA thật, Kho/IT đối chiếu UI hiện hành và bổ sung ảnh chụp được phép vàoasset mới. Bảng tiền tố ô trong ảnh cũ không phải phạm vi đã chốt2026.

## Nội dung phải giữ đúng

- A/B/C riêng người trên cùng dữ liệu; B độc lập, C chỉ sau tem 1; tem 2 chồng lệch, tem 3 trên ô sau hoàn tất phiếu.
- Không gán màu cố định choColor 1/2/3 trongkey; dùng tên bước và cấu hình màu đã xác nhận.
- Tách đóng cửa sổ tài liệu sau tạo khỏi chuyểnCompleted cuối quy trình.
- WMS kiểm kê chỉ mở sau chuẩn bị hoàn tất mọi khu vực và thông báo Audit Team, không chỉ khu mình.
- Trong khóa không chuyển hàng giữa khu; sai trạng thái/vị trí vẫn ghi đúng hiện trạng và báo; chuyển vật lý+hệ thống sau kiểm kê theo quy trình.
- SFP có linh kiện ngoài specification: đếm linh kiện riêng và báo; REF không nhập thànhOK; hàngwrite-off đã xác minh cách ly đỏ loại trừ.
- Hộp nguyên nhà cung cấp chưa mở có ngoại lệ không bắt buộc mở đếm lại; không suy ngoại lệ này cho hộp đã mở.
- LệchNVLthiếu theo công cụ Writing-off materials from Box đúng quyền; thừa báo Audit Team. Nhãn sai theo tuyến xóa/in lại, không tạo hai nhãn mâu thuẫn.
- Reset ô chỉ theo trường hợp/hướng dẫn được phép; không reset hàng loạt mặc định.
- Kiểm lệch từng mã trên tất cả ô; không bù trừ mã/kho/trạng thái. Kho rà và ký danh sách kho trong Closing of Intermediate Inventory.
- Mở lại phải chờ Audit Team xác nhận điều chỉnh xong, cấm chứng từ lùi vào kỳ; mọi lệch cóincident.

## Xuất bản và thay đổi

Nội dungdraft có thể sửa, published là bất biến. Publish gồmversion,digest,người rà,ngày. Không sửa key của đề đang thi. Thay đổi trọng yếu làm mới điều kiện cần học; hệ thống giữ bản cũ để giải thích lịch sử. App cần thể hiện “bản đang áp dụng” và nguồn ngay trong màn học.

Các trạng thái “pending local validation” trong kit là nhiệm vụ quản trị triển khai, không phải yêu cầu người dùng phải xin phép để tiếp tục viếtapp. Antigravity có thể xây và chạytest đầy đủ ngay; chỉ không mở thi thật trên tồn thật khi chưa có điều kiệnlab đã chốt.
