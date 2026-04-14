"""
Основной сервис для работы с базой знаний (KB)
Адаптировано из ~/sql4A/ под схему knowledge_base
"""

import os
import json
import logging
import asyncpg
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

from services.embedding_service import EmbeddingService
from services.chunking_service import ChunkingService
from utils.db import get_db_pool, ensure_pgvector_extension

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env", override=True)

logger = logging.getLogger(__name__)


class KBService:
    """
    Сервис для работы с базой знаний на основе PostgreSQL + pgvector
    """
    
    def __init__(self):
        """
        Инициализация сервиса KB
        """
        self.database_url = os.getenv("DATABASE_URL")
        self.kb_table = os.getenv("KB_TABLE", "knowledge_base")
        self.embedding_service = EmbeddingService()
        self.chunking_service = ChunkingService()
        
        if not self.database_url:
            raise ValueError("DATABASE_URL не настроен в config.env")
        
        logger.info(f"✅ KBService инициализирован (table={self.kb_table})")
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
        target_audience: Optional[str] = None,
        priority: Optional[str] = None,
        settlement_id: Optional[int] = None,
        min_similarity: float = 0.6,
        use_case: Optional[str] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Семантический поиск в KB через pgvector
        
        Args:
            query: Поисковый запрос
            limit: Количество результатов
            category: Фильтр по категории
            target_audience: Фильтр по целевой аудитории
            priority: Фильтр по приоритету
            settlement_id: Фильтр по ID поселка (мультитенантность)
            min_similarity: Минимальная схожесть (0.0-1.0)
            use_case: Фильтр по сценарию использования
            stage: Фильтр по этапу воронки
            
        Returns:
            Список результатов поиска с полями: id, content, metadata, similarity
        """
        try:
            # Генерируем embedding для запроса
            query_embedding = self.embedding_service.generate_embedding(query)
            if not query_embedding:
                logger.error("Не удалось сгенерировать embedding для запроса")
                return []
            
            # Конвертируем embedding в строку для pgvector
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Подключаемся к БД
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                # Убеждаемся, что pgvector установлен
                await ensure_pgvector_extension(conn)
                
                # Формируем WHERE условия
                where_clauses = ["is_active = TRUE"]
                params = [embedding_str]
                param_idx = 2
                
                if category:
                    where_clauses.append(f"metadata->>'category' = ${param_idx}")
                    params.append(category)
                    param_idx += 1
                
                if target_audience:
                    where_clauses.append(f"metadata->>'target_audience' = ${param_idx}")
                    params.append(target_audience)
                    param_idx += 1
                
                if priority:
                    where_clauses.append(f"metadata->>'priority' = ${param_idx}")
                    params.append(priority)
                    param_idx += 1
                
                if settlement_id:
                    where_clauses.append(f"(metadata->>'settlement_id')::int = ${param_idx}")
                    params.append(settlement_id)
                    param_idx += 1
                
                if use_case:
                    where_clauses.append(f"metadata->'context'->>'use_case' = ${param_idx}")
                    params.append(use_case)
                    param_idx += 1
                
                if stage:
                    where_clauses.append(f"metadata->'context'->>'stage' = ${param_idx}")
                    params.append(stage)
                    param_idx += 1
                
                if source:
                    where_clauses.append(f"metadata->>'source' ILIKE ${param_idx}")
                    params.append(f"%{source}%")
                    param_idx += 1
                
                where_sql = " AND ".join(where_clauses)
                
                # Выполняем векторный поиск
                # Используем оператор <=> (cosine distance)
                # similarity = 1 - distance
                # ВАЖНО: используем безопасное форматирование для имени таблицы
                # LIMIT не параметризуем, так как это безопасное число
                query_sql = f"""
                    SELECT 
                        id,
                        content,
                        metadata,
                        version,
                        created_at,
                        updated_at,
                        last_updated,
                        is_active,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM {self.kb_table}
                    WHERE {where_sql}
                    ORDER BY embedding <=> $1::vector
                    LIMIT {limit}
                """
                
                # asyncpg.fetch принимает SQL и параметры отдельно
                # Первый параметр - embedding_str, остальные - фильтры
                results = await conn.fetch(query_sql, *params)
                
                # Фильтруем по min_similarity
                filtered_results = []
                for row in results:
                    similarity = float(row['similarity'])
                    if similarity >= min_similarity:
                        filtered_results.append({
                            "id": row['id'],
                            "content": row['content'],
                            "metadata": row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata']) if row['metadata'] else {},
                            "version": row['version'],
                            "similarity": similarity,
                            "created_at": row['created_at'],
                            "updated_at": row['updated_at'],
                            "last_updated": row['last_updated'],
                            "is_active": row['is_active']
                        })
                
                logger.info(f"Найдено {len(filtered_results)} результатов для запроса: {query[:50]}...")
                return filtered_results
                
        except Exception as e:
            logger.error(f"Ошибка поиска в KB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    async def add_chunk(
        self,
        content: str,
        category: str,
        target_audience: str = "both",
        priority: str = "medium",
        subcategory: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        version: str = "1.0",
        related_links: Optional[List[str]] = None,
        use_case: Optional[str] = None,
        stage: Optional[str] = None,
        settlement_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Добавляет новый chunk в KB
        
        Returns:
            ID созданного chunk
        """
        try:
            # Генерируем embedding
            embedding = self.embedding_service.generate_embedding(content)
            if not embedding:
                raise ValueError("Не удалось сгенерировать embedding")
            
            # Формируем metadata
            kb_metadata = {
                "category": category,
                "target_audience": target_audience,
                "priority": priority
            }
            
            if subcategory:
                kb_metadata["subcategory"] = subcategory
            if tags:
                kb_metadata["tags"] = tags
            if source:
                kb_metadata["source"] = source
            if related_links:
                kb_metadata["related_links"] = related_links
            if settlement_id:
                kb_metadata["settlement_id"] = settlement_id
            
            context = {}
            if use_case:
                context["use_case"] = use_case
            if stage:
                context["stage"] = stage
            if context:
                kb_metadata["context"] = context
            
            # Добавляем дополнительные metadata
            if metadata:
                kb_metadata.update(metadata)
            
            # Сохраняем в БД
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await ensure_pgvector_extension(conn)
                
                # Конвертируем embedding в строку для pgvector
                # asyncpg требует строку в формате '[0.1, 0.2, ...]'
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                chunk_id = await conn.fetchval(f"""
                    INSERT INTO {self.kb_table} (
                        content,
                        embedding,
                        metadata,
                        version
                    ) VALUES ($1, $2::vector, $3::jsonb, $4)
                    RETURNING id
                """, content, embedding_str, json.dumps(kb_metadata), version)
                
                logger.info(f"✅ Chunk добавлен в KB (id={chunk_id}, category={category})")
                return chunk_id
                
        except Exception as e:
            logger.error(f"Ошибка добавления chunk в KB: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def get_chunk(self, chunk_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает chunk по ID
        """
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(f"""
                    SELECT 
                        id, content, metadata, version,
                        created_at, updated_at, last_updated, is_active
                    FROM {self.kb_table}
                    WHERE id = $1
                """, chunk_id)
                
                if not row:
                    return None
                
                return {
                    "id": row['id'],
                    "content": row['content'],
                    "metadata": row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata']) if row['metadata'] else {},
                    "version": row['version'],
                    "created_at": row['created_at'],
                    "updated_at": row['updated_at'],
                    "last_updated": row['last_updated'],
                    "is_active": row['is_active']
                }
        except Exception as e:
            logger.error(f"Ошибка получения chunk {chunk_id}: {e}")
            return None
    
    async def update_chunk(
        self,
        chunk_id: int,
        content: Optional[str] = None,
        metadata_updates: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Обновляет chunk в KB
        
        Если обновляется content, перегенерируется embedding
        """
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                await ensure_pgvector_extension(conn)
                
                updates = []
                params = []
                param_idx = 1
                
                if content:
                    # Перегенерируем embedding
                    embedding = self.embedding_service.generate_embedding(content)
                    # Конвертируем embedding в строку для pgvector
                    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                    updates.append(f"content = ${param_idx}")
                    params.append(content)
                    param_idx += 1
                    
                    updates.append(f"embedding = ${param_idx}::vector")
                    params.append(embedding_str)
                    param_idx += 1
                
                if metadata_updates:
                    # Обновляем metadata (слияние с существующими)
                    updates.append(f"""
                        metadata = COALESCE(metadata, '{{}}'::jsonb) || ${param_idx}::jsonb
                    """)
                    params.append(json.dumps(metadata_updates))
                    param_idx += 1
                
                if is_active is not None:
                    updates.append(f"is_active = ${param_idx}")
                    params.append(is_active)
                    param_idx += 1
                
                if not updates:
                    return False
                
                updates.append(f"updated_at = NOW()")
                updates.append(f"last_updated = NOW()")
                
                params.append(chunk_id)
                
                await conn.execute(f"""
                    UPDATE {self.kb_table}
                    SET {', '.join(updates)}
                    WHERE id = ${param_idx}
                """, *params)
                
                logger.info(f"✅ Chunk {chunk_id} обновлен")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка обновления chunk {chunk_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def delete_chunk(self, chunk_id: int, soft_delete: bool = True) -> bool:
        """
        Удаляет chunk из KB
        
        Args:
            chunk_id: ID chunk для удаления
            soft_delete: Если True, помечает is_active=False, иначе физически удаляет
        """
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                if soft_delete:
                    await conn.execute(f"""
                        UPDATE {self.kb_table}
                        SET is_active = FALSE, updated_at = NOW()
                        WHERE id = $1
                    """, chunk_id)
                else:
                    await conn.execute(f"""
                        DELETE FROM {self.kb_table}
                        WHERE id = $1
                    """, chunk_id)
                
                logger.info(f"✅ Chunk {chunk_id} {'деактивирован' if soft_delete else 'удален'}")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка удаления chunk {chunk_id}: {e}")
            return False
    
    async def import_from_text(
        self,
        text: str,
        category: str,
        target_audience: str = "both",
        source: Optional[str] = None,
        chunk_size: int = 3000,
        chunk_overlap: int = 300,
        settlement_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Импортирует текст в KB с автоматическим разбиением на chunks.
        metadata (images, documents) применяется к каждому chunk для релевантного ответа агента с медиа.
        
        Returns:
            Словарь с количеством добавленных chunks
        """
        try:
            # Разбиваем текст на chunks
            chunks = self.chunking_service.chunk_text(
                text=text,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                category=category
            )
            
            added = 0
            failed = 0
            
            # Добавляем каждый chunk
            for chunk_data in chunks:
                try:
                    await self.add_chunk(
                        content=chunk_data["content"],
                        category=category,
                        target_audience=target_audience,
                        source=source,
                        settlement_id=settlement_id,
                        metadata=metadata,
                    )
                    added += 1
                except Exception as e:
                    logger.error(f"Ошибка добавления chunk: {e}")
                    failed += 1
            
            logger.info(f"✅ Импорт завершен: добавлено {added}, ошибок {failed}")
            return {
                "added": added,
                "failed": failed,
                "total_chunks": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Ошибка импорта текста: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"added": 0, "failed": 0, "total_chunks": 0}

    async def list_chunks(self, limit: int = 2000, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Список активных chunk: id и заголовок (для выбора при редактировании).
        title берётся из metadata->>'title' или начало content.
        source: если задан, фильтр по metadata->>'source' (ILIKE).
        """
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                if source:
                    source_pattern = f"%{source}%"
                    rows = await conn.fetch(f"""
                        SELECT id, content, metadata
                        FROM {self.kb_table}
                        WHERE is_active = TRUE AND metadata->>'source' ILIKE $1
                        ORDER BY id
                        LIMIT $2
                    """, source_pattern, limit)
                else:
                    rows = await conn.fetch(f"""
                        SELECT id, content, metadata
                        FROM {self.kb_table}
                        WHERE is_active = TRUE
                        ORDER BY id
                        LIMIT $1
                    """, limit)
                result = []
                for row in rows:
                    meta = row['metadata'] if isinstance(row['metadata'], dict) else json.loads(row['metadata']) if row['metadata'] else {}
                    title = (meta.get("title") or "").strip() if meta else ""
                    if not title and row['content']:
                        title = (row['content'] or "").strip()[:80]
                    if not title:
                        title = f"Chunk #{row['id']}"
                    result.append({"id": row["id"], "title": title})
                return result
        except Exception as e:
            logger.error(f"Ошибка list_chunks: {e}")
            return []

    async def list_sources(self) -> List[str]:
        """Список уникальных значений metadata->>'source' (для фильтра по источнику)."""
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(f"""
                    SELECT DISTINCT metadata->>'source' AS source
                    FROM {self.kb_table}
                    WHERE is_active = TRUE AND metadata->>'source' IS NOT NULL AND metadata->>'source' != ''
                    ORDER BY metadata->>'source'
                """)
                return [r["source"] for r in rows if r["source"]]
        except Exception as e:
            logger.error(f"Ошибка list_sources: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Получает статистику по KB
        """
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                # Общая статистика
                total = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM {self.kb_table}
                """)
                
                active = await conn.fetchval(f"""
                    SELECT COUNT(*) FROM {self.kb_table} WHERE is_active = TRUE
                """)
                
                # По категориям
                categories = await conn.fetch(f"""
                    SELECT 
                        metadata->>'category' as category,
                        COUNT(*) as count
                    FROM {self.kb_table}
                    WHERE is_active = TRUE
                    GROUP BY metadata->>'category'
                """)
                
                # По целевой аудитории
                audiences = await conn.fetch(f"""
                    SELECT 
                        metadata->>'target_audience' as audience,
                        COUNT(*) as count
                    FROM {self.kb_table}
                    WHERE is_active = TRUE
                    GROUP BY metadata->>'target_audience'
                """)
                
                # По приоритету
                priorities = await conn.fetch(f"""
                    SELECT 
                        metadata->>'priority' as priority,
                        COUNT(*) as count
                    FROM {self.kb_table}
                    WHERE is_active = TRUE
                    GROUP BY metadata->>'priority'
                """)
                
                # Последнее обновление
                last_updated = await conn.fetchval(f"""
                    SELECT MAX(last_updated) FROM {self.kb_table}
                """)
                
                return {
                    "total_chunks": total or 0,
                    "active_chunks": active or 0,
                    "chunks_by_category": {row['category']: row['count'] for row in categories if row['category']},
                    "chunks_by_target_audience": {row['audience']: row['count'] for row in audiences if row['audience']},
                    "chunks_by_priority": {row['priority']: row['count'] for row in priorities if row['priority']},
                    "last_updated": last_updated
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {
                "total_chunks": 0,
                "active_chunks": 0,
                "chunks_by_category": {},
                "chunks_by_target_audience": {},
                "chunks_by_priority": {},
                "last_updated": None
            }

