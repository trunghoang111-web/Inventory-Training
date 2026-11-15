"""Start the ASV Inventory Training application server."""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import SERVER_HOST, SERVER_PORT, DB_PATH
from backend.db import init_db
from backend.seed import seed_database
from backend.server import run_server

def main():
    print("=== AJAX SYSTEMS VIETNAM · ĐÀO TẠO KIỂM KÊ 2026 ===")
    if not DB_PATH.exists():
        print(f"Khởi tạo và nạp dữ liệu chuẩn vào: {DB_PATH}")
        seed_database()
    else:
        init_db(DB_PATH)
        print(f"Cơ sở dữ liệu sẵn sàng tại: {DB_PATH}")
        
    print(f"Ứng dụng đang chạy tại: http://{SERVER_HOST}:{SERVER_PORT}/")
    print("Tài khoản quản trị bootstrap: ADMIN01 / AsvAdmin@2026")
    print("Nhấn Ctrl+C để dừng server.")
    run_server(SERVER_HOST, SERVER_PORT)

if __name__ == "__main__":
    main()
