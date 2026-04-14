# Отладка узла KB Search (Connection Refused)

Когда в workflow «Sales Agent - KB Integration» узел **KB Search** выдаёт «The service refused the connection» — запрос из n8n не доходит до kb-service. Мы используем **локальный n8n** (без Docker), поэтому в узлах должны быть URL **localhost**.

## Чеклист (локальный n8n)

1. **kb-service запущен и слушает 0.0.0.0**
   - Запуск: `cd kb-service && uvicorn api.main:app --host 0.0.0.0 --port 8001`  
     или через `./start_all_services.sh start`
   - Проверка: `curl -s http://localhost:8001/health` → ответ с `"status":"healthy"`

2. **В узле KB Search в n8n указан localhost**
   - В редакторе workflow откройте узел **KB Search**.
   - URL должен быть: `http://localhost:8001/api/kb/search`
   - Если в логе ошибки видно `"uri": "http://localhost:8001/..."` и при этом ECONNREFUSED — значит, kb-service не запущен или не слушает на 8001 (см. п.1).
   - Используйте workflow **sales-agent-kb-integration-localhost.json** (в нём уже правильные URL).

3. **n8n запущен локально**
   - Запуск: `./start_all_services.sh start` (n8n поднимется через npx) или `cd n8n && ./start_n8n_local.sh`
   - Не используйте Docker для n8n — тогда не нужен host.docker.internal.

**Итого:** локальный n8n + workflow с **localhost** (sales-agent-kb-integration-localhost.json) + kb-service на 8001.
