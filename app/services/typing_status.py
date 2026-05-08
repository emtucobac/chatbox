"""Trạng thái 'đang nhập' trong bộ nhớ tiến trình (có khóa luồng)."""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_typing: dict[str, float] = {}

# Sau khoảng thời gian này không nhận ping → coi như không còn gõ.
TYPING_TTL_SEC = 4.0


def set_typing(username: str, active: bool) -> None:
    name = (username or "").strip()
    if not name:
        return
    with _lock:
        if active:
            _typing[name] = time.monotonic()
        else:
            _typing.pop(name, None)


def list_typing_except(exclude_username: str) -> list[str]:
    exclude = (exclude_username or "").strip()
    now = time.monotonic()
    with _lock:
        stale = [u for u, ts in _typing.items() if now - ts > TYPING_TTL_SEC]
        for u in stale:
            _typing.pop(u, None)
        return sorted(u for u in _typing if u != exclude)
