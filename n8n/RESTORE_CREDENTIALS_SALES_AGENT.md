# Восстановление credentials для workflow Sales Agent - KB Integration

После импорта `sales-agent-kb-integration-localhost.json` в n8n нужно заново привязать credential для **LLM (ProxyAPI)**. Вызовы AmoCRM в этом workflow идут на локальный amocrm-api (порт 8010), ему credential в n8n не нужны — токены в `config.env` у amocrm-api.

---

## 1. Credential для агента (LLM ProxyAPI)

Нода **«LLM ProxyAPI»** вызывает `https://api.proxyapi.ru/openai/v1/chat/completions` с заголовком `Authorization: Bearer <ключ>`.

### Шаги в n8n

1. Откройте workflow **Sales Agent - KB Integration**.
2. Откройте ноду **«LLM ProxyAPI»** (HTTP Request к proxyapi.ru).
3. В блоке **Authentication** выберите **Header Auth** (или Generic Credential Type → HTTP Header Auth).
4. Нажмите **Create New Credential** (или выберите уже созданный).
5. Заполните:
   - **Credential Name**: `ProxyAPI` (или любое имя).
   - **Name** (заголовок): `Authorization`
   - **Value**: `Bearer <ваш_PROXYAPI_KEY>`
     - Ключ возьмите из `config.env` в корне проекта: переменная `PROXYAPI_KEY` или `OPENAI_API_KEY`.
     - Пример: `Bearer sk-0rjJ3guVbISwIjvhypozyF4YEicN2fUY`
6. Сохраните credential, затем сохраните ноду и workflow.

После этого нода «LLM ProxyAPI» будет отправлять запросы с вашим ключом.

---

## 2. AmoCRM в этом workflow

В этом workflow AmoCRM не использует credentials внутри n8n:

- **Resolve Conversation** и **Save Messages API** обращаются к `AMOCRM_API_BASE_URL` (по умолчанию `http://localhost:8010`) — это ваш сервис **amocrm-api**, он сам берёт токены из своего конфига.
- **AmoCRM Create Lead** — POST на `http://localhost:8010/api/test-lead-from-chat` без авторизации в n8n.

Что нужно проверить:

- В **config.env** (откуда запускаете n8n, например через `start_all_services.sh`) задано:
  - `AMOCRM_API_BASE_URL=http://localhost:8010`
- В **config.env** (или в окружении процесса **amocrm-api**) заданы токены AmoCRM:
  - `AMOCRM_SUBDOMAIN`, `AMOCRM_ACCESS_TOKEN`, при необходимости `AMOCRM_REFRESH_TOKEN`  
  См. [docs/AMOCRM_API_SETUP.md](../docs/AMOCRM_API_SETUP.md).

Если нужны credentials для **других** workflow (напрямую в API amoCRM из n8n), см. [docs/AMOCRM_N8N_CREDENTIALS_SETUP.md](../docs/AMOCRM_N8N_CREDENTIALS_SETUP.md).

---

## 3. Переменные окружения для n8n

Чтобы ноды **Resolve Conversation** и др. видели `AMOCRM_API_BASE_URL`, n8n должен запускаться с подгруженным конфигом. При запуске через `./start_all_services.sh start` делается `source config.env`, переменные попадают в процесс n8n.

Если запускаете n8n вручную (например, `npx n8n`), перед запуском выполните:

```bash
cd /projects/brats
set -a && source config.env && set +a
cd n8n && npx n8n
```

Тогда в workflow будут доступны `$env.AMOCRM_API_BASE_URL` и остальные переменные из config.env.
