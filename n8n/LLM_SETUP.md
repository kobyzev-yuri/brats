# Настройка LLM в n8n для workflow Sales Agent - KB Integration

Workflow **sales-agent-kb-integration-localhost.json** уже содержит вызов LLM через узел **LLM ProxyAPI** (HTTP Request на proxyapi.ru). Ключи не хранятся в JSON — читаются из переменных окружения при запуске n8n.

Чтобы чат отвечал через реальную модель (GPT-4o через proxyapi.ru), задайте ключи в **config.env** и перезапустите n8n через `./start_all_services.sh` или `./start_n8n_local.sh` (они подхватывают config.env и передают в n8n).

## 1. Переменные в config.env (корень проекта)

В `config.env` задайте (те же значения, что для kb-service):

```bash
OPENAI_API_KEY=ваш-ключ-proxyapi-или-openai
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2
```

При запуске через `./start_all_services.sh` или `./start_n8n_local.sh` эти переменные подхватываются из `config.env` и доступны в n8n как переменные окружения (если не отключён доступ к env).

## 2. Credential в n8n для ProxyAPI (обязательно для узла LLM ProxyAPI)

В workflow **не используется** доступ к переменным окружения ($env), поэтому ключ задаётся только через credential.

1. Откройте n8n → **Credentials** (или **Settings** → **Credentials**) → **Add Credential**.
2. Выберите **Header Auth**.
   - **Name**: `Authorization`
   - **Value**: `Bearer ВАШ_PROXYAPI_KEY` (подставьте ключ из config.env, например значение `PROXYAPI_KEY` или `OPENAI_API_KEY`).
3. Сохраните credential, например с именем **ProxyAPI** или **OpenAI ProxyAPI**.
4. Откройте workflow → узел **LLM ProxyAPI** → в блоке **Authentication** найдите поле **«Header Auth account»** (под «Generic Auth Type: Header Auth»). Это и есть выбор credential: нажмите на это поле — откроется выпадающий список; выберите созданный credential (например **ProxyAPI**). Если в списке пусто — сначала создайте credential (п. 1–3), обновите страницу n8n и снова откройте узел.
5. Сохраните workflow (Ctrl+S).

Либо, если в вашей версии n8n есть credential **OpenAI Api** с полем **Base URL**:
- Создайте credential **OpenAI Api**.
- **API Key** = ваш ключ.
- **Base URL** = `https://api.proxyapi.ru/openai/v1` (если есть такое поле).
- Модель в узле укажите `gpt-4o`.

## 3. Вариант A: узел OpenAI в workflow (если есть Base URL)

1. Откройте workflow **Sales Agent - KB Integration (local)**.
2. Удалите узел **Sales Agent Call** (HTTP на localhost:8003) или отключите его.
3. Добавьте узел **OpenAI** (или **@n8n/n8n-nodes-langchain.openAi** → Chat Model):
   - **Credential**: выбранный OpenAI/ProxyAPI credential.
   - **Model**: `gpt-4o` (или из переменной).
   - **Prompt / Message**: `={{ $json.prompt }}` (промпт из узла Format KB Context).
4. Подключите выход **Format KB Context** к новому узлу OpenAI, выход OpenAI — к **Prepare Response**.
5. В узле **Prepare Response** нужно брать ответ из выхода OpenAI. Обычно это что-то вроде `$input.first().json.message.content` или `$input.first().json.choices[0].message.content` — в зависимости от формата выхода узла. Откройте Prepare Response → в коде замените:
   - `const agentResponse = $input.first().json;`
   - на извлечение текста из ответа LLM, например:
     `const raw = $input.first().json; const agentResponse = { response: raw.message?.content ?? raw.choices?.[0]?.message?.content ?? '' };`
   и дальше используйте `agentResponse.response` как сейчас.

Сохраните workflow и включите Active.

## 4. Вариант B: узел HTTP Request на chat/completions (всегда работает)

Если у credential OpenAI в n8n нет поля Base URL, используйте общий вызов API через **HTTP Request**:

1. В workflow после **Format KB Context** добавьте узел **HTTP Request**:
   - **Method**: POST
   - **URL**: `https://api.proxyapi.ru/openai/v1/chat/completions` (или `{{ $env.OPENAI_BASE_URL }}/chat/completions`, если n8n видит переменные окружения).
   - **Authentication**: Generic Credential Type → **Header Auth** (credential из п.2).
   - **Body Content Type**: JSON
   - **Body**:
     ```json
     {
       "model": "gpt-4o",
       "temperature": 0.2,
       "messages": [
         { "role": "user", "content": "={{ $json.prompt }}" }
       ]
     }
     ```
2. После этого узла добавьте узел **Code** (или измените следующий узел), чтобы из ответа API достать текст:
   - Вход: вывод HTTP Request (объект с `choices[0].message.content`).
   - Выход: один объект с полем `response` (и при необходимости `message`), чтобы узел **Prepare Response** работал без изменений, например:
     ```js
     const raw = $input.first().json;
     const text = raw.choices?.[0]?.message?.content ?? '';
     return { json: { response: text, message: text } };
     ```
3. Подключите: Format KB Context → HTTP Request → этот Code → Prepare Response → Respond to Webhook.

Сохраните и включите workflow.

## 5. Workflow уже с LLM (HTTP Request)

В **sales-agent-kb-integration-localhost.json** цепочка сейчас такая:
- **Format KB Context** → **LLM ProxyAPI** (HTTP Request на proxyapi.ru) → **LLM Response Format** (Code) → **Prepare Response** → **Respond to Webhook**.

Узел **Sales Agent Call** оставлен в workflow отключённым (disabled) — его можно включить, если нужен ответ без LLM (заглушка с localhost:8003).

URL и модель в узле **LLM ProxyAPI** зашиты (proxyapi.ru, gpt-4o). Ключ API задаётся только через **credential** в n8n (см. п.2 выше) — не через переменные окружения.

## 6. Проверка

Откройте сайт чата, отправьте сообщение. Ответ должен приходить от LLM (GPT-4o через proxyapi.ru), а не заглушка.

## Сводка

| Что | Где |
|-----|-----|
| Ключ и URL LLM | `config.env`: OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL |
| Credential в n8n | Header Auth с `Authorization: Bearer <key>` или OpenAI Api с Base URL |
| Вызов LLM | Вариант A: узел OpenAI в workflow; Вариант B: HTTP Request на `/chat/completions` |

После настройки LLM в n8n цепочка будет: **Webhook → Normalize Input → KB Search → Format KB Context → LLM (OpenAI или HTTP Request) → Prepare Response → Respond to Webhook**.
