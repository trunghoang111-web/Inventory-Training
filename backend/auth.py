"""Authentication, password hashing, token management, and RBAC / scope checks."""
import hashlib
import hmac
import os
import time
import json
import base64
from typing import Optional, Dict, Any, List
from backend.config import JWT_SECRET
from backend.db import get_db_connection

PBKDF2_ITERATIONS = 100_000

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${dk.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_dk = bytes.fromhex(hash_hex)
        actual_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        return hmac.compare_digest(actual_dk, expected_dk)
    except Exception:
        return False

def create_access_token(user_id: str, employee_id: str, roles: List[Dict[str, Any]], expires_in: int = 86400) -> str:
    payload = {
        "user_id": user_id,
        "employee_id": employee_id,
        "roles": roles,
        "exp": int(time.time()) + expires_in
    }
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')
    sig = hmac.new(JWT_SECRET.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(JWT_SECRET.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padded_b64 = payload_b64 + "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_json = base64.urlsafe_b64decode(padded_b64).decode('utf-8')
        payload = json.loads(payload_json)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

def get_user_by_id(user_id: str, db_path=None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return None
        roles_rows = conn.execute("SELECT app_role, scope_workcell_ids FROM user_roles WHERE user_id = ?", (user_id,)).fetchall()
        roles = []
        for r in roles_rows:
            scope = json.loads(r["scope_workcell_ids"]) if r["scope_workcell_ids"] else ["ALL"]
            roles.append({"app_role": r["app_role"], "scope": scope})
        profile = conn.execute("SELECT * FROM employee_profiles WHERE user_id = ?", (user_id,)).fetchone()
        return {
            "id": user["id"],
            "employee_id": user["employee_id"],
            "full_name": user["full_name"],
            "active": bool(user["active"]),
            "is_placeholder": bool(user["is_placeholder"]),
            "roles": roles,
            "profile": dict(profile) if profile else None
        }
    finally:
        conn.close()

def user_has_role(user: Dict[str, Any], required_role: str) -> bool:
    for r in user.get("roles", []):
        if r.get("app_role") == required_role or r.get("app_role") == "SYSTEM_ADMIN":
            return True
    return False

def check_workcell_scope(user: Dict[str, Any], target_workcell_id: Optional[str]) -> bool:
    if not target_workcell_id:
        return True
    for r in user.get("roles", []):
        if r.get("app_role") in ("SYSTEM_ADMIN", "PM_VIEWER"):
            return True
        scope = r.get("scope", [])
        if "ALL" in scope or target_workcell_id in scope:
            return True
    return False

def check_anti_self_eval(actor_user_id: str, target_user_id: str):
    if actor_user_id == target_user_id:
        raise PermissionError("Không được tự chấm/tự đánh giá hoặc tự phê duyệt bản thân.")
