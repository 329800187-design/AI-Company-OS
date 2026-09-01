"""AI Company OS supported application entry point.

The supported runtime is assembled in :mod:`backend.core_app`.  This module
keeps the stable ``backend.app:app`` import path used by Uvicorn, Docker, and
the desktop launcher.
"""

from backend.core_app import app

__all__ = ["app"]
