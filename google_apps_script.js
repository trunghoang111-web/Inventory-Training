/**
 * =========================================================================
 * AJAX SYSTEMS VIETNAM · ĐÀO TẠO KIỂM KÊ SẢN XUẤT 2026
 * GOOGLE APPS SCRIPT WEBHOOK ĐỒNG BỘ KẾT QUẢ TỰ ĐỘNG
 * =========================================================================
 * 
 * HƯỚNG DẪN CÀI ĐẶT 3 BƯỚC (CHỈ MẤT 1 PHÚT):
 * 1. Tạo 1 file Google Sheets mới (ví dụ đặt tên: "ASV_Ket_Qua_Kiem_Ke_2026").
 * 2. Trên thanh menu, chọn: Tiện ích mở rộng (Extensions) -> Apps Script.
 *    Xóa toàn bộ mã mặc định và DÁN TOÀN BỘ ĐOẠN MÃ DƯỚI ĐÂY vào. Bấm "Lưu" (Ctrl+S / Cmd+S).
 * 3. Bấm nút "Triển khai" (Deploy) ở góc trên bên phải:
 *    -> Chọn "Tùy chọn triển khai mới" (New deployment)
 *    -> Chọn loại: "Ứng dụng web" (Web app)
 *    -> Mô tả: "ASV Inventory Webhook"
 *    -> Thực thi dưới dạng (Execute as): "Tôi" (Me)
 *    -> Ai có quyền truy cập (Who has access): "Bất kỳ ai" (Anyone)
 *    -> Bấm "Triển khai" (Deploy) và cấp quyền truy cập nếu Google hỏi.
 *    -> SAO CHÉP ĐƯỜNG LINK WEB APP URL (có đuôi /exec) và dán vào ô Google Sheet trong trang Quản lý app!
 */

function doPost(e) {
  var lock = LockService.getScriptLock();
  // Khóa tối đa 15 giây để tránh xung đột ghi đồng thời từ nhiều học viên
  lock.waitLock(15000);

  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    // 1. Tab tổng hợp trạng thái học viên (mỗi nhân viên 1 dòng duy nhất, tự cập nhật)
    var summarySheet = ss.getSheetByName("Ket_Qua_Tong_Hop");
    if (!summarySheet) {
      summarySheet = ss.insertSheet("Ket_Qua_Tong_Hop");
      summarySheet.appendRow([
        "Mã nhân viên", "Họ và tên", "Vị trí", "Bắt đầu lúc", 
        "Số trang đã học", "Đã học hết", "Số lần làm bài", 
        "Điểm gần nhất", "Kết quả", "Hoàn tất lúc", "Lần cập nhật cuối"
      ]);
      // Định dạng màu Ajax chuẩn: Nền tối / Xanh Ajax, chữ trắng in đậm
      summarySheet.getRange(1, 1, 1, 11).setFontWeight("bold").setBackground("#0b4f2a").setFontColor("#ffffff");
      summarySheet.setFrozenRows(1);
    }

    // 2. Tab lịch sử chi tiết (ghi lại mọi lần nộp bài để làm bằng chứng kiểm toán)
    var logSheet = ss.getSheetByName("Nhat_Ky_Chi_Tiet");
    if (!logSheet) {
      logSheet = ss.insertSheet("Nhat_Ky_Chi_Tiet");
      logSheet.appendRow([
        "Thời gian ghi nhận", "Mã nhân viên", "Họ và tên", "Vị trí", 
        "Lần thi số", "Điểm số /10", "Kết quả", "Chi tiết câu trả lời"
      ]);
      logSheet.getRange(1, 1, 1, 8).setFontWeight("bold").setBackground("#111111").setFontColor("#ffffff");
      logSheet.setFrozenRows(1);
    }

    var rawContents = "";
    if (e && e.postData && e.postData.contents) {
      rawContents = e.postData.contents;
    } else if (e && e.parameter && e.parameter.data) {
      rawContents = e.parameter.data;
    }

    var data = null;
    if (rawContents) {
      try {
        data = JSON.parse(rawContents);
      } catch (errParse) {
        data = null;
      }
    } else if (e && e.parameter && e.parameter.employee_id) {
      data = [e.parameter];
    }

    if (!data) {
      return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": "Không nhận được dữ liệu hợp lệ." }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    var records = Array.isArray(data) ? data : [data];
    var nowStr = Utilities.formatDate(new Date(), "Asia/Ho_Chi_Minh", "yyyy-MM-dd HH:mm:ss");

    var summaryData = summarySheet.getDataRange().getValues();
    var idRowMap = {};
    for (var r = 1; r < summaryData.length; r++) {
      var rawId = String(summaryData[r][0]).replace(/^'/, '').trim();
      if (rawId) {
        idRowMap[rawId] = r + 1; // 1-based index
      }
    }

    for (var i = 0; i < records.length; i++) {
      var item = records[i];
      var cleanEmpId = String(item.employee_id || "").trim();
      var empIdFormatted = "'" + cleanEmpId; // Dấu nháy đơn ở đầu để Excel/Sheets không xóa số 0 đầu
      var fullName = item.full_name || "";
      var position = item.position || "";
      var startedAt = item.started_at ? String(item.started_at).substring(0, 19).replace('T', ' ') : "";
      var slidesViewed = item.slides_viewed_count || "";
      var isCompletedSlides = item.is_completed_slides || "";
      var attemptsCount = item.attempts_count !== undefined ? item.attempts_count : 0;
      var latestScore = item.latest_score !== undefined ? String(item.latest_score) : "—";
      var resultStatus = item.result_status || "";
      var completedAt = item.completed_at ? String(item.completed_at).substring(0, 19).replace('T', ' ') : "—";

      var rowValues = [
        empIdFormatted, fullName, position, startedAt,
        slidesViewed, isCompletedSlides, attemptsCount,
        latestScore, resultStatus, completedAt, nowStr
      ];

      var existingRow = idRowMap[cleanEmpId];
      if (existingRow) {
        summarySheet.getRange(existingRow, 1, 1, 11).setValues([rowValues]);
      } else {
        summarySheet.appendRow(rowValues);
        idRowMap[cleanEmpId] = summarySheet.getLastRow();
      }

      // Nếu là sự kiện nộp bài kiểm tra thì ghi thêm 1 dòng vào nhật ký
      if (item.is_test_submit) {
        logSheet.appendRow([
          nowStr, empIdFormatted, fullName, position,
          attemptsCount, latestScore, resultStatus, JSON.stringify(item.answers || {})
        ]);
      }
    }

    return ContentService.createTextOutput(JSON.stringify({ "status": "success", "synced": records.length }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ "status": "error", "message": err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  if (e && e.parameter && (e.parameter.data || e.parameter.employee_id)) {
    return doPost(e);
  }
  return ContentService.createTextOutput("Ajax Systems Vietnam Inventory Training Google Sheet Webhook is active and healthy!");
}
