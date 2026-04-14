# Настройка config.env для n8n

## Создание config.env

1. Скопируйте пример конфигурации:
```bash
cd /projects/brats
cp config.env.example config.env
```

2. Отредактируйте `config.env` и укажите реальные значения:
```bash
nano config.env
# или
vim config.env
```

## Настройки n8n в config.env

```bash
# n8n Configuration
N8N_URL=http://localhost:5678
N8N_PROTOCOL=http
N8N_HOST=0.0.0.0
N8N_PORT=5678

# Аутентификация n8n
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=changeme  # ⚠️ ИЗМЕНИТЕ ПАРОЛЬ!

# Webhook URL для n8n
N8N_WEBHOOK_URL=http://localhost:5678/
```

## Использование config.env

### С docker-compose

`docker-compose.yml` автоматически загружает переменные из `../config.env`:
```bash
cd /projects/brats/n8n
docker-compose up -d
```

### С start_n8n.sh

Скрипт `start_n8n.sh` также загружает переменные из `../config.env`:
```bash
cd /projects/brats/n8n
./start_n8n.sh
```

## Безопасность

⚠️ **ВАЖНО**: 
- Файл `config.env` находится в `.gitignore` и не будет закоммичен в git
- Не храните реальные пароли в `config.env.example`
- Для продакшена используйте отдельный `config.env` с безопасными паролями

## Проверка настроек

После создания `config.env` и запуска n8n, проверьте:
```bash
# Проверка, что n8n использует настройки из config.env
docker exec n8n-brats env | grep N8N
```

Должны отображаться значения из вашего `config.env`.
















