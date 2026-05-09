"""Trạng thái 'đang nhập' trong bộ nhớ tiến trình (có khóa luồng)."""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_typing: dict[tuple[str, str], float] = {}

# Sau khoảng thời gian này không nhận ping → coi như không còn gõ.
TYPING_TTL_SEC = 4.0


def set_typing(username: str, active: bool, *, channel: str) -> None:
    name = (username or "").strip()
    ch = (channel or "").strip()
    if not name or not ch:
        return
    key = (ch, name)
    with _lock:
        if active:
            _typing[key] = time.monotonic()
        else:
            _typing.pop(key, None)


def list_typing_except(exclude_username: str, *, channel: str) -> list[str]:
    exclude = (exclude_username or "").strip()
    ch_key = (channel or "").strip()
    now = time.monotonic()
    with _lock:
        stale_keys = [k for k, ts in _typing.items() if now - ts > TYPING_TTL_SEC]
        for k in stale_keys:
            _typing.pop(k, None)
        return sorted(
            u for (ch, u) in _typing if ch == ch_key and u != exclude
        )
