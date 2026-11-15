# Phòng thực hành và sát hạch PDA thật

Kho/IT cung cấp môi trường test được phép ghi, tài khoản theo vai và mã hợp lệ trên WMS test. Mã SIM-ASV chỉ phục vụ app; không coi là mã WMS thật. Nếu chưa có môi trường test, có thể luyện bằng đồ dùng/nhãn giả nhưng chưa ký đạt thao tác WMS thật cho tới khi có phương án Kho/IT xác nhận.

## Thiết bị và người

Thực hành cần4 người hướng dẫn,12 PDA,4 PC,2 máy in; nhóm khoảng16–17 người chia bốn tổ luân phiên. Thi cần5 làn,5 người chấm,5 PDA+1dự phòng,5 PC,2 máy in theo luồng. Kiểm mạng,pin,quyền,tài khoản,mã,máy in và reset dữ liệu test giữa lượt. Không dùng chung tài khoản để ghi kết quả người học. Giám khảo có thể đóng vai A2/PC/Controller trong kịch bản, nhưng phải ghi ai quan sát.

## Đồ dùng mỗi làn

1. Hộp NVL M01 đã mở: nhãn20 pcs, thực tế18; hộp B12 pcs và C10 pcs. Dùng tình huống thực tế thấp hơn nhãn. Đây là bộ riêng, khác bài đếm lại ở mục6.
2. Hộp M02 thực tế7 pcs, cố ý dán nhãn M01. Sau học viên báo lỗi, giám khảo đưa nhãn đúng để tiếp tục.
3. Mã Box/P-number/ô hợp lệ tronglab: ít nhất hai pallet, hai ô và một receiving, mã riêng mỗi làn; Kho xác nhận bảng ánh xạ.
4. Tem1/2/3 đúng màu do Kho chốt; bút✓xanh,Xđen; nhãn lỗi/nhãn thay; giấy ghi số và phiếu đối chiếu.
5. Phiếu test chưa hoàn tất và tình huống timeout có trạng thái xác định. Không ngắt mạng ảnh hưởng WMS thật.
6. Bộ đếm lại M01 riêng: hệ thống ôA32,ôB10; thực tế ôA30,ôB10. Có vật mẫu/token đủ; không dùng số18ở mục1để chấm tình huống này.

## Bốn trạm luyện, mỗi trạm35 phút

| Trạm | Từng người thực hiện | Người hướng dẫn kiểm |
|---|---|---|
| P1 Đếm/nhãn | Đọc mã/unit, đếm hộp thiếu, tuyến sửa, nhãn mới và dấu A; gửi mẫu SFP | Đúng hộp, lượng và đơn vị; không tin nhãn sai |
| P2 B/tem1 | Kiểm bộ người khác đếm, phát hiện sai mã, báo lỗi, kiểm lại | B khác A; tem sau kiểm, không che barcode |
| P3 Gán/tem2 | Box→P-number→ô, đọc phản hồi, xử lý thiếu tem1, rà receiving | Đủ hai tầng, đúng ô, hai tem nhìn được |
| P4 Phiếu/tem3/kiểm lại | Phối hợp PC/PDT, timeout, tem3lênô, Stock Balance mọi ô | Kiểm trạng thái, không Completed sớm, tổng40và lệch−2 |

Buổi180 phút: mở10+4×35+chuyển10+thi mô phỏng15+phản hồi5. Từng người phải tự thao tác; xem bạn làm không thay phần thực hành cá nhân.

## Thi cá nhân25 phút

Mỗi làn gồm năm trạm S1–S5, khoảng5 phút/trạm. Một người chấm phụ trách một làn và theo học viên qua cả năm trạm; năm làn làm song song. Không hiểu là năm người chấm chia mỗi người một trạm để40 người cùng làm. Các làn có mã/kịch bản riêng.

| Trạm | Nhiệm vụ | Quan sát chính |
|---|---|---|
| S1 | Đăng nhập lab, đọc Box/P/ô,unit; đếm hộp20/18 | Danh tính,môi trường,mã,unit,lượng thực |
| S2 | B kiểm bộ của người khác, tìm nhãn sai, tem1sau sửa | Độc lập,tuyến sửa,không che barcode |
| S3 | Gán hai tầng, tem2, receiving | Phản hồi đúng,không thiếu tem1 |
| S4 | Nhận phiếu, timeout, hoàn tất, tem3lênô, báo PC | Đúng phạm vi,trạng thái,PC kiểm rồi Completed |
| S5 | Stock Balance mọi ô của M01, ghi30+10=40,lệch−2 | Đủ ô,bàn giao lỗi,không tự sửa1C,điều kiện mở lại |

Rubric20 mục ở `data/hardware_rubrics.json` là nguồn chấm, không chỉ năm dòng tóm tắt trên. Mỗi mục5/0/null; null chưa được nộp hoàn tất. Không bỏ qua mục rồi cho5 điểm. Fail critical thì lượt đó fail dù tiếp tục quan sát để học; muốn thi lại phải tạo lượt mới sau ôn.

Trước mỗi lượt, giám khảo đặt lại test và checklist. Bộ cho B/C do người khác chuẩn bị, không để học viên tự kiểm dữ liệu vừa tạo. Chỉ người có quyền test thao tác chức năng đó; học viên mô tả phối hợp PC ở bài chung, còn vai PC có bài trực tiếp riêng. Hỏng môi trường khiến không thể quan sát phải tạm dừng/void có ghi nhận, không tự chấm đỗ.

## Bài vai bổ sung

A2/PC20 phút: batch SFP có hai hộp cùng mã và một nhãn sai; nhập,in,ghép nhãn,phản hồi,tạo/giao/đóng phiếu,kiểm Completed và coverage. Controller15 phút: hộp thừa,thiếu tem1,mapping sai; khoanh vùng,chọn người sửa,kiểm lại sau sửa. Dùng rubric10và6 mục trong JSON, đúng mọi critical. Xếp ngay chiều ngày3của kíp, trước01/12.

Sau thi lưu người,thiết bị,lab,rubric version,từng quan sát,lỗi,thời gian server và chữ ký giám khảo. Một ảnh đẹp không thay quan sát thực tế. Có thể dùng biên bản ký thay video; không cần bắt quay mặt nếu không phục vụ chấm.
