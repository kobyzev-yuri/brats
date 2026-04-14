"""
DLP HTTP API для обезличивания данных перед отправкой в зарубежные LLM.
Используется n8n (чат с сайта) и другими сервисами. См. docs/DLP_FOR_SALES_AGENT.md.
"""

from typing import Any, Dict, Optional  # noqa: F401

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.dlp_service import get_dlp_service

router = APIRouter(prefix="/api/dlp", tags=["DLP"])


@router.get("/health")
def dlp_health() -> dict:
    """Проверка доступности DLP API (kb-service перезапущен с DLP)."""
    return {"status": "ok", "service": "dlp"}


class SanitizeTextRequest(BaseModel):
    text: Optional[str] = ""


class SanitizeTextResponse(BaseModel):
    sanitized_text: str


class SanitizeDataRequest(BaseModel):
    data: Dict[str, Any]


class SanitizeDataResponse(BaseModel):
    sanitized_data: Any


@router.post("/sanitize-text", response_model=SanitizeTextResponse)
def sanitize_text(request: SanitizeTextRequest) -> SanitizeTextResponse:
    """
    Обезличивание текста (телефоны, email, паспорта, карты и т.д.).
    Для использования в n8n перед отправкой сообщения пользователя в LLM.
    """
    try:
        dlp = get_dlp_service()
        sanitized = dlp._mask_text(request.text or "")
        return SanitizeTextResponse(sanitized_text=sanitized)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sanitize", response_model=SanitizeDataResponse)
def sanitize_data(request: SanitizeDataRequest) -> SanitizeDataResponse:
    """
    Обезличивание JSON (удаление/маскирование полей с ПДн и чувствительными данными).
    Для контекста диалога, слотов, metadata, additional_context и т.д.
    """
    try:
        dlp = get_dlp_service()
        sanitized = dlp.sanitize_for_llm(request.data)
        return SanitizeDataResponse(sanitized_data=sanitized)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sanitize-conversation-context", response_model=SanitizeDataResponse)
def sanitize_conversation_context(request: SanitizeDataRequest) -> SanitizeDataResponse:
    """
    Обезличивание контекста диалога (slots, metadata, visitor_id, session_id).
    """
    try:
        dlp = get_dlp_service()
        sanitized = dlp.sanitize_conversation_context(request.data)
        return SanitizeDataResponse(sanitized_data=sanitized)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
