"""Deployment entrypoint for CareOS FastAPI."""

from backend.app.main import app

__all__ = ["app"]
