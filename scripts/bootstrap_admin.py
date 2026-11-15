"""Bootstrap or reset Administrator account credentials."""
import sys
import uuid
import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import now_iso, DB_PATH
from backend.db import get_db_connection, db_transaction, init_db
from backend.auth import hash_password

def bootstrap_admin(emp_id="ADMIN01", full_name="Hệ Thống Quản Trị ASV", password=None):
    init_db()
    if not password:
        password = "AsvAdmin@2026"
    
    pwd_hash = hash_password(password)
    now_str = now_iso()

    with db_transaction() as conn:
        existing = conn.execute("SELECT id FROM users WHERE employee_id = ?", (emp_id,)).fetchone()
        if existing:
            user_id = existing["id"]
            conn.execute("""
                UPDATE users SET full_name = ?, password_hash = ?, active = 1, is_placeholder = 0, updated_at = ?
                WHERE id = ?
            """, (full_name, pwd_hash, now_str, user_id))
            print(f"✓ Đã cập nhật tài khoản quản trị: {emp_id}")
        else:
            user_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO users (id, employee_id, full_name, password_hash, active, is_placeholder, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, 0, ?, ?)
            """, (user_id, emp_id, full_name, pwd_hash, now_str, now_str))
            
            roles = ["SYSTEM_ADMIN", "CONTENT_ADMIN", "PM_VIEWER", "WCM_VIEWER", "WAREHOUSE_APPROVER"]
            for r in roles:
                conn.execute("""
                    INSERT INTO user_roles (id, user_id, app_role, scope_workcell_ids, created_at)
                    VALUES (?, ?, ?, '["ALL"]', ?)
                    ON CONFLICT(user_id, app_role) DO NOTHING
                """, (str(uuid.uuid4()), user_id, r, now_str))

            conn.execute("""
                INSERT INTO employee_profiles (id, user_id, job_title, crew, workcell_id, group_name, operational_roles, effective_at)
                VALUES (?, ?, 'PRODUCTION_MANAGER', 'OFFICE', 'WC_ALL', 'OFFICE', '["CONTROLLER"]', ?)
            """, (str(uuid.uuid4()), user_id, now_str))
            print(f"✓ Đã tạo mới tài khoản quản trị: {emp_id}")

    print(f"Mã đăng nhập: {emp_id}")
    print("Mật khẩu đã được băm PBKDF2-SHA256 với salt ngẫu nhiên.")

if __name__ == "__main__":
    emp_id = sys.argv[1] if len(sys.argv) > 1 else "ADMIN01"
    pwd = sys.argv[2] if len(sys.argv) > 2 else "AsvAdmin@2026"
    bootstrap_admin(emp_id, password=pwd)
