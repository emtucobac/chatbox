"""Firebase Realtime REST helpers for the messages tree."""

from __future__ import annotations

from typing import Any

import requests
from flask import current_app


def _messages_json_url() -> str:
    base = str(current_app.config["FIREBASE_MESSAGES_URL"]).rstrip("/")
    return f"{base}.json"


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
