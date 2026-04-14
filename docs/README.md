# Документация проекта

Компактный набор концептуальных и справочных документов в соответствии с бизнес-процессами.

---

## Концепция и процессы

| Документ | Содержание |
|----------|------------|
| **[CONCEPT.md](./CONCEPT.md)** | База знаний (принципы, медиа, скрипты, админка), ведение по воронке, идентификация посетителя. |
| **[BUSINESS_PROCESSES.md](./BUSINESS_PROCESSES.md)** | Воронка продаж, FSM, роль n8n, AmoCRM, ЛК, KB; связь документов. |

---

## Настройка и интеграции

| Документ | Содержание |
|----------|------------|
| **[SETUP.md](./SETUP.md)** | Минимальная настройка: config.env, запуск сервисов, webhook, чат. |
| **[AMOCRM.md](./AMOCRM.md)** | Интеграция с AmoCRM: API amocrm-api, лид из чата, ЛК, календарь, закрытие сделки, сообщение менеджера в чат. |
| **[AMOCRM_API_SETUP.md](./AMOCRM_API_SETUP.md)** | OAuth2 и получение токенов AmoCRM. |

---

## По темам

- **Календарь, КП, договор:** [FUNNEL_CALENDAR_CP_CONTRACT.md](./FUNNEL_CALENDAR_CP_CONTRACT.md). Сценарий до закрытия: [SCENARIO_REPEAT_VISIT_CP_CONTRACT.md](./SCENARIO_REPEAT_VISIT_CP_CONTRACT.md).
- **n8n:** [n8n/README.md](../n8n/README.md) — запуск, webhook, структура workflow; детали узлов: [n8n/BUSINESS_PROCESSES.md](../n8n/BUSINESS_PROCESSES.md).
- **База знаний:** [KB.md](./KB.md) — назначение, структура, хранение, использование в потоке.
- **Личный кабинет:** [PERSONAL_CABINET_LK.md](./PERSONAL_CABINET_LK.md) — ЛК в PostgreSQL, связь с чатом, коммуналка и соседи.
- **Развёртывание ветки Татьяны (RAG):** [TATIANA_RAG_DEPLOY_PLAN.md](./TATIANA_RAG_DEPLOY_PLAN.md) — безопасный план, DNS/TLS, nginx, compose.
- **Статус для согласования с Татьяной:** [Tatiana_Eryukova.md](./Tatiana_Eryukova.md) — фактический статус на сервере и next steps.
- **Сайт и чат:** [SANDBOX_AND_SITE_INTEGRATION_PLAN.md](./SANDBOX_AND_SITE_INTEGRATION_PLAN.md), [site-integration/](../site-integration/).
- **DLP:** [DLP_FOR_SALES_AGENT.md](./DLP_FOR_SALES_AGENT.md).

Устаревшие и дублирующие документы — в **docs/archive/** (в т.ч. лишние AMOCRM-документы, X_TWITTER, SERVER_SPECIFICATION, объёмные KB/N8N-справочники).
