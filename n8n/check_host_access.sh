#!/bin/bash
# Проверка доступа из контейнера n8n к сервисам на хосте (KB :8001, sales-agent :8003).
# Нужен только если n8n запущен в Docker. При локальном n8n (./start_n8n_local.sh
# или start_all_services.sh) используйте workflow с localhost — эта проверка не нужна.
# Запускайте из папки n8n: ./check_host_access.sh

set -e

# Подгружаем config.env для единого значения N8N_EXTRA_HOSTS
if [ -f "config.env" ]; then
    set -a; source config.env; set +a
elif [ -f "../config.env" ]; then
    set -a; source ../config.env; set +a
fi
EXTRA_HOSTS="${N8N_EXTRA_HOSTS:-host.docker.internal:host-gateway}"

echo "=== Проверка доступа к хосту из контейнера (extra_hosts: $EXTRA_HOSTS) ==="
echo ""

echo "1. С хоста (localhost):8001 — kb-service должен быть запущен и слушать 0.0.0.0"
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://localhost:8001/health 2>/dev/null | grep -q 200; then
    echo "   OK: kb-service отвечает на localhost:8001"
else
    echo "   FAIL: localhost:8001 не отвечает. Запустите: cd kb-service && uvicorn api.main:app --host 0.0.0.0 --port 8001"
fi

echo ""
echo "2. Из контейнера (host.docker.internal:8001) — как видит n8n"
CODE=$(docker run --rm --add-host="$EXTRA_HOSTS" curlimages/curl:latest curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://host.docker.internal:8001/health 2>/dev/null || echo "000")
if [ "$CODE" = "200" ]; then
    echo "   OK: host.docker.internal:8001 доступен из контейнера (KB Search должен работать)"
else
    echo "   FAIL: из контейнера host.docker.internal:8001 вернул код $CODE или таймаут."
    echo "   Убедитесь: 1) kb-service запущен с --host 0.0.0.0  2) n8n запущен с тем же extra_hosts (./start_n8n.sh или docker compose с N8N_EXTRA_HOSTS)"
fi

echo ""
echo "3. С хоста (localhost):8003 — sales-agent"
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://localhost:8003/ 2>/dev/null | grep -q 200; then
    echo "   OK: sales-agent отвечает на localhost:8003"
else
    echo "   FAIL или не 200: localhost:8003. Запустите sales-agent с --host 0.0.0.0 --port 8003"
fi

echo ""
echo "4. Из контейнера (host.docker.internal:8003)"
CODE3=$(docker run --rm --add-host="$EXTRA_HOSTS" curlimages/curl:latest curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://host.docker.internal:8003/ 2>/dev/null || echo "000")
if [ "$CODE3" = "200" ]; then
    echo "   OK: host.docker.internal:8003 доступен (Sales Agent Call должен работать)"
else
    echo "   FAIL: из контейнера 8003 вернул $CODE3"
fi

echo ""
echo "=== Готово. Если п.1 и п.2 OK, узел KB Search должен проходить. ==="
