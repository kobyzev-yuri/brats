"""
Подключение к PostgreSQL для funnel-api (viewing_slots, proposals, document_templates).
Загружает DATABASE_URL из config.env в корне репо (через load_dotenv ниже).
"""
import os
import json
from pathlib import Path
from typing import Any, List, Optional

# Корень репо = родитель funnel-api
_repo_root = Path(__file__).resolve().parent.parent
_config = _repo_root / "config.env"
if _config.exists():
    from dotenv import load_dotenv
    load_dotenv(_config, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    import psycopg2
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL не задан (config.env в корне репо)")
    return psycopg2.connect(DATABASE_URL)


# --- Рабочие часы по умолчанию (9–18) ---
SLOT_START_HOUR = int(os.getenv("VIEWING_SLOT_START_HOUR", "9"))
SLOT_END_HOUR = int(os.getenv("VIEWING_SLOT_END_HOUR", "18"))
SLOT_DURATION_MINUTES = int(os.getenv("VIEWING_SLOT_DURATION_MINUTES", "60"))
