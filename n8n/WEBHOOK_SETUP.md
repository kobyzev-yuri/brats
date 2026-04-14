# Настройка Webhook узла в n8n

## Проблема: Webhook настроен на GET вместо POST

Если вы получаете ошибку:
```
{"code":404,"message":"This webhook is not registered for POST requests. Did you mean to make a GET request?"}
```

Это означает, что узел Webhook настроен на GET запросы, а нужно POST.

## Решение: Изменить HTTP Method на POST

### Шаг 1: Откройте узел Webhook

1. В редакторе workflow откройте узел **Webhook**
2. Нажмите на узел, чтобы открыть его настройки

### Шаг 2: Измените HTTP Method

1. В настройках узла найдите поле **HTTP Method**
2. Измените с **GET** на **POST**
3. Сохраните изменения

### Шаг 3: Переопубликуйте workflow

1. После изменения настроек нажмите **Publish** (или **Save** и затем **Publish**)
2. Workflow будет обновлен с новыми настройками

## Правильный URL webhook

После настройки на POST, используйте URL:
```
http://localhost:5678/webhook/sales-agent-kb
```

**Не используйте** `/webhook-test/` - это для тестового режима.

## Тестирование после исправления

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

## Дополнительные настройки Webhook

### Authentication
- Оставьте **None** для локальной разработки
- Для продакшена можно добавить Basic Auth или API Key

### Response Code
- Можно оставить **200** (OK)
- Или использовать **201** (Created)

### Respond Immediately
- Оставьте включенным, если хотите сразу вернуть ответ
- Или отключите, если нужно дождаться полного выполнения workflow

## Проверка настроек

После изменения на POST, в узле Webhook должно быть:
- **HTTP Method**: POST
- **Path**: sales-agent-kb
- **Production URL**: `http://localhost:5678/webhook/sales-agent-kb`

## Устранение проблем

### Все еще получаю ошибку 404

1. Убедитесь, что workflow опубликован (кнопка **Publish** активна)
2. Проверьте, что HTTP Method = POST
3. Проверьте правильность URL (должен быть `/webhook/`, а не `/webhook-test/`)
4. Перезапустите n8n (если нужно):
   ```bash
   docker restart n8n-brats
   ```

### Webhook не отвечает

1. Проверьте логи n8n: `docker logs n8n-brats`
2. Проверьте, что workflow активен
3. Проверьте настройки узла Webhook
















