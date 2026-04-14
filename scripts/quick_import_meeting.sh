#!/bin/bash
# Быстрый импорт данных из "Саммари встречи.odt" в KB

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Импорт данных из 'Саммари встречи.odt' в KB ===${NC}"

# Отключаем системные proxy-переменные, чтобы curl не пытался ходить через SOCKS-прокси,
# который может быть настроен в окружении и не поддерживаться.
for var in HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy; do
  if [ -n "${!var}" ]; then
    echo -e "${YELLOW}⚙️  Игнорируем proxy-переменную $var для curl${NC}"
    unset $var
  fi
done

# Проверка, что KB Service запущен
API_URL="${KB_API_URL:-http://localhost:8001}"
if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}❌ KB Service не доступен по адресу $API_URL${NC}"
    echo "Запустите KB Service: cd kb-service && ./start.sh"
    exit 1
fi

echo -e "${GREEN}✅ KB Service доступен${NC}"

# Импорт через Python скрипт
cd "$(dirname "$0")/.."

if [ ! -f "scripts/import_meeting_summary.py" ]; then
    echo -e "${RED}❌ Скрипт import_meeting_summary.py не найден${NC}"
    exit 1
fi

echo -e "${YELLOW}Запуск импорта...${NC}"
python3 scripts/import_meeting_summary.py \
    --file "docs/Саммари встречи.odt" \
    --api-url "$API_URL"

echo -e "\n${GREEN}=== Импорт завершён ===${NC}"
echo -e "${YELLOW}Проверьте результаты:${NC}"
echo "  curl -X POST $API_URL/api/kb/search -H 'Content-Type: application/json' -d '{\"query\": \"тест\", \"limit\": 3}'"

