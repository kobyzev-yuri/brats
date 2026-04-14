# KB Service - Сервис управления базой знаний

## Описание

FastAPI сервис для управления базой знаний (KB) на основе PostgreSQL с pgvector.
Адаптирован из проекта `~/sql4A/` под нужды системы нейропродажника.

## Структура проекта

```
kb-service/
├── api/              # FastAPI endpoints
│   ├── __init__.py
│   └── main.py       # Основной FastAPI app
├── services/         # Бизнес-логика
│   ├── __init__.py
│   ├── kb_service.py      # Сервис работы с KB
│   ├── embedding_service.py  # Генерация embeddings
│   └── chunking_service.py    # Разбиение текста на chunks
├── models/           # Pydantic модели
│   ├── __init__.py
│   ├── requests.py   # Request модели
│   └── responses.py  # Response модели
├── utils/            # Утилиты
│   ├── __init__.py
│   ├── db.py         # Подключение к БД
│   └── text_processing.py  # Обработка текста
├── config.env.example  # Пример конфигурации
└── README.md         # Этот файл
```

## Установка

1. Создать виртуальное окружение:
```bash
cd /projects/brats
python3 -m venv venv
source venv/bin/activate  # или `venv\Scripts\activate` на Windows
```

2. Установить зависимости:
```bash
pip install -r requirements.txt
```

3. Настроить конфигурацию:
```bash
cp kb-service/config.env.example kb-service/config.env
# Отредактировать config.env с вашими настройками
```

4. Убедиться, что PostgreSQL с pgvector развернут:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Запуск

```bash
cd kb-service
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

API будет доступен по адресу: http://localhost:8001
Документация: http://localhost:8001/docs

## Основные функции

- **CRUD операции** с chunks базы знаний
- **Векторный поиск** по KB через pgvector
- **Импорт данных** из файлов (kb_info.txt и др.)
- **Генерация embeddings** через OpenAI API
- **Chunking** текста с умными границами
- **Фильтрация** по метаданным (category, target_audience и т.д.)

## Интеграция с n8n

Сервис предоставляет REST API endpoints для использования в n8n workflows:
- `POST /api/kb/search` - поиск в KB
- `POST /api/kb/add` - добавление chunk
- `GET /api/kb/{id}` - получение chunk
- `PUT /api/kb/{id}` - обновление chunk
- `DELETE /api/kb/{id}` - удаление chunk
- `POST /api/kb/import` - импорт из файла

## Примечания по реализации

- Адаптировано из `~/sql4A/src/` проекта
- Используется та же схема работы с pgvector
- Конфигурация через config.env (как в sql4A)
- Поддержка OpenAI для embeddings (можно переключить на локальные модели)

















