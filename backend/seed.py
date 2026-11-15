"""Idempotent seed loader: populates course content, questions, rubrics, schedule, and placeholder slots."""
import json
import csv
import uuid
import hashlib
from pathlib import Path
from backend.config import (
    BASE_DIR, PUBLIC_DATA_DIR, PRIVATE_DATA_DIR, TEMPLATES_DIR,
    COURSE_VERSION, DEADLINE_EXCLUSIVE, now_iso
)
from backend.db import init_db, db_transaction
from backend.auth import hash_password

def seed_database(db_path: Path = None, create_bootstrap_admin: bool = True):
    init_db(db_path)
    
    with db_transaction(db_path) as conn:
        # 1. Course
        course_file = PUBLIC_DATA_DIR / "course.json"
        course_data = json.loads(course_file.read_text(encoding="utf-8"))
        course_digest = hashlib.sha256(course_file.read_bytes()).hexdigest()
        c_ver = course_data["version"]
        
        conn.execute("""
            INSERT INTO courses (id, version, title, status, digest, published_at, hard_deadline_exclusive, approved_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(version) DO UPDATE SET
                title = excluded.title,
                status = excluded.status,
                digest = excluded.digest,
                hard_deadline_exclusive = excluded.hard_deadline_exclusive
        """, (
            course_data.get("id", "ASV-INVENTORY-2026"),
            c_ver,
            course_data["title"],
            course_data["status"],
            course_digest,
            course_data.get("published_at", "2026-11-14T00:00:00+07:00"),
            course_data["hard_deadline_exclusive"],
            "Ajax Systems Vietnam Training Committee"
        ))

        # 2. Asset Manifest
        asset_manifest_file = BASE_DIR / "data" / "asset_manifest.json"
        if asset_manifest_file.exists():
            assets = json.loads(asset_manifest_file.read_text(encoding="utf-8"))
            for asset in assets:
                conn.execute("""
                    INSERT INTO content_records (id, course_version, content_id, kind, public_payload, private_grading_ref, source_refs, asset_refs)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(course_version, content_id, kind) DO UPDATE SET
                        public_payload = excluded.public_payload
                """, (
                    str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c_ver}-asset-{asset['id']}")),
                    c_ver,
                    asset["id"],
                    "asset",
                    json.dumps(asset, ensure_ascii=False),
                    None,
                    None,
                    None
                ))

        # 3. Assessment Blueprint
        bp_file = BASE_DIR / "data" / "assessment_blueprint.json"
        bp_data = json.loads(bp_file.read_text(encoding="utf-8"))
        conn.execute("""
            INSERT INTO content_records (id, course_version, content_id, kind, public_payload, private_grading_ref, source_refs, asset_refs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_version, content_id, kind) DO UPDATE SET
                public_payload = excluded.public_payload
        """, (
            str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c_ver}-blueprint")),
            c_ver,
            "blueprint",
            "blueprint",
            json.dumps(bp_data, ensure_ascii=False),
            None,
            None,
            None
        ))

        # 4. Lessons
        lessons_file = PUBLIC_DATA_DIR / "lessons.json"
        lessons = json.loads(lessons_file.read_text(encoding="utf-8"))
        for lesson in lessons:
            conn.execute("""
                INSERT INTO content_records (id, course_version, content_id, kind, public_payload, private_grading_ref, source_refs, asset_refs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(course_version, content_id, kind) DO UPDATE SET
                    public_payload = excluded.public_payload,
                    source_refs = excluded.source_refs,
                    asset_refs = excluded.asset_refs
            """, (
                str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c_ver}-lesson-{lesson['id']}")),
                c_ver,
                lesson["id"],
                "lesson",
                json.dumps(lesson, ensure_ascii=False),
                None,
                json.dumps(lesson.get("source_refs", []), ensure_ascii=False),
                json.dumps(lesson.get("asset_ids", []), ensure_ascii=False)
            ))

        # 5. Questions and Private Theory Keys
        questions_file = PUBLIC_DATA_DIR / "questions.json"
        questions = json.loads(questions_file.read_text(encoding="utf-8"))
        keys_file = PRIVATE_DATA_DIR / "theory_answer_key.json"
        keys = json.loads(keys_file.read_text(encoding="utf-8"))
        keys_map = {k["question_id"]: k for k in keys}

        for q in questions:
            k = keys_map.get(q["id"])
            conn.execute("""
                INSERT INTO content_records (id, course_version, content_id, kind, public_payload, private_grading_ref, source_refs, asset_refs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(course_version, content_id, kind) DO UPDATE SET
                    public_payload = excluded.public_payload,
                    private_grading_ref = excluded.private_grading_ref
            """, (
                str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c_ver}-question-{q['id']}")),
                c_ver,
                q["id"],
                "question",
                json.dumps(q, ensure_ascii=False),
                json.dumps(k, ensure_ascii=False) if k else None,
                json.dumps(q.get("source_refs", []), ensure_ascii=False),
                None
            ))

        # 6. Simulations and Private Simulation Grading Keys
        sims_file = PUBLIC_DATA_DIR / "simulations.json"
        sims = json.loads(sims_file.read_text(encoding="utf-8"))
        sim_keys_file = PRIVATE_DATA_DIR / "simulation_grading.json"
        sim_keys = json.loads(sim_keys_file.read_text(encoding="utf-8"))
        sim_keys_map = {k["case_id"]: k for k in sim_keys}

        for s in sims:
            sk = sim_keys_map.get(s["id"])
            conn.execute("""
                INSERT INTO content_records (id, course_version, content_id, kind, public_payload, private_grading_ref, source_refs, asset_refs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(course_version, content_id, kind) DO UPDATE SET
                    public_payload = excluded.public_payload,
                    private_grading_ref = excluded.private_grading_ref
            """, (
                str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c_ver}-simulation-{s['id']}")),
                c_ver,
                s["id"],
                "simulation",
                json.dumps(s, ensure_ascii=False),
                json.dumps(sk, ensure_ascii=False) if sk else None,
                None,
                None
            ))

        # 7. Hardware Rubrics
        rubrics_file = BASE_DIR / "data" / "hardware_rubrics.json"
        rubrics = json.loads(rubrics_file.read_text(encoding="utf-8"))
        conn.execute("""
            INSERT INTO content_records (id, course_version, content_id, kind, public_payload, private_grading_ref, source_refs, asset_refs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_version, content_id, kind) DO UPDATE SET
                public_payload = excluded.public_payload
        """, (
            str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c_ver}-hardware-rubrics")),
            c_ver,
            "hardware_rubrics",
            "hardware_rubric",
            json.dumps(rubrics, ensure_ascii=False),
            None,
            None,
            None
        ))

        # 8. Schedule Sessions (39 sessions)
        schedule_file = BASE_DIR / "data" / "schedule.json"
        schedule_data = json.loads(schedule_file.read_text(encoding="utf-8"))
        for session in schedule_data.get("sessions", []):
            conn.execute("""
                INSERT INTO training_sessions (
                    id, course_version, topic_vi, crew, group_name, start_at, end_at, timezone, capacity, kind, conditional, resources, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    topic_vi = excluded.topic_vi,
                    crew = excluded.crew,
                    group_name = excluded.group_name,
                    start_at = excluded.start_at,
                    end_at = excluded.end_at,
                    capacity = excluded.capacity,
                    kind = excluded.kind,
                    conditional = excluded.conditional,
                    resources = excluded.resources,
                    status = excluded.status
            """, (
                session["id"],
                c_ver,
                session["topic_vi"],
                session["crew"],
                session["group"],
                session["start_at"],
                session["end_at"],
                session.get("timezone", "Asia/Ho_Chi_Minh"),
                session.get("capacity"),
                session["kind"],
                1 if session.get("conditional") else 0,
                json.dumps(session.get("resources", {}), ensure_ascii=False),
                session.get("status", "planned_not_booked")
            ))

        # 9. Planned 132 Slots (stored as placeholders: is_placeholder=1, active=0)
        # Requirement U01: Không tạo tài khoản hoặc kết quả thật; kế hoạch 132 hiển thị riêng
        planned_slots_file = TEMPLATES_DIR / "planned_slots_132.csv"
        if planned_slots_file.exists():
            with open(planned_slots_file, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    slot_id = row.get("slot_id")
                    if not slot_id:
                        continue
                    # Check if slot already exists
                    existing = conn.execute("SELECT id FROM employee_profiles WHERE slot_id = ?", (slot_id,)).fetchone()
                    if not existing:
                        placeholder_user_id = f"placeholder-{slot_id}"
                        # Check user
                        u = conn.execute("SELECT id FROM users WHERE id = ?", (placeholder_user_id,)).fetchone()
                        if not u:
                            conn.execute("""
                                INSERT INTO users (id, employee_id, full_name, password_hash, active, is_placeholder, created_at, updated_at)
                                VALUES (?, ?, ?, ?, 0, 1, ?, ?)
                            """, (
                                placeholder_user_id,
                                f"SLOT_{slot_id}",
                                f"Placeholder {slot_id}",
                                "DISABLED_PLACEHOLDER",
                                now_iso(),
                                now_iso()
                            ))
                            conn.execute("""
                                INSERT INTO employee_profiles (id, user_id, job_title, crew, workcell_id, group_name, operational_roles, slot_id, effective_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                str(uuid.uuid4()),
                                placeholder_user_id,
                                row.get("job_title", "LINE_LEADER"),
                                None,
                                None,
                                None,
                                "[]",
                                slot_id,
                                now_iso()
                            ))

        # 10. Bootstrap Admin & Test Users (if requested)
        if create_bootstrap_admin:
            admin_user = conn.execute("SELECT id FROM users WHERE employee_id = 'ADMIN01'").fetchone()
            if not admin_user:
                admin_id = str(uuid.uuid4())
                pwd_hash = hash_password("AsvAdmin@2026")
                conn.execute("""
                    INSERT INTO users (id, employee_id, full_name, password_hash, active, is_placeholder, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, 0, ?, ?)
                """, (admin_id, "ADMIN01", "Hệ Thống Quản Trị ASV", pwd_hash, now_iso(), now_iso()))
                
                # Assign all admin roles
                admin_roles = ["SYSTEM_ADMIN", "CONTENT_ADMIN", "PM_VIEWER", "WCM_VIEWER", "WAREHOUSE_APPROVER"]
                for r in admin_roles:
                    conn.execute("""
                        INSERT INTO user_roles (id, user_id, app_role, scope_workcell_ids, created_at)
                        VALUES (?, ?, ?, '["ALL"]', ?)
                        ON CONFLICT(user_id, app_role) DO NOTHING
                    """, (str(uuid.uuid4()), admin_id, r, now_iso()))

                conn.execute("""
                    INSERT INTO employee_profiles (id, user_id, job_title, crew, workcell_id, group_name, operational_roles, effective_at)
                    VALUES (?, ?, 'PRODUCTION_MANAGER', 'OFFICE', 'WC_ALL', 'OFFICE', '["CONTROLLER"]', ?)
                """, (str(uuid.uuid4()), admin_id, now_iso()))

    return True

if __name__ == "__main__":
    seed_database()
    print("Database successfully initialized and seeded with course content, rubrics, 39 sessions, and 132 placeholder slots.")
