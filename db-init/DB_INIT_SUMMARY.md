# Сводка по инициализации базы данных

## Созданные компоненты

### SQL миграции
1. **01_init_database.sql** - Создание расширения pgvector
2. **02_create_knowledge_base.sql** - Таблица knowledge_base с векторным поиском
3. **03_create_conversations.sql** - Таблицы conversations и messages
4. **04_create_analytics_events.sql** - Таблица analytics_events
5. **05_create_products.sql** - Таблица products с векторным поиском
6. **06_create_proposals.sql** - Таблица proposals

### Скрипты
- **init_all.sh** - Автоматическая инициализация БД с использованием параметров из config.env в корне проекта

## Использование config.env (корень проекта)

Скрипт `init_all.sh` автоматически:
- Читает `DATABASE_URL` из `config.env` в корне репозитория
- Извлекает параметры подключения (host, port, user, password)
- Создаёт базу данных `brats`
- Применяет все миграции

## Размерность векторов

По умолчанию используется **1536** (OpenAI text-embedding-3-small).

Для HuggingFace модели `intfloat/multilingual-e5-base` используется **768**.

### Изменение размерности

Если вы хотите использовать HuggingFace модель (768 dim):

1. Измените в SQL файлах:
   ```sql
   embedding vector(1536)  -- было
   embedding vector(768)   -- стало
   ```

2. Обновите `kb-service/config.env`:
   ```env
   EMBEDDING_PROVIDER=huggingface
   HF_MODEL_NAME=intfloat/multilingual-e5-base
   HF_EMBEDDING_DIMENSION=768
   ```

3. Пересоздайте таблицы или выполните ALTER TABLE:
   ```sql
   ALTER TABLE knowledge_base ALTER COLUMN embedding TYPE vector(768);
   ALTER TABLE products ALTER COLUMN description_embedding TYPE vector(768);
   ```

## Структура базы данных

### Основные таблицы

1. **knowledge_base** - База знаний для RAG
   - Векторный поиск через pgvector
   - Метаданные в JSONB
   - Поддержка мультитенантности (settlement_id)

2. **conversations** - Диалоги с клиентами
   - Состояние FSM
   - Слоты (извлечённые данные)
   - Связь с amoCRM

3. **messages** - История сообщений
   - Связь с conversations
   - Метаданные сообщений

4. **analytics_events** - События аналитики
   - Агрегатор событий из разных источников
   - Используется для обогащения KB

5. **products** - Каталог объектов недвижимости
   - Векторный поиск по описанию
   - Синхронизация с amoCRM
   - Характеристики в JSONB

6. **proposals** - Коммерческие предложения
   - Версионирование
   - Структурированное содержимое

## Быстрый старт

```bash
cd /projects/brats/db-init
./init_all.sh
```

## Проверка

```sql
-- Проверка расширения
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Проверка таблиц
\dt

-- Проверка структуры
\d knowledge_base
\d products
```

## Примечания

- Все таблицы создаются с `IF NOT EXISTS`
- Индексы создаются с `IF NOT EXISTS`
- IVFFlat индекс требует минимум 1000 векторов для эффективной работы
- Для небольших объёмов можно временно использовать обычный индекс

















