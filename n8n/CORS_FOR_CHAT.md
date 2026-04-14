# CORS для чата с сайта

Если в консоли: **«blocked by CORS policy: No 'Access-Control-Allow-Origin' header»** — браузер блокирует ответ n8n.

## Решение 1: прокси (без настройки n8n)

Запустите сайт через скрипт с прокси — запросы к n8n пойдут с того же хоста, CORS не нужен:

```bash
cd site-integration
python serve_with_proxy.py
```

Откройте http://localhost:8000/site-integration-example.html и в настройках чата укажите URL: **http://localhost:8000/api/n8n-proxy**

## Решение 2: разрешить источник в n8n

1. **Переменные окружения n8n** (Docker):

   В `n8n/docker-compose.yml` в `environment` добавлено:
   ```yaml
   - N8N_CORS_ALLOW_ORIGIN=http://localhost:8000,http://brats.local:8000,http://0.0.0.0:8000
   ```
   Для разработки можно разрешить все источники:
   ```yaml
   - N8N_CORS_ALLOW_ORIGIN=*
   ```

2. **Перезапуск n8n** после изменения:
   ```bash
   cd n8n
   docker compose down && docker compose up -d
   ```

3. **Проверка**: откройте чат с той же страницы (например `http://localhost:8000/...` или `http://brats.local:8000/...`), отправьте сообщение — ответ должен появиться в чате.

## Дополнительно

- В n8n Webhook должен быть **POST** и путь **Production**: `/webhook/sales-agent-kb` (не `/webhook-test/`).
- Если страница открыта по `http://0.0.0.0:8000`, в чате подставляется URL `http://0.0.0.0:5678/...`; при проблемах укажите вручную `http://localhost:5678/webhook/sales-agent-kb` в поле URL n8n.
