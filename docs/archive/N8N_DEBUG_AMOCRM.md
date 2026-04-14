# Отладка проблемы с Authorization в n8n

## Проблема: 401 Unauthorized при запросах к amoCRM

Заголовок Authorization отправляется, но получаем 401. Возможные причины:

1. **Переменная окружения не подставляется** - `{{$env.AMOCRM_ACCESS_TOKEN}}` возвращает пустую строку
2. **Токен неверный или истек**
3. **Неправильный формат заголовка**

## Решение 1: Проверка подстановки переменной

В ноде "Get Catalogs" попробуйте использовать прямое значение для теста:

1. Откройте ноду "Get Catalogs"
2. В разделе "Send Headers" → "Authorization"
3. Временно замените значение на прямое (для теста):
   ```
   Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjZjZWIyZGVjYzcwZjBjM2EyODhhNTFhMWE2MmU5YzU0MzczOGVkYzFlYmMzNTIyM2UwM2Q2MjIwMDkzYjY1YzNiYmYwYTdhYjRiYWI3NTM0In0...
   ```
4. Выполните ноду - если работает, значит проблема в подстановке переменной

## Решение 2: Использование Code ноды для проверки переменной

Добавьте Code ноду перед HTTP Request для проверки:

```javascript
// Проверка переменных окружения
const subdomain = $env.AMOCRM_SUBDOMAIN;
const token = $env.AMOCRM_ACCESS_TOKEN;

console.log('Subdomain:', subdomain);
console.log('Token length:', token ? token.length : 'undefined');

if (!token) {
  throw new Error('AMOCRM_ACCESS_TOKEN не найден в переменных окружения');
}

return {
  json: {
    subdomain: subdomain,
    token_preview: token ? token.substring(0, 50) + '...' : 'undefined',
    url: `https://${subdomain}.amocrm.ru/api/v4/catalogs`
  }
};
```

## Решение 3: Использование Code ноды для формирования заголовка

Вместо использования переменной в заголовке, можно сформировать заголовок в Code ноде:

```javascript
const token = $env.AMOCRM_ACCESS_TOKEN;

if (!token) {
  throw new Error('AMOCRM_ACCESS_TOKEN не найден');
}

return {
  json: {
    authorization_header: `Bearer ${token}`,
    url: `https://${$env.AMOCRM_SUBDOMAIN}.amocrm.ru/api/v4/catalogs`
  }
};
```

Затем в HTTP Request ноде используйте:
- URL: `={{ $json.url }}`
- Header Authorization: `={{ $json.authorization_header }}`

## Решение 4: Проверка токена напрямую

Проверьте токен через Code ноду:

```javascript
const token = $env.AMOCRM_ACCESS_TOKEN;

// Декодируем JWT токен (только payload, без проверки подписи)
const parts = token.split('.');
if (parts.length !== 3) {
  throw new Error('Неверный формат токена');
}

const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString());
const expiresAt = new Date(payload.exp * 1000);
const now = new Date();

return {
  json: {
    token_valid: expiresAt > now,
    expires_at: expiresAt.toISOString(),
    now: now.toISOString(),
    account_id: payload.account_id,
    scopes: payload.scopes
  }
};
```

## Решение 5: Использование Bearer Token authentication

Вместо ручного заголовка, используйте встроенную аутентификацию Bearer Token:

1. В ноде HTTP Request выберите **Authentication**: `Generic Credential Type`
2. **Credential Type**: `Bearer Token`
3. Создайте credential:
   - **Name**: `amocrm-bearer`
   - **Token**: `{{$env.AMOCRM_ACCESS_TOKEN}}`
4. Выберите этот credential в ноде

## Проверка переменных окружения в n8n

В Code ноде выполните:

```javascript
// Проверка всех переменных окружения
const envVars = {
  AMOCRM_SUBDOMAIN: $env.AMOCRM_SUBDOMAIN,
  AMOCRM_ACCESS_TOKEN: $env.AMOCRM_ACCESS_TOKEN ? 'SET (' + $env.AMOCRM_ACCESS_TOKEN.length + ' chars)' : 'NOT SET',
  N8N_BLOCK_ENV_ACCESS_IN_NODE: $env.N8N_BLOCK_ENV_ACCESS_IN_NODE
};

return {
  json: envVars
};
```

Если `AMOCRM_ACCESS_TOKEN` показывает "NOT SET", значит переменная не загружена в n8n.
