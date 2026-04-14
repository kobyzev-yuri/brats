"""
Минимальный HTTP-сервис нейропродажника.

Назначение:
- POST /api/chat/initiate — инициация диалога (conversation_id)
- POST /api/chat — приём сообщения от n8n (workflow Sales Agent - KB Integration):
  n8n передаёт сюда промпт (контекст KB + вопрос клиента), ожидает ответ с полем response/message
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import os
import sys

# Настройка sys.path, если запускаем как `python api/main.py`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PACKAGE_ROOT not in sys.path:
    sys.path.append(PACKAGE_ROOT)


class ContactModel(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None


class ChatInitiateContext(BaseModel):
    page_url: Optional[str] = None
    form_type: Optional[str] = None
    intent_score: Optional[float] = None
    reasons: Optional[list[str]] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class ChatInitiateRequest(BaseModel):
    external_id: str
    channel: str = "site"
    contact: ContactModel
    context: ChatInitiateContext


class ChatInitiateResponse(BaseModel):
    conversation_id: str
    status: str
    created_at: datetime
    echo: ChatInitiateRequest


class ChatMessageRequest(BaseModel):
    """Тело запроса от n8n (узел Sales Agent Call)."""
    message: str
    conversation_id: Optional[str] = None
    channel: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Ответ для n8n — Prepare Response ищет response или message."""
    response: str
    message: Optional[str] = None  # алиас для совместимости


app = FastAPI(
    title="Sales Agent Service (MVP)",
    description="Минимальный HTTP-сервис нейропродажника для интеграции с sales-analytic",
    version="0.1.0",
)


@app.get("/")
async def root():
    return {
        "service": "Sales Agent Service (MVP)",
        "version": "0.1.0",
        "status": "running",
    }


@app.post("/api/chat/initiate", response_model=ChatInitiateResponse)
async def initiate_chat(req: ChatInitiateRequest):
    """
    Минимальный endpoint инициации диалога.

    Пока:
    - просто генерирует conversation_id
    - возвращает echo запроса

    Дальше сюда можно прикрутить:
    - FSM нейропродажника
    - работу с KB
    - интеграцию с каналами (Telegram, сайт и т.п.)
    """
    conv_id = str(uuid.uuid4())
    now = datetime.utcnow()

    return ChatInitiateResponse(
        conversation_id=conv_id,
        status="initiated",
        created_at=now,
        echo=req,
    )


@app.post("/api/chat", response_model=ChatMessageResponse)
async def chat_message(req: ChatMessageRequest):
    """
    Принимает сообщение от n8n (workflow Sales Agent - KB Integration).
    В req.message приходит уже собранный промпт (контекст KB + вопрос клиента).
    Заглушка: возвращает фиксированный ответ. Позже — вызов LLM по промпту.
    """
    # Заглушка: можно заменить на вызов LLM по req.message
    reply = (
        "Здравствуйте! Я консультант по коттеджному посёлку. "
        "Готов рассказать о домах с черновой и стандартной отделкой, ипотеке, рассрочке и скидках. "
        "Что вас интересует в первую очередь?"
    )
    return ChatMessageResponse(response=reply, message=reply)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)












