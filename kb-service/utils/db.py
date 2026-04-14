"""
Утилиты для работы с PostgreSQL + pgvector
Адаптировано из ~/sql4A/
"""

import os
import asyncpg
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Конфиг: корень проекта, затем kb-service (как в api/main.py)
_root = Path(__file__).resolve().parents[2]
_kb_dir = Path(__file__).parents[1]
load_dotenv(dotenv_path=_root / "config.env")
load_dotenv(dotenv_path=_kb_dir / "config.env", override=True)


async def get_db_pool() -> asyncpg.Pool:
    """
    Создает и возвращает пул подключений к PostgreSQL
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL не настроен в config.env")
    
    pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        command_timeout=60
    )
    return pool


async def get_db_connection() -> asyncpg.Connection:
    """
    Получить одно подключение к БД (для простых операций)
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL не настроен в config.env")
    
    conn = await asyncpg.connect(database_url)
    return conn


async def check_pgvector_extension(conn: asyncpg.Connection) -> bool:
    """
    Проверяет, установлено ли расширение pgvector
    """
    result = await conn.fetchval("""
        SELECT EXISTS(
            SELECT 1 FROM pg_extension WHERE extname = 'vector'
        )
    """)
    return result


async def ensure_pgvector_extension(conn: asyncpg.Connection):
    """
    Убеждается, что расширение pgvector установлено
    """
    if not await check_pgvector_extension(conn):
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("✅ Расширение pgvector установлено")

















