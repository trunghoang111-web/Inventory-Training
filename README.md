# Ajax Systems Vietnam · Đào tạo Kiểm kê Sản xuất

Ứng dụng web tinh gọn phục vụ đào tạo và kiểm tra quy trình kiểm kê cho các bộ phận xưởng: Line leader, Group leader, Feeder, Dispatcher (Điều phối), QD (Quản lý chất lượng), Workcell manager.

## 1. Khởi chạy nhanh (Local)

Yêu cầu máy có cài **Python 3.10 trở lên** (không cần cài thêm thư viện phụ thuộc):

```bash
python3 scripts/run_server.py
```

* Người học truy cập: `http://127.0.0.1:8000/`
* Quản lý & Báo cáo: `http://127.0.0.1:8000/#admin`
  * Tài khoản: `ADMIN01`
  * Mật khẩu: `AsvAdmin@2026`

## 2. Kiểm thử tự động

Chạy bộ kiểm thử 7 tiêu chuẩn nghiệm thu:

```bash
python3 -m unittest tests/test_simple_app.py
```

## 3. Cấu trúc thư mục

* `backend/`: API và logic máy chủ (xử lý phiên, chấm điểm server-side, bảo mật, xuất báo cáo).
* `frontend/`: Giao diện người dùng tối ưu hóa xưởng (nền tối Ajax, nút to, phóng to ảnh, bảng quản lý).
* `slides/`: 19 hình ảnh slide bài giảng và logo nhận diện Ajax.
* `scripts/`: Script khởi chạy server `run_server.py`.
* `data/`: Cấu hình danh mục và dữ liệu chuẩn.
* `slides.json`: Danh mục 20 trang học kèm nội dung cần nhớ.
* `questions.json`: 10 câu hỏi trắc nghiệm kiểm tra hiểu quy trình.
* `answer_key.server.json`: Khóa đáp án và lời giải bảo mật phía máy chủ.
* `Mau_bao_cao.csv`: Mẫu định dạng đối chiếu báo cáo.
* `google_apps_script.js`: Mã script cài đặt vào Google Sheets để lưu kết quả vĩnh viễn.

## 4. Tích hợp Google Sheets (Lưu dữ liệu vĩnh viễn không mất)

Khi chạy trên Render gói miễn phí, ổ đĩa là bộ nhớ tạm (ephemeral). Ứng dụng đã được tích hợp tính năng **đồng bộ trực tiếp sang Google Sheets**:
1. Mở file Google Sheets mới trên trình duyệt.
2. Bấm **Tiện ích mở rộng** (Extensions) → **Apps Script**, dán mã từ file `google_apps_script.js`.
3. Bấm **Triển khai** (Deploy) → **Ứng dụng web** (Web app) → Ai có quyền truy cập: **Bất kỳ ai** (Anyone).
4. Copy link Web App và dán vào mục Google Sheets trong trang Quản lý (`#admin`) hoặc cài biến môi trường `GOOGLE_SHEET_WEBHOOK_URL` trên Render. Mọi kết quả thi sẽ tự động ghi vĩnh viễn vào Google Sheet!
