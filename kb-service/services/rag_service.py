"""
RAG (Retrieval-Augmented Generation) сервис
Объединяет поиск в KB, DLP и LLM для генерации ответов
"""

import logging
from typing import Dict, Any, List, Optional

from services.kb_service import KBService
from services.llm_service import get_llm_service
from services.dlp_service import get_dlp_service

logger = logging.getLogger(__name__)


class RAGService:
    """
    Сервис для RAG (Retrieval-Augmented Generation)
    """
    
    def __init__(self):
        """
        Инициализация RAG сервиса
        """
        self.kb_service = KBService()
        self.llm_service = get_llm_service()
        self.dlp_service = get_dlp_service()
        
        logger.info("✅ RAGService инициализирован")
    
    async def generate_response(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
        target_audience: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.6,
        system_prompt: Optional[str] = None,
        sanitize_context: bool = True,
        **llm_kwargs
    ) -> Dict[str, Any]:
        """
        Генерация ответа с использованием RAG
        
        Args:
            query: Пользовательский запрос
            context: Дополнительный контекст (будет обезличен)
            category: Категория для поиска в KB
            target_audience: Целевая аудитория для фильтрации
            limit: Количество результатов из KB
            min_similarity: Минимальная схожесть для результатов KB
            system_prompt: Кастомный системный промпт
            sanitize_context: Обезличивать ли контекст перед отправкой в LLM
            **llm_kwargs: Дополнительные параметры для LLM
            
        Returns:
            Ответ с текстом, метаданными и источниками
        """
        try:
            logger.info(f"RAG запрос: {query[:50]}...")
            
            # Шаг 1: Поиск в KB
            kb_results = await self.kb_service.search(
                query=query,
                limit=limit,
                category=category,
                target_audience=target_audience,
                min_similarity=min_similarity
            )
            
            logger.info(f"Найдено {len(kb_results)} результатов в KB")
            
            # Шаг 2: Генерация ответа с использованием RAG
            llm_response = await self.llm_service.generate_with_rag(
                query=query,
                kb_results=kb_results,
                system_prompt=system_prompt,
                context=context,
                sanitize_context=sanitize_context,
                **llm_kwargs
            )
            
            # Шаг 3: Формируем итоговый ответ
            response = {
                "response": llm_response["response"],
                "sources": [
                    {
                        "id": result["id"],
                        "content": result["content"][:200] + "..." if len(result["content"]) > 200 else result["content"],
                        "similarity": result.get("similarity"),
                        "metadata": result.get("metadata", {})
                    }
                    for result in kb_results
                ],
                "kb_results_count": len(kb_results),
                "llm_usage": llm_response.get("usage", {}),
                "model": llm_response.get("model"),
                "finish_reason": llm_response.get("finish_reason")
            }
            
            logger.info(f"RAG ответ сгенерирован (sources={len(kb_results)}, tokens={llm_response.get('usage', {}).get('total_tokens', 0)})")
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка генерации RAG ответа: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def generate_streaming(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
        target_audience: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.6,
        system_prompt: Optional[str] = None,
        sanitize_context: bool = True,
        **llm_kwargs
    ):
        """
        Генерация ответа в режиме стриминга
        
        Yields:
            Чанки ответа от LLM
        """
        try:
            # Поиск в KB
            kb_results = await self.kb_service.search(
                query=query,
                limit=limit,
                category=category,
                target_audience=target_audience,
                min_similarity=min_similarity
            )
            
            # Обезличиваем результаты KB
            sanitized_kb_results = self.dlp_service.sanitize_kb_results(kb_results)
            
            # Формируем промпт с контекстом из KB
            kb_context = "\n\n".join([
                f"[Источник {i+1}]: {result.get('content', '')}"
                for i, result in enumerate(sanitized_kb_results[:5])
            ])
            
            default_system_prompt = """Ты - профессиональный продавец недвижимости. 
Используй информацию из базы знаний для ответа на вопросы клиентов.
Отвечай дружелюбно, профессионально и по делу."""
            
            final_system_prompt = system_prompt or default_system_prompt
            final_system_prompt += f"\n\nБаза знаний:\n{kb_context}"
            
            # Обезличиваем контекст если нужно
            if context and sanitize_context:
                sanitized_context = self.dlp_service.sanitize_conversation_context(context)
                final_system_prompt += f"\n\nКонтекст: {sanitized_context}"
            
            # Стриминг ответа
            messages = [{"role": "user", "content": query}]
            
            # generate_streaming - это генератор, не async генератор
            for chunk in self.llm_service.generate_streaming(
                messages=messages,
                system_prompt=final_system_prompt,
                context=None,  # Уже добавлен в system_prompt
                sanitize_context=False,
                **llm_kwargs
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Ошибка стриминга RAG ответа: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise


# Глобальный экземпляр
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """
    Получить глобальный экземпляр RAG сервиса
    """
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

