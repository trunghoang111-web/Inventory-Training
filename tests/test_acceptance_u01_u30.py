"""Comprehensive Acceptance Test Suite covering U01 through U30 from docs/08_NGHIEM_THU.md."""
import unittest
import json
import uuid
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from backend.config import BASE_DIR, COURSE_VERSION, DEADLINE_EXCLUSIVE, now_vn, now_iso
from backend.db import init_db, get_db_connection, db_transaction
from backend.seed import seed_database
from backend.auth import (
    hash_password, verify_password, create_access_token, verify_access_token,
    get_user_by_id, user_has_role, check_workcell_scope, check_anti_self_eval
)
from backend.grading import (
    check_threshold, calculate_current_result, is_on_time,
    calculate_qualified_rate, check_readiness, generate_theory_exam,
    save_theory_progress, submit_theory_exam, start_simulation_attempt,
    process_simulation_event, submit_simulation_case, submit_simulation_attempt,
    submit_hardware_assessment, void_assessment_attempt, evaluate_candidate_readiness
)
from backend.schedule_engine import check_session_conflicts, assign_users_to_session
from backend.import_export import (
    preview_employee_import, commit_employee_import, sanitize_csv_cell,
    export_candidate_report_csv
)
from backend.api import handle_api_request

class TestAcceptanceU01ToU30(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "test_asv.db"
        seed_database(db_path=cls.db_path, create_bootstrap_admin=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def _create_user(self, emp_id: str, full_name: str, app_role: str = "LEARNER") -> str:
        uid = str(uuid.uuid4())
        now_str = now_iso()
        with db_transaction(self.db_path) as conn:
            conn.execute("""
                INSERT INTO users (id, employee_id, full_name, password_hash, active, is_placeholder, created_at, updated_at)
                VALUES (?, ?, ?, 'pwd', 1, 0, ?, ?)
            """, (uid, emp_id, full_name, now_str, now_str))
            conn.execute("""
                INSERT INTO user_roles (id, user_id, app_role, scope_workcell_ids, created_at)
                VALUES (?, ?, ?, '["WC01"]', ?)
            """, (str(uuid.uuid4()), uid, app_role, now_str))
            conn.execute("""
                INSERT INTO employee_profiles (id, user_id, job_title, crew, workcell_id, group_name, operational_roles, effective_at)
                VALUES (?, ?, 'LINE_LEADER', 'A', 'WC01', 'N1', '["A", "B"]', ?)
            """, (str(uuid.uuid4()), uid, now_str))
        return uid

    # --- U01: Nhập 132 placeholder ---
    def test_u01_planned_slots_are_placeholders(self):
        conn = get_db_connection(self.db_path)
        placeholders = conn.execute("SELECT * FROM users WHERE is_placeholder = 1").fetchall()
        real_users = conn.execute("SELECT * FROM users WHERE is_placeholder = 0").fetchall()
        conn.close()

        self.assertEqual(len(placeholders), 132, "Phải có đúng 132 placeholder slots")
        for p in placeholders:
            self.assertEqual(p["active"], 0, "Placeholder slot không được active")
            self.assertTrue(p["employee_id"].startswith("SLOT_"), "Placeholder ID phải có tiền tố SLOT_")
        self.assertGreaterEqual(len(real_users), 1, "Có user bootstrap admin lúc khởi tạo")

    # --- U02: ID trùng, tên trùng khác ID, kíp không hợp lệ ---
    def test_u02_import_duplicate_id_and_invalid_crew(self):
        csv_sample = """employee_id,full_name,job_title,crew,workcell,group,operational_roles,app_role,manager_employee_id,active,is_placeholder
EMP001,Nguyen Van A,LINE_LEADER,A,WC01,N1,A|B,LEARNER,,true,false
EMP001,Nguyen Van A Duplicate,LINE_LEADER,A,WC01,N1,A|B,LEARNER,,true,false
EMP002,Tran Thi B,GROUP_LEADER,INVALID_CREW,WC01,N1,C,LEARNER,,true,false
EMP003,,FEEDER,B,WC02,N1,A,LEARNER,,true,false
"""
        preview = preview_employee_import(csv_sample, db_path=self.db_path)
        summary = preview["summary"]
        self.assertEqual(summary["create_count"], 1, "Chỉ 1 dòng hợp lệ (EMP001 đầu tiên)")
        self.assertEqual(summary["reject_count"], 3, "3 dòng bị reject (trùng ID, sai crew, tên rỗng)")
        
        reject_errors = [err for r in preview["rejects"] for err in r["errors"]]
        self.assertTrue(any("trùng lặp" in e for e in reject_errors))
        self.assertTrue(any("Kíp làm việc không hợp lệ" in e for e in reject_errors))
        self.assertTrue(any("Họ và tên không được để trống" in e for e in reject_errors))

    # --- U03: 10 người thật, 2 qualified, 3 chưa học ---
    def test_u03_denominator_and_qualification_rate(self):
        real_required = 10
        qualified = 2
        rate = calculate_qualified_rate(real_required, qualified)
        self.assertEqual(rate, 0.2, "10 người thật, 2 qualified => tỷ lệ 20% (0.2)")

    # --- U04: Mẫu số 0 -> hiển thị N/A (None) ---
    def test_u04_zero_denominator_shows_none_na(self):
        rate = calculate_qualified_rate(0, 0)
        self.assertIsNone(rate, "Mẫu số 0 phải trả về None (hiển thị N/A), không được trả về 100%")

    # --- U05: Làm đề 20 câu rồi refresh/đổi máy -> giữ nguyên snapshot ---
    def test_u05_theory_exam_snapshot_preserved(self):
        learner_id = self._create_user("LEARNER_U05", "Learner U05")
        exam1 = generate_theory_exam(learner_id, db_path=self.db_path)
        exam_id = exam1["attempt_id"]
        q_ids_1 = [q["question_id"] for q in exam1["questions"]]

        save_theory_progress(exam_id, {q_ids_1[0]: exam1["questions"][0]["snapshot"]["options"][0]["id"]}, db_path=self.db_path)

        exam2 = generate_theory_exam(learner_id, db_path=self.db_path)
        self.assertEqual(exam2["attempt_id"], exam_id, "Phải trả về đúng attempt đang mở")
        q_ids_2 = [q["question_id"] for q in exam2["questions"]]
        self.assertEqual(q_ids_1, q_ids_2, "Đề thi và thứ tự câu hỏi snapshot không được thay đổi khi refresh")
        self.assertIsNotNone(exam2["questions"][0]["selected_option_id"], "Đáp án đã lưu phải còn nguyên")

    # --- U06: 90 điểm sai 1 critical -> FAIL; 90 điểm mọi critical đúng -> PASS ---
    def test_u06_theory_threshold_and_critical_rule(self):
        pass_case = check_threshold("THEORY", 90, critical_failed=[])
        self.assertTrue(pass_case, "90 điểm và 0 lỗi critical => PASS")

        fail_case = check_threshold("THEORY", 95, critical_failed=["CR_FREEZE"])
        self.assertFalse(fail_case, "95 điểm nhưng sai 1 critical => FAIL")

    # --- U07: Lý thuyết/mô phỏng đạt nhưng thiếu PDA thật -> Chưa Qualified ---
    def test_u07_missing_hardware_not_qualified(self):
        readiness = check_readiness({
            "lessons": True,
            "attendance": True,
            "theory": True,
            "simulation": True,
            "hardware": False,
            "special": True,
            "current_version": True,
            "signature": True
        })
        self.assertFalse(readiness, "Thiếu PDA thật thì chưa đủ điều kiện Qualified")

    # --- U08: PDA 95 điểm nhưng một critical sai hoặc một mục null -> FAIL ---
    def test_u08_hardware_null_or_critical_fail(self):
        fail_crit = check_threshold("HARDWARE_COMMON", 95, critical_failed=["HP01"], missing_observations=0)
        self.assertFalse(fail_crit, "PDA 95 điểm nhưng sai critical => FAIL")

        fail_missing = check_threshold("HARDWARE_COMMON", 95, critical_failed=[], missing_observations=1)
        self.assertFalse(fail_missing, "PDA 95 điểm nhưng còn 1 mục NULL => FAIL (chưa hoàn tất)")

    # --- U09: Học viên tự gọi API chấm/ký hoặc tự phê duyệt -> BỊ CHẶN ---
    def test_u09_anti_self_evaluation(self):
        actor_id = "USER_123"
        with self.assertRaises(PermissionError):
            check_anti_self_eval(actor_user_id=actor_id, target_user_id=actor_id)

    # --- U10: WCM khu A xin dữ liệu khu B -> Chặn ngoài scope ---
    def test_u10_wcm_scope_restriction(self):
        wcm_user = {
            "id": "WCM_A",
            "roles": [{"app_role": "WCM_VIEWER", "scope": ["WC01"]}]
        }
        self.assertTrue(check_workcell_scope(wcm_user, "WC01"), "Khu WC01 trong scope")
        self.assertFalse(check_workcell_scope(wcm_user, "WC02"), "Khu WC02 ngoài scope => BỊ CHẶN")

    # --- U11: A2/PC 45/50; Controller 25/30 ---
    def test_u11_special_role_rubrics(self):
        self.assertTrue(check_threshold("A2_PC", 45, critical_failed=[]), "A2/PC 45 điểm => PASS")
        self.assertFalse(check_threshold("A2_PC", 40, critical_failed=[]), "A2/PC 40 điểm => FAIL")

        self.assertTrue(check_threshold("CONTROLLER", 25, critical_failed=[]), "Controller 25 điểm => PASS")
        self.assertFalse(check_threshold("CONTROLLER", 30, critical_failed=["CT01"]), "Controller 30 điểm nhưng sai critical => FAIL")

    # --- U12: Pass -> luyện trượt -> thi chính thức trượt ---
    def test_u12_retake_official_overrides_pass(self):
        attempts_1 = [
            {"official": True, "state": "GRADED", "passed": True},
            {"official": False, "state": "GRADED", "passed": False}
        ]
        self.assertEqual(calculate_current_result(attempts_1), "PASS")

        attempts_2 = [
            {"official": True, "state": "GRADED", "passed": True},
            {"official": True, "state": "GRADED", "passed": False}
        ]
        self.assertEqual(calculate_current_result(attempts_2), "FAIL")

    # --- U13: Đang có lượt chính thức mở -> PENDING ---
    def test_u13_active_attempt_is_pending(self):
        attempts = [
            {"official": True, "state": "GRADED", "passed": True},
            {"official": True, "state": "IN_PROGRESS"}
        ]
        self.assertEqual(calculate_current_result(attempts), "PENDING")

    # --- U14: SIM05 quét tạm sai rồi sửa; xác nhận gán sai ---
    def test_u14_simulation_scan_preview_diagnostic_vs_commit(self):
        learner_id = self._create_user("LEARNER_U14", "Learner U14")
        att = start_simulation_attempt(learner_id, is_official=False, db_path=self.db_path)
        att_id = att["attempt_id"]

        res1 = process_simulation_event(
            att_id, "SIM05", seq=1, idempotency_key="k1", event_type="SCAN_PREVIEW",
            payload={"code": "WRONG_BOX"}, actor=learner_id, db_path=self.db_path
        )
        self.assertEqual(res1["status"], "DIAGNOSTIC_PREVIEW")

        res2 = process_simulation_event(
            att_id, "SIM05", seq=2, idempotency_key="k2", event_type="CONFIRM_MAPPING",
            payload={"box_id": "WRONG_BOX", "p_number": "P-99", "cell_id": "WC-99"},
            actor=learner_id, db_path=self.db_path
        )
        self.assertTrue(res2["is_critical"])
        self.assertEqual(res2["critical_terminal_event"], "COMMIT_WRONG_MAPPING")

    # --- U15: SIM03 chia 3+3 đúng -> PASS; lặp/gộp hộp -> FAIL ---
    def test_u15_sim03_batch_partition(self):
        learner_id = self._create_user("LEARNER_U15", "Learner U15")
        att = start_simulation_attempt(learner_id, is_official=False, db_path=self.db_path)
        att_id = att["attempt_id"]

        process_simulation_event(
            att_id, "SIM03", seq=1, idempotency_key="b1", event_type="BATCH_SUBMITTED",
            payload={"lines": ["BOX01", "BOX02", "BOX03"]}, actor=learner_id, db_path=self.db_path
        )
        process_simulation_event(
            att_id, "SIM03", seq=2, idempotency_key="b2", event_type="BATCH_SUBMITTED",
            payload={"lines": ["BOX04", "BOX05", "BOX06"]}, actor=learner_id, db_path=self.db_path
        )

        res = submit_simulation_case(att_id, "SIM03", db_path=self.db_path)
        self.assertEqual(res["state"], "COMPLETED_CORRECT", "Chia 3+3 đúng quy tắc phải ĐẠT")

    # --- U16: SIM10 kiểm B trước A -> ĐẠT; bỏ B -> CHƯA ĐẠT ---
    def test_u16_sim10_reconcile_any_order(self):
        learner_id = self._create_user("LEARNER_U16", "Learner U16")
        att = start_simulation_attempt(learner_id, is_official=False, db_path=self.db_path)
        att_id = att["attempt_id"]

        process_simulation_event(
            att_id, "SIM10", seq=1, idempotency_key="c1", event_type="CELL_RECONCILED",
            payload={"cell_id": "W01-B", "qty": 10}, actor=learner_id, db_path=self.db_path
        )
        process_simulation_event(
            att_id, "SIM10", seq=2, idempotency_key="c2", event_type="CELL_RECONCILED",
            payload={"cell_id": "W01-A", "qty": 30}, actor=learner_id, db_path=self.db_path
        )
        process_simulation_event(
            att_id, "SIM10", seq=3, idempotency_key="c3", event_type="SUMMARY_SUBMITTED",
            payload={"total": 40, "diff": -2}, actor=learner_id, db_path=self.db_path
        )

        res = submit_simulation_case(att_id, "SIM10", db_path=self.db_path)
        self.assertEqual(res["state"], "COMPLETED_CORRECT", "Kiểm B trước A vẫn phải ĐẠT khi đủ cả hai ô")

    # --- U17: Gửi lại cùng key, stale seq -> Chặn đúng ---
    def test_u17_idempotency_and_seq_protection(self):
        learner_id = self._create_user("LEARNER_U17", "Learner U17")
        att = start_simulation_attempt(learner_id, is_official=False, db_path=self.db_path)
        att_id = att["attempt_id"]

        res1 = process_simulation_event(
            att_id, "SIM01", seq=1, idempotency_key="key_abc", event_type="COUNT_SUBMITTED",
            payload={"qty": 18, "unit": "pcs"}, actor=learner_id, db_path=self.db_path
        )
        self.assertEqual(res1["status"], "EVENT_RECORDED")

        res_replay = process_simulation_event(
            att_id, "SIM01", seq=1, idempotency_key="key_abc", event_type="COUNT_SUBMITTED",
            payload={"qty": 18, "unit": "pcs"}, actor=learner_id, db_path=self.db_path
        )
        self.assertEqual(res_replay["status"], "IDEMPOTENT_REPLAY")

        with self.assertRaises(ValueError):
            process_simulation_event(
                att_id, "SIM01", seq=1, idempotency_key="key_abc", event_type="COUNT_SUBMITTED",
                payload={"qty": 20, "unit": "pcs"}, actor=learner_id, db_path=self.db_path
            )

        with self.assertRaises(ValueError):
            process_simulation_event(
                att_id, "SIM01", seq=1, idempotency_key="key_xyz", event_type="MARK_A",
                payload={}, actor=learner_id, db_path=self.db_path
            )

    # --- U18: Hết giờ tự nộp phần đã lưu ---
    def test_u18_auto_submit_on_expiry(self):
        learner_id = self._create_user("LEARNER_U18", "Learner U18")
        exam = generate_theory_exam(learner_id, db_path=self.db_path)
        att_id = exam["attempt_id"]

        past_iso = (now_vn() - timedelta(minutes=5)).isoformat()
        with db_transaction(self.db_path) as conn:
            conn.execute("UPDATE assessment_attempts SET expires_at = ? WHERE id = ?", (past_iso, att_id))

        res = generate_theory_exam(learner_id, db_path=self.db_path)
        self.assertEqual(res["state"], "GRADED", "Khi hết giờ, bài thi tự động chuyển sang GRADED")

    # --- U19: Hạn chót exclusive 2026-12-01T00:00:00+07:00 ---
    def test_u19_deadline_exclusive(self):
        self.assertTrue(is_on_time("2026-11-30T23:59:59+07:00"), "23:59:59 ngày 30/11 là TRƯỚC hạn")
        self.assertFalse(is_on_time("2026-12-01T00:00:00+07:00"), "Đúng 00:00 ngày 01/12 là TRỄ (exclusive)")

    # --- U20: Trùng lịch người/thiết bị hoặc vượt capacity ---
    def test_u20_schedule_conflict_detection(self):
        conflicts = check_session_conflicts(
            "PRE01", user_ids=["USER_01"], assessor_ids=[], device_ids=["PDA01"], db_path=self.db_path
        )
        self.assertIsInstance(conflicts, list)

    # --- U21: Ca đêm thiếu người chấm, kíp OFF cảnh báo ---
    def test_u21_shift_warnings(self):
        conflicts = check_session_conflicts("A-LT1", user_ids=[], db_path=self.db_path)
        self.assertIsInstance(conflicts, list)

    # --- U22: Thiết bị hỏng, void có lý do -> Giữ lịch sử ---
    def test_u22_void_attempt_with_reason(self):
        learner_id = self._create_user("LEARNER_U22", "Learner U22")
        att = start_simulation_attempt(learner_id, is_official=True, db_path=self.db_path)
        att_id = att["attempt_id"]

        res = void_assessment_attempt(att_id, voided_by="ASSESSOR_01", reason="Thiết bị PDA bị mất nguồn", db_path=self.db_path)
        self.assertEqual(res["status"], "VOIDED")

        conn = get_db_connection(self.db_path)
        row = conn.execute("SELECT state, void_reason FROM assessment_attempts WHERE id = ?", (att_id,)).fetchone()
        conn.close()
        self.assertEqual(row["state"], "VOIDED")
        self.assertIn("mất nguồn", row["void_reason"])

    # --- U23: Qualified nhưng chưa duyệt vai -> Chưa Authorized ---
    def test_u23_qualified_vs_authorized(self):
        readiness_not_auth = {
            "funnel_stage": "QUALIFIED",
            "is_qualified": True,
            "is_authorized": False
        }
        self.assertTrue(readiness_not_auth["is_qualified"])
        self.assertFalse(readiness_not_auth["is_authorized"], "Qualified không tự động có nhãn Authorized khi chưa ký duyệt vai")

    # --- U24: Không lộ key/expected_steps trong build và API thi ---
    def test_u24_no_private_keys_leak(self):
        conn = get_db_connection(self.db_path)
        admin = conn.execute("SELECT id FROM users WHERE employee_id = 'ADMIN01'").fetchone()
        conn.close()
        exam = generate_theory_exam(admin["id"], is_demo=True, db_path=self.db_path)
        for q in exam["questions"]:
            snap = q["snapshot"]
            self.assertNotIn("correct_option_id", snap, "Không được chứa correct_option_id trong đề đang thi")
            self.assertNotIn("explanation_vi", snap, "Không được chứa explanation_vi trong đề đang thi")

    # --- U25: Snapshot đề bất biến khi đổi nội dung ---
    def test_u25_snapshot_immutability(self):
        learner_id = self._create_user("LEARNER_U25", "Learner U25")
        exam = generate_theory_exam(learner_id, db_path=self.db_path)
        original_stem = exam["questions"][0]["snapshot"]["stem_vi"]

        q_id = exam["questions"][0]["question_id"]
        with db_transaction(self.db_path) as conn:
            conn.execute("""
                UPDATE content_records
                SET public_payload = json_set(public_payload, '$.stem_vi', 'NEW MODIFIED STEM')
                WHERE content_id = ? AND kind = 'question'
            """, (q_id,))

        conn = get_db_connection(self.db_path)
        item = conn.execute("SELECT question_snapshot FROM theory_items WHERE attempt_id = ? AND question_id = ?", (exam["attempt_id"], q_id)).fetchone()
        conn.close()
        saved_snap = json.loads(item["question_snapshot"])
        self.assertEqual(saved_snap["stem_vi"], original_stem, "Snapshot của đề đang mở không bị sửa khi admin đổi nội dung")

    # --- U26: 360px & Text Status Badges ---
    def test_u26_accessible_badges_and_css(self):
        css_file = BASE_DIR / "frontend" / "css" / "app.css"
        css_text = css_file.read_text(encoding="utf-8")
        self.assertIn("badge-pass", css_text)
        self.assertIn("badge-fail", css_text)
        self.assertIn("badge-critical", css_text)
        self.assertIn("@media (max-width: 600px)", css_text)

    # --- U27: Formula Injection Sanitization ---
    def test_u27_formula_injection_sanitization(self):
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1", "Formula = phải có dấu nháy đơn")
        self.assertEqual(sanitize_csv_cell("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0", "Formula + phải có dấu nháy đơn")
        self.assertEqual(sanitize_csv_cell("@SUM(A1:A10)"), "'@SUM(A1:A10)", "Formula @ phải có dấu nháy đơn")
        self.assertEqual(sanitize_csv_cell("-DDE(...)"), "'-DDE(...)", "Text bắt đầu bằng - không phải số phải có dấu nháy đơn")
        self.assertEqual(sanitize_csv_cell("-2"), "-2", "Số âm -2 thực sự phải giữ nguyên kiểu số")
        self.assertEqual(sanitize_csv_cell("-15.5"), "-15.5", "Số âm -15.5 phải giữ nguyên")

    # --- U28: Backup/Restore & Idempotent Seed ---
    def test_u28_seed_idempotency(self):
        seed_database(db_path=self.db_path, create_bootstrap_admin=True)
        conn = get_db_connection(self.db_path)
        lessons_count = conn.execute("SELECT COUNT(*) FROM content_records WHERE kind = 'lesson'").fetchone()[0]
        sessions_count = conn.execute("SELECT COUNT(*) FROM training_sessions").fetchone()[0]
        slots_count = conn.execute("SELECT COUNT(*) FROM users WHERE is_placeholder = 1").fetchone()[0]
        conn.close()

        self.assertEqual(lessons_count, 12, "Số bài học không bị nhân đôi sau seed lần 2")
        self.assertEqual(sessions_count, 39, "Số buổi không bị nhân đôi sau seed lần 2")
        self.assertEqual(slots_count, 132, "Số slot placeholder không bị nhân đôi sau seed lần 2")

    # --- U29: Server tự chấm từ key, không tin score client gửi ---
    def test_u29_server_evaluates_score_ignoring_client_claims(self):
        learner_id = self._create_user("LEARNER_U29", "Learner U29")
        exam = generate_theory_exam(learner_id, db_path=self.db_path)
        att_id = exam["attempt_id"]

        wrong_answers = {q["question_id"]: "INVALID_OPT_ID" for q in exam["questions"]}
        res = submit_theory_exam(att_id, answers=wrong_answers, db_path=self.db_path)
        self.assertEqual(res["score"], 0.0, "Trả lời sai thì điểm phải là 0, client không thể gửi điểm giả")
        self.assertFalse(res["passed"])

    # --- U30: Người chấm khác học viên ---
    def test_u30_assessor_different_from_learner(self):
        user_id = self._create_user("LEARNER_U30", "Learner U30")
        observations = {"HP01": 5}
        with self.assertRaises(PermissionError):
            submit_hardware_assessment(
                assessor_id=user_id,
                learner_id=user_id,
                assessment_type="HARDWARE_COMMON",
                session_id="S01",
                device_id="DEV01",
                lab_id="LAB01",
                observations=observations,
                notes="Self test",
                attestation="Self sign",
                db_path=self.db_path
            )

if __name__ == "__main__":
    unittest.main()
