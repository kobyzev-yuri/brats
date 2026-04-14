# Исправление проблемы входа в n8n

## Проблема

Не можете войти в n8n, хотя он запущен. Возможные причины:

1. **Basic Auth включен**, но переменные `N8N_BASIC_AUTH_USER` и `N8N_BASIC_AUTH_PASSWORD` не передаются в контейнер
2. **Пользователь уже создан** в базе данных с другими данными
3. **Несоответствие** между данными в `config.env` и реальными учетными данными

## Решение 1: Использовать Basic Auth из config.env (если включен)

Если в `config.env` указано:
```bash
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=yuri.kobyzev@mail.ru
N8N_BASIC_AUTH_PASSWORD=Loriskeld57&
```

1. **Обновите docker-compose.yml** (уже исправлено - переменные Basic Auth добавлены)
2. **Перезапустите n8n**:
   ```bash
   cd /projects/brats/n8n
   docker-compose down
   docker-compose up -d
   ```
3. **Войдите используя Basic Auth**:
   - При запросе логина/пароля в браузере введите:
     - **Username**: `yuri.kobyzev@mail.ru`
     - **Password**: `Loriskeld57&`

## Решение 2: Отключить Basic Auth и использовать первого пользователя

Если хотите отключить Basic Auth и использовать обычную авторизацию:

1. **Отредактируйте `config.env`**:
   ```bash
   N8N_BASIC_AUTH_ACTIVE=false
   ```

2. **Добавьте/обновите переменные первого пользователя**:
   ```bash
   N8N_USER_FIRST_NAME=Admin
   N8N_USER_LAST_NAME=User
   N8N_USER_EMAIL=admin@brats.local
   N8N_USER_PASSWORD=124
   ```

3. **Сбросьте базу данных** (если пользователь уже создан):
   ```bash
   docker stop n8n-brats
   docker rm n8n-brats
   docker volume rm n8n_n8n_data  # Удалить volume с данными
   # ИЛИ удалить локальную директорию:
   # rm -rf ~/.n8n/database.sqlite
   ```

4. **Перезапустите n8n**:
   ```bash
   cd /projects/brats/n8n
   docker-compose up -d
   ```

5. **Войдите используя**:
   - **Email**: `admin@brats.local`
   - **Password**: `124`

## Решение 3: Сброс базы данных и создание нового пользователя

Если забыли пароль или хотите начать заново:

1. **Остановите n8n**:
   ```bash
   docker stop n8n-brats
   docker rm n8n-brats
   ```

2. **Удалите данные n8n** (⚠️ **ВНИМАНИЕ**: это удалит все workflows и настройки!):
   ```bash
   # Вариант 1: Удалить volume (если используете docker-compose)
   docker volume rm n8n_n8n_data
   
   # Вариант 2: Удалить локальную директорию (если используете start_n8n.sh)
   rm -rf ~/.n8n/database.sqlite
   ```

3. **Настройте `config.env`**:
   ```bash
   N8N_BASIC_AUTH_ACTIVE=false
   N8N_USER_EMAIL=admin@brats.local
   N8N_USER_PASSWORD=124
   ```

4. **Запустите n8n заново**:
   ```bash
   cd /projects/brats/n8n
   docker-compose up -d
   # ИЛИ
   ./start_n8n.sh
   ```

5. **Войдите** используя данные из `config.env`

## Проверка текущих настроек

```bash
# Проверка переменных окружения в контейнере
docker exec n8n-brats env | grep -E "N8N_BASIC_AUTH|N8N_USER" | sort

# Проверка логов
docker logs n8n-brats --tail 50
```

## Быстрое решение (рекомендуется)

Если хотите быстро войти прямо сейчас:

1. **Отключите Basic Auth** в `config.env`:
   ```bash
   N8N_BASIC_AUTH_ACTIVE=false
   ```

2. **Перезапустите n8n**:
   ```bash
   cd /projects/brats/n8n
   docker-compose restart
   ```

3. **Попробуйте войти с**:
   - Email: `admin@example.com` (значение по умолчанию)
   - Password: `changeme` (значение по умолчанию)

Если не работает, значит пользователь уже создан с другими данными - используйте **Решение 3** для сброса базы данных.
