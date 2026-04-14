# План улучшения документации: устранение хардкода моделей

## Проблема

В документации присутствуют примеры кода с явным указанием моделей (например, `text-embedding-3-small`, `gpt-4`), которые не соответствуют реальной конфигурации проекта. Это создает путаницу и несоответствие между документацией и реальной реализацией.

### Текущая конфигурация (из `kb-service/config.env.example`)

```env
# Реальная конфигурация
EMBEDDING_PROVIDER=openai  # или huggingface
EMBEDDING_MODEL=text-embedding-3-small  # для OpenAI
HF_MODEL_NAME=intfloat/multilingual-e5-base  # для HuggingFace
OPENAI_MODEL=gpt-4o
```

### Проблемные места в документации

1. **Примеры кода с хардкодом моделей** вместо использования переменных окружения
2. **Несоответствие между документацией и конфигурацией** (в документации `text-embedding-3-small`, в конфиге может быть `intfloat/multilingual-e5-base`)
3. **Дублирование информации** о моделях в разных местах
4. **Отсутствие единого источника правды** для конфигурации

---

## Анализ проблемных файлов

### 1. `sales-analytic/docs/ANALYTICS_EVENTS_FOR_KB.md`

**Проблемы:**
- Строки 113, 210, 363: `model="text-embedding-3-small"` (хардкод)
- Строки 97, 194: `model="gpt-4"` (должно быть `gpt-4o` или из конфига)

**Исправление:**
- Использовать `os.getenv("EMBEDDING_MODEL")` или `EmbeddingService`
- Использовать `os.getenv("OPENAI_MODEL")` или `LLMService`

### 2. `docs/KB_ADMINISTRATION_AND_MULTITENANCY.md`

**Проблемы:**
- Строки 101, 141, 183, 212, 532: `model="text-embedding-3-small"` (хардкод)
- Строка 515: `model="gpt-4-vision-preview"` (специфичная модель)

**Исправление:**
- Заменить на использование сервисов или переменных окружения
- Добавить примечание о необходимости настройки конфига

### 3. `docs/KB_STRUCTURE.md`

**Проблемы:**
- Строки 785, 1022, 1042: `model="text-embedding-3-small"` (хардкод)
- Строка 26: упоминание `text-embedding-3-small` как единственной модели

**Исправление:**
- Использовать абстракцию через `EmbeddingService`
- Указать, что модель настраивается через конфиг

### 4. `docs/AMOCRM_CATALOG_INTEGRATION.md`

**Проблемы:**
- Строки 240, 308: `model="text-embedding-3-small"` (хардкод)

### 5. `docs/POSTGRESQL_ARCHITECTURE_EXPLAINED.md`

**Проблемы:**
- Строка 131: `model="text-embedding-3-small"` (хардкод)

### 6. `kb-service/RAG_DLP_INTEGRATION.md`

**Проблемы:**
- Строки 122, 168: `model="gpt-4o"` (хардкод, хотя соответствует конфигу)
- Строка 285: `EMBEDDING_MODEL=text-embedding-3-small` (пример конфига, но не соответствует реальному `HF_MODEL_NAME`)

### 7. `kb-service/IMPLEMENTATION_NOTES.md`

**Проблемы:**
- Строки 30, 60: упоминание `text-embedding-3-small` как единственной модели

### 8. `kb-service/SUMMARY.md`

**Проблемы:**
- Строка 20: упоминание `text-embedding-3-small` как единственной модели

---

## План исправления

### Этап 1: Создание единого источника правды

1. **Создать документ `docs/CONFIGURATION_REFERENCE.md`**
   - Описание всех переменных окружения
   - Примеры конфигурации для разных сценариев
   - Ссылки на этот документ из всех остальных

2. **Обновить `kb-service/config.env.example`**
   - Добавить комментарии о том, что это основной источник конфигурации
   - Указать, что документация должна ссылаться на этот файл

### Этап 2: Исправление примеров кода

**Принципы:**
1. **Не использовать хардкод моделей** в примерах кода
2. **Использовать сервисы** (`EmbeddingService`, `LLMService`) вместо прямых вызовов API
3. **Ссылаться на переменные окружения** через `os.getenv()` или через сервисы
4. **Добавлять примечания** о необходимости настройки конфига

**Шаблон для примеров:**

```python
# ❌ ПЛОХО: хардкод модели
embedding = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=text
).data[0].embedding

# ✅ ХОРОШО: использование сервиса
from services.embedding_service import EmbeddingService

embedding_service = EmbeddingService()
embedding = embedding_service.generate_embedding(text)

# ✅ ХОРОШО: через переменные окружения (если нужен прямой вызов)
import os
from openai import OpenAI

openai_client = OpenAI()
model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
embedding = openai_client.embeddings.create(
    model=model,
    input=text
).data[0].embedding
```

### Этап 3: Обновление документации

1. **Заменить все хардкоды моделей** на использование сервисов или переменных окружения
2. **Добавить ссылки на `CONFIGURATION_REFERENCE.md`** в начале каждого документа с примерами кода
3. **Убрать упоминания конкретных моделей** из описаний, заменить на "модель из конфигурации"

### Этап 4: Создание скриптов и их документации

**Принципы для скриптов:**
1. **Скрипты должны читать конфигурацию** из `config.env` или переменных окружения
2. **Не использовать хардкод** моделей в скриптах
3. **Документация скриптов** должна ссылаться на `CONFIGURATION_REFERENCE.md`

**Структура документации скрипта:**
```markdown
# Название скрипта

## Описание
[Что делает скрипт]

## Требования
- Настроенный `config.env` (см. [CONFIGURATION_REFERENCE.md](../docs/CONFIGURATION_REFERENCE.md))
- [Другие требования]

## Использование
[Примеры использования]

## Конфигурация
Скрипт использует следующие переменные из `config.env`:
- `EMBEDDING_PROVIDER` - провайдер embeddings
- `HF_MODEL_NAME` - модель HuggingFace (если используется)
- [Другие переменные]

## Примеры
[Примеры кода с использованием сервисов]
```

---

## Рекомендации по написанию документации

### 1. Единый источник правды

- **Конфигурация**: `kb-service/config.env.example` - единственный источник правды для конфигурации
- **Ссылки**: Все документы должны ссылаться на этот файл или на `CONFIGURATION_REFERENCE.md`

### 2. Примеры кода

**✅ ХОРОШО:**
- Использование сервисов (`EmbeddingService`, `LLMService`)
- Использование переменных окружения через `os.getenv()`
- Добавление комментариев о необходимости настройки конфига
- Ссылки на документацию по конфигурации

**❌ ПЛОХО:**
- Хардкод моделей (`model="text-embedding-3-small"`)
- Прямые вызовы API без абстракции
- Упоминание конкретных моделей как единственного варианта
- Отсутствие ссылок на конфигурацию

### 3. Структура документации

**Для каждого документа с примерами кода:**
1. **Введение** - описание цели документа
2. **Требования** - ссылка на `CONFIGURATION_REFERENCE.md`
3. **Примеры кода** - с использованием сервисов или переменных окружения
4. **Примечания** - о необходимости настройки конфига

### 4. Документация скриптов

**Обязательные разделы:**
- Описание назначения
- Требования (конфигурация)
- Использование
- Примеры
- Ссылки на конфигурацию

### 5. Обновление документации

**При изменении конфигурации:**
1. Обновить `config.env.example`
2. Обновить `CONFIGURATION_REFERENCE.md`
3. Проверить все документы на соответствие
4. Обновить примеры кода, если необходимо

---

## Приоритет исправлений

### Высокий приоритет (критично)
1. `sales-analytic/docs/ANALYTICS_EVENTS_FOR_KB.md` - содержит много примеров с хардкодом
2. `docs/KB_ADMINISTRATION_AND_MULTITENANCY.md` - содержит много примеров
3. Создание `docs/CONFIGURATION_REFERENCE.md` - единый источник правды

### Средний приоритет
4. `docs/KB_STRUCTURE.md` - содержит примеры
5. `docs/AMOCRM_CATALOG_INTEGRATION.md` - содержит примеры
6. `docs/POSTGRESQL_ARCHITECTURE_EXPLAINED.md` - содержит примеры

### Низкий приоритет (можно оставить как есть с примечаниями)
7. `kb-service/RAG_DLP_INTEGRATION.md` - примеры конфига, но нужно добавить примечание
8. `kb-service/IMPLEMENTATION_NOTES.md` - исторические заметки, можно добавить примечание
9. `kb-service/SUMMARY.md` - краткая сводка, можно добавить примечание

---

## Примеры исправлений

### Пример 1: Исправление `ANALYTICS_EVENTS_FOR_KB.md`

**Было:**
```python
embedding = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=content
).data[0].embedding
```

**Стало:**
```python
# Использование EmbeddingService (читает конфигурацию из config.env)
from services.embedding_service import EmbeddingService

embedding_service = EmbeddingService()
embedding = embedding_service.generate_embedding(content)
```

### Пример 2: Исправление `KB_STRUCTURE.md`

**Было:**
```python
def generate_embedding(text: str) -> list:
    """Генерация embedding для текста через OpenAI"""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
```

**Стало:**
```python
def generate_embedding(text: str) -> list:
    """
    Генерация embedding для текста.
    
    Использует модель из конфигурации (config.env):
    - EMBEDDING_PROVIDER (openai или huggingface)
    - EMBEDDING_MODEL или HF_MODEL_NAME
    """
    from services.embedding_service import EmbeddingService
    
    embedding_service = EmbeddingService()
    return embedding_service.generate_embedding(text)
```

---

## Чек-лист для проверки документации

При создании или обновлении документации проверьте:

- [ ] Нет хардкода моделей в примерах кода
- [ ] Используются сервисы (`EmbeddingService`, `LLMService`) или переменные окружения
- [ ] Есть ссылка на `CONFIGURATION_REFERENCE.md` или `config.env.example`
- [ ] Упоминания моделей сопровождаются примечанием о конфигурации
- [ ] Примеры кода соответствуют реальной реализации
- [ ] Документация скриптов содержит раздел о конфигурации

---

## Следующие шаги

1. ✅ Создать этот план (вы здесь)
2. ⏳ Создать `docs/CONFIGURATION_REFERENCE.md`
3. ⏳ Исправить файлы высокого приоритета
4. ⏳ Исправить файлы среднего приоритета
5. ⏳ Добавить примечания в файлы низкого приоритета
6. ⏳ Обновить все ссылки на конфигурацию
7. ⏳ Проверить все документы по чек-листу

---

## Дата создания
2026-02-08

## Автор
AI Assistant (по запросу пользователя)













