# Kiểm tra bộ dữ liệu

Chạy `python3 scripts/validate_pack.py` từ thư mục gốc. Chỉ cần Python3 có thư viện chuẩn. Script kiểm liên kết bài–đề–đáp án–ảnh, số lượng, blueprint, lịch và deadline, placeholder,20golden cases vàhashmanifest.

`assessment_reference.py` chỉ mô tả quy tắc biên để nhà phát triển dùng làm đối chiếu; không có xác thực/API/database và không dùng nó như server thật. Antigravity phải viết và chạy các kiểm thử ứng dụng theo `docs/08_NGHIEM_THU.md`.

Nếu sửa dữ liệu sau khi giải nén, hashmanifest cũ sẽ báo lỗi; đây là phát hiện thay đổi có chủ ý. Tạo phiên bản vàmanifest mới qua quy trình xuất bản nội dung, không chỉ bỏ qua lỗihash để tuyên bố bộ dữ liệu vẫn nguyên bản.
