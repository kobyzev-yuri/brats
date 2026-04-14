"""
Pydantic модели для запросов к KB API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class Category(str, Enum):
    """Категории контента в KB"""
    PRODUCT_INFO = "product_info"
    SALES_SCRIPT = "sales_script"
    OBJECTION_HANDLING = "objection_handling"
    TARGET_AUDIENCE = "target_audience"
    TONE_OF_VOICE = "tone_of_voice"
    CONTACTS = "contacts"
    PRICING = "pricing"
    LOCATION = "location"


class TargetAudience(str, Enum):
    """Целевая аудитория"""
    END_BUYER = "end_buyer"
    REALTOR = "realtor"
    BOTH = "both"


class Priority(str, Enum):
    """Приоритет контента"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class KBChunkCreate(BaseModel):
    """Модель для создания нового chunk в KB"""
    content: str = Field(..., description="Текстовое содержимое chunk")
    category: Category = Field(..., description="Категория контента")
    target_audience: TargetAudience = Field(default=TargetAudience.BOTH, description="Целевая аудитория")
    priority: Priority = Field(default=Priority.MEDIUM, description="Приоритет")
    subcategory: Optional[str] = Field(None, description="Подкатегория")
    tags: Optional[List[str]] = Field(default_factory=list, description="Теги")
    source: Optional[str] = Field(None, description="Источник контента")
    version: Optional[str] = Field("1.0", description="Версия контента")
    related_links: Optional[List[str]] = Field(default_factory=list, description="Связанные ссылки")
    use_case: Optional[str] = Field(None, description="Сценарий использования (greeting, qualification, proposal, objection, closing)")
    stage: Optional[str] = Field(None, description="Этап воронки (early, middle, late)")
    settlement_id: Optional[int] = Field(None, description="ID поселка для мультитенантности")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные метаданные")


class KBChunkUpdate(BaseModel):
    """Модель для обновления chunk в KB"""
    content: Optional[str] = None
    category: Optional[Category] = None
    target_audience: Optional[TargetAudience] = None
    priority: Optional[Priority] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    version: Optional[str] = None
    related_links: Optional[List[str]] = None
    use_case: Optional[str] = None
    stage: Optional[str] = None
    settlement_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class KBSearchRequest(BaseModel):
    """Модель для поиска в KB"""
    query: str = Field(..., description="Поисковый запрос")
    limit: int = Field(default=5, ge=1, le=50, description="Количество результатов")
    category: Optional[Category] = Field(None, description="Фильтр по категории")
    target_audience: Optional[TargetAudience] = Field(None, description="Фильтр по целевой аудитории")
    priority: Optional[Priority] = Field(None, description="Фильтр по приоритету")
    settlement_id: Optional[int] = Field(None, description="Фильтр по ID поселка")
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0, description="Минимальная схожесть")
    use_case: Optional[str] = Field(None, description="Фильтр по сценарию использования")
    stage: Optional[str] = Field(None, description="Фильтр по этапу воронки")
    source: Optional[str] = Field(None, description="Фильтр по источнику (подстрока metadata.source)")


class KBImportRequest(BaseModel):
    """Модель для импорта данных в KB"""
    file_path: Optional[str] = Field(None, description="Путь к файлу для импорта")
    content: Optional[str] = Field(None, description="Содержимое для импорта (если не файл)")
    category: Category = Field(..., description="Категория для импортируемых chunks")
    target_audience: TargetAudience = Field(default=TargetAudience.BOTH)
    source: Optional[str] = Field(None, description="Источник импорта")
    chunk_size: int = Field(default=3000, ge=100, le=10000, description="Размер chunk")
    chunk_overlap: int = Field(default=300, ge=0, le=1000, description="Перекрытие chunks")
    settlement_id: Optional[int] = Field(None, description="ID поселка для мультитенантности")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Метаданные для всех chunks (images, documents — для релевантного ответа агента)")

















