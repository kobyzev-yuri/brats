# Активация нейропродажника через онлайн-аналитику трекеров

## ✅ Да, онлайн-аналитика позволяет активировать нейропродажника!

Система поддерживает **реал-тайм активацию нейропродажника** на основе анализа данных от трекеров (Яндекс.Метрика, Google Analytics, Tilda Statistics) в режиме онлайн.

---

## 🔄 Архитектура потока данных

```
┌─────────────────────┐
│ Яндекс.Метрика      │
│ (Realtime API)      │  ← События в реальном времени
│ WebSocket/Webhook   │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│   n8n (триггер)     │  ← Обработка событий
│   Webhook/HTTP       │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Нейроаналитик       │
│ (онлайн-модуль)     │
│                     │
│ • Анализ паттернов  │
│ • Определение       │
│   "горячего" лида   │
│ • Оценка интереса   │
└──────────┬──────────┘
           │
           ↓ (если триггер сработал)
┌─────────────────────┐
│   n8n (workflow)    │
│   Инициация продажника│
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Нейропродажник      │
│ (FSM: PROPOSAL)     │  ← Активирован!
│                     │
│ • Инициация диалога │
│ • Квалификация      │
│ • Генерация КП      │
└─────────────────────┘
```

---

## 🎯 Триггеры для активации

### 1. Высокий интерес (High Intent)

**Критерии:**
- ✅ Просмотр 3+ типов отделки (BLACK BOX, WHITE BOX, STANDARD, DESIGN)
- ✅ Просмотр планировок (более 30 секунд)
- ✅ Просмотр видеообзора (более 1 минуты)
- ✅ Время на сайте > 5 минут
- ✅ Возврат на сайт (2+ визита)
- ✅ Глубина просмотра > 10 страниц

**Пример события:**
```json
{
  "visitor_id": "visitor_123",
  "session_id": "session_456",
  "events": [
    {"type": "renovation_view", "data": {"type": "black_box"}},
    {"type": "renovation_view", "data": {"type": "white_box"}},
    {"type": "renovation_view", "data": {"type": "standard"}},
    {"type": "plan_view", "data": {"duration": 45}},
    {"type": "time_on_site", "data": {"seconds": 320}}
  ],
  "intent_score": 0.85  // Высокий интерес
}
```

### 2. Критические действия

**Критерии:**
- ✅ Заполнение формы (но не отправка) — пользователь начал, но не завершил
- ✅ Клик по телефону (`+7 (988) 199-89-98`)
- ✅ Клик по WhatsApp
- ✅ Расчет ипотеки (заполнение калькулятора)
- ✅ Просмотр цены на DESIGN (самый дорогой вариант)

**Пример события:**
```json
{
  "visitor_id": "visitor_123",
  "event_type": "phone_click",
  "timestamp": "2025-02-07T15:30:00Z",
  "page_url": "/katalog",
  "intent_score": 0.95  // Очень высокий интерес
}
```

### 3. Сегментация по цене

**Критерии:**
- ✅ Интерес к DESIGN (самый дорогой: 8.95M + 1.5M ремонт)
- ✅ Расчет ипотеки с суммой > 10M
- ✅ Просмотр всех типов отделки (сравнение цен)

---

## 💻 Реализация

### Шаг 1: Получение онлайн-данных из Яндекс.Метрики

**API Endpoint:**
```python
GET https://api-metrika.yandex.net/management/v1/counter/103165578/realtime
```

**Пример кода:**
```python
from integrations.yandex_metrika import YandexMetrikaClient

async def monitor_realtime_visitors():
    """Мониторинг онлайн посетителей"""
    client = YandexMetrikaClient()
    
    while True:
        # Получаем онлайн посетителей
        visitors = await client.get_realtime_visitors()
        
        for visitor in visitors:
            # Анализируем поведение
            intent_score = await analyze_visitor_intent(visitor)
            
            # Если высокий интерес - активируем нейропродажника
            if intent_score > 0.7:
                await trigger_sales_agent(visitor)
        
        await asyncio.sleep(30)  # Проверка каждые 30 секунд
```

### Шаг 2: Анализ паттернов поведения

**Файл:** `analytics-service/agents/online_analyst.py`

```python
from typing import Dict, List
import asyncpg
from datetime import datetime, timedelta

class OnlineAnalyst:
    """Онлайн-аналитик для определения горячих лидов"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
    
    async def analyze_visitor_intent(
        self,
        visitor_id: str,
        session_id: str
    ) -> float:
        """
        Анализирует поведение посетителя и возвращает score интереса (0-1)
        """
        async with self.db.acquire() as conn:
            # Получаем события за последний час
            events = await conn.fetch("""
                SELECT event_type, event_data, created_at
                FROM analytics_events
                WHERE visitor_id = $1
                  AND session_id = $2
                  AND created_at > NOW() - INTERVAL '1 hour'
                  AND source = 'yandex_metrika'
                ORDER BY created_at DESC
            """, visitor_id, session_id)
            
            if not events:
                return 0.0
            
            score = 0.0
            
            # Анализ типов событий
            renovation_views = sum(1 for e in events if 'renovation_type' in str(e['event_data']))
            plan_views = sum(1 for e in events if e['event_type'] == 'plan_view')
            video_views = sum(1 for e in events if e['event_type'] == 'video_view')
            phone_clicks = sum(1 for e in events if e['event_type'] == 'phone_click')
            whatsapp_clicks = sum(1 for e in events if e['event_type'] == 'whatsapp_click')
            form_starts = sum(1 for e in events if e['event_type'] == 'form_start')
            mortgage_calculations = sum(1 for e in events if e['event_type'] == 'mortgage_calculate')
            
            # Подсчет score
            if renovation_views >= 3:
                score += 0.3  # Просмотрел все типы отделки
            if plan_views > 0:
                score += 0.2  # Смотрел планировки
            if video_views > 0:
                score += 0.2  # Смотрел видео
            if phone_clicks > 0:
                score += 0.4  # Кликнул по телефону (критично!)
            if whatsapp_clicks > 0:
                score += 0.4  # Кликнул по WhatsApp (критично!)
            if form_starts > 0:
                score += 0.3  # Начал заполнять форму
            if mortgage_calculations > 0:
                score += 0.3  # Рассчитывал ипотеку
            
            # Анализ времени на сайте
            if events:
                first_event = min(e['created_at'] for e in events)
                last_event = max(e['created_at'] for e in events)
                time_on_site = (last_event - first_event).total_seconds()
                
                if time_on_site > 300:  # > 5 минут
                    score += 0.2
            
            # Анализ глубины просмотра
            unique_pages = len(set(e.get('page_url', '') for e in events))
            if unique_pages > 10:
                score += 0.2
            
            return min(score, 1.0)  # Ограничиваем до 1.0
    
    async def is_high_intent_visitor(
        self,
        visitor_id: str,
        session_id: str,
        threshold: float = 0.7
    ) -> bool:
        """Проверяет, является ли посетитель высокоинтересным"""
        score = await self.analyze_visitor_intent(visitor_id, session_id)
        return score >= threshold
```

### Шаг 3: Активация нейропродажника

**Файл:** `analytics-service/triggers/sales_agent_trigger.py`

```python
import httpx
from typing import Dict, Optional
import asyncpg

class SalesAgentTrigger:
    """Триггер для активации нейропродажника"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self.sales_agent_url = "http://localhost:8000/api/chat/initiate"
        self.n8n_webhook_url = "http://localhost:5678/webhook/trigger-sales-agent"
    
    async def trigger_sales_agent(
        self,
        visitor_id: str,
        session_id: str,
        trigger_reason: str,
        context: Dict
    ):
        """
        Активирует нейропродажника через n8n webhook
        """
        # Получаем контекст посетителя
        visitor_context = await self.get_visitor_context(visitor_id, session_id)
        
        # Формируем payload для n8n
        payload = {
            "visitor_id": visitor_id,
            "session_id": session_id,
            "trigger_reason": trigger_reason,
            "context": {
                **visitor_context,
                **context
            },
            "channel": "site",  # или определяем по источнику
            "metadata": {
                "source": "online_analytics",
                "intent_score": context.get("intent_score", 0.0),
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Отправляем в n8n
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.n8n_webhook_url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
        
        # Логируем активацию
        await self.log_activation(visitor_id, session_id, trigger_reason)
    
    async def get_visitor_context(
        self,
        visitor_id: str,
        session_id: str
    ) -> Dict:
        """Получает контекст посетителя для нейропродажника"""
        async with self.db.acquire() as conn:
            events = await conn.fetch("""
                SELECT event_type, event_data, created_at
                FROM analytics_events
                WHERE visitor_id = $1
                  AND session_id = $2
                ORDER BY created_at DESC
                LIMIT 50
            """, visitor_id, session_id)
            
            # Анализируем интересы
            interests = []
            viewed_renovations = set()
            
            for event in events:
                data = event['event_data']
                if isinstance(data, dict):
                    if 'renovation_type' in data:
                        viewed_renovations.add(data['renovation_type'])
                    if event['event_type'] == 'plan_view':
                        interests.append("Просматривал планировки")
                    if event['event_type'] == 'video_view':
                        interests.append("Смотрел видеообзор")
                    if event['event_type'] == 'mortgage_calculate':
                        interests.append("Рассчитывал ипотеку")
            
            return {
                "visitor_id": visitor_id,
                "session_id": session_id,
                "interests": interests,
                "viewed_renovations": list(viewed_renovations),
                "events_count": len(events),
                "last_activity": events[0]['created_at'].isoformat() if events else None
            }
    
    async def log_activation(
        self,
        visitor_id: str,
        session_id: str,
        trigger_reason: str
    ):
        """Логирует активацию нейропродажника"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO analytics_events (
                    event_type,
                    event_data,
                    source,
                    visitor_id,
                    session_id,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
                "sales_agent_triggered",
                {"reason": trigger_reason},
                "online_analytics",
                visitor_id,
                session_id,
                datetime.now()
            )
```

### Шаг 4: n8n Workflow для обработки триггера

**Workflow:** `n8n/workflows/online-analytics-trigger-sales-agent.json`

```json
{
  "name": "Online Analytics → Sales Agent",
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "trigger-sales-agent",
        "httpMethod": "POST"
      }
    },
    {
      "name": "Check Intent Score",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "number": [
            {
              "value1": "={{ $json.context.intent_score }}",
              "operation": "largerEqual",
              "value2": 0.7
            }
          ]
        }
      }
    },
    {
      "name": "Get Visitor Context",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "GET",
        "url": "http://analytics-service:8002/api/visitor/{{ $json.visitor_id }}/context"
      }
    },
    {
      "name": "Initiate Sales Agent",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://sales-agent:8000/api/chat/initiate",
        "body": {
          "visitor_id": "={{ $json.visitor_id }}",
          "channel": "site",
          "context": "={{ $json.context }}",
          "trigger_reason": "={{ $json.trigger_reason }}"
        }
      }
    },
    {
      "name": "Create Lead in amoCRM",
      "type": "n8n-nodes-base.amocrm",
      "parameters": {
        "operation": "create",
        "resource": "lead",
        "name": "Лид с сайта ({{ $json.visitor_id }})",
        "pipeline_id": 12345,
        "status_id": 123456
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Check Intent Score"}]]
    },
    "Check Intent Score": {
      "main": [
        [{"node": "Get Visitor Context"}],
        [{"node": "End"}]
      ]
    },
    "Get Visitor Context": {
      "main": [[{"node": "Initiate Sales Agent"}]]
    },
    "Initiate Sales Agent": {
      "main": [[{"node": "Create Lead in amoCRM"}]]
    }
  }
}
```

---

## ⚡ Режимы работы

### 1. Polling (опрос API)

**Как работает:**
- Нейроаналитик периодически опрашивает Realtime API Яндекс.Метрики
- Интервал: каждые 30-60 секунд
- Анализирует новых посетителей и их поведение

**Плюсы:**
- Простая реализация
- Не требует настройки webhook в Метрике

**Минусы:**
- Задержка до 60 секунд
- Дополнительная нагрузка на API

### 2. WebSocket (реал-тайм)

**Как работает:**
- Подключение к WebSocket Яндекс.Метрики: `wss://mc.yandex.ru/solid.ws`
- Получение событий в реальном времени
- Мгновенная реакция на действия посетителей

**Плюсы:**
- Минимальная задержка (< 1 секунда)
- Эффективное использование ресурсов

**Минусы:**
- Требует поддержки WebSocket соединения
- Более сложная реализация

### 3. Webhook от сайта (альтернативный подход)

**Как работает:**
- ⚠️ **Важно**: Яндекс.Метрика НЕ предоставляет webhook для отправки событий на внешние серверы
- Вместо этого можно настроить webhook на стороне сайта (Tilda)
- JavaScript на сайте отправляет события в n8n webhook при действиях пользователя
- n8n обрабатывает события и может дополнять их данными из Метрики через API

**Документация:** Полный код для интеграции находится в [`site-integration/SITE_INTEGRATION_CODE.md`](../site-integration/SITE_INTEGRATION_CODE.md)

**Плюсы:**
- Минимальная задержка (события отправляются сразу)
- Полный контроль над событиями
- Можно отправлять кастомные события

**Минусы:**
- Требует изменения кода на сайте (добавление JavaScript)
- Нужен публичный URL для приема webhook
- Дублирование событий (и в Метрику, и в n8n)

---

## 📊 Примеры сценариев

### Сценарий 1: Посетитель с высоким интересом

**Хронология:**
1. 10:00 — Посетитель зашел на сайт
2. 10:02 — Просмотрел BLACK BOX
3. 10:03 — Просмотрел WHITE BOX
4. 10:04 — Просмотрел STANDARD
5. 10:05 — Просмотрел планировки (45 секунд)
6. 10:06 — **Триггер сработал** (intent_score = 0.75)
7. 10:06 — Нейропродажник инициирован
8. 10:06 — Отправлено сообщение: "Здравствуйте! Вижу, вы интересуетесь нашими коттеджами. Помогу подобрать оптимальный вариант?"

### Сценарий 2: Критическое действие

**Хронология:**
1. 14:30 — Посетитель зашел на сайт
2. 14:31 — Кликнул по телефону `+7 (988) 199-89-98`
3. 14:31 — **Триггер сработал** (intent_score = 0.95)
4. 14:31 — Нейропродажник инициирован
5. 14:31 — Создан лид в amoCRM с меткой "Горячий лид"
6. 14:32 — Отправлено сообщение: "Спасибо за интерес! Готов ответить на ваши вопросы. Какой вариант отделки вас интересует?"

### Сценарий 3: Возвращающийся посетитель

**Хронология:**
1. 09:00 — Первый визит (просмотрел 2 типа отделки)
2. 15:00 — Второй визит (вернулся на сайт)
3. 15:01 — Просмотрел DESIGN (самый дорогой)
4. 15:02 — Рассчитал ипотеку (сумма 10.5M)
5. 15:02 — **Триггер сработал** (intent_score = 0.80)
6. 15:02 — Нейропродажник инициирован с контекстом: "Возвращающийся посетитель, интерес к премиум-варианту"

---

## 🔧 Настройка порогов

### Рекомендуемые пороги intent_score

```python
# Критические действия (немедленная активация)
CRITICAL_THRESHOLD = 0.9  # Клик по телефону, WhatsApp

# Высокий интерес (быстрая активация)
HIGH_INTENT_THRESHOLD = 0.7  # Просмотр 3+ типов, планировок, видео

# Средний интерес (активация с задержкой)
MEDIUM_INTENT_THRESHOLD = 0.5  # Просмотр 2 типов, время > 3 минут

# Низкий интерес (не активировать)
LOW_INTENT_THRESHOLD = 0.3  # Только просмотр главной страницы
```

### Настройка в коде

```python
# analytics-service/config.py
ONLINE_ANALYTICS_CONFIG = {
    "intent_thresholds": {
        "critical": 0.9,
        "high": 0.7,
        "medium": 0.5
    },
    "polling_interval": 30,  # секунды
    "max_events_per_visitor": 50,
    "time_window_hours": 1
}
```

---

## ✅ Преимущества онлайн-активации

1. **Мгновенная реакция** — активация в течение секунд после действия посетителя
2. **Высокая конверсия** — контакт в момент максимального интереса
3. **Персонализация** — контекст из аналитики передается нейропродажнику
4. **Автоматизация** — не требует участия менеджера
5. **Масштабируемость** — обработка множества посетителей одновременно

---

## ⚠️ Ограничения и рекомендации

### Ограничения

1. **Задержка данных:**
   - Realtime API может иметь задержку до 1-2 минут
   - WebSocket более оперативен, но требует стабильного соединения

2. **Идентификация посетителя:**
   - Анонимные посетители идентифицируются по cookie/session
   - После деанонимизации можно связать с контактом в amoCRM

3. **Ложные срабатывания:**
   - Нужна настройка порогов для минимизации ложных активаций
   - Рекомендуется A/B тестирование порогов

### Рекомендации

1. **Начать с высоких порогов** (0.8-0.9) для минимизации ложных срабатываний
2. **Мониторить эффективность** — отслеживать конверсию активированных лидов
3. **Настроить rate limiting** — не активировать для одного посетителя чаще 1 раза в час
4. **Логировать все активации** — для анализа и оптимизации

---

## 📋 Чеклист внедрения

- [ ] Настроить Realtime API Яндекс.Метрики
- [ ] Реализовать `OnlineAnalyst` для анализа поведения
- [ ] Реализовать `SalesAgentTrigger` для активации
- [ ] Создать n8n workflow для обработки триггеров
- [ ] Настроить пороги intent_score
- [ ] Протестировать на реальных данных
- [ ] Настроить мониторинг и логирование
- [ ] Оптимизировать пороги на основе результатов

---

## 🔗 Связанные документы

- [`SITE_ANALYTICS_INTEGRATION_ANALYSIS.md`](./SITE_ANALYTICS_INTEGRATION_ANALYSIS.md) — анализ трекеров сайта
- [`ANALYTICS_REPORTS_AND_CONVERSION.md`](./ANALYTICS_REPORTS_AND_CONVERSION.md) — онлайн и оффлайн отчёты
- [`YANDEX_METRIKA_API_SETUP.md`](./YANDEX_METRIKA_API_SETUP.md) — настройка API Яндекс.Метрики

---

**Последнее обновление:** 2025-02-07

