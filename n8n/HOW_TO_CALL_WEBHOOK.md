# Как вызвать webhook workflow в n8n

## Проверка: Workflow активирован?

Webhook работает только если workflow **активирован** (переключатель "Active" включен).

### Как проверить:

1. Откройте n8n: http://localhost:5678
2. Перейдите в **Workflows**
3. Найдите **"amoCRM - Get Deal History (Simple)"**
4. Откройте workflow
5. Проверьте переключатель **"Active"** в правом верхнем углу:
   - ✅ **Включен (зеленый)** - webhook работает
   - ❌ **Выключен (серый)** - webhook не работает

## Как вызвать webhook

### Вариант 1: Через curl (командная строка)

```bash
# Обязательно отключите прокси для localhost
unset all_proxy ALL_PROXY http_proxy HTTP_PROXY https_proxy HTTPS_PROXY

# Вызов webhook
curl -X POST http://localhost:5678/webhook/amocrm-get-deal-history-simple \
  -H "Content-Type: application/json" \
  -d '{"contact_id": 46692527}'
```

### Вариант 2: Через другой workflow в n8n

В Code node или HTTP Request node:

```javascript
// В Code node
const response = await $http.request({
  method: 'POST',
  url: 'http://localhost:5678/webhook/amocrm-get-deal-history-simple',
  headers: {
    'Content-Type': 'application/json'
  },
  body: {
    contact_id: 46692527
  }
});

return {
  json: {
    deal_history: response.deal_history,
    ...
  }
};
```

Или через HTTP Request node:
- **Method**: POST
- **URL**: `http://localhost:5678/webhook/amocrm-get-deal-history-simple`
- **Body**: JSON
  ```json
  {
    "contact_id": 46692527
  }
  ```

### Вариант 3: Через Python скрипт

```python
import requests

response = requests.post(
    'http://localhost:5678/webhook/amocrm-get-deal-history-simple',
    json={'contact_id': 46692527}
)

print(response.json())
```

## Проверка: Webhook зарегистрирован?

### Если получаете ошибку 404:

```
{"code":404,"message":"The requested webhook \"POST amocrm-get-deal-history-simple\" is not registered."}
```

**Решение:**
1. Убедитесь, что workflow активирован (переключатель "Active" включен)
2. Сохраните workflow (нажмите **Save**)
3. Попробуйте снова

### Если получаете пустой ответ:

1. Проверьте выполнение в **Executions**
2. Откройте последнее выполнение
3. Проверьте, на каком узле остановилось выполнение

## URL webhook

После активации workflow, URL webhook будет:
```
http://localhost:5678/webhook/amocrm-get-deal-history-simple
```

**Важно:**
- Используйте `/webhook/` (не `/webhook-test/`)
- Метод: **POST** (не GET)
- Content-Type: **application/json**

## Тестирование

### Быстрый тест:

```bash
# 1. Проверьте, что workflow активирован в n8n UI

# 2. Вызовите webhook
unset all_proxy ALL_PROXY http_proxy HTTP_PROXY https_proxy HTTPS_PROXY

curl -X POST http://localhost:5678/webhook/amocrm-get-deal-history-simple \
  -H "Content-Type: application/json" \
  -d '{"contact_id": 46692527}'

# 3. Ожидаемый ответ:
# {
#   "contact_id": 46692527,
#   "total_leads": 250,
#   "closed_leads": 4,
#   "deal_history": [...]
# }
```

### Если получаете пустой ответ:

1. Откройте n8n → **Executions**
2. Найдите последнее выполнение
3. Проверьте каждый узел:
   - Какой узел красный (если есть)?
   - Что показывает Output каждого узла?

## Интеграция в другие workflow

Если вы хотите вызывать этот webhook из другого workflow:

1. Добавьте **HTTP Request** node
2. Настройте:
   - **Method**: POST
   - **URL**: `http://localhost:5678/webhook/amocrm-get-deal-history-simple`
   - **Body**: JSON с `contact_id`
3. Используйте результат в следующих узлах

## Автоматический вызов

Workflow можно вызвать автоматически:

1. **По расписанию** - добавьте **Cron** node в начале
2. **При событии** - используйте **Webhook** как триггер
3. **Из другого workflow** - используйте **HTTP Request** node

Но для получения истории сделок обычно вызывают по требованию (по запросу), а не автоматически.
