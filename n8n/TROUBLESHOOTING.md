# Устранение проблем с n8n

**Нет записи в CRM, данные не доходят до n8n** (форма/чат работают «чудом» или не создают лид) — пошаговая диагностика: [docs/TROUBLESHOOTING_CRM_AND_N8N.md](../docs/TROUBLESHOOTING_CRM_AND_N8N.md). Там же: как смотреть логи прокси (serve_with_proxy.py) и что проверять в n8n Executions.

---

## Проблема: в Executions пусто (только старая ошибка, новых запусков нет)

Прокси показывает `[n8n] POST chat <- 200`, но в n8n в списке Executions не появляются новые записи.

### 1. Workflow должен быть включён (Active)

- Откройте **Workflows** → выберите **Sales Agent - KB Integration** (или ваш основной workflow с чатом).
- Справа вверху переключатель **Active** должен быть **включён** (зелёный). Если выключен — webhook не зарегистрирован, запросы могут обрабатываться другим workflow или возвращать 404/дефолтный ответ.

### 2. Фильтр Executions

- В **Executions** сверху выберите **All** (или **Success**), а не только **Error** — иначе успешные запуски не видны.

### 3. Сохранение успешных выполнений (curl OK, но в списке пусто)

Если **curl** возвращает полный ответ с `agent_response`, а в **Executions** новых строк нет — отключено сохранение успешных запусков.

**Вариант A: переменная окружения (при запуске n8n)**  
Убедитесь, что **не** задано `EXECUTIONS_DATA_SAVE_ON_SUCCESS=none`. Чтобы успешные выполнения сохранялись, либо не задавайте эту переменную (по умолчанию сохраняются), либо явно задайте:
```bash
export EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
```
Затем перезапустите n8n.

**Вариант B: настройки workflow**  
Откройте workflow **Sales Agent - KB Integration** → меню (три точки) или вкладка **Settings** у workflow → найдите опцию вроде **Save successful production executions** / **Save execution data**. Поставьте **Save** или **Use default** (не «Do not save»). Сохраните workflow.

### 4. Тот ли workflow отвечает на webhook

- В workflow откройте узел **Webhook** → вкладка **Production URL**. Должен быть путь вида `.../webhook/sales-agent-kb`.
- Прокси по умолчанию шлёт на `http://localhost:5678/webhook/sales-agent-kb`. Если у вас другой хост/порт — задайте **N8N_WEBHOOK_URL** при запуске прокси.
- Проверка с терминала:  
  `curl -X POST http://localhost:5678/webhook/sales-agent-kb -H "Content-Type: application/json" -d '{"message":"тест","channel":"website","external_id":"test-1"}'`  
  Сразу после этого в **Executions** должна появиться новая строка (Success или Error). Если не появляется — webhook не привязан к этому workflow (включите Active) или n8n не сохраняет выполнения (п. 3).

### 5. Перезапуск n8n

- После включения workflow (Active) или смены настроек Executions перезапустите n8n и снова отправьте сообщение из чата.

---

## Проблема: "Cannot GET" при открытии http://localhost:5678

### Решение 1: Очистка кэша браузера

1. Откройте браузер в режиме инкогнито (Ctrl+Shift+N)
2. Или очистите кэш браузера (Ctrl+Shift+Delete)

### Решение 2: Использование 127.0.0.1 вместо localhost

Попробуйте открыть:
- http://127.0.0.1:5678

### Решение 3: Проверка, что n8n запущен

```bash
# Проверка статуса контейнера
docker ps | grep n8n-brats

# Проверка логов
docker logs --tail 50 n8n-brats

# Проверка health check
curl http://localhost:5678/healthz
```

Должен вернуться: `{"status":"ok"}`

### Решение 4: Перезапуск n8n

```bash
cd /projects/brats/n8n
docker stop n8n-brats
docker rm n8n-brats
./start_n8n.sh
```

Подождите 10-15 секунд после запуска, затем откройте браузер.

### Решение 5: Проверка порта

```bash
# Проверка, что порт 5678 открыт
netstat -tuln | grep 5678
# или
ss -tuln | grep 5678
```

### Решение 6: Проверка через curl

```bash
# Проверка, что n8n отвечает
curl http://localhost:5678/
```

Если возвращается HTML - n8n работает, проблема в браузере.

## Проблема: Страница загружается, но показывает ошибку

### Проверка логов

```bash
docker logs -f n8n-brats
```

Смотрите на ошибки в логах.

## Проблема: Не могу создать учетную запись

1. Убедитесь, что используете валидный email (например: `admin@localhost`)
2. Пароль должен быть достаточно сложным (обычно минимум 8 символов)
3. Проверьте логи на наличие ошибок

## Проблема: Забыл пароль

Если забыли пароль, можно сбросить данные n8n:

```bash
# Остановка n8n
docker stop n8n-brats
docker rm n8n-brats

# Удаление данных (⚠️ ВНИМАНИЕ: это удалит все workflows!)
rm -rf ~/.n8n

# Запуск заново
cd /projects/brats/n8n
./start_n8n.sh
```

## Проблема: узел «LLM ProxyAPI» — «invalid JSON in response body»

**Симптом:** в Executions узел **LLM ProxyAPI** падает с ошибкой вроде *invalid JSON in response body*, а в сообщении виден текст пользователя (например «Простите, телефон +7 *** ***-**-**»).

**Причина:** ответ от ProxyAPI/OpenAI пришёл не в виде валидного JSON. Так бывает, если:
- API вернул тело ответа как **plain text** (например, только текст ответа модели без обёртки `{"choices":[...]}`);
- модель «эхо» вернула сообщение пользователя как свой ответ, и прокси отдал его без JSON-обёртки;
- произошла ошибка на стороне API и вернулось текстовое описание.

**Что сделать:**

1. **В узле LLM ProxyAPI (HTTP Request):**  
   В настройках найдите опцию **Response** / **Response Format**. Если стоит **JSON**, переключите на **String** или **Autodetect**, чтобы n8n не падал на не-JSON теле. Сохраните узел.

2. **В узле «LLM Response Format» (Code):**  
   Сделайте код устойчивым к обоим вариантам — и к объекту (стандартный ответ OpenAI), и к строке (сырой текст):
   ```js
   const raw = $input.first().json;
   let text = '';
   if (typeof raw === 'string') {
     text = raw.trim();
   } else {
     text = raw.choices?.[0]?.message?.content ?? raw.message?.content ?? '';
   }
   return [{ json: { response: text, message: text } }];
   ```
   Тогда при ответе в виде строки (в т.ч. «Простите, телефон +7 …») она уйдёт в чат как ответ агента, а не как падение узла.

3. **Проверка в Executions:**  
   Откройте упавшее выполнение → клик по узлу LLM ProxyAPI → посмотрите **Response** / **Body**. Если там строка без `choices`, значит API действительно вернул не-JSON; п. 1 и 2 это обрабатывают.

4. **Промпт:**  
   Если модель часто возвращает только эхо сообщения пользователя, ужесточите системный промпт в **Format KB Context** (например: «Отвечай только от имени консультанта, не повторяй сообщение клиента дословно»).

## Полезные команды

```bash
# Просмотр логов в реальном времени
docker logs -f n8n-brats

# Перезапуск n8n
docker restart n8n-brats

# Остановка n8n
docker stop n8n-brats

# Удаление контейнера
docker rm n8n-brats

# Проверка использования ресурсов
docker stats n8n-brats
```
















