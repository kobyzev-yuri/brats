# KB Admin - Веб-админка для управления Knowledge Base

Веб-интерфейс для управления блоками в PostgreSQL KB с возможностью пометки как неактивные и удаления.

## Установка

1. Установить зависимости:
```bash
pip install -r requirements_admin.txt
```

2. Настроить переменные окружения (создать `.env` файл):
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kb_db
DB_USER=postgres
DB_PASSWORD=password
SECRET_KEY=your-secret-key-here
```

**Для вторичной обработки через Gemini:**
Убедитесь, что `kb-service` установлен и настроен `GEMINI_API_KEY` в `kb-service/config.env`:
```env
GEMINI_API_KEY=your_proxyapi_key_here
GEMINI_BASE_URL=https://api.proxyapi.ru/google
GEMINI_MODEL=gemini-3-pro-preview
```

3. Запустить приложение:
```bash
python kb_admin_app.py
```

4. Открыть в браузере:
```
http://localhost:5000
```

## Функционал

### 1. Список блоков (`/blocks`)
- Просмотр всех блоков с фильтрацией
- Поиск по тексту
- Фильтры: тип, вкладка, статус (активный/неактивный)
- Массовые операции:
  - Пометить выбранные как неактивные
  - Пометить выбранные как активные
  - Вторичная обработка выбранных
  - Удалить выбранные
- Индивидуальные действия для каждого блока

### 2. Дубликаты (`/duplicates`)
- Поиск дубликатов по типу и содержимому
- Автоматическая очистка дубликатов (оставить самый старый)
- Массовые операции с дубликатами

### 3. Статистика (`/statistics`)
- Общая статистика по блокам
- Статистика по типам блоков
- Статистика по вкладкам
- Визуализация процента активных блоков

### 4. Детальная информация (`/blocks/<id>`)
- Просмотр полной информации о блоке
- Изменение статуса
- Вторичная обработка блока
- Удаление блока

### 5. Вторичная обработка (`/reprocess`)
- Выбор блоков для доработки
- Ввод дополнительных инструкций для Gemini
- Автоматическая обработка через Gemini API
- Обновление блоков в KB после обработки
- Примеры инструкций для быстрого выбора

## API Endpoints

### POST `/api/blocks/mark-inactive`
Пометить блоки как неактивные
```json
{
  "block_ids": [45, 46, 47]
}
```

### POST `/api/blocks/mark-active`
Пометить блоки как активные
```json
{
  "block_ids": [45, 46, 47]
}
```

### POST `/api/blocks/delete`
Удалить блоки
```json
{
  "block_ids": [45, 46, 47],
  "create_backup": true
}
```

### POST `/api/duplicates/cleanup`
Автоматическая очистка дубликатов
```json
{
  "block_type": "product_info",
  "keep_oldest": true
}
```

### POST `/api/blocks/reprocess`
Вторичная обработка блоков через Gemini
```json
{
  "block_ids": [45, 46, 47],
  "additional_instructions": "Добавь больше деталей о материалах и технологиях"
}
```

**Ответ:**
```json
{
  "success": true,
  "message": "Обработано блоков: 3 из 3",
  "blocks_count": 3,
  "updated_count": 3,
  "instructions": "Добавь больше деталей о материалах и технологиях"
}
```

## Структура БД

Предполагаемая структура таблицы `kb_blocks`:

```sql
CREATE TABLE kb_blocks (
    id SERIAL PRIMARY KEY,
    block_id VARCHAR(255) UNIQUE NOT NULL,
    block_type VARCHAR(50),
    tab_name VARCHAR(50),
    content TEXT,
    content_hash VARCHAR(64),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_block_type ON kb_blocks(block_type);
CREATE INDEX idx_tab_name ON kb_blocks(tab_name);
CREATE INDEX idx_is_active ON kb_blocks(is_active);
CREATE INDEX idx_content_hash ON kb_blocks(content_hash);
```

## Безопасность

⚠️ **Важно для продакшена:**

1. Изменить `SECRET_KEY` в `.env`
2. Настроить аутентификацию (добавить login/logout)
3. Настроить HTTPS
4. Ограничить доступ по IP или через VPN
5. Добавить логирование действий

## Пример добавления аутентификации

```python
from flask_login import LoginManager, login_required

login_manager = LoginManager()
login_manager.init_app(app)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Реализация логина
    pass

@app.before_request
def require_login():
    if request.endpoint not in ['login', 'static']:
        # Проверка аутентификации
        pass
```

## Развертывание

### Docker

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements_admin.txt .
RUN pip install -r requirements_admin.txt
COPY . .
CMD ["python", "kb_admin_app.py"]
```

### Systemd service

```ini
[Unit]
Description=KB Admin
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/app
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python kb_admin_app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Скриншоты функций

- **Список блоков**: Таблица с фильтрами и массовыми операциями
- **Дубликаты**: Автоматический поиск и очистка
- **Статистика**: Визуализация данных
- **Детали блока**: Полная информация и управление

## Вторичная обработка блоков

Функция вторичной обработки позволяет доработать уже существующие блоки в KB с помощью Gemini.

### Как использовать:

1. **Выберите блоки** в списке блоков (через чекбоксы или на странице деталей)
2. **Нажмите "Вторичная обработка"**
3. **Введите инструкции** - опишите, что нужно изменить/дополнить:
   - "Добавь больше деталей о материалах"
   - "Улучши описание, сделай его более привлекательным"
   - "Добавь информацию о гарантии"
   - "Структурируй текст лучше"
   - "Оптимизируй для SEO"
4. **Отправьте на обработку** - Gemini обработает блоки и обновит их в KB

### Примеры инструкций:

- **Детализация**: "Добавь больше деталей о материалах и технологиях, используемых в отделке"
- **Улучшение текста**: "Улучши описание, сделай его более привлекательным для покупателей"
- **Дополнение**: "Добавь информацию о гарантии и сроках выполнения работ"
- **Структура**: "Структурируй текст лучше, добавь подзаголовки и списки"
- **SEO**: "Добавь ключевые слова для SEO, сохраняя естественность текста"

### Требования:

- Установлен `kb-service` с настроенным `GeminiTextService`
- Настроен `GEMINI_API_KEY` в `kb-service/config.env`
- Блоки должны существовать в KB

## Поддержка

При возникновении проблем проверь:
1. Подключение к PostgreSQL
2. Существование таблицы `kb_blocks`
3. Наличие колонки `is_active`
4. Логи приложения
5. Для вторичной обработки: доступность `kb-service` и `GEMINI_API_KEY`

