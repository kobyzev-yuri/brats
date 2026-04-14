# Настройка API доступа к amoCRM

## Обзор

Для работы с API amoCRM необходимо настроить OAuth2 авторизацию и получить токены доступа. amoCRM использует стандартный OAuth2 flow для авторизации приложений.

## Необходимые параметры

### 1. Данные для создания интеграции в amoCRM

Для начала работы нужно создать интеграцию в вашем аккаунте amoCRM:

1. **Subdomain (поддомен)**
   - Это часть URL вашего аккаунта amoCRM
   - Если ваш аккаунт доступен по адресу `mycompany.amocrm.ru`, то subdomain = `"mycompany"`
   - Используется в URL всех API запросов: `https://{subdomain}.amocrm.ru/api/v4/...`

2. **Client ID (ID интеграции)**
   - Получается при создании интеграции в amoCRM
   - Находится в разделе "Настройки" → "Интеграции" → "Создать интеграцию"
   - Используется для получения токенов доступа

3. **Client Secret (Секретный ключ)**
   - Получается вместе с Client ID при создании интеграции
   - **Важно**: хранить в секрете, не коммитить в репозиторий
   - Используется для получения токенов доступа

4. **Redirect URI (URI перенаправления)**
   - URL, на который amoCRM перенаправит после авторизации
   - Должен быть зарегистрирован в настройках интеграции
   - Примеры:
     - Для локальной разработки: `http://localhost:8000/auth/amocrm/callback`
     - Для продакшена: `https://yourdomain.com/auth/amocrm/callback`
   - **Важно**: должен точно совпадать с тем, что указано в настройках интеграции

### 2. Токены доступа (получаются после авторизации)

После успешной авторизации вы получите:

1. **Access Token (токен доступа)**
   - Используется для всех API запросов
   - Время жизни: обычно 24 часа
   - Передаётся в заголовке: `Authorization: Bearer {access_token}`
   - **Важно**: токен нужно обновлять через Refresh Token

2. **Refresh Token (токен обновления)**
   - Используется для получения нового Access Token
   - Время жизни: обычно 30 дней (или больше, в зависимости от настроек)
   - **Важно**: хранить в безопасном месте, использовать для автоматического обновления токенов

## Процесс получения токенов (OAuth2 Authorization Code Flow)

> **Для n8n:** пошаговое создание внешней интеграции в amoМаркет и подключение к n8n описано в [AMOCRM_N8N_INTEGRATION_SETUP.md](./AMOCRM_N8N_INTEGRATION_SETUP.md).

### Шаг 1: Создание интеграции в amoCRM

1. Войдите в ваш аккаунт amoCRM
2. Перейдите в **Настройки** → **Интеграции** или **amoМаркет** → **Создать интеграцию**
3. Заполните форму:
   - **Название**: например, "Нейропродажник"
   - **Redirect URI**: URL вашего приложения для callback (например, `http://localhost:8000/auth/amocrm/callback`)
   - **Права доступа**: выберите необходимые права:
     - `leads` - работа с лидами и сделками
     - `contacts` - работа с контактами
     - `catalogs` - работа с каталогами товаров
     - `notes` - работа с примечаниями
     - `tasks` - работа с задачами
     - `companies` - работа с компаниями
4. Сохраните интеграцию
5. Скопируйте **Client ID** и **Client Secret**

### Шаг 2: Первичная авторизация (получение кода)

Пользователь должен авторизовать приложение, перейдя по ссылке:

```
https://{subdomain}.amocrm.ru/oauth2/authorize?
  client_id={client_id}&
  response_type=code&
  redirect_uri={redirect_uri}
```

Пример:
```
https://mycompany.amocrm.ru/oauth2/authorize?
  client_id=12345678-1234-1234-1234-123456789012&
  response_type=code&
  redirect_uri=http://localhost:8000/auth/amocrm/callback
```

После авторизации amoCRM перенаправит на `redirect_uri` с параметром `code`:
```
http://localhost:8000/auth/amocrm/callback?code=AUTHORIZATION_CODE
```

### Шаг 3: Обмен кода на токены

Используйте полученный `code` для получения токенов:

```python
import httpx

async def get_amocrm_tokens(
    subdomain: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    authorization_code: str
) -> dict:
    """
    Обмен authorization code на access token и refresh token.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{subdomain}.amocrm.ru/oauth2/access_token",
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": redirect_uri
            }
        )
        response.raise_for_status()
        return response.json()
```

Ответ будет содержать:
```json
{
  "token_type": "Bearer",
  "expires_in": 86400,
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "def50200a1b2c3d4e5f6..."
}
```

### Шаг 4: Обновление токена (когда access_token истёк)

Когда `access_token` истечёт, используйте `refresh_token` для получения нового:

```python
async def refresh_amocrm_token(
    subdomain: str,
    client_id: str,
    client_secret: str,
    refresh_token: str
) -> dict:
    """
    Обновление access token через refresh token.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{subdomain}.amocrm.ru/oauth2/access_token",
            json={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "redirect_uri": redirect_uri  # Тот же, что использовался при создании интеграции
            }
        )
        response.raise_for_status()
        return response.json()
```

## Хранение конфигурации

### Рекомендуемый формат: `.env` файл

Создайте файл `.env` в корне проекта (не коммитьте его в Git):

```bash
# amoCRM Configuration
AMOCRM_SUBDOMAIN=mycompany
AMOCRM_CLIENT_ID=12345678-1234-1234-1234-123456789012
AMOCRM_CLIENT_SECRET=abcdefghijklmnopqrstuvwxyz1234567890
AMOCRM_REDIRECT_URI=http://localhost:8000/auth/amocrm/callback

# Токены (получаются после авторизации, обновляются автоматически)
# Access Token - используется для всех API запросов (срок жизни ~24 часа)
AMOCRM_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjEyMzQ1Njc4LTkwYWItMTIzNC00NTY3LTg5MGFiMTIzNDU2NyJ9.eyJpc3MiOiJodHRwczovL215Y29tcGFueS5hbW9jcm0ucnUiLCJhdWQiOiJodHRwczovL215Y29tcGFueS5hbW9jcm0ucnUvYXBpL3Y0IiwianRpIjoiMTIzNDU2NzgtOTBhYi0xMjM0LTQ1NjctODkwYWIxMjM0NTY3IiwiZXhwIjoxNzM2OTQ1NjAwLCJuYmYiOjE3MzY4NTkyMDAsImlhdCI6MTczNjg1OTIwMCwianRpIjoiMTIzNDU2NzgtOTBhYi0xMjM0LTQ1NjctODkwYWIxMjM0NTY3IiwidXNlcl9pZCI6MTIzNDU2Nywic2NvcGUiOlsibGVhZHMiLCJjb250YWN0cyIsImNhdGFsb2dzIl19.abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz1234567890

# Refresh Token - используется для обновления Access Token (срок жизни ~30 дней)
AMOCRM_REFRESH_TOKEN=def50200a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4a5b6c7d8e9f0g1h2i3j4k5l6m7n8o9p0q1r2s3t4u5v6w7x8y9z0a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6

# Дата истечения Access Token (ISO формат)
AMOCRM_TOKEN_EXPIRES_AT=2024-01-15T12:00:00Z
```

**Примечания:**
- `AMOCRM_ACCESS_TOKEN` — это JWT токен, обычно длиной 500-1000 символов
- `AMOCRM_REFRESH_TOKEN` — это строка, обычно длиной 200-400 символов
- Токены получаются после успешной авторизации через OAuth2
- Access Token автоматически обновляется через Refresh Token перед истечением

### Добавьте `.env` в `.gitignore`

```gitignore
# Environment variables
.env
.env.local
.env.*.local
```

### Использование в коде

```python
import os
from dotenv import load_dotenv

load_dotenv()

AMOCRM_SUBDOMAIN = os.getenv("AMOCRM_SUBDOMAIN")
AMOCRM_CLIENT_ID = os.getenv("AMOCRM_CLIENT_ID")
AMOCRM_CLIENT_SECRET = os.getenv("AMOCRM_CLIENT_SECRET")
AMOCRM_REDIRECT_URI = os.getenv("AMOCRM_REDIRECT_URI")
AMOCRM_ACCESS_TOKEN = os.getenv("AMOCRM_ACCESS_TOKEN")
AMOCRM_REFRESH_TOKEN = os.getenv("AMOCRM_REFRESH_TOKEN")
```

## Практические примеры использования токенов при вызовах API

### Пример 1: Простой запрос с использованием токена из .env

```python
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def get_leads_example():
    """
    Получение списка лидов с использованием токена из .env.
    """
    subdomain = os.getenv("AMOCRM_SUBDOMAIN")
    access_token = os.getenv("AMOCRM_ACCESS_TOKEN")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{subdomain}.amocrm.ru/api/v4/leads",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            params={"limit": 50, "page": 1}
        )
        response.raise_for_status()
        data = response.json()
        
        leads = data.get("_embedded", {}).get("leads", [])
        print(f"Найдено лидов: {len(leads)}")
        return leads

# Использование
# import asyncio
# asyncio.run(get_leads_example())
```

### Пример 2: Создание лида с токеном из .env

```python
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def create_lead_example():
    """
    Создание нового лида с использованием токена из .env.
    """
    subdomain = os.getenv("AMOCRM_SUBDOMAIN")
    access_token = os.getenv("AMOCRM_ACCESS_TOKEN")
    
    lead_data = {
        "name": "Лид от нейропродажника",
        "price": 0,
        "custom_fields_values": [
            {
                "field_id": 123456,  # ID поля в amoCRM
                "values": [
                    {
                        "value": "Интерес к коттеджу"
                    }
                ]
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{subdomain}.amocrm.ru/api/v4/leads",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=[lead_data]  # amoCRM ожидает массив
        )
        response.raise_for_status()
        data = response.json()
        
        created_lead = data.get("_embedded", {}).get("leads", [])[0]
        lead_id = created_lead.get("id")
        print(f"Создан лид с ID: {lead_id}")
        return lead_id
```

### Пример 3: Получение каталогов и товаров с токеном из .env

```python
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def get_catalogs_example():
    """
    Получение списка каталогов с использованием токена из .env.
    """
    subdomain = os.getenv("AMOCRM_SUBDOMAIN")
    access_token = os.getenv("AMOCRM_ACCESS_TOKEN")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{subdomain}.amocrm.ru/api/v4/catalogs",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        catalogs = data.get("_embedded", {}).get("catalogs", [])
        print(f"Найдено каталогов: {len(catalogs)}")
        return catalogs

async def get_catalog_elements_example(catalog_id: int):
    """
    Получение элементов каталога с использованием токена из .env.
    """
    subdomain = os.getenv("AMOCRM_SUBDOMAIN")
    access_token = os.getenv("AMOCRM_ACCESS_TOKEN")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{subdomain}.amocrm.ru/api/v4/catalogs/{catalog_id}/elements",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            params={"limit": 250}  # Максимум за один запрос
        )
        response.raise_for_status()
        data = response.json()
        
        elements = data.get("_embedded", {}).get("elements", [])
        print(f"Найдено элементов в каталоге: {len(elements)}")
        return elements

# Использование
# import asyncio
# catalogs = asyncio.run(get_catalogs_example())
# if catalogs:
#     elements = asyncio.run(get_catalog_elements_example(catalogs[0]["id"]))
```

### Пример 4: Обработка истечения токена и автоматическое обновление

```python
import os
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class AmoCRMAPI:
    def __init__(self):
        self.subdomain = os.getenv("AMOCRM_SUBDOMAIN")
        self.client_id = os.getenv("AMOCRM_CLIENT_ID")
        self.client_secret = os.getenv("AMOCRM_CLIENT_SECRET")
        self.redirect_uri = os.getenv("AMOCRM_REDIRECT_URI")
        self.access_token = os.getenv("AMOCRM_ACCESS_TOKEN")
        self.refresh_token = os.getenv("AMOCRM_REFRESH_TOKEN")
        
        # Парсим дату истечения токена из .env
        expires_at_str = os.getenv("AMOCRM_TOKEN_EXPIRES_AT")
        self.token_expires_at = None
        if expires_at_str:
            self.token_expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
    
    async def refresh_access_token(self):
        """
        Обновляет access token через refresh token и обновляет .env файл.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.subdomain}.amocrm.ru/oauth2/access_token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "redirect_uri": self.redirect_uri
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Обновляем токены
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            expires_in = data.get("expires_in", 86400)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Обновляем .env файл (опционально, для удобства разработки)
            self._update_env_file()
            
            print("Токен успешно обновлён")
            return self.access_token
    
    def _update_env_file(self):
        """
        Обновляет токены в .env файле.
        """
        env_path = ".env"
        if not os.path.exists(env_path):
            return
        
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            if line.startswith("AMOCRM_ACCESS_TOKEN="):
                new_lines.append(f"AMOCRM_ACCESS_TOKEN={self.access_token}\n")
            elif line.startswith("AMOCRM_REFRESH_TOKEN="):
                new_lines.append(f"AMOCRM_REFRESH_TOKEN={self.refresh_token}\n")
            elif line.startswith("AMOCRM_TOKEN_EXPIRES_AT="):
                new_lines.append(f"AMOCRM_TOKEN_EXPIRES_AT={self.token_expires_at.isoformat()}\n")
            else:
                new_lines.append(line)
        
        with open(env_path, "w") as f:
            f.writelines(new_lines)
    
    async def _ensure_valid_token(self):
        """
        Проверяет и обновляет токен, если он истёк или скоро истечёт.
        """
        if not self.access_token:
            raise ValueError("Access token not set. Please authorize first.")
        
        # Проверяем, нужно ли обновить токен (за 5 минут до истечения)
        if self.token_expires_at and datetime.now() >= self.token_expires_at - timedelta(minutes=5):
            await self.refresh_access_token()
    
    async def api_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        Выполняет запрос к API с автоматическим обновлением токена.
        """
        await self._ensure_valid_token()
        
        url = f"https://{self.subdomain}.amocrm.ru/api/v4/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        })
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            
            # Если токен истёк (401), пробуем обновить и повторить запрос
            if response.status_code == 401:
                await self.refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs
                )
            
            response.raise_for_status()
            return response
    
    async def get_leads(self, limit: int = 50, page: int = 1):
        """
        Получение списка лидов.
        """
        response = await self.api_request(
            "GET",
            "/leads",
            params={"limit": limit, "page": page}
        )
        return response.json()
    
    async def create_lead(self, lead_data: dict):
        """
        Создание лида.
        """
        response = await self.api_request(
            "POST",
            "/leads",
            json=[lead_data]  # amoCRM ожидает массив
        )
        return response.json()
    
    async def get_catalogs(self):
        """
        Получение списка каталогов.
        """
        response = await self.api_request("GET", "/catalogs")
        return response.json()
    
    async def get_catalog_elements(self, catalog_id: int, limit: int = 250):
        """
        Получение элементов каталога.
        """
        response = await self.api_request(
            "GET",
            f"/catalogs/{catalog_id}/elements",
            params={"limit": limit}
        )
        return response.json()

# Использование
async def main():
    api = AmoCRMAPI()
    
    # Получение лидов (токен обновится автоматически, если нужно)
    leads_data = await api.get_leads(limit=10)
    leads = leads_data.get("_embedded", {}).get("leads", [])
    print(f"Найдено лидов: {len(leads)}")
    
    # Получение каталогов
    catalogs_data = await api.get_catalogs()
    catalogs = catalogs_data.get("_embedded", {}).get("catalogs", [])
    print(f"Найдено каталогов: {len(catalogs)}")
    
    # Создание лида
    new_lead = await api.create_lead({
        "name": "Новый лид от API",
        "price": 0
    })
    print(f"Создан лид: {new_lead}")

# import asyncio
# asyncio.run(main())
```

### Пример 5: Использование в FastAPI приложении

```python
from fastapi import FastAPI, HTTPException
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

app = FastAPI()

# Глобальный объект для работы с amoCRM API
amocrm_api = None

def get_amocrm_api():
    """
    Получает или создаёт клиент amoCRM API.
    """
    global amocrm_api
    if amocrm_api is None:
        amocrm_api = AmoCRMAPI()  # Используем класс из примера выше
    return amocrm_api

@app.get("/api/leads")
async def get_leads(limit: int = 50, page: int = 1):
    """
    Эндпоинт для получения лидов из amoCRM.
    """
    try:
        api = get_amocrm_api()
        leads_data = await api.get_leads(limit=limit, page=page)
        return leads_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/leads")
async def create_lead(lead_data: dict):
    """
    Эндпоинт для создания лида в amoCRM.
    """
    try:
        api = get_amocrm_api()
        result = await api.create_lead(lead_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/catalogs")
async def get_catalogs():
    """
    Эндпоинт для получения каталогов из amoCRM.
    """
    try:
        api = get_amocrm_api()
        catalogs_data = await api.get_catalogs()
        return catalogs_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Пример 6: Использование в n8n через HTTP Request ноду

Если вы используете n8n, токены из `.env` можно использовать через переменные окружения:

**Настройка HTTP Request ноды в n8n:**

```
Method: GET
URL: https://{{$env.AMOCRM_SUBDOMAIN}}.amocrm.ru/api/v4/leads
Headers:
  Authorization: Bearer {{$env.AMOCRM_ACCESS_TOKEN}}
  Content-Type: application/json
Query Parameters:
  limit: 50
  page: 1
```

**Или через credentials в n8n:**

1. Создайте credentials в n8n с типом "Generic Credential Type"
2. Добавьте поля:
   - `subdomain` (текст)
   - `accessToken` (текст, секретное)
3. Используйте в HTTP Request:
   ```
   URL: https://{{$credentials.amocrm.subdomain}}.amocrm.ru/api/v4/leads
   Headers:
     Authorization: Bearer {{$credentials.amocrm.accessToken}}
   ```

## Пример клиента amoCRM с автоматическим обновлением токенов

```python
import httpx
import os
from datetime import datetime, timedelta
from typing import Optional
import json

class AmoCRMClient:
    def __init__(
        self,
        subdomain: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None
    ):
        self.subdomain = subdomain
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.base_url = f"https://{subdomain}.amocrm.ru/api/v4"
    
    async def _ensure_valid_token(self):
        """
        Проверяет и обновляет токен, если он истёк.
        """
        if not self.access_token:
            raise ValueError("Access token not set. Please authorize first.")
        
        # Проверяем, нужно ли обновить токен (за 5 минут до истечения)
        if self.token_expires_at and datetime.now() >= self.token_expires_at - timedelta(minutes=5):
            await self.refresh_token()
    
    async def refresh_token(self):
        """
        Обновляет access token через refresh token.
        """
        if not self.refresh_token:
            raise ValueError("Refresh token not set. Please re-authorize.")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{self.subdomain}.amocrm.ru/oauth2/access_token",
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "redirect_uri": self.redirect_uri
                }
            )
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            expires_in = data.get("expires_in", 86400)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        Выполняет запрос к API с автоматическим обновлением токена.
        """
        await self._ensure_valid_token()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            
            # Если токен истёк, пробуем обновить и повторить запрос
            if response.status_code == 401:
                await self.refresh_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    **kwargs
                )
            
            response.raise_for_status()
            return response
    
    async def get_leads(self, limit: int = 50, page: int = 1):
        """
        Получение списка лидов.
        """
        response = await self._request(
            "GET",
            "/leads",
            params={"limit": limit, "page": page}
        )
        return response.json()
    
    async def get_catalogs(self):
        """
        Получение списка каталогов.
        """
        response = await self._request("GET", "/catalogs")
        return response.json()
    
    async def get_catalog_elements(self, catalog_id: int, limit: int = 250):
        """
        Получение элементов каталога.
        """
        response = await self._request(
            "GET",
            f"/catalogs/{catalog_id}/elements",
            params={"limit": limit}
        )
        return response.json()
    
    async def create_lead(self, lead_data: dict):
        """
        Создание лида.
        """
        response = await self._request(
            "POST",
            "/leads",
            json=[lead_data]  # amoCRM ожидает массив
        )
        return response.json()
    
    def save_tokens_to_env_file(self, env_file_path: str = ".env"):
        """
        Сохраняет токены в .env файл (для удобства разработки).
        """
        env_lines = []
        if os.path.exists(env_file_path):
            with open(env_file_path, "r") as f:
                env_lines = f.readlines()
        
        # Обновляем или добавляем токены
        tokens_updated = False
        new_lines = []
        for line in env_lines:
            if line.startswith("AMOCRM_ACCESS_TOKEN="):
                new_lines.append(f"AMOCRM_ACCESS_TOKEN={self.access_token}\n")
                tokens_updated = True
            elif line.startswith("AMOCRM_REFRESH_TOKEN="):
                new_lines.append(f"AMOCRM_REFRESH_TOKEN={self.refresh_token}\n")
                tokens_updated = True
            elif line.startswith("AMOCRM_TOKEN_EXPIRES_AT="):
                new_lines.append(f"AMOCRM_TOKEN_EXPIRES_AT={self.token_expires_at.isoformat()}\n")
                tokens_updated = True
            else:
                new_lines.append(line)
        
        if not tokens_updated:
            new_lines.append(f"AMOCRM_ACCESS_TOKEN={self.access_token}\n")
            new_lines.append(f"AMOCRM_REFRESH_TOKEN={self.refresh_token}\n")
            new_lines.append(f"AMOCRM_TOKEN_EXPIRES_AT={self.token_expires_at.isoformat()}\n")
        
        with open(env_file_path, "w") as f:
            f.writelines(new_lines)

# Пример использования
async def main():
    # Инициализация клиента
    client = AmoCRMClient(
        subdomain=os.getenv("AMOCRM_SUBDOMAIN"),
        client_id=os.getenv("AMOCRM_CLIENT_ID"),
        client_secret=os.getenv("AMOCRM_CLIENT_SECRET"),
        redirect_uri=os.getenv("AMOCRM_REDIRECT_URI"),
        access_token=os.getenv("AMOCRM_ACCESS_TOKEN"),
        refresh_token=os.getenv("AMOCRM_REFRESH_TOKEN")
    )
    
    # Получение каталогов
    catalogs = await client.get_catalogs()
    print(f"Найдено каталогов: {len(catalogs.get('_embedded', {}).get('catalogs', []))}")
    
    # Получение лидов
    leads = await client.get_leads(limit=10)
    print(f"Найдено лидов: {len(leads.get('_embedded', {}).get('leads', []))}")
```

## Интеграция с n8n

Если вы используете n8n для оркестрации, можно настроить OAuth2 через встроенные ноды:

### Вариант 1: n8n-node-amocrm

1. Установите community node: `n8n-nodes-amocrm`
2. В настройках ноды укажите:
   - **Subdomain**: ваш поддомен amoCRM
   - **Client ID**: из настроек интеграции
   - **Client Secret**: из настроек интеграции
   - **Redirect URI**: URL для callback (n8n может предоставить свой)
3. При первом использовании n8n откроет окно авторизации

### Вариант 2: HTTP Request + OAuth2 API нода

1. Используйте встроенный **OAuth2 API** нод для получения токена
2. Используйте **HTTP Request** нод для всех API вызовов:
   ```
   URL: https://{{$credentials.amocrm.subdomain}}.amocrm.ru/api/v4/leads
   Method: GET
   Headers:
     Authorization: Bearer {{$credentials.amocrm.accessToken}}
   ```

## Безопасность

### ✅ Рекомендации

1. **Никогда не коммитьте токены в Git**
   - Используйте `.env` файлы
   - Добавьте `.env` в `.gitignore`

2. **Храните токены в безопасном месте**
   - Для продакшена: используйте секреты (Kubernetes Secrets, AWS Secrets Manager, etc.)
   - Для разработки: `.env` файл (не коммитить)

3. **Регулярно обновляйте токены**
   - Access Token обновляется автоматически через Refresh Token
   - Refresh Token может истечь — нужно будет переавторизоваться

4. **Используйте минимально необходимые права**
   - При создании интеграции выберите только те права, которые действительно нужны

5. **Мониторинг использования API**
   - amoCRM имеет лимиты на количество запросов
   - Следите за rate limits в ответах API

## Лимиты API amoCRM

- **Rate Limit**: обычно 7 запросов в секунду на аккаунт
- **Batch Requests**: до 50 объектов за один запрос (для создания/обновления)
- **Pagination**: максимум 250 записей за один запрос (для получения списков)

## Полезные ссылки

- [Документация API amoCRM](https://www.amocrm.ru/developers/content/api/account)
- [OAuth2 в amoCRM](https://www.amocrm.ru/developers/content/oauth/step-by-step)
- [Примеры запросов](https://www.amocrm.ru/developers/content/api/leads)

## Чек-лист настройки

- [ ] Создана интеграция в amoCRM
- [ ] Получены Client ID и Client Secret
- [ ] Настроен Redirect URI
- [ ] Выбраны необходимые права доступа
- [ ] Выполнена первичная авторизация
- [ ] Получены Access Token и Refresh Token
- [ ] Токены сохранены в `.env` (или в системе секретов)
- [ ] `.env` добавлен в `.gitignore`
- [ ] Реализована логика автоматического обновления токенов
- [ ] Протестированы основные API запросы

