#!/bin/bash
# Скрипт для проверки данных в KB
# Использует config.env в корне проекта

set -e

BRATS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$BRATS_ROOT/config.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Ошибка: не найден $CONFIG_FILE"
    exit 1
fi

# Извлекаем DATABASE_URL
DB_URL=$(grep "^DATABASE_URL=" "$CONFIG_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")

# Парсим параметры
DB_USER=$(echo "$DB_URL" | sed -n 's|postgresql://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DB_URL" | sed -n 's|postgresql://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|postgresql://[^@]*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|postgresql://[^@]*@[^:]*:\([^/]*\)/.*|\1|p')
DB_NAME="brats"

export PGPASSWORD="$DB_PASS"

echo "=== Проверка данных в KB ==="
echo ""

echo "1. Импортированные chunks из 'Саммари встречи.odt':"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    id,
    LEFT(content, 100) AS preview,
    metadata->>'category' AS category,
    metadata->>'source' AS source
FROM knowledge_base 
WHERE metadata->>'source' = 'Саммари встречи.odt'
ORDER BY id
LIMIT 10;
"

echo ""
echo "2. Статистика по категориям:"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    metadata->>'category' AS category,
    COUNT(*) AS count
FROM knowledge_base 
WHERE metadata->>'source' = 'Саммари встречи.odt'
GROUP BY metadata->>'category'
ORDER BY count DESC;
"

echo ""
echo "3. Общая статистика KB:"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    COUNT(*) AS total_chunks,
    COUNT(CASE WHEN is_active = TRUE THEN 1 END) AS active_chunks,
    COUNT(DISTINCT metadata->>'category') AS categories_count
FROM knowledge_base;
"

















