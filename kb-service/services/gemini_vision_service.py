"""
Сервис аннотирования изображений (и при возможности видео) через Gemini.

Используется в мультимедийной базе знаний (MMKB): картинки и видео по возможности
аннотируются через Gemini 3 (или gemini-2.0-flash / gemini-1.5-pro), fallback — GPT-4o vision.

Переменные окружения (config.env):
- GEMINI_API_KEY или OPENAI_API_KEY (ключ ProxyAPI)
- GEMINI_BASE_URL (по умолчанию https://api.proxyapi.ru/google)
- GEMINI_VISION_MODEL или GEMINI_MODEL (например gemini-2.0-flash, gemini-1.5-pro)
- USE_GEMINI_FOR_VISION=true — предпочитать Gemini для аннотирования изображений
"""

import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pathlib import Path
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env", override=True)

logger = logging.getLogger(__name__)


def _is_probably_icon(url: str) -> bool:
    """Пропускаем иконки/логотипы — не аннотируем."""
    lower = url.lower()
    for k in ["icon", "phone", "whatsapp", "telegram", "vk", "logo", "arrow", "strelka", "/16x", "/24x", "/32x"]:
        if k in lower:
            return True
    return False


class GeminiVisionService:
    """
    Аннотирование изображений через Gemini (generateContent с inline_data).
    Видео: при поддержке API можно передавать в generateContent; пока — заглушка для расширения.
    """

    def __init__(self) -> None:
        import os
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = (os.getenv("GEMINI_BASE_URL") or "https://api.proxyapi.ru/google").rstrip("/")
        self.model = os.getenv("GEMINI_VISION_MODEL") or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.timeout = int(os.getenv("GEMINI_TIMEOUT", "120"))
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=float(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _fetch_image(self, url: str) -> Optional[Tuple[bytes, str]]:
        """Скачивает изображение по URL, возвращает (bytes, mime_type)."""
        try:
            r = await self._get_client().get(url, timeout=15.0)
            r.raise_for_status()
            data = r.content
            ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
            if "image/" in ct:
                mime = ct
            elif url.lower().endswith(".png"):
                mime = "image/png"
            elif url.lower().endswith(".webp"):
                mime = "image/webp"
            else:
                mime = "image/jpeg"
            return (data, mime)
        except Exception as e:
            logger.warning("Не удалось загрузить изображение %s: %s", url[:80], e)
            return None

    async def describe_images(
        self,
        image_urls: List[str],
        context_text: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Описание изображений через Gemini (vision). Формат ответа совместим с LLMService.describe_images:
        {"images": [{"index": int, "url": str, "description": str, "alt": str}]}
        """
        if not self.api_key or not image_urls:
            return {"images": []}

        # Фильтруем иконки
        filtered_urls: List[str] = []
        index_map: List[int] = []
        for idx, url in enumerate(image_urls):
            if not url or _is_probably_icon(url):
                continue
            filtered_urls.append(url)
            index_map.append(idx)

        if not filtered_urls:
            return {"images": []}

        # Скачиваем изображения и строим parts для Gemini
        parts: List[Dict[str, Any]] = []
        prompt_parts = [
            "Ты помогаешь отделу продаж недвижимости описывать изображения для базы знаний и сайта.",
            "Для каждого изображения (они идут по порядку) сформируй краткое описание и alt‑текст.",
            "Верни СТРОГО JSON без markdown, в одном блоке:\n",
            '{"images": [{"index": 0, "description": "...", "alt": "..."}, ...]}\n',
            "index должен совпадать с порядком изображений (0, 1, 2, ...). Говори по-русски.",
        ]
        if context_text:
            prompt_parts.insert(1, f"Контекст: {context_text[:1500]}")
        parts.append({"text": "\n".join(prompt_parts)})

        image_data_list: List[Tuple[bytes, str]] = []
        for url in filtered_urls:
            pair = await self._fetch_image(url)
            if pair:
                image_data_list.append(pair)
            else:
                image_data_list.append((b"", "image/jpeg"))

        for data, mime in image_data_list:
            if not data:
                continue
            b64 = base64.b64encode(data).decode("utf-8")
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": b64,
                }
            })

        if len(parts) <= 1:
            return {"images": []}

        request_body: Dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        model_endpoint = f"/v1beta/models/{self.model}:generateContent"

        try:
            logger.info(
                "Отправка запроса Gemini Vision: %s изображений (model=%s)",
                len(filtered_urls),
                self.model,
            )
            response = await self._get_client().post(model_endpoint, json=request_body)
            response.raise_for_status()
            data = response.json()
            text = None
            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    if "text" in part:
                        text = (text or "") + (part.get("text") or "")
                        break
            if not text or not text.strip():
                return {"images": []}

            text = text.strip()
            if "```" in text:
                m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
                if m:
                    text = m.group(1).strip()
            parsed = json.loads(text)
            if not isinstance(parsed, dict) or "images" not in parsed:
                return {"images": []}

            result_images: List[Dict[str, Any]] = []
            for ann in parsed.get("images", []):
                idx = ann.get("index")
                if isinstance(idx, int) and 0 <= idx < len(index_map):
                    ann = dict(ann)
                    ann["index"] = index_map[idx]
                    ann["url"] = filtered_urls[idx]
                    result_images.append(ann)
            return {"images": result_images}

        except Exception as e:
            logger.warning("Gemini Vision описание изображений не удалось: %s", e)
            return {"images": []}

    async def describe_video(self, video_url: str, context_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Аннотирование видео через Gemini (когда API поддерживает видео).
        Пока — заглушка: можно расширить по документации Gemini (file API или inline video).
        """
        # Gemini 1.5+ поддерживает video в generateContent; для URL нужна загрузка или File API
        logger.info("describe_video пока не реализован (video_url=%s)", video_url[:80] if video_url else "")
        return {"description": "", "alt": "", "segments": []}


_gemini_vision_service: Optional[GeminiVisionService] = None


def get_gemini_vision_service() -> Optional[GeminiVisionService]:
    """Возвращает сервис Gemini Vision или None, если ключ не настроен."""
    global _gemini_vision_service
    if _gemini_vision_service is not None:
        return _gemini_vision_service
    import os
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")):
        return None
    try:
        _gemini_vision_service = GeminiVisionService()
        logger.info("✅ GeminiVisionService инициализирован (model=%s)", _gemini_vision_service.model)
        return _gemini_vision_service
    except Exception as e:
        logger.warning("GeminiVisionService не инициализирован: %s", e)
        return None
