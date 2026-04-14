"""
Бизнес-логика анализа и атрибуции
"""
from typing import List
from datetime import datetime, timedelta
import json

import asyncpg

from domain.models import VisitorIntentScore


class AnalyticsService:
    """Сервис для анализа данных"""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

    async def calculate_intent_score(
        self,
        visitor_id: str,
        session_id: str,
    ) -> VisitorIntentScore:
        """
        Рассчитывает оценку интереса посетителя (0-1) на основе событий
        из таблицы analytics_events (внутренний счётчик site_integration).
        """
        async with self.db.acquire() as conn:
            # Берём события за последний час по visitor_id + session_id
            rows = await conn.fetch(
                """
                SELECT event_type, event_data, created_at
                FROM analytics_events
                WHERE event_data->>'visitor_id' = $1
                  AND event_data->>'session_id' = $2
                  AND created_at > NOW() - INTERVAL '1 hour'
                ORDER BY created_at ASC
                """,
                visitor_id,
                session_id,
            )

        if not rows:
            return VisitorIntentScore(
                visitor_id=visitor_id,
                session_id=session_id,
                score=0.0,
                reasons=[],
            )

        # Парсим event_data (у нас там JSON-строка)
        events = []
        for r in rows:
            data_raw = r["event_data"]
            if isinstance(data_raw, str):
                try:
                    data = json.loads(data_raw)
                except json.JSONDecodeError:
                    data = {}
            else:
                data = data_raw or {}

            events.append(
                {
                    "event_type": r["event_type"],
                    "created_at": r["created_at"],
                    "data": data,
                }
            )

        score = 0.0
        reasons: List[str] = []

        # Подсмотр базовых типов событий
        def count(event_type: str) -> int:
            return sum(1 for e in events if e["event_type"] == event_type)

        phone_clicks = count("phone_click")
        whatsapp_clicks = count("whatsapp_click")
        form_submits = count("form_submit")
        email_inputs = count("email_input")
        phone_inputs = count("phone_input")
        place_interest = count("place_interest")  # клик «Интересуюсь этим объектом» на карточке
        card_view_long = count("card_view_duration")  # время на карточке объекта > N сек (опционально с фронта)

        # Весовые коэффициенты (эвристика под шкалу:
        # 0.0–0.29 холодный, 0.3–0.69 тёплый, 0.7–1.0 горячий)
        if place_interest > 0:
            score += 0.75
            reasons.append("Интерес к объекту (карточка/место)")
        if card_view_long > 0:
            score += 0.4
            reasons.append("Долгий просмотр карточки объекта")
        if phone_clicks > 0:
            score += 0.6
            reasons.append("Кликнул по телефону")
        if whatsapp_clicks > 0:
            score += 0.6
            reasons.append("Кликнул по WhatsApp")
        if form_submits > 0:
            score += 0.5
            reasons.append("Отправил форму")
        if phone_inputs > 0:
            score += 0.4
            reasons.append("Ввел телефон в форму")
        if email_inputs > 0:
            score += 0.3
            reasons.append("Оставил email")

        # Время на сайте по разнице между первым и последним событием
        first_event_ts = events[0]["created_at"]
        last_event_ts = events[-1]["created_at"]
        time_on_site = (last_event_ts - first_event_ts).total_seconds()
        if time_on_site > 300:  # > 5 минут
            score += 0.1
            reasons.append("Время на сайте > 5 минут")

        # Глубина просмотра по уникальным page_url
        pages = {
            e["data"].get("page_url")
            for e in events
            if isinstance(e["data"], dict) and e["data"].get("page_url")
        }
        if len(pages) > 5:
            score += 0.1
            reasons.append("Глубина просмотра > 5 страниц")

        return VisitorIntentScore(
            visitor_id=visitor_id,
            session_id=session_id,
            score=min(score, 1.0),
            reasons=reasons,
        )

    async def is_high_intent_visitor(
        self,
        visitor_id: str,
        session_id: str,
        threshold: float = 0.7,
    ) -> bool:
        """
        Проверяет, является ли посетитель высокоинтересным.
        """
        intent_score = await self.calculate_intent_score(visitor_id, session_id)
        return intent_score.score >= threshold
