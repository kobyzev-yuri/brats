# Справочник по конфигурации проекта

> ⚠️ **ВАЖНО**: Этот документ является единым источником правды для конфигурации проекта. Все примеры кода в документации должны ссылаться на этот документ или на `config.env.example`.

## Расположение файлов конфигурации

- **Основной файл конфигурации**: `kb-service/config.env.example` (скопировать в `kb-service/config.env`)
- **Корневой файл конфигурации**: `config.env.example` (скопировать в `config.env`)

---

## LLM Configuration (Генерация текста)

### Провайдер LLM

```env
LLM_PROVIDER=openai  # 'openai' или 'ollama'
```

### OpenAI/ProxyAPI Configuration

```env
# API ключ (получить на https://api.proxyapi.ru или https://platform.openai.com)
OPENAI_API_KEY=your-api-key-here

# Base URL (для proxyapi.ru или прямой OpenAI)
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
# или
# OPENAI_BASE_URL=https://api.openai.com/v1

# Модель для генерации текста
OPENAI_MODEL=gpt-4o

# Параметры генерации
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT=60
```

**Важно**: 
- Модель `OPENAI_MODEL` используется для генерации ответов агента
- В примерах кода используйте `os.getenv("OPENAI_MODEL")` или `LLMService`
- Не используйте хардкод `model="gpt-4o"` в коде

---

## Embedding Configuration (Векторные представления)

### Провайдер Embeddings

```env
EMBEDDING_PROVIDER=openai  # 'openai' или 'huggingface'
```

### OpenAI Embeddings

```env
# Модель для генерации embeddings (OpenAI)
EMBEDDING_MODEL=text-embedding-3-small  # или text-embedding-3-large
EMBEDDING_DIMENSION=1536  # для text-embedding-3-small
# или
# EMBEDDING_DIMENSION=3072  # для text-embedding-3-large
```

**Важно**:
- Размерность вектора должна соответствовать модели
- Таблица в PostgreSQL должна иметь правильный тип: `vector(1536)` или `vector(3072)`

### HuggingFace Embeddings

```env
# Модель для генерации embeddings (HuggingFace)
HF_MODEL_NAME=intfloat/multilingual-e5-base
HF_EMBEDDING_DIMENSION=768
```

**Важно**:
- Размерность вектора должна соответствовать модели
- Таблица в PostgreSQL должна иметь правильный тип: `vector(768)`
- Модель загружается локально при первом использовании

### Использование в коде

**❌ ПЛОХО: хардкод модели**
```python
embedding = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=text
).data[0].embedding
```

**✅ ХОРОШО: использование сервиса**
```python
from services.embedding_service import EmbeddingService

embedding_service = EmbeddingService()  # Читает конфигурацию из config.env
embedding = embedding_service.generate_embedding(text)
```

**✅ ХОРОШО: через переменные окружения (если нужен прямой вызов)**
```python
import os
from openai import OpenAI

openai_client = OpenAI()
model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
embedding = openai_client.embeddings.create(
    model=model,
    input=text
).data[0].embedding
```

---

## Database Configuration

```env
# PostgreSQL connection string
DATABASE_URL=postgresql://postgres:password@localhost:5432/brats

# Таблица для базы знаний
KB_TABLE=knowledge_base
```

---

## Chunking Configuration

```env
# Размеры чанков для разных типов контента
CHUNK_SIZE_PRODUCT_INFO=3000
CHUNK_SIZE_SALES_SCRIPT=2000
CHUNK_SIZE_OBJECTION_HANDLING=1500
CHUNK_SIZE_DOCUMENTATION=3000

# Перекрытия (overlap) для сохранения контекста
CHUNK_OVERLAP_PRODUCT_INFO=300
CHUNK_OVERLAP_SALES_SCRIPT=200
CHUNK_OVERLAP_OBJECTION_HANDLING=150
CHUNK_OVERLAP_DOCUMENTATION=300

# Использовать умное разбиение по границам предложений/абзацев
CHUNK_USE_SMART_BOUNDARIES=true
```

---

## API Configuration

```env
# KB Service API
API_HOST=0.0.0.0
API_PORT=8001
KB_API_URL=http://localhost:8001

# Sales Agent API (когда будет реализован)
SALES_AGENT_URL=http://localhost:8000
```

---

## n8n Configuration

```env
# URL для доступа к n8n
N8N_URL=http://localhost:5678
N8N_PROTOCOL=http
N8N_HOST=0.0.0.0
N8N_PORT=5678

# Webhook URL для n8n
N8N_WEBHOOK_URL=http://localhost:5678/

# Аутентификация n8n
N8N_BASIC_AUTH_ACTIVE=false
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=changeme

# Первый пользователь n8n
N8N_USER_FIRST_NAME=Admin
N8N_USER_LAST_NAME=User
N8N_USER_EMAIL=admin@example.com
N8N_USER_PASSWORD=changeme

# Лицензионный ключ n8n
N8N_LICENSE_KEY=your-license-key-here
```

---

## Примеры конфигурации

### Пример 1: OpenAI для всего (LLM + Embeddings)

```env
# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

### Пример 2: OpenAI для LLM, HuggingFace для Embeddings

```env
# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o

# Embeddings
EMBEDDING_PROVIDER=huggingface
HF_MODEL_NAME=intfloat/multilingual-e5-base
HF_EMBEDDING_DIMENSION=768
```

**Важно**: При использовании HuggingFace нужно изменить тип колонки в PostgreSQL:
```sql
ALTER TABLE knowledge_base ALTER COLUMN embedding TYPE vector(768);
```

### Пример 3: Локальная модель Ollama (если поддерживается)

```env
# LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Embeddings
EMBEDDING_PROVIDER=huggingface
HF_MODEL_NAME=intfloat/multilingual-e5-base
HF_EMBEDDING_DIMENSION=768
```

---

## Важные замечания

### 1. Размерность векторов

Размерность вектора embeddings должна соответствовать:
- Типу колонки в PostgreSQL (`vector(1536)`, `vector(768)`, `vector(3072)`)
- Модели, указанной в конфигурации

### 2. Изменение модели embeddings

Если вы меняете модель embeddings:

1. **Обновите конфигурацию** в `config.env`
2. **Измените тип колонки** в PostgreSQL:
   ```sql
   ALTER TABLE knowledge_base ALTER COLUMN embedding TYPE vector(768);
   ```
3. **Пересоздайте индексы**:
   ```sql
   DROP INDEX IF EXISTS idx_knowledge_base_embedding;
   CREATE INDEX idx_knowledge_base_embedding 
       ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   ```
4. **Перегенерируйте embeddings** для существующих данных (если необходимо)

### 3. Использование в коде

**Всегда используйте сервисы** (`EmbeddingService`, `LLMService`) вместо прямых вызовов API. Сервисы автоматически читают конфигурацию из `config.env`.

### 4. Документация

При написании документации:
- **Не используйте хардкод моделей** в примерах кода
- **Ссылайтесь на этот документ** или на `config.env.example`
- **Используйте сервисы** в примерах кода

---

## Ссылки

- `kb-service/config.env.example` - пример конфигурации KB Service
- `config.env.example` - пример общей конфигурации проекта
- `docs/DOCUMENTATION_IMPROVEMENT_PLAN.md` - план улучшения документации

---

## Дата обновления
2026-02-08

## Последнее обновление
2026-02-08













