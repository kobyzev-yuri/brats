#!/bin/bash
# Скрипт установки и запуска n8n

set -e

echo "=== Установка и настройка n8n ==="

# Проверка наличия Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js не установлен"
    echo "Установите Node.js:"
    echo "  - Ubuntu/Debian: sudo apt-get install nodejs npm"
    echo "  - Или используйте Docker вариант (см. docker-compose.yml)"
    exit 1
fi

# Проверка версии Node.js (n8n требует >=20.19 <=24.x)
NODE_MAJOR=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
NODE_MINOR=$(node -v | cut -d'v' -f2 | cut -d'.' -f2)
if [ "$NODE_MAJOR" -lt 20 ] || { [ "$NODE_MAJOR" -eq 20 ] && [ "$NODE_MINOR" -lt 19 ]; }; then
    echo "❌ n8n требует Node.js >=20.19 (текущая: $(node -v))"
    echo "   Обновление (NodeSource): curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
    exit 1
fi
if [ "$NODE_MAJOR" -gt 24 ]; then
    echo "❌ n8n поддерживает Node.js <=24.x (текущая: $(node -v))"
    exit 1
fi

echo "✅ Node.js версия: $(node -v)"

# Установка n8n глобально
echo "📦 Установка n8n..."
npm install -g n8n

# Создание директории для данных n8n
N8N_DATA_DIR="$HOME/.n8n"
mkdir -p "$N8N_DATA_DIR"
echo "✅ Директория данных n8n: $N8N_DATA_DIR"

# Создание конфигурационного файла
cat > "$N8N_DATA_DIR/config" <<EOF
# Конфигурация n8n для проекта brats
N8N_PORT=5678
N8N_HOST=0.0.0.0
N8N_PROTOCOL=http
WEBHOOK_URL=http://localhost:5678/
EOF

echo ""
echo "✅ n8n установлен успешно!"
echo ""
echo "Для запуска n8n:"
echo "  Из корня репо (все сервисы, n8n локально):  ./start_all_services.sh start"
echo "  Только n8n локально:                        cd n8n && ./start_n8n_local.sh"
echo "  Или глобально:                              n8n start"
echo "  Docker:                                     cd n8n && ./start_n8n.sh"
echo ""
echo "При локальном n8n импортируйте workflow: n8n/workflows/sales-agent-kb-integration-localhost.json"
echo "После запуска: http://localhost:5678"
















