# Следующие шаги после инициализации БД

## ✅ База данных создана успешно!

База данных `brats` инициализирована со всеми необходимыми таблицами.

## Проверка структуры

Выполните следующие команды для проверки:

```bash
# Подключение к базе данных
psql -U postgres -d brats

# Проверка расширения pgvector
SELECT * FROM pg_extension WHERE extname = 'vector';

# Список всех таблиц
\dt

# Структура таблицы knowledge_base
\d knowledge_base

# Структура таблицы products
\d products

# Проверка индексов
\di
```

## Настройка KB Service

1. **Скопируйте и настройте config.env**:
   ```bash
   cd /projects/brats/kb-service
   cp config.env.example config.env
   ```

2. **Отредактируйте config.env**:
   - `DATABASE_URL=postgresql://postgres:1234@localhost:5432/brats`
   - `OPENAI_API_KEY` - ваш ключ из ~/sql4A/config.env
   - `OPENAI_BASE_URL` - из ~/sql4A/config.env
   - Или настройте HuggingFace модель:
     ```env
     EMBEDDING_PROVIDER=huggingface
     HF_MODEL_NAME=intfloat/multilingual-e5-base
     HF_EMBEDDING_DIMENSION=768
     ```

3. **Установите зависимости** (если ещё не установлены):
   ```bash
   cd /projects/brats
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Запуск KB Service

```bash
cd /projects/brats/kb-service
./start.sh
```

Или напрямую:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

## Проверка работы KB Service

1. **Health check**:
   ```bash
   curl http://localhost:8001/health
   ```

2. **Откройте документацию API**:
   ```
   http://localhost:8001/docs
   ```

3. **Тестовый поиск** (после импорта данных):
   ```bash
   curl -X POST http://localhost:8001/api/kb/search \
     -H "Content-Type: application/json" \
     -d '{
       "query": "тест",
       "limit": 5
     }'
   ```

## Импорт данных в KB

После запуска KB Service можно импортировать данные:

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

Или через Python скрипт (если есть):
```bash
python docs/kb_import_example.py
```

## Проверка данных в БД

```sql
-- Подключение к базе
psql -U postgres -d brats

-- Проверка количества chunks в KB
SELECT COUNT(*) FROM knowledge_base;

-- Проверка категорий
SELECT metadata->>'category' as category, COUNT(*) 
FROM knowledge_base 
GROUP BY metadata->>'category';

-- Проверка активных chunks
SELECT COUNT(*) FROM knowledge_base WHERE is_active = TRUE;

-- Примеры chunks
SELECT id, LEFT(content, 100) as content_preview, metadata->>'category' as category
FROM knowledge_base 
LIMIT 5;
```

## Следующие этапы

1. ✅ База данных создана
2. ✅ Таблицы созданы
3. ⏳ Настройка KB Service
4. ⏳ Импорт данных в KB
5. ⏳ Тестирование поиска
6. ⏳ Интеграция с n8n
7. ⏳ Подключение к агенту продаж

## Полезные команды

```bash
# Перезапуск KB Service
cd /projects/brats/kb-service
./start.sh

# Просмотр логов
tail -f logs/kb-service.log  # если настроено логирование в файл

# Проверка подключения к БД
psql -U postgres -d brats -c "SELECT version();"

# Проверка pgvector
psql -U postgres -d brats -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

## Примечания

- Все таблицы созданы с `IF NOT EXISTS` - можно запускать миграции повторно
- Индексы созданы с `IF NOT EXISTS`
- IVFFlat индекс требует минимум 1000 векторов для эффективной работы
- Для небольших объёмов можно временно использовать обычный индекс

## Проблемы и решения

### Ошибка подключения к БД
- Проверьте `DATABASE_URL` в `kb-service/config.env`
- Убедитесь, что PostgreSQL запущен
- Проверьте права доступа пользователя

### Ошибка генерации embeddings
- Проверьте `OPENAI_API_KEY` в `config.env`
- Или настройте HuggingFace модель
- Убедитесь, что есть доступ к интернету (для OpenAI) или модель загружена (для HF)

### Ошибка pgvector
- Убедитесь, что расширение установлено: `CREATE EXTENSION vector;`
- Проверьте версию PostgreSQL (нужна 11+)

















