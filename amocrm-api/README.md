# amocrm-api — интеграция с amoCRM (разработка и тестирование)

Отдельная директория для разработки и тестирования интеграции с amoCRM. Независимый от n8n слой доступа к API: чтение лидов, контактов, воронок, примечаний и создание **тестовых** лидов.

**Документация:** [docs/AMOCRM.md](../docs/AMOCRM.md) — API, примеры использования, результаты обследования и выводы о бизнес-процессах в одном файле. OAuth2: [AMOCRM_API_SETUP.md](../docs/AMOCRM_API_SETUP.md).

## Переменные окружения

Скопируйте из того же `config.env` / `.env`, где настроен n8n:

- `AMOCRM_SUBDOMAIN`
- `AMOCRM_CLIENT_ID`
- `AMOCRM_CLIENT_SECRET`
- `AMOCRM_REDIRECT_URI`
- `AMOCRM_ACCESS_TOKEN`
- `AMOCRM_REFRESH_TOKEN`
- (опционально) `AMOCRM_TOKEN_EXPIRES_AT`

## Запуск

```bash
# из корня репозитория
cd amocrm-api
pip install -r requirements.txt
# задайте переменные (или загрузите из ../config.env)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8010
```

Документация API: http://localhost:8010/docs

## Эндпоинты

- **Чтение**: `GET /api/leads`, `GET /api/leads/{id}`, `GET /api/contacts`, `GET /api/pipelines`, `GET /api/leads/{id}/notes`, `GET /api/catalogs`
- **Тестовый лид**: `POST /api/test-leads` — создаёт лид с префиксом `[BRATS-TEST]` и тегом `brats_test` (см. [AMOCRM.md](../docs/AMOCRM.md), раздел 4)

## Использование из других сервисов

- Из **sales-agent** / **sales-analytic**: вызывать `http://amocrm-api:8010/api/...` или подключать клиент `amocrm-api/client.py` как библиотеку.
- Токен обновляется автоматически при 401.
