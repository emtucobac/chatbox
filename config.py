"""Root configuration (env-backed defaults for Flask app)."""

import os


class Config:
    """Default app settings. Override via environment when deploying.

    Lưu ý: đừng đặt biến môi trường SERVER_NAME trên Render trừ khi giá trị
    khớp chính xác host — nếu sai, mọi route có thể trả 404.
    """

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-chatbox-secret-change-in-production",
    )

    # Trình duyệt không tách cookie theo cổng: localhost:5000 và :5001 cùng dùng một
    # cookie "session" → đăng nhập tab này ghi đè session tab kia. Thêm hậu tố PORT
    # (hoặc đặt SESSION_COOKIE_NAME khi deploy) để mỗi instance có jar riêng.
    SESSION_COOKIE_NAME = os.environ.get(
        "SESSION_COOKIE_NAME",
        f"session_p{os.environ.get('PORT', '5000')}",
    )

    FIREBASE_MESSAGES_URL = os.environ.get(
        "FIREBASE_MESSAGES_URL",
        "https://chatbox-7c6bc-default-rtdb.asia-southeast1.firebasedatabase.app/messages",
    )

    _fb_messages = FIREBASE_MESSAGES_URL.rstrip("/")
    if _fb_messages.endswith("/messages"):
        _fb_root = _fb_messages[: -len("/messages")]
    else:
        _fb_root = _fb_messages
    FIREBASE_USERS_URL = os.environ.get(
        "FIREBASE_USERS_URL",
        f"{_fb_root}/users",
    )

    FIREBASE_CHAT_ROOMS_URL = os.environ.get(
        "FIREBASE_CHAT_ROOMS_URL",
        f"{_fb_root}/chat_rooms",
    )

    # Realtime Database REST: thêm ?auth=... nếu rules không cho ghi không xác thực.
    # Dùng “database secret” (legacy) hoặc token phù hợp với rule đang bật.
    FIREBASE_RTDB_AUTH = (os.environ.get("FIREBASE_RTDB_AUTH") or "").strip()

    # Timeout HTTP tới RTDB (giây). Sidebar trang chủ dùng ngắn hơn để không chặn redirect sau login.
    FIREBASE_HTTP_TIMEOUT = float(os.environ.get("FIREBASE_HTTP_TIMEOUT", "18"))
    FIREBASE_HTTP_TIMEOUT_SIDEBAR = float(os.environ.get("FIREBASE_HTTP_TIMEOUT_SIDEBAR", "5"))

    # UPLOAD_FOLDER được gán trong create_app (đường dẫn tuyệt đối tới static/uploads).
    MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))

