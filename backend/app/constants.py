"""Centralised constants for the backend application."""

import os

API_VERSION = "0.1.0"

FRONTEND_CORS_ORIGIN = os.environ.get("FRONTEND_CORS_ORIGIN", "http://localhost:5173")
