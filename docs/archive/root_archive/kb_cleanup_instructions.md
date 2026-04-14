# Инструкции: Очистка дубликатов из PostgreSQL KB

## Проблема

В KB есть 3 практически идентичных блока (ID: 45, 46, 47) типа `product_info`, полученных из 3 разных вкладок из-за неправильной обработки.

## Решение

Два варианта:
1. **Пометить как неактивные** (рекомендуется) - блоки остаются в БД, но не используются
2. **Удалить из PostgreSQL** - полное удаление (необратимо, нужен бэкап)

## Вариант 1: Пометить как неактивные (рекомендуется)

### Преимущества:
- ✅ Блоки сохраняются для истории
- ✅ Можно восстановить при необходимости
- ✅ Безопасно и обратимо

### SQL запрос:

```sql
-- Убедиться, что колонка is_active существует
ALTER TABLE kb_blocks 
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Пометить блоки как неактивные
UPDATE kb_blocks 
SET is_active = FALSE,
    updated_at = NOW()
WHERE id IN (45, 46, 47);

-- Проверка результата
SELECT id, block_id, block_type, tab_name, is_active, created_at
FROM kb_blocks
WHERE id IN (45, 46, 47);
```

### Использование Python:

```python
from kb_postgresql_management import KBPostgreSQLManager

manager = KBPostgreSQLManager("postgresql://user:password@localhost:5432/kb_db")
manager.connect()

# Пометить как неактивные
count = manager.mark_as_inactive([45, 46, 47])
print(f"Обновлено блоков: {count}")

manager.close()
```

### Обновление кода для фильтрации:

В коде, который использует KB, добавь фильтр:

```python
# При запросе к KB
results = kb.search(query)

# Фильтровать неактивные блоки
results = [r for r in results if r.get('is_active', True)]
```

Или в SQL запросе:

```sql
SELECT * FROM kb_blocks
WHERE is_active = TRUE
  AND block_type = 'product_info'
  -- остальные условия
```

## Вариант 2: Удалить из PostgreSQL

### ⚠️ ВНИМАНИЕ: Удаление необратимо!

### Шаг 1: Создать бэкап

```sql
-- Создать таблицу бэкапа
CREATE TABLE IF NOT EXISTS kb_blocks_backup AS
SELECT * FROM kb_blocks WHERE FALSE;

-- Сохранить блоки в бэкап
INSERT INTO kb_blocks_backup
SELECT * FROM kb_blocks WHERE id IN (45, 46, 47);
```

### Шаг 2: Удалить блоки

```sql
DELETE FROM kb_blocks
WHERE id IN (45, 46, 47);
```

### Использование Python:

```python
from kb_postgresql_management import KBPostgreSQLManager

manager = KBPostgreSQLManager("postgresql://user:password@localhost:5432/kb_db")
manager.connect()

# Удалить с созданием бэкапа
count = manager.delete_blocks([45, 46, 47], create_backup=True)
print(f"Удалено блоков: {count}")

manager.close()
```

### Восстановление из бэкапа (если нужно):

```sql
INSERT INTO kb_blocks
SELECT * FROM kb_blocks_backup
WHERE id IN (45, 46, 47)
ON CONFLICT (block_id) DO NOTHING;
```

Или через Python:

```python
manager.restore_from_backup([45, 46, 47])
```

## Поиск дубликатов

### Найти все дубликаты:

```sql
SELECT block_type, 
       tab_name,
       content_hash,
       COUNT(*) as count,
       ARRAY_AGG(id ORDER BY created_at) as ids
FROM kb_blocks
WHERE is_active = TRUE
GROUP BY block_type, tab_name, content_hash
HAVING COUNT(*) > 1
ORDER BY count DESC;
```

### Найти дубликаты типа product_info:

```python
duplicates = manager.find_duplicates(block_type='product_info')
for dup in duplicates:
    print(f"Найдено {dup['count']} дубликатов: IDs {dup['ids']}")
```

## Автоматическая очистка дубликатов

### Оставить только самый старый блок, остальные пометить как неактивные:

```sql
WITH duplicates AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY block_type, content_hash 
               ORDER BY created_at ASC
           ) as rn
    FROM kb_blocks
    WHERE block_type = 'product_info'
      AND is_active = TRUE
)
UPDATE kb_blocks kb
SET is_active = FALSE,
    updated_at = NOW()
FROM duplicates d
WHERE kb.id = d.id
  AND d.rn > 1;
```

## Проверка результата

### Статистика по активным/неактивным блокам:

```sql
SELECT 
    block_type,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active_count,
    COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_count,
    COUNT(*) as total_count
FROM kb_blocks
GROUP BY block_type
ORDER BY total_count DESC;
```

### Информация о конкретных блоках:

```python
blocks_info = manager.get_block_info([45, 46, 47])
for block in blocks_info:
    print(f"ID: {block['id']}, Active: {block['is_active']}")
```

## Рекомендации

1. **Используй вариант 1 (пометка как неактивные)** - безопаснее
2. **Всегда создавай бэкап** перед удалением
3. **Проверяй результат** после операций
4. **Обнови код** для фильтрации неактивных блоков
5. **Настрой автоматическую проверку** на дубликаты при записи

## Обновление кода приложения

После пометки блоков как неактивных, обнови код:

```python
# В функции поиска по KB
def search_kb(query):
    results = db.query("""
        SELECT * FROM kb_blocks
        WHERE is_active = TRUE
          AND content ILIKE %s
    """, (f"%{query}%",))
    return results
```

Или используй ORM:

```python
results = KBBlock.query.filter_by(is_active=True).all()
```

## Резюме

**Рекомендуемый подход:**
1. ✅ Пометить блоки 45, 46, 47 как неактивные
2. ✅ Обновить код для фильтрации `is_active = TRUE`
3. ✅ Настроить автоматическую проверку на дубликаты при записи

**Если нужно полное удаление:**
1. ⚠️ Создать бэкап
2. ⚠️ Удалить блоки
3. ⚠️ Проверить результат



