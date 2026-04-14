# Интеграция каталога amoCRM с Нейропродажником

## Обзор

amoCRM имеет встроенный каталог товаров/услуг (nomenklatura), который может быть использован как источник данных для Нейропродажника. Это позволяет:

1. **Единый источник истины** — менеджеры работают с каталогом в amoCRM
2. **Синхронизация с 1C** — каталог можно синхронизировать с учётными системами через CSV
3. **Автоматический расчёт стоимости** — при добавлении товаров в сделки автоматически рассчитывается сумма
4. **Контекст для агента** — агент может использовать данные каталога для формирования КП

## Возможности каталога amoCRM

### Основные функции

- **Структурированный список товаров/услуг** с SKU, ценами и описаниями
- **Добавление товаров в сделки** — автоматический расчёт общей стоимости
- **Цифровая автоматизация** — информация о продуктах может триггерить действия в воронке
- **Импорт/экспорт** — синхронизация с 1C и другими системами через CSV

### Структура товара в amoCRM

```json
{
  "id": 12345,
  "name": "Коттедж BLACK BOX, участок 12",
  "sku": "BLACK_BOX_001",
  "price": 8350000,
  "currency": "RUB",
  "description": "Современный дом с черновой отделкой...",
  "category": {
    "id": 100,
    "name": "Коттеджи"
  },
  "custom_fields": [
    {
      "id": 500,
      "name": "Площадь",
      "value": "120 кв.м"
    },
    {
      "id": 501,
      "name": "Участок",
      "value": "6 соток"
    }
  ]
}
```

## Архитектура интеграции

### Гибридный подход: amoCRM + PostgreSQL

**amoCRM каталог** — источник истины для менеджеров:
- Управление номенклатурой через интерфейс amoCRM
- Синхронизация с 1C через CSV импорт/экспорт
- Использование в сделках для автоматического расчёта стоимости

**PostgreSQL products** — расширенная версия для агента:
- Кэш данных из amoCRM каталога
- Дополнительные поля для RAG (embeddings, метаданные)
- Векторный поиск для семантического подбора объектов
- Связь с вариантами скидок и продаж

### Схема синхронизации

```
┌─────────────────┐
│  amoCRM Catalog │  ← Менеджеры управляют каталогом
│  (nomenklatura) │  ← Синхронизация с 1C через CSV
└────────┬────────┘
         │
         │ n8n workflow: синхронизация каталога
         │ (периодически или по событию)
         ↓
┌─────────────────┐
│  PostgreSQL     │
│  products       │  ← Кэш + расширенные данные
│                 │  ← Embeddings для RAG
│  discount_rules │  ← Варианты скидок
│  sales_options  │  ← Варианты продаж
└────────┬────────┘
         │
         │ Используется агентом
         ↓
┌─────────────────┐
│  Нейропродажник │
│  (sales-agent)  │  ← Векторный поиск объектов
│                 │  ← Генерация КП с товарами
└─────────────────┘
```

## Схема таблицы products (обновлённая)

### Добавление полей для синхронизации с amoCRM

```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    
    -- Связь с каталогом amoCRM
    amocrm_catalog_id INTEGER UNIQUE,  -- ID товара в каталоге amoCRM
    amocrm_sku VARCHAR(100),  -- SKU из amoCRM (для синхронизации)
    sync_status VARCHAR(50) DEFAULT 'synced',  -- 'synced', 'pending', 'error'
    last_synced_at TIMESTAMP,  -- Дата последней синхронизации
    
    -- Базовые данные (синхронизируются из amoCRM)
    code VARCHAR(50) UNIQUE,  -- Внутренний код (может совпадать с SKU)
    name VARCHAR(200),  -- Название из amoCRM
    category VARCHAR(100),  -- Категория из amoCRM
    
    -- Ценовая информация (из amoCRM, может быть переопределена)
    price_base DECIMAL(12, 2),  -- Базовая цена из amoCRM
    price_current DECIMAL(12, 2),  -- Текущая цена (может быть со скидкой)
    price_currency VARCHAR(3) DEFAULT 'RUB',
    discount_percent DECIMAL(5, 2),  -- Процент скидки (если есть)
    
    -- Технические характеристики
    area_total DECIMAL(8, 2),
    area_living DECIMAL(8, 2),
    area_land DECIMAL(8, 2),
    rooms_count INTEGER,
    floors_count INTEGER,
    
    -- Дополнительные характеристики (JSONB)
    features JSONB,
    
    -- Описание для LLM (расширенное, может быть дополнено)
    description TEXT,  -- Полное описание (из amoCRM + дополнения)
    description_short TEXT,  -- Краткое описание из amoCRM
    advantages TEXT[],  -- Массив преимуществ
    objections_handling JSONB,  -- Типовые возражения и ответы
    
    -- Векторное представление для семантического поиска
    description_embedding vector(1536),  -- Эмбеддинг описания для RAG
    
    -- Статус и доступность
    status VARCHAR(50),  -- 'available', 'reserved', 'sold', 'construction'
    availability_date DATE,
    
    -- Метаданные
    location JSONB,
    photos_urls TEXT[],
    floor_plan_url VARCHAR(500),
    
    -- Данные из amoCRM (JSONB для гибкости)
    amocrm_data JSONB,  -- Полные данные из amoCRM (custom_fields и т.д.)
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX ON products (amocrm_catalog_id);
CREATE INDEX ON products (amocrm_sku);
CREATE INDEX ON products (sync_status, last_synced_at);
CREATE INDEX ON products USING ivfflat (description_embedding vector_cosine_ops);
CREATE INDEX ON products (category, status);
CREATE INDEX ON products USING GIN (features);
CREATE INDEX ON products (price_current);
```

## Процесс синхронизации каталога

### 1. Первичная синхронизация (импорт из amoCRM)

```python
# n8n workflow или отдельный сервис catalog-sync
import asyncpg
import httpx
import json
from openai import OpenAI

async def sync_catalog_from_amocrm(
    amocrm_subdomain: str,
    access_token: str,
    db_url: str
):
    """
    Синхронизация каталога из amoCRM в PostgreSQL.
    Выполняется периодически (например, раз в час) или по событию.
    """
    openai_client = OpenAI()
    
    # Получение каталога из amoCRM
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{amocrm_subdomain}.amocrm.ru/api/v4/catalogs",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        catalogs = response.json()["_embedded"]["catalogs"]
        
        # Для каждого каталога получаем товары
        for catalog in catalogs:
            catalog_id = catalog["id"]
            
            # Получение товаров каталога
            products_response = await client.get(
                f"https://{amocrm_subdomain}.amocrm.ru/api/v4/catalogs/{catalog_id}/elements",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"limit": 250}  # Максимум за один запрос
            )
            products = products_response.json()["_embedded"]["elements"]
            
            # Синхронизация каждого товара
            async with asyncpg.create_pool(db_url) as pool:
                async with pool.acquire() as conn:
                    for product in products:
                        await sync_product(conn, product, catalog_id, openai_client)


async def sync_product(
    conn: asyncpg.Connection,
    amocrm_product: dict,
    catalog_id: int,
    openai_client: OpenAI
):
    """
    Синхронизация одного товара из amoCRM в PostgreSQL.
    """
    amocrm_id = amocrm_product["id"]
    sku = amocrm_product.get("sku", "")
    name = amocrm_product.get("name", "")
    price = amocrm_product.get("price", 0) / 100  # amoCRM хранит цены в копейках
    description = amocrm_product.get("description", "")
    
    # Извлечение custom_fields
    custom_fields = {}
    for field in amocrm_product.get("custom_fields_values", []):
        field_name = field.get("field_name", "")
        field_value = field.get("values", [{}])[0].get("value", "")
        custom_fields[field_name] = field_value
    
    # Генерация embedding для описания
    full_description = f"{name}. {description}"
    if custom_fields:
        full_description += f" Характеристики: {custom_fields}"
    
    embedding = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=full_description
    ).data[0].embedding
    
    # Проверка существования товара
    existing = await conn.fetchrow(
        "SELECT id FROM products WHERE amocrm_catalog_id = $1",
        amocrm_id
    )
    
    if existing:
        # Обновление существующего товара
        await conn.execute("""
            UPDATE products
            SET
                amocrm_sku = $1,
                name = $2,
                price_base = $3,
                price_current = $3,
                description = $4,
                description_short = $5,
                description_embedding = $6::vector,
                amocrm_data = $7,
                sync_status = 'synced',
                last_synced_at = NOW(),
                updated_at = NOW()
            WHERE amocrm_catalog_id = $8
        """,
            sku, name, price, full_description, description,
            embedding, json.dumps(amocrm_product), amocrm_id
        )
    else:
        # Создание нового товара
        await conn.execute("""
            INSERT INTO products (
                amocrm_catalog_id, amocrm_sku, code, name,
                price_base, price_current, description, description_short,
                description_embedding, amocrm_data, sync_status, last_synced_at
            )
            VALUES ($1, $2, $3, $4, $5, $5, $6, $7, $8::vector, $9, 'synced', NOW())
        """,
            amocrm_id, sku, sku or f"AMOCRM_{amocrm_id}", name,
            price, full_description, description, embedding, json.dumps(amocrm_product)
        )
```

### 2. Использование каталога в агенте

```python
# sales-agent/domain/product_search.py
import asyncpg
from openai import OpenAI

async def search_products_for_proposal(
    query: str,
    budget_min: float = None,
    budget_max: float = None,
    category: str = None,
    db_url: str = None
) -> list:
    """
    Поиск товаров для коммерческого предложения.
    Использует данные из PostgreSQL (синхронизированные из amoCRM).
    """
    openai_client = OpenAI()
    
    # Генерация embedding для запроса
    query_embedding = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    ).data[0].embedding
    
    # Построение SQL запроса
    where_clauses = ["status = 'available'", "sync_status = 'synced'"]
    params = [query_embedding]
    param_idx = 2
    
    if budget_min:
        where_clauses.append(f"price_current >= ${param_idx}")
        params.append(budget_min)
        param_idx += 1
    
    if budget_max:
        where_clauses.append(f"price_current <= ${param_idx}")
        params.append(budget_max)
        param_idx += 1
    
    if category:
        where_clauses.append(f"category = ${param_idx}")
        params.append(category)
        param_idx += 1
    
    where_sql = " AND ".join(where_clauses)
    
    # Выполнение запроса
    async with asyncpg.create_pool(db_url) as pool:
        async with pool.acquire() as conn:
            results = await conn.fetch(f"""
                SELECT 
                    id,
                    amocrm_catalog_id,
                    name,
                    description_short,
                    price_current,
                    category,
                    features,
                    amocrm_data,
                    1 - (description_embedding <=> $1::vector) as similarity
                FROM products
                WHERE {where_sql}
                  AND 1 - (description_embedding <=> $1::vector) > 0.6
                ORDER BY description_embedding <=> $1::vector
                LIMIT ${param_idx}
            """, *params, 10)
            
            return [
                {
                    "id": r["id"],
                    "amocrm_catalog_id": r["amocrm_catalog_id"],
                    "name": r["name"],
                    "description": r["description_short"],
                    "price": float(r["price_current"]),
                    "category": r["category"],
                    "features": r["features"],
                    "amocrm_data": r["amocrm_data"],
                    "similarity": float(r["similarity"])
                }
                for r in results
            ]
```

### 3. Генерация КП с товарами из каталога

```python
# proposal-generator/service/proposal_service.py
async def generate_proposal_with_catalog_items(
    conversation_id: int,
    selected_products: list,  # Список {amocrm_catalog_id, quantity}
    db_url: str,
    amocrm_subdomain: str,
    access_token: str
):
    """
    Генерация КП с товарами из каталога amoCRM.
    Товары добавляются в КП через amoCRM API для автоматического расчёта стоимости.
    """
    # Получение данных о товарах из PostgreSQL
    async with asyncpg.create_pool(db_url) as pool:
        async with pool.acquire() as conn:
            product_ids = [p["amocrm_catalog_id"] for p in selected_products]
            products = await conn.fetch("""
                SELECT id, amocrm_catalog_id, name, price_current, description_short
                FROM products
                WHERE amocrm_catalog_id = ANY($1)
            """, product_ids)
    
    # Формирование структуры КП
    proposal_items = []
    total_price = 0
    
    for selected in selected_products:
        product = next(p for p in products if p["amocrm_catalog_id"] == selected["amocrm_catalog_id"])
        quantity = selected.get("quantity", 1)
        item_price = float(product["price_current"]) * quantity
        
        proposal_items.append({
            "amocrm_catalog_id": product["amocrm_catalog_id"],
            "name": product["name"],
            "price": float(product["price_current"]),
            "quantity": quantity,
            "total": item_price
        })
        total_price += item_price
    
    # Сохранение КП в PostgreSQL
    proposal_id = await conn.fetchval("""
        INSERT INTO proposals (
            conversation_id, status, content_structured, version
        )
        VALUES ($1, 'draft', $2, 1)
        RETURNING id
    """, conversation_id, json.dumps({
        "items": proposal_items,
        "total_price": total_price,
        "currency": "RUB"
    }))
    
    # Создание сделки в amoCRM с товарами из каталога
    async with httpx.AsyncClient() as client:
        # Получение лида из conversation
        conversation = await conn.fetchrow(
            "SELECT amocrm_lead_id FROM conversations WHERE id = $1",
            conversation_id
        )
        
        if conversation and conversation["amocrm_lead_id"]:
            # Создание сделки с товарами
            deal_data = {
                "name": f"КП #{proposal_id}",
                "price": int(total_price * 100),  # amoCRM хранит в копейках
                "_embedded": {
                    "leads": [{"id": conversation["amocrm_lead_id"]}]
                }
            }
            
            deal_response = await client.post(
                f"https://{amocrm_subdomain}.amocrm.ru/api/v4/leads",
                headers={"Authorization": f"Bearer {access_token}"},
                json=[deal_data]
            )
            deal_id = deal_response.json()["_embedded"]["leads"][0]["id"]
            
            # Добавление товаров в сделку
            catalog_items = [
                {
                    "catalog_id": catalog_id,  # ID каталога в amoCRM
                    "quantity": item["quantity"],
                    "price_id": item["amocrm_catalog_id"]
                }
                for item in proposal_items
            ]
            
            await client.post(
                f"https://{amocrm_subdomain}.amocrm.ru/api/v4/leads/{deal_id}/links",
                headers={"Authorization": f"Bearer {access_token}"},
                json=catalog_items
            )
            
            # Обновление proposal с amocrm_deal_id
            await conn.execute("""
                UPDATE proposals
                SET amocrm_lead_id = $1
                WHERE id = $2
            """, deal_id, proposal_id)
    
    return proposal_id
```

## n8n Workflow для синхронизации

### Периодическая синхронизация каталога

```
[Cron Trigger: каждый час]
  ↓
[HTTP Request: GET /api/v4/catalogs]
  ↓
[Code: обработка каталогов]
  ↓
[HTTP Request: GET /api/v4/catalogs/{id}/elements]
  ↓
[Code: генерация embeddings через OpenAI]
  ↓
[PostgreSQL: INSERT/UPDATE products]
  ↓
[Если ошибка → уведомление в Telegram]
```

### Синхронизация при изменении в amoCRM

```
[Webhook от amoCRM: изменение товара]
  ↓
[HTTP Request: GET /api/v4/catalogs/{id}/elements/{id}]
  ↓
[Code: генерация embedding]
  ↓
[PostgreSQL: UPDATE products]
```

## Преимущества гибридного подхода

### ✅ Единый источник истины
- Менеджеры работают с каталогом в amoCRM
- Синхронизация с 1C через CSV
- Автоматический расчёт стоимости в сделках

### ✅ Расширенные возможности для агента
- Векторный поиск для семантического подбора
- Дополнительные метаданные для RAG
- Связь с вариантами скидок и продаж

### ✅ Гибкость
- Можно дополнять данные в PostgreSQL (embeddings, метаданные)
- При этом основная информация синхронизируется из amoCRM

## Рекомендации по реализации

1. **Первичная синхронизация**: выполнить полный импорт каталога из amoCRM
2. **Периодическая синхронизация**: настроить n8n workflow на синхронизацию раз в час
3. **Событийная синхронизация**: настроить webhook от amoCRM для мгновенного обновления
4. **Обработка ошибок**: логировать ошибки синхронизации и уведомлять администраторов
5. **Валидация данных**: проверять корректность данных перед сохранением в PostgreSQL

## Примеры использования

### Пример 1: Агент ищет объект по запросу клиента

```
Клиент: "Мне нужен дом с 3 спальнями, бюджет до 10 млн"
  ↓
Агент: векторный поиск в PostgreSQL (products)
  ↓
Находит объекты из каталога amoCRM (синхронизированные)
  ↓
Предлагает клиенту варианты с ценами из каталога
```

### Пример 2: Генерация КП с товарами из каталога

```
Агент определил подходящие объекты
  ↓
proposal-generator: создаёт КП с товарами
  ↓
Товары добавляются в сделку amoCRM через API
  ↓
amoCRM автоматически рассчитывает стоимость
  ↓
КП сохраняется в PostgreSQL с ссылкой на сделку
```

### Пример 3: Синхронизация с 1C

```
1C экспортирует каталог в CSV
  ↓
Менеджер импортирует CSV в amoCRM
  ↓
n8n workflow синхронизирует каталог в PostgreSQL
  ↓
Агент получает обновлённые данные
```

