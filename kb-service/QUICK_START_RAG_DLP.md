# Быстрый старт: RAG + DLP + GPT-4o

## Шаг 1: Настройка конфигурации

Скопируйте `config.env.example` в `config.env` и заполните:

```bash
cd kb-service
cp config.env.example config.env
```

Отредактируйте `config.env`:

```bash
# LLM через proxyapi.ru
OPENAI_API_KEY=your_proxyapi_key_here
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/brats
```

## Шаг 2: Установка зависимостей

```bash
pip install -r ../requirements.txt
```

## Шаг 3: Запуск сервиса

```bash
python api/main.py
```

Сервис будет доступен на `http://localhost:8001`

## Шаг 4: Тестирование

### Вариант 1: Автоматический тест

```bash
python test_rag_dlp.py
```

### Вариант 2: Ручной тест через curl

```bash
curl -X POST http://localhost:8001/api/rag/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Расскажите о ценах на коттеджи",
    "context": {
      "visitor_id": "test_123",
      "phone": "+7 (988) 199-89-98",
      "email": "test@example.com"
    },
    "sanitize_context": true
  }'
```

### Вариант 3: Через Swagger UI

Откройте в браузере: http://localhost:8001/docs

Найдите endpoint `/api/rag/webhook` и протестируйте через интерфейс.

## Проверка работы DLP

В ответе от LLM не должно быть:
- ❌ Реальных телефонов (`+7 (988) 199-89-98`)
- ❌ Реальных email (`test@example.com`)
- ❌ Реальных имен и идентификаторов

Вместо этого должны быть:
- ✅ Маскированные данные (`+7 *** ***-**-**`)
- ✅ Псевдонимы (`VISITOR_ab12cd34`)

## Troubleshooting

**Ошибка: "OPENAI_API_KEY не настроен"**
- Проверьте файл `config.env`
- Убедитесь, что указан правильный ключ от proxyapi.ru

**Ошибка: "KB Service недоступен"**
- Убедитесь, что PostgreSQL запущен
- Проверьте `DATABASE_URL` в `config.env`

**Медленные ответы**
- Уменьшите `limit` в запросе
- Проверьте подключение к proxyapi.ru

---

Подробная документация: [`RAG_DLP_INTEGRATION.md`](./RAG_DLP_INTEGRATION.md)















