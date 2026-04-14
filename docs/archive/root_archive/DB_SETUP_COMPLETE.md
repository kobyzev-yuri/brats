# Инициализация базы данных brats - Завершено ✅

## Что создано

### 1. SQL миграции (`db-init/`)
- ✅ `01_init_database.sql` - Создание расширения pgvector
- ✅ `02_create_knowledge_base.sql` - Таблица knowledge_base с векторным поиском
- ✅ `03_create_conversations.sql` - Таблицы conversations и messages
- ✅ `04_create_analytics_events.sql` - Таблица analytics_events
- ✅ `05_create_products.sql` - Таблица products с векторным поиском
- ✅ `06_create_proposals.sql` - Таблица proposals

### 2. Скрипт автоматической инициализации
- ✅ `init_all.sh` - Автоматическая инициализация с использованием параметров из `~/sql4A/config.env`

### 3. Обновления KB Service
- ✅ Поддержка HuggingFace моделей через sentence-transformers
- ✅ Автоматическое определение провайдера (OpenAI или HuggingFace)
- ✅ Поддержка разных размерностей векторов (1536 для OpenAI, 768 для HF)

### 4. Конфигурация
- ✅ Обновлён `kb-service/config.env.example` с параметрами из `~/sql4A/config.env`
- ✅ Добавлена поддержка `HF_MODEL_NAME=intfloat/multilingual-e5-base`

## Использование параметров из ~/sql4A/config.env

Скрипт `init_all.sh` автоматически:
1. Читает `DATABASE_URL` из `~/sql4A/config.env`
2. Извлекает параметры подключения (host, port, user, password)
3. Создаёт базу данных `brats`
4. Применяет все миграции по порядку

## Быстрый старт

```bash
# 1. Инициализация базы данных
cd /projects/brats/db-init
./init_all.sh

# 2. Настройка KB Service
cd /projects/brats/kb-service
cp config.env.example config.env
# Отредактировать config.env с вашими настройками

# 3. Запуск KB Service
./start.sh
```

## Размерность векторов

### По умолчанию: 1536 (OpenAI)
- Используется `text-embedding-3-small` (1536 dim)
- Таблицы создаются с `vector(1536)`

### Альтернатива: 768 (HuggingFace)
Если хотите использовать `intfloat/multilingual-e5-base`:

1. **Измените SQL файлы** (или выполните ALTER TABLE):
   ```sql
   ALTER TABLE knowledge_base ALTER COLUMN embedding TYPE vector(768);
   ALTER TABLE products ALTER COLUMN description_embedding TYPE vector(768);
   ```

2. **Обновите config.env**:
   ```env
   EMBEDDING_PROVIDER=huggingface
   HF_MODEL_NAME=intfloat/multilingual-e5-base
   HF_EMBEDDING_DIMENSION=768
   ```

3. **Пересоздайте индексы**:
   ```sql
   DROP INDEX IF EXISTS idx_knowledge_base_embedding;
   CREATE INDEX idx_knowledge_base_embedding 
       ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   ```

## Структура базы данных

### Основные таблицы

1. **knowledge_base** - База знаний для RAG
   - Векторный поиск через pgvector (`embedding vector(1536)`)
   - Метаданные в JSONB
   - Поддержка мультитенантности (`metadata->>'settlement_id'`)

2. **conversations** - Диалоги с клиентами
   - Состояние FSM (`state`)
   - Слоты (`slots JSONB`)
   - Связь с amoCRM (`amocrm_lead_id`, `amocrm_contact_id`)

3. **messages** - История сообщений
   - Связь с conversations
   - Метаданные сообщений (`metadata JSONB`)

4. **analytics_events** - События аналитики
   - Агрегатор событий из разных источников
   - Используется для обогащения KB

5. **products** - Каталог объектов недвижимости
   - Векторный поиск по описанию (`description_embedding vector(1536)`)
   - Синхронизация с amoCRM
   - Характеристики в JSONB

6. **proposals** - Коммерческие предложения
   - Версионирование (`version`, `parent_proposal_id`)
   - Структурированное содержимое (`content_structured JSONB`)

## Проверка

После инициализации проверьте:

```sql
-- Подключение к базе
\c brats

-- Проверка расширения pgvector
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Проверка таблиц
\dt

-- Проверка структуры knowledge_base
\d knowledge_base

-- Проверка индексов
\di
```

## Краткое резюме: инициализация, тестирование и поддержка KB

### Инициализация

1. **Создание БД и таблиц**
   - Скрипты миграций: `db-init/01_init_database.sql` … `06_create_proposals.sql`
   - Автоинициализация:  
     ```bash
     cd /projects/brats/db-init
     ./init_all.sh
     ```
   - Расширение `pgvector` включено, таблица `knowledge_base` создана.

2. **Настройка KB Service**
   - Конфигурация: `kb-service/config.env` (копия `config.env.example`)
   - Важно:
     - `DATABASE_URL=postgresql://postgres:1234@localhost:5432/brats`
     - `OPENAI_API_KEY` / `OPENAI_BASE_URL`
   - Запуск сервиса:
     ```bash
     cd /projects/brats/kb-service
     ./start.sh
     # Health-check:
     curl http://localhost:8001/health
     ```

### Тестирование KB

1. **Импорт тестовых данных**
   - Импорт из `Саммари встречи.odt`:
     ```bash
     cd /projects/brats
     ./scripts/quick_import_meeting.sh
     ```
   - Результат: 44 chunks в `knowledge_base` (категории: product_info, sales_script, objection_handling, target_audience, tone_of_voice, pricing, contacts).

2. **Проверка данных в БД**
   - Скрипт проверки:
     ```bash
     ./scripts/check_kb_data.sh
     ```
   - Показывает:
     - Примеры chunks по `source = 'Саммари встречи.odt'`
     - Статистику по категориям
     - Общее число chunks / активных записей

3. **Проверка поиска**
   - Прямой HTTP-запрос:
     ```bash
     curl -X POST http://localhost:8001/api/kb/search \
       -H "Content-Type: application/json" \
       -d '{
         "query": "коттеджный посёлок",
         "limit": 5,
         "min_similarity": 0.0
       }'
     ```
   - Рекомендуемые значения `min_similarity`: 0.2–0.4 (подбираются экспериментально).

### Поддержка и администрирование KB

1. **Web-интерфейс (Streamlit)**
   - Приложение: `kb-service/web/kb_admin_app.py`
   - Запуск:
     ```bash
     cd /projects/brats
     source venv/bin/activate
     cd kb-service
     streamlit run web/kb_admin_app.py --server.port 8501
     ```
   - Функции:
     - Обзор и поиск chunks (фильтры по категории, схожести)
     - Редактирование контента и метаданных (category, target_audience, priority, tags, source, is_active)
     - Импорт текста и `.txt` файлов с автоматическим chunking
     - Просмотр статистики KB.

2. **CLI и скрипты**
   - Импорт из ODT: `scripts/import_meeting_summary.py`
   - Быстрый импорт: `scripts/quick_import_meeting.sh`
   - Проверка данных: `scripts/check_kb_data.sh`

3. **Интеграция с n8n**
   - KB Service доступен по `http://localhost:8001`
   - Используется в workflow через HTTP Request ноды:
     - `POST /api/kb/search` — поиск для агента продаж
     - `POST /api/kb/add` / `/api/kb/import` — наполнение KB
   - Детали: `kb-service/N8N_INTEGRATION.md`

### Краткий чек-лист

- [x] БД `brats` создана, pgvector включён
- [x] Таблица `knowledge_base` и связанные таблицы созданы (через `db-init`)
- [x] KB Service запущен (`./start.sh`), health OK
- [x] Тестовые данные из `Саммари встречи.odt` импортированы (44 chunks)
- [x] Поиск в KB работает (проверен через HTTP и прямой SQL)
- [x] Web UI для администрирования KB (`kb_admin_app.py`) готов

## Важные файлы

- **Миграции**: `db-init/*.sql`
- **Скрипт инициализации**: `db-init/init_all.sh`
- **Документация**: `db-init/README.md`
- **Конфигурация KB Service**: `kb-service/config.env.example`

## Примечания

- Все таблицы создаются с `IF NOT EXISTS` - можно запускать повторно
- Индексы создаются с `IF NOT EXISTS`
- IVFFlat индекс требует минимум 1000 векторов для эффективной работы
- Для небольших объёмов можно временно использовать обычный индекс
- Используются параметры подключения из `~/sql4A/config.env` (как в проекте sql4A)

