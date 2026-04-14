# n8n: оркестрация чата и воронки

n8n — единая точка входа для сообщений из чата (сайт, ЛК, Telegram, Avito). Workflow реализует: нормализацию, DLP, память диалога, поиск в KB, вызов LLM, создание лида в AmoCRM, календарь просмотров и сохранение реплик.

---

## Запуск

**Из корня репо (все сервисы):**
```bash
./start_all_services.sh start
```

**Только n8n:**
```bash
cd n8n && ./start_n8n_local.sh
```

Требуется Node.js ≥20. Данные: `~/.n8n`. Импорт workflow: **workflows/sales-agent-kb-integration-localhost.json**.

---

## Webhook и тест

- **URL:** `POST http://localhost:5678/webhook/sales-agent-kb`
- **Тело:** `message`, `channel` (website | lk | telegram), `external_id` (сессия чата). Для ЛК можно передавать `conversation_id`.

Пример:
```bash
curl -X POST http://localhost:5678/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{"message": "Расскажите о ценах", "channel": "website", "external_id": "test-1"}'
```

---

## Структура workflow

```
Webhook → Normalize Input → DLP Sanitize → Resolve Conversation (история)
    → Get Viewing Slots (при необходимости) → KB Search → Format KB Context
    → LLM (ProxyAPI/GPT-4o) → Maybe Create Lead (при телефоне) → Save Messages
    → Respond to Webhook
```

Ветки: распознавание бронирования слота (Book Viewing Slot), распознавание handoff («связать с менеджером») → обновление state и задача в AmoCRM.

---

## Настройка

- **LLM:** credential OpenAI-совместимый (proxyapi.ru или иной); переменные в config.env: OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL.
- **Сервисы:** kb-service (8001), amocrm-api (8010), funnel-api (8011). URL в узлах — localhost или переменная AMOCRM_API_BASE_URL для amocrm-api.
- **Память:** чат должен передавать `external_id`; по нему загружается история из PostgreSQL (conversation_id, messages). Миграция `09_add_conversation_external_id.sql` обязательна.

---

## Документация

| Тема | Документ |
|------|----------|
| Бизнес-процессы (воронка, FSM, AmoCRM, KB) | [docs/BUSINESS_PROCESSES.md](../docs/BUSINESS_PROCESSES.md) |
| Узлы, DLP, календарь, лид, handoff | [n8n/BUSINESS_PROCESSES.md](./BUSINESS_PROCESSES.md) |
| AmoCRM API и OAuth | [docs/AMOCRM.md](../docs/AMOCRM.md), [docs/AMOCRM_API_SETUP.md](../docs/AMOCRM_API_SETUP.md) |
| Календарь, КП, договор | [docs/FUNNEL_CALENDAR_CP_CONTRACT.md](../docs/FUNNEL_CALENDAR_CP_CONTRACT.md) |

Отладка и детальные шаги — в [BUSINESS_PROCESSES.md](./BUSINESS_PROCESSES.md) (память, слоты, сохранение реплик, план тестирования).
