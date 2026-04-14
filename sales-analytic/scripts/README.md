# Скрипты для sales-analytic service

## Описание

Скрипты для автоматизации задач анализа и обогащения базы знаний (KB) на основе данных из `analytics_events`.

## Требования

- Настроенный `config.env` (см. [CONFIGURATION_REFERENCE.md](../../docs/CONFIGURATION_REFERENCE.md))
- Запущенный KB Service (для некоторых скриптов)
- PostgreSQL с таблицами `analytics_events` и `knowledge_base`

## Установка зависимостей

```bash
cd /projects/brats/sales-analytic
pip install -r requirements.txt
```

## Скрипты

### 1. `kb_enrichment.py` - Обогащение KB из analytics_events

**Назначение:** Автоматическое обогащение базы знаний на основе реальных данных о поведении пользователей.

**Что делает:**
- Обнаруживает новые возражения из событий `objection_detected`
- Анализирует популярные вопросы из событий `question_asked`
- Обновляет информацию о продуктах на основе просмотров
- Улучшает скрипты продаж на основе успешных диалогов

**Использование:**

```bash
# Анализ за последние 30 дней (dry-run - только анализ, без изменений)
python scripts/kb_enrichment.py --days 30 --dry-run

# Анализ за последние 7 дней с реальным добавлением в KB
python scripts/kb_enrichment.py --days 7

# Указать другой URL KB Service
KB_API_URL=http://localhost:8001 python scripts/kb_enrichment.py --days 30
```

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)
- `KB_API_URL` - URL KB Service API (по умолчанию `http://localhost:8001`)
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` - для генерации ответов через LLM
- `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` или `HF_MODEL_NAME` - для генерации embeddings

**Примеры:**

```bash
# Только обнаружение новых возражений (dry-run)
python scripts/kb_enrichment.py --days 30 --dry-run

# Полное обогащение за последнюю неделю
python scripts/kb_enrichment.py --days 7
```

**См. также:**
- [ANALYTICS_EVENTS_FOR_KB.md](../docs/ANALYTICS_EVENTS_FOR_KB.md) - подробное описание процесса
- [CONFIGURATION_REFERENCE.md](../../docs/CONFIGURATION_REFERENCE.md) - справочник по конфигурации

---

### 2. `analyze_questions.py` - Анализ популярных вопросов

**Назначение:** Анализ вопросов клиентов и автоматическое добавление ответов в KB.

**Использование:**

```bash
# Анализ за последние 30 дней (dry-run)
python scripts/analyze_questions.py --days 30 --min-frequency 5 --dry-run

# Анализ за последние 7 дней с реальным добавлением в KB
python scripts/analyze_questions.py --days 7 --min-frequency 3
```

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)
- `KB_API_URL` - URL KB Service API
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` - для генерации ответов через LLM
- `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` или `HF_MODEL_NAME` - для генерации embeddings

**См. также:**
- [ANALYTICS_EVENTS_FOR_KB.md](../docs/ANALYTICS_EVENTS_FOR_KB.md) - подробное описание процесса

---

### 3. `update_product_info.py` - Обновление информации о продуктах

**Назначение:** Обновление информации о продуктах в KB на основе аналитики просмотров.

**Использование:**

```bash
# Анализ за последние 30 дней (dry-run)
python scripts/update_product_info.py --days 30 --min-views 10 --dry-run

# Анализ за последние 7 дней с реальным обновлением
python scripts/update_product_info.py --days 7 --min-views 5
```

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)
- `KB_API_URL` - URL KB Service API

**См. также:**
- [ANALYTICS_EVENTS_FOR_KB.md](../docs/ANALYTICS_EVENTS_FOR_KB.md) - подробное описание процесса

---

### 4. `improve_sales_scripts.py` - Улучшение скриптов продаж

**Назначение:** Анализ успешных диалогов и автоматическое улучшение скриптов продаж.

**Использование:**

```bash
# Анализ за последние 30 дней (dry-run)
python scripts/improve_sales_scripts.py --days 30 --dry-run

# Анализ за последние 7 дней с реальным обновлением
python scripts/improve_sales_scripts.py --days 7
```

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)
- `KB_API_URL` - URL KB Service API
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` - для генерации улучшенных скриптов
- `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` или `HF_MODEL_NAME` - для генерации embeddings

**См. также:**
- [ANALYTICS_EVENTS_FOR_KB.md](../docs/ANALYTICS_EVENTS_FOR_KB.md) - подробное описание процесса

---

## Принципы разработки скриптов

1. **Чтение конфигурации из `config.env`** - не использовать хардкод
2. **Использование сервисов** (`EmbeddingService`, `LLMService`) вместо прямых вызовов API
3. **Поддержка dry-run режима** - для тестирования без изменений
4. **Логирование результатов** - понятный вывод о том, что было сделано
5. **Обработка ошибок** - graceful degradation при недоступности сервисов

## Структура скрипта

```python
#!/usr/bin/env python3
"""
Краткое описание скрипта

Использование:
    python scripts/script_name.py [опции]

Конфигурация:
    Скрипт использует переменные из config.env:
    - VAR1 - описание
    - VAR2 - описание

См. также:
    - docs/CONFIGURATION_REFERENCE.md
"""
import asyncio
import argparse
# ... остальные импорты

class ScriptService:
    """Основной класс скрипта"""
    
    def __init__(self, db_pool, dry_run=False):
        self.db = db_pool
        self.dry_run = dry_run
        # Инициализация сервисов
    
    async def main_logic(self):
        """Основная логика скрипта"""
        pass

async def main():
    parser = argparse.ArgumentParser(description="...")
    parser.add_argument("--dry-run", action="store_true", help="...")
    args = parser.parse_args()
    
    # Подключение к БД
    db_pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    
    try:
        service = ScriptService(db_pool, dry_run=args.dry_run)
        await service.main_logic()
    finally:
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Дата создания
2026-02-08

