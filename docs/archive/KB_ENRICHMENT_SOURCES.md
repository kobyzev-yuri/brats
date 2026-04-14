# Источники обогащения Knowledge Base: разделение ролей

## Ключевой момент

**Яндекс.Метрика НЕ собирает вопросы и возражения клиентов напрямую.**

Но она даёт **важную контекстную информацию**, которая помогает понять, **какую информацию нужно добавить в KB**.

---

## Разделение ролей источников

### 1. Яндекс.Метрика — контекст и поведение

**Что даёт для KB:**
- ✅ Понимание популярных объектов (какие объекты чаще просматривают)
- ✅ Понимание проблемных мест (где пользователи уходят)
- ✅ Понимание эффективности контента (какие страницы конвертируются)
- ✅ Понимание интересов (какие характеристики объектов важны)

**Что НЕ даёт:**
- ❌ Тексты вопросов клиентов
- ❌ Тексты возражений
- ❌ Тексты диалогов

**Как используется для обогащения KB:**

#### Пример 1: Популярные объекты

```python
# analytics-service/analysis/kb_enrichment.py
async def identify_popular_products_for_kb(db: asyncpg.Pool):
    """Определение популярных объектов из Яндекс.Метрики для приоритизации в KB"""
    async with db.acquire() as conn:
        # Анализ просмотров объектов из Яндекс.Метрики
        popular_products = await conn.fetch("""
            SELECT 
                event_data->>'product_id' as product_id,
                event_data->>'product_name' as product_name,
                COUNT(*) as view_count,
                AVG((event_data->>'time_on_page')::int) as avg_time,
                COUNT(DISTINCT amocrm_lead_id) as unique_visitors
            FROM analytics_events
            WHERE source = 'yandex_metrika'
              AND event_type = 'page_view'
              AND event_data->>'url' LIKE '%product%'
              AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY event_data->>'product_id', event_data->>'product_name'
            HAVING COUNT(*) >= 20  -- Минимум 20 просмотров
            ORDER BY view_count DESC
        """)
        
        # Проверка наличия информации в KB
        for product in popular_products:
            existing_kb = await conn.fetchrow("""
                SELECT id
                FROM knowledge_base
                WHERE metadata->>'category' = 'product_info'
                  AND content LIKE $1
            """, f"%{product['product_name']}%")
            
            if not existing_kb:
                # Рекомендация: добавить информацию о популярном объекте в KB
                await create_kb_addition_recommendation(
                    conn,
                    product_id=product["product_id"],
                    product_name=product["product_name"],
                    reason="Популярный объект (просмотров: {})".format(product["view_count"]),
                    priority="high"
                )
```

#### Пример 2: Проблемные места в воронке

```python
async def identify_funnel_issues_for_kb(db: asyncpg.Pool):
    """Определение проблемных мест из Яндекс.Метрики для улучшения KB"""
    async with db.acquire() as conn:
        # Анализ отказов (пользователи ушли быстро)
        high_bounce_pages = await conn.fetch("""
            SELECT 
                event_data->>'url' as url,
                COUNT(*) as views,
                COUNT(CASE WHEN (event_data->>'time_on_page')::int < 10 THEN 1 END) as quick_exits
            FROM analytics_events
            WHERE source = 'yandex_metrika'
              AND event_type = 'page_view'
              AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY event_data->>'url'
            HAVING COUNT(*) >= 10
              AND COUNT(CASE WHEN (event_data->>'time_on_page')::int < 10 THEN 1 END)::float / COUNT(*) > 0.5
            ORDER BY quick_exits DESC
        """)
        
        # Рекомендации для KB
        for page in high_bounce_pages:
            # Если страница с высоким отказом - возможно, контент не отвечает на вопросы
            await create_kb_improvement_recommendation(
                conn,
                page_url=page["url"],
                issue="Высокий процент отказов ({}%)".format(
                    round(page["quick_exits"] / page["views"] * 100, 1)
                ),
                recommendation="Добавить в KB информацию, которая отвечает на вопросы по этой странице"
            )
```

#### Пример 3: Эффективные страницы

```python
async def identify_effective_content_for_kb(db: asyncpg.Pool):
    """Определение эффективного контента для использования в KB"""
    async with db.acquire() as conn:
        # Страницы с высокой конверсией
        high_conversion_pages = await conn.fetch("""
            SELECT 
                event_data->>'url' as url,
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'page_view') as visitors,
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'goal' AND event_data->>'goal_id' = 'lead_form') as conversions
            FROM analytics_events
            WHERE source = 'yandex_metrika'
              AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY event_data->>'url'
            HAVING COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'page_view') >= 10
            ORDER BY 
                COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'goal')::float /
                NULLIF(COUNT(DISTINCT amocrm_lead_id) FILTER (WHERE event_type = 'page_view'), 0) DESC
        """)
        
        # Рекомендация: использовать контент с эффективных страниц в KB
        for page in high_conversion_pages:
            conversion_rate = page["conversions"] / page["visitors"] * 100 if page["visitors"] > 0 else 0
            if conversion_rate > 10:  # Конверсия выше 10%
                await create_kb_content_recommendation(
                    conn,
                    page_url=page["url"],
                    reason="Высокая конверсия ({}%)".format(round(conversion_rate, 1)),
                    action="Использовать элементы контента этой страницы в KB"
                )
```

---

### 2. Диалоги с агентом — прямые вопросы и возражения

**Что даёт для KB:**
- ✅ Реальные вопросы клиентов (текст)
- ✅ Реальные возражения (текст)
- ✅ Успешные ответы агента
- ✅ Паттерны эффективных диалогов

**Источник:** Таблица `messages` в PostgreSQL

**Как используется:**

```python
async def extract_questions_from_agent_conversations(db: asyncpg.Pool):
    """Извлечение вопросов из диалогов с агентом"""
    async with db.acquire() as conn:
        # Получение вопросов клиентов
        questions = await conn.fetch("""
            SELECT 
                m.content as question,
                m.metadata->>'intent' as intent,
                COUNT(*) as frequency
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.role = 'user'
              AND m.content LIKE '%?'
              AND m.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY m.content, m.metadata->>'intent'
            HAVING COUNT(*) >= 3
            ORDER BY frequency DESC
        """)
        
        return questions
```

---

### 3. Примечания менеджеров — вопросы и возражения от живых менеджеров

**Что даёт для KB:**
- ✅ Вопросы клиентов (из примечаний)
- ✅ Возражения клиентов (из примечаний)
- ✅ Результаты переговоров

**Источник:** Примечания в amoCRM

**Как используется:**

```python
async def extract_info_from_manager_notes(db: asyncpg.Pool, amocrm_client):
    """Извлечение информации из примечаний менеджеров"""
    # Получение примечаний из amoCRM
    notes = await amocrm_client.get_recent_notes(days=30)
    
    # Анализ через LLM для извлечения вопросов и возражений
    for note in notes:
        analysis = await analyze_note_with_llm(note["text"])
        # Создание событий в analytics_events с source='amocrm_note'
```

---

## Схема обогащения KB из разных источников

```
┌─────────────────────────────────────────────────────────┐
│              Источники данных                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  1. Яндекс.Метрика                                      │
│     └─→ Контекст: популярные объекты, проблемные места │
│         НЕ даёт: вопросы и возражения                  │
│                                                          │
│  2. Диалоги с агентом (messages)                       │
│     └─→ Прямые данные: вопросы, возражения, ответы     │
│                                                          │
│  3. Примечания менеджеров (amoCRM)                     │
│     └─→ Прямые данные: вопросы, возражения из текста   │
│                                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│         Анализ и обогащение KB                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Из Яндекс.Метрики:                                     │
│  ├─→ Определение популярных объектов → приоритизация KB │
│  ├─→ Выявление проблемных мест → добавление контента   │
│  └─→ Анализ эффективного контента → использование в KB  │
│                                                          │
│  Из диалогов и примечаний:                              │
│  ├─→ Добавление новых возражений с ответами             │
│  ├─→ Добавление ответов на популярные вопросы           │
│  └─→ Улучшение скриптов продаж                          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Конкретные примеры использования Яндекс.Метрики для KB

### Пример 1: Приоритизация объектов в KB

**Проблема:** В KB есть информация о многих объектах, но непонятно, на каких фокусироваться.

**Решение через Яндекс.Метрику:**
```python
# Анализ просмотров объектов
popular_products = analyze_product_views_from_metrika()

# Обновление приоритетов в KB
for product in popular_products:
    update_kb_priority(
        product_id=product["id"],
        priority="high",  # Популярные объекты получают высокий приоритет
        reason="Популярный объект ({} просмотров)".format(product["views"])
    )
```

**Результат:** Агент чаще использует информацию о популярных объектах.

---

### Пример 2: Выявление недостающей информации

**Проблема:** Пользователи часто уходят со страницы объекта — возможно, не находят нужную информацию.

**Решение через Яндекс.Метрику:**
```python
# Анализ отказов
high_bounce_products = analyze_bounce_rate_from_metrika()

# Проверка наличия информации в KB
for product in high_bounce_products:
    kb_content = check_kb_for_product(product["id"])
    
    if not kb_content or len(kb_content) < 200:  # Мало информации
        create_kb_addition_task(
            product_id=product["id"],
            reason="Высокий отказ ({}%), мало информации в KB".format(product["bounce_rate"]),
            priority="high"
        )
```

**Результат:** В KB добавляется недостающая информация о проблемных объектах.

---

### Пример 3: Использование эффективного контента

**Проблема:** Нужно понять, какой контент работает лучше всего.

**Решение через Яндекс.Метрику:**
```python
# Анализ конверсии страниц
effective_pages = analyze_conversion_from_metrika()

# Извлечение ключевых элементов контента
for page in effective_pages:
    if page["conversion_rate"] > 15:  # Высокая конверсия
        content_elements = extract_content_elements(page["url"])
        
        # Добавление в KB
        add_to_kb(
            content=content_elements["key_points"],
            category="product_info",
            reason="Эффективный контент (конверсия {}%)".format(page["conversion_rate"])
        )
```

**Результат:** Эффективные элементы контента попадают в KB.

---

## Что НЕ даёт Яндекс.Метрика (и откуда это брать)

### ❌ Вопросы клиентов
**Источник:** Диалоги с агентом (`messages`) или примечания менеджеров

### ❌ Возражения клиентов
**Источник:** Диалоги с агентом (`messages`) или примечания менеджеров

### ❌ Тексты диалогов
**Источник:** Таблица `messages` в PostgreSQL

---

## Итоговая схема вклада каждого источника

```
┌─────────────────────────────────────────────────────────┐
│  Яндекс.Метрика                                         │
│  Вклад в KB:                                            │
│  ✅ Контекст (популярные объекты, проблемные места)    │
│  ✅ Приоритизация (на что фокусироваться в KB)         │
│  ✅ Выявление пробелов (где не хватает информации)     │
│  ✅ Эффективный контент (что работает)                 │
│                                                          │
│  НЕ даёт:                                               │
│  ❌ Вопросы клиентов                                    │
│  ❌ Возражения клиентов                                 │
└─────────────────────────────────────────────────────────┘
                       +
┌─────────────────────────────────────────────────────────┐
│  Диалоги с агентом (messages)                          │
│  Вклад в KB:                                            │
│  ✅ Вопросы клиентов (текст)                           │
│  ✅ Возражения клиентов (текст)                         │
│  ✅ Успешные ответы агента                              │
│  ✅ Паттерны эффективных диалогов                       │
└─────────────────────────────────────────────────────────┘
                       +
┌─────────────────────────────────────────────────────────┐
│  Примечания менеджеров (amoCRM)                        │
│  Вклад в KB:                                            │
│  ✅ Вопросы клиентов (из текста примечаний)            │
│  ✅ Возражения клиентов (из текста примечаний)         │
│  ✅ Результаты переговоров                              │
└─────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Обогащённая Knowledge Base                             │
│                                                          │
│  Структурированная информация:                          │
│  - Приоритетные объекты (из Метрики)                    │
│  - Ответы на вопросы (из диалогов/примечаний)           │
│  - Обработка возражений (из диалогов/примечаний)        │
│  - Эффективные скрипты (из успешных диалогов)           │
└─────────────────────────────────────────────────────────┘
```

---

## Выводы

1. **Яндекс.Метрика** даёт **контекст и приоритеты**, но не тексты вопросов/возражений
2. **Диалоги с агентом** дают **прямые тексты** вопросов и возражений
3. **Примечания менеджеров** дают **вопросы и возражения** через анализ текста
4. **Все источники дополняют друг друга:**
   - Метрика показывает **ЧТО** важно (популярные объекты)
   - Диалоги/примечания показывают **КАК** отвечать (вопросы, возражения)




















