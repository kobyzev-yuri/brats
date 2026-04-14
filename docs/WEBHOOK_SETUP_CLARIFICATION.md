# Уточнение по настройке Webhook для Яндекс.Метрики

## ❌ Важно: Яндекс.Метрика НЕ предоставляет webhook

**Яндекс.Метрика не имеет встроенного механизма webhook** для отправки событий в реальном времени на внешние серверы (в отличие от некоторых других сервисов).

## ✅ Как получить данные в реальном времени

### Вариант 1: Realtime API (Polling) - Рекомендуется

**Как работает:**
- Нейроаналитик периодически опрашивает Realtime API Яндекс.Метрики
- Интервал: каждые 30-60 секунд
- **Не требует настройки на стороне заказчика**

**API Endpoint:**
```
GET https://api-metrika.yandex.net/management/v1/counter/{counter_id}/realtime
```

**Что нужно от заказчика:**
- ✅ OAuth токен с правами `metrika:read`
- ✅ Counter ID: `103165578` (уже известен)

**Настройка:**
- Создать OAuth-приложение на [oauth.yandex.ru](https://oauth.yandex.ru/)
- Получить OAuth токен
- **Никаких настроек в кабинете Метрики не требуется!**

**Пример кода:**
```python
from integrations.yandex_metrika import YandexMetrikaClient

async def monitor_realtime():
    client = YandexMetrikaClient()
    
    while True:
        visitors = await client.get_realtime_visitors()
        # Анализ и обработка
        await asyncio.sleep(30)  # Каждые 30 секунд
```

---

### Вариант 2: Webhook от сайта (альтернативный)

**Как работает:**
- На стороне сайта (Tilda) добавляется JavaScript код
- При действиях пользователя события отправляются в n8n webhook
- n8n обрабатывает события и может дополнять данными из Метрики

**Что нужно от заказчика:**
- ✅ Доступ к редактированию кода сайта (Tilda)
- ✅ Добавить JavaScript код для отправки событий

**JavaScript код для сайта:**

Полный код для интеграции находится в [`site-integration/SITE_INTEGRATION_CODE.md`](../site-integration/SITE_INTEGRATION_CODE.md).

Пример отправки события:
```javascript
// Отправка события в n8n при клике по телефону
document.querySelector('a[href^="tel:"]').addEventListener('click', function() {
    fetch('https://your-n8n-domain.com/webhook/sales-agent-kb', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            message: 'Пользователь кликнул по телефону',
            channel: 'site',
            external_id: getVisitorId(),
            metadata: {
                event_type: 'phone_click',
                phone_number: this.getAttribute('href').replace('tel:', ''),
                timestamp: new Date().toISOString()
            }
        })
    });
});
```

**Плюсы:**
- Мгновенная отправка событий (< 1 секунда)
- Можно отправлять кастомные события
- Не зависит от API Метрики

**Минусы:**
- Требует изменения кода на сайте
- Нужен публичный URL для n8n
- Дублирование событий (и в Метрику, и в n8n)

---

### Вариант 3: Комбинированный подход (рекомендуется для MVP)

**Как работает:**
1. Используем Realtime API для получения базовых данных о посетителях
2. На критических страницах (формы, калькулятор) добавляем JavaScript для мгновенной отправки событий
3. n8n объединяет данные из обоих источников

**Преимущества:**
- Не требует полной переделки сайта
- Критические события приходят мгновенно
- Остальные события через Realtime API

---

## 📋 Что нужно от заказчика

### Минимальный вариант (только Realtime API):

✅ **НЕ требуется настройка webhook в кабинете Яндекс.Метрики**

✅ **Нужно только:**
1. Создать OAuth-приложение на oauth.yandex.ru (один раз)
2. Получить OAuth токен с правами `metrika:read`
3. Предоставить токен для интеграции

**Никаких настроек в кабинете Метрики не требуется!**

### Расширенный вариант (с webhook от сайта):

✅ **Требуется:**
1. Доступ к редактированию кода сайта (Tilda)
2. Добавить JavaScript код для отправки событий (см. [`site-integration/SITE_INTEGRATION_CODE.md`](../site-integration/SITE_INTEGRATION_CODE.md))
3. Настроить публичный URL для n8n webhook

---

## 🔧 Настройка OAuth-приложения (один раз)

### Шаг 1: Создание приложения

1. Перейти на [oauth.yandex.ru](https://oauth.yandex.ru/)
2. Войти в аккаунт Яндекс
3. Нажать **"Создать новое приложение"**
4. Заполнить форму:
   - **Название**: "Нейроаналитик"
   - **Платформы**: "Веб-сервисы"
   - **Redirect URI**: `http://localhost:8000/auth/yandex/callback` (для разработки)
   - **Права доступа**: `metrika:read`
5. Сохранить и скопировать **Client ID** и **Client Secret**

### Шаг 2: Получение токена

1. Перейти по ссылке авторизации:
```
https://oauth.yandex.ru/authorize?
  response_type=code&
  client_id={client_id}&
  redirect_uri={redirect_uri}
```

2. После авторизации получить `code` из callback URL

3. Обменять `code` на OAuth токен (см. [`YANDEX_METRIKA_API_SETUP.md`](./YANDEX_METRIKA_API_SETUP.md))

### Шаг 3: Использование токена

Токен используется для всех запросов к API:
```python
headers = {"Authorization": f"OAuth {oauth_token}"}
```

---

## ❓ FAQ

**Q: Нужно ли настраивать webhook в кабинете Яндекс.Метрики?**  
A: **Нет**, Яндекс.Метрика не предоставляет такой функционал. Используется Realtime API через polling.

**Q: Что нужно от заказчика для начала работы?**  
A: Только OAuth токен с правами `metrika:read`. Никаких настроек в кабинете Метрики не требуется.

**Q: Можно ли получать события в реальном времени?**  
A: Да, через Realtime API (опрос каждые 30-60 секунд) или через webhook от сайта (мгновенно).

**Q: Нужен ли доступ к редактированию сайта?**  
A: Для базового варианта (Realtime API) - **нет**. Для расширенного (webhook от сайта) - **да**.

**Q: Какая задержка у Realtime API?**  
A: Обычно 1-2 минуты. Для критических событий лучше использовать webhook от сайта.

---

## 🔗 Связанные документы

- [`YANDEX_METRIKA_API_SETUP.md`](./YANDEX_METRIKA_API_SETUP.md) — подробная инструкция по настройке OAuth
- [`ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md`](./ONLINE_ANALYTICS_TRIGGER_SALES_AGENT.md) — активация нейропродажника
- [`MINIMAL_SETUP_REQUIREMENTS.md`](./MINIMAL_SETUP_REQUIREMENTS.md) — минимальные требования

---

**Последнее обновление:** 2025-02-07


