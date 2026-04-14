#!/bin/bash
# Запуск n8n через Docker (без docker-compose).
# Для запуска без Docker используйте: ./start_n8n_local.sh
# Или из корня репо: ./start_all_services.sh start (n8n по умолчанию локальный).

set -e

echo "=== Запуск n8n через Docker ==="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

# Создание директории для данных
N8N_DATA_DIR="$HOME/.n8n"
mkdir -p "$N8N_DATA_DIR"
echo "✅ Директория данных: $N8N_DATA_DIR"

# Остановка и удаление старого контейнера, если существует
if docker ps -a | grep -q n8n-brats; then
    echo "🛑 Остановка и удаление старого контейнера n8n-brats..."
    docker stop n8n-brats 2>/dev/null || true
    docker rm n8n-brats 2>/dev/null || true
fi

# Загрузка переменных из config.env (если существует)
if [ -f "config.env" ]; then
    echo "📋 Загрузка настроек из config.env..."
    set -a
    source config.env
    set +a
elif [ -f "../config.env" ]; then
    echo "📋 Загрузка настроек из ../config.env..."
    set -a
    source ../config.env
    set +a
fi

# Доступ workflow к сервисам на хосте (KB :8001, sales-agent :8003)
N8N_EXTRA_HOSTS="${N8N_EXTRA_HOSTS:-host.docker.internal:host-gateway}"
ADD_HOST_OPT="--add-host=${N8N_EXTRA_HOSTS}"

# Запуск n8n
echo "🚀 Запуск n8n (extra_hosts: $N8N_EXTRA_HOSTS)..."
docker run -d \
  --name n8n-brats \
  --restart unless-stopped \
  $ADD_HOST_OPT \
  -p ${N8N_PORT:-5678}:5678 \
  -e N8N_BASIC_AUTH_ACTIVE=${N8N_BASIC_AUTH_ACTIVE:-false} \
  -e N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER:-} \
  -e N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD:-} \
  -e N8N_HOST=${N8N_HOST:-0.0.0.0} \
  -e N8N_PORT=5678 \
  -e N8N_PROTOCOL=${N8N_PROTOCOL:-http} \
  -e WEBHOOK_URL=${N8N_WEBHOOK_URL:-http://localhost:5678/} \
  -e GENERIC_TIMEZONE=Europe/Moscow \
  -e N8N_USER_MANAGEMENT_DISABLED=false \
  -e N8N_USER_FIRST_NAME=${N8N_USER_FIRST_NAME:-Admin} \
  -e N8N_USER_LAST_NAME=${N8N_USER_LAST_NAME:-User} \
  -e N8N_USER_EMAIL=${N8N_USER_EMAIL:-admin@example.com} \
  -e N8N_USER_PASSWORD=${N8N_USER_PASSWORD:-changeme} \
  -e N8N_LICENSE_KEY=${N8N_LICENSE_KEY:-} \
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e AMOCRM_SUBDOMAIN=${AMOCRM_SUBDOMAIN:-} \
  -e AMOCRM_ACCESS_TOKEN=${AMOCRM_ACCESS_TOKEN:-} \
  -v "$N8N_DATA_DIR:/home/node/.n8n" \
  -v "$(pwd)/workflows:/home/node/.n8n/workflows" \
  n8nio/n8n:latest

echo ""
echo "✅ n8n запущен!"
echo ""
echo "Доступ: http://localhost:5678"
if [ "${N8N_BASIC_AUTH_ACTIVE:-false}" = "true" ]; then
    echo "🔐 Basic Auth включен"
    echo "   Username: ${N8N_BASIC_AUTH_USER:-не указан}"
    echo "   Password: ${N8N_BASIC_AUTH_PASSWORD:+***скрыт***}"
else
    echo "⚠️  Basic Auth отключен - доступ без пароля"
    echo "При первом входе создайте учетную запись администратора"
    echo "   Email: ${N8N_USER_EMAIL:-admin@example.com}"
    echo "   Password: ${N8N_USER_PASSWORD:-changeme}"
fi
echo ""
echo "Для остановки: docker stop n8n-brats"
echo "Для просмотра логов: docker logs -f n8n-brats"

