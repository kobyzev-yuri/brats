# Использование DLP сервиса для нейропродажника

## ✅ Да, DLP сервис можно и нужно использовать!

DLP сервис из `kb-service` можно переиспользовать в нейропродажнике и в **цепочке n8n (чат с сайта)** для обезличивания персональных данных перед отправкой в зарубежные LLM (GPT-4o через proxyapi.ru).

---

## ⚠️ Защита в цепочке n8n (чат с сайта)

Сейчас чат с сайта идёт по цепочке: **сайт → n8n webhook → KB Search → LLM ProxyAPI (GPT-4o)**. В промпт LLM попадают:

- **Сообщение пользователя** — может содержать имя, телефон, email (ПДн).
- **additional_context** — карточка объекта, цена, ссылки (менее чувствительно, но может содержать идентификаторы).
- **metadata** — visitor_id, session_id, page_url.

**Без DLP эти данные уходят в зарубежный API (proxyapi.ru → GPT-4o).** Для соответствия 152-ФЗ и политике DLP их нужно обезличивать **до** вызова LLM.

### Что сделано

- В **kb-service** добавлены HTTP-эндпоинты DLP (порт 8001):
  - **POST /api/dlp/sanitize-text** — тело `{ "text": "..." }`, ответ `{ "sanitized_text": "..." }` (маскирование телефонов, email, паспортов и т.д. в тексте).
  - **POST /api/dlp/sanitize** — тело `{ "data": { ... } }`, ответ `{ "sanitized_data": { ... } }` (обезличивание JSON).
  - **POST /api/dlp/sanitize-conversation-context** — тело `{ "data": { "slots": ..., "metadata": ... } }` (контекст диалога).

### Как включить DLP в n8n

1. **Перед узлом «LLM ProxyAPI»** добавить вызовы kb-service:
   - Узел **HTTP Request**: `POST http://localhost:8001/api/dlp/sanitize-text`, body `{ "text": "{{ $json.message }}" }` → сохранить `sanitized_text` в контекст (например, в следующий Code или в тот же item).
   - Для блока «Контекст от канала/аналитики» (additional_context + metadata): при необходимости вызвать `POST /api/dlp/sanitize` с `{ "data": { "additional_context": "...", "metadata": { ... } } }` и подставлять обезличенный результат в промпт.
2. В узле **Format KB Context** (или перед LLM) использовать в промпте **обезличенные** значения: `sanitized_text` вместо сырого `message`, обезличенный контекст вместо сырого.
3. **Ответ LLM** клиенту можно отдавать как есть (он не содержит ПДн пользователя). Данные для создания лида (телефон, имя) извлекаются в n8n из **исходного** сообщения (узлом «Maybe Create Lead») и уходят только в amocrm-api и AmoCRM, не в LLM.

Итог: **сообщение и контекст, уходящие в LLM, должны проходить через DLP; извлечение контакта для AmoCRM — из исходного сообщения, без отправки в зарубежный API.**

---

## Почему это важно для нейропродажника?

Нейропродажник работает с:
- ✅ **Персональными данными клиентов** (имя, телефон, email)
- ✅ **Данными из amoCRM** (lead_id, contact_id, deal_id)
- ✅ **Контекстом диалога** (slots с информацией о клиенте)
- ✅ **Историей сообщений** (могут содержать ПДн)

**При использовании зарубежных LLM (GPT-4o через proxyapi.ru) все эти данные должны быть обезличены!**

---

## Архитектура интеграции

```
┌─────────────────────┐
│ Нейропродажник      │
│ (sales-agent)       │
│                     │
│ • Диалог-менеджер   │
│ • FSM состояния     │
│ • Slots с ПДн       │
└──────────┬──────────┘
           │
           ↓ (перед отправкой в LLM)
┌─────────────────────┐
│ DLP Service         │  ← Переиспользование из kb-service
│ (обезличивание)     │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ LLM (GPT-4o)        │
│ через proxyapi.ru    │
└─────────────────────┘
```

---

## Варианты интеграции

### Вариант 1: Прямое использование DLP сервиса (рекомендуется)

**Преимущества:**
- ✅ Единый источник обезличивания
- ✅ Консистентность правил
- ✅ Легкое обновление правил в одном месте

**Реализация:**

```python
# sales-agent/services/dlp_integration.py
import sys
from pathlib import Path

# Добавляем путь к kb-service для импорта DLP
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "kb-service"))

from services.dlp_service import get_dlp_service

class SalesAgentDLP:
    """Обёртка DLP сервиса для нейропродажника"""
    
    def __init__(self):
        self.dlp = get_dlp_service()
    
    def sanitize_conversation_slots(self, slots: dict) -> dict:
        """Обезличивание слотов диалога"""
        return self.dlp.sanitize_conversation_context({
            "slots": slots
        })["slots"]
    
    def sanitize_message(self, message: str) -> str:
        """Обезличивание текста сообщения"""
        return self.dlp._mask_text(message)
    
    def sanitize_amocrm_data(self, amocrm_data: dict) -> dict:
        """Обезличивание данных из amoCRM"""
        return self.dlp.sanitize_for_llm(amocrm_data)
```

### Вариант 2: DLP как отдельный сервис (микросервисная архитектура)

**Преимущества:**
- ✅ Независимое развертывание
- ✅ Использование из разных сервисов
- ✅ Масштабируемость

**Реализация:**

```python
# sales-agent/services/dlp_client.py
import httpx
from typing import Dict, Any

class DLPClient:
    """Клиент для DLP сервиса через HTTP"""
    
    def __init__(self, dlp_service_url: str = "http://localhost:8001"):
        self.base_url = f"{dlp_service_url}/api/dlp"
    
    async def sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Обезличивание данных через DLP API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/sanitize",
                json={"data": data}
            )
            response.raise_for_status()
            return response.json()["sanitized_data"]
```

**DLP endpoints уже добавлены в kb-service** (`api/dlp_endpoints.py`): `POST /api/dlp/sanitize-text`, `POST /api/dlp/sanitize`, `POST /api/dlp/sanitize-conversation-context`. См. раздел «Защита в цепочке n8n» выше.

---

## Пример использования в нейропродажнике

### Пример 1: Обезличивание перед генерацией ответа

```python
# sales-agent/agent/dialogue_manager.py
from services.dlp_integration import SalesAgentDLP

class DialogueManager:
    def __init__(self):
        self.dlp = SalesAgentDLP()
        self.llm_service = LLMService()  # GPT-4o через proxyapi.ru
    
    async def generate_response(
        self,
        user_message: str,
        conversation_slots: dict,
        amocrm_context: dict = None
    ) -> str:
        """
        Генерация ответа с автоматическим обезличиванием
        """
        # Шаг 1: Обезличиваем слоты диалога
        sanitized_slots = self.dlp.sanitize_conversation_slots(conversation_slots)
        
        # Шаг 2: Обезличиваем сообщение пользователя
        sanitized_message = self.dlp.sanitize_message(user_message)
        
        # Шаг 3: Обезличиваем контекст из amoCRM
        sanitized_amocrm = {}
        if amocrm_context:
            sanitized_amocrm = self.dlp.sanitize_amocrm_data(amocrm_context)
        
        # Шаг 4: Формируем промпт с обезличенными данными
        system_prompt = f"""
        Ты - профессиональный продавец недвижимости.
        
        Контекст диалога:
        {json.dumps(sanitized_slots, ensure_ascii=False)}
        
        Данные из CRM:
        {json.dumps(sanitized_amocrm, ensure_ascii=False)}
        """
        
        # Шаг 5: Генерируем ответ через LLM
        response = await self.llm_service.generate_response(
            messages=[{"role": "user", "content": sanitized_message}],
            system_prompt=system_prompt
        )
        
        return response["response"]
```

### Пример 2: Обезличивание при работе с RAG

```python
# sales-agent/agent/rag_dialogue_manager.py
from services.dlp_integration import SalesAgentDLP
from services.rag_service import get_rag_service  # Из kb-service

class RAGDialogueManager:
    def __init__(self):
        self.dlp = SalesAgentDLP()
        self.rag_service = get_rag_service()  # Уже использует DLP внутри
    
    async def generate_response_with_kb(
        self,
        user_message: str,
        conversation_slots: dict
    ) -> str:
        """
        Генерация ответа с использованием KB и RAG
        DLP уже встроен в rag_service
        """
        # Обезличиваем слоты для контекста
        sanitized_slots = self.dlp.sanitize_conversation_slots(conversation_slots)
        
        # Используем RAG (DLP уже внутри)
        result = await self.rag_service.generate_response(
            query=user_message,
            context={"slots": sanitized_slots},
            category="sales_script",
            sanitize_context=True  # Дополнительная защита
        )
        
        return result["response"]
```

### Пример 3: Обезличивание при генерации КП

```python
# sales-agent/proposal_generator.py
from services.dlp_integration import SalesAgentDLP

class ProposalGenerator:
    def __init__(self):
        self.dlp = SalesAgentDLP()
        self.llm_service = LLMService()
    
    async def generate_proposal(
        self,
        client_requirements: dict,
        selected_products: list,
        amocrm_deal_data: dict
    ) -> dict:
        """
        Генерация коммерческого предложения
        """
        # Обезличиваем все данные перед отправкой в LLM
        sanitized_requirements = self.dlp.sanitize_for_llm(client_requirements)
        sanitized_products = [self.dlp.sanitize_for_llm(p) for p in selected_products]
        sanitized_deal = self.dlp.sanitize_amocrm_data(amocrm_deal_data)
        
        # Формируем промпт для генерации КП
        prompt = f"""
        Сгенерируй коммерческое предложение на основе:
        
        Требования клиента:
        {json.dumps(sanitized_requirements, ensure_ascii=False)}
        
        Выбранные объекты:
        {json.dumps(sanitized_products, ensure_ascii=False)}
        
        Данные сделки:
        {json.dumps(sanitized_deal, ensure_ascii=False)}
        """
        
        # Генерируем КП через LLM
        proposal = await self.llm_service.generate_response(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="Ты - эксперт по составлению коммерческих предложений"
        )
        
        return {
            "proposal_text": proposal["response"],
            "original_requirements": client_requirements,  # Сохраняем оригинал локально
            "original_products": selected_products
        }
```

---

## Интеграция в FSM нейропродажника

```python
# sales-agent/agent/fsm_states.py
from services.dlp_integration import SalesAgentDLP

class SalesAgentFSM:
    def __init__(self):
        self.dlp = SalesAgentDLP()
        self.current_state = "GREETING"
        self.slots = {}
    
    async def process_message(self, message: str, channel: str):
        """
        Обработка сообщения с автоматическим обезличиванием
        """
        # Извлекаем информацию из сообщения
        extracted_info = await self.extract_info(message)
        
        # Обновляем слоты
        self.slots.update(extracted_info)
        
        # Обезличиваем перед отправкой в LLM
        sanitized_slots = self.dlp.sanitize_conversation_slots(self.slots)
        sanitized_message = self.dlp.sanitize_message(message)
        
        # Генерируем ответ
        response = await self.generate_response(
            sanitized_message,
            sanitized_slots
        )
        
        return response
    
    async def extract_info(self, message: str) -> dict:
        """
        Извлечение информации из сообщения
        (может содержать телефон, email и т.д.)
        """
        # Здесь может быть NER для извлечения ПДн
        # Но перед отправкой в LLM всё равно обезличиваем
        return {
            "message": message,
            # ... извлеченные данные
        }
```

---

## Преимущества переиспользования DLP сервиса

### 1. **Единые правила обезличивания**
- Все сервисы используют одинаковые правила
- Легко обновлять правила в одном месте
- Консистентность между RAG и нейропродажником

### 2. **Соответствие 152-ФЗ**
- Централизованное управление политикой безопасности
- Легко аудировать и проверять соответствие
- Единая точка контроля

### 3. **Упрощение разработки**
- Не нужно дублировать код обезличивания
- Готовые методы для разных типов данных
- Тестирование в одном месте

### 4. **Гибкость**
- Можно использовать как библиотеку (прямой импорт)
- Можно использовать как сервис (HTTP API)
- Легко переключаться между вариантами

---

## Рекомендуемая структура

```
sales-agent/
├── services/
│   ├── dlp_integration.py      # Обёртка DLP сервиса
│   ├── llm_service.py           # LLM клиент (использует DLP)
│   └── rag_client.py            # Клиент RAG (опционально)
├── agent/
│   ├── dialogue_manager.py      # Использует DLP
│   ├── fsm_states.py            # Использует DLP
│   └── handoff_detector.py
└── proposal_generator/
    └── generator.py             # Использует DLP
```

---

## Конфигурация

### Вариант 1: Прямой импорт (рекомендуется для начала)

```python
# sales-agent/config.py
import sys
from pathlib import Path

# Добавляем kb-service в путь
KB_SERVICE_PATH = Path(__file__).parent.parent / "kb-service"
sys.path.insert(0, str(KB_SERVICE_PATH))
```

### Вариант 2: HTTP API

```python
# sales-agent/config.py
DLP_SERVICE_URL = "http://localhost:8001"  # KB Service с DLP endpoints
```

---

## Тестирование

```python
# sales-agent/tests/test_dlp_integration.py
import pytest
from services.dlp_integration import SalesAgentDLP

def test_sanitize_slots():
    dlp = SalesAgentDLP()
    
    slots = {
        "client_name": "Иван Иванов",
        "phone": "+7 (988) 199-89-98",
        "email": "ivan@example.com",
        "budget": 10000000
    }
    
    sanitized = dlp.sanitize_conversation_slots(slots)
    
    # Проверяем обезличивание
    assert "+7 (988) 199-89-98" not in str(sanitized)
    assert "ivan@example.com" not in str(sanitized)
    assert "Иван Иванов" not in str(sanitized)
    assert sanitized["budget"] == 10000000  # Бюджет не обезличивается
```

---

## Миграция существующего кода

Если у вас уже есть код нейропродажника:

1. **Добавьте DLP интеграцию:**
   ```python
   from services.dlp_integration import SalesAgentDLP
   dlp = SalesAgentDLP()
   ```

2. **Найдите все места отправки в LLM:**
   - Поиск по `llm_service.generate`
   - Поиск по `openai.ChatCompletion`
   - Поиск по `client.chat.completions`

3. **Добавьте обезличивание перед каждым вызовом:**
   ```python
   # Было:
   response = await llm.generate(messages, context=slots)
   
   # Стало:
   sanitized_slots = dlp.sanitize_conversation_slots(slots)
   response = await llm.generate(messages, context=sanitized_slots)
   ```

---

## Чеклист внедрения

### Цепочка n8n (чат с сайта)

- [ ] В workflow n8n перед узлом LLM ProxyAPI добавить вызов **POST http://localhost:8001/api/dlp/sanitize-text** для поля сообщения пользователя.
- [ ] В промпт LLM подставлять обезличенный текст сообщения и при необходимости обезличенный additional_context (через **POST /api/dlp/sanitize**).
- [ ] Убедиться, что извлечение телефона/имени для AmoCRM (Maybe Create Lead) идёт из **исходного** сообщения, а не из обезличенного.

### sales-agent (Python)

- [ ] Добавить DLP интеграцию в sales-agent
- [ ] Обновить dialogue_manager для использования DLP
- [ ] Обновить proposal_generator для использования DLP
- [ ] Добавить тесты для проверки обезличивания
- [ ] Проверить все места отправки в LLM
- [ ] Документировать использование DLP в коде
- [ ] Настроить мониторинг обезличивания (логи)

---

## Связанные документы

- [`kb-service/RAG_DLP_INTEGRATION.md`](../kb-service/RAG_DLP_INTEGRATION.md) — документация DLP сервиса
- [`kb-service/services/dlp_service.py`](../kb-service/services/dlp_service.py) — исходный код DLP
- [`README.md`](../README.md#соблюдение-152-фз) — требования 152-ФЗ

---

**Последнее обновление:** 2026-02-23 — добавлены DLP HTTP API в kb-service и раздел про защиту в цепочке n8n (чат с сайта).















