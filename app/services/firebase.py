"""Firebase Realtime REST helpers for the messages tree."""

from __future__ import annotations

import re
from typing import Any

import requests
from flask import current_app

_MESSAGE_ID_RE = re.compile(r"^-?[A-Za-z0-9_-]+$")


def _messages_base_url() -> str:
    return str(current_app.config["FIREBASE_MESSAGES_URL"]).rstrip("/")


def _messages_json_url() -> str:
    return f"{_messages_base_url()}.json"


def safe_message_id(message_id: str) -> str:
    if not message_id or not isinstance(message_id, str):
        raise ValueError("invalid message id")
    sid = message_id.strip()
    if not _MESSAGE_ID_RE.match(sid):
        raise ValueError("invalid message id")
    return sid


def _message_json_url(message_id: str) -> str:
    return f"{_messages_base_url()}/{safe_message_id(message_id)}.json"


def _message_reactions_json_url(message_id: str) -> str:
    return f"{_messages_base_url()}/{safe_message_id(message_id)}/reactions.json"


def fetch_messages_raw() -> dict[str, Any] | None:
    response = requests.get(_messages_json_url(), timeout=15)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None


def append_message(payload: dict[str, Any]) -> None:
    response = requests.post(_messages_json_url(), json=payload, timeout=15)
    response.raise_for_status()


def clear_messages() -> None:
    response = requests.delete(_messages_json_url(), timeout=15)
    response.raise_for_status()


def fetch_message(message_id: str) -> dict[str, Any] | None:
    response = requests.get(_message_json_url(message_id), timeout=15)
    response.raise_for_status()
    data = response.json()
    if data is None:
        return None
    return data if isinstance(data, dict) else None


def set_message_reactions(message_id: str, reactions: dict[str, list[str]]) -> None:
    response = requests.put(_message_reactions_json_url(message_id), json=reactions, timeout=15)
    response.raise_for_status()
