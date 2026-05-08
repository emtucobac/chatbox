import os
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config


def _running_on_render() -> bool:
    return bool(
        os.environ.get("RENDER_EXTERNAL_URL")
        or os.environ.get("RENDER_SERVICE_ID")
        or (os.environ.get("RENDER", "").lower() in ("true", "1", "yes"))
    )


def create_app(config_class: type = Config) -> Flask:
    root = Path(__file__).resolve().parent.parent

    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)
    upload_dir = root / "static" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(upload_dir)

    from app.services.users import init_db

    init_db(app)

    @app.get("/healthz")
    def _healthz():
        return {"status": "ok"}, 200

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.chat import bp as chat_bp

    # Chat trước: route `/` thuộc chat; tránh xung đột nếu sau này thêm rule ở auth.
    app.register_blueprint(chat_bp)
    app.register_blueprint(auth_bp)

    # Render / reverse proxy: nhận đúng Host và HTTPS để redirect & cookie hoạt động.
    if os.environ.get("TRUST_PROXY", "true").lower() not in ("0", "false", "no"):
        app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_port=1,
            x_prefix=1,
        )

    if _running_on_render():
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            PREFERRED_URL_SCHEME="https",
        )

    return app
