# Workflow n8n для BRATS

Используется **один** workflow: чат с нейропродажником, воронка продаж, DLP, создание лида в AmoCRM и контекст календаря.

## Файл

- **`sales-agent-kb-integration-localhost.json`** — основной workflow (воронка + DLP + календарь).

**Webhook:** `POST /webhook/sales-agent-kb`

**Цепочка:** Webhook → Normalize Input → DLP Sanitize Text → Merge Sanitized → Merge (с Get Viewing Slots) → KB Search → Format KB Context → LLM ProxyAPI → LLM Response Format → Prepare Response → Respond to Webhook и параллельно Maybe Create Lead → при наличии телефона → AmoCRM Create Lead.

## Зависимости (сервисы)

| Сервис        | Порт | Назначение в workflow |
|---------------|------|------------------------|
| kb-service    | 8001 | DLP (sanitize-text), KB Search |
| funnel-api    | 8011 | Get Viewing Slots (свободные слоты 9–18) |
| amocrm-api    | 8010 | Создание лида и контакта из чата |
| ProxyAPI (LLM)| внешний | GPT-4o для ответов (credential в n8n) |

Запуск: `./start_all_services.sh start` (из корня репо). Импорт: Workflows → Import from File → выбрать этот JSON. Включить workflow (Active).

## Настройка в n8n

1. **Credential для LLM:** HTTP Header Auth, Name=Authorization, Value=Bearer &lt;PROXYAPI_KEY&gt; (из config.env).
2. Узлы HTTP Request используют фиксированные URL localhost; при другом хосте изменить в узлах DLP Sanitize Text, Get Viewing Slots, KB Search, AmoCRM Create Lead.

Подробнее по бизнес-процессам и воронке: [docs/BUSINESS_PROCESSES.md](../../docs/BUSINESS_PROCESSES.md).
