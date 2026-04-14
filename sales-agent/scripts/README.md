# Скрипты для sales-agent service

## Описание

Скрипты для автоматизации задач анализа, тестирования и обслуживания диалогов sales-agent.

## Требования

- Настроенный `config.env` (см. [CONFIGURATION_REFERENCE.md](../../docs/CONFIGURATION_REFERENCE.md))
- PostgreSQL с таблицами `conversations` и `messages`
- Запущенный KB Service (для некоторых скриптов)

## Установка зависимостей

```bash
cd /projects/brats/sales-agent
pip install -r requirements.txt
```

## Созданные скрипты

### ✅ 1. `extract_kb_from_conversations.py` - Извлечение знаний из диалогов

**Назначение:** Автоматическое извлечение полезной информации из успешных диалогов для обогащения KB.

**Что делает:**
- Анализирует успешные диалоги (привели к КП/сделке)
- Извлекает эффективные ответы на вопросы
- Извлекает успешные паттерны обработки возражений
- Улучшает скрипты продаж по этапам FSM
- Добавляет в KB через KB Service API

**Использование:**

```bash
# Анализ за последние 30 дней (dry-run)
python scripts/extract_kb_from_conversations.py --days 30 --min-success-rate 0.7 --dry-run

# Анализ за последние 7 дней с реальным добавлением в KB
python scripts/extract_kb_from_conversations.py --days 7 --min-success-rate 0.8
```

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)
- `KB_API_URL` - URL KB Service API
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` - для LLM
- `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` или `HF_MODEL_NAME` - для embeddings

**См. также:**
- [BUSINESS_PROCESSES.md](../../docs/BUSINESS_PROCESSES.md) - описание FSM состояний
- [sales-analytic/scripts/kb_enrichment.py](../../sales-analytic/scripts/kb_enrichment.py) - аналогичный скрипт для analytics_events

---

### ✅ 2. `test_conversation_flow.py` - Тестирование FSM воронки

**Назначение:** Автоматическое тестирование состояний FSM и переходов между ними.

**Что делает:**
- Тестирует все состояния FSM (GREETING, QUALIFYING, PROPOSAL и т.д.)
- Проверяет корректность переходов между состояниями
- Валидирует схему БД для поддержки FSM
- Проверяет значения состояний в реальных диалогах
- Выявляет недопустимые переходы и застрявшие диалоги

**Использование:**

```bash
# Тестирование всех состояний
python scripts/test_conversation_flow.py --test-all

# Тестирование конкретного состояния
python scripts/test_conversation_flow.py --test-state QUALIFYING

# Подробный вывод
python scripts/test_conversation_flow.py --test-all --verbose
```

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)

**См. также:**
- [BUSINESS_PROCESSES.md](../../docs/BUSINESS_PROCESSES.md) - описание FSM состояний и переходов

---

### ✅ 3. `simulate_conversation.py` - Симуляция диалога

**Назначение:** Симуляция диалога для тестирования без реального клиента.

**Что делает:**
- Создает тестовый диалог в БД
- Отправляет сообщения от имени "клиента"
- Проверяет ответы агента (когда API будет реализован)
- Валидирует переходы состояний FSM
- Поддерживает предопределенные сценарии и интерактивный режим

**Использование:**

```bash
# Запуск сценария обработки возражений
python scripts/simulate_conversation.py --scenario objection_handling

# Интерактивный режим
python scripts/simulate_conversation.py --interactive

# Список доступных сценариев
python scripts/simulate_conversation.py --list-scenarios
```

**Доступные сценарии:**
- `objection_handling` - тестирование обработки возражений
- `qualification` - тестирование квалификации лида
- `proposal_generation` - тестирование генерации КП
- `handoff` - тестирование передачи менеджеру

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)
- `SALES_AGENT_URL` - URL Sales Agent API (когда будет реализован)

**См. также:**
- [BUSINESS_PROCESSES.md](../../docs/BUSINESS_PROCESSES.md) - описание FSM состояний

---

### ✅ 4. `analyze_conversations.py` - Анализ эффективности диалогов

**Назначение:** Анализ завершенных диалогов для выявления паттернов успеха/неудачи.

**Что делает:**
- Анализирует статистику по диалогам (количество, средняя длительность, конверсия)
- Определяет успешные диалоги (привели к КП/сделке)
- Выявляет паттерны успешных сообщений
- Анализирует причины handoff
- Генерирует рекомендации по улучшению

**Использование:**

```bash
# Анализ за последние 30 дней
python scripts/analyze_conversations.py --days 30

# Сохранение отчета в JSON
python scripts/analyze_conversations.py --days 30 --output report.json --format json
```

**Конфигурация:**

Скрипт использует следующие переменные из `config.env`:
- `DATABASE_URL` - подключение к PostgreSQL (обязательно)

**Выходные данные:**
- Статистика по диалогам
- Топ успешных фраз/паттернов
- Причины handoff (частота, категории)
- Рекомендации по улучшению

**См. также:**
- [BUSINESS_PROCESSES.md](../../docs/BUSINESS_PROCESSES.md) - описание процессов

---

## Планируемые скрипты

### Средний приоритет

5. **`monitor_active_conversations.py`** - Мониторинг активных диалогов
6. **`generate_conversation_report.py`** - Генерация отчетов (расширенная версия analyze_conversations)

### Низкий приоритет

7. **`export_conversations.py`** / **`import_conversations.py`** - Экспорт/импорт диалогов
8. **`detect_handoff_patterns.py`** - Обнаружение паттернов handoff
9. **`migrate_conversations.py`** - Миграция данных
10. **`cleanup_old_conversations.py`** - Очистка старых диалогов

## Принципы разработки скриптов

1. **Использование сервисов** - скрипты используют сервисы (`EmbeddingService`, `LLMService`) вместо прямых вызовов API
2. **Чтение конфигурации из `config.env`** - не использовать хардкод
3. **Поддержка dry-run режима** - для тестирования без изменений
4. **Логирование результатов** - понятный вывод о том, что было сделано
5. **Обработка ошибок** - graceful degradation при недоступности сервисов
6. **Соответствие архитектуре** - скрипты следуют архитектуре из `BUSINESS_PROCESSES.md`

## См. также

- [SCRIPTS_ANALYSIS.md](SCRIPTS_ANALYSIS.md) - подробный анализ всех скриптов
- [BUSINESS_PROCESSES.md](../../docs/BUSINESS_PROCESSES.md) - описание бизнес-процессов и FSM
- [sales-analytic/scripts/](../../sales-analytic/scripts/) - примеры скриптов для другого сервиса
- [n8n/workflows/](../../n8n/workflows/) - существующие workflows
- [docs/CONFIGURATION_REFERENCE.md](../../docs/CONFIGURATION_REFERENCE.md) - справочник по конфигурации

