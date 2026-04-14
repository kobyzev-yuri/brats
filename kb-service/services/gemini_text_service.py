"""
Gemini text service для библиотекаря мультимодальной KB.

Использует ProxyAPI.ru для доступа к Google Gemini:
- GEMINI_API_KEY
- GEMINI_BASE_URL (по умолчанию https://api.proxyapi.ru/google)
- GEMINI_MODEL (например, gemini-3-pro-preview)
"""

import os
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env", override=True)

logger = logging.getLogger(__name__)


class GeminiTextService:
    """
    Минимальный клиент для работы с Gemini через ProxyAPI.ru.
    Ориентирован на генерацию JSON‑ответов.
    """

    def __init__(self) -> None:
        # По умолчанию используем тот же ключ ProxyAPI, что и для OpenAI,
        # чтобы не дублировать его в config.env.
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("GEMINI_BASE_URL", "https://api.proxyapi.ru/google")
        self.model = os.getenv("GEMINI_MODEL", "gemini-3-pro-preview")
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
        self.timeout = int(os.getenv("GEMINI_TIMEOUT", "120"))

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY или OPENAI_API_KEY не настроен в config.env для kb-service "
                "(нужен ключ ProxyAPI.ru)."
            )

        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=None,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        logger.info(
            f"✅ GeminiTextService инициализирован (model={self.model}, base_url={self.base_url})"
        )

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_output_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Генерация JSON‑ответа через Gemini.

        Args:
            prompt: Пользовательский промпт (описание задачи)
            system_prompt: Системный промпт (инструкция роли), опционально
            max_output_tokens: Лимит токенов для ответа
        """
        # Добавляем инструкцию, что нужен только JSON
        full_prompt = (
            f"{prompt}\n\nВерни ответ ТОЛЬКО в формате JSON, без дополнительного текста."
        )

        parts = [{"text": full_prompt}]

        request_data: Dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }

        if system_prompt:
            request_data["systemInstruction"] = {
                "parts": [{"text": system_prompt}],
            }

        model_endpoint = f"/v1beta/models/{self.model}:generateContent"

        try:
            logger.debug(
                f"📤 Gemini JSON запрос: {self.base_url}{model_endpoint}, prompt_len={len(full_prompt)}"
            )
            response = await self._client.post(
                model_endpoint,
                json=request_data,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates", []) or []
            if not candidates:
                logger.warning("⚠️ Gemini вернул пустой список candidates")
                return {}

            content = candidates[0].get("content", {})
            parts_out = content.get("parts", []) or []
            if not parts_out:
                logger.warning("⚠️ Gemini вернул пустые parts в content")
                return {}

            text = parts_out[0].get("text", "") or ""
            if not text:
                logger.warning("⚠️ Gemini вернул пустой text в parts")
                return {}

            # Пытаемся распарсить JSON
            import re

            clean_text = text.strip()

            # Если модель вернула JSON в ```json ... ``` — вырезаем содержимое
            if "```" in clean_text:
                fence_match = re.search(
                    r"```(?:json)?\s*([\s\S]*?)```", clean_text, re.IGNORECASE
                )
                if fence_match:
                    clean_text = fence_match.group(1).strip()

            # 1. Прямая попытка распарсить то, что осталось
            try:
                return json.loads(clean_text)
            except json.JSONDecodeError:
                # 2. Попытка вырезать JSON‑подстроку по фигурным скобкам
                m = re.search(r"\{[\s\S]*\}", clean_text)
                if m:
                    candidate = m.group(0)
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        logger.error(
                            "❌ Ошибка парсинга JSON из подстроки Gemini ответа"
                        )

                # Логируем небольшой фрагмент ответа для отладки
                logger.error(
                    "❌ Ошибка парсинга JSON из ответа Gemini. Фрагмент: %s",
                    clean_text[:500].replace("\n", "\\n"),
                )
                return {}

        except Exception as e:
            logger.error(f"❌ Ошибка запроса к Gemini: {e}", exc_info=True)
            return {}


_gemini_text_service: Optional[GeminiTextService] = None


def get_gemini_text_service() -> GeminiTextService:
    global _gemini_text_service
    if _gemini_text_service is None:
        _gemini_text_service = GeminiTextService()
    return _gemini_text_service


