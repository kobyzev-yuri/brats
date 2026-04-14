# Отслеживание эффективности бюджета Яндекс.Директ

## Обзор

Для понимания эффективности бюджета, потраченного на Яндекс.Директ, необходимо связать данные о расходах из Яндекс.Директ API с данными о конверсиях из Яндекс.Метрики и amoCRM. Это позволяет рассчитать ключевые метрики: CPA, ROAS, ROI и оптимизировать рекламные кампании.

---

## Архитектура сбора данных

### Источники данных

```
┌─────────────────┐
│ Яндекс.Директ   │  ← Расходы, клики, показы, кампании
│ API             │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Яндекс.Метрика  │  ← Конверсии, цели, источники трафика
│ API              │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  amoCRM API     │  ← Лиды, сделки, суммы сделок
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Нейроаналитик  │
│  (analytics-    │
│   service)      │
│                 │
│  - Сбор данных  │
│  - Связывание   │
│  - Расчёт       │
│    метрик       │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  PostgreSQL      │
│  ad_campaigns    │  ← Данные о рекламных кампаниях
│  ad_performance   │  ← Эффективность по периодам
│  analytics_events │  ← События с источниками трафика
└─────────────────┘
```

---

## Схема базы данных

### Таблица ad_campaigns (рекламные кампании)

```sql
CREATE TABLE ad_campaigns (
    id SERIAL PRIMARY KEY,
    
    -- Связь с Яндекс.Директ
    yandex_direct_campaign_id BIGINT UNIQUE NOT NULL,  -- ID кампании в Яндекс.Директ
    yandex_direct_ad_group_id BIGINT,  -- ID группы объявлений (опционально)
    
    -- Базовая информация
    name VARCHAR(500) NOT NULL,  -- Название кампании
    status VARCHAR(50),  -- 'active', 'paused', 'archived'
    campaign_type VARCHAR(50),  -- 'text', 'image', 'video', 'smart'
    
    -- Бюджет
    daily_budget DECIMAL(12, 2),  -- Дневной бюджет
    total_budget DECIMAL(12, 2),  -- Общий бюджет (если установлен)
    
    -- Метаданные
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Дополнительные данные из Яндекс.Директ (JSONB)
    yandex_direct_data JSONB  -- Полные данные из API
);

CREATE INDEX ON ad_campaigns (yandex_direct_campaign_id);
CREATE INDEX ON ad_campaigns (status);
```

### Таблица ad_performance (эффективность рекламы по периодам)

```sql
CREATE TABLE ad_performance (
    id SERIAL PRIMARY KEY,
    
    -- Связь с кампанией
    ad_campaign_id INTEGER REFERENCES ad_campaigns(id) ON DELETE CASCADE,
    yandex_direct_campaign_id BIGINT,  -- Для быстрого поиска
    
    -- Период
    date DATE NOT NULL,
    
    -- Расходы (из Яндекс.Директ)
    cost DECIMAL(12, 2) DEFAULT 0,  -- Потрачено рублей
    clicks INTEGER DEFAULT 0,  -- Кликов
    impressions INTEGER DEFAULT 0,  -- Показов
    ctr DECIMAL(5, 2),  -- CTR (клики/показы * 100)
    avg_cpc DECIMAL(10, 2),  -- Средняя цена клика
    
    -- Трафик (из Яндекс.Метрики)
    visitors INTEGER DEFAULT 0,  -- Уникальных посетителей
    sessions INTEGER DEFAULT 0,  -- Сессий
    
    -- Конверсии (из Яндекс.Метрики)
    goals INTEGER DEFAULT 0,  -- Достижений целей
    goal_conversions INTEGER DEFAULT 0,  -- Конверсий в цели
    
    -- Лиды (из amoCRM)
    leads INTEGER DEFAULT 0,  -- Созданных лидов
    qualified_leads INTEGER DEFAULT 0,  -- Квалифицированных лидов
    
    -- Сделки (из amoCRM)
    deals INTEGER DEFAULT 0,  -- Созданных сделок
    deals_amount DECIMAL(12, 2) DEFAULT 0,  -- Сумма сделок
    
    -- Рассчитанные метрики
    cpa DECIMAL(10, 2),  -- CPA = cost / leads (стоимость привлечения лида)
    roas DECIMAL(10, 2),  -- ROAS = deals_amount / cost (возврат на рекламу)
    roi DECIMAL(10, 2),  -- ROI = (deals_amount - cost) / cost * 100 (возврат инвестиций)
    conversion_rate DECIMAL(5, 2),  -- Конверсия = leads / visitors * 100
    
    -- Метаданные
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Уникальность: одна запись на кампанию и дату
    UNIQUE(ad_campaign_id, date)
);

CREATE INDEX ON ad_performance (date);
CREATE INDEX ON ad_performance (yandex_direct_campaign_id, date);
CREATE INDEX ON ad_performance (ad_campaign_id, date);
```

### Обновление таблицы analytics_events

Добавим поле для связи с рекламными кампаниями:

```sql
-- Если таблица уже существует, добавим поле
ALTER TABLE analytics_events 
ADD COLUMN IF NOT EXISTS ad_campaign_id INTEGER REFERENCES ad_campaigns(id);

CREATE INDEX ON analytics_events (ad_campaign_id);
```

---

## Получение данных из Яндекс.Директ API

### Настройка доступа

Для работы с Яндекс.Директ API нужны:
- **OAuth токен** (можно использовать тот же, что для Яндекс.Метрики, или отдельный)
- **Client ID** и **Client Secret** для OAuth-приложения
- **Login** (логин рекламодателя в Яндекс.Директ)

Подробнее см. [`docs/YANDEX_METRIKA_API_SETUP.md`](./YANDEX_METRIKA_API_SETUP.md) для получения OAuth токена.

### Пример клиента Яндекс.Директ API

```python
# analytics-service/integrations/yandex_direct.py
import httpx
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class YandexDirectClient:
    def __init__(
        self,
        oauth_token: Optional[str] = None,
        login: Optional[str] = None
    ):
        self.oauth_token = oauth_token or os.getenv("YANDEX_DIRECT_OAUTH_TOKEN")
        self.login = login or os.getenv("YANDEX_DIRECT_LOGIN")
        self.base_url = "https://api.direct.yandex.com/json/v5"
        
        if not self.oauth_token:
            raise ValueError("OAuth token not set. Set YANDEX_DIRECT_OAUTH_TOKEN in .env")
        if not self.login:
            raise ValueError("Login not set. Set YANDEX_DIRECT_LOGIN in .env")
    
    async def _request(
        self,
        method: str,
        params: Dict
    ) -> Dict:
        """
        Выполняет запрос к Яндекс.Директ API.
        """
        headers = {
            "Authorization": f"Bearer {self.oauth_token}",
            "Client-Login": self.login,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json={
                    "method": method,
                    "params": params
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                raise ValueError(f"API Error: {data['error']}")
            
            return data.get("result", {})
    
    async def get_campaigns(self) -> List[Dict]:
        """
        Получение списка кампаний.
        """
        result = await self._request(
            "Campaigns.get",
            {
                "SelectionCriteria": {},
                "FieldNames": [
                    "Id", "Name", "Status", "Type", 
                    "DailyBudget", "Funds", "Statistics"
                ]
            }
        )
        return result.get("Campaigns", [])
    
    async def get_campaign_statistics(
        self,
        campaign_ids: List[int],
        date_from: datetime,
        date_to: datetime
    ) -> List[Dict]:
        """
        Получение статистики по кампаниям за период.
        """
        result = await self._request(
            "Reports.get",
            {
                "SelectionCriteria": {
                    "DateFrom": date_from.strftime("%Y-%m-%d"),
                    "DateTo": date_to.strftime("%Y-%m-%d"),
                    "Ids": campaign_ids
                },
                "FieldNames": [
                    "CampaignId", "CampaignName", "Date",
                    "Impressions", "Clicks", "Cost"
                ],
                "ReportName": "CampaignPerformance",
                "ReportType": "CAMPAIGN_PERFORMANCE_REPORT",
                "DateRangeType": "CUSTOM_DATE",
                "Format": "TSV",
                "IncludeVAT": "YES",
                "IncludeDiscount": "NO"
            }
        )
        return result.get("data", [])
    
    async def get_keywords_statistics(
        self,
        campaign_ids: List[int],
        date_from: datetime,
        date_to: datetime
    ) -> List[Dict]:
        """
        Получение статистики по ключевым словам.
        """
        result = await self._request(
            "Reports.get",
            {
                "SelectionCriteria": {
                    "DateFrom": date_from.strftime("%Y-%m-%d"),
                    "DateTo": date_to.strftime("%Y-%m-%d"),
                    "CampaignIds": campaign_ids
                },
                "FieldNames": [
                    "CampaignId", "CampaignName", "Keyword", "Date",
                    "Impressions", "Clicks", "Cost"
                ],
                "ReportName": "KeywordPerformance",
                "ReportType": "KEYWORD_PERFORMANCE_REPORT",
                "DateRangeType": "CUSTOM_DATE",
                "Format": "TSV"
            }
        )
        return result.get("data", [])
```

---

## Синхронизация данных

### 1. Синхронизация кампаний

```python
# analytics-service/service/ad_sync.py
import asyncpg
import json
from datetime import datetime
from integrations.yandex_direct import YandexDirectClient

async def sync_campaigns(db: asyncpg.Pool):
    """
    Синхронизация списка кампаний из Яндекс.Директ.
    """
    direct_client = YandexDirectClient()
    campaigns = await direct_client.get_campaigns()
    
    async with db.acquire() as conn:
        for campaign in campaigns:
            campaign_id = campaign["Id"]
            name = campaign["Name"]
            status = campaign.get("Status", "unknown")
            campaign_type = campaign.get("Type", "unknown")
            daily_budget = campaign.get("DailyBudget", {}).get("Amount", 0) / 1000000  # Конвертация из микро-рублей
            
            # Проверка существования
            existing = await conn.fetchrow(
                "SELECT id FROM ad_campaigns WHERE yandex_direct_campaign_id = $1",
                campaign_id
            )
            
            if existing:
                # Обновление
                await conn.execute("""
                    UPDATE ad_campaigns
                    SET
                        name = $1,
                        status = $2,
                        campaign_type = $3,
                        daily_budget = $4,
                        yandex_direct_data = $5,
                        updated_at = NOW()
                    WHERE yandex_direct_campaign_id = $6
                """, name, status, campaign_type, daily_budget, 
                    json.dumps(campaign), campaign_id)
            else:
                # Создание
                await conn.execute("""
                    INSERT INTO ad_campaigns (
                        yandex_direct_campaign_id, name, status, 
                        campaign_type, daily_budget, yandex_direct_data
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, campaign_id, name, status, campaign_type, 
                    daily_budget, json.dumps(campaign))
```

### 2. Синхронизация статистики по кампаниям

```python
async def sync_campaign_statistics(
    db: asyncpg.Pool,
    date_from: datetime,
    date_to: datetime
):
    """
    Синхронизация статистики по кампаниям за период.
    """
    direct_client = YandexDirectClient()
    
    # Получение всех активных кампаний
    async with db.acquire() as conn:
        campaigns = await conn.fetch("""
            SELECT id, yandex_direct_campaign_id 
            FROM ad_campaigns 
            WHERE status = 'active'
        """)
    
    campaign_ids = [c["yandex_direct_campaign_id"] for c in campaigns]
    
    if not campaign_ids:
        return
    
    # Получение статистики из Яндекс.Директ
    statistics = await direct_client.get_campaign_statistics(
        campaign_ids,
        date_from,
        date_to
    )
    
    # Сохранение в БД
    async with db.acquire() as conn:
        for stat in statistics:
            campaign_id = stat["CampaignId"]
            date = datetime.strptime(stat["Date"], "%Y-%m-%d").date()
            cost = stat.get("Cost", 0) / 1000000  # Конвертация из микро-рублей
            clicks = stat.get("Clicks", 0)
            impressions = stat.get("Impressions", 0)
            
            # Получение ad_campaign_id
            campaign = await conn.fetchrow(
                "SELECT id FROM ad_campaigns WHERE yandex_direct_campaign_id = $1",
                campaign_id
            )
            
            if not campaign:
                continue
            
            ad_campaign_id = campaign["id"]
            
            # Расчёт CTR и CPC
            ctr = (clicks / impressions * 100) if impressions > 0 else 0
            avg_cpc = (cost / clicks) if clicks > 0 else 0
            
            # Получение данных о трафике и конверсиях из analytics_events
            traffic_data = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'page_view') as visitors,
                    COUNT(*) FILTER (WHERE event_type = 'page_view') as sessions,
                    COUNT(*) FILTER (WHERE event_type = 'goal') as goals
                FROM analytics_events
                WHERE ad_campaign_id = $1
                  AND DATE(created_at) = $2
            """, ad_campaign_id, date)
            
            # Получение данных о лидах и сделках из amoCRM
            leads_data = await conn.fetchrow("""
                SELECT 
                    COUNT(*) FILTER (WHERE amocrm_lead_id IS NOT NULL) as leads,
                    COUNT(*) FILTER (WHERE amocrm_lead_id IS NOT NULL AND status = 'qualified') as qualified_leads
                FROM conversations
                WHERE ad_campaign_id = $1
                  AND DATE(created_at) = $2
            """, ad_campaign_id, date)
            
            deals_data = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as deals,
                    COALESCE(SUM(amount), 0) as deals_amount
                FROM contracts
                WHERE amocrm_lead_id IN (
                    SELECT amocrm_lead_id 
                    FROM conversations 
                    WHERE ad_campaign_id = $1
                )
                AND DATE(created_at) = $2
            """, ad_campaign_id, date)
            
            visitors = traffic_data["visitors"] or 0
            sessions = traffic_data["sessions"] or 0
            goals = traffic_data["goals"] or 0
            leads = leads_data["leads"] or 0
            qualified_leads = leads_data["qualified_leads"] or 0
            deals = deals_data["deals"] or 0
            deals_amount = float(deals_data["deals_amount"] or 0)
            
            # Расчёт метрик
            cpa = (cost / leads) if leads > 0 else None
            roas = (deals_amount / cost) if cost > 0 else None
            roi = ((deals_amount - cost) / cost * 100) if cost > 0 else None
            conversion_rate = (leads / visitors * 100) if visitors > 0 else 0
            
            # Сохранение или обновление
            await conn.execute("""
                INSERT INTO ad_performance (
                    ad_campaign_id, yandex_direct_campaign_id, date,
                    cost, clicks, impressions, ctr, avg_cpc,
                    visitors, sessions, goals, goal_conversions,
                    leads, qualified_leads, deals, deals_amount,
                    cpa, roas, roi, conversion_rate
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                ON CONFLICT (ad_campaign_id, date) 
                DO UPDATE SET
                    cost = EXCLUDED.cost,
                    clicks = EXCLUDED.clicks,
                    impressions = EXCLUDED.impressions,
                    ctr = EXCLUDED.ctr,
                    avg_cpc = EXCLUDED.avg_cpc,
                    visitors = EXCLUDED.visitors,
                    sessions = EXCLUDED.sessions,
                    goals = EXCLUDED.goals,
                    goal_conversions = EXCLUDED.goal_conversions,
                    leads = EXCLUDED.leads,
                    qualified_leads = EXCLUDED.qualified_leads,
                    deals = EXCLUDED.deals,
                    deals_amount = EXCLUDED.deals_amount,
                    cpa = EXCLUDED.cpa,
                    roas = EXCLUDED.roas,
                    roi = EXCLUDED.roi,
                    conversion_rate = EXCLUDED.conversion_rate,
                    updated_at = NOW()
            """,
                ad_campaign_id, campaign_id, date,
                cost, clicks, impressions, ctr, avg_cpc,
                visitors, sessions, goals, goals,  # goal_conversions = goals
                leads, qualified_leads, deals, deals_amount,
                cpa, roas, roi, conversion_rate
            )
```

### 3. Связывание событий с кампаниями

Для правильного связывания событий из Яндекс.Метрики с кампаниями нужно использовать UTM-метки или параметры Яндекс.Директ.

```python
async def link_events_to_campaigns(db: asyncpg.Pool):
    """
    Связывание событий из analytics_events с рекламными кампаниями.
    Использует UTM-метки или параметры из event_data.
    """
    async with db.acquire() as conn:
        # События с UTM-метками или параметрами Яндекс.Директ
        events = await conn.fetch("""
            SELECT id, event_data, created_at
            FROM analytics_events
            WHERE ad_campaign_id IS NULL
              AND event_data->>'source' = 'yandex_direct'
              AND created_at >= NOW() - INTERVAL '7 days'
        """)
        
        for event in events:
            event_data = event["event_data"]
            
            # Извлечение campaign_id из UTM или параметров
            campaign_id = None
            
            # Вариант 1: из UTM-меток
            if "utm_campaign" in event_data:
                utm_campaign = event_data["utm_campaign"]
                # Поиск кампании по UTM-метке
                campaign = await conn.fetchrow("""
                    SELECT id FROM ad_campaigns
                    WHERE yandex_direct_data->>'utm_campaign' = $1
                       OR name ILIKE '%' || $1 || '%'
                    LIMIT 1
                """, utm_campaign)
                if campaign:
                    campaign_id = campaign["id"]
            
            # Вариант 2: из параметров Яндекс.Директ
            if not campaign_id and "yclid" in event_data:
                # yclid содержит информацию о кампании
                # Можно использовать API Яндекс.Директ для получения campaign_id по yclid
                # Или хранить маппинг yclid -> campaign_id
                pass
            
            # Обновление события
            if campaign_id:
                await conn.execute("""
                    UPDATE analytics_events
                    SET ad_campaign_id = $1
                    WHERE id = $2
                """, campaign_id, event["id"])
```

---

## Отчёты по эффективности

### 1. Отчёт по кампаниям за период

```python
# analytics-service/api/ad_reports.py
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
import asyncpg

router = APIRouter(prefix="/api/ad-reports", tags=["advertising"])

@router.get("/campaigns")
async def get_campaigns_report(
    date_from: datetime = Query(..., description="Начальная дата"),
    date_to: datetime = Query(..., description="Конечная дата"),
    db: asyncpg.Pool = None
):
    """
    Отчёт по эффективности кампаний за период.
    """
    async with db.acquire() as conn:
        results = await conn.fetch("""
            SELECT 
                c.id,
                c.name,
                c.status,
                c.daily_budget,
                SUM(p.cost) as total_cost,
                SUM(p.clicks) as total_clicks,
                SUM(p.impressions) as total_impressions,
                AVG(p.ctr) as avg_ctr,
                AVG(p.avg_cpc) as avg_cpc,
                SUM(p.visitors) as total_visitors,
                SUM(p.leads) as total_leads,
                SUM(p.deals) as total_deals,
                SUM(p.deals_amount) as total_deals_amount,
                AVG(p.cpa) as avg_cpa,
                AVG(p.roas) as avg_roas,
                AVG(p.roi) as avg_roi,
                AVG(p.conversion_rate) as avg_conversion_rate
            FROM ad_campaigns c
            LEFT JOIN ad_performance p ON c.id = p.ad_campaign_id
            WHERE p.date BETWEEN $1 AND $2
            GROUP BY c.id, c.name, c.status, c.daily_budget
            ORDER BY total_cost DESC
        """, date_from.date(), date_to.date())
        
        return [
            {
                "campaign_id": r["id"],
                "campaign_name": r["name"],
                "status": r["status"],
                "daily_budget": float(r["daily_budget"] or 0),
                "metrics": {
                    "total_cost": float(r["total_cost"] or 0),
                    "total_clicks": r["total_clicks"] or 0,
                    "total_impressions": r["total_impressions"] or 0,
                    "avg_ctr": float(r["avg_ctr"] or 0),
                    "avg_cpc": float(r["avg_cpc"] or 0),
                    "total_visitors": r["total_visitors"] or 0,
                    "total_leads": r["total_leads"] or 0,
                    "total_deals": r["total_deals"] or 0,
                    "total_deals_amount": float(r["total_deals_amount"] or 0),
                    "avg_cpa": float(r["avg_cpa"] or 0) if r["avg_cpa"] else None,
                    "avg_roas": float(r["avg_roas"] or 0) if r["avg_roas"] else None,
                    "avg_roi": float(r["avg_roi"] or 0) if r["avg_roi"] else None,
                    "avg_conversion_rate": float(r["avg_conversion_rate"] or 0)
                }
            }
            for r in results
        ]
```

### 2. Детальный отчёт по кампании

```python
@router.get("/campaigns/{campaign_id}/details")
async def get_campaign_details(
    campaign_id: int,
    date_from: datetime = Query(..., description="Начальная дата"),
    date_to: datetime = Query(..., description="Конечная дата"),
    db: asyncpg.Pool = None
):
    """
    Детальный отчёт по эффективности кампании с разбивкой по дням.
    """
    async with db.acquire() as conn:
        # Общая информация о кампании
        campaign = await conn.fetchrow("""
            SELECT * FROM ad_campaigns WHERE id = $1
        """, campaign_id)
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Статистика по дням
        daily_stats = await conn.fetch("""
            SELECT 
                date,
                cost,
                clicks,
                impressions,
                ctr,
                avg_cpc,
                visitors,
                leads,
                deals,
                deals_amount,
                cpa,
                roas,
                roi,
                conversion_rate
            FROM ad_performance
            WHERE ad_campaign_id = $1
              AND date BETWEEN $2 AND $3
            ORDER BY date
        """, campaign_id, date_from.date(), date_to.date())
        
        # Итоговые метрики
        totals = await conn.fetchrow("""
            SELECT 
                SUM(cost) as total_cost,
                SUM(clicks) as total_clicks,
                SUM(leads) as total_leads,
                SUM(deals) as total_deals,
                SUM(deals_amount) as total_deals_amount
            FROM ad_performance
            WHERE ad_campaign_id = $1
              AND date BETWEEN $2 AND $3
        """, campaign_id, date_from.date(), date_to.date())
        
        total_cost = float(totals["total_cost"] or 0)
        total_leads = totals["total_leads"] or 0
        total_deals = totals["total_deals"] or 0
        total_deals_amount = float(totals["total_deals_amount"] or 0)
        
        return {
            "campaign": {
                "id": campaign["id"],
                "name": campaign["name"],
                "status": campaign["status"],
                "daily_budget": float(campaign["daily_budget"] or 0)
            },
            "period": {
                "from": date_from.date().isoformat(),
                "to": date_to.date().isoformat()
            },
            "summary": {
                "total_cost": total_cost,
                "total_clicks": totals["total_clicks"] or 0,
                "total_leads": total_leads,
                "total_deals": total_deals,
                "total_deals_amount": total_deals_amount,
                "cpa": (total_cost / total_leads) if total_leads > 0 else None,
                "roas": (total_deals_amount / total_cost) if total_cost > 0 else None,
                "roi": ((total_deals_amount - total_cost) / total_cost * 100) if total_cost > 0 else None
            },
            "daily_stats": [
                {
                    "date": r["date"].isoformat(),
                    "cost": float(r["cost"] or 0),
                    "clicks": r["clicks"] or 0,
                    "impressions": r["impressions"] or 0,
                    "ctr": float(r["ctr"] or 0),
                    "avg_cpc": float(r["avg_cpc"] or 0),
                    "visitors": r["visitors"] or 0,
                    "leads": r["leads"] or 0,
                    "deals": r["deals"] or 0,
                    "deals_amount": float(r["deals_amount"] or 0),
                    "cpa": float(r["cpa"] or 0) if r["cpa"] else None,
                    "roas": float(r["roas"] or 0) if r["roas"] else None,
                    "roi": float(r["roi"] or 0) if r["roi"] else None,
                    "conversion_rate": float(r["conversion_rate"] or 0)
                }
                for r in daily_stats
            ]
        }
```

### 3. Сравнение эффективности кампаний

```python
@router.get("/campaigns/compare")
async def compare_campaigns(
    date_from: datetime = Query(..., description="Начальная дата"),
    date_to: datetime = Query(..., description="Конечная дата"),
    metric: str = Query("roas", description="Метрика для сравнения: roas, roi, cpa, conversion_rate"),
    db: asyncpg.Pool = None
):
    """
    Сравнение эффективности кампаний по выбранной метрике.
    """
    async with db.acquire() as conn:
        results = await conn.fetch(f"""
            SELECT 
                c.id,
                c.name,
                AVG(p.{metric}) as metric_value,
                SUM(p.cost) as total_cost,
                SUM(p.leads) as total_leads,
                SUM(p.deals_amount) as total_deals_amount
            FROM ad_campaigns c
            LEFT JOIN ad_performance p ON c.id = p.ad_campaign_id
            WHERE p.date BETWEEN $1 AND $2
            GROUP BY c.id, c.name
            HAVING AVG(p.{metric}) IS NOT NULL
            ORDER BY metric_value DESC
        """, date_from.date(), date_to.date())
        
        return [
            {
                "campaign_id": r["id"],
                "campaign_name": r["name"],
                "metric": metric,
                "metric_value": float(r["metric_value"] or 0),
                "total_cost": float(r["total_cost"] or 0),
                "total_leads": r["total_leads"] or 0,
                "total_deals_amount": float(r["total_deals_amount"] or 0)
            }
            for r in results
        ]
```

---

## Ключевые метрики

### 1. CPA (Cost Per Acquisition) — стоимость привлечения лида

```
CPA = Расходы на рекламу / Количество лидов
```

**Интерпретация:**
- Чем ниже CPA, тем эффективнее кампания
- CPA должен быть меньше среднего дохода с лида
- Целевой CPA обычно составляет 20-30% от стоимости сделки

### 2. ROAS (Return On Ad Spend) — возврат на рекламу

```
ROAS = Доход от сделок / Расходы на рекламу
```

**Интерпретация:**
- ROAS > 1 означает, что реклама окупается
- ROAS > 3 считается хорошим показателем
- ROAS < 1 означает убыточность рекламы

### 3. ROI (Return On Investment) — возврат инвестиций

```
ROI = (Доход от сделок - Расходы на рекламу) / Расходы на рекламу * 100%
```

**Интерпретация:**
- ROI > 0% означает прибыльность
- ROI > 100% считается отличным показателем
- ROI < 0% означает убыточность

### 4. Conversion Rate — конверсия

```
Conversion Rate = Количество лидов / Количество посетителей * 100%
```

**Интерпретация:**
- Показывает, какой процент посетителей становится лидами
- Средняя конверсия для недвижимости: 2-5%
- Конверсия > 5% считается хорошей

---

## Рекомендации по оптимизации

### На основе метрик

1. **Если CPA высокий:**
   - Улучшить таргетинг (сузить аудиторию)
   - Оптимизировать объявления (улучшить CTR)
   - Улучшить посадочные страницы (повысить конверсию)

2. **Если ROAS низкий:**
   - Перераспределить бюджет на более эффективные кампании
   - Остановить убыточные кампании
   - Улучшить воронку продаж

3. **Если конверсия низкая:**
   - Улучшить посадочные страницы
   - Оптимизировать форму обратной связи
   - Улучшить UX сайта

---

## Переменные окружения

Добавьте в `.env`:

```bash
# Яндекс.Директ
YANDEX_DIRECT_OAUTH_TOKEN=AQAAAAA1234567890abcdefghijklmnopqrstuvwxyz
YANDEX_DIRECT_LOGIN=your-direct-login
YANDEX_DIRECT_CLIENT_ID=1234567890abcdef1234567890abcdef
YANDEX_DIRECT_CLIENT_SECRET=abcdef1234567890abcdef1234567890abcdef
```

---

## Полезные ссылки

- [Документация Яндекс.Директ API](https://yandex.ru/dev/direct/doc/dg-v4/ru/)
- [Методы API Яндекс.Директ](https://yandex.ru/dev/direct/doc/dg-v4/reference/Reports-docpage/)
- [Интеграция с Яндекс.Метрикой](https://yandex.ru/support/metrica/general/connection-direct.html)

---

## Чек-лист настройки

- [ ] Настроен доступ к Яндекс.Директ API (OAuth токен, Login)
- [ ] Созданы таблицы `ad_campaigns` и `ad_performance`
- [ ] Настроена синхронизация кампаний из Яндекс.Директ
- [ ] Настроена синхронизация статистики по кампаниям
- [ ] Настроено связывание событий из Яндекс.Метрики с кампаниями
- [ ] Настроено связывание лидов и сделок из amoCRM с кампаниями
- [ ] Протестированы отчёты по эффективности
- [ ] Настроены периодические синхронизации (например, раз в день)

