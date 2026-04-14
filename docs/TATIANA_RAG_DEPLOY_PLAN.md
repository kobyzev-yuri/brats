# План развёртывания ветки Tatiana_Eryukova (RAG)

Цель: аккуратно развернуть проект Татьяны на сервере `brats` без поломки текущих сервисов (`neurostrengths.pro`, существующая БД/боты).

## Входные данные

- Код уже на сервере: `/home/brats/Brotherly_hearts_analyst/Tatiana_Eryukova`.
- Runtime-копия: `/opt/neuro-analyst` (синхронизация с `Tatiana_Eryukova`).
- Целевой поддомен: `rag.neurostrengths.pro` (A-запись на `217.177.35.18`).
- В проде уже есть nginx-конфиг для `neurostrengths.pro`, трогать только точечно.

## Что уже сделано

- Установлены Docker и Compose v2; пользователь `brats` в группе `docker`.
- Установлены доп. компоненты для проекта:
  - `rclone`
  - `ffmpeg`
  - `jq`
  - `certbot`, `python3-certbot-nginx`
  - `python3-venv`, `python3-dev`, `pkg-config`, `libpq-dev`
- **Redis (системный):** `redis-server` включён, слушает **`127.0.0.1:6379`** (`redis-cli ping` → `PONG`). В compose проекта обычно свой контейнер `redis`; системный Redis — запасной вариант или отладка.
- Создан каталог под развёртывание: `/opt/neuro-analyst` (владелец `brats`).
- Добавлен nginx server block для `rag.neurostrengths.pro` (прокси на `127.0.0.1:18000`).
- **TLS:** отдельный выпуск сертификата на `rag` через Let’s Encrypt давал `NXDOMAIN`; используется **тот же сертификат**, что у `neurostrengths.pro` (пути в `sites-available` на существующие `fullchain.pem` / `privkey.pem`). Возможны предупреждения браузера, если SAN не включает `rag` — при необходимости расширить cert или выпустить отдельный после стабилизации DNS.
- **DNS** `rag.neurostrengths.pro` → `217.177.35.18` заведён.

## Тестовый запуск docker compose на `brats`

Чтобы отловить грубые ошибки, на `brats` в `/opt/neuro-analyst` прогнали тестовую проверку инфраструктуры (без запуска `app_server`):

- `docker compose -f docker-compose.yml config` — OK (рендер/валидация compose без ошибок)
- `docker compose -f docker-compose.yml up -d postgres redis qdrant`
  - `postgres` — health `healthy`
  - `redis` — `redis-cli ping` → `PONG`
  - `qdrant` — HTTP `200` на `http://127.0.0.1:6333/`
- `docker compose build app_server` (сборка образа `neuro-analyst:latest`) — успешно

Примечания по сборке (не фатальные, но могут всплывать в сценариях с Whisper/зависимостями):
- при установке `openai-whisper` были предупреждения по зависимостям (`numba`/`triton` версии)
- после переустановки `setuptools==68.2.2` pip ругался на несоответствие требованиям `grpcio-tools` (но сборка не упала)

## Текущее состояние и ограничения

- **PostgreSQL:** на brats уже есть **хостовый** Postgres на **`127.0.0.1:5432`**. Стек Татьяны подстраиваем под её **`docker-compose`**: **Postgres в контейнере** (`postgres`, `pgvector/pgvector:pg17`), без публикации **5432** на хост — конфликта с системным Postgres **нет**. В `.env` для контейнеров: `DATABASE_URL` с хостом **`postgres`**, не `localhost`.
- Ранее на **6333/6334** висел чужой контейнер **`qdrant`**; он **остановлен и удалён**, порты свободны для Qdrant из compose Татьяни.
- Сайт `https://rag.neurostrengths.pro` может отдавать **502**, пока приложение не слушает **`127.0.0.1:18000`** (или пока nginx не переключён на фактический порт, например **8000**, после запуска compose).

## Согласованный безопасный план

1. Подготовить runtime в `/opt/neuro-analyst`:
   - актуальный код из `Tatiana_Eryukova`
   - `.env` и `config.ini` под сервер: готовый каркас — в **`Kobyzev_Yuri/docs/Tatiana_Eryukova.md`** (раздел «Конкретные предложения для `.env` на brats»); детали и скрипты — в `Tatiana_Eryukova/DEPLOY.md`
2. Согласовать порты и сервисы:
   - Qdrant из её compose может слушать **6333/6334** на хосте; при новом конфликте — править compose/override, а не держать два Qdrant на одних портах
   - приложение снаружи — только через nginx; внутренний порт приложения и nginx `proxy_pass` должны совпадать
3. Поднять стек через compose (без затрагивания чужих контейнеров).
4. Проверить:
   - `curl -sS http://127.0.0.1:<порт_приложения>/api/health/ping` (или эквивалент из её API)
   - `https://rag.neurostrengths.pro`
5. Передать Татьяне чеклист эксплуатации:
   - где логи (`docker compose logs`)
   - как обновлять код
   - как перезапускать сервисы без `down` на общий сервер

## Риски и аккуратность

- Не изменять существующий `server` для `neurostrengths.pro` кроме отдельного добавления нового host.
- Не трогать существующую рабочую БД/контейнеры без явного подтверждения.
- Все новые сервисы для ветки Татьяны запускать из отдельного каталога и с отдельными именами контейнеров/портов.
