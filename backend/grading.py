"""Server-side assessment grading, question blueprints, simulation state engine, and qualification logic."""
import json
import random
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from backend.config import COURSE_VERSION, DEADLINE_EXCLUSIVE, TZ_VN, now_vn, now_iso
from backend.db import get_db_connection, db_transaction

# Reference thresholds
LIMITS = {'THEORY': 90, 'SIMULATION': 90, 'HARDWARE_COMMON': 90, 'A2_PC': 45, 'CONTROLLER': 25}
MAXIMUMS = {'THEORY': 100, 'SIMULATION': 100, 'HARDWARE_COMMON': 100, 'A2_PC': 50, 'CONTROLLER': 30}

def check_threshold(kind: str, score: float, critical_failed: List[str], missing_observations: int = 0) -> bool:
    if kind not in LIMITS:
        return False
    return (0 <= score <= MAXIMUMS[kind] and
            score >= LIMITS[kind] and
            len(critical_failed) == 0 and
            missing_observations == 0)

def calculate_current_result(attempts: List[Dict[str, Any]]) -> str:
    """Calculates official current result for a candidate/type on current version.
    chronological order, non-voided.
    """
    official = [a for a in attempts if a.get('official') and a.get('state') != 'VOIDED']
    if any(a.get('state') in ('CREATED', 'IN_PROGRESS', 'SUBMITTED') for a in official):
        return 'PENDING'
    graded = [a for a in official if a.get('state') == 'GRADED']
    if not graded:
        return 'PENDING'
    return 'PASS' if graded[-1].get('passed') else 'FAIL'

def is_on_time(iso_timestamp: str) -> bool:
    dt = datetime.fromisoformat(iso_timestamp)
    return dt < DEADLINE_EXCLUSIVE

def calculate_qualified_rate(real_required: int, qualified: int) -> Optional[float]:
    return (qualified / real_required) if real_required > 0 else None

def check_readiness(d: Dict[str, bool]) -> bool:
    return all(d.get(k, False) for k in [
        'lessons', 'attendance', 'theory', 'simulation', 'hardware', 'special', 'current_version', 'signature'
    ])

# ---------------- THEORY EXAM ENGINE ----------------

def generate_theory_exam(user_id: str, is_demo: bool = False, db_path=None) -> Dict[str, Any]:
    """Generates an official or demo theory exam attempt according to blueprint:
    Draw 1 question from each of 4 critical pools (CR_FREEZE, CR_INDEPENDENCE, CR_STICKER, CR_RELEASE)
    Draw 2 questions from each of 8 general pools. Total 20 questions, 20 minutes.
    Shuffles options for each question snapshot.
    """
    conn = get_db_connection(db_path)
    try:
        # Check if there is an active exam attempt
        active_attempt = conn.execute("""
            SELECT * FROM assessment_attempts
            WHERE user_id = ? AND course_version = ? AND type = 'THEORY' AND state IN ('CREATED', 'IN_PROGRESS')
        """, (user_id, COURSE_VERSION)).fetchone()
        
        if active_attempt:
            # Check expiration
            expires_at = datetime.fromisoformat(active_attempt["expires_at"])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=TZ_VN)
            if now_vn() >= expires_at:
                # Expired - auto-submit and grade
                conn.close()
                return submit_theory_exam(active_attempt["id"], answers={}, auto_submit_reason="EXPIRED", db_path=db_path)
            
            # Retrieve existing active attempt items in exact order
            items_rows = conn.execute("""
                SELECT id, question_id, question_snapshot, pool, critical, selected_option_id, answered_at
                FROM theory_items WHERE attempt_id = ?
                ORDER BY item_order ASC, rowid ASC
            """, (active_attempt["id"],)).fetchall()
            
            items = []
            for r in items_rows:
                items.append({
                    "item_id": r["id"],
                    "question_id": r["question_id"],
                    "snapshot": json.loads(r["question_snapshot"]),
                    "pool": r["pool"],
                    "critical": bool(r["critical"]),
                    "selected_option_id": r["selected_option_id"]
                })
            
            return {
                "attempt_id": active_attempt["id"],
                "state": active_attempt["state"],
                "started_at": active_attempt["started_at"],
                "expires_at": active_attempt["expires_at"],
                "minutes": 20,
                "is_demo": bool(active_attempt["is_demo"]),
                "questions": items
            }
        
        # Check deadline before opening
        now = now_vn()
        if now >= DEADLINE_EXCLUSIVE:
            raise ValueError("Kỳ thi đã kết thúc. Không thể mở đề sau hạn chót 01/12/2026.")
        
        # Calculate expiration: min(now + 20 mins, DEADLINE_EXCLUSIVE)
        from datetime import timedelta
        expires_at = min(now + timedelta(minutes=20), DEADLINE_EXCLUSIVE)
        if (expires_at - now).total_seconds() < 60:
            raise ValueError("Thời gian còn lại trước hạn chót không đủ để thực hiện bài thi.")

        # Load blueprint and all questions from content_records
        bp_row = conn.execute("SELECT public_payload FROM content_records WHERE content_id = 'blueprint' AND course_version = ?", (COURSE_VERSION,)).fetchone()
        bp = json.loads(bp_row["public_payload"])["theory"]
        
        q_rows = conn.execute("SELECT content_id, public_payload FROM content_records WHERE kind = 'question' AND course_version = ?", (COURSE_VERSION,)).fetchall()
        pools_dict: Dict[str, List[Dict[str, Any]]] = {}
        for r in q_rows:
            q_data = json.loads(r["public_payload"])
            pool = q_data["pool"]
            pools_dict.setdefault(pool, []).append(q_data)
        
        selected_questions = []
        for pool_cfg in bp["pools"]:
            pool_name = pool_cfg["pool"]
            draw_count = pool_cfg["draw"]
            available = list(pools_dict.get(pool_name, []))
            random.shuffle(available)
            selected_questions.extend(available[:draw_count])
        
        attempt_id = str(uuid.uuid4())
        policy_snapshot = {
            "version": COURSE_VERSION,
            "pass_score": bp["pass_score"],
            "critical_all_correct": bp["critical_all_correct"],
            "minutes": bp["minutes"],
            "points_each": bp["points_each"],
            "question_count": len(selected_questions)
        }
        
        with db_transaction(db_path) as tx_conn:
            tx_conn.execute("""
                INSERT INTO assessment_attempts (
                    id, user_id, course_version, type, state, official, is_demo,
                    policy_snapshot, started_at, expires_at
                ) VALUES (?, ?, ?, 'THEORY', 'IN_PROGRESS', ?, ?, ?, ?, ?)
            """, (
                attempt_id, user_id, COURSE_VERSION,
                0 if is_demo else 1,
                1 if is_demo else 0,
                json.dumps(policy_snapshot, ensure_ascii=False),
                now.isoformat(),
                expires_at.isoformat()
            ))
            
            client_items = []
            for idx, q in enumerate(selected_questions):
                # Shuffle options in snapshot
                options = list(q["options"])
                random.shuffle(options)
                snapshot = {
                    "id": q["id"],
                    "stem_vi": q["stem_vi"],
                    "options": options,
                    "pool": q["pool"],
                    "critical": q["critical"]
                }
                item_id = str(uuid.uuid4())
                tx_conn.execute("""
                    INSERT INTO theory_items (
                        id, attempt_id, item_order, question_id, question_snapshot, pool, critical
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_id, attempt_id, idx, q["id"],
                    json.dumps(snapshot, ensure_ascii=False),
                    q["pool"], 1 if q["critical"] else 0
                ))
                
                client_items.append({
                    "item_id": item_id,
                    "question_id": q["id"],
                    "snapshot": snapshot,
                    "pool": q["pool"],
                    "critical": q["critical"],
                    "selected_option_id": None
                })
        
        return {
            "attempt_id": attempt_id,
            "state": "IN_PROGRESS",
            "started_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "minutes": 20,
            "is_demo": is_demo,
            "questions": client_items
        }
    finally:
        conn.close()

def save_theory_progress(attempt_id: str, answers: Dict[str, str], db_path=None) -> Dict[str, Any]:
    """Saves answers for an ongoing theory exam without grading."""
    with db_transaction(db_path) as conn:
        attempt = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt or attempt["state"] != "IN_PROGRESS":
            raise ValueError("Bài thi không trong trạng thái làm bài.")
        
        expires_at = datetime.fromisoformat(attempt["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=TZ_VN)
        if now_vn() >= expires_at:
            return submit_theory_exam(attempt_id, answers, auto_submit_reason="EXPIRED", db_path=db_path)
            
        now_str = now_iso()
        for q_id, opt_id in answers.items():
            conn.execute("""
                UPDATE theory_items
                SET selected_option_id = ?, answered_at = ?
                WHERE attempt_id = ? AND question_id = ?
            """, (opt_id, now_str, attempt_id, q_id))
            
    return {"status": "SAVED", "attempt_id": attempt_id}

def submit_theory_exam(attempt_id: str, answers: Optional[Dict[str, str]] = None, auto_submit_reason: Optional[str] = None, db_path=None) -> Dict[str, Any]:
    """Grades a theory exam on server.
    Compares selected options against server private grading keys.
    Computes score (5 pts/correct), checks all critical questions.
    Returns graded result.
    """
    with db_transaction(db_path) as conn:
        attempt = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt:
            raise ValueError("Không tìm thấy bài thi.")
        if attempt["state"] == "GRADED":
            # Already graded, return result
            return get_theory_attempt_result(attempt_id, conn)

        # Update any last-minute answers passed
        now_str = now_iso()
        if answers:
            for q_id, opt_id in answers.items():
                conn.execute("""
                    UPDATE theory_items
                    SET selected_option_id = ?, answered_at = ?
                    WHERE attempt_id = ? AND question_id = ?
                """, (opt_id, now_str, attempt_id, q_id))

        # Grade items against private keys
        items = conn.execute("SELECT * FROM theory_items WHERE attempt_id = ?", (attempt_id,)).fetchall()
        total_questions = len(items)
        correct_count = 0
        critical_fail_ids = []
        remedial_lesson_ids = set()

        for item in items:
            q_id = item["question_id"]
            selected_option = item["selected_option_id"]
            key_row = conn.execute("""
                SELECT private_grading_ref FROM content_records
                WHERE content_id = ? AND kind = 'question' AND course_version = ?
            """, (q_id, attempt["course_version"])).fetchone()
            
            key_data = json.loads(key_row["private_grading_ref"]) if key_row and key_row["private_grading_ref"] else {}
            correct_option_id = key_data.get("correct_option_id")
            
            is_correct = (selected_option == correct_option_id) if selected_option else False
            if is_correct:
                correct_count += 1
            else:
                if item["critical"]:
                    critical_fail_ids.append(item["pool"])
                for lid in key_data.get("remedial_lesson_ids", []):
                    remedial_lesson_ids.add(lid)
                    
            conn.execute("""
                UPDATE theory_items
                SET is_correct = ?
                WHERE id = ?
            """, (1 if is_correct else 0, item["id"]))

        score = correct_count * 5.0
        policy = json.loads(attempt["policy_snapshot"])
        pass_threshold = policy.get("pass_score", 90)
        
        # Pass requires score >= 90 AND all critical correct
        passed = (score >= pass_threshold and len(critical_fail_ids) == 0)

        conn.execute("""
            UPDATE assessment_attempts
            SET state = 'GRADED',
                submitted_at = ?,
                graded_at = ?,
                score = ?,
                passed = ?,
                critical_fail_ids = ?,
                notes = ?
            WHERE id = ?
        """, (
            now_str,
            now_str,
            score,
            1 if passed else 0,
            json.dumps(critical_fail_ids),
            auto_submit_reason,
            attempt_id
        ))

        # Record remedial action if failed
        if not passed and attempt["official"]:
            conn.execute("""
                INSERT INTO remedial_actions (
                    id, user_id, failed_attempt_id, lesson_ids, critical_error_ids, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'OPEN', ?)
            """, (
                str(uuid.uuid4()),
                attempt["user_id"],
                attempt_id,
                json.dumps(list(remedial_lesson_ids)),
                json.dumps(critical_fail_ids),
                now_str
            ))

        return get_theory_attempt_result(attempt_id, conn)

def get_theory_attempt_result(attempt_id: str, conn) -> Dict[str, Any]:
    attempt = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
    items = conn.execute("SELECT * FROM theory_items WHERE attempt_id = ?", (attempt_id,)).fetchall()
    
    graded_items = []
    for it in items:
        key_row = conn.execute("""
            SELECT private_grading_ref FROM content_records
            WHERE content_id = ? AND kind = 'question' AND course_version = ?
        """, (it["question_id"], attempt["course_version"])).fetchone()
        key_data = json.loads(key_row["private_grading_ref"]) if key_row and key_row["private_grading_ref"] else {}
        
        graded_items.append({
            "question_id": it["question_id"],
            "pool": it["pool"],
            "critical": bool(it["critical"]),
            "selected_option_id": it["selected_option_id"],
            "is_correct": bool(it["is_correct"]),
            "correct_option_id": key_data.get("correct_option_id"),
            "explanation_vi": key_data.get("explanation_vi")
        })

    return {
        "attempt_id": attempt["id"],
        "user_id": attempt["user_id"],
        "state": attempt["state"],
        "score": attempt["score"],
        "passed": bool(attempt["passed"]),
        "critical_fail_ids": json.loads(attempt["critical_fail_ids"]),
        "submitted_at": attempt["submitted_at"],
        "official": bool(attempt["official"]),
        "is_demo": bool(attempt["is_demo"]),
        "items": graded_items
    }

# ---------------- SIMULATION ENGINE ----------------

def start_simulation_attempt(user_id: str, is_official: bool = True, is_demo: bool = False, db_path=None) -> Dict[str, Any]:
    """Starts a simulation attempt (10 assessed cases SIM01-SIM10 + 2 practice cases P01-P02)."""
    now = now_vn()
    if is_official and now >= DEADLINE_EXCLUSIVE:
        raise ValueError("Kỳ thi mô phỏng đã kết thúc sau hạn chót 01/12/2026.")

    conn = get_db_connection(db_path)
    try:
        # Check active attempt
        if is_official:
            active = conn.execute("""
                SELECT * FROM assessment_attempts
                WHERE user_id = ? AND course_version = ? AND type = 'SIMULATION' AND state IN ('CREATED', 'IN_PROGRESS')
            """, (user_id, COURSE_VERSION)).fetchone()
            if active:
                return {"attempt_id": active["id"], "state": active["state"], "expires_at": active["expires_at"]}

        attempt_id = str(uuid.uuid4())
        from datetime import timedelta
        expires_at = min(now + timedelta(minutes=15), DEADLINE_EXCLUSIVE) if is_official else now + timedelta(hours=2)

        policy_snapshot = {
            "version": COURSE_VERSION,
            "pass_score": 90,
            "case_count": 10,
            "points_each": 10
        }

        with db_transaction(db_path) as tx_conn:
            tx_conn.execute("""
                INSERT INTO assessment_attempts (
                    id, user_id, course_version, type, state, official, is_demo,
                    policy_snapshot, started_at, expires_at
                ) VALUES (?, ?, ?, 'SIMULATION', 'IN_PROGRESS', ?, ?, ?, ?, ?)
            """, (
                attempt_id, user_id, COURSE_VERSION,
                1 if is_official else 0,
                1 if is_demo else 0,
                json.dumps(policy_snapshot, ensure_ascii=False),
                now.isoformat(),
                expires_at.isoformat()
            ))

        return {
            "attempt_id": attempt_id,
            "state": "IN_PROGRESS",
            "started_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "official": is_official,
            "is_demo": is_demo
        }
    finally:
        conn.close()

def process_simulation_event(
    attempt_id: str,
    case_id: str,
    seq: int,
    idempotency_key: str,
    event_type: str,
    payload: Dict[str, Any],
    actor: str,
    db_path=None
) -> Dict[str, Any]:
    """Processes an event in a simulation case.
    Enforces idempotency, sequence checks, state transitions, and server-side critical event detection.
    """
    with db_transaction(db_path) as conn:
        attempt = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt or attempt["state"] != "IN_PROGRESS":
            raise ValueError("Lượt thi mô phỏng không hoạt động.")

        exp_dt = datetime.fromisoformat(attempt["expires_at"])
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=TZ_VN)
        if attempt["official"] and now_vn() >= exp_dt:
            # Auto submit on timeout
            conn.execute("UPDATE assessment_attempts SET state = 'SUBMITTED', submitted_at = ? WHERE id = ?", (now_iso(), attempt_id))
            raise ValueError("Đã hết thời gian làm bài mô phỏng. Hệ thống tự động nộp bài.")

        # Idempotency check: same idempotency_key
        existing_event = conn.execute("""
            SELECT * FROM simulation_events WHERE attempt_id = ? AND case_id = ? AND idempotency_key = ?
        """, (attempt_id, case_id, idempotency_key)).fetchone()

        if existing_event:
            # Check if payload matches
            saved_payload = json.loads(existing_event["payload"])
            if saved_payload == payload and existing_event["event_type"] == event_type:
                return {
                    "status": "IDEMPOTENT_REPLAY",
                    "event_id": existing_event["event_id"],
                    "case_id": case_id,
                    "next_state": existing_event["next_state"]
                }
            else:
                raise ValueError("409 Conflict: idempotency_key trùng lặp với payload khác.")

        # Check sequence
        last_event = conn.execute("""
            SELECT seq, next_state FROM simulation_events
            WHERE attempt_id = ? AND case_id = ?
            ORDER BY seq DESC LIMIT 1
        """, (attempt_id, case_id)).fetchone()

        expected_seq = (last_event["seq"] + 1) if last_event else 1
        if seq != expected_seq:
            raise ValueError(f"Stale sequence: nhận seq {seq}, mong đợi {expected_seq}.")

        # Retrieve case grading rules
        rule_row = conn.execute("""
            SELECT private_grading_ref FROM content_records
            WHERE content_id = ? AND kind = 'simulation' AND course_version = ?
        """, (case_id, attempt["course_version"])).fetchone()
        rules = json.loads(rule_row["private_grading_ref"]) if rule_row and rule_row["private_grading_ref"] else {}

        # Analyze event against critical rules
        critical_terminals = rules.get("critical_terminal_events", [])
        is_critical = False
        critical_name = None

        # Diagnostic event: SCAN_PREVIEW does not advance or fail
        if event_type == "SCAN_PREVIEW":
            event_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO simulation_events (
                    id, attempt_id, case_id, seq, event_id, idempotency_key, event_type, payload,
                    previous_state, next_state, server_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), attempt_id, case_id, seq, event_id, idempotency_key, event_type,
                json.dumps(payload), last_event["next_state"] if last_event else "ACTIVE",
                last_event["next_state"] if last_event else "ACTIVE", now_iso()
            ))
            return {
                "status": "DIAGNOSTIC_PREVIEW",
                "event_id": event_id,
                "case_id": case_id,
                "next_state": last_event["next_state"] if last_event else "ACTIVE"
            }

        # Check critical events based on scenario specifics
        if event_type in critical_terminals:
            is_critical = True
            critical_name = event_type
        elif case_id == "SIM01" and event_type == "COUNT_SUBMITTED" and payload.get("qty") != 18:
            is_critical = True
            critical_name = "COMMIT_FAKE_QTY"
        elif case_id == "SIM04" and event_type == "OPERATOR_B_CHOSEN" and payload.get("operator_b") == "OPERATOR_A":
            is_critical = True
            critical_name = "COMMIT_SELF_CHECK"
        elif case_id == "SIM05" and event_type == "CONFIRM_MAPPING" and (
            payload.get("box_id") != "SIM-ASV-BOX-05" or payload.get("p_number") != "P-05" or payload.get("cell_id") != "W01-R02-B03"
        ):
            is_critical = True
            critical_name = "COMMIT_WRONG_MAPPING"
        elif case_id == "SIM05" and event_type == "APPLY_STICKER1":
            # Check if verified first
            has_verified = conn.execute("""
                SELECT 1 FROM simulation_events
                WHERE attempt_id = ? AND case_id = ? AND event_type = 'VERIFY_BOX'
            """, (attempt_id, case_id)).fetchone()
            if not has_verified:
                is_critical = True
                critical_name = "APPLY_STICKER1_BEFORE_CHECK"

        next_state = "CRITICAL_FAILED" if is_critical else "ACTIVE"
        event_id = str(uuid.uuid4())

        conn.execute("""
            INSERT INTO simulation_events (
                id, attempt_id, case_id, seq, event_id, idempotency_key, event_type, payload,
                previous_state, next_state, server_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), attempt_id, case_id, seq, event_id, idempotency_key, event_type,
            json.dumps(payload), last_event["next_state"] if last_event else "NOT_STARTED",
            next_state, now_iso()
        ))

        # Update case results
        if is_critical:
            conn.execute("""
                INSERT INTO simulation_case_results (
                    id, attempt_id, case_id, state, score, critical_failed, critical_terminal_event, submitted_at
                ) VALUES (?, ?, ?, 'CRITICAL_FAILED', 0, 1, ?, ?)
                ON CONFLICT(attempt_id, case_id) DO UPDATE SET
                    state = 'CRITICAL_FAILED',
                    score = 0,
                    critical_failed = 1,
                    critical_terminal_event = excluded.critical_terminal_event,
                    submitted_at = excluded.submitted_at
            """, (str(uuid.uuid4()), attempt_id, case_id, critical_name, now_iso()))

        return {
            "status": "EVENT_RECORDED",
            "event_id": event_id,
            "case_id": case_id,
            "is_critical": is_critical,
            "critical_terminal_event": critical_name,
            "next_state": next_state
        }

def submit_simulation_case(attempt_id: str, case_id: str, db_path=None) -> Dict[str, Any]:
    """Finalizes and grades a single simulation case."""
    with db_transaction(db_path) as conn:
        attempt = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
        rule_row = conn.execute("""
            SELECT private_grading_ref, public_payload FROM content_records
            WHERE content_id = ? AND kind = 'simulation' AND course_version = ?
        """, (case_id, attempt["course_version"])).fetchone()
        rules = json.loads(rule_row["private_grading_ref"]) if rule_row and rule_row["private_grading_ref"] else {}
        pub = json.loads(rule_row["public_payload"]) if rule_row and rule_row["public_payload"] else {}

        # Check existing result
        res = conn.execute("SELECT * FROM simulation_case_results WHERE attempt_id = ? AND case_id = ?", (attempt_id, case_id)).fetchone()
        if res and res["state"] == "CRITICAL_FAILED":
            return dict(res)

        # Retrieve events
        events = conn.execute("""
            SELECT event_type, payload FROM simulation_events
            WHERE attempt_id = ? AND case_id = ? AND event_type != 'SCAN_PREVIEW'
            ORDER BY seq ASC
        """, (attempt_id, case_id)).fetchall()

        expected_steps = rules.get("expected_steps", [])
        semantic_rules = rules.get("semantic_rules", {})
        is_pass = False

        matching_type = rules.get("matching")
        if semantic_rules.get("accept_any_valid_batch_partition") and case_id == "SIM03":
            # Any valid batch partition of lines <= 5
            batches = [json.loads(e["payload"]) for e in events if e["event_type"] == "BATCH_SUBMITTED"]
            total_lines = sum(len(b.get("lines", [])) for b in batches)
            all_valid_sizes = all(1 <= len(b.get("lines", [])) <= 5 for b in batches)
            if total_lines == 6 and all_valid_sizes:
                is_pass = True
        elif (matching_type == "ordered_phases_unordered_members" or case_id == "SIM10"):
            # SIM10 / Unordered groups: Check all cells A and B in any order, then reconcile/escalate
            checked_a = any((json.loads(e["payload"]).get("cell") == "SIM-ASV-A" or json.loads(e["payload"]).get("cell_id") == "W01-A") for e in events if e["event_type"] in ("CHECK_CELL", "CELL_RECONCILED"))
            checked_b = any((json.loads(e["payload"]).get("cell") == "SIM-ASV-B" or json.loads(e["payload"]).get("cell_id") == "W01-B") for e in events if e["event_type"] in ("CHECK_CELL", "CELL_RECONCILED"))
            has_reconcile = any(e["event_type"] in ("RECONCILE", "SUMMARY_SUBMITTED") for e in events)
            if checked_a and checked_b and has_reconcile:
                is_pass = True
        else:
            # Match expected steps sequence
            if len(events) >= len(expected_steps):
                step_matches = True
                for exp, actual in zip(expected_steps, events):
                    if exp["event_type"] != actual["event_type"]:
                        step_matches = False
                        break
                    actual_payload = json.loads(actual["payload"])
                    exp_payload = exp.get("payload_subset", {})
                    for k, v in exp_payload.items():
                        if actual_payload.get(k) != v:
                            step_matches = False
                            break
                    if not step_matches:
                        break
                is_pass = step_matches

        points = pub.get("points", 10) if pub.get("assessed", True) else 0
        score = points if is_pass else 0
        state = "COMPLETED_CORRECT" if is_pass else "COMPLETED_INCORRECT"

        conn.execute("""
            INSERT INTO simulation_case_results (
                id, attempt_id, case_id, state, score, critical_failed, critical_terminal_event, submitted_at
            ) VALUES (?, ?, ?, ?, ?, 0, NULL, ?)
            ON CONFLICT(attempt_id, case_id) DO UPDATE SET
                state = excluded.state,
                score = excluded.score,
                critical_failed = 0,
                submitted_at = excluded.submitted_at
        """, (str(uuid.uuid4()), attempt_id, case_id, state, score, now_iso()))

        return {
            "case_id": case_id,
            "state": state,
            "score": score,
            "critical_failed": False,
            "explanation_vi": rules.get("explanation_vi")
        }

def submit_simulation_attempt(attempt_id: str, db_path=None) -> Dict[str, Any]:
    """Finalizes and grades the complete simulation attempt."""
    with db_transaction(db_path) as conn:
        attempt = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt:
            raise ValueError("Không tìm thấy bài thi mô phỏng.")

        results = conn.execute("SELECT * FROM simulation_case_results WHERE attempt_id = ?", (attempt_id,)).fetchall()
        total_score = sum(r["score"] for r in results)
        critical_failed = any(r["critical_failed"] for r in results)
        critical_events = [r["critical_terminal_event"] for r in results if r["critical_failed"] and r["critical_terminal_event"]]

        passed = (total_score >= 90 and not critical_failed)
        now_str = now_iso()

        conn.execute("""
            UPDATE assessment_attempts
            SET state = 'GRADED',
                submitted_at = ?,
                graded_at = ?,
                score = ?,
                passed = ?,
                critical_fail_ids = ?
            WHERE id = ?
        """, (
            now_str, now_str, total_score,
            1 if passed else 0,
            json.dumps(critical_events),
            attempt_id
        ))

        return {
            "attempt_id": attempt_id,
            "score": total_score,
            "passed": passed,
            "critical_fail_ids": critical_events,
            "submitted_at": now_str
        }

# ---------------- HARDWARE REAL PDA CHECKLIST ENGINE ----------------

def submit_hardware_assessment(
    assessor_id: str,
    learner_id: str,
    assessment_type: str,  # HARDWARE_COMMON, A2_PC, CONTROLLER
    session_id: str,
    device_id: str,
    lab_id: str,
    observations: Dict[str, Optional[int]],  # criterion_id -> 5, 0, or None
    notes: str,
    attestation: str,
    is_demo: bool = False,
    db_path=None
) -> Dict[str, Any]:
    """Records and grades a real PDA or special role hardware observation.
    Assessor must NOT be learner (anti-self-eval).
    Score: 5 pts per pass, 0 for fail, NULL not allowed for submission.
    Checks threshold, missing observations, critical fails, and records signature.
    """
    if assessor_id == learner_id:
        raise PermissionError("Giám khảo không được tự chấm/tự ký bản thân.")

    now = now_vn()
    if not is_demo and now >= DEADLINE_EXCLUSIVE:
        raise ValueError("Sát hạch PDA thật phải hoàn tất trước hạn chót 01/12/2026.")

    conn = get_db_connection(db_path)
    try:
        # Load rubric definition
        rubric_row = conn.execute("""
            SELECT public_payload FROM content_records
            WHERE content_id = 'hardware_rubrics' AND course_version = ?
        """, (COURSE_VERSION,)).fetchone()
        rubrics = json.loads(rubric_row["public_payload"])

        if assessment_type == "HARDWARE_COMMON":
            criteria_list = rubrics["common"]
            expected_count = 20
        elif assessment_type == "A2_PC":
            criteria_list = rubrics["special"]["A2_PC"]
            expected_count = 10
        elif assessment_type == "CONTROLLER":
            criteria_list = rubrics["special"]["CONTROLLER"]
            expected_count = 6
        else:
            raise ValueError(f"Loại sát hạch không hợp lệ: {assessment_type}")

        criteria_map = {c["id"]: c for c in criteria_list}
        missing_count = 0
        critical_fail_ids = []
        score = 0.0

        for cid, crit in criteria_map.items():
            val = observations.get(cid)
            if val is None:
                missing_count += 1
            elif val == 5 or val == 1:
                score += 5.0
            elif val == 0:
                if crit.get("critical", False):
                    critical_fail_ids.append(cid)
            else:
                missing_count += 1

        # Check threshold
        passed = check_threshold(assessment_type, score, critical_fail_ids, missing_count)
        attempt_id = str(uuid.uuid4())
        now_str = now_iso()

        with db_transaction(db_path) as tx_conn:
            tx_conn.execute("""
                INSERT INTO assessment_attempts (
                    id, user_id, course_version, type, state, official, is_demo,
                    policy_snapshot, started_at, expires_at, submitted_at, graded_at,
                    score, passed, critical_fail_ids, missing_observations,
                    assessor_id, device_id, lab_id, notes
                ) VALUES (?, ?, ?, ?, 'GRADED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt_id, learner_id, COURSE_VERSION, assessment_type,
                0 if is_demo else 1,
                1 if is_demo else 0,
                json.dumps({"type": assessment_type, "criteria_count": expected_count}, ensure_ascii=False),
                now_str, now_str, now_str, now_str,
                score, 1 if passed else 0,
                json.dumps(critical_fail_ids),
                missing_count,
                assessor_id, device_id, lab_id, notes
            ))

            for cid, val in observations.items():
                tx_conn.execute("""
                    INSERT INTO hardware_observations (
                        id, attempt_id, criterion_id, pass, notes, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), attempt_id, cid, val,
                    f"Quan sát bởi {assessor_id}", now_str
                ))

            # Record Assessor Signature
            tx_conn.execute("""
                INSERT INTO assessor_signatures (
                    id, attempt_id, assessor_id, attestation, server_signed_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), attempt_id, assessor_id,
                attestation or "Xác nhận quan sát trực tiếp và đánh giá đúng quy tắc",
                now_str
            ))

        return {
            "attempt_id": attempt_id,
            "learner_id": learner_id,
            "assessor_id": assessor_id,
            "type": assessment_type,
            "score": score,
            "passed": passed,
            "missing_observations": missing_count,
            "critical_fail_ids": critical_fail_ids,
            "server_signed_at": now_str
        }
    finally:
        conn.close()

def void_assessment_attempt(attempt_id: str, voided_by: str, reason: str, db_path=None) -> Dict[str, Any]:
    """Voids an assessment attempt with recorded reason."""
    if not reason or not reason.strip():
        raise ValueError("Phải có lý do hủy lượt thi (void reason).")

    with db_transaction(db_path) as conn:
        attempt = conn.execute("SELECT * FROM assessment_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt:
            raise ValueError("Không tìm thấy lượt thi.")

        conn.execute("""
            UPDATE assessment_attempts
            SET state = 'VOIDED',
                void_reason = ?,
                voided_by = ?
            WHERE id = ?
        """, (reason, voided_by, attempt_id))

        conn.execute("""
            INSERT INTO audit_events (
                id, actor_id, action, target_type, target_id, old_value, new_value, reason, server_at
            ) VALUES (?, ?, 'VOID_ATTEMPT', 'assessment_attempts', ?, ?, 'VOIDED', ?, ?)
        """, (
            str(uuid.uuid4()), voided_by, attempt_id, attempt["state"], reason, now_iso()
        ))

    return {"attempt_id": attempt_id, "status": "VOIDED", "reason": reason}

# ---------------- CANDIDATE READINESS & QUALIFICATION STATUS ----------------

def evaluate_candidate_readiness(user_id: str, db_path=None) -> Dict[str, Any]:
    """Evaluates candidate qualification status using the mutually exclusive funnel:
    NOT_STARTED -> LEARNING -> THEORY_PENDING/FAILED -> PRACTICE_PENDING ->
    SIM_PENDING/FAILED -> HARDWARE_PENDING/FAILED -> SPECIAL_PENDING/FAILED -> QUALIFIED.
    Also returns separate ROLE_AUTHORIZED status and missing conditions.
    """
    conn = get_db_connection(db_path)
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return {"status": "UNKNOWN", "missing": ["USER_NOT_FOUND"]}
        if user["is_placeholder"]:
            return {"status": "PLACEHOLDER", "missing": ["PLACEHOLDER_SLOT"]}

        profile = conn.execute("SELECT * FROM employee_profiles WHERE user_id = ?", (user_id,)).fetchone()
        op_roles = json.loads(profile["operational_roles"]) if profile and profile["operational_roles"] else []

        enrollment = conn.execute("""
            SELECT id FROM enrollments WHERE user_id = ? AND course_version = ?
        """, (user_id, COURSE_VERSION)).fetchone()

        # 1. Lessons check
        lessons_count = conn.execute("""
            SELECT COUNT(*) FROM content_records WHERE kind = 'lesson' AND course_version = ?
        """, (COURSE_VERSION,)).fetchone()[0]

        completed_lessons = 0
        started_lessons = 0
        if enrollment:
            rows = conn.execute("""
                SELECT check_passed, cards_viewed FROM lesson_progress WHERE enrollment_id = ?
            """, (enrollment["id"],)).fetchall()
            for r in rows:
                if r["check_passed"]:
                    completed_lessons += 1
                if json.loads(r["cards_viewed"]) or r["check_passed"]:
                    started_lessons += 1

        lessons_done = (completed_lessons >= lessons_count) and (lessons_count > 0)

        # 2. Theory check
        theory_attempts = conn.execute("""
            SELECT official, state, passed, submitted_at FROM assessment_attempts
            WHERE user_id = ? AND course_version = ? AND type = 'THEORY'
            ORDER BY started_at ASC
        """, (user_id, COURSE_VERSION)).fetchall()
        theory_res = calculate_current_result([dict(a) for a in theory_attempts])
        theory_done = (theory_res == 'PASS')

        # 3. Practice attendance check
        attendance_rows = conn.execute("""
            SELECT status FROM attendance WHERE user_id = ?
        """, (user_id,)).fetchall()
        attended_practice = any(a["status"] == "PRESENT" for a in attendance_rows)

        # 4. Simulation check
        sim_attempts = conn.execute("""
            SELECT official, state, passed, submitted_at FROM assessment_attempts
            WHERE user_id = ? AND course_version = ? AND type = 'SIMULATION'
            ORDER BY started_at ASC
        """, (user_id, COURSE_VERSION)).fetchall()
        sim_res = calculate_current_result([dict(a) for a in sim_attempts])
        sim_done = (sim_res == 'PASS')

        # 5. Hardware Common check
        hw_attempts = conn.execute("""
            SELECT a.official, a.state, a.passed, a.submitted_at, s.id as sig_id
            FROM assessment_attempts a
            LEFT JOIN assessor_signatures s ON s.attempt_id = a.id
            WHERE a.user_id = ? AND a.course_version = ? AND a.type = 'HARDWARE_COMMON'
            ORDER BY a.started_at ASC
        """, (user_id, COURSE_VERSION)).fetchall()
        hw_res = calculate_current_result([dict(a) for a in hw_attempts])
        hw_done = (hw_res == 'PASS')
        hw_signed = any(a["sig_id"] is not None for a in hw_attempts if a["state"] == "GRADED" and a["passed"])

        # 6. Special role check (A2, PC, CONTROLLER)
        special_needed = any(r in ("A2", "PC", "CONTROLLER") for r in op_roles)
        special_done = True
        special_missing = []

        if "A2" in op_roles or "PC" in op_roles:
            a2_attempts = conn.execute("""
                SELECT official, state, passed FROM assessment_attempts
                WHERE user_id = ? AND course_version = ? AND type = 'A2_PC'
                ORDER BY started_at ASC
            """, (user_id, COURSE_VERSION)).fetchall()
            if calculate_current_result([dict(a) for a in a2_attempts]) != 'PASS':
                special_done = False
                special_missing.append("A2_PC")

        if "CONTROLLER" in op_roles:
            ctrl_attempts = conn.execute("""
                SELECT official, state, passed FROM assessment_attempts
                WHERE user_id = ? AND course_version = ? AND type = 'CONTROLLER'
                ORDER BY started_at ASC
            """, (user_id, COURSE_VERSION)).fetchall()
            if calculate_current_result([dict(a) for a in ctrl_attempts]) != 'PASS':
                special_done = False
                special_missing.append("CONTROLLER")

        # 7. Role authorization check
        role_auths = conn.execute("""
            SELECT * FROM role_authorizations
            WHERE user_id = ? AND course_version = ? AND revoked_at IS NULL
        """, (user_id, COURSE_VERSION)).fetchall()
        is_authorized = len(role_auths) > 0

        # Construct missing conditions
        missing = []
        if not lessons_done:
            missing.append("Chưa hoàn thành 12 bài học lý thuyết")
        if not theory_done:
            missing.append("Chưa đạt bài thi lý thuyết 20 câu (hoặc đang thi)")
        if not attended_practice:
            missing.append("Chưa có điểm danh buổi thực hành có hướng dẫn")
        if not sim_done:
            missing.append("Chưa đạt bài thi mô phỏng PDA")
        if not hw_done or not hw_signed:
            missing.append("Chưa hoàn thành sát hạch PDA thật có chữ ký giám khảo")
        if not special_done:
            missing.append(f"Chưa đạt bài sát hạch vai bổ sung ({', '.join(special_missing)})")

        # Mutually exclusive funnel stage
        if completed_lessons == 0 and started_lessons == 0 and len(theory_attempts) == 0:
            stage = "NOT_STARTED"
        elif not lessons_done:
            stage = "LEARNING"
        elif not theory_done:
            stage = "THEORY_PENDING" if theory_res == 'PENDING' else "THEORY_FAILED"
        elif not attended_practice:
            stage = "PRACTICE_PENDING"
        elif not sim_done:
            stage = "SIM_PENDING" if sim_res == 'PENDING' else "SIM_FAILED"
        elif not hw_done:
            stage = "HARDWARE_PENDING" if hw_res == 'PENDING' else "HARDWARE_FAILED"
        elif not special_done:
            stage = "SPECIAL_PENDING"
        else:
            stage = "QUALIFIED"

        return {
            "user_id": user_id,
            "employee_id": user["employee_id"],
            "full_name": user["full_name"],
            "funnel_stage": stage,
            "is_qualified": (stage == "QUALIFIED"),
            "is_authorized": is_authorized,
            "missing_conditions": missing,
            "lessons": {"completed": completed_lessons, "total": lessons_count, "done": lessons_done},
            "theory": {"result": theory_res, "done": theory_done},
            "attendance": {"attended": attended_practice},
            "simulation": {"result": sim_res, "done": sim_done},
            "hardware": {"result": hw_res, "signed": hw_signed, "done": hw_done and hw_signed},
            "special": {"required": special_needed, "done": special_done, "missing": special_missing}
        }
    finally:
        conn.close()
