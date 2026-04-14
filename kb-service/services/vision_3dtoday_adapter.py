"""
Адаптер для использования аннотирования изображений из проекта ~/3dtoday.

Когда задан путь к backend 3dtoday (например VISION_3DTODAY_PATH=~/3dtoday/backend),
библиотекарь MMKB может вызывать VisionAnalyzer из 3dtoday для анализа картинок через Gemini
(с fallback на Ollama/llava). Формат ответа приводится к виду describe_images: {images: [{index, url, description, alt}]}.

Настройка в config.env:
- VISION_3DTODAY_PATH — путь к корню backend 3dtoday (например /home/user/3dtoday/backend или /home/user/3dtoday)
- USE_3DTODAY_VISION=true — использовать 3dtoday для аннотирования изображений (приоритет над встроенным Gemini/GPT-4o)
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_vision_analyzer = None


def _get_3dtoday_vision_analyzer():
    """Импортирует и создаёт VisionAnalyzer из 3dtoday при наличии VISION_3DTODAY_PATH."""
    global _vision_analyzer
    if _vision_analyzer is not None:
        return _vision_analyzer
    path = os.getenv("VISION_3DTODAY_PATH")
    if not path:
        return None
    path = Path(path).expanduser().resolve()
    # backend/app/services/vision_analyzer.py
    backend = path if (path / "app").is_dir() else path / "backend"
    if not (backend / "app" / "services" / "vision_analyzer.py").exists():
        logger.warning("VISION_3DTODAY_PATH указан, но vision_analyzer.py не найден: %s", backend)
        return None
    try:
        import sys
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
        from app.services.vision_analyzer import VisionAnalyzer
        _vision_analyzer = VisionAnalyzer(prefer_ollama=False)
        logger.info("✅ VisionAnalyzer из 3dtoday загружен (backend=%s)", backend)
        return _vision_analyzer
    except Exception as e:
        logger.warning("Не удалось загрузить VisionAnalyzer из 3dtoday: %s", e)
        return None


async def describe_images_via_3dtoday(
    image_urls: List[str],
    context_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Аннотирование изображений через VisionAnalyzer из 3dtoday.
    Возвращает формат, совместимый с LLMService.describe_images: {"images": [{index, url, description, alt}]}.
    """
    analyzer = _get_3dtoday_vision_analyzer()
    if not analyzer:
        return {"images": []}

    loop = asyncio.get_event_loop()
    results: List[Dict[str, Any]] = []

    def _analyze_one(idx: int, url: str) -> None:
        name = f"image_{idx}"
        try:
            out = analyzer.analyze_image_from_url(url, name)
            if out.get("success") and out.get("analysis"):
                desc = (out.get("analysis") or "").strip()
                results.append({
                    "index": idx,
                    "url": url,
                    "description": desc[:2000] if desc else "",
                    "alt": (desc[:200] + "…") if len(desc) > 200 else (desc or ""),
                })
            else:
                results.append({"index": idx, "url": url, "description": "", "alt": ""})
        except Exception as e:
            logger.warning("3dtoday VisionAnalyzer для %s: %s", url[:60], e)
            results.append({"index": idx, "url": url, "description": "", "alt": ""})

    # Вызываем синхронный analyze_image_from_url в executor, чтобы не блокировать event loop
    for idx, url in enumerate(image_urls):
        if not url:
            continue
        await loop.run_in_executor(None, _analyze_one, idx, url)

    results.sort(key=lambda x: x.get("index", 0))
    return {"images": results}


def is_3dtoday_vision_available() -> bool:
    """Проверка: настроен ли путь к 3dtoday и загружается ли VisionAnalyzer."""
    return os.getenv("USE_3DTODAY_VISION", "").lower() in ("1", "true", "yes") and _get_3dtoday_vision_analyzer() is not None
