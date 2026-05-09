"""Lưu tài khoản người dùng trong SQLite (instance/users.sqlite)."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlite3
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash


def _sync_user_firebase(app, user_id: int, username: str, created_at: str | None) -> bool:
    """Ghi /users/{id} trên Firebase (Realtime DB REST). Trả False nếu lỗi mạng/rules/auth."""
    payload = {
        "username": username,
        "id": user_id,
        "created_at": created_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        from app.services.firebase import save_registered_user

        with app.app_context():
            save_registered_user(user_id, payload)
        return True
    except Exception:
        app.logger.warning(
            "Không đồng bộ user %s (%s) lên Firebase.",
            user_id,
            username,
            exc_info=True,
        )
        return False


def _db_path(app) -> Path:
    return Path(app.instance_path) / "users.sqlite"


def init_db(app) -> None:
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    path = _db_path(app)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def list_sqlite_users_public(app) -> dict[int, str]:
    """id → username (chỉ thông tin hiển thị trong UI — không có password)."""
    path = _db_path(app)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return {
            int(row["id"]): str(row["username"])
            for row in conn.execute("SELECT id, username FROM users ORDER BY id")
        }
    finally:
        conn.close()


def create_user(app, username: str, password: str) -> tuple[int, bool]:
    """Tạo user trong SQLite; đồng bộ Firebase trong cùng request. raise ValueError nếu trùng username.

    Trả (user_id, firebase_ok). firebase_ok False khi ghi RTDB thất bại (vẫn có tài khoản local).
    """
    path = _db_path(app)
    h = generate_password_hash(password)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, h),
        )
        conn.commit()
        user_id = int(cur.lastrowid)
        crow = conn.execute("SELECT created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        created_at = str(crow[0]) if crow and crow[0] is not None else None
        firebase_ok = _sync_user_firebase(app, user_id, username, created_at)
        return user_id, firebase_ok
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise ValueError("username_taken") from e
    finally:
        conn.close()


def verify_login(app, username: str, password: str) -> dict | None:
    """Trả về {id, username} nếu đúng, ngược lại None."""
    path = _db_path(app)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None:
            return None
        if not check_password_hash(row["password_hash"], password):
            return None
        uid = int(row["id"])
        cat = row["created_at"]
        created_at = str(cat) if cat is not None else None
        _sync_user_firebase(app, uid, row["username"], created_at)
        return {"id": uid, "username": row["username"]}
    finally:
        conn.close()
