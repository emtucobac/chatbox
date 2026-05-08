from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.services.firebase import append_message, clear_messages, fetch_messages_raw
from app.services.uploads import save_chat_image

bp = Blueprint("chat", __name__)


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
    return jsonify({"status": "success"})


@bp.route("/messages")
def get_messages():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    raw = fetch_messages_raw()

    if not raw:
        return jsonify([])

    messages = []
    for _key, value in raw.items():
        entry = {
            "username": value.get("username"),
            "message": value.get("message") or "",
        }
        if value.get("image_url"):
            entry["image_url"] = value.get("image_url")
        messages.append(entry)
    return jsonify(messages)


@bp.route("/reset", methods=["POST"])
def reset_chat():
    if _require_user() is None:
        return jsonify({"error": "unauthorized"}), 401
    clear_messages()
    return jsonify({"status": "success"})
