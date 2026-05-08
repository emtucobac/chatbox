"""Chạy dev: python app.py — production WSGI: wsgi.py."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
