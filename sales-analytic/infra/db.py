"""
Подключение к базе данных
"""
import asyncpg
from typing import Optional
from infra.settings import settings


class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Создать пул подключений"""
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=5,
            max_size=20
        )
    
    async def disconnect(self):
        """Закрыть пул подключений"""
        if self.pool:
            await self.pool.close()
    
    async def execute(self, query: str, *args):
        """Выполнить запрос"""
        if not self.pool:
            raise RuntimeError("Database not connected")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Выполнить запрос и получить результаты"""
        if not self.pool:
            raise RuntimeError("Database not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Выполнить запрос и получить одну строку"""
        if not self.pool:
            raise RuntimeError("Database not connected")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)


db = Database()














