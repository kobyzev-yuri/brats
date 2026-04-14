# Инициализация базы данных brats

## Описание

Скрипты для создания базы данных `brats` и всех необходимых таблиц с поддержкой pgvector.

## Структура миграций

1. **01_init_database.sql** - Создание расширения pgvector
2. **02_create_knowledge_base.sql** - Таблица knowledge_base для базы знаний
3. **03_create_conversations.sql** - Таблицы conversations и messages для диалогов
4. **04_create_analytics_events.sql** - Таблица analytics_events для событий аналитики
5. **05_create_products.sql** - Таблица products для каталога объектов недвижимости
6. **06_create_proposals.sql** - Таблица proposals для коммерческих предложений
7. **07_viewing_slots_and_templates.sql** - Календарь показов (viewing_slots), шаблоны КП/договоров (document_templates)
8. **08_seed_samples.sql** - Образцы: 2 объекта в products, 2 шаблона документов, слоты календаря на 5 дней

## Быстрый старт

### Автоматическая инициализация

```bash
cd /projects/brats/db-init
./init_all.sh
```

Скрипт:
1. Читает параметры подключения из `config.env` в корне проекта
2. Создаёт базу данных `brats` (если не существует)
3. Применяет все миграции по порядку

### Ручная инициализация

```bash
# 1. Создать базу данных
psql -U postgres -c "CREATE DATABASE brats;"

# 2. Применить миграции
psql -U postgres -d brats -f 01_init_database.sql
psql -U postgres -d brats -f 02_create_knowledge_base.sql
psql -U postgres -d brats -f 03_create_conversations.sql
psql -U postgres -d brats -f 04_create_analytics_events.sql
psql -U postgres -d brats -f 05_create_products.sql
psql -U postgres -d brats -f 06_create_proposals.sql
psql -U postgres -d brats -f 07_viewing_slots_and_templates.sql
psql -U postgres -d brats -f 08_seed_samples.sql
```

## Проверка

После инициализации проверьте:

```sql
-- Проверка расширения pgvector
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Проверка таблиц
\dt

-- Проверка структуры knowledge_base
\d knowledge_base

-- Проверка индексов
\di
```

## Использование config.env (корень проекта)

Скрипт `init_all.sh` читает параметры из `config.env` в корне репозитория:
- `DATABASE_URL` — для подключения к PostgreSQL (host, port, user, password)
- Создаётся база данных `brats` (имя базы в URL не используется)

## Размерность векторов

По умолчанию используется размерность **1536** (для OpenAI text-embedding-3-small).

Если вы используете HuggingFace модель `intfloat/multilingual-e5-base`, размерность будет **768**.

Для изменения размерности:
1. Измените `vector(1536)` на `vector(768)` в SQL файлах
2. Обновите `EMBEDDING_DIMENSION` в `kb-service/config.env`

## Примечания

- Все таблицы создаются с `IF NOT EXISTS`, можно запускать повторно
- Индексы создаются с `IF NOT EXISTS`
- IVFFlat индекс требует минимум 1000 векторов для эффективной работы
- Для небольших объёмов данных можно временно использовать обычный индекс

















