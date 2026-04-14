# Импорт workflow для интеграции KB с агентом продаж

## Шаг 1: Импорт workflow

1. В n8n перейдите в **Workflows** (вы уже там: http://localhost:5678/home/workflows)
2. Нажмите кнопку **Import from File** (или **Import** → **From File**)
3. Выберите файл: `/projects/brats/n8n/workflows/sales-agent-kb-integration.json`
4. Workflow будет импортирован и откроется в редакторе

## Шаг 2: Проверка настроек workflow

После импорта проверьте следующие узлы:

### 1. Узел "KB Search"
- **URL**: `http://localhost:8001/api/kb/search`
- Убедитесь, что KB Service запущен:
  ```bash
  curl http://localhost:8001/health
  ```

### 2. Узел "Sales Agent Call"
- **URL**: `http://localhost:8000/api/chat` (или ваш URL агента продаж)
- Если агент еще не реализован, можно временно закомментировать этот узел или использовать mock endpoint

### 3. Узел "Webhook"
- Запомните URL webhook (будет показан после активации workflow)
- Пример: `http://localhost:5678/webhook/sales-agent-kb`

## Шаг 3: Активация workflow (Publish)

В новом интерфейсе n8n workflow активируется через кнопку **Publish**:

1. В правом верхнем углу редактора найдите кнопку **Publish**
2. Нажмите **Publish** - workflow будет опубликован и активирован
3. После публикации workflow станет активным и готов принимать запросы
4. URL webhook будет показан в узле Webhook

## Шаг 4: Тестирование workflow

### Тест через curl

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

### Ожидаемый результат

1. Webhook получает запрос
2. Данные нормализуются
3. Выполняется поиск в KB
4. Результаты форматируются для промпта
5. Вызывается агент продаж (если настроен)
6. Возвращается ответ

## Просмотр выполнения

1. В n8n перейдите в **Executions** (в левом меню)
2. Вы увидите историю выполнения workflow
3. Кликните на выполнение, чтобы увидеть детали каждого узла

## Следующие шаги

1. ✅ n8n установлен и настроен
2. ✅ Пользователь создан
3. ⏳ Импортировать workflow
4. ⏳ Настроить интеграцию с KB Service
5. ⏳ Настроить интеграцию с агентом продаж (когда будет готов)
6. ⏳ Протестировать полный цикл

## Устранение проблем

### Workflow не активируется
- Проверьте, что все узлы настроены правильно
- Убедитесь, что нет ошибок в узлах (красные индикаторы)
- Проверьте логи выполнения в **Executions**

### KB Search не работает
- Убедитесь, что KB Service запущен: `curl http://localhost:8001/health`
- Проверьте URL в узле "KB Search"
- Проверьте логи KB Service

### Webhook не отвечает
- Убедитесь, что workflow активирован
- Проверьте правильность URL webhook
- Проверьте логи n8n: `docker logs n8n-brats`

