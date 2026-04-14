"""
LLM сервис для работы с GPT-4o через proxyapi.ru
С интеграцией DLP для обезличивания данных
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv
import httpx
from openai import OpenAI

from services.dlp_service import get_dlp_service

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env", override=True)

logger = logging.getLogger(__name__)


class LLMService:
    """
    Сервис для работы с LLM (GPT-4o через proxyapi.ru)
    """
    
    def __init__(self):
        """
        Инициализация LLM сервиса
        """
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
        self.dlp_service = get_dlp_service()
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не настроен в config.env")
        
        # Инициализируем OpenAI клиент
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        logger.info(f"✅ LLMService инициализирован (model={self.model}, base_url={self.base_url})")
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        sanitize_context: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Генерация ответа от LLM
        
        Args:
            messages: Список сообщений в формате OpenAI (role, content)
            system_prompt: Системный промпт
            context: Контекст для включения в промпт (будет обезличен если sanitize_context=True)
            sanitize_context: Обезличивать ли контекст перед отправкой
            **kwargs: Дополнительные параметры (temperature, max_tokens и т.д.)
            
        Returns:
            Ответ от LLM с метаданными
        """
        try:
            # Формируем список сообщений
            formatted_messages = []
            
            # Добавляем системный промпт
            if system_prompt:
                formatted_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            # Обезличиваем контекст если нужно
            if context and sanitize_context:
                sanitized_context = self.dlp_service.sanitize_conversation_context(context)
                # Добавляем контекст в системный промпт или отдельным сообщением
                if system_prompt:
                    formatted_messages[0]["content"] += f"\n\nКонтекст: {json.dumps(sanitized_context, ensure_ascii=False)}"
                else:
                    formatted_messages.append({
                        "role": "system",
                        "content": f"Контекст: {json.dumps(sanitized_context, ensure_ascii=False)}"
                    })
            
            # Добавляем пользовательские сообщения (тоже обезличиваем)
            for msg in messages:
                sanitized_msg = {
                    "role": msg.get("role", "user"),
                    "content": self.dlp_service._mask_text(msg.get("content", ""))
                }
                formatted_messages.append(sanitized_msg)
            
            # Параметры запроса
            request_params = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "max_tokens": kwargs.get("max_tokens", 2000),
                "timeout": self.timeout
            }
            
            # Выполняем запрос
            logger.info(f"Отправка запроса к LLM (model={self.model}, messages={len(formatted_messages)})")
            
            response = self.client.chat.completions.create(**request_params)
            
            # Извлекаем ответ
            assistant_message = response.choices[0].message.content
            
            return {
                "response": assistant_message,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "finish_reason": response.choices[0].finish_reason
            }
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа от LLM: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def generate_with_rag(
        self,
        query: str,
        kb_results: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        sanitize_context: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Генерация ответа с использованием RAG (Retrieval-Augmented Generation)
        
        Args:
            query: Пользовательский запрос
            kb_results: Результаты поиска из KB
            system_prompt: Системный промпт
            context: Дополнительный контекст
            sanitize_context: Обезличивать ли контекст
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ от LLM с использованием RAG
        """
        try:
            # Обезличиваем результаты KB
            sanitized_kb_results = self.dlp_service.sanitize_kb_results(kb_results)
            
            # Формируем промпт с контекстом из KB
            kb_context = "\n\n".join([
                f"[Источник {i+1}]: {result.get('content', '')}"
                for i, result in enumerate(sanitized_kb_results[:5])  # Берем топ-5 результатов
            ])
            
            # Системный промпт по умолчанию
            default_system_prompt = """Ты - профессиональный продавец недвижимости. 
Используй информацию из базы знаний для ответа на вопросы клиентов.
Отвечай дружелюбно, профессионально и по делу.
Если информации недостаточно, честно скажи об этом."""
            
            final_system_prompt = system_prompt or default_system_prompt
            final_system_prompt += f"\n\nБаза знаний:\n{kb_context}"
            
            # Формируем сообщения
            messages = [
                {
                    "role": "user",
                    "content": query
                }
            ]
            
            # Генерируем ответ
            return await self.generate_response(
                messages=messages,
                system_prompt=final_system_prompt,
                context=context,
                sanitize_context=sanitize_context,
                **kwargs
            )
            
        except Exception as e:
            logger.error(f"Ошибка генерации с RAG: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    async def describe_images(
        self,
        image_urls: List[str],
        context_text: Optional[str] = None,
        max_tokens: int = 800,
    ) -> Dict[str, Any]:
        """
        Описание изображений с помощью GPT-4o (vision) через proxyapi.ru.

        Args:
            image_urls: Список URL изображений (должны быть доступными по HTTP/HTTPS)
            context_text: Дополнительный текстовый контекст (опционально)
            max_tokens: Лимит токенов для ответа

        Returns:
            Словарь с ключом "images": список аннотаций вида:
            {
              "index": int,
              "url": str,
              "description": str,
              "alt": str
            }
        """
        if not image_urls:
            return {"images": []}

        try:
            # Фильтруем заведомо "мусорные" иконки (стрелки, телефоны, соцсети и т.п.),
            # чтобы vision‑модель не тратила на них время и не придумывала описания.
            def _is_probably_icon(url: str) -> bool:
                lower = url.lower()
                icon_keywords = [
                    "icon",
                    "phone",
                    "whatsapp",
                    "telegram",
                    "vk",
                    "viber",
                    "instagram",
                    "insta",
                    "logo",
                    "arrow",
                    "strelka",
                    "strela",
                ]
                tiny_size_markers = [
                    "/16x",
                    "/20x",
                    "/24x",
                    "/32x",
                    "/40x",
                ]
                if any(k in lower for k in icon_keywords):
                    return True
                if any(m in lower for m in tiny_size_markers):
                    return True
                return False

            filtered_urls: List[str] = []
            index_map: List[int] = []
            for idx, url in enumerate(image_urls):
                if not url:
                    continue
                if _is_probably_icon(url):
                    # пропускаем иконки/мусор
                    continue
                filtered_urls.append(url)
                index_map.append(idx)

            if not filtered_urls:
                return {"images": []}

            # Формируем мультимодальный контент: текст + изображения
            user_content: List[Dict[str, Any]] = []
            if context_text:
                user_content.append(
                    {
                        "type": "text",
                        "text": (
                            "Контекст для понимания изображений (описание объекта/посёлка):\n"
                            f"{context_text[:1000]}"
                        ),
                    }
                )

            for idx, url in enumerate(filtered_urls):
                if not url:
                    continue
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": url},
                    }
                )

            system_prompt = (
                "Ты помогаешь отделу продаж недвижимости описывать изображения для базы знаний и сайта.\n"
                "Для каждого изображения сформируй краткое описание и alt‑текст, верни СТРОГО JSON:\n"
                "{\n"
                '  \"images\": [\n'
                '    {\"index\": 0, \"url\": \"...\", \"description\": \"...\", \"alt\": \"...\"}\n'
                "  ]\n"
                "}\n"
                "Говори по-русски, без лишних комментариев вне JSON."
            )

            messages: List[Dict[str, Any]] = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ]

            logger.info(
                f"Отправка запроса на описание {len(filtered_urls)} изображений (model={self.model}, отфильтровано {len(image_urls) - len(filtered_urls)} иконок)"
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content
            if not content:
                return {"images": []}

            # В новых версиях OpenAI Python content может быть как строкой, так и списком частей
            import re

            if isinstance(content, list):
                # Собираем все текстовые части в одну строку
                text_parts = []
                for part in content:
                    # Формат ProxyAPI/OpenAI: {"type": "text", "text": "..."}
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part.get("text") or "")
                text = "".join(text_parts).strip()
            else:
                text = str(content).strip()

            if not text:
                return {"images": []}

            # Если модель вернула ```json ... ``` — вырезаем содержимое
            if "```" in text:
                fence_match = re.search(
                    r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE
                )
                if fence_match:
                    text = fence_match.group(1).strip()

            # Пытаемся распарсить JSON
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict) and "images" in parsed:
                    # Маппим индексы обратно на исходные (пропуская иконки)
                    result_images = []
                    for ann in parsed.get("images", []):
                        ann_idx = ann.get("index")
                        if isinstance(ann_idx, int) and 0 <= ann_idx < len(index_map):
                            ann["index"] = index_map[ann_idx]
                        result_images.append(ann)
                    return {"images": result_images}
            except Exception:
                # fallback: попытаться вырезать JSON из текста по фигурным скобкам
                try:
                    m = re.search(r"\{[\s\S]*\}", text)
                    if m:
                        candidate = m.group(0)
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict) and "images" in parsed:
                            # Маппим индексы обратно на исходные
                            result_images = []
                            for ann in parsed.get("images", []):
                                ann_idx = ann.get("index")
                                if isinstance(ann_idx, int) and 0 <= ann_idx < len(index_map):
                                    ann["index"] = index_map[ann_idx]
                                result_images.append(ann)
                            return {"images": result_images}
                except Exception:
                    logger.warning("Не удалось извлечь JSON из ответа describe_images")

            return {"images": []}

        except Exception as e:
            logger.error(f"Ошибка описания изображений: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"images": []}
    
    async def generate_streaming(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        sanitize_context: bool = True,
        **kwargs
    ):
        """
        Генерация ответа в режиме стриминга (для веб-сокетов)
        
        Args:
            messages: Список сообщений
            system_prompt: Системный промпт
            context: Контекст
            sanitize_context: Обезличивать ли контекст
            **kwargs: Дополнительные параметры
            
        Yields:
            Чанки ответа от LLM
        """
        try:
            # Формируем сообщения (аналогично generate_response)
            formatted_messages = []
            
            if system_prompt:
                formatted_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            if context and sanitize_context:
                sanitized_context = self.dlp_service.sanitize_conversation_context(context)
                if system_prompt:
                    formatted_messages[0]["content"] += f"\n\nКонтекст: {json.dumps(sanitized_context, ensure_ascii=False)}"
                else:
                    formatted_messages.append({
                        "role": "system",
                        "content": f"Контекст: {json.dumps(sanitized_context, ensure_ascii=False)}"
                    })
            
            for msg in messages:
                sanitized_msg = {
                    "role": msg.get("role", "user"),
                    "content": self.dlp_service._mask_text(msg.get("content", ""))
                }
                formatted_messages.append(sanitized_msg)
            
            # Параметры для стриминга
            request_params = {
                "model": self.model,
                "messages": formatted_messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "max_tokens": kwargs.get("max_tokens", 2000),
                "stream": True,
                "timeout": self.timeout
            }
            
            # Стриминг ответа
            stream = self.client.chat.completions.create(**request_params)
            
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content
                    
        except Exception as e:
            logger.error(f"Ошибка стриминга ответа от LLM: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise


# Глобальный экземпляр
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Получить глобальный экземпляр LLM сервиса
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

