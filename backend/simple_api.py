"""REST API and business logic for the simplified ASV Inventory Training application."""
import json
import csv
import io
import uuid
import random
import threading
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from backend.config import (
    COURSE_VERSION, SLIDES_FILE, QUESTIONS_FILE, ANSWER_KEY_FILE,
    ADMIN_USERNAME, ADMIN_PASSWORD, GOOGLE_SHEET_WEBHOOK_URL, now_iso, now_vn
)
from backend.db import get_db_connection, db_transaction, get_setting, set_setting
from backend.auth import create_access_token, verify_access_token

def load_slides_data() -> Dict[str, Any]:
    with open(SLIDES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_questions_data() -> Dict[str, Any]:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_answer_key_data() -> Dict[str, Any]:
    with open(ANSWER_KEY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def sanitize_csv_cell(value: Any) -> str:
    """Sanitizes text cells starting with =, +, -, @ to prevent formula injection."""
    if value is None:
        return ""
    s = str(value)
    if not s:
        return ""
    if s.startswith("-"):
        try:
            float(s)
            return s
        except ValueError:
            return f"'{s}"
    if s[0] in ("=", "+", "@"):
        return f"'{s}"
    return s

def sync_to_google_sheet(records: Any, webhook_url: str = None, db_path: Path = None) -> bool:
    """Send one or more learner records to Google Apps Script Webhook."""
    if not webhook_url:
        webhook_url = get_setting("google_sheet_webhook_url", db_path=db_path) or GOOGLE_SHEET_WEBHOOK_URL
    if not webhook_url or not str(webhook_url).strip().startswith("https://script.google.com/"):
        return False

    try:
        payload = json.dumps(records, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            webhook_url.strip(),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            resp_body = resp.read().decode("utf-8", errors="ignore")
            print(f"[Google Sheet Sync] Success: {resp_body[:100]}")
        return True
    except Exception as e:
        print(f"[Google Sheet Sync Warning] Error connecting to {webhook_url[:40]}...: {e}")
        return False

def parse_simple_auth(headers: Dict[str, str], db_path=None) -> Optional[Dict[str, Any]]:
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    payload = verify_access_token(token)
    if not payload:
        return None
    
    # Check admin role
    roles = payload.get("roles", [])
    for r in roles:
        if isinstance(r, dict) and r.get("is_admin"):
            return {"is_admin": True, "username": r.get("username", "admin")}

    learner_id = payload.get("user_id")
    if not learner_id:
        return None

    conn = get_db_connection(db_path)
    try:
        learner = conn.execute("SELECT * FROM simple_learners WHERE id = ?", (learner_id,)).fetchone()
        if not learner:
            return None
        return dict(learner)
    finally:
        conn.close()

def get_learner_progress_summary(learner_id: str, db_path=None) -> Dict[str, Any]:
    conn = get_db_connection(db_path)
    try:
        # Slides viewed
        viewed_rows = conn.execute("""
            SELECT slide_id FROM simple_slide_progress
            WHERE learner_id = ? AND course_version = ?
        """, (learner_id, COURSE_VERSION)).fetchall()
        viewed_ids = set(r["slide_id"] for r in viewed_rows)
        slides_count = len(viewed_ids)
        is_completed_slides = (slides_count >= 20)

        # Test attempts
        attempts = conn.execute("""
            SELECT * FROM simple_test_attempts
            WHERE learner_id = ? AND course_version = ?
            ORDER BY attempt_number ASC
        """, (learner_id, COURSE_VERSION)).fetchall()
        
        attempts_count = len(attempts)
        submitted_attempts = [a for a in attempts if a["state"] == "SUBMITTED"]
        latest_submitted = submitted_attempts[-1] if submitted_attempts else None
        
        has_passed = any(a["passed"] == 1 for a in submitted_attempts)
        latest_score = latest_submitted["score"] if latest_submitted else None
        completed_at = next((a["submitted_at"] for a in submitted_attempts if a["passed"] == 1), None)

        # Status text
        if has_passed:
            status_text = "Đã hoàn thành"
        elif attempts_count > 0 and latest_submitted:
            status_text = "Cần ôn/Chưa đạt"
        elif is_completed_slides:
            status_text = "Đang học · Chờ làm bài"
        else:
            status_text = "Đang học"

        return {
            "slides_viewed_count": slides_count,
            "is_completed_slides": is_completed_slides,
            "attempts_count": attempts_count,
            "has_passed": has_passed,
            "latest_score": latest_score,
            "completed_at": completed_at,
            "status_text": status_text
        }
    finally:
        conn.close()

def handle_simple_api_request(
    method: str,
    path: str,
    headers: Dict[str, str],
    body_bytes: bytes,
    query_params: Dict[str, str],
    db_path=None
) -> Tuple[int, Dict[str, str], bytes]:
    resp_headers = {"Content-Type": "application/json; charset=utf-8"}

    if "?" in path:
        parsed = urllib.parse.urlparse(path)
        path = parsed.path
        if not query_params:
            query_params = dict(urllib.parse.parse_qsl(parsed.query))

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

    current_auth = parse_simple_auth(headers, db_path=db_path)

    # ---------------- 1. LEARNER START / IDENTITY ----------------
    if path == "/api/simple/start" and method == "POST":
        raw_emp_id = body.get("employee_id")
        full_name = body.get("full_name")
        position = body.get("position")
        custom_pos = body.get("custom_position")
        confirm = body.get("confirm", False)
        update_info = body.get("update_info", False)

        if not raw_emp_id or not str(raw_emp_id).strip():
            return error_resp(400, "Vui lòng nhập Mã nhân viên.")
        
        # Clean employee ID: trim whitespace, preserve leading zeros
        emp_id = str(raw_emp_id).strip()

        if not full_name or not str(full_name).strip():
            return error_resp(400, "Vui lòng nhập Họ và tên.")
        full_name = str(full_name).strip()

        if not position or not str(position).strip():
            return error_resp(400, "Vui lòng chọn Vị trí.")
        position = str(position).strip()

        final_pos = custom_pos.strip() if position == "Khác" and custom_pos else position

        conn = get_db_connection(db_path)
        try:
            existing = conn.execute("SELECT * FROM simple_learners WHERE employee_id = ?", (emp_id,)).fetchone()
            
            if existing and not confirm and not update_info:
                # Existing user detected: return info for user confirmation
                summary = get_learner_progress_summary(existing["id"], db_path=db_path)
                return json_resp(200, {
                    "exists": True,
                    "existing_learner": {
                        "id": existing["id"],
                        "employee_id": existing["employee_id"],
                        "full_name": existing["full_name"],
                        "position": existing["position"],
                        "custom_position": existing["custom_position"]
                    },
                    "progress": summary
                })

            with db_transaction(db_path) as tx_conn:
                now_str = now_iso()
                if existing:
                    learner_id = existing["id"]
                    if update_info:
                        # Log history of changes
                        if existing["full_name"] != full_name:
                            tx_conn.execute("""
                                INSERT INTO simple_learner_history (id, learner_id, field_name, old_value, new_value, changed_at)
                                VALUES (?, ?, 'full_name', ?, ?, ?)
                            """, (str(uuid.uuid4()), learner_id, existing["full_name"], full_name, now_str))
                        if existing["position"] != final_pos:
                            tx_conn.execute("""
                                INSERT INTO simple_learner_history (id, learner_id, field_name, old_value, new_value, changed_at)
                                VALUES (?, ?, 'position', ?, ?, ?)
                            """, (str(uuid.uuid4()), learner_id, existing["position"], final_pos, now_str))

                        tx_conn.execute("""
                            UPDATE simple_learners
                            SET full_name = ?, position = ?, custom_position = ?, updated_at = ?
                            WHERE id = ?
                        """, (full_name, final_pos, custom_pos, now_str, learner_id))
                else:
                    learner_id = str(uuid.uuid4())
                    tx_conn.execute("""
                        INSERT INTO simple_learners (id, employee_id, full_name, position, custom_position, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (learner_id, emp_id, full_name, final_pos, custom_pos, now_str, now_str))

            # Create session token
            token = create_access_token(user_id=learner_id, employee_id=emp_id, roles=[{"learner_id": learner_id}])
            summary = get_learner_progress_summary(learner_id, db_path=db_path)
            
            return json_resp(200, {
                "success": True,
                "token": token,
                "learner": {
                    "id": learner_id,
                    "employee_id": emp_id,
                    "full_name": full_name,
                    "position": final_pos
                },
                "progress": summary
            })
        finally:
            conn.close()

    if path == "/api/simple/session" and method == "GET":
        if not current_auth or current_auth.get("is_admin"):
            return error_resp(401, "Chưa đăng nhập người học.")
        summary = get_learner_progress_summary(current_auth["id"], db_path=db_path)
        return json_resp(200, {
            "learner": current_auth,
            "progress": summary
        })

    # ---------------- 2. SLIDES & PROGRESS ----------------
    if path == "/api/simple/slides" and method == "GET":
        slides_data = load_slides_data()
        slides = slides_data.get("slides", [])
        
        viewed_slide_ids = []
        if current_auth and not current_auth.get("is_admin"):
            conn = get_db_connection(db_path)
            try:
                rows = conn.execute("""
                    SELECT slide_id FROM simple_slide_progress
                    WHERE learner_id = ? AND course_version = ?
                """, (current_auth["id"], COURSE_VERSION)).fetchall()
                viewed_slide_ids = [r["slide_id"] for r in rows]
            finally:
                conn.close()

        return json_resp(200, {
            "title_vi": slides_data.get("title_vi"),
            "version": slides_data.get("version"),
            "slides": slides,
            "viewed_slide_ids": viewed_slide_ids
        })

    if path == "/api/simple/slides/view" and method == "POST":
        if not current_auth or current_auth.get("is_admin"):
            return error_resp(401, "Chưa đăng nhập người học.")

        slide_id = body.get("slide_id")
        slide_order = body.get("slide_order")

        if not slide_id or not slide_order:
            return error_resp(400, "Thiếu slide_id hoặc slide_order.")

        conn = get_db_connection(db_path)
        try:
            # Check sequential progress: on first pass, must complete previous slide first
            if slide_order > 1:
                prev_order = slide_order - 1
                has_prev = conn.execute("""
                    SELECT 1 FROM simple_slide_progress
                    WHERE learner_id = ? AND course_version = ? AND slide_order = ?
                """, (current_auth["id"], COURSE_VERSION, prev_order)).fetchone()
                
                # Check if current slide was already viewed
                already_viewed = conn.execute("""
                    SELECT 1 FROM simple_slide_progress
                    WHERE learner_id = ? AND course_version = ? AND slide_id = ?
                """, (current_auth["id"], COURSE_VERSION, slide_id)).fetchone()

                if not has_prev and not already_viewed:
                    return error_resp(400, f"Vui lòng xem trang {prev_order} trước khi xem trang {slide_order}.")

            with db_transaction(db_path) as tx_conn:
                tx_conn.execute("""
                    INSERT INTO simple_slide_progress (id, learner_id, course_version, slide_id, slide_order, viewed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(learner_id, course_version, slide_id) DO UPDATE SET
                        viewed_at = excluded.viewed_at
                """, (str(uuid.uuid4()), current_auth["id"], COURSE_VERSION, slide_id, slide_order, now_iso()))

            summary = get_learner_progress_summary(current_auth["id"], db_path=db_path)
            return json_resp(200, {"success": True, "progress": summary})
        finally:
            conn.close()

    # ---------------- 3. TEST & GRADING ----------------
    if path == "/api/simple/test" and method == "GET":
        if not current_auth or current_auth.get("is_admin"):
            return error_resp(401, "Chưa đăng nhập người học.")

        learner_id = current_auth["id"]
        summary = get_learner_progress_summary(learner_id, db_path=db_path)

        # GATE: Must have viewed all 20 slides
        if summary["slides_viewed_count"] < 20:
            return error_resp(403, "Bạn chưa hoàn thành đủ 20 trang học. Vui lòng học hết các trang trước khi làm bài kiểm tra.")

        conn = get_db_connection(db_path)
        try:
            # Check for existing IN_PROGRESS attempt
            active_attempt = conn.execute("""
                SELECT * FROM simple_test_attempts
                WHERE learner_id = ? AND course_version = ? AND state = 'IN_PROGRESS'
                ORDER BY attempt_number DESC LIMIT 1
            """, (learner_id, COURSE_VERSION)).fetchone()

            q_data = load_questions_data()
            all_questions = q_data.get("questions", [])

            if active_attempt:
                attempt_id = active_attempt["id"]
                attempt_num = active_attempt["attempt_number"]
                options_order = json.loads(active_attempt["options_order_snapshot"])
                saved_answers = json.loads(active_attempt["answers_json"])
            else:
                # Create fresh attempt
                last_attempt = conn.execute("""
                    SELECT MAX(attempt_number) FROM simple_test_attempts
                    WHERE learner_id = ? AND course_version = ?
                """, (learner_id, COURSE_VERSION)).fetchone()[0]
                attempt_num = (last_attempt + 1) if last_attempt else 1
                attempt_id = str(uuid.uuid4())

                # Shuffle options order per question and snapshot it
                options_order = {}
                for q in all_questions:
                    opts = list(q["options"])
                    random.shuffle(opts)
                    options_order[q["id"]] = [o["id"] for o in opts]

                saved_answers = {}
                with db_transaction(db_path) as tx_conn:
                    tx_conn.execute("""
                        INSERT INTO simple_test_attempts (
                            id, learner_id, course_version, attempt_number, state,
                            options_order_snapshot, answers_json, started_at
                        ) VALUES (?, ?, ?, ?, 'IN_PROGRESS', ?, '{}', ?)
                    """, (attempt_id, learner_id, COURSE_VERSION, attempt_num, json.dumps(options_order), now_iso()))

            # Construct clean question payloads matching snapshot option order
            clean_questions = []
            for q in all_questions:
                qid = q["id"]
                ordered_opt_ids = options_order.get(qid, [o["id"] for o in q["options"]])
                opts_map = {o["id"]: o for o in q["options"]}
                ordered_opts = [opts_map[oid] for oid in ordered_opt_ids if oid in opts_map]

                clean_questions.append({
                    "id": qid,
                    "question_vi": q["question_vi"],
                    "options": [{"id": o["id"], "text_vi": o["text_vi"]} for o in ordered_opts]
                })

            return json_resp(200, {
                "attempt_id": attempt_id,
                "attempt_number": attempt_num,
                "total_questions": len(clean_questions),
                "questions": clean_questions,
                "answers": saved_answers
            })
        finally:
            conn.close()

    if path == "/api/simple/test/save" and method == "POST":
        if not current_auth or current_auth.get("is_admin"):
            return error_resp(401, "Chưa đăng nhập người học.")
        attempt_id = body.get("attempt_id")
        answers = body.get("answers", {})

        with db_transaction(db_path) as conn:
            att = conn.execute("SELECT * FROM simple_test_attempts WHERE id = ? AND learner_id = ?", (attempt_id, current_auth["id"])).fetchone()
            if not att or att["state"] != "IN_PROGRESS":
                return error_resp(400, "Lượt thi không hợp lệ hoặc đã nộp.")
            
            conn.execute("""
                UPDATE simple_test_attempts
                SET answers_json = ?
                WHERE id = ?
            """, (json.dumps(answers), attempt_id))

        return json_resp(200, {"status": "SAVED"})

    if path == "/api/simple/test/submit" and method == "POST":
        if not current_auth or current_auth.get("is_admin"):
            return error_resp(401, "Chưa đăng nhập người học.")
        attempt_id = body.get("attempt_id")
        answers = body.get("answers", {})

        conn = get_db_connection(db_path)
        try:
            att = conn.execute("SELECT * FROM simple_test_attempts WHERE id = ? AND learner_id = ?", (attempt_id, current_auth["id"])).fetchone()
            if not att:
                return error_resp(404, "Không tìm thấy bài làm.")

            # Idempotency: If already submitted, return existing result without duplicate record
            if att["state"] == "SUBMITTED":
                return json_resp(200, {
                    "attempt_id": att["id"],
                    "score": att["score"],
                    "passed": bool(att["passed"]),
                    "submitted_at": att["submitted_at"],
                    "is_resubmission": True
                })

            q_data = load_questions_data()
            total_required = len(q_data.get("questions", []))

            # Must have answered all questions
            if len(answers) < total_required:
                return error_resp(400, f"Vui lòng trả lời đầy đủ {total_required} câu hỏi trước khi nộp bài (hiện đã chọn {len(answers)}/{total_required}).")

            # Grade on server against private answer key
            key_data = load_answer_key_data()
            key_map = {a["id"]: a for a in key_data.get("answers", [])}
            q_map = {q["id"]: q for q in q_data.get("questions", [])}

            score = 0
            failed_questions = []

            for q in q_data.get("questions", []):
                qid = q["id"]
                user_choice = answers.get(qid)
                key_item = key_map.get(qid)
                correct_id = key_item.get("correct_option_id") if key_item else None

                if user_choice == correct_id:
                    score += 1
                else:
                    opt_map = {o["id"]: o["text_vi"] for o in q["options"]}
                    failed_questions.append({
                        "id": qid,
                        "question_vi": q["question_vi"],
                        "your_answer": opt_map.get(user_choice, "Chưa chọn"),
                        "correct_answer": opt_map.get(correct_id, ""),
                        "explanation_vi": key_item.get("explanation_vi") if key_item else "",
                        "review_slide_ids": q.get("review_slide_ids", [])
                    })

            # Threshold: >= 9 correct answers to pass
            pass_threshold = q_data.get("pass_correct", 9)
            passed = (score >= pass_threshold)
            now_str = now_iso()

            with db_transaction(db_path) as tx_conn:
                tx_conn.execute("""
                    UPDATE simple_test_attempts
                    SET state = 'SUBMITTED',
                        answers_json = ?,
                        score = ?,
                        passed = ?,
                        submitted_at = ?
                    WHERE id = ?
                """, (json.dumps(answers), score, 1 if passed else 0, now_str, attempt_id))

            # Trigger background sync to Google Sheet if configured
            try:
                sheet_url = get_setting("google_sheet_webhook_url", db_path=db_path) or GOOGLE_SHEET_WEBHOOK_URL
                if sheet_url:
                    learner = conn.execute("SELECT * FROM simple_learners WHERE id = ?", (current_auth["id"],)).fetchone()
                    attempts_cnt = conn.execute(
                        "SELECT COUNT(*) FROM simple_test_attempts WHERE learner_id = ? AND state = 'SUBMITTED'",
                        (current_auth["id"],)
                    ).fetchone()[0]
                    if learner:
                        sync_item = {
                            "employee_id": learner["employee_id"],
                            "full_name": learner["full_name"],
                            "position": learner["position"],
                            "started_at": learner["created_at"],
                            "slides_viewed_count": "20/20",
                            "is_completed_slides": "Có",
                            "attempts_count": attempts_cnt,
                            "latest_score": f"{int(score)}/{total_required}",
                            "result_status": "Đã hoàn thành" if passed else "Cần ôn/Chưa đạt",
                            "completed_at": now_str if passed else "",
                            "is_test_submit": True,
                            "answers": answers
                        }
                        threading.Thread(target=sync_to_google_sheet, args=([sync_item], sheet_url, db_path), daemon=True).start()
            except Exception as e:
                print(f"[Sheet Trigger Exception] {e}")

            return json_resp(200, {
                "attempt_id": attempt_id,
                "score": score,
                "total_questions": total_required,
                "pass_threshold": pass_threshold,
                "passed": passed,
                "failed_questions": failed_questions,
                "submitted_at": now_str
            })
        finally:
            conn.close()

    if path == "/api/simple/test/result" and method == "GET":
        if not current_auth or current_auth.get("is_admin"):
            return error_resp(401, "Chưa đăng nhập người học.")

        conn = get_db_connection(db_path)
        try:
            latest = conn.execute("""
                SELECT * FROM simple_test_attempts
                WHERE learner_id = ? AND course_version = ? AND state = 'SUBMITTED'
                ORDER BY submitted_at DESC LIMIT 1
            """, (current_auth["id"], COURSE_VERSION)).fetchone()

            if not latest:
                return error_resp(404, "Chưa có kết quả kiểm tra.")

            q_data = load_questions_data()
            key_data = load_answer_key_data()
            key_map = {a["id"]: a for a in key_data.get("answers", [])}
            q_map = {q["id"]: q for q in q_data.get("questions", [])}
            saved_answers = json.loads(latest["answers_json"])

            failed_questions = []
            for q in q_data.get("questions", []):
                qid = q["id"]
                user_choice = saved_answers.get(qid)
                key_item = key_map.get(qid)
                correct_id = key_item.get("correct_option_id") if key_item else None

                if user_choice != correct_id:
                    opt_map = {o["id"]: o["text_vi"] for o in q["options"]}
                    failed_questions.append({
                        "id": qid,
                        "question_vi": q["question_vi"],
                        "your_answer": opt_map.get(user_choice, "Chưa chọn"),
                        "correct_answer": opt_map.get(correct_id, ""),
                        "explanation_vi": key_item.get("explanation_vi") if key_item else "",
                        "review_slide_ids": q.get("review_slide_ids", [])
                    })

            return json_resp(200, {
                "attempt_id": latest["id"],
                "score": latest["score"],
                "total_questions": len(q_data.get("questions", [])),
                "passed": bool(latest["passed"]),
                "failed_questions": failed_questions,
                "submitted_at": latest["submitted_at"]
            })
        finally:
            conn.close()

    # ---------------- 4. ADMIN & MANAGEMENT ----------------
    if path == "/api/simple/admin/login" and method == "POST":
        user = body.get("username", "").strip()
        pwd = body.get("password", "")

        if user == ADMIN_USERNAME and pwd == ADMIN_PASSWORD:
            token = create_access_token(user_id="ADMIN01", employee_id="ADMIN01", roles=[{"is_admin": True, "username": user}])
            return json_resp(200, {"success": True, "token": token, "username": user})
        return error_resp(401, "Tài khoản hoặc mật khẩu quản trị không đúng.")

    if path == "/api/simple/admin/report" and method == "GET":
        if not current_auth or not current_auth.get("is_admin"):
            return error_resp(403, "Cần quyền Quản trị viên để truy cập báo cáo.")

        status_filter = query_params.get("status", "ALL")
        pos_filter = query_params.get("position", "ALL")
        search_query = query_params.get("q", "").strip().lower()

        conn = get_db_connection(db_path)
        try:
            learners = conn.execute("SELECT * FROM simple_learners ORDER BY created_at DESC").fetchall()
            report_rows = []

            for l in learners:
                summary = get_learner_progress_summary(l["id"], db_path=db_path)
                
                # Filter by status
                if status_filter != "ALL" and summary["status_text"] != status_filter:
                    continue

                # Filter by position
                if pos_filter != "ALL" and l["position"] != pos_filter:
                    continue

                # Search by query (ID, Name, or Position)
                if search_query:
                    match_id = search_query in l["employee_id"].lower()
                    match_name = search_query in l["full_name"].lower()
                    match_pos = search_query in (l["position"] or "").lower()
                    if not match_id and not match_name and not match_pos:
                        continue

                report_rows.append({
                    "employee_id": l["employee_id"],
                    "full_name": l["full_name"],
                    "position": l["position"],
                    "course_version": COURSE_VERSION,
                    "started_at": l["created_at"],
                    "slides_viewed_count": f"{summary['slides_viewed_count']}/20",
                    "is_completed_slides": "Có" if summary["is_completed_slides"] else "Chưa",
                    "attempts_count": summary["attempts_count"],
                    "latest_score": f"{int(summary['latest_score'])}/10" if summary["latest_score"] is not None else "—",
                    "result_status": summary["status_text"],
                    "completed_at": summary["completed_at"] or "—"
                })

            return json_resp(200, {
                "course_version": COURSE_VERSION,
                "total_learners": len(report_rows),
                "learners": report_rows
            })
        finally:
            conn.close()

    if path == "/api/simple/admin/export-csv" and method == "GET":
        # Check token via query param or header
        token = query_params.get("auth")
        auth_user = None
        if token:
            payload = verify_access_token(token)
            if payload:
                roles = payload.get("roles", [])
                for r in roles:
                    if isinstance(r, dict) and r.get("is_admin"):
                        auth_user = payload
        elif current_auth and current_auth.get("is_admin"):
            auth_user = current_auth

        if not auth_user:
            return error_resp(403, "Cần quyền Quản trị viên để xuất báo cáo.")

        output = io.StringIO()
        # UTF-8 BOM so Excel opens with proper Vietnamese diacritics
        output.write("\ufeff")
        writer = csv.writer(output)

        # Header matching Mau_bao_cao.csv
        writer.writerow([
            "Mã nhân viên", "Họ tên", "Vị trí", "Phiên bản khóa học", "Bắt đầu",
            "Số trang đã học", "Đã học hết", "Số lần làm bài", "Điểm gần nhất /10", "Kết quả", "Hoàn tất"
        ])

        conn = get_db_connection(db_path)
        try:
            learners = conn.execute("SELECT * FROM simple_learners ORDER BY created_at DESC").fetchall()
            for l in learners:
                summary = get_learner_progress_summary(l["id"], db_path=db_path)
                writer.writerow([
                    sanitize_csv_cell(l["employee_id"]),
                    sanitize_csv_cell(l["full_name"]),
                    sanitize_csv_cell(l["position"]),
                    sanitize_csv_cell(COURSE_VERSION),
                    sanitize_csv_cell(l["created_at"]),
                    sanitize_csv_cell(f"{summary['slides_viewed_count']}/20"),
                    sanitize_csv_cell("Có" if summary["is_completed_slides"] else "Chưa"),
                    sanitize_csv_cell(summary["attempts_count"]),
                    sanitize_csv_cell(int(summary["latest_score"]) if summary["latest_score"] is not None else "—"),
                    sanitize_csv_cell(summary["status_text"]),
                    sanitize_csv_cell(summary["completed_at"] or "—")
                ])

            csv_bytes = output.getvalue().encode("utf-8")
            csv_headers = {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": 'attachment; filename="ASV_Bao_cao_Kiem_ke_San_xuat.csv"'
            }
            return 200, csv_headers, csv_bytes
        finally:
            conn.close()

    # ---------------- 5. GOOGLE SHEETS SYNC APIS ----------------
    if path == "/api/simple/admin/sheet-config" and method == "GET":
        if not current_auth or not current_auth.get("is_admin"):
            return error_resp(403, "Cần quyền Quản trị viên.")
        url = get_setting("google_sheet_webhook_url", db_path=db_path) or GOOGLE_SHEET_WEBHOOK_URL
        return json_resp(200, {"webhook_url": url or ""})

    if path == "/api/simple/admin/sheet-config" and method == "POST":
        if not current_auth or not current_auth.get("is_admin"):
            return error_resp(403, "Cần quyền Quản trị viên.")
        url = str(body.get("webhook_url", "")).strip()
        set_setting("google_sheet_webhook_url", url, db_path=db_path)
        return json_resp(200, {"success": True, "webhook_url": url})

    if path == "/api/simple/admin/sync-sheet" and method == "POST":
        if not current_auth or not current_auth.get("is_admin"):
            return error_resp(403, "Cần quyền Quản trị viên.")
        url = str(body.get("webhook_url", "")).strip() or get_setting("google_sheet_webhook_url", db_path=db_path) or GOOGLE_SHEET_WEBHOOK_URL
        if not url:
            return error_resp(400, "Vui lòng nhập đường dẫn Google Apps Script Webhook URL.")

        conn = get_db_connection(db_path)
        try:
            learners = conn.execute("SELECT * FROM simple_learners ORDER BY created_at ASC").fetchall()
            records = []
            for l in learners:
                summary = get_learner_progress_summary(l["id"], db_path=db_path)
                records.append({
                    "employee_id": l["employee_id"],
                    "full_name": l["full_name"],
                    "position": l["position"],
                    "started_at": l["created_at"],
                    "slides_viewed_count": f"{summary['slides_viewed_count']}/20",
                    "is_completed_slides": "Có" if summary["is_completed_slides"] else "Chưa",
                    "attempts_count": summary["attempts_count"],
                    "latest_score": f"{int(summary['latest_score'])}/10" if summary["latest_score"] is not None else "—",
                    "result_status": summary["status_text"],
                    "completed_at": summary["completed_at"] or "—"
                })
        finally:
            conn.close()

        if not records:
            return json_resp(200, {"success": True, "count": 0, "message": "Hiện chưa có dữ liệu học viên để đồng bộ."})

        ok = sync_to_google_sheet(records, webhook_url=url, db_path=db_path)
        if ok:
            return json_resp(200, {"success": True, "count": len(records), "message": f"Đã đồng bộ thành công {len(records)} học viên sang Google Sheet!"})
        else:
            return error_resp(500, "Không thể kết nối đến Google Sheet Webhook. Vui lòng kiểm tra lại đường dẫn Webhook URL và quyền truy cập.")

    return error_resp(404, f"API không tồn tại: {path}")
