from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.firebase import (
    append_message,
    clear_messages,
    fetch_message,
    fetch_messages_raw,
    safe_message_id,
    set_message_reactions,
)
from app.services.uploads import save_chat_image
from app.services.typing_status import list_typing_except, set_typing

bp = Blueprint("chat", __name__)

REACTION_KEYS: tuple[str, ...] = ("like", "love", "angry")
ALLOWED_REACTIONS = frozenset(REACTION_KEYS)


def _require_user():
    if not session.get("user_id"):
        return None
    return session.get("username")


@bp.route("/")
def home():
    username = _require_user()
    if username is None:
        return redirect(url_for("auth.login"))
    return render_template("index.html", username=username)


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
    append_message(message_data)
    set_typing(chat_username, False)
    return jsonify({"status": "success"})


@bp.route("/typing", methods=["GET"])
def get_typing():
    chat_username = _require_user()
    if chat_username is None:
        return jsonify({"error": "unauthorized"}), 401
    users = list_typing_except(chat_username)
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
    set_typing(chat_username, active)
    return jsonify({"status": "success"})


@bp.route("/messages")
def get_messages():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    raw = fetch_messages_raw()

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
    clear_messages()
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

    msg = fetch_message(message_id)
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

    set_message_reactions(message_id, buckets)
    return jsonify({"status": "success", "reactions": buckets})
