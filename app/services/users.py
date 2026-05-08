"""Lưu tài khoản người dùng trong SQLite (instance/users.sqlite)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash


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


def create_user(app, username: str, password: str) -> int:
    """Tạo user; raise ValueError nếu trùng username."""
    path = _db_path(app)
    h = generate_password_hash(password)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, h),
        )
        conn.commit()
        return int(cur.lastrowid)
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
            "SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if row is None:
            return None
        if not check_password_hash(row["password_hash"], password):
            return None
        return {"id": int(row["id"]), "username": row["username"]}
    finally:
        conn.close()
