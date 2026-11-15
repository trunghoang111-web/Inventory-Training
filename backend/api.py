"""REST API router and request handlers."""
import json
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple
from backend.config import (
    COURSE_VERSION, DEADLINE_EXCLUSIVE, now_vn, now_iso, PUBLIC_DATA_DIR
)
from backend.db import get_db_connection, db_transaction
from backend.auth import (
    hash_password, verify_password, create_access_token, verify_access_token,
    get_user_by_id, user_has_role, check_workcell_scope, check_anti_self_eval
)
from backend.grading import (
    generate_theory_exam, save_theory_progress, submit_theory_exam,
    start_simulation_attempt, process_simulation_event, submit_simulation_case,
    submit_simulation_attempt, submit_hardware_assessment, void_assessment_attempt,
    evaluate_candidate_readiness, calculate_qualified_rate, check_readiness
)
from backend.schedule_engine import check_session_conflicts, assign_users_to_session
from backend.import_export import (
    preview_employee_import, commit_employee_import, export_candidate_report_csv
)

def parse_auth_header(headers: Dict[str, str], db_path=None) -> Optional[Dict[str, Any]]:
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    payload = verify_access_token(token)
    if not payload:
        return None
    return get_user_by_id(payload["user_id"], db_path=db_path)

def handle_api_request(
    method: str,
    path: str,
    headers: Dict[str, str],
    body_bytes: bytes,
    query_params: Dict[str, str],
    db_path=None
) -> Tuple[int, Dict[str, str], bytes]:
    """Main REST API request router. Returns (status_code, response_headers, response_bytes)."""
    resp_headers = {"Content-Type": "application/json; charset=utf-8"}
    
    def json_resp(status: int, data: Any):
        return status, resp_headers, json.dumps(data, ensure_ascii=False).encode("utf-8")
    
    def error_resp(status: int, message: str):
        return status, resp_headers, json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")

    body = {}
    if body_bytes:
        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            pass

    current_user = parse_auth_header(headers, db_path=db_path)

    # ---------------- 1. AUTH ENDPOINTS ----------------
    if path == "/api/auth/login" and method == "POST":
        emp_id = (body.get("employee_id") or "").strip()
        pwd = (body.get("password") or "").strip()
        if not emp_id or not pwd:
            return error_resp(400, "Vui lòng nhập mã nhân viên và mật khẩu.")

        conn = get_db_connection(db_path)
        try:
            user = conn.execute("SELECT * FROM users WHERE employee_id = ?", (emp_id,)).fetchone()
            if not user or not user["active"]:
                return error_resp(401, "Mã nhân viên không tồn tại hoặc đã bị khóa.")
            if user["is_placeholder"]:
                return error_resp(403, "Slot này là placeholder kế hoạch, chưa được gán nhân sự thật.")
            if not verify_password(pwd, user["password_hash"]):
                return error_resp(401, "Mật khẩu không chính xác.")

            full_user = get_user_by_id(user["id"], db_path=db_path)
            token = create_access_token(user["id"], user["employee_id"], full_user["roles"])
            return json_resp(200, {
                "token": token,
                "user": full_user
            })
        finally:
            conn.close()

    if path == "/api/auth/me" and method == "GET":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập hoặc phiên làm việc hết hạn.")
        return json_resp(200, {"user": current_user})

    # ---------------- 2. LEARNER: LESSONS & KNOWLEDGE CHECKS ----------------
    if path == "/api/lessons" and method == "GET":
        conn = get_db_connection(db_path)
        try:
            lessons_rows = conn.execute("""
                SELECT content_id, public_payload FROM content_records
                WHERE kind = 'lesson' AND course_version = ?
                ORDER BY content_id ASC
            """, (COURSE_VERSION,)).fetchall()
            
            lessons = []
            user_progress = {}
            if current_user:
                enr = conn.execute("SELECT id FROM enrollments WHERE user_id = ? AND course_version = ?", (current_user["id"], COURSE_VERSION)).fetchone()
                if enr:
                    prog_rows = conn.execute("SELECT * FROM lesson_progress WHERE enrollment_id = ?", (enr["id"],)).fetchall()
                    for pr in prog_rows:
                        user_progress[pr["lesson_id"]] = {
                            "cards_viewed": json.loads(pr["cards_viewed"]),
                            "check_passed": bool(pr["check_passed"]),
                            "completed_at": pr["completed_at"]
                        }

            for r in lessons_rows:
                l_data = json.loads(r["public_payload"])
                lid = l_data["id"]
                prog = user_progress.get(lid, {"cards_viewed": [], "check_passed": False, "completed_at": None})
                lessons.append({
                    "id": lid,
                    "order": l_data.get("order"),
                    "title_vi": l_data.get("title_vi"),
                    "minutes": l_data.get("minutes"),
                    "cards_count": len(l_data.get("cards", [])),
                    "cards_viewed_count": len(prog["cards_viewed"]),
                    "check_passed": prog["check_passed"],
                    "completed_at": prog["completed_at"],
                    "asset_ids": l_data.get("asset_ids", [])
                })
            lessons.sort(key=lambda x: x["order"] or 0)
            return json_resp(200, {"lessons": lessons})
        finally:
            conn.close()

    if path.startswith("/api/lessons/") and method == "GET":
        lesson_id = path.replace("/api/lessons/", "")
        conn = get_db_connection(db_path)
        try:
            row = conn.execute("""
                SELECT public_payload FROM content_records
                WHERE content_id = ? AND kind = 'lesson' AND course_version = ?
            """, (lesson_id, COURSE_VERSION)).fetchone()
            if not row:
                return error_resp(404, "Không tìm thấy bài học.")
            
            lesson = json.loads(row["public_payload"])
            
            # Fetch asset details
            assets_details = []
            for aid in lesson.get("asset_ids", []):
                arow = conn.execute("SELECT public_payload FROM content_records WHERE content_id = ? AND kind = 'asset' AND course_version = ?", (aid, COURSE_VERSION)).fetchone()
                if arow:
                    assets_details.append(json.loads(arow["public_payload"]))
            
            # Fetch knowledge check questions (WITHOUT answer keys!)
            kc_questions = []
            for qid in lesson.get("knowledge_check_ids", []):
                qrow = conn.execute("SELECT public_payload FROM content_records WHERE content_id = ? AND kind = 'question' AND course_version = ?", (qid, COURSE_VERSION)).fetchone()
                if qrow:
                    q_data = json.loads(qrow["public_payload"])
                    # Ensure no private leak
                    q_clean = {
                        "id": q_data["id"],
                        "stem_vi": q_data["stem_vi"],
                        "options": q_data["options"],
                        "pool": q_data.get("pool"),
                        "critical": q_data.get("critical", False)
                    }
                    kc_questions.append(q_clean)

            # Get user progress
            progress = {"cards_viewed": [], "check_passed": False}
            if current_user:
                enr = conn.execute("SELECT id FROM enrollments WHERE user_id = ? AND course_version = ?", (current_user["id"], COURSE_VERSION)).fetchone()
                if enr:
                    lp = conn.execute("SELECT * FROM lesson_progress WHERE enrollment_id = ? AND lesson_id = ?", (enr["id"], lesson_id)).fetchone()
                    if lp:
                        progress = {
                            "cards_viewed": json.loads(lp["cards_viewed"]),
                            "check_passed": bool(lp["check_passed"]),
                            "completed_at": lp["completed_at"]
                        }

            return json_resp(200, {
                "lesson": lesson,
                "assets": assets_details,
                "knowledge_checks": kc_questions,
                "progress": progress
            })
        finally:
            conn.close()

    if path.startswith("/api/lessons/") and path.endswith("/card-view") and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        lesson_id = path.split("/")[3]
        card_id = body.get("card_id")
        if not card_id:
            return error_resp(400, "Thiếu card_id.")

        with db_transaction(db_path) as conn:
            enr = conn.execute("SELECT id FROM enrollments WHERE user_id = ? AND course_version = ?", (current_user["id"], COURSE_VERSION)).fetchone()
            if not enr:
                enr_id = str(uuid.uuid4())
                conn.execute("INSERT INTO enrollments (id, user_id, course_version, created_at) VALUES (?, ?, ?, ?)", (enr_id, current_user["id"], COURSE_VERSION, now_iso()))
            else:
                enr_id = enr["id"]

            lp = conn.execute("SELECT * FROM lesson_progress WHERE enrollment_id = ? AND lesson_id = ?", (enr_id, lesson_id)).fetchone()
            if not lp:
                cards = [card_id]
                conn.execute("""
                    INSERT INTO lesson_progress (id, enrollment_id, lesson_id, cards_viewed, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (str(uuid.uuid4()), enr_id, lesson_id, json.dumps(cards), now_iso()))
            else:
                cards = json.loads(lp["cards_viewed"])
                if card_id not in cards:
                    cards.append(card_id)
                    conn.execute("UPDATE lesson_progress SET cards_viewed = ?, updated_at = ? WHERE id = ?", (json.dumps(cards), now_iso(), lp["id"]))

        return json_resp(200, {"status": "OK", "cards_viewed": cards})

    if path.startswith("/api/lessons/") and path.endswith("/knowledge-check") and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        lesson_id = path.split("/")[3]
        answers = body.get("answers", {})  # question_id -> option_id

        conn = get_db_connection(db_path)
        try:
            results = {}
            all_correct = True
            for qid, opt_id in answers.items():
                krow = conn.execute("""
                    SELECT private_grading_ref FROM content_records
                    WHERE content_id = ? AND kind = 'question' AND course_version = ?
                """, (qid, COURSE_VERSION)).fetchone()
                if not krow or not krow["private_grading_ref"]:
                    continue
                kdata = json.loads(krow["private_grading_ref"])
                correct_id = kdata.get("correct_option_id")
                is_corr = (opt_id == correct_id)
                results[qid] = {
                    "is_correct": is_corr,
                    "correct_option_id": correct_id,
                    "explanation_vi": kdata.get("explanation_vi")
                }
                if not is_corr:
                    all_correct = False

            # Update lesson progress if all correct
            if all_correct and len(results) > 0:
                with db_transaction(db_path) as tx_conn:
                    enr = tx_conn.execute("SELECT id FROM enrollments WHERE user_id = ? AND course_version = ?", (current_user["id"], COURSE_VERSION)).fetchone()
                    if enr:
                        tx_conn.execute("""
                            UPDATE lesson_progress
                            SET check_passed = 1, completed_at = ?, updated_at = ?
                            WHERE enrollment_id = ? AND lesson_id = ?
                        """, (now_iso(), now_iso(), enr["id"], lesson_id))

            return json_resp(200, {"all_correct": all_correct, "results": results})
        finally:
            conn.close()

    # ---------------- 3. CANDIDATE READINESS & PROFILE ----------------
    if path == "/api/learner/readiness" and method == "GET":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        target_uid = query_params.get("user_id") or current_user["id"]
        # Scope check if viewing someone else
        if target_uid != current_user["id"] and not user_has_role(current_user, "WCM_VIEWER") and not user_has_role(current_user, "PM_VIEWER"):
            return error_resp(403, "Không có quyền xem thông tin học viên khác.")

        readiness = evaluate_candidate_readiness(target_uid, db_path=db_path)
        return json_resp(200, readiness)

    # ---------------- 4. THEORY EXAM ----------------
    if path == "/api/theory/start" and method == "GET":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        is_demo = query_params.get("demo") == "true"
        try:
            exam = generate_theory_exam(current_user["id"], is_demo=is_demo, db_path=db_path)
            return json_resp(200, exam)
        except Exception as e:
            return error_resp(400, str(e))

    if path == "/api/theory/save" and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        attempt_id = body.get("attempt_id")
        answers = body.get("answers", {})
        try:
            res = save_theory_progress(attempt_id, answers, db_path=db_path)
            return json_resp(200, res)
        except Exception as e:
            return error_resp(400, str(e))

    if path == "/api/theory/submit" and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        attempt_id = body.get("attempt_id")
        answers = body.get("answers", {})
        try:
            res = submit_theory_exam(attempt_id, answers, db_path=db_path)
            return json_resp(200, res)
        except Exception as e:
            return error_resp(400, str(e))

    # ---------------- 5. SIMULATION EXAM ----------------
    if path == "/api/simulations" and method == "GET":
        conn = get_db_connection(db_path)
        try:
            rows = conn.execute("""
                SELECT public_payload FROM content_records
                WHERE kind = 'simulation' AND course_version = ?
                ORDER BY content_id ASC
            """, (COURSE_VERSION,)).fetchall()
            sims = [json.loads(r["public_payload"]) for r in rows]
            return json_resp(200, {"simulations": sims})
        finally:
            conn.close()

    if path == "/api/simulations/start" and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        is_official = body.get("official", True)
        is_demo = body.get("demo", False)
        try:
            att = start_simulation_attempt(current_user["id"], is_official=is_official, is_demo=is_demo, db_path=db_path)
            return json_resp(200, att)
        except Exception as e:
            return error_resp(400, str(e))

    if path == "/api/simulations/event" and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        attempt_id = body.get("attempt_id")
        case_id = body.get("case_id")
        seq = body.get("seq")
        idempotency_key = body.get("idempotency_key")
        event_type = body.get("event_type")
        payload = body.get("payload", {})

        if not all([attempt_id, case_id, seq, idempotency_key, event_type]):
            return error_resp(400, "Thiếu tham số bắt buộc của sự kiện mô phỏng.")

        try:
            res = process_simulation_event(
                attempt_id, case_id, seq, idempotency_key, event_type, payload,
                actor=current_user["id"], db_path=db_path
            )
            return json_resp(200, res)
        except Exception as e:
            err_msg = str(e)
            status_code = 409 if "409" in err_msg else 400
            return error_resp(status_code, err_msg)

    if path == "/api/simulations/submit-case" and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        attempt_id = body.get("attempt_id")
        case_id = body.get("case_id")
        try:
            res = submit_simulation_case(attempt_id, case_id, db_path=db_path)
            return json_resp(200, res)
        except Exception as e:
            return error_resp(400, str(e))

    if path == "/api/simulations/submit-attempt" and method == "POST":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        attempt_id = body.get("attempt_id")
        try:
            res = submit_simulation_attempt(attempt_id, db_path=db_path)
            return json_resp(200, res)
        except Exception as e:
            return error_resp(400, str(e))

    # ---------------- 6. ASSESSOR: PDA REAL HARDWARE & SESSIONS ----------------
    if path == "/api/assessor/rubrics" and method == "GET":
        conn = get_db_connection(db_path)
        try:
            row = conn.execute("""
                SELECT public_payload FROM content_records
                WHERE content_id = 'hardware_rubrics' AND course_version = ?
            """, (COURSE_VERSION,)).fetchone()
            if not row:
                return error_resp(404, "Không tìm thấy rubrics.")
            return json_resp(200, json.loads(row["public_payload"]))
        finally:
            conn.close()

    if path == "/api/assessor/sessions" and method == "GET":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        conn = get_db_connection(db_path)
        try:
            sessions = conn.execute("""
                SELECT s.*,
                    (SELECT COUNT(*) FROM session_assignments WHERE session_id = s.id AND capacity_role = 'LEARNER') as assigned_learners
                FROM training_sessions s
                ORDER BY s.start_at ASC
            """).fetchall()
            return json_resp(200, {"sessions": [dict(s) for s in sessions]})
        finally:
            conn.close()

    if path.startswith("/api/assessor/session/") and path.endswith("/attendance") and method == "GET":
        session_id = path.split("/")[4]
        conn = get_db_connection(db_path)
        try:
            roster = conn.execute("""
                SELECT u.id, u.employee_id, u.full_name, p.crew, p.workcell_id, p.job_title,
                       a.status, a.confirmed_at, a.notes
                FROM session_assignments sa
                JOIN users u ON u.id = sa.user_id
                JOIN employee_profiles p ON p.user_id = u.id
                LEFT JOIN attendance a ON a.session_id = sa.session_id AND a.user_id = u.id
                WHERE sa.session_id = ? AND sa.capacity_role = 'LEARNER'
            """, (session_id,)).fetchall()
            return json_resp(200, {"roster": [dict(r) for r in roster]})
        finally:
            conn.close()

    if path.startswith("/api/assessor/session/") and path.endswith("/attendance") and method == "POST":
        if not current_user or (not user_has_role(current_user, "TRAINER") and not user_has_role(current_user, "SYSTEM_ADMIN")):
            return error_resp(403, "Cần quyền Trainer để điểm danh.")
        session_id = path.split("/")[4]
        records = body.get("records", [])  # list of {user_id, status, notes}

        with db_transaction(db_path) as conn:
            now_str = now_iso()
            for rec in records:
                conn.execute("""
                    INSERT INTO attendance (id, session_id, user_id, status, confirmed_by, confirmed_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, user_id) DO UPDATE SET
                        status = excluded.status,
                        confirmed_by = excluded.confirmed_by,
                        confirmed_at = excluded.confirmed_at,
                        notes = excluded.notes
                """, (
                    str(uuid.uuid4()), session_id, rec["user_id"], rec["status"],
                    current_user["id"], now_str, rec.get("notes")
                ))
        return json_resp(200, {"status": "ATTENDANCE_CONFIRMED"})

    if path == "/api/assessor/hardware-exam" and method == "POST":
        if not current_user or (not user_has_role(current_user, "ASSESSOR") and not user_has_role(current_user, "SYSTEM_ADMIN")):
            return error_resp(403, "Cần quyền Assessor để chấm PDA thật.")

        learner_id = body.get("learner_id")
        assessment_type = body.get("type", "HARDWARE_COMMON")
        session_id = body.get("session_id", "HW-SESSION-01")
        device_id = body.get("device_id", "PDA-ASV-01")
        lab_id = body.get("lab_id", "LAB-ASV-01")
        observations = body.get("observations", {})
        notes = body.get("notes", "")
        attestation = body.get("attestation", "Xác nhận quan sát trực tiếp")
        is_demo = body.get("demo", False)

        try:
            check_anti_self_eval(current_user["id"], learner_id)
            res = submit_hardware_assessment(
                assessor_id=current_user["id"],
                learner_id=learner_id,
                assessment_type=assessment_type,
                session_id=session_id,
                device_id=device_id,
                lab_id=lab_id,
                observations=observations,
                notes=notes,
                attestation=attestation,
                is_demo=is_demo,
                db_path=db_path
            )
            return json_resp(200, res)
        except Exception as e:
            return error_resp(400, str(e))

    if path == "/api/assessor/void-attempt" and method == "POST":
        if not current_user or (not user_has_role(current_user, "ASSESSOR") and not user_has_role(current_user, "SYSTEM_ADMIN")):
            return error_resp(403, "Cần quyền Assessor hoặc Admin để void lượt thi.")
        attempt_id = body.get("attempt_id")
        reason = body.get("reason")
        try:
            res = void_assessment_attempt(attempt_id, current_user["id"], reason, db_path=db_path)
            return json_resp(200, res)
        except Exception as e:
            return error_resp(400, str(e))

    # ---------------- 7. WCM / PM DASHBOARD ----------------
    if path == "/api/dashboard/stats" and method == "GET":
        if not current_user or (not user_has_role(current_user, "WCM_VIEWER") and not user_has_role(current_user, "PM_VIEWER")):
            return error_resp(403, "Cần quyền WCM_VIEWER hoặc PM_VIEWER để xem dashboard.")

        filter_crew = query_params.get("crew")
        filter_workcell = query_params.get("workcell")

        conn = get_db_connection(db_path)
        try:
            users_rows = conn.execute("""
                SELECT u.id, u.employee_id, u.full_name, p.crew, p.workcell_id, p.job_title, p.operational_roles
                FROM users u
                JOIN employee_profiles p ON p.user_id = u.id
                WHERE u.is_placeholder = 0 AND u.active = 1
            """).fetchall()

            # Denominator: active_required_real
            active_required_real = 0
            funnel_counts = {
                "NOT_STARTED": 0, "LEARNING": 0, "THEORY_PENDING": 0, "THEORY_FAILED": 0,
                "PRACTICE_PENDING": 0, "SIM_PENDING": 0, "SIM_FAILED": 0,
                "HARDWARE_PENDING": 0, "HARDWARE_FAILED": 0, "SPECIAL_PENDING": 0, "QUALIFIED": 0
            }
            qualified_count = 0
            authorized_count = 0
            action_items = []

            for u in users_rows:
                wc = u["workcell_id"] or ""
                cr = u["crew"] or ""
                if not check_workcell_scope(current_user, wc):
                    continue
                if filter_workcell and wc != filter_workcell:
                    continue
                if filter_crew and cr != filter_crew:
                    continue

                active_required_real += 1
                readiness = evaluate_candidate_readiness(u["id"], db_path=db_path)
                stage = readiness["funnel_stage"]
                funnel_counts[stage] = funnel_counts.get(stage, 0) + 1

                if readiness["is_qualified"]:
                    qualified_count += 1
                if readiness["is_authorized"]:
                    authorized_count += 1

                if not readiness["is_qualified"]:
                    action_items.append({
                        "user_id": u["id"],
                        "employee_id": u["employee_id"],
                        "full_name": u["full_name"],
                        "crew": cr,
                        "workcell": wc,
                        "job_title": u["job_title"],
                        "stage": stage,
                        "missing": readiness["missing_conditions"]
                    })

            rate = calculate_qualified_rate(active_required_real, qualified_count)

            # Planned slots count (132 baseline)
            placeholder_count = conn.execute("SELECT COUNT(*) FROM users WHERE is_placeholder = 1").fetchone()[0]

            return json_resp(200, {
                "course_version": COURSE_VERSION,
                "planned_slots": placeholder_count,
                "active_required_real": active_required_real,
                "trained_qualified": qualified_count,
                "qualified_rate": rate,  # None renders as N/A
                "role_authorized": authorized_count,
                "funnel": funnel_counts,
                "action_items_count": len(action_items),
                "action_items": action_items[:50]
            })
        finally:
            conn.close()

    if path == "/api/dashboard/export-csv" and method == "GET":
        if not current_user:
            return error_resp(401, "Chưa đăng nhập.")
        csv_str = export_candidate_report_csv(
            current_user,
            filter_crew=query_params.get("crew"),
            filter_workcell=query_params.get("workcell"),
            db_path=db_path
        )
        csv_headers = {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=\"asv_inventory_training_report.csv\""
        }
        return 200, csv_headers, csv_str.encode("utf-8-sig")

    # ---------------- 8. ADMIN: IMPORT & ROLE AUTHORIZATION ----------------
    if path == "/api/admin/import/preview" and method == "POST":
        if not current_user or (not user_has_role(current_user, "CONTENT_ADMIN") and not user_has_role(current_user, "SYSTEM_ADMIN")):
            return error_resp(403, "Cần quyền Admin để import dữ liệu.")
        csv_text = body.get("csv_content", "")
        if not csv_text:
            return error_resp(400, "Nội dung CSV rỗng.")
        preview = preview_employee_import(csv_text, db_path=db_path)
        return json_resp(200, preview)

    if path == "/api/admin/import/commit" and method == "POST":
        if not current_user or (not user_has_role(current_user, "CONTENT_ADMIN") and not user_has_role(current_user, "SYSTEM_ADMIN")):
            return error_resp(403, "Cần quyền Admin để import dữ liệu.")
        preview_data = body.get("preview", {})
        default_pwd = body.get("default_password", "Ajax@12345")
        try:
            res = commit_employee_import(preview_data, default_password=default_pwd, db_path=db_path)
            return json_resp(200, res)
        except Exception as e:
            return error_resp(400, str(e))

    if path == "/api/admin/role-authorizations" and method == "GET":
        conn = get_db_connection(db_path)
        try:
            auths = conn.execute("""
                SELECT ra.*, u.employee_id, u.full_name, p.crew, p.workcell_id, p.job_title
                FROM role_authorizations ra
                JOIN users u ON u.id = ra.user_id
                JOIN employee_profiles p ON p.user_id = u.id
                ORDER BY ra.valid_from DESC
            """).fetchall()
            return json_resp(200, {"authorizations": [dict(a) for a in auths]})
        finally:
            conn.close()

    if path == "/api/admin/role-authorizations" and method == "POST":
        if not current_user or (not user_has_role(current_user, "WAREHOUSE_APPROVER") and not user_has_role(current_user, "WCM_VIEWER") and not user_has_role(current_user, "SYSTEM_ADMIN")):
            return error_resp(403, "Cần quyền Warehouse Approver hoặc WCM để duyệt vai.")

        target_uid = body.get("user_id")
        op_role = body.get("operational_role")
        scope = body.get("scope_workcell_ids", ["WC01"])
        
        # Anti-self-approval check
        try:
            check_anti_self_eval(current_user["id"], target_uid)
        except PermissionError as pe:
            return error_resp(403, str(pe))

        # Check candidate readiness: must be QUALIFIED
        readiness = evaluate_candidate_readiness(target_uid, db_path=db_path)
        if not readiness["is_qualified"]:
            return error_resp(400, f"Học viên chưa QUALIFIED (đang ở giai đoạn: {readiness['funnel_stage']}). Chưa thể phê duyệt vai.")

        with db_transaction(db_path) as conn:
            auth_id = str(uuid.uuid4())
            now_str = now_iso()
            conn.execute("""
                INSERT INTO role_authorizations (
                    id, user_id, course_version, operational_role, scope_workcell_ids,
                    wcm_reviewer_id, wcm_reviewed_at, warehouse_reviewer_id, warehouse_reviewed_at,
                    system_access_confirmed, valid_from
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                auth_id, target_uid, COURSE_VERSION, op_role,
                json.dumps(scope), current_user["id"], now_str,
                current_user["id"], now_str, now_str
            ))

        return json_resp(200, {"status": "AUTHORIZED", "authorization_id": auth_id})

    # Default not found
    return error_resp(404, f"API endpoint không tồn tại: {path}")
