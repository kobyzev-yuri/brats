# n8n в Docker: доступ к сервисам на хосте

**По умолчанию мы используем n8n без Docker** (`./start_all_services.sh start` или `./start_n8n_local.sh`) и workflow **sales-agent-kb-integration-localhost.json** с URL localhost. Этот файл нужен только если вы сознательно запускаете n8n в Docker.

Когда n8n запущен в Docker, запросы из workflow на **localhost** идут внутрь контейнера, а не на хост. Поэтому узлы «KB Search» и «Sales Agent Call» не доходят до kb-service (8001) и sales-agent (8003).

## Решение

В workflow используются адреса **host.docker.internal**:
- KB Search: `http://host.docker.internal:8001/api/kb/search`
- Sales Agent Call: `http://host.docker.internal:8003/api/chat`

В `docker-compose.yml` для n8n добавлено:
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```
(на Linux это даёт контейнеру доступ к хосту по имени host.docker.internal.)

## Конфиг

В `config.env` (в корне проекта или в папке `n8n/`) задайте:

```bash
N8N_EXTRA_HOSTS=host.docker.internal:host-gateway
```


## Что сделать

1. **Сервисы на хосте должны слушать 0.0.0.0**, иначе контейнер не подключится:
   - **kb-service:** `uvicorn api.main:app --host 0.0.0.0 --port 8001` (или `API_HOST=0.0.0.0`). Не запускайте с `--host 127.0.0.1`.
   - **sales-agent:** `uvicorn api.main:app --host 0.0.0.0 --port 8003`.

2. **Перезапустить n8n** с `--add-host=host.docker.internal:host-gateway` (в `start_n8n.sh` это уже есть):
   ```bash
   cd n8n
   ./start_n8n.sh
   ```

3. **Обновить workflow в n8n**: импортировать `workflows/sales-agent-kb-integration.json` или в узлах «KB Search» и «Sales Agent Call» указать URL с `host.docker.internal`.

4. **Проверка с хоста:** `curl -s http://localhost:8001/health` и `curl -s http://localhost:8003/` — оба должны отвечать.

5. **Диагностика «The service refused the connection»:** запустите скрипт из папки `n8n`:
   ```bash
   cd n8n
   chmod +x check_host_access.sh
   ./check_host_access.sh
   ```
   Он проверит доступ к 8001/8003 с хоста и из контейнера. Если из контейнера «FAIL»:
   - убедитесь, что **kb-service** запущен с `--host 0.0.0.0` (не `127.0.0.1`);
   - перезапустите n8n так, чтобы подхватить `N8N_EXTRA_HOSTS`: `./start_n8n.sh` или `docker compose down && docker compose up -d` (для compose переменная подставляется из default в yml или из окружения).

---

## Отладка узла KB Search (Connection Refused)

Если в n8n узел **KB Search** падает с «The service refused the connection», а админка KB на том же хосте работает — запрос из контейнера n8n не доходит до kb-service. По шагам:

### 1. Проверить, что kb-service слушает на 0.0.0.0

Админка ходит с браузера на `localhost:8001`, n8n — из контейнера на `host.docker.internal:8001`. Если kb-service запущен с `--host 127.0.0.1`, с хоста будет работать, из контейнера — connection refused.

- Запуск kb-service **правильно**:  
  `uvicorn api.main:app --host 0.0.0.0 --port 8001`  
  (или в `start.sh` / переменной окружения: `API_HOST=0.0.0.0`).
- Проверка с хоста:  
  `curl -s http://localhost:8001/health` — должен вернуть JSON со статусом.

### 2. Проверить доступ из контейнера к хосту

Из папки `n8n`:

```bash
./check_host_access.sh
```

Смотрите пункт «2. Из контейнера (host.docker.internal:8001)». Должно быть **OK**. Если **FAIL**:
- n8n должен быть запущен с `extra_hosts` / `--add-host=host.docker.internal:host-gateway` (см. выше);
- перезапустите n8n после изменения конфига.

### 3. URL в узле KB Search в n8n

В логе n8n при ошибке смотрите поле **Request → uri**. Если там `http://localhost:8001/...` — это и есть причина: из контейнера **localhost** = сам контейнер, до хоста не доходит.

В редакторе workflow откройте узел **KB Search** и замените URL на:

- `http://host.docker.internal:8001/api/kb/search`

**Не** оставляйте `http://localhost:8001/...`. Сохраните workflow (Ctrl+S). Либо заново импортируйте `workflows/sales-agent-kb-integration.json` (в нём уже стоит host.docker.internal).

### 4. Итог

| Где проверяем | Команда / действие |
|---------------|---------------------|
| kb-service на хосте | `curl -s http://localhost:8001/health` → 200 |
| Доступ из контейнера | `./check_host_access.sh` → п.2 OK |
| URL в n8n | В узле KB Search: `http://host.docker.internal:8001/api/kb/search` |
| Перезапуск n8n | `./start_n8n.sh` или `docker compose down && docker compose up -d` |

После этого узел KB Search должен проходить. Если появится ошибка 422 (Unprocessable Entity) — значит соединение есть, но тело запроса не подходит: в узле KB Search выберите отправку тела как **JSON** и передайте поля `query`, `limit`, `target_audience`, `min_similarity` в формате JSON.
