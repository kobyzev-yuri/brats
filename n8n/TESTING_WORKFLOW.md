# Тестирование опубликованного workflow

## ✅ Workflow опубликован!

После публикации workflow активен и готов принимать запросы.

## 🔍 Как найти URL webhook

### Способ 1: Через узел Webhook

1. В редакторе workflow откройте узел **Webhook**
2. В настройках узла будет показан **Production URL**
3. Пример: `http://localhost:5678/webhook/sales-agent-kb`

### Способ 2: Через список Workflows

1. Перейдите в раздел **Workflows**
2. Найдите ваш workflow "Sales Agent - KB Integration"
3. URL webhook может быть показан в карточке workflow

### Способ 3: Стандартный формат

Если webhook ID в workflow: `sales-agent-kb`, то URL будет:
```
http://localhost:5678/webhook/sales-agent-kb
```

## 🧪 Тестирование workflow

### Тест 1: Базовый запрос

```bash
curl -X POST http://localhost:5678/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Расскажите о ценах на коттеджи",
    "channel": "telegram",
    "external_id": "test_user_123",
    "metadata": {
      "user_type": "end_buyer"
    }
  }'
```

### Тест 2: Запрос для риелтора

```bash
curl -X POST http://localhost:5678/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Какие условия сотрудничества для риелторов?",
    "channel": "telegram",
    "external_id": "test_realtor_456",
    "metadata": {
      "user_type": "realtor",
      "is_realtor": true
    }
  }'
```

### Тест 3: Простой запрос

```bash
curl -X POST http://localhost:5678/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Привет",
    "channel": "telegram"
  }'
```

### Тест 4: Сообщение с телефоном (проверка создания лида в AmoCRM)

Если amocrm-api (порт 8010) запущен и в config.env заданы AMOCRM_ACCESS_TOKEN и AMOCRM_SUBDOMAIN, после этого запроса в AmoCRM должен появиться тестовый лид с префиксом [BRATS-TEST] и тегом brats_test.

```bash
curl -X POST http://localhost:5678/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Меня зовут Иван, перезвоните +79161234567",
    "channel": "website",
    "external_id": "finish_test_001",
    "metadata": {}
  }'
```

Проверка: n8n → **Executions** → последний запуск → узлы **Maybe Create Lead** → **Create Lead If Phone** → **AmoCRM Create Lead** должны выполниться без ошибки. В AmoCRM — сделка с контактом и примечанием из чата.

### Тест 5: Запись в календарь (слот на просмотр)

При сообщении вида «24 февраля 10:00–11:00 запишите» и наличии `conversation_id` (передавайте тот же `external_id`, что и в предыдущих сообщениях) workflow создаёт запись в таблице `viewing_slots` (funnel-api). Подробный сценарий прохождения воронки: [ПЛАН_ТЕСТИРОВАНИЯ_ВОРОНКИ.md](ПЛАН_ТЕСТИРОВАНИЯ_ВОРОНКИ.md).

```bash
curl -X POST http://localhost:5678/webhook/sales-agent-kb \
  -H "Content-Type: application/json" \
  -d '{
    "message": "24 февраля 10:00–11:00 запишите",
    "channel": "website",
    "external_id": "funnel-test-001",
    "metadata": {}
  }'
```

Проверка: в **Executions** — узлы **Parse Slot From Message** → **Book Slot If Parsed** → **Book Viewing Slot API**; в БД: `SELECT * FROM viewing_slots WHERE status = 'booked' ORDER BY created_at DESC LIMIT 5;`

## 📊 Просмотр выполнения

⚠️ **Важно**: Выполнения не показываются сразу в редакторе, но их можно увидеть в списке executions.

### Как посмотреть выполнения:

1. В n8n перейдите в **Executions** (в левом меню)
2. Вы увидите список всех выполнений workflow
3. Кликните на выполнение, чтобы увидеть детали:
   - Входные данные каждого узла
   - Выходные данные каждого узла
   - Ошибки (если есть)
   - Время выполнения

### Фильтрация выполнений:

- Можно фильтровать по статусу (Success, Error, Running)
- Можно фильтровать по workflow
- Можно фильтровать по дате

## 🔍 Проверка работы узлов

### Узел "KB Search"

После выполнения проверьте:
1. Откройте выполнение в **Executions**
2. Откройте узел **KB Search**
3. Проверьте:
   - **Input**: должен содержать запрос из сообщения
   - **Output**: должен содержать результаты поиска из KB

**Ожидаемый результат:**
```json
{
  "results": [
    {
      "id": 1,
      "content": "...",
      "similarity": 0.85,
      "metadata": {...}
    }
  ],
  "total": 5
}
```

### Узел "Format KB Context"

Проверьте, что результаты KB правильно отформатированы для промпта.

### Узел "Sales Agent Call"

Если агент продаж еще не реализован:
- Узел может вернуть ошибку - это нормально
- Можно временно закомментировать этот узел
- Или настроить mock endpoint для тестирования

## ⚠️ Устранение проблем

### Webhook не отвечает

1. Проверьте, что workflow опубликован (кнопка **Publish** должна быть активна)
2. Проверьте правильность URL webhook
3. Проверьте логи n8n: `docker logs n8n-brats`

### KB Search не работает

1. Убедитесь, что KB Service запущен:
   ```bash
   curl http://localhost:8001/health
   ```
2. Проверьте URL в узле "KB Search": `http://localhost:8001/api/kb/search`
3. Проверьте логи KB Service

### Ошибки в выполнении

1. Откройте выполнение в **Executions**
2. Найдите узел с ошибкой (красный индикатор)
3. Проверьте входные данные узла
4. Проверьте настройки узла
5. Посмотрите сообщение об ошибке

### Выполнения не сохраняются

По умолчанию n8n может не сохранять все выполнения. Чтобы сохранять:
1. Откройте настройки workflow (три точки → **Settings**)
2. Включите **Save Execution Data** или **Save Data on Error**

## ✅ Завершение тестирования (чеклист)

Перед тем как считать тестирование workflow завершённым:

1. **Сервисы запущены**
   - n8n: `http://localhost:5678` (workflow активен — переключатель **Active** включён)
   - KB Service: `curl http://localhost:8001/health` → OK
   - amocrm-api (для памяти диалога и лидов): `curl http://localhost:8010/health` → OK  
   - Опционально: funnel-api на 8011 (слоты просмотра) — при отсутствии workflow продолжает работу

2. **В n8n**
   - Workflow **Sales Agent - KB Integration** импортирован из `n8n/workflows/sales-agent-kb-integration-localhost.json` (если ещё не импортирован)
   - В узле **LLM ProxyAPI** выбран credential **Header Auth** (ProxyAPI) с ключом proxyapi.ru
   - Workflow сохранён и **Active** включён

3. **Прогон curl-тестов**
   - Тест 1: запрос по ценам (см. выше)
   - Тест 2: запрос для риелтора
   - Тест 3: простой «Привет»
   - Тест 4: сообщение с телефоном — затем проверить лид в AmoCRM

4. **Executions**
   - В n8n → **Executions** убедиться, что последние запуски в статусе Success; при тесте 4 — Maybe Create Lead → AmoCRM Create Lead; при тесте 5 — Parse Slot From Message → Book Viewing Slot API.

5. **Полный проход по воронке** — см. [ПЛАН_ТЕСТИРОВАНИЯ_ВОРОНКИ.md](ПЛАН_ТЕСТИРОВАНИЯ_ВОРОНКИ.md).

6. **Чат с сайта (опционально)**
   - Открыть `http://localhost:8000/site-integration-example.html` (или ваш фронт), отправить сообщение и сообщение с телефоном — проверить ответ и появление лида в AmoCRM.

7. **Быстрая проверка одной командой**
   ```bash
   cd /projects/brats/n8n && ./run_integration_tests.sh
   ```
   Проверяет доступность kb, sales-agent, n8n и один POST на webhook.

Когда все пункты выполнены — тестирование workflow можно считать завершённым.

## 📝 Следующие шаги (после тестов)

1. ✅ Workflow опубликован и протестирован
2. Интеграция с Telegram/Avito (подставить webhook URL в ботов/интеграции)
3. При необходимости: настройка AMOCRM_TEST_PIPELINE_ID в config.env для нужной воронки

## 💡 Полезные команды

```bash
# Проверка KB Service
curl http://localhost:8001/health

# Проверка n8n
curl http://localhost:5678/healthz

# Просмотр логов n8n
docker logs -f n8n-brats

# Просмотр логов KB Service (если есть)
cd /projects/brats/kb-service && tail -f logs/*.log
```
















