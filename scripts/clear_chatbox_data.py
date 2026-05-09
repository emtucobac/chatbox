"""Xóa user SQLite + nhánh RTDB users / chat_rooms / messages (chạy một lần).

Usage (từ thư mục gốc project): python scripts/clear_chatbox_data.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests

from app import create_app


def main() -> int:
    app = create_app()
    root = Path(app.instance_path)
    root.mkdir(parents=True, exist_ok=True)
    db = root / "users.sqlite"
    if db.exists():
        conn = sqlite3.connect(db)
        try:
            conn.execute("DELETE FROM users")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='users'")
            conn.commit()
        finally:
            conn.close()
        print("OK SQLite:", db, "(users + reset AUTOINCREMENT)")
    else:
        print("Không có file SQLite — bỏ qua.")

    auth = (app.config.get("FIREBASE_RTDB_AUTH") or "").strip()
    params = {"auth": auth} if auth else {}

    urls = [
        ("users", app.config["FIREBASE_USERS_URL"]),
        ("chat_rooms", app.config["FIREBASE_CHAT_ROOMS_URL"]),
        ("messages", app.config["FIREBASE_MESSAGES_URL"]),
    ]
    exit_err = 0
    for label, base in urls:
        url = str(base).rstrip("/") + ".json"
        try:
            r = requests.delete(url, params=params, timeout=45)
            if r.status_code >= 400:
                print(f"Lỗi Firebase [{label}] HTTP {r.status_code}:", (r.text or "")[:400])
                exit_err = 1
            else:
                print(f"OK Firebase [{label}] HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"Lỗi Firebase [{label}]:", e, file=sys.stderr)
            exit_err = 1
    return exit_err


if __name__ == "__main__":
    raise SystemExit(main())
