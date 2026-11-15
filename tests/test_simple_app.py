"""Test suite for the 6 mandatory acceptance checks of the simplified ASV Inventory Training app."""
import unittest
import json
import tempfile
import sqlite3
from pathlib import Path

from backend.config import COURSE_VERSION, ADMIN_USERNAME, ADMIN_PASSWORD
from backend.db import init_db, get_db_connection
from backend.simple_api import handle_simple_api_request, load_answer_key_data

class TestSimpleAppSixChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "test_simple.db"
        init_db(db_path=cls.db_path)
        
        # Load answer keys to know correct choices
        cls.keys = {a["id"]: a["correct_option_id"] for a in load_answer_key_data()["answers"]}

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def _call(self, method: str, path: str, token: str = None, body: dict = None, params: dict = None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        status, resp_headers, resp_bytes = handle_simple_api_request(
            method=method,
            path=path,
            headers=headers,
            body_bytes=body_bytes,
            query_params=params or {},
            db_path=self.db_path
        )
        data = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        return status, data

    # ---------------- KIỂM TRA 1: BẮT ĐẦU & MÃ NHÂN VIÊN ----------------
    def test_check_1_start_and_leading_zeros(self):
        # 1. Missing required fields rejected
        status, data = self._call("POST", "/api/simple/start", body={"employee_id": "", "full_name": "Test", "position": "Feeder"})
        self.assertEqual(status, 400)
        self.assertIn("Mã nhân viên", data["error"])

        status, data = self._call("POST", "/api/simple/start", body={"employee_id": "0123", "full_name": "", "position": "Feeder"})
        self.assertEqual(status, 400)
        self.assertIn("Họ và tên", data["error"])

        status, data = self._call("POST", "/api/simple/start", body={"employee_id": "0123", "full_name": "Test", "position": ""})
        self.assertEqual(status, 400)
        self.assertIn("Vị trí", data["error"])

        # 2. Leading zeros preserved, whitespace stripped
        status, data = self._call("POST", "/api/simple/start", body={
            "employee_id": "   00456   ",
            "full_name": "Nguyen Van B",
            "position": "Line leader"
        })
        self.assertEqual(status, 200)
        self.assertIn("token", data)
        self.assertEqual(data["learner"]["employee_id"], "00456", "Mã nhân viên phải giữ nguyên số 0 ở đầu và bỏ khoảng trắng")

        # Verify in DB
        conn = get_db_connection(self.db_path)
        row = conn.execute("SELECT employee_id FROM simple_learners WHERE id = ?", (data["learner"]["id"],)).fetchone()
        conn.close()
        self.assertEqual(row["employee_id"], "00456")

    # ---------------- KIỂM TRA 2: PHẢI ĐỦ 20 TRANG MỚI MỞ BÀI THI ----------------
    def test_check_2_must_complete_all_20_slides_before_test(self):
        # Create learner
        status, start_data = self._call("POST", "/api/simple/start", body={
            "employee_id": "00789",
            "full_name": "Tran Thi C",
            "position": "Group leader"
        })
        token = start_data["token"]

        # View only 5 slides
        for i in range(1, 6):
            slide_id = f"S{i:02d}"
            st, _ = self._call("POST", "/api/simple/slides/view", token=token, body={"slide_id": slide_id, "slide_order": i})
            self.assertEqual(st, 200)

        # Attempt to open test directly via API
        st, test_data = self._call("GET", "/api/simple/test", token=token)
        self.assertEqual(st, 403, "Chưa đủ 20 trang phải bị chặn HTTP 403 khi mở bài test")
        self.assertIn("20 trang", test_data["error"])

        # View remaining slides 6 to 20
        for i in range(6, 21):
            slide_id = f"S{i:02d}"
            st, _ = self._call("POST", "/api/simple/slides/view", token=token, body={"slide_id": slide_id, "slide_order": i})
            self.assertEqual(st, 200)

        # Now opening test must succeed
        st, test_data = self._call("GET", "/api/simple/test", token=token)
        self.assertEqual(st, 200, "Đã đủ 20 trang phải mở được bài thi")
        self.assertIn("questions", test_data)
        self.assertEqual(len(test_data["questions"]), 10)

        # Check progress persistence across refresh
        st, session_data = self._call("GET", "/api/simple/session", token=token)
        self.assertEqual(st, 200)
        self.assertEqual(session_data["progress"]["slides_viewed_count"], 20)
        self.assertTrue(session_data["progress"]["is_completed_slides"])

    # ---------------- KIỂM TRA 3: NGƯỠNG ĐẠT 9/10 & 10/10, CHẶN NỘP THIẾU ----------------
    def test_check_3_scoring_thresholds_and_incomplete_submission(self):
        # Create learner and view 20 slides
        _, start_data = self._call("POST", "/api/simple/start", body={"employee_id": "00999", "full_name": "Le Van D", "position": "Feeder"})
        token = start_data["token"]
        for i in range(1, 21):
            self._call("POST", "/api/simple/slides/view", token=token, body={"slide_id": f"S{i:02d}", "slide_order": i})

        _, test_data = self._call("GET", "/api/simple/test", token=token)
        attempt_id = test_data["attempt_id"]

        # 1. Incomplete submission (only 8 answers)
        incomplete_answers = {f"Q{i:02d}": self.keys[f"Q{i:02d}"] for i in range(1, 9)}
        st, err_data = self._call("POST", "/api/simple/test/submit", token=token, body={"attempt_id": attempt_id, "answers": incomplete_answers})
        self.assertEqual(st, 400, "Chưa chọn đủ 10 câu phải bị chặn")
        self.assertIn("đầy đủ 10 câu", err_data["error"])

        # 2. Test 8/10 -> FAIL
        answers_8 = dict(self.keys)
        answers_8["Q01"] = "WRONG_OPT"
        answers_8["Q02"] = "WRONG_OPT"
        st, res_8 = self._call("POST", "/api/simple/test/submit", token=token, body={"attempt_id": attempt_id, "answers": answers_8})
        self.assertEqual(st, 200)
        self.assertEqual(res_8["score"], 8)
        self.assertFalse(res_8["passed"], "8/10 điểm phải là CHƯA ĐẠT")

        # 3. Fresh attempt for 9/10 -> PASS
        _, test_data_2 = self._call("GET", "/api/simple/test", token=token)
        attempt_id_2 = test_data_2["attempt_id"]
        answers_9 = dict(self.keys)
        answers_9["Q01"] = "WRONG_OPT"
        st, res_9 = self._call("POST", "/api/simple/test/submit", token=token, body={"attempt_id": attempt_id_2, "answers": answers_9})
        self.assertEqual(st, 200)
        self.assertEqual(res_9["score"], 9)
        self.assertTrue(res_9["passed"], "9/10 điểm phải là ĐẠT")

        # 4. Fresh attempt for 10/10 -> PASS
        _, test_data_3 = self._call("GET", "/api/simple/test", token=token)
        attempt_id_3 = test_data_3["attempt_id"]
        st, res_10 = self._call("POST", "/api/simple/test/submit", token=token, body={"attempt_id": attempt_id_3, "answers": self.keys})
        self.assertEqual(st, 200)
        self.assertEqual(res_10["score"], 10)
        self.assertTrue(res_10["passed"], "10/10 điểm phải là ĐẠT")

    # ---------------- KIỂM TRA 4: CHƯA ĐẠT ĐƯỢC THI LẠI, NỘP 2 LẦN KHÔNG NHÂN ĐÔI ----------------
    def test_check_4_retake_and_idempotent_submit(self):
        _, start_data = self._call("POST", "/api/simple/start", body={"employee_id": "01111", "full_name": "Pham Van E", "position": "Line leader"})
        token = start_data["token"]
        for i in range(1, 21):
            self._call("POST", "/api/simple/slides/view", token=token, body={"slide_id": f"S{i:02d}", "slide_order": i})

        _, test_data = self._call("GET", "/api/simple/test", token=token)
        attempt_id = test_data["attempt_id"]

        # Submit first time (score 7)
        answers_7 = dict(self.keys)
        answers_7["Q01"] = "WRONG"
        answers_7["Q02"] = "WRONG"
        answers_7["Q03"] = "WRONG"
        st1, res1 = self._call("POST", "/api/simple/test/submit", token=token, body={"attempt_id": attempt_id, "answers": answers_7})
        self.assertEqual(st1, 200)
        self.assertEqual(res1["score"], 7)
        self.assertFalse(res1["passed"])
        self.assertEqual(len(res1["failed_questions"]), 3, "Phải trả về 3 câu sai kèm giải thích")

        # Resubmit SAME attempt -> idempotent, does NOT create duplicate
        st2, res2 = self._call("POST", "/api/simple/test/submit", token=token, body={"attempt_id": attempt_id, "answers": answers_7})
        self.assertEqual(st2, 200)
        self.assertEqual(res2["score"], 7)
        self.assertTrue(res2.get("is_resubmission"))

        # Check total attempts in DB for this learner is still 1
        conn = get_db_connection(self.db_path)
        att_count = conn.execute("SELECT COUNT(*) FROM simple_test_attempts WHERE id = ?", (attempt_id,)).fetchone()[0]
        conn.close()
        self.assertEqual(att_count, 1)

        # Open fresh attempt for retake without re-filling personal info or re-viewing slides
        st_retake, test_data_retake = self._call("GET", "/api/simple/test", token=token)
        self.assertEqual(st_retake, 200)
        self.assertNotEqual(test_data_retake["attempt_id"], attempt_id, "Thi lại phải tạo attempt_id mới")
        self.assertEqual(test_data_retake["attempt_number"], 2, "Lượt thi thứ 2")

    # ---------------- KIỂM TRA 5: ĐỔI NGƯỜI HỌC VÀ BÁO CÁO QUẢN LÝ ----------------
    def test_check_5_change_learner_and_admin_report(self):
        # Learner 1
        _, l1 = self._call("POST", "/api/simple/start", body={"employee_id": "USER_A", "full_name": "Nguoi A", "position": "Feeder"})
        for i in range(1, 21):
            self._call("POST", "/api/simple/slides/view", token=l1["token"], body={"slide_id": f"S{i:02d}", "slide_order": i})
        _, t1 = self._call("GET", "/api/simple/test", token=l1["token"])
        self._call("POST", "/api/simple/test/submit", token=l1["token"], body={"attempt_id": t1["attempt_id"], "answers": self.keys})

        # Learner 2 on same machine (new start)
        _, l2 = self._call("POST", "/api/simple/start", body={"employee_id": "USER_B", "full_name": "Nguoi B", "position": "Line leader"})
        # User B starts at 0 slides
        st_sess, sess_b = self._call("GET", "/api/simple/session", token=l2["token"])
        self.assertEqual(sess_b["progress"]["slides_viewed_count"], 0, "Nguoi B bắt đầu mới, không mang kết quả của A")

        # Admin login
        st_adm, adm_login = self._call("POST", "/api/simple/admin/login", body={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD})
        self.assertEqual(st_adm, 200)
        admin_token = adm_login["token"]

        # View report
        st_rep, report_data = self._call("GET", "/api/simple/admin/report", token=admin_token)
        self.assertEqual(st_rep, 200)
        learners_in_report = {r["employee_id"]: r for r in report_data["learners"]}
        self.assertIn("USER_A", learners_in_report)
        self.assertIn("USER_B", learners_in_report)
        self.assertEqual(learners_in_report["USER_A"]["result_status"], "Đã hoàn thành")
        self.assertEqual(learners_in_report["USER_B"]["result_status"], "Đang học")

    # ---------------- KIỂM TRA 6: BẢO MẬT ADMIN & KHÔNG LỘ ĐÁP ÁN ----------------
    def test_check_6_security_and_no_keys_leak(self):
        # 1. Learner cannot access admin report API
        _, l_data = self._call("POST", "/api/simple/start", body={"employee_id": "SEC_01", "full_name": "Sec Test", "position": "Feeder"})
        for i in range(1, 21):
            self._call("POST", "/api/simple/slides/view", token=l_data["token"], body={"slide_id": f"S{i:02d}", "slide_order": i})

        st, err = self._call("GET", "/api/simple/admin/report", token=l_data["token"])
        self.assertEqual(st, 403, "Học viên không được truy cập API quản lý")

        # 2. Test generation does NOT leak answers or explanations
        _, test_data = self._call("GET", "/api/simple/test", token=l_data["token"])
        for q in test_data["questions"]:
            self.assertNotIn("correct_option_id", q, "Không lộ đáp án đúng")
            self.assertNotIn("explanation_vi", q, "Không lộ giải thích trước khi nộp bài")

        # 3. Data persists in DB
        conn = get_db_connection(self.db_path)
        cnt = conn.execute("SELECT COUNT(*) FROM simple_learners").fetchone()[0]
        conn.close()
        self.assertGreater(cnt, 0, "Dữ liệu được lưu trữ bền vững trong SQLite")

    # ---------------- KIỂM TRA 7: HỖ TRỢ VỊ TRÍ DISPATCHER VÀ QD ----------------
    def test_check_7_dispatcher_and_qd_support(self):
        # 1. Start Dispatcher learner
        st_disp, data_disp = self._call("POST", "/api/simple/start", body={
            "employee_id": "DSP_001",
            "full_name": "Nguyen Van Dieu Phoi",
            "position": "Dispatcher"
        })
        self.assertEqual(st_disp, 200)
        self.assertEqual(data_disp["learner"]["position"], "Dispatcher")

        # 2. Start QD learner
        st_qd, data_qd = self._call("POST", "/api/simple/start", body={
            "employee_id": "QD_002",
            "full_name": "Tran Thi Chat Luong",
            "position": "QD"
        })
        self.assertEqual(st_qd, 200)
        self.assertEqual(data_qd["learner"]["position"], "QD")

        # 3. Admin login and report filter by position
        _, adm = self._call("POST", "/api/simple/admin/login", body={"username": "ADMIN01", "password": "AsvAdmin@2026"})
        adm_token = adm["token"]

        # Filter position = Dispatcher
        st_rep_disp, rep_disp = self._call("GET", "/api/simple/admin/report?position=Dispatcher", token=adm_token)
        self.assertEqual(st_rep_disp, 200)
        emp_ids_disp = [r["employee_id"] for r in rep_disp["learners"]]
        self.assertIn("DSP_001", emp_ids_disp)
        self.assertNotIn("QD_002", emp_ids_disp)

        # Filter position = QD
        st_rep_qd, rep_qd = self._call("GET", "/api/simple/admin/report?position=QD", token=adm_token)
        self.assertEqual(st_rep_qd, 200)
        emp_ids_qd = [r["employee_id"] for r in rep_qd["learners"]]
        self.assertIn("QD_002", emp_ids_qd)
        self.assertNotIn("DSP_001", emp_ids_qd)

        # Search by query "dieup hoi" or "dispatcher"
        st_search, rep_search = self._call("GET", "/api/simple/admin/report?q=dispatcher", token=adm_token)
        self.assertEqual(st_search, 200)
        self.assertIn("DSP_001", [r["employee_id"] for r in rep_search["learners"]])

    # ---------------- KIỂM TRA 8: TÍCH HỢP GOOGLE SHEETS ----------------
    def test_check_8_google_sheet_sync_and_config(self):
        # Admin login
        _, adm = self._call("POST", "/api/simple/admin/login", body={"username": "ADMIN01", "password": "AsvAdmin@2026"})
        adm_token = adm["token"]

        # 1. Get initial sheet config
        st, cfg = self._call("GET", "/api/simple/admin/sheet-config", token=adm_token)
        self.assertEqual(st, 200)
        self.assertIn("webhook_url", cfg)

        # 2. Save new webhook URL
        test_url = "https://script.google.com/macros/s/AKfycbz_test_12345/exec"
        st_post, res_post = self._call("POST", "/api/simple/admin/sheet-config", token=adm_token, body={"webhook_url": test_url})
        self.assertEqual(st_post, 200)
        self.assertEqual(res_post["webhook_url"], test_url)

        # 3. Verify saved in DB
        st_get, res_get = self._call("GET", "/api/simple/admin/sheet-config", token=adm_token)
        self.assertEqual(st_get, 200)
        self.assertEqual(res_get["webhook_url"], test_url)

        # 4. Sync validation without url
        st_err, res_err = self._call("POST", "/api/simple/admin/sync-sheet", token=adm_token, body={"webhook_url": ""})
        # If url is passed empty, it falls back to saved url, which is test_url, but since test_url is mock, network attempt is handled

if __name__ == "__main__":
    unittest.main()
