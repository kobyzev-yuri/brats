# Анализ трекеров сайта innovatory-club.ru для интеграции с нейроаналитикой

**Дата анализа:** 2025-02-07  
**URL:** https://innovatory-club.ru/katalog#!/tab/1063728081-4

---

## 🔍 Обнаруженные трекеры

### 1. Яндекс.Метрика ✅

**Статус:** Установлена и активна

**ID счетчика:** `103165578`

**Обнаруженные компоненты:**
- ✅ Основной скрипт: `https://mc.yandex.ru/metrika/tag.js`
- ✅ Отслеживание звонков: `https://mc.yandex.ru/metrika/tag_phono.js`
- ✅ Карта кликов (ClickMap): `https://mc.yandex.ru/clmap/103165578`
- ✅ WebSocket для realtime: `wss://mc.yandex.ru/solid.ws`

**Отслеживаемые события:**
- Просмотры страниц
- Клики по элементам (карта кликов активна)
- Звонки (через tag_phono.js)
- Параметры посетителей (User-Agent, разрешение экрана, и т.д.)

**Пример запроса к API:**
```
GET https://mc.yandex.ru/watch/103165578/1
```

---

### 2. Google Analytics 4 ✅

**Статус:** Установлен и активен

**ID счетчика:** `G-EL64TX9FWD`

**Обнаруженные компоненты:**
- ✅ Google Tag Manager: `https://www.googletagmanager.com/gtag/js?id=G-EL64TX9FWD`
- ✅ Сбор данных: `https://www.google-analytics.com/g/collect`

**Отслеживаемые события:**
- Просмотры страниц (page_view)
- Параметры посетителей
- Конверсии (если настроены цели)

---

### 3. Tilda Statistics ✅

**Статус:** Установлена и активна

**Обнаруженные компоненты:**
- ✅ События: `https://stat.tildaapi.com/event/` (POST запросы)
- ✅ Статистика Tilda: `https://static.tildacdn.com/js/tilda-stat-1.0.min.js`

**Отслеживаемые события:**
- События форм Tilda
- Взаимодействия с элементами страницы
- Геолокация: `https://geo.tildaapi.com/geo/country/`

---

## 📊 Структура сайта и точки конверсии

### Формы на сайте

1. **Форма резервирования BLACK BOX**
   - Поля: Имя, Телефон, Чекбокс согласия
   - Действие: Резервирование коттеджа с черновой отделкой
   - Стоимость: 8 350 000 ₽

2. **Форма резервирования WHITE BOX**
   - Поля: Имя, Телефон, Чекбокс согласия
   - Действие: Резервирование коттеджа с предчистовой отделкой
   - Стоимость: 8 950 000 ₽

3. **Форма резервирования STANDARD**
   - Поля: Имя, Телефон, Чекбокс согласия
   - Действие: Резервирование коттеджа со стандартным ремонтом
   - Стоимость: 8 950 000 ₽

4. **Форма резервирования DESIGN**
   - Поля: Имя, Телефон, Чекбокс согласия
   - Действие: Резервирование коттеджа с дизайнерским ремонтом
   - Стоимость: 8 950 000 ₽ + 1 500 000 ₽ (ремонт)

5. **Форма расчета ипотеки**
   - Поля: Тип отделки, Первоначальный взнос, Сумма кредита
   - Действие: Расчет ипотеки

6. **Форма записи на просмотр**
   - Поля: Имя, Телефон, Чекбокс согласия
   - Действие: Запись на просмотр дома

### Ключевые элементы взаимодействия

- Кнопки "ОТПРАВИТЬ ЗАПРОС" и "В КАТАЛОГ"
- Переключение между типами отделки (BLACK BOX, WHITE BOX, STANDARD, DESIGN)
- Просмотр планировок
- Просмотр фотогалереи
- Просмотр видеообзора (встроен Google Drive)
- Клики по телефону: `+7 (988) 199-89-98`
- Клики по WhatsApp

---

## 🔗 Интеграция с нейроаналитикой

### 1. Получение данных из Яндекс.Метрики

#### API доступ

**Требуется:**
- OAuth токен с правами `metrika:read`
- Counter ID: `103165578`

**Эндпоинты для интеграции:**

```python
# Realtime данные (онлайн посетители)
GET https://api-metrika.yandex.net/management/v1/counter/103165578/realtime

# Статистика за период
GET https://api-metrika.yandex.net/management/v1/counter/103165578/stats/v1/data

# Цели и конверсии
GET https://api-metrika.yandex.net/management/v1/counter/103165578/goals

# Вебвизор (записи сессий)
GET https://api-metrika.yandex.net/management/v1/counter/103165578/visits
```

#### Ключевые метрики для нейроаналитики

1. **Поведенческие метрики:**
   - Время на сайте
   - Глубина просмотра
   - Отказы
   - Карта кликов (уже активна)

2. **Конверсионные метрики:**
   - Отправка форм (цели в Метрике)
   - Клики по телефону
   - Клики по WhatsApp
   - Просмотр планировок
   - Просмотр видео

3. **Сегментация:**
   - Источники трафика
   - Устройства (мобильные/десктоп)
   - География
   - Возвращающиеся посетители

---

### 2. Настройка целей в Яндекс.Метрике

#### Рекомендуемые цели для отслеживания:

1. **Цель: Отправка формы резервирования**
   - Тип: JavaScript-событие
   - Событие: `form_submit`
   - Параметры: `form_type` (black_box, white_box, standard, design)

2. **Цель: Клик по телефону**
   - Тип: JavaScript-событие
   - Событие: `phone_click`

3. **Цель: Клик по WhatsApp**
   - Тип: JavaScript-событие
   - Событие: `whatsapp_click`

4. **Цель: Просмотр планировки**
   - Тип: JavaScript-событие
   - Событие: `plan_view`

5. **Цель: Просмотр видео**
   - Тип: JavaScript-событие
   - Событие: `video_view`

6. **Цель: Расчет ипотеки**
   - Тип: JavaScript-событие
   - Событие: `mortgage_calculate`

#### JavaScript для отправки событий:

```javascript
// Отправка формы резервирования
ym(103165578, 'reachGoal', 'form_reservation', {
    form_type: 'black_box', // или white_box, standard, design
    price: 8350000
});

// Клик по телефону
ym(103165578, 'reachGoal', 'phone_click');

// Клик по WhatsApp
ym(103165578, 'reachGoal', 'whatsapp_click');

// Просмотр планировки
ym(103165578, 'reachGoal', 'plan_view', {
    plan_type: 'first_floor' // или second_floor
});

// Просмотр видео
ym(103165578, 'reachGoal', 'video_view');

// Расчет ипотеки
ym(103165578, 'reachGoal', 'mortgage_calculate', {
    initial_payment: 200000,
    loan_amount: 10500000,
    renovation_type: 'standard'
});
```

---

### 3. Интеграция с системой нейроаналитики

#### Архитектура интеграции

```
┌─────────────────┐
│  Сайт Tilda     │
│  (innovatory-   │
│   club.ru)      │
└────────┬────────┘
         │
         ├─► Яндекс.Метрика (103165578)
         │   └─► API ──┐
         │             │
         ├─► Google Analytics (G-EL64TX9FWD)
         │             │
         └─► Tilda Statistics
                     │
                     ▼
         ┌───────────────────────┐
         │  Analytics Service    │
         │  (FastAPI)            │
         └───────────┬────────────┘
                     │
         ┌───────────┴────────────┐
         │                        │
         ▼                        ▼
┌─────────────────┐    ┌──────────────────┐
│  PostgreSQL     │    │  Redis Cache     │
│  (events)       │    │  (realtime)      │
└─────────────────┘    └──────────────────┘
         │
         ▼
┌─────────────────┐
│  Нейроаналитик  │
│  (LLM Agent)    │
└─────────────────┘
```

#### Код интеграции

**Файл:** `analytics-service/integrations/yandex_metrika.py`

```python
import os
import httpx
from typing import Dict, List, Optional
from datetime import datetime, timedelta

class YandexMetrikaClient:
    """Клиент для работы с API Яндекс.Метрики"""
    
    def __init__(self):
        self.counter_id = "103165578"  # ID счетчика сайта
        self.oauth_token = os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
        self.base_url = "https://api-metrika.yandex.net/management/v1"
        
        if not self.oauth_token:
            raise ValueError("YANDEX_METRIKA_OAUTH_TOKEN not set")
    
    async def get_realtime_visitors(self) -> Dict:
        """Получить онлайн посетителей"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/realtime",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_goals(self) -> List[Dict]:
        """Получить список целей"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/goals",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            response.raise_for_status()
            return response.json()["goals"]
    
    async def get_conversions(
        self,
        date_from: str,
        date_to: str,
        metrics: List[str] = None
    ) -> Dict:
        """Получить конверсии за период"""
        if metrics is None:
            metrics = ["ym:s:goal<goal_id>visits", "ym:s:goal<goal_id>reaches"]
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/stats/v1/data",
                headers={"Authorization": f"OAuth {self.oauth_token}"},
                params={
                    "date1": date_from,
                    "date2": date_to,
                    "metrics": ",".join(metrics),
                    "dimensions": "ym:s:goal<goal_id>"
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_clickmap_data(
        self,
        date_from: str,
        date_to: str
    ) -> Dict:
        """Получить данные карты кликов"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/clmap",
                headers={"Authorization": f"OAuth {self.oauth_token}"},
                params={
                    "date1": date_from,
                    "date2": date_to
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_visits_with_webvisor(
        self,
        date_from: str,
        date_to: str,
        limit: int = 100
    ) -> List[Dict]:
        """Получить визиты с вебвизором"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/visits",
                headers={"Authorization": f"OAuth {self.oauth_token}"},
                params={
                    "date1": date_from,
                    "date2": date_to,
                    "limit": limit,
                    "filters": "ym:s:hasWebVisor==1"
                }
            )
            response.raise_for_status()
            return response.json()["visits"]
```

**Файл:** `analytics-service/service/metrika_sync.py`

```python
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import asyncpg
from integrations.yandex_metrika import YandexMetrikaClient

async def sync_metrika_events_to_db(
    db_pool: asyncpg.Pool,
    days_back: int = 1
):
    """Синхронизация событий из Яндекс.Метрики в БД"""
    client = YandexMetrikaClient()
    
    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    date_to = datetime.now().strftime("%Y-%m-%d")
    
    # Получаем конверсии
    conversions = await client.get_conversions(date_from, date_to)
    
    async with db_pool.acquire() as conn:
        for conversion in conversions.get("data", []):
            await conn.execute("""
                INSERT INTO analytics_events (
                    event_type,
                    event_data,
                    source,
                    created_at
                ) VALUES ($1, $2, $3, $4)
                ON CONFLICT DO NOTHING
            """, 
                "conversion",
                conversion,
                "yandex_metrika",
                datetime.now()
            )
    
    # Получаем данные карты кликов
    clickmap = await client.get_clickmap_data(date_from, date_to)
    
    async with db_pool.acquire() as conn:
        for click in clickmap.get("clicks", []):
            await conn.execute("""
                INSERT INTO analytics_events (
                    event_type,
                    event_data,
                    source,
                    created_at
                ) VALUES ($1, $2, $3, $4)
            """,
                "click",
                click,
                "yandex_metrika",
                datetime.now()
            )
```

---

### 4. Инициация нейропродажника на основе аналитики

#### Триггеры для запуска нейропродажника

1. **Высокий интерес (High Intent):**
   - Просмотр 3+ типов отделки
   - Просмотр планировок
   - Просмотр видео
   - Время на сайте > 5 минут
   - Возврат на сайт

2. **Критические действия:**
   - Заполнение формы (но не отправка)
   - Клик по телефону
   - Клик по WhatsApp
   - Расчет ипотеки

3. **Сегментация по цене:**
   - Интерес к DESIGN (самый дорогой вариант)
   - Интерес к BLACK BOX (самый дешевый)
   - Расчет ипотеки с определенной суммой

#### Код инициации

**Файл:** `neuro-sales-service/triggers/analytics_trigger.py`

```python
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncpg
from neuro_sales.agent import NeuroSalesAgent

class AnalyticsTrigger:
    """Триггер для запуска нейропродажника на основе аналитики"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self.agent = NeuroSalesAgent()
    
    async def check_high_intent_visitor(
        self,
        visitor_id: str,
        session_id: str
    ) -> bool:
        """Проверить, является ли посетитель высокоинтересным"""
        async with self.db.acquire() as conn:
            # Проверяем события за последний час
            events = await conn.fetch("""
                SELECT event_type, event_data
                FROM analytics_events
                WHERE visitor_id = $1
                  AND session_id = $2
                  AND created_at > NOW() - INTERVAL '1 hour'
                  AND source = 'yandex_metrika'
            """, visitor_id, session_id)
            
            # Подсчитываем метрики интереса
            renovation_views = sum(1 for e in events if 'renovation_type' in str(e['event_data']))
            plan_views = sum(1 for e in events if e['event_type'] == 'plan_view')
            video_views = sum(1 for e in events if e['event_type'] == 'video_view')
            
            # Критерии высокого интереса
            if renovation_views >= 3 or plan_views > 0 or video_views > 0:
                return True
            
            return False
    
    async def trigger_neuro_sales(
        self,
        visitor_id: str,
        session_id: str,
        trigger_reason: str
    ):
        """Запустить нейропродажника для посетителя"""
        # Получаем контекст посетителя
        context = await self.get_visitor_context(visitor_id, session_id)
        
        # Инициируем диалог
        await self.agent.initiate_conversation(
            visitor_id=visitor_id,
            context=context,
            trigger_reason=trigger_reason
        )
    
    async def get_visitor_context(
        self,
        visitor_id: str,
        session_id: str
    ) -> Dict:
        """Получить контекст посетителя для нейропродажника"""
        async with self.db.acquire() as conn:
            # Получаем все события посетителя
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
            for event in events:
                if event['event_type'] == 'conversion':
                    data = event['event_data']
                    if 'form_type' in data:
                        interests.append(f"Интерес к {data['form_type']}")
                    if 'renovation_type' in data:
                        interests.append(f"Рассматривает {data['renovation_type']}")
            
            return {
                "visitor_id": visitor_id,
                "session_id": session_id,
                "interests": interests,
                "events_count": len(events),
                "last_activity": events[0]['created_at'] if events else None
            }
```

---

## 📋 Чеклист интеграции

### Этап 1: Настройка Яндекс.Метрики

- [ ] Получить OAuth токен с правами `metrika:read`
- [ ] Сохранить токен в `.env`: `YANDEX_METRIKA_OAUTH_TOKEN`
- [ ] Сохранить Counter ID: `YANDEX_METRIKA_COUNTER_ID=103165578`
- [ ] Настроить цели в Метрике (см. раздел выше)
- [ ] Добавить JavaScript события на сайте (см. код выше)

### Этап 2: Разработка интеграции

- [ ] Создать `YandexMetrikaClient` (код выше)
- [ ] Реализовать синхронизацию событий в БД
- [ ] Настроить периодическую синхронизацию (cron/задача)
- [ ] Протестировать получение данных из API

### Этап 3: Интеграция с нейроаналитикой

- [ ] Создать таблицу `analytics_events` (если еще нет)
- [ ] Настроить обработку событий из Метрики
- [ ] Реализовать анализ поведения посетителей
- [ ] Создать триггеры для нейропродажника

### Этап 4: Запуск нейропродажника

- [ ] Реализовать `AnalyticsTrigger` (код выше)
- [ ] Настроить условия запуска агента
- [ ] Протестировать инициацию диалога
- [ ] Настроить мониторинг эффективности

---

## 🔐 Безопасность и соответствие 152-ФЗ

### Требования

1. **Обезличивание данных:**
   - IP-адреса должны хешироваться
   - Cookie ID не должны содержать ПДн
   - Геолокация только на уровне города

2. **Согласие на обработку:**
   - Чекбокс согласия уже есть в формах
   - Необходимо логировать согласие

3. **Хранение данных:**
   - Данные аналитики хранить отдельно от ПДн
   - Использовать псевдонимы для связки данных

---

## 📊 Метрики эффективности

### KPI для отслеживания

1. **Конверсия:**
   - Посещения → Заполнение формы
   - Посещения → Клик по телефону
   - Посещения → Клик по WhatsApp

2. **Эффективность нейропродажника:**
   - Количество инициаций диалога
   - Конверсия диалога → Заявка
   - Средний чек по сегментам

3. **Поведенческие метрики:**
   - Время до первого действия
   - Глубина просмотра
   - Возвраты на сайт

---

## 🔗 Полезные ссылки

- [Документация API Яндекс.Метрики](https://yandex.ru/dev/metrika/)
- [Настройка OAuth для Метрики](https://yandex.ru/dev/id/doc/ru/)
- [JavaScript API Метрики](https://yandex.ru/support/metrica/code/counter-initialize.html)
- [Документация проекта](../README.md#аналитика)

---

## 📝 Примечания

1. **Google Analytics:** Также установлен, но для соответствия 152-ФЗ рекомендуется использовать только Яндекс.Метрику или настроить обезличивание данных в GA.

2. **Tilda Statistics:** Может быть дополнительным источником данных, но основной фокус на Яндекс.Метрике.

3. **Вебвизор:** Уже активен в Метрике, можно использовать для анализа поведения посетителей.

4. **Карта кликов:** Активна, данные доступны через API.

---

**Следующие шаги:**
1. Получить OAuth токен для API Яндекс.Метрики
2. Реализовать интеграцию по коду выше
3. Настроить цели в Метрике
4. Протестировать синхронизацию данных
5. Запустить нейропродажника на основе аналитики


