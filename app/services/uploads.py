"""Lưu ảnh đính kèm tin chat vào thư mục static/uploads."""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage

ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp"})


def uploads_dir() -> Path:
    return Path(current_app.config["UPLOAD_FOLDER"])


def save_chat_image(file_storage: FileStorage) -> str | None:
    if not file_storage or not file_storage.filename:
        return None
    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None
    max_b = int(current_app.config["MAX_UPLOAD_BYTES"])
    data = file_storage.read(max_b + 1)
    if len(data) > max_b or not data:
        return None
    out_name = f"{uuid.uuid4().hex}{ext}"
    out_path = uploads_dir() / out_name
    out_path.write_bytes(data)
    return f"/static/uploads/{out_name}"
