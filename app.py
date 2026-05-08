"""Chạy nhanh: python app.py (cùng app với run.py / wsgi)."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
