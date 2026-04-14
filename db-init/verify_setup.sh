#!/bin/bash
# Скрипт для проверки структуры базы данных brats
# Использует config.env в корне проекта

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Проверка структуры базы данных brats ===${NC}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BRATS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$BRATS_ROOT/config.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Ошибка: не найден $CONFIG_FILE${NC}"
    exit 1
fi

# Извлекаем DATABASE_URL из config.env
DB_URL=$(grep "^DATABASE_URL=" "$CONFIG_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'")

if [ -z "$DB_URL" ]; then
    echo -e "${RED}Ошибка: DATABASE_URL не найден в $CONFIG_FILE${NC}"
    exit 1
fi

# Парсим DATABASE_URL
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
echo ""

# Экспортируем переменные для psql
export PGPASSWORD="$DB_PASS"

# Проверка подключения
echo -e "${GREEN}1. Проверка подключения к базе данных...${NC}"
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Подключение успешно${NC}"
else
    echo -e "${RED}❌ Ошибка подключения к базе данных${NC}"
    echo "Проверьте:"
    echo "  - Запущен ли PostgreSQL?"
    echo "  - Правильны ли параметры в config.env?"
    echo "  - Существует ли база данных $DB_NAME?"
    exit 1
fi

# Применяем SQL скрипт проверки
echo -e "\n${GREEN}2. Проверка структуры базы данных...${NC}"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$(dirname "$0")/verify_setup.sql"

echo -e "\n${GREEN}=== Проверка завершена ===${NC}"

















