"""
RAG endpoints для тестирования интеграции с DLP и LLM
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG"])


class RAGRequest(BaseModel):
    """Запрос для RAG генерации"""
    query: str
    context: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    target_audience: Optional[str] = None
    limit: int = 5
    min_similarity: float = 0.6
    system_prompt: Optional[str] = None
    sanitize_context: bool = True
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class RAGResponse(BaseModel):
    """Ответ от RAG сервиса"""
    response: str
    sources: list
    kb_results_count: int
    llm_usage: Dict[str, int]
    model: str
    finish_reason: str


@router.post("/generate", response_model=RAGResponse)
async def generate_rag_response(request: RAGRequest):
    """
    Генерация ответа с использованием RAG (KB + LLM + DLP)
    """
    try:
        rag_service = get_rag_service()
        
        # Параметры для LLM
        llm_kwargs = {}
        if request.temperature is not None:
            llm_kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            llm_kwargs["max_tokens"] = request.max_tokens
        
        # Генерируем ответ
        result = await rag_service.generate_response(
            query=request.query,
            context=request.context,
            category=request.category,
            target_audience=request.target_audience,
            limit=request.limit,
            min_similarity=request.min_similarity,
            system_prompt=request.system_prompt,
            sanitize_context=request.sanitize_context,
            **llm_kwargs
        )
        
        return RAGResponse(**result)
        
    except Exception as e:
        logger.error(f"Ошибка генерации RAG ответа: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка генерации: {str(e)}")


@router.post("/stream")
async def stream_rag_response(request: RAGRequest):
    """
    Генерация ответа в режиме стриминга
    """
    try:
        rag_service = get_rag_service()
        
        # Параметры для LLM
        llm_kwargs = {}
        if request.temperature is not None:
            llm_kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            llm_kwargs["max_tokens"] = request.max_tokens
        
        async def generate():
            for chunk in rag_service.generate_streaming(
                query=request.query,
                context=request.context,
                category=request.category,
                target_audience=request.target_audience,
                limit=request.limit,
                min_similarity=request.min_similarity,
                system_prompt=request.system_prompt,
                sanitize_context=request.sanitize_context,
                **llm_kwargs
            ):
                yield chunk
        
        return StreamingResponse(generate(), media_type="text/plain")
        
    except Exception as e:
        logger.error(f"Ошибка стриминга RAG ответа: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка стриминга: {str(e)}")


@router.post("/webhook")
async def rag_webhook(request: Dict[str, Any]):
    """
    Webhook endpoint для интеграции с n8n и другими сервисами
    Принимает запросы в формате JSON
    """
    try:
        # Извлекаем параметры из запроса
        query = request.get("query") or request.get("message") or request.get("text")
        if not query:
            raise HTTPException(status_code=400, detail="Не указан query/message/text")
        
        context = request.get("context", {})
        category = request.get("category")
        target_audience = request.get("target_audience")
        limit = request.get("limit", 5)
        min_similarity = request.get("min_similarity", 0.6)
        system_prompt = request.get("system_prompt")
        sanitize_context = request.get("sanitize_context", True)
        
        # Параметры LLM
        llm_kwargs = {}
        if "temperature" in request:
            llm_kwargs["temperature"] = request["temperature"]
        if "max_tokens" in request:
            llm_kwargs["max_tokens"] = request["max_tokens"]
        
        # Генерируем ответ
        rag_service = get_rag_service()
        result = await rag_service.generate_response(
            query=query,
            context=context,
            category=category,
            target_audience=target_audience,
            limit=limit,
            min_similarity=min_similarity,
            system_prompt=system_prompt,
            sanitize_context=sanitize_context,
            **llm_kwargs
        )
        
        # Возвращаем ответ в формате для webhook
        return {
            "success": True,
            "response": result["response"],
            "sources": result["sources"],
            "metadata": {
                "kb_results_count": result["kb_results_count"],
                "llm_usage": result["llm_usage"],
                "model": result["model"],
                "finish_reason": result["finish_reason"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")

