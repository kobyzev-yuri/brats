# Настройка credentials для amoCRM в n8n

## Для workflow `amocrm-sync-catalog.json`

Workflow использует HTTP Request ноды с аутентификацией через **HTTP Header Auth**. Нужно создать credential для передачи токена amoCRM.

---

## Способ 1: Добавить заголовок напрямую в ноде (рекомендуется, проще)

Это самый простой способ — не нужно создавать отдельный credential.

### Шаг 1: Открыть ноду HTTP Request

1. Откройте workflow `amocrm-sync-catalog.json` в редакторе n8n
2. Откройте ноду **"Get Catalogs"** (или **"Get Catalog Elements"**)

### Шаг 2: Добавить заголовок Authorization

1. В ноде найдите раздел **Send Headers** (или **Headers**)
2. Включите опцию **Send Headers** (если она выключена)
3. Нажмите **Add Parameter** или **Add Header**
4. Заполните:
   - **Name**: `Authorization`
   - **Value**: `Bearer {{$env.AMOCRM_ACCESS_TOKEN}}`

**Важно:** 
- Используйте `Bearer ` (с пробелом после Bearer)
- `{{$env.AMOCRM_ACCESS_TOKEN}}` — это переменная окружения из `config.env`

### Шаг 3: Повторить для других нод

Повторите шаги 1-2 для ноды **"Get Catalog Elements"**

---

## Способ 2: Создать HTTP Header Auth credential (альтернатива)

Если хотите использовать credential для переиспользования:

### Шаг 1: Создать credential

1. В n8n перейдите в **Settings** → **Credentials**
2. Нажмите **Add Credential**
3. Найдите **Generic Credential Type** → выберите **Header Auth**

### Шаг 2: Заполнить поля

| Поле | Значение |
|------|----------|
| **Name** | `amocrm-api` |
| **Header Name** | `Authorization` |
| **Header Value** | `Bearer {{$env.AMOCRM_ACCESS_TOKEN}}` |

### Шаг 3: Применить к нодам

В нодах выберите:
- **Authentication**: `Generic Credential Type`
- **Credential Type**: `Header Auth`
- **Credential**: выберите `amocrm-api`

---

## Настроить переменные окружения в n8n

Убедитесь, что переменные окружения доступны в n8n:

1. В n8n перейдите в **Settings** → **Environment Variables** (или через docker-compose/env)
2. Добавьте переменные:
   ```
   AMOCRM_SUBDOMAIN=innovatoryclub
   AMOCRM_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjZjZWIyZGVjYzcwZjBjM2EyODhhNTFhMWE2MmU5YzU0MzczOGVkYzFlYmMzNTIyM2UwM2Q2MjIwMDkzYjY1YzNiYmYwYTdhYjRiYWI3NTM0In0...
   ```

**Или** если используете docker-compose, переменные из `config.env` должны автоматически загружаться.

---

## Пример настройки ноды "Get Catalogs" (Способ 1)

1. Откройте ноду **"Get Catalogs"**
2. Убедитесь, что:
   - **Method**: `GET`
   - **URL**: `https://{{$env.AMOCRM_SUBDOMAIN}}.amocrm.ru/api/v4/catalogs`
   - **Authentication**: `None` (или оставьте как есть)
3. Найдите раздел **Send Headers** и включите его
4. Добавьте заголовок:
   - **Name**: `Authorization`
   - **Value**: `Bearer {{$env.AMOCRM_ACCESS_TOKEN}}`
5. Сохраните ноду
6. Повторите для ноды **"Get Catalog Elements"**

---

## Альтернативный вариант: Напрямую в ноде

Если не хотите создавать отдельный credential, можно указать токен напрямую в ноде:

1. Откройте ноду **"Get Catalogs"**
2. В разделе **Authentication** выберите **Generic Credential Type** → **HTTP Header Auth**
3. В полях укажите:
   - **Header Name**: `Authorization`
   - **Header Value**: `Bearer {{$env.AMOCRM_ACCESS_TOKEN}}`

---

## Проверка настроек

После настройки credential:

1. **Проверьте переменные окружения:**
   - В ноде можно использовать `{{$env.AMOCRM_SUBDOMAIN}}` и `{{$env.AMOCRM_ACCESS_TOKEN}}`
   - Убедитесь, что они доступны в n8n

2. **Протестируйте ноду:**
   - Нажмите **Execute Node** на ноде "Get Catalogs"
   - Должен вернуться список каталогов из amoCRM

3. **Проверьте URL:**
   - URL должен быть: `https://{{$env.AMOCRM_SUBDOMAIN}}.amocrm.ru/api/v4/catalogs`
   - После подстановки: `https://innovatoryclub.amocrm.ru/api/v4/catalogs`

---

## Структура workflow `amocrm-sync-catalog.json`

```
Cron Trigger (каждый час)
  ↓
Get Catalogs (HTTP Request с HTTP Header Auth)
  ↓
Split Catalogs (Code - разделение каталогов)
  ↓
Get Catalog Elements (HTTP Request с HTTP Header Auth)
  ↓
Prepare Elements (Code - подготовка данных)
  ↓
Sync to Database (HTTP Request к KB Service)
  ↓
Log Sync (Code - логирование)
```

**Ноды, требующие credential:**
- ✅ **Get Catalogs** — нужен HTTP Header Auth credential
- ✅ **Get Catalog Elements** — нужен HTTP Header Auth credential

---

## Пример настройки ноды "Get Catalogs"

```json
{
  "method": "GET",
  "url": "=https://{{$env.AMOCRM_SUBDOMAIN}}.amocrm.ru/api/v4/catalogs",
  "authentication": "genericCredentialType",
  "genericAuthType": "httpHeaderAuth",
  "httpHeaderAuth": {
    "name": "Authorization",
    "value": "Bearer {{$env.AMOCRM_ACCESS_TOKEN}}"
  }
}
```

---

## Устранение проблем

### Ошибка: "Unauthorized" или "401"

- Проверьте, что токен правильный в `config.env`
- Убедитесь, что используется `Bearer ` (с пробелом)
- Проверьте, что переменная `{{$env.AMOCRM_ACCESS_TOKEN}}` доступна в n8n

### Ошибка: "Variable not found"

- Убедитесь, что переменные окружения загружены в n8n
- Проверьте `config.env` и перезапустите n8n
- В docker-compose убедитесь, что `env_file: - ../config.env` указан

### Ошибка: "Invalid URL"

- Проверьте, что `AMOCRM_SUBDOMAIN` правильный
- URL должен быть: `https://innovatoryclub.amocrm.ru/api/v4/catalogs`

---

## Быстрая проверка

После настройки можно протестировать вручную:

1. Откройте ноду **"Get Catalogs"**
2. Нажмите **Execute Node**
3. Должен вернуться JSON с каталогами:
   ```json
   {
     "_embedded": {
       "catalogs": [...]
     }
   }
   ```

Если всё работает — workflow готов к использованию!
