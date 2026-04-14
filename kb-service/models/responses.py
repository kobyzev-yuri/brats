"""
Pydantic модели для ответов KB API
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class KBChunkResponse(BaseModel):
    """Модель ответа с chunk из KB"""
    id: int
    content: str
    metadata: Dict[str, Any]
    version: str
    similarity: Optional[float] = None  # Для результатов поиска
    created_at: datetime
    updated_at: datetime
    last_updated: datetime
    is_active: bool


class KBSearchResponse(BaseModel):
    """Модель ответа на поиск в KB"""
    query: str
    total_found: int
    results: List[KBChunkResponse]
    search_time_ms: float


class KBAddResponse(BaseModel):
    """Модель ответа на добавление chunk"""
    success: bool
    chunk_id: int
    message: str


class KBUpdateResponse(BaseModel):
    """Модель ответа на обновление chunk"""
    success: bool
    chunk_id: int
    message: str


class KBDeleteResponse(BaseModel):
    """Модель ответа на удаление chunk"""
    success: bool
    message: str


class KBImportResponse(BaseModel):
    """Модель ответа на импорт"""
    success: bool
    chunks_added: int
    chunks_updated: int
    chunks_failed: int
    errors: List[str]
    message: str


class KBChunkListItem(BaseModel):
    """Элемент списка chunk (id + заголовок для выбора)"""
    id: int
    title: str


class KBListResponse(BaseModel):
    """Список chunk для выбора при редактировании"""
    chunks: List[KBChunkListItem]


class KBStatsResponse(BaseModel):
    """Модель статистики KB"""
    total_chunks: int
    active_chunks: int
    chunks_by_category: Dict[str, int]
    chunks_by_target_audience: Dict[str, int]
    chunks_by_priority: Dict[str, int]
    last_updated: Optional[datetime] = None


class HealthCheckResponse(BaseModel):
    """Модель проверки здоровья сервиса"""
    status: str
    database: str
    pgvector_extension: bool
    version: str

















