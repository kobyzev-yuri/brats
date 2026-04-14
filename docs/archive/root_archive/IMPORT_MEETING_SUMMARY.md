# Импорт данных из "Саммари встречи.odt" в KB

## ✅ Готово к использованию!

Скрипт успешно извлёк текст из ODT файла и определил **44 chunks** с автоматической категоризацией.

## Быстрый импорт

### Вариант 1: Автоматический импорт (рекомендуется)

```bash
cd /projects/brats

# Убедитесь, что KB Service запущен
cd kb-service && ./start.sh &
# Подождите несколько секунд

# Импорт данных
cd /projects/brats
./scripts/quick_import_meeting.sh
```

### Вариант 2: Ручной импорт через Python

```bash
cd /projects/brats

# Dry-run (только извлечение, без импорта)
python3 scripts/import_meeting_summary.py \
  --file "docs/Саммари встречи.odt" \
  --dry-run \
  --output "docs/meeting_summary_extracted.txt"

# Полный импорт
python3 scripts/import_meeting_summary.py \
  --file "docs/Саммари встречи.odt" \
  --api-url "http://localhost:8001"
```

### Вариант 3: Импорт через API (если текст уже извлечён)

```bash
curl -X POST http://localhost:8001/api/kb/import \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "docs/meeting_summary_extracted.txt",
    "category": "sales_script",
    "target_audience": "both",
    "chunk_size": 3000,
    "chunk_overlap": 300,
    "source": "Саммари встречи.odt"
  }'
```

## Что было извлечено

Скрипт автоматически определил следующие категории:

- **sales_script** - скрипты продаж и диалоги
- **product_info** - информация о продукте/посёлке
- **objection_handling** - обработка возражений
- **target_audience** - целевая аудитория
- **tone_of_voice** - тон общения
- **pricing** - ценообразование
- **contacts** - контакты и интеграции

Всего найдено: **44 chunks**

## Проверка импортированных данных

### Через SQL

```sql
-- Подключение к БД
psql -U postgres -d brats

-- Проверка импортированных chunks
SELECT 
    id,
    LEFT(content, 150) as content_preview,
    metadata->>'category' as category,
    metadata->>'source' as source
FROM knowledge_base
WHERE metadata->>'source' = 'Саммари встречи.odt'
ORDER BY metadata->>'category', id
LIMIT 20;

-- Статистика по категориям
SELECT 
    metadata->>'category' as category,
    COUNT(*) as count
FROM knowledge_base
WHERE metadata->>'source' = 'Саммари встречи.odt'
GROUP BY metadata->>'category'
ORDER BY count DESC;
```

### Через API

```bash
# Поиск по категории
curl -X POST http://localhost:8001/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "как обработать возражение",
    "category": "objection_handling",
    "limit": 5
  }'

# Статистика
curl http://localhost:8001/api/kb/stats
```

## Тестирование поиска

После импорта протестируйте релевантность поиска:

```bash
# Тест 1: Поиск информации о продукте
curl -X POST http://localhost:8001/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "коттеджный посёлок характеристики",
    "limit": 3
  }'

# Тест 2: Поиск скриптов продаж
curl -X POST http://localhost:8001/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "как вести диалог с клиентом",
    "category": "sales_script",
    "limit": 3
  }'

# Тест 3: Поиск обработки возражений
curl -X POST http://localhost:8001/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "клиент сомневается в цене",
    "category": "objection_handling",
    "limit": 3
  }'
```

## Ручная корректировка категорий

Если автоматическая категоризация работает не идеально, можно:

1. Просмотреть извлечённый текст:
   ```bash
   cat docs/meeting_summary_extracted.txt
   ```

2. Отредактировать категории через API:
   ```bash
   # Обновить категорию конкретного chunk
   curl -X PUT http://localhost:8001/api/kb/{chunk_id} \
     -H "Content-Type: application/json" \
     -d '{
       "category": "correct_category"
     }'
   ```

3. Или удалить и переимпортировать с правильными категориями

## Следующие шаги

1. ✅ Данные извлечены из ODT
2. ✅ Скрипт импорта готов
3. ⏳ Запустить KB Service
4. ⏳ Импортировать данные
5. ⏳ Протестировать поиск
6. ⏳ Интегрировать с n8n и агентом продаж

## Примечания

- Скрипт использует встроенную обработку ZIP+XML (не требует дополнительных библиотек)
- Автоматическая категоризация основана на ключевых словах
- Можно улучшить категоризацию с помощью LLM или ручной разметки
- Все импортированные chunks помечаются `source="Саммари встречи.odt"`

















