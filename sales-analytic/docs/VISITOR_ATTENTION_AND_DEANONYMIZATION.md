# Использование внимания пользователя для деанонимизации

## Обзор

Использование данных о внимании пользователя к объектам (из Яндекс.Метрики) для ненавязчивого предложения обсудить с агентом и получения контактов (деанонимизация).

---

## Отслеживание внимания пользователя

### Паттерны поведения, указывающие на интерес

#### 1. Время на странице объекта

**Индикатор:** Пользователь провёл более 2-3 минут на странице объекта

```python
# analytics-service/service/attention_tracker.py
async def track_product_attention(db: asyncpg.Pool):
    """Отслеживание внимания к объектам"""
    async with db.acquire() as conn:
        # Получение событий с длительным просмотром
        attention_events = await conn.fetch("""
            SELECT 
                event_data->>'client_id' as client_id,
                event_data->>'product_id' as product_id,
                event_data->>'product_name' as product_name,
                (event_data->>'time_on_page')::int as time_on_page,
                event_data->>'url' as url
            FROM analytics_events
            WHERE source = 'yandex_metrika'
              AND event_type = 'page_view'
              AND (event_data->>'time_on_page')::int > 120  -- Более 2 минут
              AND created_at >= NOW() - INTERVAL '1 hour'
        """)
        
        return attention_events
```

#### 2. Множественные просмотры объектов

**Индикатор:** Пользователь просмотрел 3+ разных объекта

```python
async def track_multiple_product_views(db: asyncpg.Pool):
    """Отслеживание множественных просмотров объектов"""
    async with db.acquire() as conn:
        # Подсчёт уникальных объектов на пользователя
        multiple_views = await conn.fetch("""
            SELECT 
                event_data->>'client_id' as client_id,
                COUNT(DISTINCT event_data->>'product_id') as products_viewed,
                ARRAY_AGG(DISTINCT event_data->>'product_name') as product_names,
                MAX(created_at) as last_view
            FROM analytics_events
            WHERE source = 'yandex_metrika'
              AND event_type = 'page_view'
              AND event_data->>'product_id' IS NOT NULL
              AND created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY event_data->>'client_id'
            HAVING COUNT(DISTINCT event_data->>'product_id') >= 3
        """)
        
        return multiple_views
```

#### 3. Возвраты на сайт

**Индикатор:** Пользователь вернулся на сайт в течение 7 дней

```python
async def track_returning_visitors(db: asyncpg.Pool):
    """Отслеживание возвращающихся посетителей"""
    async with db.acquire() as conn:
        returning = await conn.fetch("""
            WITH visitor_sessions AS (
                SELECT 
                    event_data->>'client_id' as client_id,
                    DATE(created_at) as visit_date,
                    COUNT(DISTINCT DATE(created_at)) OVER (PARTITION BY event_data->>'client_id') as visit_count
                FROM analytics_events
                WHERE source = 'yandex_metrika'
                  AND event_type = 'page_view'
                  AND created_at >= NOW() - INTERVAL '7 days'
            )
            SELECT 
                client_id,
                visit_count,
                MAX(visit_date) as last_visit
            FROM visitor_sessions
            WHERE visit_count >= 2
            GROUP BY client_id, visit_count
        """)
        
        return returning
```

#### 4. Просмотр каталога и фильтры

**Индикатор:** Пользователь активно использует фильтры (бюджет, площадь, количество комнат)

```python
async def track_catalog_engagement(db: asyncpg.Pool):
    """Отслеживание активности в каталоге"""
    async with db.acquire() as conn:
        engaged = await conn.fetch("""
            SELECT 
                event_data->>'client_id' as client_id,
                COUNT(*) FILTER (WHERE event_type = 'filter_applied') as filters_used,
                COUNT(*) FILTER (WHERE event_type = 'catalog_view') as catalog_views,
                event_data->>'filters' as filters_applied
            FROM analytics_events
            WHERE source = 'yandex_metrika'
              AND event_type IN ('filter_applied', 'catalog_view')
              AND created_at >= NOW() - INTERVAL '1 hour'
            GROUP BY event_data->>'client_id', event_data->>'filters'
            HAVING COUNT(*) FILTER (WHERE event_type = 'filter_applied') >= 2
        """)
        
        return engaged
```

---

## Ненавязчивые способы предложения обсуждения

### Стратегия: Прогрессивное вовлечение

**Принцип:** Не сразу просить контакты, а постепенно вовлекать в диалог.

#### Этап 1: Пассивное предложение (низкий порог)

**Триггер:** Пользователь просмотрел 1 объект более 2 минут

**Действие:** Ненавязчивый виджет на странице

```javascript
// frontend/widgets/gentle_offer.js
function showGentleOffer(productId, productName) {
    // Показываем через 2 минуты после загрузки страницы
    setTimeout(() => {
        const widget = createWidget({
            type: 'gentle',
            message: `У вас есть вопросы по "${productName}"?`,
            options: [
                { text: 'Да, хочу узнать больше', action: 'start_chat' },
                { text: 'Пока нет', action: 'dismiss' }
            ],
            dismissible: true,
            position: 'bottom-right'
        });
        
        document.body.appendChild(widget);
    }, 120000); // 2 минуты
}
```

**Дизайн виджета:**
- Небольшой размер
- Не блокирует контент
- Легко закрыть
- Дружелюбный тон

#### Этап 2: Активное предложение (средний порог)

**Триггер:** Пользователь просмотрел 3+ объекта или вернулся на сайт

**Действие:** Более заметное предложение

```javascript
function showActiveOffer(clientId, productsViewed) {
    const widget = createWidget({
        type: 'active',
        message: `Вы просмотрели ${productsViewed.length} объектов. Помочь подобрать идеальный вариант?`,
        options: [
            { text: 'Да, хочу консультацию', action: 'start_chat', primary: true },
            { text: 'Позже', action: 'dismiss' }
        ],
        dismissible: true,
        position: 'center',
        overlay: true  // Полупрозрачный фон
    });
    
    document.body.appendChild(widget);
}
```

#### Этап 3: Персонализированное предложение (высокий порог)

**Триггер:** Пользователь вернулся 2+ раза, просмотрел 5+ объектов, использовал фильтры

**Действие:** Персонализированное предложение на основе поведения

```python
# analytics-service/service/personalized_offer.py
async def generate_personalized_offer(client_id: str, db: asyncpg.Pool):
    """Генерация персонализированного предложения на основе поведения"""
    async with db.acquire() as conn:
        # Анализ поведения
        behavior = await analyze_visitor_behavior(conn, client_id)
        
        # Определение интересов
        interests = extract_interests(behavior)
        
        # Генерация предложения
        offer = {
            "message": generate_offer_message(interests),
            "products": behavior["viewed_products"],
            "suggested_action": "chat" if behavior["engagement_score"] > 0.7 else "form"
        }
        
        return offer
```

**Пример персонализированного предложения:**
```
"Мы заметили, что вас интересуют дома с 3 спальнями в районе 10 млн.
Наш агент может подобрать идеальный вариант с учётом ваших пожеланий.
Обсудим?"
```

---

## Процесс деанонимизации

### Стратегия: Многоэтапный процесс

#### Этап 1: Анонимный чат

**Цель:** Начать диалог без запроса контактов

```python
# sales-agent/api/anonymous_chat.py
@router.post("/api/chat/anonymous/start")
async def start_anonymous_chat(
    client_id: str,
    initial_message: str,
    db: asyncpg.Pool
):
    """Начало анонимного чата без контактов"""
    # Создание conversation без amocrm_lead_id
    conversation_id = await db.fetchval("""
        INSERT INTO conversations (
            state, slots, anonymous_client_id
        )
        VALUES ('GREETING', $1, $2)
        RETURNING id
    """, json.dumps({"client_id": client_id}), client_id)
    
    # Сохранение первого сообщения
    await db.execute("""
        INSERT INTO messages (conversation_id, role, content)
        VALUES ($1, 'user', $2)
    """, conversation_id, initial_message)
    
    # Ответ агента
    response = await agent.process_message(conversation_id, initial_message)
    
    return {
        "conversation_id": conversation_id,
        "response": response,
        "requires_contact": False
    }
```

#### Этап 2: Естественный момент для запроса контактов

**Триггеры для запроса контактов:**

1. **Клиент просит конкретную информацию:**
   ```
   Клиент: "Можете отправить мне планировку?"
   Агент: "Конечно! Для отправки мне нужен ваш email или телефон"
   ```

2. **Клиент готов к просмотру:**
   ```
   Клиент: "Хочу посмотреть этот дом"
   Агент: "Отлично! Давайте договоримся о времени. Как с вами связаться?"
   ```

3. **Клиент интересуется КП:**
   ```
   Клиент: "Можете подготовить коммерческое предложение?"
   Агент: "Конечно! Для отправки КП мне нужны ваши контактные данные"
   ```

```python
# sales-agent/domain/deanonimization.py
async def detect_deanonimization_opportunity(conversation_id: int, db: asyncpg.Pool):
    """Определение момента для запроса контактов"""
    async with db.acquire() as conn:
        # Получение последних сообщений
        recent_messages = await conn.fetch("""
            SELECT role, content, metadata
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT 5
        """, conversation_id)
        
        # Анализ интентов
        for message in recent_messages:
            if message["role"] == "user":
                intent = message["metadata"].get("intent")
                
                # Триггеры для запроса контактов
                if intent in ["request_document", "request_viewing", "request_proposal"]:
                    return {
                        "should_request_contact": True,
                        "reason": intent,
                        "natural_moment": True
                    }
        
        return {"should_request_contact": False}
```

#### Этап 3: Запрос контактов в естественном контексте

**Вариант 1: Запрос через контекст диалога**

```python
async def request_contact_naturally(conversation_id: int, reason: str, db: asyncpg.Pool):
    """Естественный запрос контактов в контексте диалога"""
    
    # Определение формулировки в зависимости от причины
    prompts = {
        "request_document": "Для отправки документа мне нужен ваш email или телефон",
        "request_viewing": "Давайте договоримся о времени просмотра. Как с вами связаться?",
        "request_proposal": "Для подготовки и отправки КП мне нужны ваши контактные данные"
    }
    
    prompt = prompts.get(reason, "Для продолжения общения мне нужен ваш контакт")
    
    # Генерация ответа агента
    response = await agent.generate_response(
        conversation_id=conversation_id,
        context={
            "action": "request_contact",
            "reason": reason,
            "prompt": prompt
        }
    )
    
    return response
```

**Пример диалога:**
```
Клиент: "Можете отправить мне планировку этого дома?"
Агент: "Конечно! Для отправки планировки мне нужен ваш email или телефон. 
        Куда отправить?"
Клиент: "Мой email: ivan@example.com"
Агент: "Спасибо! Отправляю планировку на ivan@example.com"
        [Создание лида в amoCRM с email]
```

#### Этап 4: Создание лида в amoCRM

```python
async def create_lead_from_anonymous_chat(
    conversation_id: int,
    contact_info: dict,  # {"email": "...", "phone": "..."}
    db: asyncpg.Pool,
    amocrm_client
):
    """Создание лида в amoCRM после получения контактов"""
    async with db.acquire() as conn:
        # Получение данных из conversation
        conversation = await conn.fetchrow("""
            SELECT slots, anonymous_client_id
            FROM conversations
            WHERE id = $1
        """, conversation_id)
        
        # Создание лида в amoCRM
        lead_data = {
            "name": f"Лид из чата {conversation_id}",
            "contacts": []
        }
        
        if contact_info.get("email"):
            lead_data["contacts"].append({
                "type": "email",
                "value": contact_info["email"]
            })
        
        if contact_info.get("phone"):
            lead_data["contacts"].append({
                "type": "phone",
                "value": contact_info["phone"]
            })
        
        # Добавление данных из conversation.slots
        if conversation["slots"]:
            slots = json.loads(conversation["slots"])
            if slots.get("budget"):
                lead_data["price"] = slots["budget"]
            if slots.get("preferred_products"):
                lead_data["notes"] = f"Интересовались: {', '.join(slots['preferred_products'])}"
        
        # Создание лида
        lead_id = await amocrm_client.create_lead(lead_data)
        
        # Обновление conversation
        await conn.execute("""
            UPDATE conversations
            SET amocrm_lead_id = $1, anonymous_client_id = NULL
            WHERE id = $2
        """, lead_id, conversation_id)
        
        # Создание события
        await conn.execute("""
            INSERT INTO analytics_events (
                amocrm_lead_id, event_type, event_data, source
            )
            VALUES ($1, 'lead_created', $2, 'agent_conversation')
        """,
            lead_id,
            json.dumps({
                "conversation_id": conversation_id,
                "deanonimization_method": "chat",
                "contact_source": "email" if contact_info.get("email") else "phone"
            })
        )
        
        return lead_id
```

---

## Интеграция с фронтендом

### Отслеживание внимания на клиенте

```javascript
// frontend/tracking/attention_tracker.js
class AttentionTracker {
    constructor(clientId) {
        this.clientId = clientId;
        this.startTime = Date.now();
        this.productId = this.getProductIdFromUrl();
        this.trackInterval = null;
    }
    
    startTracking() {
        // Отправка события каждые 30 секунд
        this.trackInterval = setInterval(() => {
            this.sendAttentionEvent();
        }, 30000);
        
        // Отслеживание ухода со страницы
        window.addEventListener('beforeunload', () => {
            this.sendFinalAttentionEvent();
        });
    }
    
    sendAttentionEvent() {
        const timeOnPage = Math.floor((Date.now() - this.startTime) / 1000);
        
        fetch('/api/analytics/track', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                client_id: this.clientId,
                event_type: 'page_view',
                event_data: {
                    product_id: this.productId,
                    time_on_page: timeOnPage,
                    url: window.location.href
                },
                source: 'yandex_metrika'
            })
        });
    }
    
    checkForOffer() {
        // Проверка, нужно ли показать предложение
        fetch(`/api/analytics/check-offer?client_id=${this.clientId}`)
            .then(res => res.json())
            .then(data => {
                if (data.should_show_offer) {
                    this.showOffer(data.offer_type, data.offer_data);
                }
            });
    }
}
```

### Виджет предложения

```javascript
// frontend/widgets/chat_offer.js
class ChatOfferWidget {
    constructor(type, data) {
        this.type = type; // 'gentle', 'active', 'personalized'
        this.data = data;
    }
    
    show() {
        const widget = this.createWidget();
        document.body.appendChild(widget);
        
        // Обработка действий
        widget.querySelector('.start-chat').addEventListener('click', () => {
            this.startAnonymousChat();
        });
    }
    
    createWidget() {
        const widget = document.createElement('div');
        widget.className = `chat-offer-widget chat-offer-${this.type}`;
        widget.innerHTML = `
            <div class="chat-offer-content">
                <p>${this.data.message}</p>
                <div class="chat-offer-actions">
                    <button class="start-chat">${this.data.cta_text || 'Начать обсуждение'}</button>
                    <button class="dismiss">Позже</button>
                </div>
            </div>
        `;
        return widget;
    }
    
    startAnonymousChat() {
        // Открытие чата без запроса контактов
        window.openChat({
            anonymous: true,
            client_id: this.data.client_id,
            context: this.data.context
        });
    }
}
```

---

## Workflow деанонимизации

```
┌─────────────────────────────────────────────────────────┐
│  Пользователь на сайте (анонимный)                      │
│  - Просматривает объекты                                │
│  - Проводит время на страницах                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Отслеживание внимания (Яндекс.Метрика)                 │
│  - Время на странице > 2 мин                            │
│  - Просмотр 3+ объектов                                 │
│  - Возврат на сайт                                       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Ненавязчивое предложение                               │
│  - Виджет на странице                                   │
│  - Персонализированное сообщение                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Анонимный чат (без контактов)                          │
│  - Диалог с агентом                                     │
│  - Ответы на вопросы                                    │
│  - Подбор объектов                                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Естественный момент для контактов                      │
│  - Клиент просит документ                               │
│  - Клиент хочет просмотр                                │
│  - Клиент просит КП                                     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Запрос контактов в контексте                           │
│  - "Для отправки документа нужен email"                 │
│  - "Для просмотра нужен телефон"                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Получение контактов                                    │
│  - Email или телефон                                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│  Создание лида в amoCRM                                 │
│  - Связь conversation с лидом                           │
│  - История диалога сохраняется                          │
└─────────────────────────────────────────────────────────┘
```

---

## Примеры сценариев

### Сценарий 1: Длительный просмотр объекта

```
1. Пользователь просматривает объект 3 минуты
   ↓
2. Появляется виджет: "У вас есть вопросы по этому объекту?"
   ↓
3. Пользователь: "Да, хочу узнать больше"
   ↓
4. Открывается анонимный чат
   ↓
5. Агент отвечает на вопросы
   ↓
6. Клиент: "Можете отправить планировку?"
   ↓
7. Агент: "Конечно! Для отправки нужен ваш email"
   ↓
8. Клиент: "ivan@example.com"
   ↓
9. Создаётся лид в amoCRM с email
```

### Сценарий 2: Множественные просмотры

```
1. Пользователь просмотрел 5 объектов за час
   ↓
2. Появляется персонализированное предложение:
   "Вы просмотрели несколько объектов. Помочь подобрать идеальный вариант?"
   ↓
3. Пользователь начинает чат
   ↓
4. Агент анализирует просмотренные объекты и предлагает варианты
   ↓
5. Клиент: "Хочу посмотреть один из этих домов"
   ↓
6. Агент: "Отлично! Для записи на просмотр нужен ваш телефон"
   ↓
7. Клиент: "+7 999 123-45-67"
   ↓
8. Создаётся лид в amoCRM с телефоном
```

### Сценарий 3: Возврат на сайт

```
1. Пользователь вернулся на сайт через 2 дня
   ↓
2. Появляется предложение:
   "Рады видеть вас снова! Продолжим обсуждение?"
   ↓
3. Пользователь начинает чат
   ↓
4. Агент: "Я помню, вас интересовали дома с 3 спальнями. 
           Нашли что-то подходящее?"
   ↓
5. Клиент: "Да, но хочу уточнить детали"
   ↓
6. Агент отвечает, предлагает КП
   ↓
7. Клиент: "Хорошо, отправьте КП"
   ↓
8. Агент: "Для отправки КП нужны ваши контактные данные"
   ↓
9. Клиент предоставляет контакты
   ↓
10. Создаётся лид в amoCRM
```

---

## Рекомендации по реализации

### 1. Прогрессивное вовлечение

- **Низкий порог:** Простое предложение после 2 минут на странице
- **Средний порог:** Более активное предложение после 3+ просмотров
- **Высокий порог:** Персонализированное предложение для возвращающихся

### 2. Естественность запроса контактов

- Не просить контакты сразу
- Запрашивать в контексте (для отправки документа, записи на просмотр)
- Объяснять зачем нужны контакты

### 3. Сохранение контекста

- Сохранять историю анонимного диалога
- При деанонимизации переносить контекст в лид
- Использовать данные о поведении для персонализации

### 4. A/B тестирование

- Тестировать разные формулировки предложений
- Тестировать моменты показа виджетов
- Оптимизировать конверсию в контакты

---

## Метрики эффективности

### Ключевые метрики

1. **Конверсия внимания в чат:**
   - Процент пользователей, которые начали чат после предложения

2. **Конверсия чата в контакты:**
   - Процент анонимных чатов, которые привели к получению контактов

3. **Время до деанонимизации:**
   - Среднее время от начала чата до получения контактов

4. **Эффективность триггеров:**
   - Какие триггеры (время на странице, множественные просмотры) работают лучше

### Отслеживание

```python
# analytics-service/analysis/deanonimization_metrics.py
async def track_deanonimization_metrics(db: asyncpg.Pool, period_days: int = 30):
    """Отслеживание метрик деанонимизации"""
    cutoff_date = datetime.now() - timedelta(days=period_days)
    
    async with db.acquire() as conn:
        # Конверсия внимания в чат
        attention_events = await conn.fetchval("""
            SELECT COUNT(DISTINCT event_data->>'client_id')
            FROM analytics_events
            WHERE event_type = 'attention_signal'
              AND created_at >= $1
        """, cutoff_date)
        
        chat_starts = await conn.fetchval("""
            SELECT COUNT(DISTINCT anonymous_client_id)
            FROM conversations
            WHERE created_at >= $1
              AND anonymous_client_id IS NOT NULL
        """, cutoff_date)
        
        attention_to_chat = (chat_starts / attention_events * 100) if attention_events > 0 else 0
        
        # Конверсия чата в контакты
        anonymous_chats = await conn.fetchval("""
            SELECT COUNT(*)
            FROM conversations
            WHERE created_at >= $1
              AND anonymous_client_id IS NOT NULL
        """, cutoff_date)
        
        deanonimized = await conn.fetchval("""
            SELECT COUNT(*)
            FROM conversations
            WHERE created_at >= $1
              AND anonymous_client_id IS NOT NULL
              AND amocrm_lead_id IS NOT NULL
        """, cutoff_date)
        
        chat_to_contact = (deanonimized / anonymous_chats * 100) if anonymous_chats > 0 else 0
        
        return {
            "attention_to_chat_conversion": round(attention_to_chat, 2),
            "chat_to_contact_conversion": round(chat_to_contact, 2),
            "total_deanonimized": deanonimized
        }
```

---

## Итоговая схема

```
Яндекс.Метрика (внимание)
    ↓
Отслеживание поведения
    ├─→ Время на странице
    ├─→ Множественные просмотры
    └─→ Возвраты на сайт
    ↓
Ненавязчивое предложение
    ↓
Анонимный чат
    ↓
Естественный момент для контактов
    ↓
Получение контактов
    ↓
Создание лида в amoCRM
    ↓
Продолжение работы с лидом
```







