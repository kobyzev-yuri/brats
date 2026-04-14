# Интеграция сайта заказчика с n8n

Эта директория содержит код и документацию для интеграции сайта заказчика с системой нейропродажника через n8n webhook.

## 📋 Содержание

1. **[ИНСТРУКЦИЯ_ДЛЯ_ЗАКАЗЧИКА.md](./ИНСТРУКЦИЯ_ДЛЯ_ЗАКАЗЧИКА.md)** — краткая инструкция на русском языке для заказчика
2. **[SITE_INTEGRATION_CODE.md](./SITE_INTEGRATION_CODE.md)** — полная документация с кодом для интеграции
3. **[site-integration-example.html](./site-integration-example.html)** — пример страницы: каталог коттеджей, **чат с нейропродажником**, форма заявки  
4. **[catalog-interest-test.html](./catalog-interest-test.html)** — тест: **интерес к конкретному объекту** → свой счётчик (событие `place_interest` в analytics_events) и **передача контекста нейропродажнику** (чат открывается, первое сообщение уходит с контекстом объекта — агент получает управление и данные о месте)

---

## 🎯 Что делает интеграция

JavaScript код автоматически:
- ✅ **Чат с нейропродажником** — кнопка и карточки каталога открывают панель чата; сообщения уходят в n8n webhook, ответ агента отображается. В метаданных передаётся контекст сюжета (черновая/стандартная отделка, ипотека, скидки).
- ✅ Отслеживает ввод телефона в формах (минимум 10 цифр)
- ✅ Отслеживает ввод email (валидация формата)
- ✅ Отправляет события в n8n webhook для инициации нейропродажника
- ✅ Отслеживает клики по телефону и WhatsApp
- ✅ Отслеживает отправку форм
- ✅ Отправляет события в Яндекс.Метрику (опционально)
- ✅ События `chat_opened`, `chat_message_sent`, `phone_input`, `form_submit` уходят во внутреннюю аналитику — для **нейроаналитика** и сюжетов.
- ✅ Работает с динамически загружаемыми формами

---

## 🚀 Быстрый старт

### Вариант 0: Единый скрипт (все сервисы разом)

Из корня репозитория:

```bash
./start_all_services.sh start
```

Поднимает kb-service (8001), sales-agent (8003), n8n (5678) и сайт с прокси (8000). Затем откройте:

**http://localhost:8000/site-integration-example.html**

Остановка: `./start_all_services.sh stop`  
Статус: `./start_all_services.sh status`  
Перезапуск: `./start_all_services.sh restart`

Требуется: активное Python-окружение с установленными зависимостями (fastapi, uvicorn и т.д.), Docker для n8n.

---

### Шаг 1: Получить URL webhook

1. Откройте n8n
2. Найдите workflow "Sales Agent - KB Integration"
3. Откройте узел "Webhook"
4. Скопируйте Production URL (например: `http://localhost:5678/webhook/sales-agent-kb`)

### Шаг 2: Настроить код

1. Откройте файл `SITE_INTEGRATION_CODE.md` или пример `site-integration-example.html`.
2. В конфигурации укажите URL webhook (для чата с нейропродажником и для событий формы):
   ```javascript
   n8nWebhookUrl: 'https://your-n8n-domain.com/webhook/sales-agent-kb',
   ```
   Если оставить `null`, чат покажет подсказку; форма и аналитика продолжат работать.

### Шаг 3: Вставить на сайт

Вставьте код в `<head>` или перед закрывающим тегом `</body>` на всех страницах сайта.

**Подробная инструкция:** см. [ИНСТРУКЦИЯ_ДЛЯ_ЗАКАЗЧИКА.md](./ИНСТРУКЦИЯ_ДЛЯ_ЗАКАЗЧИКА.md)

---

## 📊 Формат данных

При вводе телефона или email отправляется следующий JSON в n8n:

```json
{
  "message": "Пользователь ввел телефон в форму",
  "channel": "site",
  "external_id": "visitor_1234567890_abc123",
  "metadata": {
    "visitor_id": "visitor_1234567890_abc123",
    "session_id": "session_1234567890_xyz789",
    "event_type": "phone_input",
    "form_type": "reservation_black_box",
    "phone": "79981234567",
    "email": null,
    "page_url": "https://innovatory-club.ru/katalog",
    "page_title": "Каталог коттеджей",
    "user_agent": "Mozilla/5.0...",
    "timestamp": "2025-02-07T15:30:00.000Z"
  }
}
```

Этот формат совместим с существующим workflow в n8n (`n8n/workflows/sales-agent-kb-integration.json`).

---

## 🔗 Связанные документы

- [`docs/ANALYTICS_INTEREST_TRIGGER.md`](../docs/ANALYTICS_INTEREST_TRIGGER.md) — интерес к объекту: как аналитик считает intent и триггерит нейропродажника (place_interest, тесты)
- [`docs/ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md`](../docs/ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md) — активация агента через аналитику
- [`docs/SITE_ANALYTICS_INTEGRATION_ANALYSIS.md`](../docs/SITE_ANALYTICS_INTEGRATION_ANALYSIS.md) — анализ интеграции с аналитикой
- [`docs/WEBHOOK_SETUP_CLARIFICATION.md`](../docs/WEBHOOK_SETUP_CLARIFICATION.md) — настройка webhook
- [`n8n/WEBHOOK_SETUP.md`](../n8n/WEBHOOK_SETUP.md) — настройка webhook в n8n

---

## 🧪 Тестирование

### Проверка в браузере

1. Откройте сайт с установленным кодом
2. Откройте консоль разработчика (F12)
3. Введите телефон или email в форму
4. Проверьте, что в консоли нет ошибок
5. Проверьте Network tab — должен быть POST запрос к n8n webhook

### Проверка в n8n

1. Откройте n8n
2. Перейдите в **Executions**
3. Найдите последнее выполнение workflow
4. Проверьте, что данные пришли корректно

### Тест через curl

```bash
curl -X POST https://your-n8n-domain.com/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Тест инициации агента",
    "channel": "site",
    "external_id": "test_visitor_123",
    "metadata": {
      "event_type": "phone_input",
      "phone": "79981234567",
      "form_type": "reservation_black_box"
    }
  }'
```

---

## 🔒 Безопасность

### Рекомендации:

1. **HTTPS обязателен** — используйте только HTTPS для webhook URL
2. **Валидация на сервере** — не полагайтесь только на клиентскую валидацию
3. **Rate limiting** — настройте ограничение частоты запросов в n8n
4. **Не отправляйте полные данные** — телефон и email можно хешировать перед отправкой

Подробнее см. раздел "Безопасность" в [SITE_INTEGRATION_CODE.md](./SITE_INTEGRATION_CODE.md).

---

## 📝 Структура файлов

```
site-integration/
├── README.md                          # Этот файл
├── ИНСТРУКЦИЯ_ДЛЯ_ЗАКАЗЧИКА.md        # Краткая инструкция для заказчика
├── SITE_INTEGRATION_CODE.md           # Полная документация с кодом
├── site-integration-example.html      # Пример: каталог, чат с агентом, форма (реалистичные сюжеты)
├── catalog-interest-test.html         # Тест: интерес к объекту → счётчик + передача контекста агенту
├── serve_with_proxy.py                # Сервер :8000 + прокси n8n, amocrm-api, analytics
└── lk/                                # Личный кабинет (вход, чат, документы)
```

### Пример страницы (site-integration-example.html)

- **Каталог:** карточки коттеджей (черновая/стандартная отделка, участок) с ценами, пометками про ипотеку и скидки.
- **Чат:** плавающая кнопка и панель; каждое сообщение пользователя отправляется в n8n webhook с полем `message` и `metadata.real_estate_context` (если открыли чат с карточки), `metadata.scenario` (сценарий покупки коттеджа, оплата, скидки, ипотека). Ответ workflow (`agent_response`) выводится в чате.
- **Форма заявки** — альтернативный способ оставить контакт; события телефона/email по-прежнему уходят в n8n и аналитику.
- Для **нейроаналитика**: события `chat_opened`, `chat_message_sent`, `phone_input`, `form_submit` отправляются в `internalAnalyticsUrl` и могут использоваться для отчётов и сюжетов.

---

## Типичные ситуации и отладка

### Повторная отправка / исправление телефона в чате

Если пользователь сначала написал неверный номер, затем отправил сообщение вида «Простите, телефон +7 …» (исправленный номер), оба сообщения уходят в n8n как обычные `chat_message` с одним и тем же `external_id` (visitor_id). Цепочка (n8n → Sales Agent Call) должна обрабатывать их как очередные реплики диалога, без дублирования контакта: обновление телефона на стороне amoCRM/контакта — задача workflow (например, «обновить слот контакта», а не «создать новый лид»).

**Если при повторной отправке появилась ошибка:**
1. В браузере откройте DevTools (F12) → вкладка Network: посмотрите ответ на POST к webhook (статус, тело ответа).
2. В n8n откройте **Executions** и найдите запуск по времени отправки сообщения. Посмотрите, на каком узле выполнение завершилось с ошибкой (например, Sales Agent Call, KB Search, Respond to Webhook).
3. Убедитесь, что узел **Respond to Webhook** в n8n настроен на «Respond to Webhook» и возвращает JSON с полями `response` или `agent_response`/`message`, иначе в чате появится «Не удалось получить ответ от цепочки n8n».
4. Если в цепочке используется DLP (обезличивание телефона в тексте) — сообщение с маской «+7 *** ***-**-**» должно всё равно доходить до агента; ошибка чаще связана с таймаутом или форматом ответа n8n.

### «Не удалось получить ответ от цепочки n8n»

Обычно значит: n8n вернул 200, но в теле нет полей `response` / `agent_response` / `message`, или ответ не JSON. Проверьте: в workflow последний узел перед Respond to Webhook должен передавать в выход именно такое поле; в браузере во вкладке Console после отправки сообщения смотрите `[Чат] Тело ответа:` — там будет сырой ответ n8n.

### Ошибка в узле LLM ProxyAPI: «invalid JSON in response body» (в т.ч. при повторной отправке телефона)

Если в n8n Executions узел **LLM ProxyAPI** падает с *invalid JSON in response body*, а в теле виден текст вида «Простите, телефон +7 *** ***-**-**», значит API вернул ответ не в формате JSON (например, plain text). Подробное решение: **[n8n/TROUBLESHOOTING.md](../n8n/TROUBLESHOOTING.md)** — раздел «Проблема: узел LLM ProxyAPI — invalid JSON in response body». Кратко: в узле LLM ProxyAPI выставить Response Format = String (или Autodetect); в узле **LLM Response Format** (Code) обрабатывать и объект, и строку (если `typeof raw === 'string'`, использовать её как текст ответа).

---

**Последнее обновление:** 2025-02-07














