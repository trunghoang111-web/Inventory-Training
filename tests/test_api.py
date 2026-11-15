"""End-to-end API integration test suite."""
import unittest
import json
import tempfile
from pathlib import Path

from backend.config import COURSE_VERSION
from backend.seed import seed_database
from backend.api import handle_api_request
from backend.auth import create_access_token

class TestApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "test_api.db"
        seed_database(db_path=cls.db_path, create_bootstrap_admin=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def _call(self, method: str, path: str, token: str = None, body: dict = None, params: dict = None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        status, resp_headers, resp_bytes = handle_api_request(
            method=method,
            path=path,
            headers=headers,
            body_bytes=body_bytes,
            query_params=params or {},
            db_path=self.db_path
        )
        data = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        return status, data

    def test_01_auth_flow(self):
        # 1. Invalid login
        status, data = self._call("POST", "/api/auth/login", body={"employee_id": "ADMIN01", "password": "WrongPassword"})
        self.assertEqual(status, 401)

        # 2. Valid admin login
        status, data = self._call("POST", "/api/auth/login", body={"employee_id": "ADMIN01", "password": "AsvAdmin@2026"})
        self.assertEqual(status, 200)
        self.assertIn("token", data)
        token = data["token"]

        # 3. /api/auth/me
        status, me = self._call("GET", "/api/auth/me", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(me["user"]["employee_id"], "ADMIN01")

    def test_02_lessons_api_and_no_leak(self):
        status, data = self._call("GET", "/api/lessons")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["lessons"]), 12)

        # Test lesson detail L01
        status, l01 = self._call("GET", "/api/lessons/L01")
        self.assertEqual(status, 200)
        self.assertIn("lesson", l01)
        self.assertIn("knowledge_checks", l01)
        # Verify NO private answers or explanations leaked
        for qc in l01["knowledge_checks"]:
            self.assertNotIn("correct_option_id", qc)
            self.assertNotIn("explanation_vi", qc)

    def test_03_dashboard_api(self):
        # Admin login
        _, login_data = self._call("POST", "/api/auth/login", body={"employee_id": "ADMIN01", "password": "AsvAdmin@2026"})
        token = login_data["token"]

        status, stats = self._call("GET", "/api/dashboard/stats", token=token)
        self.assertEqual(status, 200)
        self.assertIn("active_required_real", stats)
        self.assertIn("trained_qualified", stats)
        self.assertIn("qualified_rate", stats)
        self.assertEqual(stats["planned_slots"], 132)

    def test_04_csv_import_preview_and_commit(self):
        _, login_data = self._call("POST", "/api/auth/login", body={"employee_id": "ADMIN01", "password": "AsvAdmin@2026"})
        token = login_data["token"]

        csv_content = """employee_id,full_name,job_title,crew,workcell,group,operational_roles,app_role,manager_employee_id,active,is_placeholder
ASV_TEST_01,Phan Van T,LINE_LEADER,B,WC01,N1,A|B,LEARNER,,true,false
ASV_TEST_02,Do Thi M,GROUP_LEADER,B,WC01,N1,CONTROLLER,LEARNER,,true,false
"""
        status, preview = self._call("POST", "/api/admin/import/preview", token=token, body={"csv_content": csv_content})
        self.assertEqual(status, 200)
        self.assertEqual(preview["summary"]["create_count"], 2)
        self.assertEqual(preview["summary"]["reject_count"], 0)

        # Commit import
        status, commit_res = self._call("POST", "/api/admin/import/commit", token=token, body={"preview": preview})
        self.assertEqual(status, 200)
        self.assertEqual(commit_res["created_count"], 2)

if __name__ == "__main__":
    unittest.main()
