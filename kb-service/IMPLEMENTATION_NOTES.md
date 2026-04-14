# Заметки по реализации KB Service

## Дата начала: 2026-02-03

## Цель
Создать сервис управления базой знаний (KB) на основе pgvector для интеграции с нейропродажником через n8n.

## Источник реализации
Проект `~/sql4A/` - изучена структура и адаптирована под наши нужды.

## Ключевые компоненты из sql4A

### 1. Конфигурация (config.env)
- Используется тот же подход с `.env` файлом
- Настройки LLM провайдера (OpenAI/Ollama)
- Параметры chunking для разных типов контента
- Database URL для PostgreSQL

### 2. Работа с pgvector
- Таблица `knowledge_base` с полем `embedding vector(1536)`
- Векторный поиск через оператор `<=>` (cosine distance)
- Индексы IVFFlat для быстрого поиска

### 3. FastAPI структура
- `api/main.py` - основной FastAPI app
- `services/` - бизнес-логика
- `models/` - Pydantic модели для запросов/ответов

### 4. Генерация embeddings
- Используется OpenAI API (text-embedding-3-small)
- Можно переключить на локальные модели через sentence-transformers

## Адаптация под наш проект

### Отличия от sql4A:
1. **Таблица**: `knowledge_base` вместо `vanna_vectors`
2. **Метаданные**: структура под наши категории (product_info, sales_script, objection_handling и т.д.)
3. **Целевая аудитория**: фильтрация по `target_audience` (end_buyer, realtor, both)
4. **Мультитенантность**: поддержка нескольких поселков через `metadata->>'settlement_id'`

### Что взято из sql4A:
- Логика chunking с умными границами
- Генерация embeddings через OpenAI
- Векторный поиск через asyncpg
- Структура FastAPI сервиса

## Реализованные компоненты

### ✅ Структура проекта
- `kb-service/` - корневая директория сервиса
- `api/` - FastAPI endpoints
- `services/` - бизнес-логика (kb_service, embedding_service, chunking_service)
- `models/` - Pydantic модели (requests, responses)
- `utils/` - утилиты (db.py для работы с PostgreSQL)

### ✅ Сервисы
1. **EmbeddingService** (`services/embedding_service.py`)
   - Генерация embeddings через OpenAI API
   - Поддержка батчей для эффективной обработки
   - Модель: text-embedding-3-small (1536 измерений)

2. **ChunkingService** (`services/chunking_service.py`)
   - Разбиение текста на chunks с умными границами
   - Поддержка overlap для сохранения контекста
   - Разбиение по абзацам и предложениям

3. **KBService** (`services/kb_service.py`)
   - CRUD операции с chunks
   - Семантический поиск через pgvector
   - Импорт текста с автоматическим chunking
   - Статистика по KB

### ✅ API Endpoints
- `POST /api/kb/search` - семантический поиск
- `POST /api/kb/add` - добавление chunk
- `GET /api/kb/{id}` - получение chunk
- `PUT /api/kb/{id}` - обновление chunk
- `DELETE /api/kb/{id}` - удаление chunk
- `POST /api/kb/import` - импорт текста
- `GET /api/kb/stats` - статистика
- `GET /health` - проверка здоровья

## Реализованные компоненты (статус)

1. ✅ Создана структура проекта
2. ✅ Создан requirements.txt
3. ✅ Создан config.env.example
4. ✅ Реализован kb_service.py (основной сервис работы с KB)
5. ✅ Реализован embedding_service.py (генерация embeddings через OpenAI)
6. ✅ Реализован chunking_service.py (разбиение текста на chunks)
7. ✅ Созданы API endpoints (CRUD, поиск, импорт, статистика)
8. ✅ Созданы модели Pydantic (requests, responses)
9. ✅ Создана документация (README, QUICK_START, N8N_INTEGRATION)
10. ✅ Создан скрипт запуска (start.sh)

## Следующие шаги

1. ⏳ Создать интерфейс управления KB (Streamlit - опционально, можно использовать API напрямую)
2. ⏳ Интеграция с n8n (HTTP Request nodes) - см. N8N_INTEGRATION.md
3. ⏳ Тестирование поиска и импорта
4. ⏳ Подключение к агенту продаж в n8n workflow
5. ⏳ Импорт данных из kb_info.txt

## Важные файлы для изучения в sql4A

- `~/sql4A/src/services/query_service.py` - работа с векторной БД
- `~/sql4A/src/vector_kb_interface.py` - интерфейс управления KB (Streamlit)
- `~/sql4A/src/api/main.py` - структура FastAPI
- `~/sql4A/config.env` - конфигурация

## Команды для быстрого старта

```bash
# Активация venv
cd /projects/brats
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка config.env
cp kb-service/config.env.example kb-service/config.env
# Отредактировать config.env с вашими настройками

# Запуск сервиса
cd kb-service
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

## Проверка работы

1. Проверить health endpoint:
```bash
curl http://localhost:8001/health
```

2. Попробовать поиск:
```bash
curl -X POST http://localhost:8001/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{"query": "как обработать возражение о цене", "limit": 5}'
```

3. Открыть документацию:
```
http://localhost:8001/docs
```

## Связь с документацией проекта

- `docs/KB.md` — структура и использование KB
- `docs/POSTGRESQL_ARCHITECTURE_EXPLAINED.md` - архитектура таблицы knowledge_base
- `README.md` - общая архитектура проекта
- `BUSINESS_PROCESSES.md` - бизнес-процессы

## Примечания

- Используется существующая БД PostgreSQL из ~/sql4A/ или можно создать новую
- pgvector должен быть установлен в PostgreSQL
- Таблица `knowledge_base` должна быть создана согласно схеме из README.md
- Для работы нужен OpenAI API ключ (или можно переключить на локальные модели)
