"""ASGI entry point for uvicorn: `uvicorn review_radar.api.main:app`."""

import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from review_radar.api.app import create_app

app = create_app()
