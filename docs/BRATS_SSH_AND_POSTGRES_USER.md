# Доступ к серверу brats: SSH и PostgreSQL

Краткая инструкция для пользователей. **Пароль для первого входа по SSH выдаётся индивидуально** администратором.

## Параметры сервера

| Что | Значение |
|-----|----------|
| Хост (имя в SSH) | `brats` |
| **IPv4** | `217.177.35.18` |
| Пользователь для работы | `brats` |

Дальше в командах вместо имени хоста можно использовать **IP** — так надёжнее, если DNS не настроен.

---

## 1. Первый вход по паролю

С вашего компьютера (Linux / macOS / WSL):

```bash
ssh brats@217.177.35.18
```

Введите выданный пароль. При запросе про отпечаток ключа хоста — подтвердите (`yes`).

---

## 2. Перенос SSH-ключа (после первого успешного входа)

На **своей машине** сгенерируйте ключ, если его ещё нет:

```bash
ssh-keygen -t ed25519 -C "ваш_email@example.com" -f ~/.ssh/id_ed25519
```

Скопируйте **публичный** ключ на сервер (один раз; дальше вход без пароля):

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub brats@217.177.35.18
```

Проверка:

```bash
ssh brats@217.177.35.18
```

Должно подключаться **без** ввода пароля.

---

## 3. Проверка локального подключения к PostgreSQL

PostgreSQL на сервере слушает только **localhost** — подключаться нужно **после** входа по SSH (или с той же машины через `127.0.0.1`).

Уже на сервере, под пользователем `brats`:

```bash
psql -d brats -c "SELECT version();"
```

Если команда выводит версию PostgreSQL — локальный доступ с сокета работает.

Подключение по TCP с паролем (для скриптов и `DATABASE_URL` на этом же сервере):

```bash
PGPASSWORD=$(cat ~/.pg_password_brats) psql -h 127.0.0.1 -U brats -d brats -c "SELECT current_user, current_database();"
```

Файл `~/.pg_password_brats` есть только у пользователя `brats` на сервере; пароль из него подставляйте в строку подключения приложений:

`postgresql://brats:ПАРОЛЬ@127.0.0.1:5432/brats`

---

## 4. Доступ пользователя `brats` к Qdrant и создание своей KB

Qdrant развернут в Docker на сервере и доступен локально:

- HTTP: `http://127.0.0.1:6333`
- gRPC: `127.0.0.1:6334`
- Контейнер: `qdrant`
- Данные: `/opt/qdrant/storage`

Проверка после SSH-входа под `brats`:

```bash
curl http://127.0.0.1:6333/
docker ps --filter name=qdrant
```

### 4.1 Создать свою коллекцию KB

Пример (эмбеддинги размерности `1024`, метрика `Cosine`):

```bash
curl -X PUT "http://127.0.0.1:6333/collections/kb_brats" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1024,
      "distance": "Cosine"
    }
  }'
```

### 4.2 Загрузить документы (чанки)

```bash
curl -X PUT "http://127.0.0.1:6333/collections/kb_brats/points?wait=true" \
  -H "Content-Type: application/json" \
  -d '{
    "points": [
      {
        "id": 1,
        "vector": [0.01, 0.02, 0.03, 0.04],
        "payload": {
          "text": "Пример текста из KB",
          "source": "manual.pdf",
          "chunk_id": 0
        }
      }
    ]
  }'
```

### 4.3 Поиск по вектору

```bash
curl -X POST "http://127.0.0.1:6333/collections/kb_brats/points/search" \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.01, 0.02, 0.03, 0.04],
    "limit": 5,
    "with_payload": true
  }'
```

---

## 5. Скрипты: GitHub → локально → rsync на brats (Tsapin_Ilya)

В каталоге `scripts/` проекта brats:

| Скрипт | Назначение |
|--------|------------|
| `pull_brotherly_hearts_github.sh` | `git pull` монорепозитория `/projects/Brotherly_hearts_analyst` (ветка `main`). **Только локально**, на GitHub не отправляет ничего. |
| `rsync_tsapin_ilya_to_brats.sh` | Копирование `Tsapin_Ilya/` на `brats@217.177.35.18:~/Brotherly_hearts_analyst/Tsapin_Ilya/`. |
| `sync_tsapin_ilya_to_brats.sh` | Сначала pull, затем rsync (опции `--no-git`, `--dry-run`). |
| `rsync_brotherly_subfolder_to_brats.sh` | Универсальный rsync любой подпапки: `./scripts/rsync_brotherly_subfolder_to_brats.sh Tatiana_Eryukova` (имя с пробелом — в кавычках). |
| `sync_tatiana_eryukova_to_brats.sh` | pull + rsync для `Tatiana_Eryukova`. |

Запуск из корня brats:

```bash
./scripts/sync_tsapin_ilya_to_brats.sh
```

Проверка rsync без записи на сервер: `./scripts/sync_tsapin_ilya_to_brats.sh --dry-run`

Пути и `user@host` можно переопределить переменными окружения (см. комментарии в начале каждого скрипта).

### Sparse-checkout в монорепозитории

Если в `/projects/Brotherly_hearts_analyst` в `ls` видна **только одна** папка (например только `Tsapin_Ilya`), включён **sparse checkout** — остальные каталоги скрыты локально, в GitHub они не удаляются.

Вернуть полное дерево файлов из текущего коммита (безопасно для удалённого репозитория):

```bash
cd /projects/Brotherly_hearts_analyst
git sparse-checkout disable
git checkout HEAD -- .
```

Снова ограничить рабочую копию одной папкой можно командой `git sparse-checkout` — делайте это осознанно, чтобы не удивляться «пропавшим» каталогам.

---

## 6. Docker и Compose на сервере brats

Установлено: **Docker Engine** (`docker.io`) и **Compose v2** (`docker-compose-v2` → команда `docker compose`).

Пользователь **`brats`** добавлен в группу **`docker`** — можно выполнять `docker` и `docker compose` **без `sudo`**.

После первого добавления в группу зайдите на сервер **заново по SSH** (новая сессия), иначе оболочка может не видеть группу `docker`.

Проверка:

```bash
ssh brats@217.177.35.18
docker --version
docker compose version
docker run --rm hello-world
```

Развёртывание из каталога с `docker-compose.yml`:

```bash
docker compose up -d
```

Установка пакетов и правка systemd — по-прежнему через **root** при необходимости.

---

## Замечания

- Доступ к базе **с интернета напрямую** не открыт — только с самого сервера или через туннель SSH при необходимости.
- Смена пароля Linux или проблемы с ключом — к администратору сервера.
