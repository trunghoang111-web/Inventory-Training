"""Database layer: SQLite schema, connection management, transactions, and row mappings."""
import sqlite3
import json
import uuid
from typing import Optional
from pathlib import Path
from contextlib import contextmanager
from backend.config import DB_PATH, DEMO_DB_PATH

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    employee_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    is_placeholder INTEGER NOT NULL DEFAULT 0,
    auth_provider_subject TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_roles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app_role TEXT NOT NULL,
    scope_workcell_ids TEXT NOT NULL DEFAULT '["ALL"]',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, app_role)
);

CREATE TABLE IF NOT EXISTS employee_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_title TEXT NOT NULL,
    crew TEXT,
    workcell_id TEXT,
    group_name TEXT,
    operational_roles TEXT NOT NULL DEFAULT '[]',
    manager_employee_id TEXT,
    slot_id TEXT,
    effective_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    version TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    digest TEXT NOT NULL,
    published_at TEXT,
    hard_deadline_exclusive TEXT NOT NULL,
    approved_by TEXT
);

CREATE TABLE IF NOT EXISTS content_records (
    id TEXT PRIMARY KEY,
    course_version TEXT NOT NULL REFERENCES courses(version),
    content_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    public_payload TEXT NOT NULL,
    private_grading_ref TEXT,
    source_refs TEXT,
    asset_refs TEXT,
    UNIQUE(course_version, content_id, kind)
);

CREATE TABLE IF NOT EXISTS enrollments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_version TEXT NOT NULL REFERENCES courses(version),
    required INTEGER NOT NULL DEFAULT 1,
    assigned_roles TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'ENROLLED',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, course_version)
);

CREATE TABLE IF NOT EXISTS lesson_progress (
    id TEXT PRIMARY KEY,
    enrollment_id TEXT NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    lesson_id TEXT NOT NULL,
    cards_viewed TEXT NOT NULL DEFAULT '[]',
    check_attempts TEXT NOT NULL DEFAULT '[]',
    check_passed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(enrollment_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS training_sessions (
    id TEXT PRIMARY KEY,
    course_version TEXT NOT NULL REFERENCES courses(version),
    topic_vi TEXT NOT NULL,
    crew TEXT NOT NULL,
    group_name TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    capacity INTEGER,
    kind TEXT NOT NULL,
    conditional INTEGER NOT NULL DEFAULT 0,
    resources TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'planned_not_booked'
);

CREATE TABLE IF NOT EXISTS session_assignments (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    capacity_role TEXT NOT NULL,
    device_id TEXT,
    UNIQUE(session_id, user_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    confirmed_by TEXT REFERENCES users(id),
    confirmed_at TEXT,
    notes TEXT,
    UNIQUE(session_id, user_id)
);

CREATE TABLE IF NOT EXISTS assessment_attempts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    course_version TEXT NOT NULL REFERENCES courses(version),
    type TEXT NOT NULL,
    state TEXT NOT NULL,
    official INTEGER NOT NULL DEFAULT 1,
    is_demo INTEGER NOT NULL DEFAULT 0,
    policy_snapshot TEXT NOT NULL,
    content_snapshot TEXT,
    started_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    submitted_at TEXT,
    graded_at TEXT,
    score REAL,
    passed INTEGER,
    critical_fail_ids TEXT NOT NULL DEFAULT '[]',
    missing_observations INTEGER NOT NULL DEFAULT 0,
    void_reason TEXT,
    voided_by TEXT,
    assessor_id TEXT REFERENCES users(id),
    device_id TEXT,
    lab_id TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS theory_items (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    item_order INTEGER NOT NULL DEFAULT 0,
    question_id TEXT NOT NULL,
    question_snapshot TEXT NOT NULL,
    pool TEXT NOT NULL,
    critical INTEGER NOT NULL,
    selected_option_id TEXT,
    is_correct INTEGER,
    answered_at TEXT
);

CREATE TABLE IF NOT EXISTS simulation_events (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_id TEXT UNIQUE NOT NULL,
    idempotency_key TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    previous_state TEXT,
    next_state TEXT,
    server_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_case_results (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    state TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    critical_failed INTEGER NOT NULL DEFAULT 0,
    critical_terminal_event TEXT,
    submitted_at TEXT,
    UNIQUE(attempt_id, case_id)
);

CREATE TABLE IF NOT EXISTS hardware_observations (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    criterion_id TEXT NOT NULL,
    pass INTEGER,
    notes TEXT,
    observed_at TEXT,
    UNIQUE(attempt_id, criterion_id)
);

CREATE TABLE IF NOT EXISTS assessor_signatures (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    assessor_id TEXT NOT NULL REFERENCES users(id),
    attestation TEXT NOT NULL,
    server_signed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_authorizations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    course_version TEXT NOT NULL REFERENCES courses(version),
    operational_role TEXT NOT NULL,
    scope_workcell_ids TEXT NOT NULL DEFAULT '[]',
    wcm_reviewer_id TEXT REFERENCES users(id),
    wcm_reviewed_at TEXT,
    warehouse_reviewer_id TEXT REFERENCES users(id),
    warehouse_reviewed_at TEXT,
    system_access_confirmed INTEGER NOT NULL DEFAULT 0,
    valid_from TEXT NOT NULL,
    revoked_at TEXT,
    revoke_reason TEXT
);

CREATE TABLE IF NOT EXISTS remedial_actions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    failed_attempt_id TEXT NOT NULL REFERENCES assessment_attempts(id),
    lesson_ids TEXT NOT NULL DEFAULT '[]',
    critical_error_ids TEXT NOT NULL DEFAULT '[]',
    owner_id TEXT REFERENCES users(id),
    retest_session_id TEXT REFERENCES training_sessions(id),
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    actor_id TEXT,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    server_at TEXT NOT NULL
);

-- Bảng cho ứng dụng đào tạo kiểm kê rút gọn (Simple App)
CREATE TABLE IF NOT EXISTS simple_learners (
    id TEXT PRIMARY KEY,
    employee_id TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    position TEXT NOT NULL,
    custom_position TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simple_learner_history (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES simple_learners(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simple_slide_progress (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES simple_learners(id) ON DELETE CASCADE,
    course_version TEXT NOT NULL,
    slide_id TEXT NOT NULL,
    slide_order INTEGER NOT NULL,
    viewed_at TEXT NOT NULL,
    UNIQUE(learner_id, course_version, slide_id)
);

CREATE TABLE IF NOT EXISTS simple_test_attempts (
    id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL REFERENCES simple_learners(id) ON DELETE CASCADE,
    course_version TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'IN_PROGRESS',
    options_order_snapshot TEXT NOT NULL,
    answers_json TEXT NOT NULL DEFAULT '{}',
    score REAL,
    passed INTEGER,
    started_at TEXT NOT NULL,
    submitted_at TEXT
);

CREATE TABLE IF NOT EXISTS simple_app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assessment_attempts_user ON assessment_attempts(user_id, course_version, type);
CREATE INDEX IF NOT EXISTS idx_simulation_events_attempt ON simulation_events(attempt_id, case_id, seq);
CREATE INDEX IF NOT EXISTS idx_audit_events_server_at ON audit_events(server_at);
CREATE INDEX IF NOT EXISTS idx_simple_slide_progress_learner ON simple_slide_progress(learner_id, course_version);
CREATE INDEX IF NOT EXISTS idx_simple_test_attempts_learner ON simple_test_attempts(learner_id, course_version);
"""

def get_db_connection(db_path: Path = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_transaction(db_path: Path = None):
    conn = get_db_connection(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: Path = None):
    if db_path is None:
        db_path = DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_transaction(db_path) as conn:
        conn.executescript(SCHEMA_SQL)

def get_setting(key: str, default: str = None, db_path: Path = None) -> Optional[str]:
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT value FROM simple_app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    except sqlite3.OperationalError:
        return default
    finally:
        conn.close()

def set_setting(key: str, value: str, db_path: Path = None):
    from datetime import datetime, timezone, timedelta
    now_str = datetime.now(timezone(timedelta(hours=7))).isoformat()
    with db_transaction(db_path) as conn:
        conn.execute("""
            INSERT INTO simple_app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, now_str))
