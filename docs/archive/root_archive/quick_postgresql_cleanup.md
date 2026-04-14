# Быстрая инструкция: Очистка дубликатов из PostgreSQL

## Вариант 1: Пометить как неактивные (рекомендуется)

```sql
-- Добавить колонку если её нет
ALTER TABLE kb_blocks 
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Пометить блоки как неактивные
UPDATE kb_blocks 
SET is_active = FALSE,
    updated_at = NOW()
WHERE id IN (45, 46, 47);
```

## Вариант 2: Удалить из PostgreSQL

```sql
-- 1. Бэкап
CREATE TABLE IF NOT EXISTS kb_blocks_backup AS
SELECT * FROM kb_blocks WHERE FALSE;

INSERT INTO kb_blocks_backup
SELECT * FROM kb_blocks WHERE id IN (45, 46, 47);

-- 2. Удаление
DELETE FROM kb_blocks
WHERE id IN (45, 46, 47);
```

## Python утилита

```python
from kb_postgresql_management import KBPostgreSQLManager

manager = KBPostgreSQLManager("postgresql://user:pass@localhost:5432/kb_db")

# Вариант 1: Пометить как неактивные
manager.mark_as_inactive([45, 46, 47])

# Вариант 2: Удалить (с бэкапом)
manager.delete_blocks([45, 46, 47], create_backup=True)
```

## Обновить код для фильтрации

```python
# В запросах к KB добавляй фильтр
WHERE is_active = TRUE
```

## Проверка

```sql
SELECT id, block_type, is_active 
FROM kb_blocks 
WHERE id IN (45, 46, 47);
```



