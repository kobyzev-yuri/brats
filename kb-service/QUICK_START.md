# Быстрый старт KB Service

## Шаг 1: Установка зависимостей

```bash
cd /projects/brats
source venv/bin/activate
pip install -r requirements.txt
```

## Шаг 2: Настройка конфигурации

```bash
cd kb-service
cp config.env.example config.env
# Отредактируйте config.env:
# - DATABASE_URL - подключение к PostgreSQL
# - OPENAI_API_KEY - ключ для генерации embeddings
```

## Шаг 3: Проверка PostgreSQL и pgvector

Убедитесь, что PostgreSQL запущен и pgvector установлен:

```sql
-- Подключитесь к БД
psql -U postgres -d brats_db

-- Проверьте расширение pgvector
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Если нет, установите:
CREATE EXTENSION IF NOT EXISTS vector;

-- Проверьте таблицу knowledge_base
SELECT COUNT(*) FROM knowledge_base;
```

## Шаг 4: Запуск сервиса

```bash
# Вариант 1: Через скрипт
./start.sh

# Вариант 2: Напрямую
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

## Шаг 5: Проверка работы

Откройте в браузере:
- Документация API: http://localhost:8001/docs
- Health check: http://localhost:8001/health

Или через curl:
```bash
curl http://localhost:8001/health
```

## Шаг 6: Тестовый импорт данных

```bash
# Импорт из kb_info.txt
curl -X POST http://localhost:8001/api/kb/import \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "../docs/kb_info.txt",
    "category": "sales_script",
    "target_audience": "both",
    "chunk_size": 3000,
    "chunk_overlap": 300
  }'
```

## Шаг 7: Тестовый поиск

```bash
curl -X POST http://localhost:8001/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "как обработать возражение о цене",
    "limit": 5,
    "min_similarity": 0.6
  }'
```

## Следующие шаги

1. Импортируйте данные из `docs/kb_info.txt`
2. Настройте интеграцию с n8n (см. `N8N_INTEGRATION.md`)
3. Подключите к агенту продаж
4. Протестируйте работу в реальных диалогах

## Устранение проблем

### Ошибка подключения к БД
- Проверьте DATABASE_URL в config.env
- Убедитесь, что PostgreSQL запущен
- Проверьте права доступа пользователя

### Ошибка генерации embeddings
- Проверьте OPENAI_API_KEY в config.env
- Убедитесь, что есть доступ к интернету
- Проверьте лимиты API ключа

### Ошибка pgvector
- Убедитесь, что расширение установлено: `CREATE EXTENSION vector;`
- Проверьте версию PostgreSQL (нужна 11+)

### Таблица knowledge_base не существует
- Создайте таблицу согласно схеме из `docs/KB.md` и db-init
- Или используйте миграции из `shared-db/migrations/`

















