# Sales Analytic Service

Сервис нейроаналитики для анализа поведения пользователей на сайте и эффективности рекламных каналов.

## 📋 Описание

Sales Analytic Service собирает и анализирует данные из:
- Яндекс.Метрики (события на сайте, поведение посетителей)
- amoCRM (лиды, сделки, конверсии)
- Сайта заказчика (через JavaScript интеграцию)

Основная цель: обнаружение "горячих" лидов и оптимизация конверсии.

## 🏗️ Структура проекта

```
sales-analytic/
├── api/                    # FastAPI endpoints
│   ├── __init__.py
│   └── main.py            # Основные эндпоинты
├── domain/                 # Бизнес-логика
│   ├── __init__.py
│   ├── models.py          # Pydantic модели для отчётов
│   ├── services.py        # Логика анализа и атрибуции
│   └── online_analyst.py  # Онлайн-аналитик для определения горячих лидов
├── integrations/           # Интеграции с внешними сервисами
│   ├── __init__.py
│   ├── metrika_client.py  # Клиент Яндекс.Метрики API
│   └── amocrm_client.py   # Клиент amoCRM API (опционально)
├── infra/                 # Инфраструктура
│   ├── __init__.py
│   ├── db.py              # Подключение к PostgreSQL/Redis
│   └── settings.py        # Конфигурация (env-переменные)
├── tests/                  # Тесты
│   ├── __init__.py
│   ├── test_domain.py     # Тесты аналитической логики
│   └── test_api.py        # Тесты HTTP-эндпоинтов
└── docs/                   # Документация
    ├── SITE_ANALYTICS_INTEGRATION_ANALYSIS.md
    ├── YANDEX_METRIKA_API_SETUP.md
    ├── YANDEX_DIRECT_EFFECTIVENESS.md
    ├── ANALYTICS_REPORTS_AND_CONVERSION.md
    ├── ANALYTICS_EVENTS_SOURCES.md
    ├── ANALYTICS_EVENTS_FOR_KB.md
    ├── ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md
    └── VISITOR_ATTENTION_AND_DEANONYMIZATION.md
```

## 🎯 Основные функции

### 1. Сбор данных
- Получение данных из Яндекс.Метрики (Realtime API, Stats API)
- Синхронизация событий с сайта заказчика
  - собственный счётчик (`POST /api/analytics/collect`) пишет события в таблицу `analytics_events`
  - JavaScript-код в `site-integration/site-integration-example.html` отправляет события (`phone_input`, `email_input`, `form_submit`, клики по телефону/WhatsApp) напрямую в `sales-analytic`
- Интеграция с amoCRM для данных о лидах и сделках

### 2. Онлайн-аналитика
- Мониторинг посетителей в реальном времени (через Яндекс.Метрику и собственный счётчик)
- Определение "горячих" лидов на основе поведения:
  - веса событий: клики по телефону/WhatsApp, отправка формы, ввод телефона/email, время на сайте, глубина просмотров
  - расчёт `intent_score` в `AnalyticsService` по событиям из `analytics_events`
- Триггеры для инициации нейропродажника:
  - `POST /api/analytics/trigger` рассчитывает `intent_score` и флаг `triggered`
  - при hot lead (`triggered = true`) сервис вызывает нейропродажника (`SALES_AGENT_URL/api/chat/initiate`) и передаёт контакты и контекст лида

### 3. Офлайн-отчёты
- Ежедневные, еженедельные, месячные отчёты
- Анализ конверсии и выявление узких мест
- Отслеживание эффективности рекламных каналов

### 4. Обогащение базы знаний
- Использование analytics_events для обогащения KB
- Анализ вопросов и возражений из диалогов
- Выявление паттернов поведения

## 📚 Документация

### Настройка и интеграция
- [`docs/YANDEX_METRIKA_API_SETUP.md`](./docs/YANDEX_METRIKA_API_SETUP.md) — настройка API доступа к Яндекс.Метрике
- [`docs/SITE_ANALYTICS_INTEGRATION_ANALYSIS.md`](./docs/SITE_ANALYTICS_INTEGRATION_ANALYSIS.md) — анализ трекеров сайта и интеграция

### Аналитика и отчёты
- [`docs/ANALYTICS_REPORTS_AND_CONVERSION.md`](./docs/ANALYTICS_REPORTS_AND_CONVERSION.md) — онлайн и оффлайн отчёты, улучшение конверсии
- [`docs/YANDEX_DIRECT_EFFECTIVENESS.md`](./docs/YANDEX_DIRECT_EFFECTIVENESS.md) — отслеживание эффективности Яндекс.Директ

### События и данные
- [`docs/ANALYTICS_EVENTS_SOURCES.md`](./docs/ANALYTICS_EVENTS_SOURCES.md) — источники данных для analytics_events
- [`docs/ANALYTICS_EVENTS_FOR_KB.md`](./docs/ANALYTICS_EVENTS_FOR_KB.md) — использование analytics_events для обогащения KB

### Онлайн-триггеры
- [`docs/ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md`](./docs/ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md) — активация нейропродажника через онлайн-аналитику
- [`docs/VISITOR_ATTENTION_AND_DEANONYMIZATION.md`](./docs/VISITOR_ATTENTION_AND_DEANONYMIZATION.md) — использование внимания пользователя для деанонимизации

## 🚀 Быстрый старт

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Настройка переменных окружения

Создайте файл `.env`:

```env
# Яндекс.Метрика
YANDEX_METRIKA_OAUTH_TOKEN=your_oauth_token
YANDEX_METRIKA_COUNTER_ID=103165578

# База данных
DATABASE_URL=postgresql://user:password@localhost:5432/brats

# Redis (опционально)
REDIS_URL=redis://localhost:6379/0

# FastAPI
API_HOST=0.0.0.0
API_PORT=8002
```

### Запуск сервиса

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8002
```

## 🔗 Интеграция с другими компонентами

- **n8n** — получение событий через webhook, триггеры для нейропродажника
- **sales-agent** — передача данных о горячих лидах для инициации диалога
- **kb-service** — обогащение базы знаний данными из аналитики
- **site-integration** — получение событий с сайта заказчика

## 📊 API Endpoints

### Онлайн-аналитика
- `GET /api/analytics/realtime` — агрегированные метрики за период (через Яндекс.Метрику)
- `GET /api/analytics/visitor/{visitor_id}` — данные о конкретном посетителе (зарезервирован)
- `POST /api/analytics/trigger` — триггер для инициации нейропродажника (расчёт intent_score + вызов sales-agent)

### Отчёты
- `GET /api/analytics/reports/daily` — ежедневный отчёт
- `GET /api/analytics/reports/weekly` — еженедельный отчёт
- `GET /api/analytics/reports/monthly` — месячный отчёт
- `GET /api/analytics/conversion` — анализ конверсии

### События
- `POST /api/analytics/collect` — приём сырых событий с сайта (собственный счётчик, пишет в analytics_events)
- `POST /api/analytics/events` — создание события (зарезервировано)
- `GET /api/analytics/events` — получение событий с фильтрацией (в том числе для `source=site_integration`)

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# Запуск тестов с покрытием
pytest --cov=domain --cov=api
```

## 📝 Примечания

- Сервис использует PostgreSQL для хранения событий (`analytics_events`)
- Для онлайн-аналитики рекомендуется использовать Redis для кэширования
- Все данные должны соответствовать требованиям 152-ФЗ (обезличивание ПДн)

---

**Последнее обновление:** 2026-02-10




