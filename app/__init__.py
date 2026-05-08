from pathlib import Path

from flask import Flask

from config import Config


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

    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.chat import bp as chat_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)

    return app
