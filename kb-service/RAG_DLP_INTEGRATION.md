# Интеграция RAG + DLP + GPT-4o через proxyapi.ru

## Обзор

Реализована полная интеграция RAG (Retrieval-Augmented Generation) с DLP (Data Loss Prevention) для безопасной работы с GPT-4o через proxyapi.ru.

## Компоненты

### 1. DLP Service (`services/dlp_service.py`)

**Назначение:** Обезличивание персональных данных перед отправкой в зарубежные LLM

**Функции:**
- Удаление запрещенных полей (phone, email, passport, inn и т.д.)
- Маскирование паттернов в тексте (телефоны, email, номера карт)
- Псевдонимизация идентификаторов (visitor_id, session_id)

**Пример использования:**
```python
from services.dlp_service import get_dlp_service

dlp = get_dlp_service()

# Обезличивание данных
sanitized = dlp.sanitize_for_llm({
    "name": "Иван Иванов",
    "phone": "+7 (988) 199-89-98",
    "email": "ivan@example.com"
})
# Результат: {"name": "***", "phone": "+7 *** ***-**-**", "email": "user***@example.com"}
```

### 2. LLM Service (`services/llm_service.py`)

**Назначение:** Работа с GPT-4o через proxyapi.ru

**Конфигурация:**
```bash
# config.env
OPENAI_API_KEY=your_proxyapi_key
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT=60
```

**Функции:**
- `generate_response()` - генерация ответа
- `generate_with_rag()` - генерация с использованием RAG
- `generate_streaming()` - стриминг ответа

**Автоматическое обезличивание:**
Все данные автоматически обезличиваются через DLP перед отправкой в LLM.

### 3. RAG Service (`services/rag_service.py`)

**Назначение:** Объединение поиска в KB, DLP и LLM

**Workflow:**
1. Поиск в KB по запросу пользователя
2. Обезличивание результатов KB через DLP
3. Формирование промпта с контекстом из KB
4. Генерация ответа через LLM
5. Возврат ответа с источниками

**Пример использования:**
```python
from services.rag_service import get_rag_service

rag = get_rag_service()

result = await rag.generate_response(
    query="Расскажите о ценах на коттеджи",
    context={"visitor_id": "visitor_123"},
    category="product_info",
    sanitize_context=True  # Включаем DLP
)
```

## API Endpoints

### 1. `/api/rag/generate` (POST)

**Описание:** Генерация ответа с использованием RAG

**Запрос:**
```json
{
  "query": "Расскажите о ценах на коттеджи",
  "context": {
    "visitor_id": "visitor_123",
    "slots": {
      "budget": 10000000
    }
  },
  "category": "product_info",
  "target_audience": "end_buyer",
  "limit": 5,
  "min_similarity": 0.6,
  "sanitize_context": true
}
```

**Ответ:**
```json
{
  "response": "Ответ от LLM...",
  "sources": [
    {
      "id": 1,
      "content": "Фрагмент из KB...",
      "similarity": 0.85,
      "metadata": {...}
    }
  ],
  "kb_results_count": 3,
  "llm_usage": {
    "prompt_tokens": 500,
    "completion_tokens": 200,
    "total_tokens": 700
  },
  "model": "gpt-4o",
  "finish_reason": "stop"
}
```

### 2. `/api/rag/stream` (POST)

**Описание:** Генерация ответа в режиме стриминга

**Использование:**
```bash
curl -X POST http://localhost:8001/api/rag/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Расскажите о ценах"}' \
  --no-buffer
```

### 3. `/api/rag/webhook` (POST)

**Описание:** Webhook endpoint для интеграции с n8n и другими сервисами

**Формат запроса:**
```json
{
  "query": "Расскажите о ценах",
  "message": "Альтернативное поле для запроса",
  "text": "Еще один вариант",
  "context": {
    "visitor_id": "visitor_123",
    "phone": "+7 (988) 199-89-98",
    "email": "user@example.com"
  },
  "category": "product_info",
  "sanitize_context": true
}
```

**Формат ответа:**
```json
{
  "success": true,
  "response": "Ответ от LLM...",
  "sources": [...],
  "metadata": {
    "kb_results_count": 3,
    "llm_usage": {...},
    "model": "gpt-4o"
  }
}
```

## Тестирование

### Запуск тестов

```bash
cd kb-service
python test_rag_dlp.py
```

Тесты проверяют:
1. ✅ Работу DLP сервиса (обезличивание данных)
2. ✅ Генерацию ответов через RAG
3. ✅ Webhook endpoint
4. ✅ Отсутствие утечек персональных данных

### Ручное тестирование через curl

```bash
# Тест webhook
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

# Тест generate endpoint
curl -X POST http://localhost:8001/api/rag/generate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Какие варианты отделки доступны?",
    "category": "product_info",
    "limit": 5
  }'
```

## Интеграция с n8n

### Workflow для n8n

1. **Webhook узел** - принимает запрос от внешнего сервиса
2. **HTTP Request узел** - отправляет запрос в `/api/rag/webhook`
3. **Обработка ответа** - использование ответа в дальнейшем workflow

**Пример n8n workflow:**
```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "rag-query",
        "httpMethod": "POST"
      }
    },
    {
      "name": "RAG Request",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://localhost:8001/api/rag/webhook",
        "body": {
          "query": "={{ $json.query }}",
          "context": "={{ $json.context }}",
          "sanitize_context": true
        }
      }
    }
  ]
}
```

## Безопасность

### Что обезличивается автоматически:

1. **Телефоны:** `+7 (988) 199-89-98` → `+7 *** ***-**-**`
2. **Email:** `user@example.com` → `user***@example.com`
3. **Паспорта:** `1234 567890` → `**** ******`
4. **ИНН:** `1234567890` → `***`
5. **Номера карт:** `1234 5678 9012 3456` → `**** **** **** ****`
6. **Идентификаторы:** `visitor_123` → `VISITOR_ab12cd34` (псевдоним)

### Запрещенные поля (удаляются):

- `phone`, `email`, `passport`, `inn`, `kpp`
- `bank_account`, `card_number`
- `amocrm_lead_id`, `amocrm_contact_id`
- `visitor_id`, `user_id`, `client_id`
- `full_name`, `first_name`, `last_name`
- `address`, `birth_date`, `snils`

## Конфигурация

### config.env

```bash
# LLM Configuration (proxyapi.ru)
OPENAI_API_KEY=your_proxyapi_key_here
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT=60

# Embedding Configuration
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/brats
```

## Запуск сервиса

```bash
cd kb-service

# Установка зависимостей
pip install -r ../requirements.txt

# Запуск сервиса
python api/main.py
```

Сервис будет доступен на `http://localhost:8001`

## Документация API

После запуска доступна Swagger документация:
- http://localhost:8001/docs
- http://localhost:8001/redoc

## Примеры использования

### Python

```python
import httpx
import asyncio

async def test_rag():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/rag/webhook",
            json={
                "query": "Расскажите о ценах",
                "context": {
                    "visitor_id": "test_123",
                    "phone": "+7 (988) 199-89-98"
                },
                "sanitize_context": True
            }
        )
        result = response.json()
        print(result["response"])

asyncio.run(test_rag())
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

async function testRAG() {
  const response = await axios.post('http://localhost:8001/api/rag/webhook', {
    query: 'Расскажите о ценах',
    context: {
      visitor_id: 'test_123',
      phone: '+7 (988) 199-89-98'
    },
    sanitize_context: true
  });
  
  console.log(response.data.response);
}

testRAG();
```

## Troubleshooting

### Ошибка: "OPENAI_API_KEY не настроен"

**Решение:** Проверьте файл `config.env` и убедитесь, что указан правильный API ключ от proxyapi.ru

### Ошибка: "KB Service недоступен"

**Решение:** 
1. Убедитесь, что сервис запущен: `python api/main.py`
2. Проверьте, что порт 8001 свободен
3. Проверьте подключение к PostgreSQL

### Медленная генерация ответов

**Решение:**
- Уменьшите `limit` в запросе (меньше результатов из KB)
- Уменьшите `max_tokens` для LLM
- Используйте стриминг для лучшего UX

## Следующие шаги

1. ✅ Интеграция с n8n workflow
2. ✅ Добавление метрик и мониторинга
3. ✅ Кэширование частых запросов
4. ✅ Оптимизация промптов для лучших ответов

---

**Последнее обновление:** 2025-02-07















