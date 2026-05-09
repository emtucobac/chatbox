import secrets
from datetime import datetime, timezone
from typing import Any

import requests
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from app.services.firebase import (
    append_message,
    clear_messages,
    delete_chat_room,
    fetch_all_chat_rooms,
    fetch_chat_room,
    fetch_message,
    fetch_messages_raw,
    fetch_registered_users,
    is_generated_room_id,
    safe_message_id,
    save_chat_room,
    set_message_reactions,
)
from app.services.uploads import save_chat_image
from app.services.typing_status import list_typing_except, set_typing

bp = Blueprint("chat", __name__)

REACTION_KEYS: tuple[str, ...] = ("like", "love", "angry")
ALLOWED_REACTIONS = frozenset(REACTION_KEYS)

SESSION_CHAT_CHANNEL_KEY = "chat_channel"


def _merged_user_profiles() -> dict[int, dict[str, Any]]:
    """Danh sách người cho nhóm chat: Firebase trước, gốp thêm user chỉ có trong SQLite."""
    merged: dict[int, dict[str, Any]] = {}
    try:
        merged.update(fetch_registered_users())
    except Exception:
        current_app.logger.warning(
            "Không đọc được nhánh users trên Firebase — chỉ dùng SQLite.",
            exc_info=True,
        )
    try:
        from app.services.users import list_sqlite_users_public

        for uid, uname in list_sqlite_users_public(current_app).items():
            if uid not in merged:
                merged[uid] = {"username": uname, "id": uid}
    except Exception:
        current_app.logger.warning("Không đọc được users.sqlite để gốp danh sách.", exc_info=True)
    return merged


def _require_user():
    if not session.get("user_id"):
        return None
    return session.get("username")


def _session_user_id() -> int | None:
    uid = session.get("user_id")
    if uid is None:
        return None
    try:
        return int(uid)
    except (TypeError, ValueError):
        return None


def _member_ids_from_room(data: dict) -> list[int]:
    raw = data.get("member_ids")
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _resolve_accessible_channel(raw: object, user_id: int) -> str | None:
    ch = (raw if isinstance(raw, str) else "").strip().lower()
    if not ch:
        return None
    if is_generated_room_id(ch):
        room_to = float(current_app.config.get("FIREBASE_HTTP_TIMEOUT_SIDEBAR", 5))
        room = fetch_chat_room(ch, timeout=room_to)
        if room is not None and user_id in _member_ids_from_room(room):
            return ch
    return None


def _custom_room_rows(user_id: int) -> list[tuple[str, str, str, bool]]:
    rows: list[tuple[str, str, str, bool]] = []
    sidebar_to = float(current_app.config.get("FIREBASE_HTTP_TIMEOUT_SIDEBAR", 5))
    try:
        rooms = fetch_all_chat_rooms(timeout=sidebar_to)
    except (requests.Timeout, requests.ConnectionError):
        current_app.logger.warning("chat_rooms: timeout hoặc lỗi mạng (sidebar).")
        return rows
    except Exception:
        current_app.logger.warning("Không đọc được chat_rooms từ Firebase.", exc_info=True)
        return rows
    if not rooms:
        return rows
    keyed: list[tuple[str, str, str, bool]] = []
    for rid, data in rooms.items():
        rid_norm = str(rid).strip().lower()
        if not is_generated_room_id(rid_norm):
            continue
        if not isinstance(data, dict):
            continue
        if user_id not in _member_ids_from_room(data):
            continue
        title = (data.get("title") or "").strip()
        if not title:
            musers = data.get("member_usernames")
            if isinstance(musers, list):
                title = ", ".join(str(u) for u in musers if u)
            else:
                title = "Đoạn chat"
        created_at = str(data.get("created_at") or "")
        cb = data.get("created_by")
        can_delete = False
        try:
            if cb is not None:
                can_delete = int(cb) == user_id
        except (TypeError, ValueError):
            pass
        keyed.append((created_at, rid_norm, title, can_delete))
    keyed.sort(key=lambda x: x[0], reverse=True)
    rows = [(rid, title, "room", cd) for _, rid, title, cd in keyed]
    return rows


def _first_room_id_for_user(user_id: int) -> str | None:
    rows = _custom_room_rows(user_id)
    if not rows:
        return None
    return rows[0][0]


def _channel_rows(user_id: int) -> list[tuple[str, str, str, bool]]:
    return _custom_room_rows(user_id)


def _current_channel_id() -> str:
    user_id = _session_user_id()
    if user_id is None:
        return ""
    raw = session.get(SESSION_CHAT_CHANNEL_KEY)
    resolved = _resolve_accessible_channel(raw, user_id)
    if resolved:
        return resolved
    first = _first_room_id_for_user(user_id)
    if first:
        session[SESSION_CHAT_CHANNEL_KEY] = first
        return first
    session.pop(SESSION_CHAT_CHANNEL_KEY, None)
    return ""


def _label_for_channel(user_id: int, channel_id: str) -> str:
    ch = channel_id.strip().lower()
    if not ch:
        return ""
    for cid, lbl, _k, _d in _channel_rows(user_id):
        if cid == ch:
            return lbl
    return ch


def _kind_for_channel(user_id: int, channel_id: str) -> str:
    ch = channel_id.strip().lower()
    if not ch:
        return "none"
    for cid, _lbl, kind, _d in _channel_rows(user_id):
        if cid == ch:
            return kind
    if is_generated_room_id(ch):
        return "room"
    return "none"


@bp.route("/")
def home():
    username = _require_user()
    if username is None:
        return redirect(url_for("auth.login"))
    user_id = _session_user_id()
    if user_id is None:
        session.clear()
        return redirect(url_for("auth.login"))

    rows = _channel_rows(user_id)
    current_id = _current_channel_id()
    if not current_id:
        current_label = "Chưa có đoạn chat"
        kind = "none"
    else:
        current_label = next((lbl for cid, lbl, _k, _d in rows if cid == current_id), current_id)
        kind = next((k for cid, _lbl, k, _d in rows if cid == current_id), "room")

    return render_template(
        "index.html",
        username=username,
        chat_channels=rows,
        current_channel_id=current_id,
        current_channel_label=current_label,
        current_channel_kind=kind,
    )


@bp.route("/channels")
def list_channels_json():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    user_id = _session_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    rows = _channel_rows(user_id)
    channels = [
        {"id": cid, "label": lbl, "kind": knd, "can_delete": bool(cd)} for cid, lbl, knd, cd in rows
    ]
    return jsonify({"channels": channels})


@bp.route("/firebase-users")
def firebase_users_list():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    uid = _session_user_id()
    if uid is None:
        return jsonify({"error": "unauthorized"}), 401
    profiles = _merged_user_profiles()
    users = [
        {"id": kid, "username": str(rec.get("username") or "?")}
        for kid, rec in profiles.items()
        if kid != uid
    ]
    users.sort(key=lambda u: str(u["username"]).lower())
    return jsonify({"users": users})


@bp.route("/rooms", methods=["POST"])
def create_room():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    me = _session_user_id()
    if me is None:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    title = str(data.get("title") or "").strip()[:100]
    raw_ids = data.get("member_ids")

    others: list[int] = []
    if isinstance(raw_ids, list):
        for x in raw_ids:
            try:
                oid = int(x)
                if oid != me:
                    others.append(oid)
            except (TypeError, ValueError):
                continue
    others = list(dict.fromkeys(others))

    if len(others) < 1:
        return jsonify({"error": "need_members", "detail": "Chọn ít nhất một người."}), 400

    profiles = _merged_user_profiles()

    all_ids_sorted = sorted({me, *others})
    for oid in all_ids_sorted:
        if oid not in profiles:
            return jsonify({"error": "unknown_member", "id": oid}), 400

    labels = [str(profiles[i].get("username") or "?") for i in all_ids_sorted]
    display_title = title if title else ", ".join(labels)

    room_id = "r" + secrets.token_hex(8)

    payload = {
        "title": display_title,
        "member_ids": all_ids_sorted,
        "member_usernames": labels,
        "created_by": me,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        save_chat_room(room_id, payload)
    except requests.HTTPError as e:
        r = e.response
        status = getattr(r, "status_code", None) if r is not None else None
        body = ""
        if r is not None and getattr(r, "text", ""):
            body = str(r.text).strip()[:400]
        current_app.logger.warning("save_chat_room HTTP %s: %s", status, body[:200])
        return jsonify(
            {
                "error": "firebase_save",
                "http_status": status,
                "firebase_body": body,
            }
        ), 502
    except requests.RequestException as e:
        current_app.logger.warning("save_chat_room network: %s", e)
        return jsonify({"error": "firebase_save", "http_status": None, "detail": "network"}), 502
    except Exception:
        current_app.logger.exception("save_chat_room")
        return jsonify({"error": "firebase_save"}), 502

    session[SESSION_CHAT_CHANNEL_KEY] = room_id
    return jsonify(
        {
            "status": "success",
            "channel": room_id,
            "label": display_title,
            "kind": "room",
        }
    )


@bp.route("/rooms/eligible-members")
def room_eligible_members():
    """Thành viên nhóm xem tài khoản có thể mời: Firebase + SQLite, chưa trong nhóm."""
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    me = _session_user_id()
    if me is None:
        return jsonify({"error": "unauthorized"}), 401

    room_id = (request.args.get("room_id") or "").strip().lower()
    if not is_generated_room_id(room_id):
        return jsonify({"error": "bad_room"}), 400

    room = fetch_chat_room(room_id)
    if room is None:
        return jsonify({"error": "not_found"}), 404
    if me not in _member_ids_from_room(room):
        return jsonify({"error": "forbidden"}), 403

    existing = frozenset(_member_ids_from_room(room))
    profiles = _merged_user_profiles()
    users = [
        {"id": kid, "username": str(rec.get("username") or "?")}
        for kid, rec in profiles.items()
        if kid != me and kid not in existing
    ]
    users.sort(key=lambda u: str(u["username"]).lower())
    return jsonify({"users": users})


@bp.route("/rooms/members", methods=["POST"])
def add_room_members():
    """Thành viên hiện tại thêm người đã đăng ký (Firebase và/hoặc SQLite) vào nhóm."""
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    me = _session_user_id()
    if me is None:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    room_id = (data.get("room_id") or "").strip().lower()
    raw_ids = data.get("member_ids")

    if not is_generated_room_id(room_id):
        return jsonify({"error": "bad_room"}), 400

    room = fetch_chat_room(room_id)
    if room is None:
        return jsonify({"error": "not_found"}), 404

    members = _member_ids_from_room(room)
    if me not in members:
        return jsonify({"error": "forbidden"}), 403

    member_set = set(members)
    to_add: list[int] = []
    if isinstance(raw_ids, list):
        for x in raw_ids:
            try:
                oid = int(x)
            except (TypeError, ValueError):
                continue
            if oid == me:
                continue
            if oid in member_set:
                continue
            if oid not in to_add:
                to_add.append(oid)

    if not to_add:
        return jsonify(
            {"error": "no_new_members", "detail": "Chọn ít nhất một người chưa có trong nhóm."}
        ), 400

    profiles = _merged_user_profiles()

    for oid in to_add:
        if oid not in profiles:
            return jsonify({"error": "unknown_member", "id": oid}), 400

    merged_ids = sorted(member_set | set(to_add))
    labels = [str(profiles[i].get("username") or "?") for i in merged_ids]

    title = str(room.get("title") or "").strip()
    if not title:
        title = ", ".join(labels)
    title = title[:100]

    payload = {
        "title": title,
        "member_ids": merged_ids,
        "member_usernames": labels,
        "created_by": room.get("created_by"),
        "created_at": str(room.get("created_at") or ""),
    }

    try:
        save_chat_room(room_id, payload)
    except requests.HTTPError as e:
        r = e.response
        status = getattr(r, "status_code", None) if r is not None else None
        body = ""
        if r is not None and getattr(r, "text", ""):
            body = str(r.text).strip()[:400]
        current_app.logger.warning("save_chat_room (add members) HTTP %s: %s", status, body[:200])
        return jsonify({"error": "firebase_save", "http_status": status}), 502
    except requests.RequestException as e:
        current_app.logger.warning("save_chat_room (add members) network: %s", e)
        return jsonify({"error": "firebase_save", "detail": "network"}), 502

    display_title = str(payload["title"] or "").strip() or ", ".join(labels)
    return jsonify(
        {
            "status": "success",
            "channel": room_id,
            "label": display_title,
            "kind": "room",
        }
    )


@bp.route("/rooms/delete", methods=["POST"])
def delete_room():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    me = _session_user_id()
    if me is None:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    room_id = (data.get("room_id") or "").strip().lower()
    confirm_title = str(data.get("confirm_title") or "").strip()

    if not is_generated_room_id(room_id):
        return jsonify({"error": "bad_room"}), 400

    room = fetch_chat_room(room_id)
    if room is None:
        return jsonify({"error": "not_found"}), 404

    creator_raw = room.get("created_by")
    try:
        creator_id = int(creator_raw) if creator_raw is not None else None
    except (TypeError, ValueError):
        creator_id = None

    if creator_id != me:
        return jsonify({"error": "forbidden"}), 403

    expected = str(room.get("title") or "").strip()
    if confirm_title != expected:
        return jsonify({"error": "title_mismatch"}), 400

    try:
        clear_messages(room_id)
    except requests.HTTPError as e:
        r = e.response
        status = getattr(r, "status_code", None) if r is not None else None
        current_app.logger.warning("clear_messages HTTP %s khi xóa phòng", status)
        return jsonify({"error": "firebase_clear", "http_status": status}), 502
    except requests.RequestException as e:
        current_app.logger.warning("clear_messages network khi xóa phòng: %s", e)
        return jsonify({"error": "firebase_clear", "detail": "network"}), 502

    try:
        delete_chat_room(room_id)
    except requests.HTTPError as e:
        r = e.response
        status = getattr(r, "status_code", None) if r is not None else None
        body = ""
        if r is not None and getattr(r, "text", ""):
            body = str(r.text).strip()[:400]
        current_app.logger.warning("delete_chat_room HTTP %s: %s", status, body[:200])
        return jsonify({"error": "firebase_delete", "http_status": status}), 502
    except requests.RequestException as e:
        current_app.logger.warning("delete_chat_room network: %s", e)
        return jsonify({"error": "firebase_delete", "detail": "network"}), 502

    if session.get(SESSION_CHAT_CHANNEL_KEY) == room_id:
        session.pop(SESSION_CHAT_CHANNEL_KEY, None)

    next_room = _first_room_id_for_user(me)
    if next_room:
        session[SESSION_CHAT_CHANNEL_KEY] = next_room

    return jsonify(
        {
            "status": "success",
            "switch_to": next_room or "",
            "switch_label": _label_for_channel(me, next_room) if next_room else "",
            "switch_kind": "room" if next_room else "none",
        }
    )


@bp.route("/channel", methods=["POST"])
def set_chat_channel():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    user_id = _session_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    channel = (data.get("channel") or "").strip().lower()

    if not is_generated_room_id(channel):
        return jsonify({"error": "bad_channel"}), 400
    room = fetch_chat_room(channel)
    if room is None or user_id not in _member_ids_from_room(room):
        return jsonify({"error": "bad_channel"}), 400

    session[SESSION_CHAT_CHANNEL_KEY] = channel
    label = _label_for_channel(user_id, channel)
    kind = _kind_for_channel(user_id, channel)
    return jsonify({"status": "success", "channel": channel, "label": label, "kind": kind})


@bp.route("/send", methods=["POST"])
def send_message():
    chat_username = _require_user()
    if chat_username is None:
        return jsonify({"error": "unauthorized"}), 401

    image_url = None
    text = ""

    ct = request.content_type or ""
    if "multipart/form-data" in ct:
        text = (request.form.get("message") or "").strip()
        file = request.files.get("image")
        if file and file.filename:
            image_url = save_chat_image(file)
            if image_url is None:
                return jsonify({"error": "bad_image"}), 400
    else:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        text = (data.get("message") or "").strip()

    if not text and not image_url:
        return jsonify({"error": "empty"}), 400

    message_data: dict = {
        "username": chat_username,
        "message": text,
    }
    if image_url:
        message_data["image_url"] = image_url
    ch = _current_channel_id()
    if not ch:
        return jsonify({"error": "no_channel"}), 400
    append_message(message_data, ch)
    set_typing(chat_username, False, channel=ch)
    return jsonify({"status": "success"})


@bp.route("/typing", methods=["GET"])
def get_typing():
    chat_username = _require_user()
    if chat_username is None:
        return jsonify({"error": "unauthorized"}), 401
    users = list_typing_except(chat_username, channel=_current_channel_id())
    return jsonify({"typing": users})


@bp.route("/typing", methods=["POST"])
def post_typing():
    chat_username = _require_user()
    if chat_username is None:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    active = bool(data.get("typing"))
    set_typing(chat_username, active, channel=_current_channel_id())
    return jsonify({"status": "success"})


@bp.route("/messages")
def get_messages():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    ch = _current_channel_id()
    if not ch:
        return jsonify([])
    raw = fetch_messages_raw(ch)

    if not raw:
        return jsonify([])

    messages = []
    for msg_id, value in raw.items():
        entry = {
            "id": msg_id,
            "username": value.get("username"),
            "message": value.get("message") or "",
        }
        if value.get("image_url"):
            entry["image_url"] = value.get("image_url")
        reactions_out: dict[str, list[str]] = {k: [] for k in REACTION_KEYS}
        raw_rx = value.get("reactions")
        if isinstance(raw_rx, dict):
            for rk in REACTION_KEYS:
                lst = raw_rx.get(rk)
                if isinstance(lst, list):
                    reactions_out[rk] = [str(u) for u in lst if u is not None and str(u).strip()]
        entry["reactions"] = reactions_out
        messages.append(entry)
    return jsonify(messages)


@bp.route("/reset", methods=["POST"])
def reset_chat():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    ch = _current_channel_id()
    if not ch:
        return jsonify({"error": "no_channel"}), 400
    clear_messages(ch)
    return jsonify({"status": "success"})


def _normalize_reaction_buckets(raw_rx: object) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {k: [] for k in REACTION_KEYS}
    if not isinstance(raw_rx, dict):
        return buckets
    for rk in REACTION_KEYS:
        lst = raw_rx.get(rk)
        if isinstance(lst, list):
            buckets[rk] = [str(u) for u in lst if u is not None and str(u).strip()]
    return buckets


@bp.route("/messages/<message_id>/react", methods=["POST"])
def react_message(message_id: str):
    chat_username = _require_user()
    if chat_username is None:
        return jsonify({"error": "unauthorized"}), 401
    try:
        safe_message_id(message_id)
    except ValueError:
        return jsonify({"error": "bad_id"}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    reaction = (data.get("reaction") or "").strip().lower()
    if reaction not in ALLOWED_REACTIONS:
        return jsonify({"error": "bad_reaction"}), 400

    ch = _current_channel_id()
    if not ch:
        return jsonify({"error": "no_channel"}), 400
    msg = fetch_message(message_id, ch)
    if msg is None:
        return jsonify({"error": "not_found"}), 404

    buckets = _normalize_reaction_buckets(msg.get("reactions"))
    user = chat_username.strip()

    current: str | None = None
    for k in REACTION_KEYS:
        if user in buckets[k]:
            current = k
            break

    for k in REACTION_KEYS:
        buckets[k] = [u for u in buckets[k] if u != user]

    if reaction != current:
        buckets[reaction].append(user)

    set_message_reactions(message_id, buckets, ch)
    return jsonify({"status": "success", "reactions": buckets})
