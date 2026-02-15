from __future__ import annotations

import os
from pathlib import Path

from bafa_agent.config import load_project_config


def project_root() -> Path:
    root = Path(os.getenv("BAFA_BASE_DIR", ".")).resolve()
    load_project_config(root)
    return root


def database_url() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite:///./bafa_webapp.db")
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg2://", 1)
    return raw


def redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://localhost:6379/0")
