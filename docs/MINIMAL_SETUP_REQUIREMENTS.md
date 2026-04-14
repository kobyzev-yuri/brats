# Минимальные требования для начала работы

## ✅ Что нужно для старта

### 1. Яндекс.Метрика (для нейроаналитики)

**Минимально необходимо:**
- ✅ **OAuth токен** с правами `metrika:read`
- ✅ **Counter ID**: `103165578` (уже известен для сайта innovatory-club.ru)

**Для получения токена (первичная настройка):**
- Client ID (ID OAuth-приложения)
- Client Secret (секретный ключ)
- Redirect URI (URL для callback)

**Где получить:**
1. Создать OAuth-приложение на [oauth.yandex.ru](https://oauth.yandex.ru/)
2. Выбрать права: `metrika:read`
3. Получить токен через OAuth2 flow (см. [`YANDEX_METRIKA_API_SETUP.md`](./YANDEX_METRIKA_API_SETUP.md))

**Переменные окружения:**
```bash
YANDEX_METRIKA_COUNTER_ID=103165578
YANDEX_METRIKA_OAUTH_TOKEN=AQAAAAA...  # OAuth токен
```

---

### 2. amoCRM (для работы с лидами и сделками)

**Минимально необходимо:**
- ✅ **Access Token** (токен доступа)
- ✅ **Refresh Token** (токен обновления)
- ✅ **Subdomain** (поддомен вашего аккаунта amoCRM)

**Для получения токенов (первичная настройка):**
- Client ID (ID интеграции)
- Client Secret (секретный ключ)
- Redirect URI (URL для callback)

**Где получить:**
1. Создать интеграцию в amoCRM: Настройки → Интеграции → Создать интеграцию
2. Выбрать права: `leads`, `contacts`, `catalogs`, `notes`, `tasks`, `companies`
3. Получить токены через OAuth2 flow (см. [`AMOCRM_API_SETUP.md`](./AMOCRM_API_SETUP.md))

**Важно:**
- Access Token живет **24 часа**, нужно обновлять через Refresh Token
- Refresh Token живет **30 дней** (или больше)
- Нужна автоматическая логика обновления токенов

**Переменные окружения:**
```bash
AMOCRM_SUBDOMAIN=yourcompany  # поддомен вашего аккаунта
AMOCRM_ACCESS_TOKEN=eyJ0eXAi...  # Access Token
AMOCRM_REFRESH_TOKEN=def50200...  # Refresh Token
AMOCRM_CLIENT_ID=12345678-1234-1234-1234-123456789012
AMOCRM_CLIENT_SECRET=abcdef...
```

---

### 3. LLM (для нейропродажника) - опционально на старте

**Варианты:**
- **GigaChat** (рекомендуется для 152-ФЗ)
- **YandexGPT** (альтернатива)
- **Локальные модели** (Llama, Mistral)

**Для GigaChat:**
```bash
GIGACHAT_CLIENT_ID=***
GIGACHAT_CLIENT_SECRET=***
GIGACHAT_SCOPE=GIGACHAT_API_PERS
```

**Для YandexGPT:**
```bash
YANDEX_GPT_API_KEY=***
```

**Примечание:** Можно начать без LLM, используя mock-ответы для тестирования интеграций.

---

### 4. Инфраструктура

**Обязательно:**
- ✅ **PostgreSQL** (база данных)
- ✅ **Redis** (кэш и очереди)
- ✅ **n8n** (оркестратор workflow)

**Переменные окружения:**
```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_DB=brats
POSTGRES_USER=brats
POSTGRES_PASSWORD=***

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# n8n
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=***
```

---

## 📋 Чеклист для начала работы

### Этап 1: Получение токенов (обязательно)

- [ ] **Яндекс.Метрика:**
  - [ ] Создать OAuth-приложение на oauth.yandex.ru
  - [ ] Получить OAuth токен с правами `metrika:read`
  - [ ] Сохранить токен в `.env`: `YANDEX_METRIKA_OAUTH_TOKEN`
  - [ ] Указать Counter ID: `YANDEX_METRIKA_COUNTER_ID=103165578`

- [ ] **amoCRM:**
  - [ ] Создать интеграцию в amoCRM
  - [ ] Получить Access Token и Refresh Token
  - [ ] Сохранить в `.env`: `AMOCRM_ACCESS_TOKEN`, `AMOCRM_REFRESH_TOKEN`
  - [ ] Указать Subdomain: `AMOCRM_SUBDOMAIN=yourcompany`
  - [ ] Сохранить Client ID и Secret для обновления токенов

### Этап 2: Настройка инфраструктуры

- [ ] Запустить PostgreSQL
- [ ] Запустить Redis
- [ ] Запустить n8n
- [ ] Проверить подключения

### Этап 3: Тестирование интеграций

- [ ] Протестировать подключение к Яндекс.Метрике (получить данные)
- [ ] Протестировать подключение к amoCRM (получить список лидов)
- [ ] Настроить автоматическое обновление токенов amoCRM

---

## 🚀 Минимальный старт (MVP)

**Для начала работы с нейроаналитикой достаточно:**

1. ✅ OAuth токен Яндекс.Метрики с правами `metrika:read`
2. ✅ Counter ID: `103165578`
3. ✅ PostgreSQL и Redis запущены
4. ✅ n8n запущен

**С этим можно:**
- Получать данные из Яндекс.Метрики
- Анализировать поведение посетителей
- Синхронизировать события в БД
- Генерировать базовые отчеты

**Для полноценной работы с нейропродажником дополнительно нужно:**

5. ✅ Access Token и Refresh Token для amoCRM
6. ✅ Subdomain amoCRM
7. ✅ Токены для LLM (GigaChat/YandexGPT) - или использовать mock

---

## 📝 Пример `.env` файла для старта

```bash
# ============================================
# Минимальная конфигурация для начала работы
# ============================================

# Яндекс.Метрика (ОБЯЗАТЕЛЬНО для нейроаналитики)
YANDEX_METRIKA_COUNTER_ID=103165578
YANDEX_METRIKA_OAUTH_TOKEN=AQAAAAA1234567890abcdefghijklmnopqrstuvwxyz

# amoCRM (ОБЯЗАТЕЛЬНО для нейропродажника)
AMOCRM_SUBDOMAIN=yourcompany
AMOCRM_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGc...
AMOCRM_REFRESH_TOKEN=def50200a1b2c3d4e5f6...
AMOCRM_CLIENT_ID=12345678-1234-1234-1234-123456789012
AMOCRM_CLIENT_SECRET=abcdef1234567890abcdef1234567890abcdef

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_DB=brats
POSTGRES_USER=brats
POSTGRES_PASSWORD=your_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# LLM (опционально, можно начать без этого)
# GIGACHAT_CLIENT_ID=***
# GIGACHAT_CLIENT_SECRET=***
# GIGACHAT_SCOPE=GIGACHAT_API_PERS

# n8n
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=your_secure_password
```

---

## 🔗 Полезные ссылки

- [`YANDEX_METRIKA_API_SETUP.md`](./YANDEX_METRIKA_API_SETUP.md) — подробная инструкция по настройке Яндекс.Метрики
- [`AMOCRM_API_SETUP.md`](./AMOCRM_API_SETUP.md) — подробная инструкция по настройке amoCRM
- [`SITE_ANALYTICS_INTEGRATION_ANALYSIS.md`](./SITE_ANALYTICS_INTEGRATION_ANALYSIS.md) — анализ трекеров сайта

---

## ❓ Часто задаваемые вопросы

**Q: Можно ли начать только с Яндекс.Метрикой, без amoCRM?**  
A: Да, для работы нейроаналитика достаточно только Яндекс.Метрики. amoCRM нужен для нейропродажника.

**Q: Нужен ли LLM токен сразу?**  
A: Нет, можно начать с mock-ответами для тестирования интеграций. LLM нужен для полноценной работы нейропродажника.

**Q: Как часто нужно обновлять токены?**  
A: 
- Яндекс.Метрика: токен не истекает (но может быть отозван)
- amoCRM Access Token: каждые 24 часа (автоматически через Refresh Token)
- amoCRM Refresh Token: каждые 30 дней (нужно переавторизоваться)

**Q: Что делать, если токен отозван?**  
A: Нужно переавторизоваться через OAuth2 flow (см. инструкции в соответствующих документах).

---

**Последнее обновление:** 2025-02-07















