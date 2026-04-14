#!/usr/bin/env bash
#
# Запуск n8n локально (без Docker). Тогда localhost:8001 и localhost:8003
# в workflow указывают на сервисы на том же хосте — не нужен host.docker.internal.
#
# Требуется: Node.js (npx). Использование:
#   ./start_n8n_local.sh          # запуск в текущем терминале (Ctrl+C — стоп)
#   ./start_n8n_local.sh &        # в фоне
#
# После первого запуска откройте http://localhost:5678 и импортируйте
# workflow: workflows/sales-agent-kb-integration-localhost.json
#

set -e

N8N_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$N8N_DIR"

# Лицензия и прочие настройки из config.env
if [ -f "config.env" ]; then
    set -a; source config.env; set +a
elif [ -f "../config.env" ]; then
    set -a; source ../config.env; set +a
fi
# Для LLM в workflow: если OPENAI_API_KEY не задан, берём PROXYAPI_KEY
[ -z "${OPENAI_API_KEY:-}" ] && [ -n "${PROXYAPI_KEY:-}" ] && export OPENAI_API_KEY="$PROXYAPI_KEY"

# По умолчанию ~/.n8n — те же данные, что у Docker, без повторной регистрации
export N8N_USER_FOLDER="${N8N_USER_FOLDER:-$HOME/.n8n}"
export N8N_PORT="${N8N_PORT:-5678}"
export N8N_HOST="${N8N_HOST:-0.0.0.0}"
export N8N_LICENSE_KEY="${N8N_LICENSE_KEY:-}"
# Куки по HTTP (localhost без HTTPS)
export N8N_SECURE_COOKIE="${N8N_SECURE_COOKIE:-false}"
# Разрешить узлам читать переменные окружения (для LLM: OPENAI_API_KEY, OPENAI_BASE_URL в workflow)
export N8N_BLOCK_ENV_ACCESS_IN_NODE="${N8N_BLOCK_ENV_ACCESS_IN_NODE:-false}"
# Сохранять успешные выполнения в списке Executions (по умолчанию all; none — не сохранять)
export EXECUTIONS_DATA_SAVE_ON_SUCCESS="${EXECUTIONS_DATA_SAVE_ON_SUCCESS:-all}"

mkdir -p "$N8N_USER_FOLDER"
echo "n8n (локально): http://localhost:${N8N_PORT}"
echo "Данные: $N8N_USER_FOLDER"
echo "Workflow с localhost: workflows/sales-agent-kb-integration-localhost.json"
echo ""

exec npx n8n
