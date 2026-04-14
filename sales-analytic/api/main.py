"""
FastAPI приложение для сервиса аналитики
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import os
import sys
import json
import httpx

# Настройка sys.path для запуска из директории `sales-analytic`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PACKAGE_ROOT not in sys.path:
    sys.path.append(PACKAGE_ROOT)

from integrations.metrika_client import YandexMetrikaClient
from infra.db import db
from domain.services import AnalyticsService
from domain.services import AnalyticsService


app = FastAPI(
    title="Sales Analytic Service",
    description="Сервис нейроаналитики для анализа поведения пользователей",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    """Подключаемся к БД при старте сервиса."""
    await db.connect()


@app.on_event("shutdown")
async def on_shutdown():
    """Отключаемся от БД при остановке сервиса."""
    await db.disconnect()


# Pydantic модели
class AnalyticsEvent(BaseModel):
    """Модель события аналитики"""
    event_type: str
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    event_data: dict
    source: str
    timestamp: Optional[datetime] = None


class RealtimeVisitor(BaseModel):
    """Модель онлайн посетителя"""
    visitor_id: str
    session_id: str
    page_url: str
    time_on_site: int
    events_count: int


class IntentScore(BaseModel):
    """Модель оценки интереса посетителя"""
    visitor_id: str
    session_id: str
    score: float
    reasons: List[str]
    timestamp: datetime


# Вспомогательные функции

def get_metrika_client() -> YandexMetrikaClient:
    """
    Фабрика клиента Яндекс.Метрики.

    Сейчас использует значения из config.env:
    - YANDEX_METRIKA_COUNTER_ID
    - YANDEX_METRIKA_OAUTH_TOKEN

    Клиент уже реализован в `integrations/metrika_client.py`.
    """
    return YandexMetrikaClient()


def get_analytics_service() -> AnalyticsService:
    """
    Фабрика сервиса аналитики.
    Использует пул подключений infra.db.db.
    """
    if db.pool is None:
        raise RuntimeError("Database pool is not initialized")
    return AnalyticsService(db.pool)


def get_analytics_service() -> AnalyticsService:
    """
    Фабрика сервиса аналитики.
    Использует пул подключений infra.db.db.
    """
    if db.pool is None:
        raise RuntimeError("Database pool is not initialized")
    return AnalyticsService(db.pool)


# Endpoints

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "service": "Sales Analytic Service",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/api/analytics/realtime")
async def get_realtime_visitors(days: int = 1):
    """
    Упрощённый "realtime" endpoint:
    возвращает агрегированные метрики за последние `days` дней
    по данным Яндекс.Метрики.
    """
    if days <= 0:
        raise HTTPException(status_code=400, detail="days must be >= 1")

    client = get_metrika_client()

    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=days - 1)

    metrics = ["ym:s:visits", "ym:s:pageviews", "ym:s:users"]

    try:
        data = await client.get_conversions(
            date_from=date_from.strftime("%Y-%m-%d"),
            date_to=date_to.strftime("%Y-%m-%d"),
            metrics=metrics,
        )

        totals = data.get("totals", [0, 0, 0])
        visits, pageviews, users = totals[:3]

        return {
            "period": {
                "from": date_from.strftime("%Y-%m-%d"),
                "to": date_to.strftime("%Y-%m-%d"),
            },
            "metrics": {
                "visits": int(visits),
                "pageviews": int(pageviews),
                "users": int(users),
            },
            "raw": data,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error from Yandex.Metrika API: {e}")


@app.get("/api/analytics/visitor/{visitor_id}")
async def get_visitor_data(visitor_id: str):
    """
    Получение данных о конкретном посетителе
    
    TODO: Реализовать получение данных из БД
    """
    # TODO: Реализация
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/api/analytics/events")
async def create_event(event: AnalyticsEvent):
    """
    Создание события аналитики
    
    TODO: Реализовать сохранение события в БД
    """
    # TODO: Реализация
    return {"status": "created", "event_id": "temp_id"}


@app.post("/api/analytics/collect")
async def collect_analytics_event(event: AnalyticsEvent):
    """
    Принимает сырое событие с сайта и сохраняет его в analytics_events.

    Это наш внутренний "самодельный счётчик".
    Параллельно может работать счётчик Яндекс.Метрики — они не мешают друг другу:
    один шлёт данные в Яндекс, второй — в нашу БД.
    """
    # Собираем event_data с базовыми полями
    base_data = dict(event.event_data or {})
    base_data.update({
        "visitor_id": event.visitor_id,
        "session_id": event.session_id,
        "timestamp": (event.timestamp or datetime.now()).isoformat(),
    })

    row = await db.fetchrow(
        """
        INSERT INTO analytics_events (amocrm_lead_id, event_type, event_data, source, settlement_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, created_at
        """,
        None,  # amocrm_lead_id пока не знаем
        event.event_type,
        json.dumps(base_data),  # храним как JSON-строку (подходит и для jsonb, и для text)
        "site_integration",  # источник: наш внутренний счётчик с сайта
        None,  # settlement_id можно добавить позже, когда появятся реальные данные
    )

    return {
        "status": "ok",
        "event_id": row["id"],
        "created_at": row["created_at"].isoformat(),
    }


@app.get("/api/analytics/events")
async def get_events(
    visitor_id: Optional[str] = None,
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 100
):
    """
    Получение событий с фильтрацией

    Использует таблицу analytics_events.
    Удобно для отладки собственного счётчика (`source='site_integration'`).
    """
    if limit <= 0 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")

    conditions = []
    params = []

    if visitor_id:
        conditions.append("event_data->>'visitor_id' = $%d" % (len(params) + 1))
        params.append(visitor_id)
    if session_id:
        conditions.append("event_data->>'session_id' = $%d" % (len(params) + 1))
        params.append(session_id)
    if event_type:
        conditions.append("event_type = $%d" % (len(params) + 1))
        params.append(event_type)
    if source:
        conditions.append("source = $%d" % (len(params) + 1))
        params.append(source)
    if date_from:
        conditions.append("created_at >= $%d" % (len(params) + 1))
        params.append(date_from)
    if date_to:
        conditions.append("created_at <= $%d" % (len(params) + 1))
        params.append(date_to)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            id,
            event_type,
            source,
            created_at,
            event_data
        FROM analytics_events
        {where_clause}
        ORDER BY created_at DESC
        LIMIT {limit}
    """

    rows = await db.fetch(query, *params)
    events = [
        {
            "id": r["id"],
            "event_type": r["event_type"],
            "source": r["source"],
            "created_at": r["created_at"].isoformat(),
            "event_data": r["event_data"],
        }
        for r in rows
    ]

    return {"events": events, "count": len(events)}


@app.post("/api/analytics/trigger")
async def trigger_sales_agent(
    visitor_id: str,
    session_id: str,
    threshold: float = 0.7,
):
    """
    Триггер для инициации нейропродажника на основе аналитики.

    Сейчас:
    - считает intent_score по событиям собственного счётчика (analytics_events)
    - возвращает, является ли лид "горячим"

    В будущем здесь можно добавить:
    - вызов n8n webhook
    - создание лида в amoCRM
    - обращение к сервису sales-agent
    """
    try:
        service = get_analytics_service()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    intent = await service.calculate_intent_score(visitor_id, session_id)
    is_hot = intent.score >= threshold

    sales_agent_called = False
    sales_agent_error: str | None = None
    conversation_id = None

    # Минимальное подключение нейропродажника:
    # если лид "горячий", пробуем дернуть endpoint sales-agent.
    if is_hot:
        sales_agent_base = os.getenv("SALES_AGENT_URL")
        if sales_agent_base:
            sales_agent_endpoint = sales_agent_base.rstrip("/") + "/api/chat/initiate"

            # Пробуем вытащить контактные данные и контекст объекта из событий
            last_event = await db.fetchrow(
                """
                SELECT event_type, event_data
                FROM analytics_events
                WHERE event_data->>'visitor_id' = $1
                  AND event_data->>'session_id' = $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                visitor_id,
                session_id,
            )
            place_interest_event = await db.fetchrow(
                """
                SELECT event_data
                FROM analytics_events
                WHERE event_data->>'visitor_id' = $1
                  AND event_data->>'session_id' = $2
                  AND event_type = 'place_interest'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                visitor_id,
                session_id,
            )
            card_view_event = await db.fetchrow(
                """
                SELECT event_data
                FROM analytics_events
                WHERE event_data->>'visitor_id' = $1
                  AND event_data->>'session_id' = $2
                  AND event_type = 'card_view_duration'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                visitor_id,
                session_id,
            )

            contact_email = None
            contact_phone = None
            page_url = None
            form_type = None
            place_context = None
            card_view_context = None

            def _parse_event_data(raw):
                if isinstance(raw, str):
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return {}
                return raw or {}

            if last_event:
                data = _parse_event_data(last_event["event_data"])
                contact_email = data.get("email")
                contact_phone = data.get("phone")
                page_url = data.get("page_url")
                form_type = data.get("form_type")

            if place_interest_event:
                data = _parse_event_data(place_interest_event["event_data"])
                place_context = {
                    "place_id": data.get("place_id"),
                    "place_name": data.get("place_name"),
                    "settlement": data.get("settlement"),
                    "price": data.get("price"),
                    "area": data.get("area"),
                }

            if card_view_event:
                data = _parse_event_data(card_view_event["event_data"])
                card_view_context = {
                    "place_id": data.get("place_id"),
                    "place_name": data.get("place_name"),
                    "object_name": data.get("object_name"),
                    "duration_seconds": data.get("duration_seconds"),
                    "renovation_type": data.get("renovation_type"),
                }

            payload = {
                "external_id": f"{visitor_id}:{session_id}",
                "channel": "site",
                "contact": {
                    "phone": contact_phone,
                    "email": contact_email,
                },
                "context": {
                    "page_url": page_url,
                    "form_type": form_type,
                    "intent_score": intent.score,
                    "reasons": intent.reasons,
                    "place_interest": place_context,
                    "card_view_duration": card_view_context,
                },
            }

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(sales_agent_endpoint, json=payload)
                if resp.status_code < 300:
                    sales_agent_called = True
                    try:
                        body = resp.json()
                        conversation_id = body.get("conversation_id")
                    except Exception:
                        conversation_id = None
                else:
                    sales_agent_error = f"{resp.status_code} {resp.text[:200]}"
            except Exception as e:
                sales_agent_error = str(e)
        else:
            sales_agent_error = "SALES_AGENT_URL not set in environment"

    return {
        "triggered": is_hot,
        "visitor_id": visitor_id,
        "session_id": session_id,
        "threshold": threshold,
        "intent_score": intent.score,
        "reasons": intent.reasons,
        "sales_agent_called": sales_agent_called,
        "sales_agent_error": sales_agent_error,
        "conversation_id": conversation_id,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/analytics/reports/daily")
async def get_daily_report(date: Optional[datetime] = None):
    """
    Получение ежедневного отчёта
    
    TODO: Реализовать генерацию отчёта
    """
    # TODO: Реализация
    return {"report": {}, "date": date or datetime.now().date().isoformat()}


@app.get("/api/analytics/reports/weekly")
async def get_weekly_report(week_start: Optional[datetime] = None):
    """
    Получение еженедельного отчёта
    
    TODO: Реализовать генерацию отчёта
    """
    # TODO: Реализация
    return {"report": {}, "week_start": week_start or (datetime.now() - timedelta(days=7)).isoformat()}


@app.get("/api/analytics/reports/monthly")
async def get_monthly_report(month: Optional[int] = None, year: Optional[int] = None):
    """
    Получение месячного отчёта
    
    TODO: Реализовать генерацию отчёта
    """
    # TODO: Реализация
    return {
        "report": {},
        "month": month or datetime.now().month,
        "year": year or datetime.now().year
    }


@app.get("/api/analytics/conversion")
async def get_conversion_analysis(
    date_from: datetime,
    date_to: datetime,
    channel: Optional[str] = None
):
    """
    Анализ конверсии за период
    
    TODO: Реализовать анализ конверсии
    """
    # TODO: Реализация
    return {
        "conversion_rate": 0.0,
        "funnel": {},
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat()
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)



