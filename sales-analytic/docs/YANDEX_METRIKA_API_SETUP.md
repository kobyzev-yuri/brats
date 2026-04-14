# Настройка API доступа к Яндекс.Метрике

## Обзор

Для работы с API Яндекс.Метрики необходимо создать OAuth-приложение в Яндекс ID и получить OAuth токен. Яндекс.Метрика использует OAuth2 для авторизации приложений.

## Необходимые параметры

### 1. Данные для создания OAuth-приложения в Яндекс ID

Для начала работы нужно создать OAuth-приложение:

1. **OAuth Token (OAuth токен)**
   - Получается после авторизации пользователя через OAuth2
   - Используется для всех API запросов
   - **Важно**: токен не имеет срока истечения, но может быть отозван пользователем
   - Передаётся в заголовке: `Authorization: OAuth {token}`

2. **Counter ID (ID счётчика)**
   - Это ID вашего счётчика Яндекс.Метрики
   - Находится в настройках счётчика или в URL: `https://metrika.yandex.ru/dashboard?id={counter_id}`
   - Используется в URL всех API запросов: `https://api-metrika.yandex.net/management/v1/counter/{counter_id}/...`

3. **Client ID (ID приложения)**
   - Получается при создании OAuth-приложения в Яндекс ID
   - Используется для получения токена через OAuth2 flow

4. **Client Secret (Секретный ключ)**
   - Получается вместе с Client ID при создании OAuth-приложения
   - **Важно**: хранить в секрете, не коммитить в репозиторий
   - Используется для получения токена

5. **Redirect URI (URI перенаправления)**
   - URL, на который Яндекс перенаправит после авторизации
   - Должен быть зарегистрирован в настройках приложения **и в точности совпадать** с тем, что использует ваше приложение (символ в символ)
   - **Важно:** Яндекс не принимает "голый" IP вида `127.0.0.1` как хост в настройках приложения — используйте `localhost` или доменное имя
   - Примеры:
     - Для локальной разработки: `http://localhost:8000/auth/yandex/callback`
     - Для продакшена: `https://yourdomain.com/auth/yandex/callback`

## Процесс получения токена (OAuth2 Authorization Code Flow)

### Шаг 1: Создание OAuth-приложения в Яндекс ID

1. Перейдите на [Яндекс ID для разработчиков](https://oauth.yandex.ru/)
2. Войдите в свой аккаунт Яндекс
3. Нажмите **"Создать новое приложение"**
4. Заполните форму:
   - **Название**: например, "Нейроаналитик"
   - **Платформы**: выберите **"Веб-сервисы"**
   - На шаге **2 из 4 – Платформы приложений** укажите:
     - **URL, куда направим пользователя после того, как он разрешил или отказал приложению в доступе**  
       Это `redirect_uri`, на который Яндекс вернёт пользователя с кодом авторизации.  
       Примеры:
       - для локальной разработки: `http://localhost:8000/auth/yandex/callback`
       - для продакшена: `https://yourdomain.com/auth/yandex/callback`
     - **Хост страницы, на которой разместится кнопка или виджет авторизации**  
       Это хост вашего фронтенда, где находится кнопка/ссылка "Войти через Яндекс".  
       Примеры:
       - для локальной разработки: `http://localhost:8000`
       - для продакшена: `https://yourdomain.com`
   - **Права доступа**: выберите необходимые права:
     - `metrika:read` — чтение данных из Яндекс.Метрики
     - `metrika:write` — запись данных в Яндекс.Метрику (если нужно)
5. Сохраните приложение
6. Скопируйте **Client ID** и **Client Secret**

> 💡 **Замечания по валидации URL в форме Яндекса**
>
> - В полях нужно указывать **валидные URL с протоколом** (`http://` или `https://`), а не просто домен.
> - Яндекс **не принимает** значение вида `127.0.0.1` как хост — для локальной разработки используйте `http://localhost:8000` и `http://localhost:8000/auth/yandex/callback`.
> - Убедитесь, что в полях **нет пробелов в начале или конце** строки, иначе форма может показывать "Неверное значение поля".
> - `redirect_uri` в настройках приложения и в вашем коде должны совпадать **до символа**, иначе вы получите ошибку при обмене кода на токен.

### Шаг 2: Первичная авторизация (получение кода)

Пользователь должен авторизовать приложение, перейдя по ссылке:

```
https://oauth.yandex.ru/authorize?
  response_type=code&
  client_id={client_id}&
  redirect_uri={redirect_uri}
```

Пример:
```
https://oauth.yandex.ru/authorize?
  response_type=code&
  client_id=1234567890abcdef1234567890abcdef&
  redirect_uri=http://localhost:8000/auth/yandex/callback
```

После авторизации Яндекс перенаправит на `redirect_uri` с параметром `code`:
```
http://localhost:8000/auth/yandex/callback?code=AUTHORIZATION_CODE
```

### Шаг 3: Обмен кода на токен

Используйте полученный `code` для получения токена:

```python
import httpx

async def get_yandex_oauth_token(
    client_id: str,
    client_secret: str,
    authorization_code: str
) -> dict:
    """
    Обмен authorization code на OAuth token.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth.yandex.ru/token",
            data={
                "grant_type": "authorization_code",
                "code": authorization_code,
                "client_id": client_id,
                "client_secret": client_secret
            }
        )
        response.raise_for_status()
        return response.json()
```

Ответ будет содержать:
```json
{
  "access_token": "AQAAAAA1234567890abcdefghijklmnopqrstuvwxyz",
  "token_type": "bearer",
  "expires_in": 31536000,
  "refresh_token": "1:refresh_token_string",
  "scope": "metrika:read"
}
```

**Важно**: 
- `access_token` — это OAuth токен, который используется для всех API запросов
- Токен не имеет срока истечения (или имеет очень длинный срок), но может быть отозван пользователем
- Если токен отозван, нужно будет переавторизоваться

## Хранение конфигурации

### Рекомендуемый формат: `.env` файл

Создайте файл `.env` в корне проекта (не коммитьте его в Git):

```bash
# Яндекс.Метрика Configuration
YANDEX_METRIKA_COUNTER_ID=12345678
YANDEX_METRIKA_OAUTH_TOKEN=AQAAAAA1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcdefghijklmnopqrstuvwxyz

# OAuth приложение (для получения токена)
YANDEX_OAUTH_CLIENT_ID=1234567890abcdef1234567890abcdef
YANDEX_OAUTH_CLIENT_SECRET=abcdef1234567890abcdef1234567890abcdef
YANDEX_OAUTH_REDIRECT_URI=http://localhost:8000/auth/yandex/callback
```

**Примечания:**
- `YANDEX_METRIKA_OAUTH_TOKEN` — это OAuth токен, обычно длиной 50-100 символов
- `YANDEX_METRIKA_COUNTER_ID` — это числовой ID счётчика (обычно 8-10 цифр)
- Токен получается после успешной авторизации через OAuth2
- Токен не имеет срока истечения, но может быть отозван пользователем в настройках Яндекс ID

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

YANDEX_METRIKA_COUNTER_ID = os.getenv("YANDEX_METRIKA_COUNTER_ID")
YANDEX_METRIKA_OAUTH_TOKEN = os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
YANDEX_OAUTH_CLIENT_ID = os.getenv("YANDEX_OAUTH_CLIENT_ID")
YANDEX_OAUTH_CLIENT_SECRET = os.getenv("YANDEX_OAUTH_CLIENT_SECRET")
YANDEX_OAUTH_REDIRECT_URI = os.getenv("YANDEX_OAUTH_REDIRECT_URI")
```

## Практические примеры использования токенов при вызовах API

### Пример 1: Простой запрос с использованием токена из .env

```python
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def get_realtime_visitors_example():
    """
    Получение количества активных посетителей с использованием токена из .env.
    """
    counter_id = os.getenv("YANDEX_METRIKA_COUNTER_ID")
    oauth_token = os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/realtime",
            headers={
                "Authorization": f"OAuth {oauth_token}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        visitors = data.get("data", [])
        print(f"Активных посетителей: {len(visitors)}")
        return visitors

# Использование
# import asyncio
# asyncio.run(get_realtime_visitors_example())
```

### Пример 2: Получение статистики за период

```python
import os
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

async def get_statistics_example():
    """
    Получение статистики за последние 7 дней с использованием токена из .env.
    """
    counter_id = os.getenv("YANDEX_METRIKA_COUNTER_ID")
    oauth_token = os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
    
    date_to = datetime.now()
    date_from = date_to - timedelta(days=7)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/stats/v1/data",
            headers={
                "Authorization": f"OAuth {oauth_token}",
                "Content-Type": "application/json"
            },
            params={
                "date1": date_from.strftime("%Y-%m-%d"),
                "date2": date_to.strftime("%Y-%m-%d"),
                "metrics": "ym:s:visits,ym:s:pageviews,ym:s:users",
                "dimensions": "ym:s:date"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"Статистика за период: {date_from.date()} - {date_to.date()}")
        return data

# Использование
# import asyncio
# asyncio.run(get_statistics_example())
```

### Пример 3: Получение целей (goals)

```python
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def get_goals_example():
    """
    Получение списка целей с использованием токена из .env.
    """
    counter_id = os.getenv("YANDEX_METRIKA_COUNTER_ID")
    oauth_token = os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/goals",
            headers={
                "Authorization": f"OAuth {oauth_token}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        goals = data.get("goals", [])
        print(f"Найдено целей: {len(goals)}")
        return goals

# Использование
# import asyncio
# asyncio.run(get_goals_example())
```

### Пример 4: Полный клиент Яндекс.Метрики с обработкой ошибок

```python
import os
import httpx
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Optional, Dict, List

load_dotenv()

class YandexMetrikaClient:
    def __init__(
        self,
        counter_id: Optional[str] = None,
        oauth_token: Optional[str] = None
    ):
        self.counter_id = counter_id or os.getenv("YANDEX_METRIKA_COUNTER_ID")
        self.oauth_token = oauth_token or os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
        self.base_url = "https://api-metrika.yandex.net/management/v1"
        
        if not self.counter_id:
            raise ValueError("Counter ID not set. Set YANDEX_METRIKA_COUNTER_ID in .env")
        if not self.oauth_token:
            raise ValueError("OAuth token not set. Set YANDEX_METRIKA_OAUTH_TOKEN in .env")
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """
        Выполняет запрос к API с обработкой ошибок.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"OAuth {self.oauth_token}",
            "Content-Type": "application/json"
        })
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            
            # Обработка ошибок
            if response.status_code == 401:
                raise ValueError(
                    "OAuth token is invalid or expired. "
                    "Please re-authorize and update YANDEX_METRIKA_OAUTH_TOKEN in .env"
                )
            elif response.status_code == 403:
                raise ValueError(
                    "Access denied. Check that your OAuth token has 'metrika:read' scope."
                )
            elif response.status_code == 404:
                raise ValueError(f"Counter {self.counter_id} not found.")
            
            response.raise_for_status()
            return response
    
    async def get_realtime_visitors(self) -> List[Dict]:
        """
        Получение количества активных посетителей в реальном времени.
        """
        response = await self._request(
            "GET",
            f"counter/{self.counter_id}/realtime"
        )
        data = response.json()
        return data.get("data", [])
    
    async def get_statistics(
        self,
        date_from: datetime,
        date_to: datetime,
        metrics: List[str] = None,
        dimensions: List[str] = None,
        filters: str = None
    ) -> Dict:
        """
        Получение статистики за период.
        
        Args:
            date_from: Начальная дата
            date_to: Конечная дата
            metrics: Список метрик (например, ["ym:s:visits", "ym:s:pageviews"])
            dimensions: Список измерений (например, ["ym:s:date", "ym:pv:URL"])
            filters: Фильтры в формате API Метрики
        """
        if metrics is None:
            metrics = ["ym:s:visits", "ym:s:pageviews", "ym:s:users"]
        
        params = {
            "date1": date_from.strftime("%Y-%m-%d"),
            "date2": date_to.strftime("%Y-%m-%d"),
            "metrics": ",".join(metrics)
        }
        
        if dimensions:
            params["dimensions"] = ",".join(dimensions)
        
        if filters:
            params["filters"] = filters
        
        response = await self._request(
            "GET",
            f"counter/{self.counter_id}/stats/v1/data",
            params=params
        )
        return response.json()
    
    async def get_goals(self) -> List[Dict]:
        """
        Получение списка целей.
        """
        response = await self._request(
            "GET",
            f"counter/{self.counter_id}/goals"
        )
        data = response.json()
        return data.get("goals", [])
    
    async def get_visits(
        self,
        date_from: datetime,
        date_to: datetime,
        limit: int = 100
    ) -> Dict:
        """
        Получение данных о визитах за период.
        """
        response = await self._request(
            "GET",
            f"counter/{self.counter_id}/stats/v1/data",
            params={
                "date1": date_from.strftime("%Y-%m-%d"),
                "date2": date_to.strftime("%Y-%m-%d"),
                "metrics": "ym:s:visits",
                "dimensions": "ym:s:visitID,ym:s:clientID,ym:pv:URL,ym:pv:title,ym:s:dateTime",
                "limit": limit
            }
        )
        return response.json()
    
    async def create_log_request(
        self,
        date_from: datetime,
        date_to: datetime,
        fields: List[str] = None
    ) -> Dict:
        """
        Создание запроса на экспорт логов (для получения детальных данных).
        
        Примечание: после создания запроса нужно дождаться его обработки
        и затем скачать файл через get_log_request_download.
        """
        if fields is None:
            fields = [
                "ym:s:visitID",
                "ym:s:clientID",
                "ym:pv:URL",
                "ym:pv:title",
                "ym:s:dateTime",
                "ym:s:goalID"
            ]
        
        response = await self._request(
            "POST",
            f"counter/{self.counter_id}/logrequests",
            json={
                "date1": date_from.strftime("%Y-%m-%d"),
                "date2": date_to.strftime("%Y-%m-%d"),
                "fields": fields
            }
        )
        return response.json()
    
    async def get_log_request_status(self, request_id: int) -> Dict:
        """
        Получение статуса запроса на экспорт логов.
        """
        response = await self._request(
            "GET",
            f"counter/{self.counter_id}/logrequest/{request_id}"
        )
        return response.json()
    
    async def get_log_request_download(self, request_id: int) -> bytes:
        """
        Скачивание готового файла с логами.
        """
        response = await self._request(
            "GET",
            f"counter/{self.counter_id}/logrequest/{request_id}/download"
        )
        return response.content

# Использование
async def main():
    client = YandexMetrikaClient()
    
    # Получение активных посетителей
    visitors = await client.get_realtime_visitors()
    print(f"Активных посетителей: {len(visitors)}")
    
    # Получение статистики за последние 7 дней
    date_to = datetime.now()
    date_from = date_to - timedelta(days=7)
    stats = await client.get_statistics(
        date_from=date_from,
        date_to=date_to,
        metrics=["ym:s:visits", "ym:s:pageviews", "ym:s:users"],
        dimensions=["ym:s:date"]
    )
    print(f"Статистика: {stats}")
    
    # Получение целей
    goals = await client.get_goals()
    print(f"Найдено целей: {len(goals)}")

# import asyncio
# asyncio.run(main())
```

### Пример 5: Использование в FastAPI приложении

```python
from fastapi import FastAPI, HTTPException
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

app = FastAPI()

# Глобальный объект для работы с Яндекс.Метрикой API
metrika_client = None

def get_metrika_client():
    """
    Получает или создаёт клиент Яндекс.Метрики API.
    """
    global metrika_client
    if metrika_client is None:
        metrika_client = YandexMetrikaClient()  # Используем класс из примера выше
    return metrika_client

@app.get("/api/metrika/realtime")
async def get_realtime_visitors():
    """
    Эндпоинт для получения активных посетителей из Яндекс.Метрики.
    """
    try:
        client = get_metrika_client()
        visitors = await client.get_realtime_visitors()
        return {"visitors": visitors, "count": len(visitors)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrika/statistics")
async def get_statistics(days: int = 7):
    """
    Эндпоинт для получения статистики за период.
    """
    try:
        client = get_metrika_client()
        date_to = datetime.now()
        date_from = date_to - timedelta(days=days)
        
        stats = await client.get_statistics(
            date_from=date_from,
            date_to=date_to,
            metrics=["ym:s:visits", "ym:s:pageviews", "ym:s:users"],
            dimensions=["ym:s:date"]
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/metrika/goals")
async def get_goals():
    """
    Эндпоинт для получения целей из Яндекс.Метрики.
    """
    try:
        client = get_metrika_client()
        goals = await client.get_goals()
        return {"goals": goals, "count": len(goals)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Пример 6: Сохранение событий из Яндекс.Метрики в analytics_events

```python
import os
import asyncpg
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

async def sync_metrika_events_to_db():
    """
    Синхронизация событий из Яндекс.Метрики в таблицу analytics_events.
    """
    client = YandexMetrikaClient()
    db_url = os.getenv("DATABASE_URL")
    
    # Получение данных за последние 24 часа
    date_to = datetime.now()
    date_from = date_to - timedelta(days=1)
    
    # Получение статистики
    stats = await client.get_statistics(
        date_from=date_from,
        date_to=date_to,
        metrics=["ym:s:visits", "ym:s:pageviews"],
        dimensions=["ym:pv:URL", "ym:s:dateTime"]
    )
    
    # Подключение к БД
    conn = await asyncpg.connect(db_url)
    
    try:
        # Обработка данных из статистики
        for row in stats.get("data", []):
            url = row.get("dimensions", {}).get("ym:pv:URL", {}).get("name", "")
            date_time = row.get("dimensions", {}).get("ym:s:dateTime", {}).get("name", "")
            visits = row.get("metrics", [0])[0]
            
            # Сохранение события
            await conn.execute("""
                INSERT INTO analytics_events (
                    amocrm_lead_id,
                    event_type,
                    event_data,
                    source,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5)
            """,
                None,  # amocrm_lead_id может быть NULL для анонимных посетителей
                "page_view",
                {
                    "url": url,
                    "visits": visits,
                    "timestamp": date_time
                },
                "yandex_metrika",
                datetime.now()
            )
        
        print(f"Синхронизировано событий из Яндекс.Метрики")
    finally:
        await conn.close()

# Использование
# import asyncio
# asyncio.run(sync_metrika_events_to_db())
```

### Пример 7: Использование в n8n через HTTP Request ноду

Если вы используете n8n, токены из `.env` можно использовать через переменные окружения:

**Настройка HTTP Request ноды в n8n:**

```
Method: GET
URL: https://api-metrika.yandex.net/management/v1/counter/{{$env.YANDEX_METRIKA_COUNTER_ID}}/realtime
Headers:
  Authorization: OAuth {{$env.YANDEX_METRIKA_OAUTH_TOKEN}}
  Content-Type: application/json
```

**Или через credentials в n8n:**

1. Создайте credentials в n8n с типом "Generic Credential Type"
2. Добавьте поля:
   - `counterId` (текст)
   - `oauthToken` (текст, секретное)
3. Используйте в HTTP Request:
   ```
   URL: https://api-metrika.yandex.net/management/v1/counter/{{$credentials.yandex_metrika.counterId}}/realtime
   Headers:
     Authorization: OAuth {{$credentials.yandex_metrika.oauthToken}}
   ```

## Безопасность

### ✅ Рекомендации

1. **Никогда не коммитьте токены в Git**
   - Используйте `.env` файлы
   - Добавьте `.env` в `.gitignore`

2. **Храните токены в безопасном месте**
   - Для продакшена: используйте секреты (Kubernetes Secrets, AWS Secrets Manager, etc.)
   - Для разработки: `.env` файл (не коммитить)

3. **Используйте минимально необходимые права**
   - При создании OAuth-приложения выберите только `metrika:read` (если не нужна запись)

4. **Мониторинг использования API**
   - Яндекс.Метрика имеет лимиты на количество запросов
   - Следите за rate limits в ответах API

## Лимиты API Яндекс.Метрики

- **Rate Limit**: обычно 100 запросов в минуту на аккаунт
- **Логи**: запросы на экспорт логов обрабатываются асинхронно (может занять время)
- **Статистика**: максимальный период для одного запроса — 1 год

## Полезные ссылки

- [Документация API Яндекс.Метрики](https://yandex.ru/dev/metrika/)
- [OAuth в Яндекс ID](https://yandex.ru/dev/id/doc/ru/)
- [Справочник API Метрики](https://yandex.ru/dev/metrika/doc/api2/api_v1/intro-docpage/)

## Чек-лист настройки

- [ ] Создано OAuth-приложение в Яндекс ID
- [ ] Получены Client ID и Client Secret
- [ ] Настроен Redirect URI
- [ ] Выбраны необходимые права доступа (`metrika:read`)
- [ ] Выполнена первичная авторизация
- [ ] Получен OAuth Token
- [ ] Получен Counter ID из настроек счётчика
- [ ] Токены сохранены в `.env` (или в системе секретов)
- [ ] `.env` добавлен в `.gitignore`
- [ ] Протестированы основные API запросы






