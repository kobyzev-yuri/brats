# Отчёт по проекту Tatiana_Eryukova (для согласования)

Дата: 26.03.2026  
Сервер: `brats` (`217.177.35.18`)

## Что уже сделано

- Код ветки Татьяны уже есть на сервере:
  - `/home/brats/Brotherly_hearts_analyst/Tatiana_Eryukova`
- Установлена инфраструктурная база для развёртывания:
  - Docker Engine + Compose v2
  - `brats` добавлен в группу `docker`
- Установлены недостающие системные компоненты:
  - `rclone`, `ffmpeg`, `jq`
  - `certbot`, `python3-certbot-nginx`
  - `python3-venv`, `python3-dev`, `pkg-config`, `libpq-dev`
- **Redis (системный):** пакет `redis-server`, сервис включён и запущен; слушает **`127.0.0.1:6379`** (`redis-cli ping` → `PONG`). Для её `docker-compose` обычно поднимается **свой** контейнер `redis` — тогда приложение ходит на `redis:6379` внутри сети compose; системный Redis пригоден для отладки или если переведём конфиг на хост.
- Подготовлен каталог под runtime:
  - `/opt/neuro-analyst` (владелец `brats`) — код синхронизирован с `Tatiana_Eryukova` из репозитория
- Добавлен отдельный nginx-host:
  - `rag.neurostrengths.pro`
  - прокси настроен на `127.0.0.1:18000`
- Настроено использование существующего сертификата `neurostrengths.pro` (без выпуска нового cert).

## Текущее состояние

- **PostgreSQL:** на сервере brats работает **системный** Postgres (`systemd`, слушает **`127.0.0.1:5432`**) — это базы других сервисов проекта. У Татьяны в **`docker-compose.yml`** своя БД — контейнер **`postgres`** (`pgvector/pgvector:pg17`), порт **5432 наружу не пробрасывается**, только внутренняя сеть compose. С хостовым Postgres **портовый конфликт не возникает**. Развёртываем **как у неё в репозитории** — БД в контейнере, volume `postgres_data`; **не** переносим её приложение на общий хостовый Postgres без отдельного решения.
- В серверном **`.env`** в `DATABASE_URL` хост должен быть **`postgres`** (имя сервиса в compose), **не** `localhost` — иначе контейнер `app_server` не попадёт в её Postgres (шаблон `.env.example` рассчитан на локальный запуск без Docker).
- Ранее на **6333/6334** был чужой контейнер **`qdrant`**; он **снят** (stop + rm), порты свободны под Qdrant из её `docker-compose`.
- DNS `rag.neurostrengths.pro` указывает на `217.177.35.18`.
- `nginx -t` успешен, конфиг загружен.
- По `rag` сейчас ожидаемо `502 Bad Gateway`, потому что backend на `127.0.0.1:18000` ещё не запущен.
- SSL-сертификат используется общий с `neurostrengths.pro` (SAN не содержит `rag`, возможны предупреждения браузера при строгой проверке имени).

## Тестовый запуск docker compose (чтобы отловить грубые ошибки)

На сервере `brats` в `/opt/neuro-analyst` провели тестовую проверку инфраструктуры (без запуска `app_server`):

- `docker compose -f docker-compose.yml config` — OK (рендер/валидация compose без ошибок)
- `docker compose -f docker-compose.yml up -d postgres redis qdrant`
  - `postgres` — health `healthy`
  - `redis` — `redis-cli ping` → `PONG`
  - `qdrant` — HTTP `200` на `http://127.0.0.1:6333/`
- `docker compose build app_server` (сборка образа `neuro-analyst:latest`) — успешно

Примечания по сборке (не фатальные, но могут всплыть в отдельных сценариях):
- при установке `openai-whisper` были предупреждения по зависимостям (`numba`/`triton` версии)
- после переустановки `setuptools==68.2.2` pip ругнулся на несоответствие требованиям `grpcio-tools` (но сборка не упала)

## Конкретные предложения для `.env` на brats (Docker Compose)

Файл лежит рядом с `docker-compose.yml` (например `/opt/neuro-analyst/.env`). **Не коммитить.** Пароль для Postgres сгенерировать, например: `openssl rand -base64 24` (если в пароле есть символы `@ : / # %` — в `DATABASE_URL` их нужно [URL-кодировать](https://docs.python.org/3/library/urllib.parse.html#urllib.parse.quote) или использовать пароль без спецсимволов).

**Как это стыкуется с кодом**

- `docker compose` подставляет **`POSTGRES_USER`** / **`POSTGRES_PASSWORD`** в сервис **`postgres`** (БД **`neurocrm_kb`** задана в compose).
- **Knowledge Base** собирает строку подключения из **`.env`** + **`config.ini`** (`[database]` host=`postgres`, `[redis]` host=`redis`, `[qdrant]` host=`qdrant`, mode=`remote`). Достаточно **`POSTGRES_USER`** и **`POSTGRES_PASSWORD`**; хосты уже «как в Docker» в репозитории.
- **`DATABASE_URL`** с хостом **`postgres`** нужен вспомогательным скриптам и модулю **neurosales**, где читается переменная окружения (см. `neurosales/infrastructure/config/settings.py`).
- **`REDIS_URL`** — для **neurosales** (отдельная логика URL); Huey/KB берут Redis из `config.ini` + опционально `REDIS_PASSWORD`.

**Минимальный каркас (подставить свои секреты)**

```env
# ─── PostgreSQL (совпадает с docker-compose и с DATABASE_URL ниже) ───
POSTGRES_USER=neurocrm_kb
POSTGRES_PASSWORD=ЗАМЕНИТЬ_НА_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ

# Тот же логин/пароль/хост/имя БД, что в compose; хост — имя сервиса, не localhost
DATABASE_URL=postgresql+asyncpg://neurocrm_kb:ЗАМЕНИТЬ_НА_ТОТ_ЖЕ_ПАРОЛЬ@postgres:5432/neurocrm_kb

# ─── Redis: в образе redis без пароля — оставить пустым ───
REDIS_PASSWORD=

# neurosales (БД redis 1 по умолчанию у модуля; KB в config.ini использует db=0)
REDIS_URL=redis://redis:6379/1

# ─── Qdrant self-hosted в compose; ключ не нужен ───
QDRANT_API_KEY=

# ─── API и токены (заполнить по необходимости; без них часть функций не заработает) ───
OPENAI_API_KEY=
GIGACHAT_API_KEY=
GIGACHAT_SCOPE=
ANTHROPIC_API_KEY=
HUGGINGFACE_TOKEN=
YANDEX_API_KEY=
YANDEX_FOLDER_ID=

# ─── Безопасность приложения ───
JWT_SECRET_KEY=ЗАМЕНИТЬ_НА_СЛУЧАЙНУЮ_СТРОКУ_32_И_БОЛЕЕ_СИМВОЛОВ
JWT_ALGORITHM=HS256
WEBHOOK_SECRET=

# ─── Telegram (если используются парсер/бот из проекта) ───
TELEGRAM_BOT_TOKEN=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_SESSION_STRING=

# ─── Прочее (опционально) ───
SENTRY_DSN=
SMTP_USERNAME=
SMTP_PASSWORD=
GOOGLE_APPLICATION_CREDENTIALS=
```

После первого `docker compose up -d` проверить, что переменные подхватились: `docker compose exec postgres env | grep POSTGRES` (пароль не светить в логах).

## Что осталось сделать

1. Подготовить серверный `.env` и `config.ini` для проекта Татьяны (см. блок **«Конкретные предложения для `.env`»** выше).
2. Развернуть проект в `/opt/neuro-analyst`:
   - скопировать код из `/home/brats/Brotherly_hearts_analyst/Tatiana_Eryukova`
   - подготовить `storage/`, `models_cache/`, `tg_media/` при необходимости.
3. Запустить compose (Qdrant может занять **6333/6334** на хосте):
   - по политике сервера не публиковать лишние порты наружу без необходимости,
   - сервис приложения держать на `127.0.0.1:18000` под nginx.
4. Проверка после старта:
   - `curl http://127.0.0.1:18000/api/health/ping`
   - `https://rag.neurostrengths.pro`
5. Передать Татьяне эксплуатационные команды:
   - `docker compose ps`
   - `docker compose logs -f app_server`
   - `docker compose logs -f app_worker`

## Важные ограничения (чтобы не ломать общий сервер)

- Не менять существующий боевой блок `neurostrengths.pro`.
- Не трогать действующие базы/контейнеры других студентов без отдельного подтверждения.
- Все действия по проекту Татьяны держать в отдельном каталоге и отдельном nginx-host.
