# Импорт данных из "Саммари встречи.odt" в KB

## Описание

Скрипт `import_meeting_summary.py` позволяет импортировать данные из ODT файла в базу знаний через KB Service API.

## Установка зависимостей

Для работы скрипта нужна одна из библиотек для работы с ODT:

```bash
# Вариант 1: odfpy (рекомендуется)
pip install odfpy

# Вариант 2: pandoc (если установлен системно)
# sudo apt-get install pandoc  # на Ubuntu/Debian

# Вариант 3: Используется встроенная обработка ZIP+XML (без дополнительных зависимостей)
```

## Использование

### Базовое использование

```bash
cd /projects/brats
python scripts/import_meeting_summary.py --file "docs/Саммари встречи.odt"
```

### Сохранение извлечённого текста

```bash
python scripts/import_meeting_summary.py \
  --file "docs/Саммари встречи.odt" \
  --output "docs/meeting_summary_extracted.txt"
```

### Dry-run (только извлечение, без импорта)

```bash
python scripts/import_meeting_summary.py \
  --file "docs/Саммари встречи.odt" \
  --dry-run \
  --output "docs/meeting_summary_extracted.txt"
```

### Указание другого API URL

```bash
python scripts/import_meeting_summary.py \
  --file "docs/Саммари встречи.odt" \
  --api-url "http://localhost:8001"
```

## Как работает скрипт

1. **Конвертация ODT в текст**
   - Пробует несколько методов: odfpy, pandoc, встроенная обработка ZIP+XML
   - Извлекает текст из документа

2. **Категоризация контента**
   - Автоматически определяет категории по ключевым словам:
     - `product_info` - информация о продукте/посёлке
     - `sales_script` - скрипты продаж
     - `objection_handling` - обработка возражений
     - `target_audience` - целевая аудитория
     - `tone_of_voice` - тон общения
     - `pricing` - ценообразование
     - `contacts` - контакты

3. **Импорт в KB**
   - Отправляет каждый chunk через KB Service API
   - Использует категорию, определённую автоматически
   - Устанавливает `source="Саммари встречи.odt"`

## Ручная категоризация

Если автоматическая категоризация работает не идеально, можно:

1. Извлечь текст вручную:
   ```bash
   python scripts/import_meeting_summary.py --dry-run --output meeting_summary.txt
   ```

2. Отредактировать файл, добавив метки категорий:
   ```
   [CATEGORY: product_info]
   Текст о продукте...

   [CATEGORY: sales_script]
   Скрипт продаж...
   ```

3. Импортировать через KB Service API напрямую или доработать скрипт

## Альтернативный способ: через LibreOffice

Если скрипт не работает, можно конвертировать ODT в TXT вручную:

1. Откройте `Саммари встречи.odt` в LibreOffice
2. Сохраните как TXT: Файл → Сохранить как → Текст (.txt)
3. Импортируйте через KB Service API:
   ```bash
   curl -X POST http://localhost:8001/api/kb/import \
     -H "Content-Type: application/json" \
     -d '{
       "file_path": "docs/meeting_summary.txt",
       "category": "sales_script",
       "target_audience": "both",
       "chunk_size": 3000,
       "chunk_overlap": 300
     }'
   ```

## Проверка импортированных данных

```sql
-- Подключение к БД
psql -U postgres -d brats

-- Проверка импортированных chunks
SELECT 
    id,
    LEFT(content, 100) as content_preview,
    metadata->>'category' as category,
    metadata->>'source' as source
FROM knowledge_base
WHERE metadata->>'source' = 'Саммари встречи.odt'
ORDER BY id;

-- Статистика по категориям
SELECT 
    metadata->>'category' as category,
    COUNT(*) as count
FROM knowledge_base
WHERE metadata->>'source' = 'Саммари встречи.odt'
GROUP BY metadata->>'category';
```

## Тестирование поиска

После импорта протестируйте поиск:

```bash
curl -X POST http://localhost:8001/api/kb/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "как обработать возражение о цене",
    "limit": 5,
    "min_similarity": 0.6
  }'
```

















