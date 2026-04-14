"""
Pydantic модели для отчётов и аналитики
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """Типы событий аналитики"""
    PAGE_VIEW = "page_view"
    PHONE_CLICK = "phone_click"
    EMAIL_INPUT = "email_input"
    PHONE_INPUT = "phone_input"
    FORM_SUBMIT = "form_submit"
    WHATSAPP_CLICK = "whatsapp_click"
    RENOVATION_VIEW = "renovation_view"
    PLAN_VIEW = "plan_view"
    VIDEO_VIEW = "video_view"
    MORTGAGE_CALCULATE = "mortgage_calculate"


class EventSource(str, Enum):
    """Источники событий"""
    YANDEX_METRIKA = "yandex_metrika"
    SITE_INTEGRATION = "site_integration"
    AMOCRM = "amocrm"
    SALES_AGENT = "sales_agent"


class AnalyticsEventModel(BaseModel):
    """Модель события аналитики"""
    event_type: EventType
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    event_data: Dict = Field(default_factory=dict)
    source: EventSource
    timestamp: datetime = Field(default_factory=datetime.now)
    page_url: Optional[str] = None
    user_agent: Optional[str] = None


class VisitorIntentScore(BaseModel):
    """Оценка интереса посетителя"""
    visitor_id: str
    session_id: str
    score: float = Field(ge=0.0, le=1.0)
    reasons: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "visitor_id": "visitor_123",
                "session_id": "session_456",
                "score": 0.85,
                "reasons": [
                    "Просмотрел 3+ типа отделки",
                    "Кликнул по телефону",
                    "Время на сайте > 5 минут"
                ],
                "timestamp": "2025-02-07T15:30:00Z"
            }
        }


class ConversionReport(BaseModel):
    """Отчёт о конверсии"""
    period_start: datetime
    period_end: datetime
    total_visitors: int
    total_leads: int
    total_deals: int
    conversion_rate: float = Field(ge=0.0, le=1.0)
    funnel: Dict[str, int] = Field(default_factory=dict)
    channel_breakdown: Dict[str, Dict] = Field(default_factory=dict)


class DailyReport(BaseModel):
    """Ежедневный отчёт"""
    date: datetime
    visitors: int
    sessions: int
    events: int
    leads: int
    deals: int
    conversion_rate: float
    top_events: List[Dict] = Field(default_factory=list)
    top_pages: List[Dict] = Field(default_factory=list)


class WeeklyReport(BaseModel):
    """Еженедельный отчёт"""
    week_start: datetime
    week_end: datetime
    total_visitors: int
    total_sessions: int
    total_events: int
    total_leads: int
    total_deals: int
    average_conversion_rate: float
    daily_breakdown: List[DailyReport] = Field(default_factory=list)


class MonthlyReport(BaseModel):
    """Месячный отчёт"""
    month: int
    year: int
    total_visitors: int
    total_sessions: int
    total_events: int
    total_leads: int
    total_deals: int
    average_conversion_rate: float
    weekly_breakdown: List[WeeklyReport] = Field(default_factory=list)
    channel_effectiveness: Dict[str, Dict] = Field(default_factory=dict)


class RealtimeVisitor(BaseModel):
    """Модель онлайн посетителя"""
    visitor_id: str
    session_id: str
    page_url: str
    time_on_site: int  # секунды
    events_count: int
    intent_score: Optional[float] = None
    last_activity: datetime














