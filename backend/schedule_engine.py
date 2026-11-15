"""Shift schedule engine: 4-shift calendar, session management, and conflict/constraint checking."""
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.config import BASE_DIR, COURSE_VERSION, DEADLINE_EXCLUSIVE, now_iso
from backend.db import get_db_connection, db_transaction

def load_shift_calendar() -> Dict[str, Dict[str, str]]:
    cal_file = BASE_DIR / "data" / "shift_calendar.json"
    if not cal_file.exists():
        return {}
    data = json.loads(cal_file.read_text(encoding="utf-8"))
    return {d["date"]: d["crews"] for d in data.get("days", [])}

def check_session_conflicts(
    session_id: str,
    user_ids: List[str],
    assessor_ids: List[str] = None,
    device_ids: List[str] = None,
    db_path=None
) -> List[Dict[str, Any]]:
    """Detects schedule conflicts for persons, assessors, and devices."""
    conflicts = []
    conn = get_db_connection(db_path)
    try:
        current_session = conn.execute("SELECT * FROM training_sessions WHERE id = ?", (session_id,)).fetchone()
        if not current_session:
            return [{"type": "SESSION_NOT_FOUND", "message": f"Không tìm thấy buổi {session_id}"}]

        s_start = datetime.fromisoformat(current_session["start_at"])
        s_end = datetime.fromisoformat(current_session["end_at"])

        # Check deadline
        if s_end >= DEADLINE_EXCLUSIVE:
            conflicts.append({
                "type": "DEADLINE_BREACH",
                "severity": "CRITICAL",
                "message": f"Buổi {session_id} kết thúc lúc {s_end.isoformat()} vượt quá hạn chót 01/12/2026."
            })

        # Check shift calendar alignment
        shift_cal = load_shift_calendar()
        date_str = current_session["start_at"][:10]
        crew = current_session["crew"]
        if crew in ("A", "B", "C", "D") and date_str in shift_cal:
            crew_status = shift_cal[date_str].get(crew)
            if crew_status == "OFF":
                conflicts.append({
                    "type": "REST_SHIFT_WARNING",
                    "severity": "WARNING",
                    "message": f"Kíp {crew} đang trong ca nghỉ (OFF) ngày {date_str}."
                })

        # Check night shift crossing midnight
        if s_start.date() != s_end.date():
            conflicts.append({
                "type": "OVERNIGHT_SHIFT",
                "severity": "INFO",
                "message": f"Buổi học ca đêm qua 0 giờ ({s_start.strftime('%d/%m %H:%M')} đến {s_end.strftime('%d/%m %H:%M')})."
            })

        # Check capacity
        cap = current_session["capacity"]
        existing_assignees = conn.execute(
            "SELECT user_id FROM session_assignments WHERE session_id = ? AND capacity_role = 'LEARNER'",
            (session_id,)
        ).fetchall()
        total_learners = len(set([r["user_id"] for r in existing_assignees] + user_ids))
        if cap and total_learners > cap:
            conflicts.append({
                "type": "CAPACITY_EXCEEDED",
                "severity": "ERROR",
                "message": f"Vượt quá sức chứa ({total_learners}/{cap} người học)."
            })

        # Check overlapping sessions for all persons
        all_check_users = set(user_ids + (assessor_ids or []))
        for uid in all_check_users:
            overlaps = conn.execute("""
                SELECT s.id, s.start_at, s.end_at, a.capacity_role, u.full_name, u.employee_id
                FROM session_assignments a
                JOIN training_sessions s ON s.id = a.session_id
                JOIN users u ON u.id = a.user_id
                WHERE a.user_id = ? AND a.session_id != ?
            """, (uid, session_id)).fetchall()

            for o in overlaps:
                o_start = datetime.fromisoformat(o["start_at"])
                o_end = datetime.fromisoformat(o["end_at"])
                # Overlap test: max(s_start, o_start) < min(s_end, o_end)
                if max(s_start, o_start) < min(s_end, o_end):
                    conflicts.append({
                        "type": "PERSON_DOUBLE_BOOKING",
                        "severity": "ERROR",
                        "user_id": uid,
                        "employee_id": o["employee_id"],
                        "name": o["full_name"],
                        "conflicting_session_id": o["id"],
                        "message": f"Nhân viên {o['full_name']} ({o['employee_id']}) bị trùng giờ với buổi {o['id']} ({o['start_at']}–{o['end_at']})."
                    })

        # Check device conflicts
        if device_ids:
            for dev in device_ids:
                dev_overlaps = conn.execute("""
                    SELECT s.id, s.start_at, s.end_at, a.device_id
                    FROM session_assignments a
                    JOIN training_sessions s ON s.id = a.session_id
                    WHERE a.device_id = ? AND a.session_id != ?
                """, (dev, session_id)).fetchall()

                for d in dev_overlaps:
                    d_start = datetime.fromisoformat(d["start_at"])
                    d_end = datetime.fromisoformat(d["end_at"])
                    if max(s_start, d_start) < min(s_end, d_end):
                        conflicts.append({
                            "type": "DEVICE_DOUBLE_BOOKING",
                            "severity": "ERROR",
                            "device_id": dev,
                            "conflicting_session_id": d["id"],
                            "message": f"Thiết bị PDA {dev} bị trùng với buổi {d['id']}."
                        })

        return conflicts
    finally:
        conn.close()

def assign_users_to_session(session_id: str, assignments: List[Dict[str, Any]], db_path=None) -> Dict[str, Any]:
    """Assigns users to session with validation."""
    uids = [a["user_id"] for a in assignments if a.get("capacity_role") == "LEARNER"]
    aids = [a["user_id"] for a in assignments if a.get("capacity_role") == "ASSESSOR"]
    devs = [a["device_id"] for a in assignments if a.get("device_id")]

    conflicts = check_session_conflicts(session_id, uids, aids, devs, db_path=db_path)
    errors = [c for c in conflicts if c.get("severity") in ("CRITICAL", "ERROR")]
    if errors:
        return {"success": False, "conflicts": conflicts}

    with db_transaction(db_path) as conn:
        for a in assignments:
            conn.execute("""
                INSERT INTO session_assignments (id, session_id, user_id, capacity_role, device_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id, user_id) DO UPDATE SET
                    capacity_role = excluded.capacity_role,
                    device_id = excluded.device_id
            """, (
                str(uuid.uuid4()), session_id, a["user_id"], a["capacity_role"], a.get("device_id")
            ))

    return {"success": True, "conflicts": conflicts}
