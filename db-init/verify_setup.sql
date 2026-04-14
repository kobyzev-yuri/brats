-- Скрипт для проверки структуры базы данных brats

-- Проверка расширения pgvector
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') 
        THEN '✅ pgvector установлен'
        ELSE '❌ pgvector НЕ установлен'
    END as pgvector_status;

-- Список всех таблиц
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;

-- Проверка структуры knowledge_base
SELECT 
    column_name,
    data_type,
    character_maximum_length
FROM information_schema.columns
WHERE table_name = 'knowledge_base'
ORDER BY ordinal_position;

-- Проверка индексов на knowledge_base
SELECT 
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'knowledge_base';

-- Проверка структуры products
SELECT 
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name = 'products'
ORDER BY ordinal_position
LIMIT 10;

-- Статистика по таблицам
SELECT 
    'knowledge_base' as table_name,
    COUNT(*) as row_count
FROM knowledge_base
UNION ALL
SELECT 
    'products',
    COUNT(*)
FROM products
UNION ALL
SELECT 
    'conversations',
    COUNT(*)
FROM conversations
UNION ALL
SELECT 
    'messages',
    COUNT(*)
FROM messages
UNION ALL
SELECT 
    'analytics_events',
    COUNT(*)
FROM analytics_events
UNION ALL
SELECT 
    'proposals',
    COUNT(*)
FROM proposals
UNION ALL
SELECT 
    'viewing_slots',
    COUNT(*)
FROM viewing_slots
UNION ALL
SELECT 
    'document_templates',
    COUNT(*)
FROM document_templates;
