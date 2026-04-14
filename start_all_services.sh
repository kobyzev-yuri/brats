#!/usr/bin/env bash
#
# Единый скрипт управления сервисами для теста site-integration-example.html
#
# n8n по умолчанию запускается локально (npx n8n) — тогда в workflow
# используйте localhost:8001/8003. Импорт: n8n/workflows/sales-agent-kb-integration-localhost.json
# Вариант с Docker: N8N_DOCKER=1 ./start_all_services.sh start
#
# Использование:
#   ./start_all_services.sh start   — поднять все сервисы (n8n локально)
#   ./start_all_services.sh stop   — остановить все
#   ./start_all_services.sh restart — перезапуск всех
#   ./start_all_services.sh restart <сервис> — перезапуск одного сервиса (см. список ниже)
#   ./start_all_services.sh status  — статус портов и сервисов
#
# Сервисы для restart <сервис>: kb-service, kb-admin, sales-agent, amocrm-api, funnel-api, n8n, site
#
# После start: http://localhost:8000/site-integration-example.html
#

set -e

BRATS_ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDS_FILE="$BRATS_ROOT/.brats_pids"
LOGS_DIR="$BRATS_ROOT/.brats_logs"
N8N_DIR="$BRATS_ROOT/n8n"

# Порты (должны совпадать с конфигами и workflow)
PORT_KB=8001
PORT_KB_ADMIN=8501
PORT_AGENT=8003
PORT_N8N=5678
PORT_SITE=8000
PORT_AMOCRM=8010
PORT_FUNNEL=8011

command="${1:-}"

log() { echo "[brats] $*"; }
err()  { echo "[brats] ERROR: $*" >&2; }

# --- Проверка: текущий Python (py310 и т.д.) с fastapi ---
check_python() {
    if ! python -c "import fastapi" 2>/dev/null; then
        err "В текущем окружении (python) не найден fastapi."
        echo "   Активируйте окружение с зависимостями (например conda activate py310) или: pip install fastapi uvicorn"
        exit 1
    fi
}

# --- Сохранить PID в файл (ключ:pid по одному на строку) ---
save_pid() {
    local key="$1"
    local pid="$2"
    mkdir -p "$(dirname "$PIDS_FILE")"
    # Удалить старую запись с таким ключом
    if [ -f "$PIDS_FILE" ]; then
        grep -v "^${key}:" "$PIDS_FILE" > "${PIDS_FILE}.tmp" 2>/dev/null || true
        mv "${PIDS_FILE}.tmp" "$PIDS_FILE" 2>/dev/null || true
    fi
    echo "${key}:${pid}" >> "$PIDS_FILE"
}

# --- Убить процесс по PID (мягко) ---
kill_pid() {
    local pid="$1"
    [ -z "$pid" ] && return
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    fi
}

# --- Освободить порт: убить процесс, слушающий порт (если есть) ---
kill_port() {
    local port="$1"
    local pid
    if command -v ss &>/dev/null; then
        pid=$(ss -tlnp 2>/dev/null | awk -v p=":${port} " '$0 ~ p { gsub(/.*pid=/, ""); gsub(/,.*/, ""); print; exit }')
    fi
    if [ -z "$pid" ] && command -v fuser &>/dev/null; then
        pid=$(fuser "$port"/tcp 2>/dev/null | awk '{print $1}')
    fi
    if [ -n "$pid" ] && [ "$pid" -eq "$pid" ] 2>/dev/null; then
        log "Освобождаю порт $port (PID $pid)..."
        kill_pid "$pid"
        sleep 1
    fi
}

# --- Остановка по .brats_pids ---
stop_by_pids() {
    if [ ! -f "$PIDS_FILE" ]; then
        return
    fi
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        key="${line%%:*}"
        pid="${line#*:}"
        if [ -n "$pid" ] && [ "$pid" -eq "$pid" ] 2>/dev/null; then
            log "Останавливаю $key (PID $pid)..."
            kill_pid "$pid"
        fi
    done < "$PIDS_FILE"
    rm -f "$PIDS_FILE"
}

# --- Остановка n8n: контейнер Docker и/или процесс по PID (n8n_local) ---
stop_n8n() {
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^n8n-brats$'; then
        log "Останавливаю n8n (контейнер n8n-brats)..."
        docker stop n8n-brats 2>/dev/null || true
    fi
}

# --- Статус: проверка порта ---
check_port() {
    local port="$1"
    if command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep -q ":${port} " && return 0
    fi
    if command -v netstat &>/dev/null; then
        netstat -tlnp 2>/dev/null | grep -q ":${port} " && return 0
    fi
    return 1
}

# --- Статус: HTTP доступность ---
http_ok() {
    local url="$1"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 "$url" 2>/dev/null || echo "000")
    [ "$code" = "200" ] || [ "${code:0:1}" = "2" ] || [ "$code" = "000" ]
}

# ========== status ==========
cmd_status() {
    log "Статус сервисов (тест site-integration-example.html)"
    echo ""
    printf "%-12s %-8s %-10s %s\n" "Сервис" "Порт" "Порт OK" "HTTP"
    echo "------------------------------------------------------------"

    for name in "kb-service" "KB Admin" "sales-agent" "amocrm-api" "funnel-api" "n8n" "site (прокси)"; do
        case "$name" in
            kb-service)   port=$PORT_KB;  url="http://localhost:${port}/health" ;;
            KB\ Admin)    port=$PORT_KB_ADMIN; url="http://localhost:${port}/" ;;
            sales-agent) port=$PORT_AGENT; url="http://localhost:${port}/" ;;
            amocrm-api)  port=$PORT_AMOCRM; url="http://localhost:${port}/health" ;;
            funnel-api)  port=$PORT_FUNNEL; url="http://localhost:${port}/health" ;;
            n8n)          port=$PORT_N8N; url="http://localhost:${port}/healthz" ;;
            site*)        port=$PORT_SITE; url="http://localhost:${port}/" ;;
            *)            port=""; url="" ;;
        esac
        if [ -z "$port" ]; then continue; fi
        port_ok="нет"
        check_port "$port" && port_ok="да"
        http_ok="нет"
        http_ok "$url" && http_ok="да"
        printf "%-12s %-8s %-10s %s\n" "$name" "$port" "$port_ok" "$http_ok"
    done

    echo ""
    echo "Страница для теста: http://localhost:${PORT_SITE}/site-integration-example.html"
    echo "Чат идёт через n8n webhook (прокси на порту ${PORT_SITE})."
}

# ========== stop ==========
cmd_stop() {
    log "Остановка всех сервисов..."
    stop_by_pids   # в т.ч. n8n_local, kb_service, sales_agent, site_proxy
    stop_n8n       # контейнер n8n-brats, если был
    # Освободить порты на случай процесса не из .brats_pids (например старый kb-service)
    kill_port "$PORT_KB"
    kill_port "$PORT_KB_ADMIN"
    kill_port "$PORT_AGENT"
    kill_port "$PORT_AMOCRM"
    kill_port "$PORT_FUNNEL"
    kill_port "$PORT_SITE"
    log "Готово."
}

# ========== start ==========
cmd_start() {
    check_python
    mkdir -p "$LOGS_DIR"

    # Загружаем config.env один раз для всех сервисов; OPENAI_API_KEY подставляется из PROXYAPI_KEY при необходимости
    if [ -f "$BRATS_ROOT/config.env" ]; then
        set -a; source "$BRATS_ROOT/config.env"; set +a
        [ -z "${OPENAI_API_KEY:-}" ] && [ -n "${PROXYAPI_KEY:-}" ] && export OPENAI_API_KEY="$PROXYAPI_KEY"
    fi

    # 1) n8n: по умолчанию локально (npx), без Docker — тогда localhost:8001/8003 работают
    if check_port "$PORT_N8N"; then
        log "n8n уже слушает порт $PORT_N8N."
    elif [ "${N8N_DOCKER:-0}" = "1" ]; then
        log "Запуск n8n (Docker)..."
        (cd "$N8N_DIR" && ./start_n8n.sh)
        sleep 2
    else
        log "Запуск n8n локально (npx, без Docker)..."
        # Приоритет системному Node (20.x)
        export PATH="/usr/bin:/usr/local/bin:$PATH"
        NPX_CMD=$(command -v npx 2>/dev/null || true)
        if [ -z "$NPX_CMD" ]; then
            err "npx не найден. Установите Node.js/npm: sudo apt-get install nodejs npm"
            exit 1
        fi
        cd "$N8N_DIR"
        export N8N_USER_FOLDER="${N8N_USER_FOLDER:-$HOME/.n8n}"
        export N8N_HOST="${N8N_HOST:-0.0.0.0}"
        export N8N_LICENSE_KEY="${N8N_LICENSE_KEY:-}"
        export N8N_SECURE_COOKIE="${N8N_SECURE_COOKIE:-false}"
        export N8N_BLOCK_ENV_ACCESS_IN_NODE="${N8N_BLOCK_ENV_ACCESS_IN_NODE:-false}"
        export EXECUTIONS_DATA_SAVE_ON_SUCCESS="${EXECUTIONS_DATA_SAVE_ON_SUCCESS:-all}"
        mkdir -p "$N8N_USER_FOLDER"
        nohup "$NPX_CMD" n8n >> "$LOGS_DIR/n8n.log" 2>&1 &
        save_pid "n8n_local" $!
        cd "$BRATS_ROOT"
        sleep 2
    fi

    # 2) kb-service (запуск в текущей оболочке, чтобы $! был верным)
    if check_port "$PORT_KB"; then
        log "kb-service уже слушает порт $PORT_KB."
    else
        log "Запуск kb-service (порт $PORT_KB)..."
        cd "$BRATS_ROOT/kb-service"
        nohup uvicorn api.main:app --host 0.0.0.0 --port "$PORT_KB" >> "$LOGS_DIR/kb-service.log" 2>&1 &
        save_pid "kb_service" $!
        cd "$BRATS_ROOT"
        sleep 2
    fi

    # 3) sales-agent
    if check_port "$PORT_AGENT"; then
        log "sales-agent уже слушает порт $PORT_AGENT."
    else
        log "Запуск sales-agent (порт $PORT_AGENT)..."
        cd "$BRATS_ROOT/sales-agent"
        nohup python api/main.py >> "$LOGS_DIR/sales-agent.log" 2>&1 &
        save_pid "sales_agent" $!
        cd "$BRATS_ROOT"
        sleep 2
    fi

    # 4) amocrm-api (лиды из чата, тестовые лиды; токены из config.env в корне репо)
    if check_port "$PORT_AMOCRM"; then
        log "amocrm-api уже слушает порт $PORT_AMOCRM."
    else
        log "Запуск amocrm-api (порт $PORT_AMOCRM)..."
        cd "$BRATS_ROOT/amocrm-api"
        nohup uvicorn api.main:app --host 0.0.0.0 --port "$PORT_AMOCRM" >> "$LOGS_DIR/amocrm-api.log" 2>&1 &
        save_pid "amocrm_api" $!
        cd "$BRATS_ROOT"
        sleep 2
    fi

    # 5) funnel-api (календарь просмотров 9–18, КП, шаблоны договоров; PostgreSQL)
    if check_port "$PORT_FUNNEL"; then
        log "funnel-api уже слушает порт $PORT_FUNNEL."
    else
        log "Запуск funnel-api (порт $PORT_FUNNEL)..."
        cd "$BRATS_ROOT/funnel-api"
        nohup uvicorn api.main:app --host 0.0.0.0 --port "$PORT_FUNNEL" >> "$LOGS_DIR/funnel-api.log" 2>&1 &
        save_pid "funnel_api" $!
        cd "$BRATS_ROOT"
        sleep 2
    fi

    # 6) site + прокси на n8n
    if check_port "$PORT_SITE"; then
        log "Сайт/прокси уже слушает порт $PORT_SITE."
    else
        log "Запуск сайта с прокси (порт $PORT_SITE)..."
        nohup python site-integration/serve_with_proxy.py >> "$LOGS_DIR/site-proxy.log" 2>&1 &
        save_pid "site_proxy" $!
    fi

    # 7) KB Admin (веб-интерфейс управления базой знаний, Streamlit)
    if check_port "$PORT_KB_ADMIN"; then
        log "KB Admin уже слушает порт $PORT_KB_ADMIN."
    else
        log "Запуск KB Admin (порт $PORT_KB_ADMIN)..."
        cd "$BRATS_ROOT/kb-service"
        nohup streamlit run web/kb_admin_app.py --server.port "$PORT_KB_ADMIN" --server.headless true >> "$LOGS_DIR/kb-admin.log" 2>&1 &
        save_pid "kb_admin" $!
        cd "$BRATS_ROOT"
        sleep 2
    fi

    sleep 2
    echo ""
    log "Все сервисы запущены."
    echo "  Страница: http://localhost:${PORT_SITE}/site-integration-example.html"
    echo "  KB Admin: http://localhost:${PORT_KB_ADMIN}"
    echo "  n8n:      http://localhost:${PORT_N8N}"
    if [ "${N8N_DOCKER:-0}" != "1" ] && ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^n8n-brats$'; then
        echo "  n8n локально: импортируйте workflow n8n/workflows/sales-agent-kb-integration-localhost.json (URL localhost:8001/8003)"
    fi
    echo "  Логи:     $LOGS_DIR/"
    echo ""
    cmd_status
    if ! check_port "$PORT_KB" || ! check_port "$PORT_AGENT"; then
        echo ""
        err "kb-service или sales-agent не поднялись. Проверьте логи: tail -20 $LOGS_DIR/kb-service.log $LOGS_DIR/sales-agent.log"
    fi
}

# --- Остановить один сервис по ключу в PIDS_FILE и/или по порту ---
stop_one() {
    local key="$1"
    local port="$2"
    if [ -f "$PIDS_FILE" ]; then
        local pid
        pid=$(grep "^${key}:" "$PIDS_FILE" 2>/dev/null | cut -d: -f2)
        if [ -n "$pid" ] && [ "$pid" -eq "$pid" ] 2>/dev/null; then
            log "Останавливаю $key (PID $pid)..."
            kill_pid "$pid"
            grep -v "^${key}:" "$PIDS_FILE" > "${PIDS_FILE}.tmp" 2>/dev/null || true
            mv "${PIDS_FILE}.tmp" "$PIDS_FILE" 2>/dev/null || true
        fi
    fi
    [ -n "$port" ] && kill_port "$port"
    sleep 1
}

# ========== restart (все или один сервис) ==========
cmd_restart() {
    local target="${1:-}"
    if [ -z "$target" ]; then
        cmd_stop
        sleep 2
        cmd_start
        return
    fi
    # Перезапуск одного сервиса
    if [ -f "$BRATS_ROOT/config.env" ]; then
        set -a; source "$BRATS_ROOT/config.env"; set +a
        [ -z "${OPENAI_API_KEY:-}" ] && [ -n "${PROXYAPI_KEY:-}" ] && export OPENAI_API_KEY="$PROXYAPI_KEY"
    fi
    mkdir -p "$LOGS_DIR"
    case "$target" in
        kb-service)
            stop_one "kb_service" "$PORT_KB"
            log "Запуск kb-service (порт $PORT_KB)..."
            cd "$BRATS_ROOT/kb-service"
            nohup uvicorn api.main:app --host 0.0.0.0 --port "$PORT_KB" >> "$LOGS_DIR/kb-service.log" 2>&1 &
            save_pid "kb_service" $!
            ;;
        kb-admin)
            stop_one "kb_admin" "$PORT_KB_ADMIN"
            log "Запуск KB Admin (порт $PORT_KB_ADMIN)..."
            cd "$BRATS_ROOT/kb-service"
            nohup streamlit run web/kb_admin_app.py --server.port "$PORT_KB_ADMIN" --server.headless true >> "$LOGS_DIR/kb-admin.log" 2>&1 &
            save_pid "kb_admin" $!
            ;;
        sales-agent)
            stop_one "sales_agent" "$PORT_AGENT"
            log "Запуск sales-agent (порт $PORT_AGENT)..."
            cd "$BRATS_ROOT/sales-agent"
            nohup python api/main.py >> "$LOGS_DIR/sales-agent.log" 2>&1 &
            save_pid "sales_agent" $!
            ;;
        amocrm-api)
            stop_one "amocrm_api" "$PORT_AMOCRM"
            log "Запуск amocrm-api (порт $PORT_AMOCRM)..."
            cd "$BRATS_ROOT/amocrm-api"
            nohup uvicorn api.main:app --host 0.0.0.0 --port "$PORT_AMOCRM" >> "$LOGS_DIR/amocrm-api.log" 2>&1 &
            save_pid "amocrm_api" $!
            ;;
        funnel-api)
            stop_one "funnel_api" "$PORT_FUNNEL"
            log "Запуск funnel-api (порт $PORT_FUNNEL)..."
            cd "$BRATS_ROOT/funnel-api"
            nohup uvicorn api.main:app --host 0.0.0.0 --port "$PORT_FUNNEL" >> "$LOGS_DIR/funnel-api.log" 2>&1 &
            save_pid "funnel_api" $!
            ;;
        n8n)
            stop_one "n8n_local" "$PORT_N8N"
            if [ "${N8N_DOCKER:-0}" = "1" ]; then
                docker stop n8n-brats 2>/dev/null || true
                sleep 2
                (cd "$N8N_DIR" && ./start_n8n.sh)
            else
                log "Запуск n8n локально..."
                export PATH="/usr/bin:/usr/local/bin:$PATH"
                cd "$N8N_DIR"
                export N8N_USER_FOLDER="${N8N_USER_FOLDER:-$HOME/.n8n}"
                export N8N_HOST="${N8N_HOST:-0.0.0.0}"
                export EXECUTIONS_DATA_SAVE_ON_SUCCESS="${EXECUTIONS_DATA_SAVE_ON_SUCCESS:-all}"
                nohup npx n8n >> "$LOGS_DIR/n8n.log" 2>&1 &
                save_pid "n8n_local" $!
            fi
            ;;
        site)
            stop_one "site_proxy" "$PORT_SITE"
            log "Запуск сайта с прокси (порт $PORT_SITE)..."
            nohup python "$BRATS_ROOT/site-integration/serve_with_proxy.py" >> "$LOGS_DIR/site-proxy.log" 2>&1 &
            save_pid "site_proxy" $!
            ;;
        *)
            err "Неизвестный сервис: $target"
            echo "  Допустимые: kb-service, kb-admin, sales-agent, amocrm-api, funnel-api, n8n, site"
            exit 1
            ;;
    esac
    cd "$BRATS_ROOT"
    sleep 2
    log "Готово: $target перезапущен."
}

# ========== main ==========
case "$command" in
    start)   cmd_start   ;;
    stop)    cmd_stop    ;;
    restart) cmd_restart "$2" ;;
    status)  cmd_status  ;;
    *)
        echo "Использование: $0 { start | stop | restart [сервис] | status }"
        echo ""
        echo "  start   — поднять kb-service (8001), sales-agent (8003), amocrm-api (8010), funnel-api (8011), n8n (5678), сайт (8000)"
        echo "  stop    — остановить все перечисленные сервисы"
        echo "  restart — остановить и снова поднять все"
        echo "  restart <сервис> — перезапустить один: kb-service, kb-admin, sales-agent, amocrm-api, funnel-api, n8n, site"
        echo "  status  — показать, какие порты заняты и отвечают ли сервисы"
        echo ""
        echo "  n8n локально (по умолчанию); с Docker: N8N_DOCKER=1 $0 start"
        echo "  После start: http://localhost:8000/site-integration-example.html"
        exit 1
        ;;
esac
