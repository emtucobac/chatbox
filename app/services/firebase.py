"""Firebase Realtime REST helpers for the messages tree."""

from __future__ import annotations

import re
from typing import Any

import requests
from flask import current_app

_MESSAGE_ID_RE = re.compile(r"^-?[A-Za-z0-9_-]+$")
_CHANNEL_SEGMENT_RE = re.compile(r"^[a-z0-9_-]+$")
_ROOM_ID_RE = re.compile(r"^r[a-f0-9]{16}$")

# Tái dùng kết nối TCP/TLS tới cùng host RTDB → lần sau nhanh hơn (polling / nhiều request).
_http_session = requests.Session()


def _req_timeout(override: float | None = None) -> float:
    if override is not None:
        return override
    try:
        return float(current_app.config.get("FIREBASE_HTTP_TIMEOUT", 18))
    except RuntimeError:
        return 18.0


def _messages_base_url() -> str:
    return str(current_app.config["FIREBASE_MESSAGES_URL"]).rstrip("/")


def _users_base_url() -> str:
    return str(current_app.config["FIREBASE_USERS_URL"]).rstrip("/")


def _chat_rooms_base_url() -> str:
    return str(current_app.config["FIREBASE_CHAT_ROOMS_URL"]).rstrip("/")


def _user_record_json_url(user_id: int) -> str:
    return f"{_users_base_url()}/{int(user_id)}.json"


def _rtdb_query_params() -> dict[str, str]:
    auth = (current_app.config.get("FIREBASE_RTDB_AUTH") or "").strip()
    return {"auth": auth} if auth else {}


def safe_message_id(message_id: str) -> str:
    if not message_id or not isinstance(message_id, str):
        raise ValueError("invalid message id")
    sid = message_id.strip()
    if not _MESSAGE_ID_RE.match(sid):
        raise ValueError("invalid message id")
    return sid


def safe_channel_segment(channel: str) -> str:
    c = (channel or "").strip().lower()
    if not c:
        raise ValueError("invalid channel")
    if _CHANNEL_SEGMENT_RE.match(c) or _ROOM_ID_RE.match(c):
        return c
    raise ValueError("invalid channel")


def is_generated_room_id(channel: str) -> bool:
    c = (channel or "").strip().lower()
    return bool(_ROOM_ID_RE.match(c))


def _chat_room_record_json_url(room_id: str) -> str:
    rid = (room_id or "").strip().lower()
    if not _ROOM_ID_RE.match(rid):
        raise ValueError("invalid room id")
    return f"{_chat_rooms_base_url()}/{rid}.json"


def fetch_registered_users() -> dict[int, dict[str, Any]]:
    """users/{numeric_id}.json — chỉ chứa username, id... (đã đồng bộ khi đăng ký)."""
    response = _http_session.get(
        f"{_users_base_url()}.json",
        params=_rtdb_query_params(),
        timeout=_req_timeout(None),
    )
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, dict):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for k, v in raw.items():
        if not str(k).isdigit() or not isinstance(v, dict):
            continue
        out[int(k)] = v
    return out


def fetch_all_chat_rooms(*, timeout: float | None = None) -> dict[str, Any] | None:
    """timeout ngắn nên dùng cho sidebar (không chặn trang chủ)."""
    response = _http_session.get(
        f"{_chat_rooms_base_url()}.json",
        params=_rtdb_query_params(),
        timeout=_req_timeout(timeout),
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def fetch_chat_room(room_id: str, *, timeout: float | None = None) -> dict[str, Any] | None:
    rid = (room_id or "").strip().lower()
    if not _ROOM_ID_RE.match(rid):
        return None
    response = _http_session.get(
        f"{_chat_rooms_base_url()}/{rid}.json",
        params=_rtdb_query_params(),
        timeout=_req_timeout(timeout),
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def save_chat_room(room_id: str, payload: dict[str, Any]) -> None:
    response = _http_session.put(
        _chat_room_record_json_url(room_id),
        json=payload,
        params=_rtdb_query_params(),
        timeout=_req_timeout(None),
    )
    response.raise_for_status()


def delete_chat_room(room_id: str) -> None:
    response = _http_session.delete(
        _chat_room_record_json_url(room_id),
        params=_rtdb_query_params(),
        timeout=_req_timeout(None),
    )
    response.raise_for_status()


def _messages_branch_url(channel: str) -> str:
    return f"{_messages_base_url()}/{safe_channel_segment(channel)}"


def _messages_json_url(channel: str) -> str:
    return f"{_messages_branch_url(channel)}.json"


def _message_json_url(message_id: str, channel: str) -> str:
    return f"{_messages_branch_url(channel)}/{safe_message_id(message_id)}.json"


def _message_reactions_json_url(message_id: str, channel: str) -> str:
    return f"{_messages_branch_url(channel)}/{safe_message_id(message_id)}/reactions.json"


def save_registered_user(user_id: int, payload: dict[str, Any]) -> None:
    """Ghi / cập nhật user đăng ký tại users/{user_id}. Không chứa mật khẩu."""
    response = _http_session.put(
        _user_record_json_url(user_id),
        json=payload,
        params=_rtdb_query_params(),
        timeout=_req_timeout(None),
    )
    response.raise_for_status()


def fetch_messages_raw(channel: str) -> dict[str, Any] | None:
    response = _http_session.get(_messages_json_url(channel), timeout=_req_timeout(None))
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def append_message(payload: dict[str, Any], channel: str) -> None:
    response = _http_session.post(_messages_json_url(channel), json=payload, timeout=_req_timeout(None))
    response.raise_for_status()


def clear_messages(channel: str) -> None:
    response = _http_session.delete(_messages_json_url(channel), timeout=_req_timeout(None))
    response.raise_for_status()


def fetch_message(message_id: str, channel: str) -> dict[str, Any] | None:
    response = _http_session.get(_message_json_url(message_id, channel), timeout=_req_timeout(None))
    response.raise_for_status()
    data = response.json()
    if data is None:
        return None
    return data if isinstance(data, dict) else None


def set_message_reactions(message_id: str, reactions: dict[str, list[str]], channel: str) -> None:
    response = _http_session.put(
        _message_reactions_json_url(message_id, channel), json=reactions, timeout=_req_timeout(None)
    )
    response.raise_for_status()
