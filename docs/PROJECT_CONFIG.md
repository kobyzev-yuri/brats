# Конфигурация проекта (свой конфиг на основе окружения)

Краткая справка по конфигурации и работе с GitHub. Подробности — в [PROJECT_INFO.md](../PROJECT_INFO.md).

## Конфиг окружения

| Что | Где |
|-----|-----|
| **Основной конфиг** | `config.env` в корне проекта: `/projects/brats/config.env` |
| **Шаблон** | `config.env.example` — скопировать в `config.env` и заполнить |
| **Источники при нехватке токенов** | Переменные из `~/.bashrc`, `~/keys/n8n_api_key` и т.п. — на их основе заполняют `config.env` в корне brats; `DATABASE_URL` должен указывать на базу `brats`. |

В `config.env` задаются: `DATABASE_URL`, `OPENAI_API_KEY` / `PROXYAPI_KEY`, переменные AmoCRM, n8n, URL сервисов (KB, sales-agent и т.д.). Не коммитить `config.env` в Git (файл в `.gitignore`).

## GitHub и коммиты

- **Репозиторий**: https://github.com/NeuronsUII/Brotherly_hearts_analyst  
- **Рабочая папка для разработки**: `/projects/brats/` — здесь только разработка, коммиты отсюда **не делаются**.  
- **Папка для коммитов**: `/projects/Brotherly_hearts_analyst/Kobyzev_Yuri/` — сюда копируют изменённые файлы из brats, отсюда выполняют `git add`, `git commit`, `git push`.

Работа с GitHub — осторожно, по процессу из PROJECT_INFO.md (копирование в репозиторий → коммит в Kobyzev_Yuri → push).

## Ссылки

- [PROJECT_INFO.md](../PROJECT_INFO.md) — расположение проекта, процесс с Git, актуальное состояние  
- [config.env.example](../config.env.example) — шаблон переменных окружения  
- [db-init/README.md](../db-init/README.md) — инициализация БД (использует `config.env` в корне проекта)
