#!/bin/bash
# Проверка базы данных brats: существование, ключевые таблицы, при необходимости — подсказка по инициализации.
# Использование: из корня репо ./db-init/check_brats_db.sh
# Конфиг: config.env в корне репо (DATABASE_URL; база для проверки подставляется brats).

set -e

BRATS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$BRATS_ROOT/config.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Не найден $CONFIG_FILE. Задайте DATABASE_URL в config.env в корне проекта."
    exit 1
fi
set -a
source "$CONFIG_FILE"
set +a

if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL не задан в config.env."
    exit 1
fi

# postgresql://user:pass@host:port/dbname или .../dbname?param -> .../brats или .../brats?param
if [[ "$DATABASE_URL" =~ ^(.*/)([^/?]+)(\?.*)?$ ]]; then
    BRATS_URL="${BASH_REMATCH[1]}brats${BASH_REMATCH[3]}"
else
    BRATS_URL="${DATABASE_URL%/}/brats"
fi

echo "=== Проверка базы brats ==="
echo "Подключение: ${BRATS_URL%%@*}@***/brats"
echo ""

if ! psql "$BRATS_URL" -c "\conninfo" >/dev/null 2>&1; then
    echo "База brats недоступна (нет соединения или база не создана)."
    echo "Инициализация: из корня репо выполните: ./db-init/init_all.sh"
    exit 1
fi

echo "1. Подключение к brats: OK"
echo ""

# Список таблиц
echo "2. Таблицы в public:"
psql "$BRATS_URL" -tAc "
SELECT string_agg(tablename, ', ' ORDER BY tablename)
FROM pg_tables
WHERE schemaname = 'public';
" 2>/dev/null || echo "  (не удалось получить список)"
echo ""

# Проверка ключевых таблиц
echo "3. Ключевые объекты:"
for table in knowledge_base conversations messages lk_users lk_sessions viewing_slots proposals document_templates products analytics_events; do
    EXISTS=$(psql "$BRATS_URL" -tAc "SELECT to_regclass('public.$table') IS NOT NULL" 2>/dev/null || echo "f")
    if [ "$EXISTS" = "t" ]; then
        COUNT=$(psql "$BRATS_URL" -tAc "SELECT COUNT(*) FROM $table" 2>/dev/null || echo "?")
        echo "   ✅ $table (записей: $COUNT)"
    else
        echo "   ❌ $table — отсутствует"
    fi
done

echo ""
echo "4. Расширение pgvector:"
PV=$(psql "$BRATS_URL" -tAc "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')" 2>/dev/null || echo "f")
[ "$PV" = "t" ] && echo "   ✅ vector установлен" || echo "   ❌ vector не установлен"

echo ""
echo "Если каких-то таблиц нет — выполните инициализацию: ./db-init/init_all.sh"
