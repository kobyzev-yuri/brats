# Администрирование Knowledge Base и мультитенантность

## Проблемы и решения

### 1. Администрирование knowledge_base

#### Проблема
- Таблица `products` синхронизируется из amoCRM автоматически
- Таблица `knowledge_base` требует ручного управления chunks
- Нужен удобный способ загрузки, обновления и актуализации документов

#### Решение: Веб-интерфейс KB Admin (реализовано)

**Реализовано**: Веб-интерфейс на базе Streamlit для управления базой знаний.

**Архитектура:**
```
kb-service/
├── api/                    # REST API для управления KB (FastAPI)
│   └── main.py            # CRUD операции, поиск, импорт, статистика
├── web/                    # Веб-интерфейс (Streamlit)
│   ├── kb_admin_app.py    # Основное приложение KB Admin
│   └── KB_ADMIN_USER_GUIDE.md  # Руководство пользователя
├── services/              # Бизнес-логика
│   ├── kb_service.py      # Основной сервис работы с KB
│   ├── embedding_service.py  # Генерация embeddings
│   └── chunking_service.py   # Разбиение текста на chunks
└── models/                # Pydantic модели
    ├── requests.py        # Модели запросов
    └── responses.py       # Модели ответов
```

**Реализованный функционал веб-интерфейса:**

1. **Управление chunks:**
   - ✅ Семантический поиск с фильтрацией (категория, целевая аудитория, min_similarity)
   - ✅ Просмотр результатов поиска с метаданными и схожестью
   - ✅ Редактирование content и metadata (категория, целевая аудитория, приоритет, теги, источник)
   - ✅ Деактивация chunks (soft delete)
   - ✅ Физическое удаление chunks (hard delete)
   - ✅ Редактирование прямо на странице поиска или через отдельную вкладку

2. **Импорт документов:**
   - ✅ Импорт текста с автоматическим chunking
   - ✅ Импорт из файлов (.txt) с поддержкой UTF-8 и CP1251
   - ✅ Настройка параметров chunking (chunk_size, chunk_overlap)
   - ✅ Указание категории, целевой аудитории и источника при импорте

3. **Автоматическая генерация embeddings:**
   - ✅ При создании/обновлении chunk'а автоматически генерируется embedding через OpenAI API
   - ✅ Поддержка OpenAI API и HuggingFace моделей
   - ✅ Обработка ошибок и логирование

4. **Статистика:**
   - ✅ Общая статистика (всего chunks, активных chunks, категорий)
   - ✅ Распределение по категориям
   - ✅ Распределение по целевой аудитории
   - ✅ Распределение по приоритету

5. **Тестирование поиска:**
   - ✅ Тестовый поиск по KB с настройкой параметров
   - ✅ Просмотр результатов с similarity scores
   - ✅ Фильтрация результатов по категориям

**Документация:**
- Полное руководство пользователя: [`kb-service/web/KB_ADMIN_USER_GUIDE.md`](../kb-service/web/KB_ADMIN_USER_GUIDE.md)
- Описание API: `kb-service/api/main.py` (FastAPI автоматическая документация на `/docs`)

**Пример API:**

```python
# kb-admin/api/chunks.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import asyncpg
from openai import OpenAI

router = APIRouter(prefix="/api/chunks", tags=["chunks"])

class ChunkCreate(BaseModel):
    content: str
    metadata: dict
    version: str = "1.0"

class ChunkUpdate(BaseModel):
    content: Optional[str] = None
    metadata: Optional[dict] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None

@router.post("/")
async def create_chunk(
    chunk: ChunkCreate,
    db: asyncpg.Pool = Depends(get_db),
    openai_client: OpenAI = Depends(get_openai)
):
    """Создать новый chunk с автоматической генерацией embedding"""
    # Генерация embedding
    embedding = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=chunk.content
    ).data[0].embedding
    
    # Сохранение в БД
    async with db.acquire() as conn:
        chunk_id = await conn.fetchval("""
            INSERT INTO knowledge_base (content, embedding, metadata, version)
            VALUES ($1, $2::vector, $3, $4)
            RETURNING id
        """, chunk.content, embedding, json.dumps(chunk.metadata), chunk.version)
    
    return {"id": chunk_id, "status": "created"}

@router.put("/{chunk_id}")
async def update_chunk(
    chunk_id: int,
    chunk: ChunkUpdate,
    db: asyncpg.Pool = Depends(get_db),
    openai_client: OpenAI = Depends(get_openai)
):
    """Обновить chunk с пересозданием embedding при изменении content"""
    async with db.acquire() as conn:
        # Получение текущего chunk'а
        current = await conn.fetchrow(
            "SELECT content, metadata FROM knowledge_base WHERE id = $1",
            chunk_id
        )
        
        if not current:
            raise HTTPException(status_code=404, detail="Chunk not found")
        
        # Определение нового content
        new_content = chunk.content if chunk.content else current["content"]
        new_metadata = chunk.metadata if chunk.metadata else current["metadata"]
        
        # Пересоздание embedding, если изменился content
        embedding = None
        if chunk.content:
            embedding = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=new_content
            ).data[0].embedding
        
        # Обновление в БД
        if embedding:
            await conn.execute("""
                UPDATE knowledge_base
                SET content = $1, embedding = $2::vector, metadata = $3,
                    version = COALESCE($4, version), is_active = COALESCE($5, is_active),
                    updated_at = NOW()
                WHERE id = $6
            """, new_content, embedding, json.dumps(new_metadata),
                chunk.version, chunk.is_active, chunk_id)
        else:
            await conn.execute("""
                UPDATE knowledge_base
                SET metadata = $1, version = COALESCE($2, version),
                    is_active = COALESCE($3, is_active), updated_at = NOW()
                WHERE id = $4
            """, json.dumps(new_metadata), chunk.version, chunk.is_active, chunk_id)
    
    return {"id": chunk_id, "status": "updated"}

@router.post("/import")
async def import_chunks(
    file: UploadFile,
    db: asyncpg.Pool = Depends(get_db),
    openai_client: OpenAI = Depends(get_openai)
):
    """Импорт chunks из JSON файла"""
    content = await file.read()
    data = json.loads(content)
    
    imported = 0
    errors = []
    
    async with db.acquire() as conn:
        for chunk_data in data.get("chunks", []):
            try:
                # Генерация embedding
                embedding = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=chunk_data["content"]
                ).data[0].embedding
                
                # Сохранение
                await conn.execute("""
                    INSERT INTO knowledge_base (content, embedding, metadata, version)
                    VALUES ($1, $2::vector, $3, $4)
                """, chunk_data["content"], embedding,
                    json.dumps(chunk_data["metadata"]),
                    chunk_data["metadata"].get("version", "1.0"))
                
                imported += 1
            except Exception as e:
                errors.append({"chunk": chunk_data.get("content", "")[:50], "error": str(e)})
    
    return {"imported": imported, "errors": errors}

@router.post("/test-search")
async def test_search(
    query: str,
    target_audience: str = "both",
    limit: int = 5,
    db: asyncpg.Pool = Depends(get_db),
    openai_client: OpenAI = Depends(get_openai)
):
    """Тестовый поиск по KB для проверки релевантности"""
    # Генерация embedding для запроса
    query_embedding = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    ).data[0].embedding
    
    # Поиск
    async with db.acquire() as conn:
        results = await conn.fetch("""
            SELECT 
                id, content, metadata,
                1 - (embedding <=> $1::vector) as similarity
            FROM knowledge_base
            WHERE is_active = TRUE
              AND (metadata->>'target_audience' = $2 OR metadata->>'target_audience' = 'both')
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """, query_embedding, target_audience, limit)
    
    return [
        {
            "id": r["id"],
            "content": r["content"][:200] + "...",
            "metadata": r["metadata"],
            "similarity": float(r["similarity"])
        }
        for r in results
    ]
```

**Вариант 2: CLI инструмент**

Для быстрого управления через командную строку:

```python
# kb-admin/cli.py
import click
import json
import asyncpg
from openai import OpenAI

@click.group()
def cli():
    """KB Admin CLI"""
    pass

@cli.command()
@click.argument('file', type=click.File('r'))
@click.option('--db-url', envvar='DATABASE_URL')
def import_chunks(file, db_url):
    """Импорт chunks из JSON файла"""
    data = json.load(file)
    # ... импорт логика

@cli.command()
@click.option('--category')
@click.option('--target-audience')
@click.option('--db-url', envvar='DATABASE_URL')
def list_chunks(category, target_audience, db_url):
    """Список chunks с фильтрацией"""
    # ... список логика

@cli.command()
@click.argument('chunk_id', type=int)
@click.option('--content')
@click.option('--metadata')
@click.option('--db-url', envvar='DATABASE_URL')
def update_chunk(chunk_id, content, metadata, db_url):
    """Обновить chunk"""
    # ... обновление логика
```

**Рекомендация:** Использовать оба варианта:
- Веб-интерфейс для регулярного управления
- CLI для автоматизации и скриптов

---

### 2. Мультитенантность для нескольких поселков

#### Проблема
- Может быть несколько поселков (например, "Инноваторы-Клуб", "Зелёный Оазис")
- KB и products должны быть разделены по поселкам
- Агент должен знать, с каким поселком работает

#### Решение: Добавить поле `village_id` (или `settlement_id`)

**Обновление схемы:**

```sql
-- Таблица поселков
CREATE TABLE villages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,  -- "Инноваторы-Клуб"
    code VARCHAR(50) UNIQUE,  -- "innovatory-club"
    amocrm_account_id INTEGER,  -- ID аккаунта amoCRM (если разные аккаунты)
    settings JSONB,  -- Настройки поселка
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Обновление knowledge_base
ALTER TABLE knowledge_base
ADD COLUMN village_id INTEGER REFERENCES villages(id);

CREATE INDEX ON knowledge_base (village_id, is_active);

-- Обновление products
ALTER TABLE products
ADD COLUMN village_id INTEGER REFERENCES villages(id);

CREATE INDEX ON products (village_id, status);

-- Обновление других таблиц
ALTER TABLE conversations
ADD COLUMN village_id INTEGER REFERENCES villages(id);

ALTER TABLE proposals
ADD COLUMN village_id INTEGER REFERENCES villages(id);
```

**Использование в агенте:**

```python
# sales-agent/domain/product_search.py
async def search_products_for_village(
    village_id: int,
    query: str,
    budget_min: float = None,
    budget_max: float = None
):
    """Поиск объектов для конкретного поселка"""
    query_embedding = generate_embedding(query)
    
    results = await db.fetch("""
        SELECT 
            id, name, description, price_current,
            1 - (description_embedding <=> $1::vector) as similarity
        FROM products
        WHERE village_id = $2
          AND status = 'available'
          AND ($3 IS NULL OR price_current >= $3)
          AND ($4 IS NULL OR price_current <= $4)
          AND 1 - (description_embedding <=> $1::vector) > 0.6
        ORDER BY description_embedding <=> $1::vector
        LIMIT 5
    """, query_embedding, village_id, budget_min, budget_max)
    
    return results

# sales-agent/llm/rag.py
async def search_knowledge_base_for_village(
    village_id: int,
    query: str,
    target_audience: str = "both"
):
    """Поиск в KB для конкретного поселка"""
    query_embedding = generate_embedding(query)
    
    results = await db.fetch("""
        SELECT 
            id, content, metadata,
            1 - (embedding <=> $1::vector) as similarity
        FROM knowledge_base
        WHERE village_id = $2
          AND is_active = TRUE
          AND (metadata->>'target_audience' = $3 OR metadata->>'target_audience' = 'both')
        ORDER BY embedding <=> $1::vector
        LIMIT 5
    """, query_embedding, village_id, target_audience)
    
    return results
```

**Определение поселка для диалога:**

```python
# sales-agent/domain/conversation.py
async def get_conversation_village(conversation_id: int):
    """Определить поселок для диалога"""
    # Вариант 1: Из conversation.village_id
    conversation = await db.fetchrow(
        "SELECT village_id FROM conversations WHERE id = $1",
        conversation_id
    )
    
    if conversation and conversation["village_id"]:
        return conversation["village_id"]
    
    # Вариант 2: Из лида в amoCRM (кастомное поле)
    conversation = await db.fetchrow(
        "SELECT amocrm_lead_id FROM conversations WHERE id = $1",
        conversation_id
    )
    
    if conversation and conversation["amocrm_lead_id"]:
        # Запрос к amoCRM API для получения village_id из кастомного поля
        village_id = await get_village_from_amocrm(conversation["amocrm_lead_id"])
        # Сохранение в conversation
        await db.execute(
            "UPDATE conversations SET village_id = $1 WHERE id = $2",
            village_id, conversation_id
        )
        return village_id
    
    # Вариант 3: По умолчанию (первый активный поселок)
    default_village = await db.fetchval(
        "SELECT id FROM villages WHERE is_active = TRUE ORDER BY id LIMIT 1"
    )
    return default_village
```

**Администрирование KB с мультитенантностью:**

В веб-интерфейсе добавить выбор поселка:
- При создании/редактировании chunk'а выбирать поселок
- Фильтрация списка chunks по поселку
- Массовый импорт с указанием поселка

---

### 3. Мультимодальная модель для анализа изображений

#### Вопрос
Нужна ли мультимодальная модель для анализа изображений объектов или достаточно ссылок?

#### Анализ вариантов

**Вариант 1: Только ссылки (простой подход)**

**Плюсы:**
- ✅ Простота реализации
- ✅ Низкие затраты (нет необходимости в мультимодальной модели)
- ✅ Быстрая работа агента
- ✅ Менеджеры могут обновлять ссылки вручную

**Минусы:**
- ❌ Агент не может анализировать изображения
- ❌ Нет автоматической проверки соответствия изображения описанию
- ❌ Клиент должен сам открывать ссылки

**Реализация:**
```sql
CREATE TABLE products (
    ...
    photos_urls TEXT[],  -- Массив ссылок на фото
    floor_plan_url VARCHAR(500),  -- Ссылка на планировку
    ...
);
```

Агент просто упоминает ссылки в ответе:
```
"У нас есть несколько вариантов. Посмотрите фото: [ссылка]
Планировки доступны здесь: [ссылка]"
```

**Вариант 2: Мультимодальная модель (продвинутый подход)**

**Плюсы:**
- ✅ Агент может анализировать изображения и описывать их
- ✅ Автоматическая проверка соответствия изображения описанию
- ✅ Более персонализированные рекомендации
- ✅ Агент может отвечать на вопросы о визуальных характеристиках

**Минусы:**
- ❌ Выше затраты (мультимодальная модель дороже)
- ❌ Сложнее реализация
- ❌ Нужно хранить embeddings изображений
- ❌ Медленнее работа (анализ изображений)

**Реализация:**

```sql
-- Добавить таблицу для embeddings изображений
CREATE TABLE product_images (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    image_url VARCHAR(500),
    image_embedding vector(1536),  -- Embedding изображения
    description TEXT,  -- Описание изображения (генерируется моделью)
    image_type VARCHAR(50),  -- 'photo', 'floor_plan', 'infrastructure'
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON product_images USING ivfflat (image_embedding vector_cosine_ops);
CREATE INDEX ON product_images (product_id);
```

```python
# Генерация embedding для изображения
from openai import OpenAI

openai_client = OpenAI()

async def process_product_image(image_url: str, product_id: int):
    """Обработка изображения продукта через мультимодальную модель"""
    # Загрузка изображения
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(image_url)
        image_data = response.content
    
    # Генерация описания через GPT-4 Vision
    description_response = openai_client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Опиши это изображение недвижимости. Укажи стиль, состояние, особенности."},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        max_tokens=300
    )
    description = description_response.choices[0].message.content
    
    # Генерация embedding для изображения (через CLIP или аналогичную модель)
    # Для примера используем описание для генерации embedding
    image_embedding = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=description
    ).data[0].embedding
    
    # Сохранение в БД
    await db.execute("""
        INSERT INTO product_images (product_id, image_url, image_embedding, description)
        VALUES ($1, $2, $3::vector, $4)
    """, product_id, image_url, image_embedding, description)
    
    return description
```

**Использование в агенте:**

```python
# Поиск объектов по описанию изображения
async def search_products_by_image_description(
    image_description: str,
    village_id: int
):
    """Поиск объектов по описанию изображения"""
    query_embedding = generate_embedding(image_description)
    
    results = await db.fetch("""
        SELECT DISTINCT
            p.id, p.name, p.description, p.price_current,
            pi.description as image_description,
            1 - (pi.image_embedding <=> $1::vector) as similarity
        FROM products p
        JOIN product_images pi ON p.id = pi.product_id
        WHERE p.village_id = $2
          AND p.status = 'available'
          AND 1 - (pi.image_embedding <=> $1::vector) > 0.6
        ORDER BY pi.image_embedding <=> $1::vector
        LIMIT 5
    """, query_embedding, village_id)
    
    return results
```

#### Рекомендация

**Для MVP: Использовать только ссылки**

**Причины:**
1. Простота реализации — быстрее запуск
2. Низкие затраты — нет необходимости в мультимодальной модели
3. Достаточная функциональность — клиенты могут сами посмотреть фото
4. Менеджеры могут обновлять ссылки вручную

**Для будущего развития: Добавить мультимодальность**

Когда система будет работать и появятся ресурсы:
1. Добавить анализ изображений через GPT-4 Vision или аналогичную модель
2. Генерировать описания изображений автоматически
3. Использовать для более точных рекомендаций

**Компромиссный вариант:**

Использовать мультимодальную модель только для:
- Автоматической генерации описаний изображений при загрузке
- Проверки соответствия изображения описанию объекта
- Но не для каждого запроса клиента (слишком дорого)

---

## Итоговая архитектура

```
┌─────────────────────────────────────────────────────────┐
│              KB Admin (веб-интерфейс + CLI)             │
│  - Управление chunks для каждого поселка                │
│  - Импорт/экспорт документов                            │
│  - Автоматическая генерация embeddings                  │
│  - Тестирование поиска                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│              PostgreSQL (мультитенантность)             │
│                                                          │
│  villages (поселки)                                     │
│    ├─ id, name, code                                    │
│                                                          │
│  knowledge_base (KB для каждого поселка)              │
│    ├─ village_id                                        │
│    ├─ content, embedding                                │
│                                                          │
│  products (объекты для каждого поселка)                │
│    ├─ village_id                                        │
│    ├─ description_embedding                             │
│    ├─ photos_urls (ссылки)                             │
│    └─ product_images (опционально, для мультимодальности)│
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────┐
│              Нейропродажник                             │
│  - Определяет village_id для диалога                   │
│  - Ищет в KB и products для конкретного поселка        │
│  - Использует ссылки на изображения (или анализирует)   │
└─────────────────────────────────────────────────────────┘
```

## План реализации

### Этап 1: MVP (без мультимодальности)
1. ✅ Создать таблицу `villages`
2. ✅ Добавить `village_id` в `knowledge_base` и `products`
3. ✅ Создать веб-интерфейс для управления KB
4. ✅ Использовать только ссылки на изображения

### Этап 2: Развитие
1. Добавить мультимодальную модель для анализа изображений
2. Автоматическая генерация описаний изображений
3. Расширенный поиск по изображениям





