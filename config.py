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

    FIREBASE_MESSAGES_URL = os.environ.get(
        "FIREBASE_MESSAGES_URL",
        "https://chatbox-7c6bc-default-rtdb.asia-southeast1.firebasedatabase.app/messages",
    )

    # UPLOAD_FOLDER được gán trong create_app (đường dẫn tuyệt đối tới static/uploads).
    MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))

