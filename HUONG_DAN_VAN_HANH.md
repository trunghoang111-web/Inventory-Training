# Hướng dẫn vận hành hệ thống đào tạo kiểm kê ASV 2026

Hệ thống đào tạo và sát hạch kiểm kê Sản xuất Ajax Systems Vietnam (ASV).

---

## 1. Khởi chạy hệ thống (Local & On-Premise)

Hệ thống được thiết kế hoàn toàn khép kín, hoạt động độc lập không phụ thuộc Internet bên ngoài (phù hợp môi trường mạng nội bộ phân xưởng và thiết bị PDA cầm tay).

### 1.1 Khởi động máy chủ & Ứng dụng
Từ thư mục gốc dự án:
```bash
python3 scripts/run_server.py
```
- Máy chủ sẽ tự động kiểm tra cơ sở dữ liệu `asv_training.db`, tự động nạp dữ liệu chuẩn (seed) nếu chạy lần đầu.
- Giao diện web được phục vụ trực tiếp tại: **`http://127.0.0.1:8000/`** (hoặc địa chỉ IP mạng nội bộ của máy chủ).

---

## 2. Tài khoản quản trị & Bootstrap an toàn

Hệ thống **không sử dụng mật khẩu dùng chung dạng hard-code**. Mật khẩu được băm một chiều bằng chuẩn an toàn **PBKDF2-HMAC-SHA256 (100.000 vòng lặp) với salt ngẫu nhiên**.

### 2.1 Tài khoản quản trị khởi tạo (Bootstrap):
- **Mã nhân viên:** `ADMIN01`
- **Mật khẩu khởi tạo:** `AsvAdmin@2026`
- **Quyền hạn tích hợp:** `SYSTEM_ADMIN`, `CONTENT_ADMIN`, `PM_VIEWER`, `WCM_VIEWER`, `WAREHOUSE_APPROVER`.

### 2.2 Tạo mới hoặc Đặt lại mật khẩu Quản trị viên:
```bash
python3 scripts/bootstrap_admin.py <MÃ_NV> <MẬT_KHẨU_MỚI>
```
*Ví dụ:*
```bash
python3 scripts/bootstrap_admin.py ADMIN_KHO "MatKhauMoi@2026"
```

---

## 3. Hướng dẫn Import danh sách học viên & Sao lưu / Phục hồi

### 3.1 Import danh sách nhân sự (CSV):
1. Đăng nhập với quyền `CONTENT_ADMIN` hoặc `SYSTEM_ADMIN`.
2. Vào tab **⚙️ Quản trị & Import**.
3. Dán hoặc tải file CSV theo đúng định dạng mẫu `templates/employee_import.csv`:
   ```csv
   slot_id,employee_id,full_name,job_title,crew,workcell,group,operational_roles,app_role,manager_employee_id,active,is_placeholder
   LL001,ASV001,Nguyen Van A,LINE_LEADER,A,WC01,N1,A|B,LEARNER,,true,false
   ```
4. Bấm **"1. Kiểm tra & Xem trước (Preview)"**:
   - Hệ thống kiểm tra trùng lặp `employee_id`, kiểm tra định dạng kíp (`A`, `B`, `C`, `D`, `OFFICE`), chức danh và vai kiểm kê.
   - Báo cáo rõ ràng số dòng tạo mới (`creates`), cập nhật (`updates`) và dòng bị từ chối (`rejects`) kèm số dòng và nguyên nhân lỗi chi tiết.
5. Bấm **"2. Xác nhận lưu vào hệ thống"**: Dữ liệu được ghi nhận trong một Transaction duy nhất (ACID).
- **Lưu ý về 132 slot kế hoạch:** 132 slot kế hoạch mặc định được lưu dưới dạng `is_placeholder=true`, `active=false`. Chúng không tự động sinh tài khoản thật hoặc kết quả đạt giả, và được tách biệt khỏi mẫu số dashboard.

### 3.2 Sao lưu cơ sở dữ liệu (Backup):
Sử dụng SQLite Online Backup API an toàn (không khóa bảng, chống lỗi dữ liệu nửa chừng):
```bash
python3 scripts/backup_restore.py
```
File sao lưu được tạo tự động tại thư mục `backups/asv_training_YYYYMMDD_HHMMSS.db`.

### 3.3 Phục hồi cơ sở dữ liệu (Restore):
Công cụ sẽ kiểm tra tính toàn vẹn (`PRAGMA integrity_check`) của file backup trước khi khôi phục:
```bash
python3 scripts/backup_restore.py restore backups/asv_training_<TIMESTAMP>.db
```

---

## 4. Kiến trúc & Hướng dẫn chuyển đổi PostgreSQL

Hệ thống hiện sử dụng **SQLite 3** cho bản thử nghiệm nội bộ một máy (zero-config, tự chứa). Khi triển khai quy mô lớn nhiều phân xưởng (hàng trăm PDA truy cập đồng thời), chuyển đổi sang **PostgreSQL**:
1. **Cấu hình biến môi trường:**
   - Thay vì `DB_PATH`, thiết lập chuỗi kết nối: `DATABASE_URL=postgresql://user:password@pg_host:5432/asv_training`.
2. **Ánh xạ kiểu dữ liệu:**
   - `TEXT PRIMARY KEY` -> `UUID PRIMARY KEY` hoặc `VARCHAR(64)`.
   - `INTEGER` (boolean) -> `BOOLEAN`.
   - `TEXT` (JSON) -> `JSONB` (tối ưu hóa truy vấn JSON trong snapshot và event log).
   - `TEXT` (ISO datetime) -> `TIMESTAMPTZ`.
3. **Cơ chế khóa & Ghi đồng thời:**
   - SQLite dùng `BEGIN IMMEDIATE`. Trong PostgreSQL dùng `SELECT ... FOR UPDATE` khi xử lý lượt thi hoặc điểm danh để chống race-condition.

---

## 5. Báo cáo kết quả kiểm thử toàn diện

Hệ thống đã chạy và vượt qua 100% các bộ kiểm thử nghiêm ngặt:

| Bộ kiểm thử | Mục đích | Số lượng ca kiểm | Kết quả |
|---|---|---|---|
| `scripts/validate_pack.py` | Kiểm tra tính nhất quán nội dung, số thẻ, số câu, pools, manifest | 488 checks | **PASS (100%)** |
| `tests/test_golden_cases.py` | Kiểm định các trường hợp biên golden policy (G01–G20) | 20 ca | **PASS (20/20)** |
| `tests/test_acceptance_u01_u30.py` | Kiểm định 30 tiêu chí nghiệm thu bắt buộc (U01–U30) | 30 ca | **PASS (30/30)** |
| `tests/test_api.py` | Kiểm tra tích hợp REST API (Auth, Lessons, Exam, Dashboard, Import) | 4 nhóm kiểm | **PASS (4/4)** |

### Các điểm kiểm soát an toàn & nghiệp vụ cốt lõi:
1. **Bảo mật khóa chấm (Anti-Cheat):**
   - Đáp án đúng, giải thích và luồng expected steps chỉ nằm ở server trong bảng `content_records`.
   - API trả về cho thí sinh đang làm bài **hoàn toàn không chứa đáp án** hay gợi ý.
   - Thí sinh không thể tự gửi điểm số (client score = 100 sẽ bị bỏ qua; điểm tính 100% từ đối soát khóa chấm server).
2. **Quy tắc Critical:**
   - Đạt lý thuyết: ≥90 điểm VÀ đúng toàn bộ 4 câu Critical.
   - Đạt PDA thật: ≥90 điểm, đủ 20 quan sát (không có mục NULL), đúng toàn bộ tiêu chí Critical và có chữ ký giám khảo hợp lệ.
   - Điểm số cao không bù đắp cho lỗi Critical.
3. **Chống tự chấm & tự phê duyệt (Anti-Self-Evaluation):**
   - Giám khảo không được chấm hoặc ký cho chính tài khoản của mình (`assessor_id != learner_id`).
   - Quản lý không được tự duyệt vai kiểm kê cho chính mình.
4. **Mẫu số Dashboard WCM/PM:**
   - Mẫu số `active_required_real` chỉ bao gồm học viên thật đang được yêu cầu (loại trừ các slot placeholder).
   - Tỷ lệ hoàn tất hiển thị `N/A` nếu mẫu số bằng 0.
   - Phân loại học viên theo phễu loại trừ nhau (Mutually Exclusive).
5. **Chống tấn công Formula Injection (CSV Injection):**
   - Mọi dữ liệu văn bản xuất CSV bắt đầu bằng `=`, `+`, `-`, `@` được tự động bọc nháy đơn `'` để không bị thực thi mã độc trên Excel/Google Sheets; trong khi số âm hợp lệ (ví dụ `-2`, `-15.5`) vẫn được giữ nguyên kiểu số.

---

## 6. Các hạng mục cần Kho / IT xác nhận thực tế trên PDA thật

Phần mềm đã sẵn sàng chạy thử nghiệm và sát hạch. Theo quy định tại `docs/10_KIEM_TRA_TRUOC_TRIEN_KHAI.md`, trước khi mở đợt thi chính thức cần các bộ phận xác nhận thực địa:

1. **IT / Thiết bị:**
   - Xác nhận model PDA và cấu hình scanner bàn phím (Keyboard wedge output với phím kết thúc Enter).
   - Kiểm tra độ ổn định kết nối Wi-Fi tại 5 làn sát hạch của xưởng.
   - Kiểm tra hiển thị giao diện trên màn hình PDA thực tế (độ rộng tối thiểu 360px).
2. **Kho / Quản lý kiểm kê:**
   - Thống nhất màu sắc vật lý cho **Tem 1** (kiểm đếm), **Tem 2** (gán vị trí), **Tem 3** (hoàn tất phiếu) tại xưởng.
   - Cung cấp mã Box, Pallet (P-number), và Ô vị trí dùng cho môi trường Lab sát hạch (không dùng mã tồn thật của phân xưởng).
   - Cung cấp danh sách phân công Giám khảo (Assessor) cho từng làn thi.
3. **WCM / Quản lý sản xuất:**
   - Chốt danh sách nhân sự thật (Roster) thay thế cho 132 slot dự kiến qua file import.
   - Chốt danh sách nhân sự giữ dây chuyền để không rút toàn bộ kíp cùng một thời điểm.
