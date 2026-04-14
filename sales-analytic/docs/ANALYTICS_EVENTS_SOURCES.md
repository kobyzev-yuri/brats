# Источники данных для analytics_events

## Важное уточнение

**Яндекс.Метрика НЕ собирает тексты диалогов и возражения клиентов.**

Таблица `analytics_events` получает данные из **нескольких источников**, не только из Яндекс.Метрики.

---

## Источники данных для analytics_events

### 1. Яндекс.Метрика (только события на сайте)

**Что собирает:**
- Просмотры страниц (`page_view`)
- Клики по элементам (`click`)
- Достижение целей (`goal`) — заполнение формы, просмотр каталога
- Время на сайте (`time_on_site`)
- Источник трафика (`source`)

**Что НЕ собирает:**
- ❌ Тексты диалогов
- ❌ Вопросы клиентов
- ❌ Возражения
- ❌ Сообщения в чате

**Пример события из Яндекс.Метрики:**
```json
{
  "event_type": "page_view",
  "event_data": {
    "url": "/catalog/product/123",
    "title": "Коттедж BLACK BOX",
    "source": "yandex_direct",
    "time_on_page": 45
  }
}
```

---

### 2. Диалоги с агентом (таблица `messages`)

**Источник:** Таблица `messages` в PostgreSQL, где хранятся все сообщения в диалогах с Нейропродажником.

**Что собираем:**
- Вопросы клиентов (`question_asked`)
- Возражения (`objection_detected`)
- Сообщения агента и клиента (`conversation_message`)

**Процесс:**
```
Клиент общается с агентом
    ↓
Сообщения сохраняются в messages
    ↓
Анализ сообщений для обнаружения:
    ├─→ Вопросов
    ├─→ Возражений
    └─→ Интересов
    ↓
Создание событий в analytics_events
```

**Пример кода:**

```python
# analytics-service/service/event_processor.py
async def process_conversation_messages(db: asyncpg.Pool):
    """Обработка сообщений из диалогов для создания событий"""
    async with db.acquire() as conn:
        # Получение новых сообщений (ещё не обработанных)
        messages = await conn.fetch("""
            SELECT 
                m.id,
                m.conversation_id,
                m.role,
                m.content,
                m.metadata,
                c.amocrm_lead_id
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.created_at > NOW() - INTERVAL '1 hour'
              AND m.processed_for_analytics = FALSE
        """)
        
        for message in messages:
            # Анализ сообщения клиента
            if message["role"] == "user":
                # Обнаружение вопроса
                if is_question(message["content"]):
                    await conn.execute("""
                        INSERT INTO analytics_events (
                            amocrm_lead_id, event_type, event_data
                        )
                        VALUES ($1, 'question_asked', $2)
                    """,
                        message["amocrm_lead_id"],
                        json.dumps({
                            "conversation_id": message["conversation_id"],
                            "message_id": message["id"],
                            "question": message["content"],
                            "category": detect_question_category(message["content"])
                        })
                    )
                
                # Обнаружение возражения
                if is_objection(message["content"]):
                    await conn.execute("""
                        INSERT INTO analytics_events (
                            amocrm_lead_id, event_type, event_data
                        )
                        VALUES ($1, 'objection_detected', $2)
                    """,
                        message["amocrm_lead_id"],
                        json.dumps({
                            "conversation_id": message["conversation_id"],
                            "message_id": message["id"],
                            "objection": message["content"],
                            "objection_type": detect_objection_type(message["content"])
                        })
                    )
            
            # Помечаем сообщение как обработанное
            await conn.execute("""
                UPDATE messages
                SET processed_for_analytics = TRUE
                WHERE id = $1
            """, message["id"])
```

---

### 3. Примечания в amoCRM (от менеджеров)

**Источник:** Примечания к лидам/сделкам в amoCRM, которые создают менеджеры.

**Что собираем:**
- Резюме диалога с клиентом
- Записанные вопросы клиента
- Записанные возражения
- Результаты переговоров

**Процесс:**
```
Менеджер работает с клиентом
    ↓
Создаёт примечание в amoCRM:
    "Клиент спрашивал про рассрочку,
     беспокоился о сроках строительства"
    ↓
n8n workflow синхронизирует примечания
    ↓
Анализ текста примечания
    ↓
Создание событий в analytics_events
```

**Пример кода:**

```python
# analytics-service/integrations/amocrm.py
async def sync_amocrm_notes(db: asyncpg.Pool, amocrm_client):
    """Синхронизация примечаний из amoCRM и создание событий"""
    # Получение примечаний за последний день
    notes = await amocrm_client.get_notes(
        entity_type="leads",
        date_from=datetime.now() - timedelta(days=1)
    )
    
    async with db.acquire() as conn:
        for note in notes:
            note_text = note.get("text", "")
            lead_id = note.get("entity_id")
            
            # Анализ текста примечания
            # Поиск вопросов и возражений через LLM или паттерны
            
            # Обнаружение вопросов
            questions = extract_questions_from_text(note_text)
            for question in questions:
                await conn.execute("""
                    INSERT INTO analytics_events (
                        amocrm_lead_id, event_type, event_data
                    )
                    VALUES ($1, 'question_asked', $2)
                """,
                    lead_id,
                    json.dumps({
                        "source": "amocrm_note",
                        "note_id": note["id"],
                        "question": question,
                        "note_text": note_text
                    })
                )
            
            # Обнаружение возражений
            objections = extract_objections_from_text(note_text)
            for objection in objections:
                await conn.execute("""
                    INSERT INTO analytics_events (
                        amocrm_lead_id, event_type, event_data
                    )
                    VALUES ($1, 'objection_detected', $2)
                """,
                    lead_id,
                    json.dumps({
                        "source": "amocrm_note",
                        "note_id": note["id"],
                        "objection": objection,
                        "note_text": note_text
                    })
                )
```

**Пример примечания в amoCRM:**
```
Клиент интересовался:
- Можно ли купить в рассрочку?
- Какие сроки строительства?
- Есть ли готовые дома?

Возражения:
- Беспокоится о сроках (хочет быстро)
- Считает цену высокой
```

---

### 4. Чат на сайте (если есть)

**Источник:** Сообщения из чата на сайте (если используется сторонний виджет).

**Что собираем:**
- Вопросы в чате
- Запросы обратного звонка
- Интересы клиентов

**Процесс:**
```
Клиент пишет в чат на сайте
    ↓
Чат отправляет webhook в n8n
    ↓
n8n → analytics-service API
    ↓
Создание события в analytics_events
```

---

### 5. Формы обратной связи

**Источник:** Заполненные формы на сайте (через Яндекс.Метрику цели или напрямую).

**Что собираем:**
- Вопросы в поле "Ваш вопрос"
- Комментарии в формах
- Запросы на консультацию

---

## Полная схема источников данных

```
┌─────────────────────────────────────────────────────────┐
│                  Источники данных                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Яндекс.Метрика                                       │
│     ├─→ page_view (просмотры страниц)                   │
│     ├─→ goal (достижение целей)                         │
│     ├─→ click (клики)                                   │
│     └─→ time_on_site (время на сайте)                   │
│                                                          │
│  2. Диалоги с агентом (messages)                        │
│     ├─→ question_asked (вопросы клиентов)               │
│     ├─→ objection_detected (возражения)                 │
│     └─→ conversation_message (сообщения)                │
│                                                          │
│  3. Примечания в amoCRM (от менеджеров)                │
│     ├─→ question_asked (вопросы из примечаний)          │
│     ├─→ objection_detected (возражения из примечаний)   │
│     └─→ manager_note (резюме диалога)                   │
│                                                          │
│  4. Чат на сайте (если есть)                            │
│     └─→ chat_message (сообщения в чате)                 │
│                                                          │
│  5. Формы обратной связи                                │
│     └─→ form_submit (заполненные формы)                 │
│                                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│              analytics_events (PostgreSQL)                │
│                                                          │
│  Все события из разных источников                       │
│  с метаданными о источнике                              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│         Анализ для обогащения KB                         │
│                                                          │
│  - Обнаружение новых возражений                         │
│  - Анализ популярных вопросов                           │
│  - Обновление скриптов продаж                           │
└─────────────────────────────────────────────────────────┘
```

---

## Обновлённая схема таблицы analytics_events

```sql
CREATE TABLE analytics_events (
    id SERIAL PRIMARY KEY,
    amocrm_lead_id INTEGER,
    event_type VARCHAR(50),  -- 'page_view', 'goal', 'question_asked', 'objection_detected', ...
    event_data JSONB,  -- Детали события
    source VARCHAR(50),  -- 'yandex_metrika', 'agent_conversation', 'amocrm_note', 'site_chat', 'form'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индекс для фильтрации по источнику
CREATE INDEX ON analytics_events (source, event_type);
CREATE INDEX ON analytics_events (amocrm_lead_id, created_at);
```

**Примеры событий из разных источников:**

```json
// Из Яндекс.Метрики
{
  "event_type": "page_view",
  "source": "yandex_metrika",
  "event_data": {
    "url": "/catalog/product/123",
    "source": "yandex_direct"
  }
}

// Из диалога с агентом
{
  "event_type": "question_asked",
  "source": "agent_conversation",
  "event_data": {
    "conversation_id": 456,
    "message_id": 789,
    "question": "Можно ли купить в рассрочку?",
    "category": "pricing"
  }
}

// Из примечания в amoCRM
{
  "event_type": "objection_detected",
  "source": "amocrm_note",
  "event_data": {
    "note_id": 123,
    "objection": "Клиент беспокоится о сроках строительства",
    "objection_type": "delivery_time",
    "note_text": "Клиент интересовался сроками..."
  }
}
```

---

## Процесс сбора данных от менеджеров

### Вариант 1: Автоматический анализ примечаний

```python
# Периодическая задача (n8n cron: каждый час)
async def sync_and_analyze_amocrm_notes():
    """Синхронизация и анализ примечаний из amoCRM"""
    # 1. Получение новых примечаний из amoCRM
    notes = await amocrm_client.get_recent_notes(hours=1)
    
    # 2. Анализ каждого примечания через LLM
    for note in notes:
        # Определение, есть ли вопросы или возражения
        analysis = await analyze_note_with_llm(note["text"])
        
        # 3. Создание событий в analytics_events
        if analysis["has_questions"]:
            for question in analysis["questions"]:
                await create_question_event(note["lead_id"], question, source="amocrm_note")
        
        if analysis["has_objections"]:
            for objection in analysis["objections"]:
                await create_objection_event(note["lead_id"], objection, source="amocrm_note")
```

### Вариант 2: Структурированные примечания

Менеджеры могут использовать шаблоны примечаний:

```
Шаблон примечания:
[Вопросы]
- Можно ли купить в рассрочку?
- Какие сроки строительства?

[Возражения]
- Беспокоится о сроках
- Считает цену высокой

[Результат]
- Отправил КП
- Ждём ответа
```

Тогда анализ упрощается — можно парсить структурированный текст.

---

## Рекомендации

### Для сбора данных от менеджеров:

1. **Структурированные примечания**
   - Создать шаблоны примечаний в amoCRM
   - Менеджеры заполняют по шаблону
   - Легче автоматически извлекать вопросы и возражения

2. **Автоматический анализ через LLM**
   - Анализировать все примечания через LLM
   - Извлекать вопросы и возражения автоматически
   - Создавать события в analytics_events

3. **Интеграция с чатом на сайте**
   - Если есть чат, собирать сообщения оттуда
   - Анализировать вопросы и интересы

4. **Комбинированный подход**
   - Использовать все источники
   - Приоритизировать данные из диалогов с агентом (более структурированные)
   - Дополнять данными из примечаний менеджеров

---

## Итоговая схема сбора данных

```
┌─────────────────────────────────────────────────────────┐
│  Клиент взаимодействует с системой                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Сценарий 1: Работает агент                             │
│    ↓                                                      │
│  messages (PostgreSQL)                                  │
│    ↓                                                      │
│  Анализ сообщений                                       │
│    ↓                                                      │
│  analytics_events (source: agent_conversation)          │
│                                                          │
│  Сценарий 2: Работает менеджер                          │
│    ↓                                                      │
│  Примечание в amoCRM                                    │
│    ↓                                                      │
│  Синхронизация через n8n                                │
│    ↓                                                      │
│  Анализ примечания (LLM)                                │
│    ↓                                                      │
│  analytics_events (source: amocrm_note)                 │
│                                                          │
│  Сценарий 3: Клиент на сайте                            │
│    ↓                                                      │
│  Яндекс.Метрика (события)                               │
│    ↓                                                      │
│  analytics_events (source: yandex_metrika)              │
│                                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Анализ analytics_events для обогащения KB              │
│  (независимо от источника)                               │
└─────────────────────────────────────────────────────────┘
```

---

## Выводы

1. **Яндекс.Метрика** собирает только события на сайте, не тексты диалогов
2. **Вопросы и возражения** собираются из:
   - Диалогов с агентом (таблица `messages`)
   - Примечаний менеджеров в amoCRM (через анализ текста)
   - Чата на сайте (если есть)
3. **Таблица `analytics_events`** — это агрегатор событий из разных источников
4. **Для работы менеджеров** нужен анализ примечаний в amoCRM через LLM или структурированные шаблоны







