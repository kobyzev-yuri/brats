# Отчёты Нейроаналитика и улучшение конверсии

## Обзор

Нейроаналитик собирает данные из Яндекс.Метрики и amoCRM для анализа поведения пользователей и оптимизации конверсии. Отчёты делятся на онлайн (real-time) и оффлайн (периодические).

---

## Архитектура сбора данных

### Источники данных

```
┌─────────────────┐
│ Яндекс.Метрика  │  ← События на сайте (просмотры, клики, цели)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Нейроаналитик  │
│  (analytics-    │
│   service)      │
│                 │
│  Онлайн модуль: │
│  - Real-time    │
│    события      │
│  - Горячие лиды │
│                 │
│  Оффлайн модуль:│
│  - Периодические│
│    отчёты       │
│  - Анализ       │
│    трендов      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  PostgreSQL      │
│  analytics_      │
│  events          │
│  analytics_      │
│  insights        │
└─────────────────┘
         │
         ↓
┌─────────────────┐
│  amoCRM         │  ← Синхронизация меток, статусов лидов
└─────────────────┘
```

---

## Онлайн отчёты (Real-time)

### Назначение
Мониторинг текущей ситуации в реальном времени для оперативного реагирования.

### Типы онлайн отчётов

#### 1. Dashboard реального времени

**Метрики:**
- Активные посетители на сайте (сейчас)
- События за последний час (график)
- Горячие лиды (обнаруженные за последний час)
- Конверсия в реальном времени (лиды/посетители)

**Техническая реализация:**

```python
# analytics-service/api/realtime.py
from fastapi import APIRouter
from datetime import datetime, timedelta
import asyncpg

router = APIRouter(prefix="/api/realtime", tags=["realtime"])

@router.get("/dashboard")
async def get_realtime_dashboard(db: asyncpg.Pool):
    """Dashboard реального времени"""
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    async with db.acquire() as conn:
        # Активные посетители (события за последние 5 минут)
        active_visitors = await conn.fetchval("""
            SELECT COUNT(DISTINCT amocrm_lead_id)
            FROM analytics_events
            WHERE created_at > NOW() - INTERVAL '5 minutes'
              AND event_type = 'page_view'
        """)
        
        # События за последний час (по типам)
        events_by_type = await conn.fetch("""
            SELECT 
                event_type,
                COUNT(*) as count
            FROM analytics_events
            WHERE created_at > $1
            GROUP BY event_type
            ORDER BY count DESC
        """, hour_ago)
        
        # Горячие лиды за последний час
        hot_leads = await conn.fetch("""
            SELECT 
                amocrm_lead_id,
                COUNT(*) as event_count,
                MAX(created_at) as last_event
            FROM analytics_events
            WHERE created_at > $1
              AND event_type IN ('goal', 'hot_lead_signal')
            GROUP BY amocrm_lead_id
            HAVING COUNT(*) >= 3
            ORDER BY event_count DESC
            LIMIT 10
        """, hour_ago)
        
        # Конверсия за последний час
        visitors = await conn.fetchval("""
            SELECT COUNT(DISTINCT amocrm_lead_id)
            FROM analytics_events
            WHERE created_at > $1
              AND event_type = 'page_view'
        """, hour_ago)
        
        leads = await conn.fetchval("""
            SELECT COUNT(DISTINCT amocrm_lead_id)
            FROM analytics_events
            WHERE created_at > $1
              AND event_type = 'lead_created'
        """, hour_ago)
        
        conversion_rate = (leads / visitors * 100) if visitors > 0 else 0
        
        return {
            "active_visitors": active_visitors,
            "events_by_type": [{"type": e["event_type"], "count": e["count"]} for e in events_by_type],
            "hot_leads": [
                {
                    "lead_id": h["amocrm_lead_id"],
                    "event_count": h["event_count"],
                    "last_event": h["last_event"].isoformat()
                }
                for h in hot_leads
            ],
            "conversion_rate": round(conversion_rate, 2),
            "timestamp": now.isoformat()
        }
```

#### 2. Алерты и уведомления

**Триггеры для алертов:**
- Резкий рост/падение трафика
- Обнаружение горячего лида
- Падение конверсии ниже порога
- Ошибки на сайте

```python
# analytics-service/service/alerts.py
async def check_alerts(db: asyncpg.Pool):
    """Проверка условий для алертов"""
    alerts = []
    
    # Проверка конверсии
    conversion = await get_current_conversion_rate(db)
    if conversion < 0.05:  # Конверсия ниже 5%
        alerts.append({
            "type": "low_conversion",
            "severity": "warning",
            "message": f"Конверсия упала до {conversion}%",
            "recommendation": "Проверить воронку продаж, возможно нужна оптимизация"
        })
    
    # Проверка горячих лидов
    hot_leads = await get_hot_leads_last_hour(db)
    if len(hot_leads) > 5:
        alerts.append({
            "type": "many_hot_leads",
            "severity": "info",
            "message": f"Обнаружено {len(hot_leads)} горячих лидов",
            "recommendation": "Усилить работу с горячими лидами"
        })
    
    return alerts
```

#### 3. Мониторинг воронки продаж

**Этапы воронки:**
1. Посетитель → Просмотр страницы
2. Просмотр → Интерес (время на сайте > 2 мин)
3. Интерес → Лид (заполнение формы)
4. Лид → Квалификация (диалог с агентом)
5. Квалификация → КП
6. КП → Договор

```python
# analytics-service/api/funnel.py
@router.get("/funnel/realtime")
async def get_realtime_funnel(db: asyncpg.Pool):
    """Воронка продаж в реальном времени (за последний час)"""
    hour_ago = datetime.now() - timedelta(hours=1)
    
    async with db.acquire() as conn:
        # Этап 1: Посетители
        visitors = await conn.fetchval("""
            SELECT COUNT(DISTINCT amocrm_lead_id)
            FROM analytics_events
            WHERE created_at > $1
              AND event_type = 'page_view'
        """, hour_ago)
        
        # Этап 2: Интерес (время на сайте > 2 мин)
        interested = await conn.fetchval("""
            SELECT COUNT(DISTINCT amocrm_lead_id)
            FROM analytics_events
            WHERE created_at > $1
              AND event_type = 'time_on_site'
              AND (event_data->>'seconds')::int > 120
        """, hour_ago)
        
        # Этап 3: Лиды (заполнение формы)
        leads = await conn.fetchval("""
            SELECT COUNT(DISTINCT amocrm_lead_id)
            FROM analytics_events
            WHERE created_at > $1
              AND event_type = 'lead_created'
        """, hour_ago)
        
        # Этап 4: Квалификация (диалог с агентом)
        qualified = await conn.fetchval("""
            SELECT COUNT(DISTINCT conversation_id)
            FROM conversations
            WHERE created_at > $1
              AND state IN ('QUALIFYING', 'PROPOSAL', 'NEGOTIATION')
        """, hour_ago)
        
        # Этап 5: КП
        proposals = await conn.fetchval("""
            SELECT COUNT(*)
            FROM proposals
            WHERE created_at > $1
              AND status IN ('sent', 'negotiating')
        """, hour_ago)
        
        # Этап 6: Договоры
        contracts = await conn.fetchval("""
            SELECT COUNT(*)
            FROM contracts
            WHERE created_at > $1
              AND status IN ('signed', 'paid')
        """, hour_ago)
        
        return {
            "funnel": [
                {"stage": "Посетители", "count": visitors, "conversion": 100.0},
                {"stage": "Интерес", "count": interested, "conversion": round(interested/visitors*100, 2) if visitors > 0 else 0},
                {"stage": "Лид", "count": leads, "conversion": round(leads/visitors*100, 2) if visitors > 0 else 0},
                {"stage": "Квалификация", "count": qualified, "conversion": round(qualified/visitors*100, 2) if visitors > 0 else 0},
                {"stage": "КП", "count": proposals, "conversion": round(proposals/visitors*100, 2) if visitors > 0 else 0},
                {"stage": "Договор", "count": contracts, "conversion": round(contracts/visitors*100, 2) if visitors > 0 else 0}
            ],
            "period": "last_hour"
        }
```

---

## Оффлайн отчёты (Периодические)

### Назначение
Анализ трендов, выявление проблем, оптимизация воронки продаж.

### Типы оффлайн отчётов

#### 1. Ежедневный отчёт

**Содержание:**
- Статистика за день (посетители, лиды, конверсия)
- Сравнение с предыдущим днём
- Топ источников трафика
- Топ страниц по конверсии
- Проблемные места воронки

```python
# analytics-service/reports/daily.py
async def generate_daily_report(date: datetime, db: asyncpg.Pool):
    """Генерация ежедневного отчёта"""
    start_date = date.replace(hour=0, minute=0, second=0)
    end_date = start_date + timedelta(days=1)
    prev_start = start_date - timedelta(days=1)
    prev_end = start_date
    
    async with db.acquire() as conn:
        # Текущий день
        today_stats = await get_period_stats(conn, start_date, end_date)
        
        # Предыдущий день
        yesterday_stats = await get_period_stats(conn, prev_start, prev_end)
        
        # Источники трафика
        traffic_sources = await conn.fetch("""
            SELECT 
                event_data->>'source' as source,
                COUNT(DISTINCT amocrm_lead_id) as visitors,
                COUNT(DISTINCT CASE WHEN event_type = 'lead_created' THEN amocrm_lead_id END) as leads
            FROM analytics_events
            WHERE created_at >= $1 AND created_at < $2
            GROUP BY event_data->>'source'
            ORDER BY visitors DESC
        """, start_date, end_date)
        
        # Топ страниц по конверсии
        top_pages = await conn.fetch("""
            SELECT 
                event_data->>'url' as url,
                COUNT(DISTINCT amocrm_lead_id) as visitors,
                COUNT(DISTINCT CASE WHEN event_type = 'lead_created' THEN amocrm_lead_id END) as leads,
                ROUND(
                    COUNT(DISTINCT CASE WHEN event_type = 'lead_created' THEN amocrm_lead_id END)::numeric /
                    NULLIF(COUNT(DISTINCT amocrm_lead_id), 0) * 100,
                    2
                ) as conversion_rate
            FROM analytics_events
            WHERE created_at >= $1 AND created_at < $2
              AND event_type IN ('page_view', 'lead_created')
            GROUP BY event_data->>'url'
            HAVING COUNT(DISTINCT amocrm_lead_id) >= 10
            ORDER BY conversion_rate DESC
            LIMIT 10
        """, start_date, end_date)
        
        # Анализ воронки
        funnel_analysis = await analyze_funnel(conn, start_date, end_date)
        
        return {
            "date": start_date.date().isoformat(),
            "summary": {
                "visitors": today_stats["visitors"],
                "visitors_change": calculate_change(today_stats["visitors"], yesterday_stats["visitors"]),
                "leads": today_stats["leads"],
                "leads_change": calculate_change(today_stats["leads"], yesterday_stats["leads"]),
                "conversion_rate": today_stats["conversion_rate"],
                "conversion_change": calculate_change(today_stats["conversion_rate"], yesterday_stats["conversion_rate"])
            },
            "traffic_sources": [
                {
                    "source": t["source"],
                    "visitors": t["visitors"],
                    "leads": t["leads"],
                    "conversion_rate": round(t["leads"]/t["visitors"]*100, 2) if t["visitors"] > 0 else 0
                }
                for t in traffic_sources
            ],
            "top_pages": [
                {
                    "url": p["url"],
                    "visitors": p["visitors"],
                    "leads": p["leads"],
                    "conversion_rate": float(p["conversion_rate"])
                }
                for p in top_pages
            ],
            "funnel_analysis": funnel_analysis,
            "recommendations": generate_recommendations(today_stats, funnel_analysis)
        }
```

#### 2. Еженедельный отчёт

**Содержание:**
- Тренды за неделю
- Сравнение с предыдущей неделей
- Анализ эффективности каналов
- Рекомендации по оптимизации

```python
# analytics-service/reports/weekly.py
async def generate_weekly_report(week_start: datetime, db: asyncpg.Pool):
    """Генерация еженедельного отчёта"""
    week_end = week_start + timedelta(days=7)
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_start
    
    async with db.acquire() as conn:
        # Текущая неделя
        week_stats = await get_period_stats(conn, week_start, week_end)
        
        # Предыдущая неделя
        prev_week_stats = await get_period_stats(conn, prev_week_start, prev_week_end)
        
        # Тренды по дням
        daily_trends = await conn.fetch("""
            SELECT 
                DATE(created_at) as date,
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'page_view') as visitors,
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'lead_created') as leads
            FROM analytics_events
            WHERE created_at >= $1 AND created_at < $2
            GROUP BY DATE(created_at)
            ORDER BY date
        """, week_start, week_end)
        
        # Эффективность каналов
        channel_efficiency = await analyze_channels(conn, week_start, week_end)
        
        # Анализ конверсии по этапам
        conversion_by_stage = await analyze_conversion_by_stage(conn, week_start, week_end)
        
        return {
            "period": {
                "start": week_start.date().isoformat(),
                "end": (week_end - timedelta(days=1)).date().isoformat()
            },
            "summary": {
                "visitors": week_stats["visitors"],
                "visitors_change": calculate_change(week_stats["visitors"], prev_week_stats["visitors"]),
                "leads": week_stats["leads"],
                "leads_change": calculate_change(week_stats["leads"], prev_week_stats["leads"]),
                "conversion_rate": week_stats["conversion_rate"],
                "conversion_change": calculate_change(week_stats["conversion_rate"], prev_week_stats["conversion_rate"])
            },
            "daily_trends": [
                {
                    "date": d["date"].isoformat(),
                    "visitors": d["visitors"],
                    "leads": d["leads"]
                }
                for d in daily_trends
            ],
            "channel_efficiency": channel_efficiency,
            "conversion_by_stage": conversion_by_stage,
            "recommendations": generate_weekly_recommendations(week_stats, channel_efficiency, conversion_by_stage)
        }
```

#### 3. Месячный отчёт

**Содержание:**
- Итоги месяца
- Сравнение с предыдущим месяцем
- Анализ эффективности рекламы
- Прогноз на следующий месяц

---

## Интеграция с Яндекс.Метрикой

### Сбор данных

**События, которые отслеживаем:**

1. **Просмотры страниц** (`page_view`)
   - URL страницы
   - Время на странице
   - Источник трафика

2. **Цели** (`goal`)
   - Просмотр каталога
   - Просмотр объекта
   - Заполнение формы
   - Запрос обратного звонка

3. **Горячие лиды** (`hot_lead_signal`)
   - Множественные просмотры объектов
   - Долгое время на сайте
   - Повторные визиты

```python
# analytics-service/integrations/yandex_metrika.py
import httpx
from datetime import datetime, timedelta

class YandexMetrikaClient:
    def __init__(self, oauth_token: str, counter_id: str):
        self.oauth_token = oauth_token
        self.counter_id = counter_id
        self.base_url = "https://api-metrika.yandex.net/management/v1"
    
    async def get_realtime_visitors(self):
        """Получить количество активных посетителей"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/realtime",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            return response.json()
    
    async def get_events(self, date_from: datetime, date_to: datetime):
        """Получить события за период"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/counter/{self.counter_id}/logrequests",
                headers={"Authorization": f"OAuth {self.oauth_token}"},
                json={
                    "date1": date_from.strftime("%Y-%m-%d"),
                    "date2": date_to.strftime("%Y-%m-%d"),
                    "fields": ["ym:s:visitID", "ym:s:clientID", "ym:pv:URL", "ym:pv:title", "ym:s:dateTime", "ym:s:goalID"]
                }
            )
            return response.json()
    
    async def get_goals(self):
        """Получить список целей"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/goals",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            return response.json()
```

### Обработка событий

```python
# analytics-service/service/event_processor.py
async def process_metrika_event(event: dict, db: asyncpg.Pool):
    """Обработка события из Яндекс.Метрики"""
    event_type = determine_event_type(event)
    
    # Сохранение в БД
    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO analytics_events (
                amocrm_lead_id, event_type, event_data, created_at
            )
            VALUES ($1, $2, $3, $4)
        """,
            event.get("client_id"),  # Связь с лидом через client_id
            event_type,
            json.dumps({
                "url": event.get("url"),
                "title": event.get("title"),
                "source": event.get("source"),
                "goal_id": event.get("goal_id")
            }),
            datetime.fromisoformat(event.get("date_time"))
        )
        
        # Проверка на горячий лид
        if is_hot_lead(event):
            await mark_hot_lead(conn, event.get("client_id"))
            # Триггер для Нейропродажника
            await trigger_sales_agent(conn, event.get("client_id"))
```

---

## Улучшение конверсии на основе данных

### 1. Анализ воронки продаж

**Выявление узких мест:**

```python
# analytics-service/analysis/funnel_optimization.py
async def analyze_funnel_bottlenecks(db: asyncpg.Pool, period_start: datetime, period_end: datetime):
    """Анализ узких мест в воронке"""
    async with db.acquire() as conn:
        # Конверсия по этапам
        stages = await conn.fetch("""
            WITH stage_counts AS (
                SELECT 
                    CASE 
                        WHEN event_type = 'page_view' THEN 'visitor'
                        WHEN event_type = 'time_on_site' AND (event_data->>'seconds')::int > 120 THEN 'interested'
                        WHEN event_type = 'lead_created' THEN 'lead'
                        WHEN event_type = 'conversation_started' THEN 'qualified'
                        WHEN event_type = 'proposal_sent' THEN 'proposal'
                        WHEN event_type = 'contract_signed' THEN 'contract'
                    END as stage,
                    COUNT(DISTINCT amocrm_lead_id) as count
                FROM analytics_events
                WHERE created_at >= $1 AND created_at < $2
                GROUP BY stage
            )
            SELECT * FROM stage_counts WHERE stage IS NOT NULL
        """, period_start, period_end)
        
        # Вычисление конверсии между этапами
        bottlenecks = []
        prev_count = None
        prev_stage = None
        
        for stage in stages:
            if prev_count and prev_count > 0:
                conversion = stage["count"] / prev_count * 100
                if conversion < 30:  # Конверсия ниже 30% - узкое место
                    bottlenecks.append({
                        "from_stage": prev_stage,
                        "to_stage": stage["stage"],
                        "conversion": round(conversion, 2),
                        "recommendation": get_recommendation_for_bottleneck(prev_stage, stage["stage"])
                    })
            prev_count = stage["count"]
            prev_stage = stage["stage"]
        
        return bottlenecks
```

### 2. Анализ источников трафика

**Определение эффективных каналов:**

```python
async def analyze_traffic_sources(db: asyncpg.Pool, period_start: datetime, period_end: datetime):
    """Анализ эффективности источников трафика"""
    async with db.acquire() as conn:
        sources = await conn.fetch("""
            SELECT 
                event_data->>'source' as source,
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'page_view') as visitors,
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'lead_created') as leads,
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'contract_signed') as contracts,
                AVG((event_data->>'time_on_site')::int) FILTER (WHERE event_type = 'time_on_site') as avg_time_on_site
            FROM analytics_events
            WHERE created_at >= $1 AND created_at < $2
            GROUP BY event_data->>'source'
            HAVING COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'page_view') >= 10
        """, period_start, period_end)
        
        return [
            {
                "source": s["source"],
                "visitors": s["visitors"],
                "leads": s["leads"],
                "contracts": s["contracts"],
                "visitor_to_lead": round(s["leads"]/s["visitors"]*100, 2) if s["visitors"] > 0 else 0,
                "lead_to_contract": round(s["contracts"]/s["leads"]*100, 2) if s["leads"] > 0 else 0,
                "avg_time_on_site": round(float(s["avg_time_on_site"] or 0), 0),
                "recommendation": get_recommendation_for_source(s)
            }
            for s in sources
        ]
```

### 3. Рекомендации по оптимизации

**Автоматическая генерация рекомендаций:**

```python
# analytics-service/analysis/recommendations.py
def generate_recommendations(stats: dict, funnel_analysis: dict, traffic_sources: list):
    """Генерация рекомендаций по улучшению конверсии"""
    recommendations = []
    
    # Низкая конверсия посетитель → лид
    if stats["conversion_rate"] < 5:
        recommendations.append({
            "priority": "high",
            "category": "conversion",
            "title": "Низкая конверсия посетителей в лиды",
            "description": f"Текущая конверсия {stats['conversion_rate']}% ниже целевой (5%+)",
            "actions": [
                "Оптимизировать формы захвата лидов (упростить, добавить социальные доказательства)",
                "Улучшить призывы к действию (CTA) на ключевых страницах",
                "Добавить чат-бот для быстрого ответа на вопросы",
                "Проверить скорость загрузки страниц"
            ]
        })
    
    # Узкое место в воронке
    for bottleneck in funnel_analysis.get("bottlenecks", []):
        recommendations.append({
            "priority": "medium",
            "category": "funnel",
            "title": f"Узкое место: {bottleneck['from_stage']} → {bottleneck['to_stage']}",
            "description": f"Конверсия {bottleneck['conversion']}%",
            "actions": bottleneck["recommendation"]
        })
    
    # Неэффективные источники трафика
    for source in traffic_sources:
        if source["visitor_to_lead"] < 2 and source["visitors"] > 50:
            recommendations.append({
                "priority": "low",
                "category": "traffic",
                "title": f"Низкая конверсия из источника: {source['source']}",
                "description": f"Конверсия {source['visitor_to_lead']}% при {source['visitors']} посетителях",
                "actions": [
                    "Пересмотреть рекламные объявления для этого источника",
                    "Проверить соответствие landing page источнику трафика",
                    "Рассмотреть возможность перераспределения бюджета"
                ]
            })
    
    return recommendations
```

---

## Примеры использования отчётов

### Пример 1: Обнаружение проблемы

```
Ежедневный отчёт показывает:
- Конверсия упала с 6% до 3%
- Узкое место: "Интерес → Лид" (конверсия 15%)

Рекомендация:
- Упростить форму захвата лидов
- Добавить социальные доказательства (отзывы, количество продаж)
- Улучшить призыв к действию
```

### Пример 2: Оптимизация каналов

```
Еженедельный отчёт показывает:
- Яндекс.Директ: 1000 посетителей, 2% конверсия
- Google Ads: 500 посетителей, 8% конверсия

Рекомендация:
- Увеличить бюджет на Google Ads
- Пересмотреть объявления в Яндекс.Директ
```

### Пример 3: Улучшение воронки

```
Анализ воронки показывает:
- Посетитель → Интерес: 80% (хорошо)
- Интерес → Лид: 15% (плохо)
- Лид → КП: 60% (хорошо)
- КП → Договор: 20% (можно улучшить)

Рекомендация:
- Фокус на этапе "Интерес → Лид": упростить форму, добавить чат-бот
- Улучшить этап "КП → Договор": автоматизировать отправку договоров, добавить напоминания
```

---

## План реализации

### Этап 1: Базовая интеграция
1. ✅ Настроить сбор событий из Яндекс.Метрики
2. ✅ Создать таблицы для хранения событий
3. ✅ Реализовать онлайн dashboard

### Этап 2: Оффлайн отчёты
1. ✅ Ежедневные отчёты
2. ✅ Еженедельные отчёты
3. ✅ Месячные отчёты

### Этап 3: Аналитика и рекомендации
1. ✅ Анализ воронки продаж
2. ✅ Анализ источников трафика
3. ✅ Автоматическая генерация рекомендаций

### Этап 4: Автоматизация
1. ✅ Автоматическая отправка отчётов
2. ✅ Алерты при проблемах
3. ✅ Интеграция с amoCRM для синхронизации меток







