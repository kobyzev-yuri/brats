# Быстрый старт n8n для интеграции KB с агентом продаж

## Предварительные требования

1. **Docker** установлен и запущен
2. **KB Service** запущен на `http://localhost:8001`
3. **PostgreSQL** с базой `brats` настроена

## Шаг 1: Запуск n8n

```bash
cd /projects/brats/n8n
docker-compose up -d
```

Проверка запуска:
```bash
docker ps | grep n8n
curl http://localhost:5678/healthz
```

## Шаг 2: Открытие n8n в браузере

Откройте: http://localhost:5678

**Первоначальная настройка:**
- Создайте учетную запись администратора
- Или используйте логин из `docker-compose.yml`:
  - Username: `admin`
  - Password: `changeme` (рекомендуется изменить!)

## Шаг 3: Импорт workflow

1. В n8n перейдите: **Workflows** → **Import from File**
2. Выберите файл: `/projects/brats/n8n/workflows/sales-agent-kb-integration.json`
3. Workflow будет импортирован

## Шаг 4: Настройка workflow

### Проверка KB Service

В узле **KB Search** убедитесь, что URL правильный:
- URL: `http://localhost:8001/api/kb/search`

Если KB Service на другом хосте, измените URL.

### Настройка Sales Agent

В узле **Sales Agent Call** укажите URL вашего агента:
- URL: `http://localhost:8000/api/chat` (или ваш URL)

Если агент еще не реализован, можно временно использовать mock endpoint или закомментировать этот узел.

## Шаг 5: Активация workflow (Publish)

1. Откройте импортированный workflow
2. Нажмите кнопку **Publish** (в правом верхнем углу)
3. Workflow будет опубликован и активирован
4. Workflow готов принимать запросы

## Шаг 6: Тестирование

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

### Просмотр выполнения

В n8n перейдите в **Executions** для просмотра истории выполнения workflow.

## Остановка n8n

```bash
cd /projects/brats/n8n
docker-compose down
```

## Обновление n8n

```bash
cd /projects/brats/n8n
docker-compose pull
docker-compose up -d
```

## Устранение проблем

### n8n не запускается

```bash
# Проверка логов
docker-compose logs n8n

# Проверка порта
netstat -tuln | grep 5678
```

### KB Service недоступен

```bash
# Проверка KB Service
curl http://localhost:8001/health

# Если не запущен, запустите:
cd /projects/brats/kb-service
./start.sh
```

### Workflow не активируется

- Проверьте, что все узлы настроены правильно
- Убедитесь, что нет ошибок в узлах (красные индикаторы)
- Проверьте логи выполнения в **Executions**

## Следующие шаги

1. ✅ Установить и запустить n8n
2. ✅ Импортировать workflow
3. ⏳ Настроить интеграцию с реальным агентом продаж
4. ⏳ Добавить обработку ошибок
5. ⏳ Настроить интеграцию с Telegram/Avito
6. ⏳ Добавить логирование в БД

