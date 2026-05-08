"""WSGI entry for production servers (gunicorn, waitress, …)."""

from app import create_app

application = create_app()

