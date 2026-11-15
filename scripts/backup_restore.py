"""Backup and restore utility for ASV Inventory Training SQLite database."""
import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import DB_PATH, BASE_DIR

BACKUP_DIR = BASE_DIR / "backups"

def backup_database():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"asv_training_{timestamp}.db"
    
    if not DB_PATH.exists():
        print(f"Lỗi: Không tìm thấy database tại {DB_PATH}")
        return None

    # SQLite online backup API to ensure ACID consistency without locking
    src_conn = sqlite3.connect(str(DB_PATH))
    dst_conn = sqlite3.connect(str(backup_file))
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    print(f"✓ Đã sao lưu database thành công tại: {backup_file}")
    return backup_file

def restore_database(backup_file_path: str):
    p = Path(backup_file_path)
    if not p.is_file():
        print(f"Lỗi: Không tìm thấy file backup tại {backup_file_path}")
        return False

    # Verify integrity of backup file before restoring
    try:
        conn = sqlite3.connect(str(p))
        integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        conn.close()
        if integrity != "ok":
            print(f"Lỗi: File backup không toàn vẹn (integrity_check: {integrity})")
            return False
    except Exception as e:
        print(f"Lỗi kiểm tra file backup: {e}")
        return False

    # Perform restore
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, DB_PATH)
    print(f"✓ Đã khôi phục database thành công từ {p} vào {DB_PATH}")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            print("Cách dùng: python3 scripts/backup_restore.py restore <path_to_backup_file>")
        else:
            restore_database(sys.argv[2])
    else:
        backup_database()
