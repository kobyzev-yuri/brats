# Минимальная настройка для работы

## 1. Конфигурация

Скопировать **`config.env.example`** в **`config.env`** в корне проекта. Заполнить переменные.

**Обязательно для чата с KB и лидами:**
- **DATABASE_URL** — PostgreSQL (та же БД для kb-service и amocrm-api).
- **KB_API_URL** — URL kb-service (по умолчанию http://localhost:8001).
- **OPENAI_API_KEY**, **OPENAI_BASE_URL** — для embeddings и LLM (например ProxyAPI).
- **AMOCRM_SUBDOMAIN**, **AMOCRM_ACCESS_TOKEN**, **AMOCRM_REFRESH_TOKEN** — для amocrm-api (лиды из чата). Получение токенов: [AMOCRM_API_SETUP.md](./AMOCRM_API_SETUP.md).

Опционально: AMOCRM_CLIENT_ID, AMOCRM_CLIENT_SECRET, AMOCRM_REDIRECT_URI (автообновление токена); AMOCRM_TEST_PIPELINE_ID; Yandex Metrika (для аналитики).

Подробный справочник переменных: [CONFIGURATION_REFERENCE.md](./CONFIGURATION_REFERENCE.md). Минимальный чек-лист: [MINIMAL_SETUP_REQUIREMENTS.md](./MINIMAL_SETUP_REQUIREMENTS.md).

---

## 2. Запуск сервисов

Из корня проекта:
```bash
./start_all_services.sh
```

Запускаются: kb-service (8001), KB Admin Streamlit (8501), n8n (5678), прокси чата (8000), amocrm-api (8010). Слоты календаря — funnel-api (8011), если настроен.

Вручную: см. README в `kb-service/`, `n8n/`, `amocrm-api/`.

---

## 3. Webhook и чат с сайта

- **URL webhook n8n:** `http://<host>:5678/webhook/sales-agent-kb`. В config.env задаётся база (например `http://localhost:5678`), путь `/webhook/sales-agent-kb` подставляется прокси/сайтом.
- Чат: открыть `site-integration/site-integration-example.html` через прокси (например http://localhost:8000), выбрать «n8n flow» и при необходимости указать URL webhook. См. [SANDBOX_AND_SITE_INTEGRATION_PLAN.md](./SANDBOX_AND_SITE_INTEGRATION_PLAN.md), [site-integration/](../site-integration/).

---

## 4. Загрузка базы знаний

```bash
source config.env   # или export KB_API_URL=http://localhost:8001
python scripts/reset_and_load_kb.py --data-dir data
```

См. [CONCEPT.md](./CONCEPT.md), раздел 3.
