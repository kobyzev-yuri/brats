-- SQL скрипты для управления блоками в PostgreSQL KB
-- Варианты: пометка как неактивные или удаление

-- ============================================
-- ВАРИАНТ 1: Пометить блоки как неактивные
-- ============================================

-- Проверка структуры таблицы (адаптируй под свою схему)
-- Предполагаемая структура:
-- CREATE TABLE kb_blocks (
--     id SERIAL PRIMARY KEY,
--     block_id VARCHAR(255) UNIQUE,
--     block_type VARCHAR(50),
--     content TEXT,
--     tab_name VARCHAR(50),
--     is_active BOOLEAN DEFAULT TRUE,
--     created_at TIMESTAMP DEFAULT NOW(),
--     updated_at TIMESTAMP DEFAULT NOW()
-- );

-- Если колонки is_active нет, добавить её:
ALTER TABLE kb_blocks 
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Пометить конкретные блоки как неактивные по ID
UPDATE kb_blocks 
SET is_active = FALSE,
    updated_at = NOW()
WHERE id IN (45, 46, 47);

-- Пометить как неактивные по block_id (если знаешь их идентификаторы)
-- UPDATE kb_blocks 
-- SET is_active = FALSE,
--     updated_at = NOW()
-- WHERE block_id IN (
--     'description_STANDARD_xxx',
--     'description_BLACK_BOX_yyy',
--     'description_WHITE_BOX_zzz'
-- );

-- Пометить как неактивные по типу и вкладке (если это дубликаты)
UPDATE kb_blocks 
SET is_active = FALSE,
    updated_at = NOW()
WHERE block_type = 'product_info'
  AND tab_name IN ('STANDARD', 'BLACK BOX', 'WHITE BOX')
  AND id IN (45, 46, 47);

-- Проверка результата
SELECT id, block_id, block_type, tab_name, is_active, created_at
FROM kb_blocks
WHERE id IN (45, 46, 47);

-- ============================================
-- ВАРИАНТ 2: Удалить блоки из PostgreSQL
-- ============================================

-- ВНИМАНИЕ: Удаление необратимо! Сначала сделай бэкап!

-- Создать бэкап перед удалением
CREATE TABLE IF NOT EXISTS kb_blocks_backup AS
SELECT * FROM kb_blocks WHERE id IN (45, 46, 47);

-- Удалить конкретные блоки по ID
DELETE FROM kb_blocks
WHERE id IN (45, 46, 47);

-- Удалить по block_id (если знаешь их идентификаторы)
-- DELETE FROM kb_blocks
-- WHERE block_id IN (
--     'description_STANDARD_xxx',
--     'description_BLACK_BOX_yyy',
--     'description_WHITE_BOX_zzz'
-- );

-- Удалить дубликаты (оставить только один, удалить остальные)
-- Например, оставить самый старый блок, удалить остальные
DELETE FROM kb_blocks
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY block_type, tab_name, content_hash 
                   ORDER BY created_at ASC
               ) as rn
        FROM kb_blocks
        WHERE block_type = 'product_info'
          AND tab_name IN ('STANDARD', 'BLACK BOX', 'WHITE BOX')
    ) t
    WHERE rn > 1  -- Оставить только первый (самый старый)
);

-- ============================================
-- ВАРИАНТ 3: Найти и пометить дубликаты автоматически
-- ============================================

-- Найти дубликаты по содержимому
WITH duplicates AS (
    SELECT id,
           block_type,
           tab_name,
           content_hash,
           ROW_NUMBER() OVER (
               PARTITION BY block_type, content_hash 
               ORDER BY created_at ASC
           ) as rn
    FROM kb_blocks
    WHERE block_type = 'product_info'
)
-- Пометить все кроме первого как неактивные
UPDATE kb_blocks kb
SET is_active = FALSE,
    updated_at = NOW()
FROM duplicates d
WHERE kb.id = d.id
  AND d.rn > 1;

-- ============================================
-- ВАРИАНТ 4: Безопасное удаление с проверкой
-- ============================================

-- Функция для безопасного удаления блоков
CREATE OR REPLACE FUNCTION safe_delete_blocks(block_ids INTEGER[])
RETURNS TABLE(deleted_id INTEGER, deleted_block_id VARCHAR) AS $$
DECLARE
    block_id INTEGER;
BEGIN
    -- Создать бэкап
    CREATE TABLE IF NOT EXISTS kb_blocks_backup AS
    SELECT * FROM kb_blocks WHERE FALSE;  -- Пустая таблица с той же структурой
    
    INSERT INTO kb_blocks_backup
    SELECT * FROM kb_blocks WHERE id = ANY(block_ids);
    
    -- Удалить блоки
    RETURN QUERY
    DELETE FROM kb_blocks
    WHERE id = ANY(block_ids)
    RETURNING id, kb_blocks.block_id;
END;
$$ LANGUAGE plpgsql;

-- Использование функции
SELECT * FROM safe_delete_blocks(ARRAY[45, 46, 47]);

-- ============================================
-- ВАРИАНТ 5: Восстановление из бэкапа
-- ============================================

-- Восстановить блоки из бэкапа
INSERT INTO kb_blocks
SELECT * FROM kb_blocks_backup
WHERE id IN (45, 46, 47)
ON CONFLICT (block_id) DO NOTHING;

-- ============================================
-- ПОЛЕЗНЫЕ ЗАПРОСЫ ДЛЯ АНАЛИЗА
-- ============================================

-- Найти все дубликаты
SELECT block_type, 
       tab_name,
       content_hash,
       COUNT(*) as count,
       ARRAY_AGG(id ORDER BY created_at) as ids,
       ARRAY_AGG(created_at ORDER BY created_at) as created_dates
FROM kb_blocks
WHERE is_active = TRUE
GROUP BY block_type, tab_name, content_hash
HAVING COUNT(*) > 1
ORDER BY count DESC;

-- Найти блоки по типу product_info
SELECT id, block_id, block_type, tab_name, is_active, created_at
FROM kb_blocks
WHERE block_type = 'product_info'
ORDER BY created_at DESC;

-- Статистика по активным/неактивным блокам
SELECT 
    block_type,
    COUNT(*) FILTER (WHERE is_active = TRUE) as active_count,
    COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_count,
    COUNT(*) as total_count
FROM kb_blocks
GROUP BY block_type
ORDER BY total_count DESC;

-- Найти блоки с одинаковым содержимым
SELECT 
    kb1.id as id1,
    kb2.id as id2,
    kb1.block_type,
    kb1.tab_name as tab1,
    kb2.tab_name as tab2,
    kb1.created_at as created1,
    kb2.created_at as created2
FROM kb_blocks kb1
JOIN kb_blocks kb2 ON kb1.content_hash = kb2.content_hash
WHERE kb1.id < kb2.id
  AND kb1.block_type = kb2.block_type
  AND kb1.is_active = TRUE
  AND kb2.is_active = TRUE
ORDER BY kb1.created_at;



