"""CSV Import with Preview & Validation, and Formula-Injection-Safe CSV Export."""
import csv
import io
import uuid
import json
from typing import Dict, Any, List, Tuple, Optional
from backend.config import COURSE_VERSION, now_iso
from backend.db import get_db_connection, db_transaction
from backend.auth import hash_password, check_workcell_scope
from backend.grading import evaluate_candidate_readiness

VALID_JOB_TITLES = {"LINE_LEADER", "GROUP_LEADER", "FEEDER", "WORKCELL_MANAGER", "PRODUCTION_MANAGER", "OTHER"}
VALID_CREWS = {"A", "B", "C", "D", "OFFICE"}
VALID_OPERATIONAL_ROLES = {"A", "B", "C", "A2", "PC", "PDT", "CONTROLLER", "INTERNAL_CONTROL"}
VALID_APP_ROLES = {"LEARNER", "TRAINER", "ASSESSOR", "WCM_VIEWER", "PM_VIEWER", "CONTENT_ADMIN", "SYSTEM_ADMIN", "WAREHOUSE_APPROVER"}

def sanitize_csv_cell(value: Any) -> str:
    """Sanitizes text cells starting with =, +, -, @ to prevent formula injection.
    Genuine negative numbers (e.g. -2, -15.5) are preserved as valid numbers.
    """
    if value is None:
        return ""
    s = str(value)
    if not s:
        return ""
    # Check if genuinely a negative number
    if s.startswith("-"):
        try:
            float(s)
            return s  # Valid negative number, preserve as-is
        except ValueError:
            return f"'{s}"
    if s[0] in ("=", "+", "@"):
        return f"'{s}"
    return s

def preview_employee_import(csv_content: str, db_path=None) -> Dict[str, Any]:
    """Parses and validates CSV input, providing preview of creates, updates, and rejects."""
    reader = csv.DictReader(io.StringIO(csv_content))
    creates = []
    updates = []
    rejects = []
    seen_ids = set()

    conn = get_db_connection(db_path)
    try:
        existing_users = {
            u["employee_id"]: u for u in conn.execute("SELECT id, employee_id, full_name, is_placeholder FROM users").fetchall()
        }

        line_num = 1
        for row in reader:
            line_num += 1
            errors = []
            emp_id = (row.get("employee_id") or "").strip()
            full_name = (row.get("full_name") or "").strip()
            job_title = (row.get("job_title") or "LINE_LEADER").strip().upper()
            crew = (row.get("crew") or "").strip().upper()
            workcell = (row.get("workcell") or "WC01").strip()
            op_roles_raw = (row.get("operational_roles") or "").strip()
            app_role = (row.get("app_role") or "LEARNER").strip().upper()
            is_placeholder_str = (row.get("is_placeholder") or "false").strip().lower()
            is_placeholder = is_placeholder_str in ("true", "1", "yes")
            active_str = (row.get("active") or "true").strip().lower()
            active = active_str in ("true", "1", "yes")

            # Validation
            if not emp_id and not is_placeholder:
                errors.append("Mã nhân viên (employee_id) không được để trống khi không phải placeholder.")
            if emp_id:
                if emp_id in seen_ids:
                    errors.append(f"Mã nhân viên '{emp_id}' bị trùng lặp trong file import.")
                seen_ids.add(emp_id)

            if not full_name and not is_placeholder:
                errors.append("Họ và tên không được để trống.")

            if job_title and job_title not in VALID_JOB_TITLES:
                errors.append(f"Chức danh không hợp lệ: '{job_title}'.")

            if crew and crew not in VALID_CREWS:
                errors.append(f"Kíp làm việc không hợp lệ: '{crew}' (chỉ chấp nhận A, B, C, D hoặc OFFICE).")

            op_roles = [r.strip() for r in op_roles_raw.split("|") if r.strip()] if op_roles_raw else []
            for r in op_roles:
                if r not in VALID_OPERATIONAL_ROLES:
                    errors.append(f"Vai kiểm kê không hợp lệ: '{r}'.")

            if app_role and app_role not in VALID_APP_ROLES:
                errors.append(f"Vai ứng dụng không hợp lệ: '{app_role}'.")

            row_record = {
                "line": line_num,
                "slot_id": (row.get("slot_id") or "").strip(),
                "employee_id": emp_id,
                "full_name": full_name,
                "job_title": job_title,
                "crew": crew,
                "workcell": workcell,
                "group": (row.get("group") or "N1").strip(),
                "operational_roles": op_roles,
                "app_role": app_role,
                "manager_employee_id": (row.get("manager_employee_id") or "").strip(),
                "active": active,
                "is_placeholder": is_placeholder
            }

            if errors:
                rejects.append({"row": row_record, "errors": errors})
            elif emp_id in existing_users:
                row_record["existing_user_id"] = existing_users[emp_id]["id"]
                updates.append(row_record)
            else:
                creates.append(row_record)

        return {
            "summary": {
                "total_rows": line_num - 1,
                "create_count": len(creates),
                "update_count": len(updates),
                "reject_count": len(rejects)
            },
            "creates": creates,
            "updates": updates,
            "rejects": rejects
        }
    finally:
        conn.close()

def commit_employee_import(preview_result: Dict[str, Any], default_password: str = "Ajax@12345", db_path=None) -> Dict[str, Any]:
    """Commits validated creates and updates in a single database transaction."""
    pwd_hash = hash_password(default_password)
    created_ids = []
    updated_ids = []

    with db_transaction(db_path) as conn:
        # Process creates
        for item in preview_result.get("creates", []):
            user_id = str(uuid.uuid4())
            now_str = now_iso()
            conn.execute("""
                INSERT INTO users (id, employee_id, full_name, password_hash, active, is_placeholder, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, item["employee_id"], item["full_name"], pwd_hash,
                1 if item["active"] else 0,
                1 if item["is_placeholder"] else 0,
                now_str, now_str
            ))

            # Roles
            conn.execute("""
                INSERT INTO user_roles (id, user_id, app_role, scope_workcell_ids, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, app_role) DO NOTHING
            """, (
                str(uuid.uuid4()), user_id, item["app_role"],
                json.dumps([item["workcell"]]), now_str
            ))

            # Profile
            conn.execute("""
                INSERT INTO employee_profiles (
                    id, user_id, job_title, crew, workcell_id, group_name, operational_roles,
                    manager_employee_id, slot_id, effective_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), user_id, item["job_title"], item["crew"], item["workcell"],
                item["group"], json.dumps(item["operational_roles"]),
                item.get("manager_employee_id"), item.get("slot_id"), now_str
            ))

            # Auto enroll if not placeholder
            if not item["is_placeholder"] and item["active"]:
                conn.execute("""
                    INSERT INTO enrollments (id, user_id, course_version, required, assigned_roles, status, created_at)
                    VALUES (?, ?, ?, 1, ?, 'ENROLLED', ?)
                    ON CONFLICT(user_id, course_version) DO NOTHING
                """, (
                    str(uuid.uuid4()), user_id, COURSE_VERSION,
                    json.dumps(item["operational_roles"]), now_str
                ))

            created_ids.append(item["employee_id"])

        # Process updates
        for item in preview_result.get("updates", []):
            user_id = item["existing_user_id"]
            now_str = now_iso()
            conn.execute("""
                UPDATE users
                SET full_name = ?, active = ?, is_placeholder = ?, updated_at = ?
                WHERE id = ?
            """, (
                item["full_name"],
                1 if item["active"] else 0,
                1 if item["is_placeholder"] else 0,
                now_str, user_id
            ))

            conn.execute("""
                UPDATE employee_profiles
                SET job_title = ?, crew = ?, workcell_id = ?, group_name = ?,
                    operational_roles = ?, manager_employee_id = ?, slot_id = ?, effective_at = ?
                WHERE user_id = ?
            """, (
                item["job_title"], item["crew"], item["workcell"], item["group"],
                json.dumps(item["operational_roles"]), item.get("manager_employee_id"),
                item.get("slot_id"), now_str, user_id
            ))

            if not item["is_placeholder"] and item["active"]:
                conn.execute("""
                    INSERT INTO enrollments (id, user_id, course_version, required, assigned_roles, status, created_at)
                    VALUES (?, ?, ?, 1, ?, 'ENROLLED', ?)
                    ON CONFLICT(user_id, course_version) DO UPDATE SET
                        assigned_roles = excluded.assigned_roles
                """, (
                    str(uuid.uuid4()), user_id, COURSE_VERSION,
                    json.dumps(item["operational_roles"]), now_str
                ))

            updated_ids.append(item["employee_id"])

    return {
        "success": True,
        "created_count": len(created_ids),
        "updated_count": len(updated_ids)
    }

def export_candidate_report_csv(requesting_user: Dict[str, Any], filter_crew: Optional[str] = None, filter_workcell: Optional[str] = None, db_path=None) -> str:
    """Exports individual learner progress and qualification report to CSV.
    Enforces workcell scope checks and formula-injection sanitization.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Mã nhân viên", "Họ và tên", "Kíp", "Workcell", "Chức danh", "Vai kiểm kê",
        "Trạng thái năng lực", "Đủ điều kiện (Qualified)", "Đã phê duyệt vai (Authorized)",
        "Lý thuyết đạt", "Mô phỏng đạt", "Sát hạch PDA đạt", "Chữ ký giám khảo",
        "Điều kiện còn thiếu", "Phiên bản đào tạo"
    ])

    conn = get_db_connection(db_path)
    try:
        users = conn.execute("""
            SELECT u.id, u.employee_id, u.full_name, p.crew, p.workcell_id, p.job_title, p.operational_roles
            FROM users u
            JOIN employee_profiles p ON p.user_id = u.id
            WHERE u.is_placeholder = 0 AND u.active = 1
            ORDER BY u.employee_id ASC
        """).fetchall()

        for u in users:
            workcell = u["workcell_id"] or ""
            crew = u["crew"] or ""

            # Check scope
            if not check_workcell_scope(requesting_user, workcell):
                continue
            if filter_workcell and workcell != filter_workcell:
                continue
            if filter_crew and crew != filter_crew:
                continue

            readiness = evaluate_candidate_readiness(u["id"], db_path=db_path)
            op_roles_list = json.loads(u["operational_roles"]) if u["operational_roles"] else []

            row = [
                sanitize_csv_cell(u["employee_id"]),
                sanitize_csv_cell(u["full_name"]),
                sanitize_csv_cell(crew),
                sanitize_csv_cell(workcell),
                sanitize_csv_cell(u["job_title"]),
                sanitize_csv_cell(", ".join(op_roles_list)),
                sanitize_csv_cell(readiness["funnel_stage"]),
                sanitize_csv_cell("ĐẠT" if readiness["is_qualified"] else "CHƯA"),
                sanitize_csv_cell("ĐÃ DUYỆT" if readiness["is_authorized"] else "CHƯA"),
                sanitize_csv_cell(readiness["theory"]["result"]),
                sanitize_csv_cell(readiness["simulation"]["result"]),
                sanitize_csv_cell(readiness["hardware"]["result"]),
                sanitize_csv_cell("CÓ" if readiness["hardware"]["signed"] else "CHƯA"),
                sanitize_csv_cell("; ".join(readiness["missing_conditions"])),
                sanitize_csv_cell(COURSE_VERSION)
            ]
            writer.writerow(row)

        return output.getvalue()
    finally:
        conn.close()
