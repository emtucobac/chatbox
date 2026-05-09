from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.services.users import create_user, verify_login

bp = Blueprint("auth", __name__)

_USERNAME_MIN = 3
_USERNAME_MAX = 40
_PASSWORD_MIN = 6


def _validate_username(raw: str) -> str | None:
    u = raw.strip()
    if len(u) < _USERNAME_MIN or len(u) > _USERNAME_MAX:
        return None
    if any(c.isspace() for c in u):
        return None
    return u


@bp.route("/login", methods=["GET", "POST"], strict_slashes=False)
def login():
    if session.get("user_id"):
        return redirect(url_for("chat.home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = verify_login(current_app, username, password)
        if user:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("chat.home"))
        flash("Sai tên đăng nhập hoặc mật khẩu.", "error")
    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"], strict_slashes=False)
def register():
    if session.get("user_id"):
        return redirect(url_for("chat.home"))
    if request.method == "POST":
        username = _validate_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if username is None:
            flash(
                f"Tên đăng nhập {_USERNAME_MIN}-{_USERNAME_MAX} ký tự, không chứa khoảng trắng.",
                "error",
            )
        elif len(password) < _PASSWORD_MIN:
            flash(f"Mật khẩu ít nhất {_PASSWORD_MIN} ký tự.", "error")
        elif password != confirm:
            flash("Mật khẩu xác nhận không khớp.", "error")
        else:
            try:
                _, firebase_ok = create_user(current_app, username, password)
                flash("Đăng ký thành công. Hãy đăng nhập.", "success")
                if not firebase_ok:
                    flash(
                        "Không ghi được hồ sơ lên Firebase — chức năng nhóm / «Thêm người» sẽ không thấy tài khoản này. Kiểm tra FIREBASE_USERS_URL và FIREBASE_RTDB_AUTH (hoặc Rules). Sau khi sửa, đăng nhập một lần để thử đồng bộ lại.",
                        "warning",
                    )
                return redirect(url_for("auth.login"))
            except ValueError:
                flash("Tên đăng nhập này đã được dùng.", "error")
    return render_template("register.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
