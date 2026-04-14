#!/bin/bash
# Скрипт для инициализации базы данных brats
# Использует config.env в корне проекта

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Инициализация базы данных brats ===${NC}"

BRATS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="$BRATS_ROOT/config.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Ошибка: не найден $CONFIG_FILE${NC}"
    exit 1
fi
echo -e "${YELLOW}Конфиг: $CONFIG_FILE${NC}"

# Извлекаем DATABASE_URL из config.env
# Формат: postgresql://user:password@host:port/database
DB_URL=$(grep "^DATABASE_URL=" "$CONFIG_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")

if [ -z "$DB_URL" ]; then
    echo -e "${RED}Ошибка: DATABASE_URL не найден в $SQL4A_CONFIG${NC}"
    exit 1
fi

# Парсим DATABASE_URL
# postgresql://postgres:1234@localhost:5432/test_docstructure
DB_USER=$(echo "$DB_URL" | sed -n 's|postgresql://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DB_URL" | sed -n 's|postgresql://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|postgresql://[^@]*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|postgresql://[^@]*@[^:]*:\([^/]*\)/.*|\1|p')
DB_NAME="brats"

echo -e "${YELLOW}Параметры подключения:${NC}"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"

# Экспортируем переменные для psql
export PGPASSWORD="$DB_PASS"

# Создаём базу данных (если не существует)
echo -e "\n${GREEN}1. Создание базы данных $DB_NAME...${NC}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<EOF
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ База данных $DB_NAME создана или уже существует${NC}"
else
    echo -e "${RED}❌ Ошибка при создании базы данных${NC}"
    exit 1
fi

# Применяем миграции
echo -e "\n${GREEN}2. Применение миграций...${NC}"

MIGRATIONS_DIR="$(dirname "$0")"
cd "$MIGRATIONS_DIR"

for migration in 01_init_database.sql 02_create_knowledge_base.sql 03_create_conversations.sql 04_create_analytics_events.sql 05_create_products.sql 06_create_proposals.sql 07_viewing_slots_and_templates.sql 08_seed_samples.sql 09_add_conversation_external_id.sql 10_create_users_and_lk.sql; do
    if [ -f "$migration" ]; then
        echo -e "${YELLOW}  Применение $migration...${NC}"
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration"
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}  ✅ $migration применён${NC}"
        else
            echo -e "${RED}  ❌ Ошибка при применении $migration${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}  ⚠️  Файл $migration не найден, пропускаем${NC}"
    fi
done

echo -e "\n${GREEN}=== Инициализация завершена успешно ===${NC}"
echo -e "${YELLOW}База данных: $DB_NAME${NC}"
echo -e "${YELLOW}Подключение: postgresql://$DB_USER:***@$DB_HOST:$DB_PORT/$DB_NAME${NC}"

















