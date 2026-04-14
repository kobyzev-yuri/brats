#!/usr/bin/env bash
set -e
echo "=== 1. kb-service (8001) ==="
curl -s --connect-timeout 2 http://localhost:8001/health || echo "FAIL"
echo ""
echo "=== 2. sales-agent (8003) ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" --connect-timeout 2 http://localhost:8003/ || echo "FAIL"
echo "=== 3. n8n (5678) ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" --connect-timeout 2 http://localhost:5678/ || echo "FAIL"
echo "=== 4. Webhook POST ==="
curl -s -X POST http://localhost:5678/webhook/sales-agent-kb -H "Content-Type: application/json" -d '{"message":"test","channel":"site"}' --connect-timeout 5 -w "\nHTTP %{http_code}\n" || echo "FAIL"
echo "=== 5. Docker -> host.docker.internal:8001 ==="
docker run --rm --add-host=host.docker.internal:host-gateway curlimages/curl curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://host.docker.internal:8001/health 2>/dev/null && echo " OK" || echo " FAIL"
