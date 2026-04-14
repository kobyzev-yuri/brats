# Интеграция KB Service с n8n

## Обзор

KB Service предоставляет REST API для использования в n8n workflows. Это позволяет агенту продаж получать релевантную информацию из базы знаний для ответов клиентам.

## Настройка в n8n

### 1. Создание Credentials для KB Service

В n8n создайте новый Credential типа "HTTP Header Auth" или "Generic Credential Type":
- **Name**: `KB Service`
- **Base URL**: `http://localhost:8001` (или ваш URL)
- **Headers**: (опционально, если нужна авторизация)

### 2. Основные Workflow узлы

#### Поиск в KB для агента продаж

**Узел: HTTP Request**
- **Method**: POST
- **URL**: `http://localhost:8001/api/kb/search`
- **Body**:
```json
{
  "query": "{{ $json.message }}",
  "limit": 5,
  "target_audience": "both",
  "min_similarity": 0.6
}
```

**Использование в workflow:**
```
[Telegram Bot] → [HTTP Request: KB Search] → [Sales Agent] → [Response to Client]
```

#### Получение контекста для промпта агента

**Узел: Function** (для форматирования результатов KB):
```javascript
// Форматируем результаты KB для промпта
const kbResults = $input.all();
let context = "База знаний:\n\n";

kbResults.forEach((item, index) => {
  const result = item.json.results[0]; // Берем первый результат
  if (result) {
    context += `${index + 1}. ${result.content}\n`;
    context += `   (Категория: ${result.metadata.category}, Схожесть: ${result.similarity.toFixed(2)})\n\n`;
  }
});

return { json: { kb_context: context } };
```

### 3. Пример Workflow: Обработка сообщения с использованием KB

```
1. [Webhook] Telegram Bot → получает сообщение
2. [HTTP Request] KB Search → поиск в KB по тексту сообщения
3. [Function] Форматирование KB контекста → подготовка для промпта
4. [HTTP Request] Sales Agent → отправка сообщения + KB контекст
5. [HTTP Request] Telegram Bot → отправка ответа клиенту
```

### 4. Пример Workflow: Импорт данных в KB

```
1. [Manual Trigger] или [Schedule] → запуск импорта
2. [Read Binary File] → чтение kb_info.txt
3. [HTTP Request] KB Import → отправка в KB Service
   - URL: http://localhost:8001/api/kb/import
   - Body:
   {
     "content": "{{ $binary.data }}",
     "category": "sales_script",
     "target_audience": "both",
     "chunk_size": 3000,
     "chunk_overlap": 300
   }
```

## API Endpoints для n8n

### Поиск в KB
- **Endpoint**: `POST /api/kb/search`
- **Использование**: Получение релевантных chunks для ответа клиенту
- **Пример запроса**:
```json
{
  "query": "как обработать возражение о высокой цене",
  "limit": 5,
  "category": "objection_handling",
  "target_audience": "end_buyer",
  "min_similarity": 0.7
}
```

### Добавление chunk
- **Endpoint**: `POST /api/kb/add`
- **Использование**: Добавление нового материала в KB из диалогов или примечаний
- **Пример запроса**:
```json
{
  "content": "Если клиент говорит о высокой цене, подчеркните уникальные преимущества...",
  "category": "objection_handling",
  "target_audience": "end_buyer",
  "priority": "high",
  "tags": ["цена", "возражение", "преимущества"]
}
```

### Импорт текста
- **Endpoint**: `POST /api/kb/import`
- **Использование**: Массовый импорт из файлов (kb_info.txt и др.)
- **Пример запроса**:
```json
{
  "file_path": "/path/to/kb_info.txt",
  "category": "sales_script",
  "chunk_size": 3000,
  "chunk_overlap": 300
}
```

### Статистика KB
- **Endpoint**: `GET /api/kb/stats`
- **Использование**: Мониторинг состояния KB

## Интеграция с Sales Agent

В workflow агента продаж добавьте узел поиска KB перед генерацией ответа:

```
[Client Message] 
  ↓
[KB Search] → получаем релевантные chunks
  ↓
[Format KB Context] → форматируем для промпта
  ↓
[LLM Call] → генерируем ответ с контекстом KB
  ↓
[Response to Client]
```

**Промпт для LLM с KB контекстом:**
```
Ты - нейропродажник. Используй следующую информацию из базы знаний для ответа клиенту:

{{ $json.kb_context }}

Вопрос клиента: {{ $json.client_message }}

Сгенерируй ответ, используя информацию из базы знаний.
```

## Тестирование интеграции

1. **Проверка health endpoint**:
   - В n8n создайте HTTP Request узел
   - URL: `http://localhost:8001/health`
   - Method: GET
   - Должен вернуть `{"status": "healthy"}`

2. **Тест поиска**:
   - Создайте HTTP Request узел
   - URL: `http://localhost:8001/api/kb/search`
   - Method: POST
   - Body: `{"query": "тест", "limit": 3}`

3. **Тест добавления**:
   - Создайте HTTP Request узел
   - URL: `http://localhost:8001/api/kb/add`
   - Method: POST
   - Body: `{"content": "Тестовый chunk", "category": "product_info"}`

## Примечания

- KB Service должен быть запущен перед использованием в n8n
- Для продакшена используйте HTTPS и настройте авторизацию
- Рекомендуется кэшировать результаты поиска KB для часто задаваемых вопросов
- Мониторьте производительность поиска через `/api/kb/stats`

















