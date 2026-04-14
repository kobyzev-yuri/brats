"""
Endpoints для работы с мультимодальной базой знаний (MMKB) и агентом‑библиотекарем.

Подход основан на проекте /mnt/ai/cnn/3dtoday:
- есть библиотекарь, который проверяет релевантность материала и дубликаты;
- библиотекарь делает краткое изложение и аннотации к изображениям перед сохранением в KB;
- администратор или n8n‑workflow могут сначала запросить решение библиотекаря, а затем сохранить запись в KB.
"""

import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from urllib.parse import urljoin
import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from models.requests import Category, TargetAudience, Priority
from models.responses import KBAddResponse
from services.kb_service import KBService
from services.mm_librarian import get_multimodal_librarian

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/mmkb", tags=["Multimodal KB"])


class MMKBImage(BaseModel):
    """Описание одного изображения, связанного с документом KB."""

    url: Optional[str] = Field(None, description="URL изображения (если хранится вне БД)")
    alt: Optional[str] = Field(None, description="Предлагаемый alt‑текст для сайта")
    description: Optional[str] = Field(None, description="Краткое описание изображения")
    annotations: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Дополнительные аннотации (например, зона интереса, тип объекта и т.п.)",
    )


class MMKBDocument(BaseModel):
    """Ссылка на документ (PDF, DOCX и т.п.) для выдачи агентом."""

    url: str = Field(..., description="URL документа")
    title: Optional[str] = Field(None, description="Название для отображения")
    description: Optional[str] = Field(None, description="Краткое описание")


class MMKBReviewRequest(BaseModel):
    """
    Запрос к библиотекарю: проанализировать материал (текст + изображения)
    перед добавлением в мультимодальную KB.
    """

    title: str = Field(..., description="Заголовок материала")
    content: str = Field(..., description="Полный текст материала")
    section: Optional[str] = Field(
        None,
        description="Раздел мультимодальной KB (например: settlement_info, product_info, pricing_offers, faq, objections, legal_finance)",
    )
    tags: List[str] = Field(default_factory=list, description="Теги/ключевые слова для поиска")
    images: List[MMKBImage] = Field(default_factory=list, description="Список связанных изображений")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные произвольные метаданные")
    analyze_images: bool = Field(
        default=False,
        description="Выполнять ли vision‑анализ изображений (медленнее и дороже)",
    )


class MMKBLibrarianResult(BaseModel):
    """Результат работы библиотекаря (см. описание в mm_librarian.py)."""

    decision: str
    reason: str
    relevance_score: float
    quality_score: float
    is_relevant: bool
    has_valuable_info: bool
    duplicate_check: Dict[str, Any]
    abstract: str
    summary: Dict[str, Any]
    filtered_content: str
    recommendations: List[str]
    key_points: List[str]
    image_annotations: List[Dict[str, Any]] = Field(default_factory=list)
    semantic_blocks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Структурированные смысловые блоки (разделы страницы, типы отделки, контакты и т.п.)",
    )


class MMKBReviewResponse(BaseModel):
    """Ответ на запрос review: библиотекарь + исходные данные."""

    title: str
    content: str
    section: Optional[str]
    tags: List[str]
    images: List[MMKBImage]
    metadata: Dict[str, Any]
    librarian_result: MMKBLibrarianResult


class MMKBSaveRequest(BaseModel):
    """
    Запрос на сохранение/создание записи в KB.

    Можно вызывать:
    - после review (передав librarian_result из UI);
    - напрямую (без библиотекаря, тогда решение будет None).
    """

    title: str = Field(..., description="Заголовок материала")
    content: str = Field(..., description="Содержимое для индексации в KB")
    section: Optional[str] = Field(
        None,
        description="Раздел мультимодальной KB (settlement_info, product_info, pricing_offers, faq, objections, legal_finance и т.п.)",
    )
    tags: List[str] = Field(default_factory=list, description="Теги/ключевые слова")
    images: List[MMKBImage] = Field(default_factory=list, description="Изображения, связанные с материалом")
    documents: List[MMKBDocument] = Field(
        default_factory=list,
        description="Ссылки на документы (PDF, DOCX) для выдачи агентом по запросу",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")

    # Параметры категорий KB (для совместимости с существующей схемой)
    category: Category = Field(
        default=Category.PRODUCT_INFO,
        description="Техническая категория KB (по умолчанию product_info)",
    )
    target_audience: TargetAudience = Field(
        default=TargetAudience.BOTH,
        description="Целевая аудитория (end_buyer/realtor/both)",
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Приоритет контента для выборки",
    )

    # Опциональное решение библиотекаря
    librarian_result: Optional[MMKBLibrarianResult] = Field(
        None,
        description="Результат работы библиотекаря (если был вызван /review)",
    )


class MMKBImportFromURLRequest(BaseModel):
    """
    Запрос на импорт материала по URL с сайта заказчика.
    LLM (через proxyapi.ru) сам загружает страницу и формирует черновой JSON‑документ,
    который затем проходит через библиотекаря.
    """

    url: str = Field(..., description="URL страницы на сайте заказчика")
    section: Optional[str] = Field(
        None,
        description="Желаемый раздел KB для импортируемого материала (если известен заранее)",
    )
    tags: List[str] = Field(default_factory=list, description="Предварительные теги (опционально)")
    llm_provider: Optional[str] = Field(
        None,
        description="Провайдер LLM (openai/gemini). Пока используется существующий LLMService (OpenAI через proxyapi.ru).",
    )
    model: Optional[str] = Field(
        None,
        description="Конкретная модель (опционально). Поддержка Gemini планируется на уровне LLMService.",
    )
    llm_timeout: Optional[int] = Field(
        None,
        description="Таймаут для анализа URL через LLM, в секундах",
    )
    analyze_images: bool = Field(
        default=False,
        description="Пытаться ли анализировать изображения со страницы (по найденным <img src=...>)",
    )


class MMKBImportFromURLResponse(BaseModel):
    """Ответ на импорт по URL: черновой документ + решение библиотекаря."""

    success: bool
    method: str
    url: str
    draft_document: Dict[str, Any]
    librarian_result: MMKBLibrarianResult


_kb_service = KBService()
_librarian = get_multimodal_librarian()


def _html_to_text(html: str, max_length: int = 20000) -> str:
    """
    Простейшее извлечение текста из HTML без внешних зависимостей.
    Удаляем <script>/<style>, теги и схлопываем пробелы.
    """
    if not html:
        return ""
    # Удаляем скрипты и стили
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    # Удаляем все теги
    text = re.sub(r"<[^>]+>", " ", html)
    # Схлопываем пробелы
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    if max_length and len(text) > max_length:
        text = text[:max_length] + "..."
    return text


def _get_tab_index_from_url(url: str) -> Optional[int]:
    """Извлекает номер вкладки из URL (#!/tab/...-N). Возвращает 1–4 или None."""
    if not url or "#!" not in url:
        return None
    match = re.search(r"#!/tab/[^-]+-(\d+)", url)
    if not match:
        return None
    n = int(match.group(1), 10)
    return n if 1 <= n <= 4 else None


# Маркеры секций вкладок для innovatory-club и аналогов (описание X = контент блока).
_TAB_BOUNDARIES = [
    (1, "описание BLACK BOX", "описание WHITE BOX"),
    (2, "описание WHITE BOX", "описание STANDARD"),
    (3, "описание STANDARD", "описание DESIGN"),
    (4, "описание DESIGN", "Рассчитать ипотеку"),
]


def _tab_section_positions(url: str, html: str) -> Optional[tuple]:
    """
    Возвращает (pos_start, pos_end) в html для секции вкладки из URL, или None.
    Позиции — границы символов в html, между ними лежит контент вкладки (в т.ч. галерея).
    """
    tab = _get_tab_index_from_url(url)
    if tab is None or not html:
        return None
    start_marker = None
    end_marker = None
    for t, start, end in _TAB_BOUNDARIES:
        if t == tab:
            start_marker = start
            end_marker = end
            break
    if not start_marker or not end_marker:
        return None
    html_lower = html.lower()
    pos_start = html_lower.find(start_marker.lower())
    pos_end = html_lower.find(end_marker.lower(), pos_start + len(start_marker) if pos_start >= 0 else 0)
    if pos_start >= 0 and pos_end > pos_start:
        return (pos_start, pos_end)
    return None


def _html_fragment_for_tab(url: str, html: str) -> str:
    """Фрагмент HTML между маркерами вкладки (для обратной совместимости)."""
    bounds = _tab_section_positions(url, html)
    if bounds is None:
        return html
    pos_start, pos_end = bounds
    return html[pos_start:pos_end]


def _image_urls_in_section(html: str, base_url: str, pos_start: int, pos_end: int) -> List[str]:
    """
    Извлекает URL изображений, чьи теги <img> попадают в диапазон [pos_start, pos_end].
    На Tilda: у <img> сначала идёт src (превью thb.), потом data-original (полный static.) —
    предпочитаем data-original. Порядок атрибутов в теге: data-original, data-src, src.
    """
    # Ищем начало каждого тега <img в секции (Tilda: возможен вид "img"src= без пробела)
    img_start_pattern = re.compile(r"<img\s", re.IGNORECASE)
    seen: set = set()
    result: List[str] = []
    for m in img_start_pattern.finditer(html):
        if m.start() < pos_start:
            continue
        if m.start() > pos_end:
            break
        tag_end = html.find(">", m.start())
        if tag_end < 0:
            continue
        tag = html[m.start() : tag_end + 1]
        # Предпочитаем data-original (полноразмерный), затем data-src, затем src
        url = None
        for attr in ("data-original", "data-src", "src"):
            attr_match = re.search(
                re.escape(attr) + r"\s*=\s*[\"']([^\"']+)[\"']",
                tag,
                re.IGNORECASE,
            )
            if attr_match:
                url = attr_match.group(1).strip()
                break
        if not url or url in seen:
            continue
        if url.lower().endswith(".svg"):
            continue
        seen.add(url)
        result.append(urljoin(base_url, url))
    return result


def _coerce_librarian_result(raw: Dict[str, Any]) -> MMKBLibrarianResult:
    """
    Гарантирует, что в результате библиотекаря есть все нужные поля,
    даже если LLM вернул неполный или странный JSON.
    """
    if raw is None or not isinstance(raw, dict):
        raw = {}

    safe_payload: Dict[str, Any] = {
        "decision": raw.get("decision", "needs_review"),
        "reason": raw.get("reason", "Нет явного решения, требуется ручная проверка."),
        "relevance_score": float(raw.get("relevance_score", 0.0) or 0.0),
        "quality_score": float(raw.get("quality_score", 0.0) or 0.0),
        "is_relevant": bool(raw.get("is_relevant", False)),
        "has_valuable_info": bool(raw.get("has_valuable_info", False)),
        "duplicate_check": raw.get("duplicate_check") or {},
        "abstract": raw.get("abstract", ""),
        "summary": raw.get("summary") or {},
        "filtered_content": raw.get("filtered_content", ""),
        "recommendations": raw.get("recommendations") or [],
        "key_points": raw.get("key_points") or [],
        "image_annotations": raw.get("image_annotations") or [],
        "semantic_blocks": raw.get("semantic_blocks") or {},
    }

    return MMKBLibrarianResult(**safe_payload)


@router.post("/review", response_model=MMKBReviewResponse)
async def review_document(request: MMKBReviewRequest) -> MMKBReviewResponse:
    """
    Пропустить материал через библиотекаря без сохранения в KB.
    Используется UI и/или n8n перед финальным сохранением.
    """
    try:
        librarian_result_dict = await _librarian.review_document(
            title=request.title,
            content=request.content,
            section=request.section,
            tags=request.tags,
            images=[img.model_dump() for img in request.images],
            metadata=request.metadata,
            analyze_images=request.analyze_images,
        )

        librarian_result = _coerce_librarian_result(librarian_result_dict)

        return MMKBReviewResponse(
            title=request.title,
            content=request.content,
            section=request.section,
            tags=request.tags,
            images=request.images,
            metadata=request.metadata,
            librarian_result=librarian_result,
        )
    except Exception as e:
        logger.error(f"Ошибка review_document в /api/mmkb/review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")


@router.post("/save", response_model=KBAddResponse)
async def save_document(request: MMKBSaveRequest) -> KBAddResponse:
    """
    Сохранить (создать) запись в KB на основе материала и (опционально) решения библиотекаря.

    - Контент идёт в поле `content` таблицы knowledge_base;
    - Всё остальное (заголовок, раздел, теги, изображения, abstract и т.п.) кладётся в metadata.
    """
    try:
        # Формируем metadata для KB
        kb_metadata: Dict[str, Any] = dict(request.metadata or {})
        kb_metadata.update(
            {
                "title": request.title,
                "section": request.section,
                "tags": request.tags,
                "images": [img.model_dump() for img in request.images],
                "documents": [doc.model_dump() for doc in request.documents],
            }
        )

        if request.librarian_result:
            kb_metadata["librarian"] = request.librarian_result.model_dump()

        # Источник всегда должен быть задан (для поиска по источнику)
        if not kb_metadata.get("source"):
            kb_metadata["source"] = (
                kb_metadata.get("source_url")
                or (request.metadata or {}).get("source_url")
                or "unknown"
            )

        chunk_id = await _kb_service.add_chunk(
            content=request.content,
            category=request.category.value,
            target_audience=request.target_audience.value,
            priority=request.priority.value,
            metadata=kb_metadata,
        )

        return KBAddResponse(
            success=True,
            chunk_id=chunk_id,
            message="Мультимодальный материал успешно добавлен в KB",
        )
    except Exception as e:
        logger.error(f"Ошибка сохранения документа в /api/mmkb/save: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}")


_UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
_UPLOADS_DIR.mkdir(exist_ok=True)
_ALLOWED_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")


@router.post("/upload_image")
async def upload_image(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Загрузка изображения для блоков оператора. Сохраняет файл в uploads/ и возвращает URL.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Нет имени файла")
    suf = Path(file.filename).suffix.lower()
    if suf not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Разрешены только изображения: {', '.join(_ALLOWED_IMAGE_EXT)}",
        )
    name = f"{uuid.uuid4().hex}{suf}"
    path = _UPLOADS_DIR / name
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл не более 10 МБ")
    path.write_bytes(content)
    base = str(request.base_url).rstrip("/")
    url = f"{base}/static/{name}"
    return {"url": url, "filename": name}


@router.post("/import_from_url", response_model=MMKBImportFromURLResponse)
async def import_from_url(request: MMKBImportFromURLRequest) -> MMKBImportFromURLResponse:
    """
    Импорт материала по URL с сайта заказчика через LLM.

    Текущая реализация:
    - скачивает HTML страницы по URL;
    - преобразует HTML в простой текст;
    - передаёт текст в библиотекаря для оценки релевантности/качества и поиска дубликатов;
    - возвращает черновой документ + решение библиотекаря.
    """
    try:
        # Увеличиваем таймаут для скачивания страницы (по умолчанию 30 секунд)
        fetch_timeout = 30
        # Таймаут для LLM запросов (по умолчанию 300 секунд = 5 минут для анализа изображений)
        llm_timeout = request.llm_timeout or 300

        # 1. Скачиваем страницу (без кэша — актуальный HTML и порядок блоков/картинок)
        logger.info(f"Загрузка страницы для MMKB по URL: {request.url} (timeout={fetch_timeout}s)")
        async with httpx.AsyncClient(timeout=fetch_timeout) as client:
            response = await client.get(
                request.url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; BRATS-KB-Bot/1.0)",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                },
            )
            response.raise_for_status()
            html_content = response.text

        # 2. Грубое извлечение текста
        text_content = _html_to_text(html_content, max_length=20000)
        if not text_content:
            raise HTTPException(
                status_code=400,
                detail="Не удалось извлечь текст из указанного URL",
            )

        # Фильтр иконок/мусора по URL
        def _is_probably_icon(url: str) -> bool:
            lower = url.lower()
            if re.search(r"resize/\d+x", lower) or re.search(r"/\d+x/", lower):
                return True
            for k in ("icon", "icons8", "phone", "whatsapp", "telegram", "vk", "viber", "instagram", "insta", "logo", "arrow", "strelka", "strela", "adress", "address", "for_site.png"):
                if k in lower:
                    return True
            return False

        # 2b–3. Изображения: при наличии вкладки в URL берём только те <img>, что лежат между маркерами секции (по позиции в HTML).
        # Так в блок STANDARD попадает вся галерея вкладки, а не картинки из BLACK BOX.
        images_payload: List[Dict[str, Any]] = []
        bounds = _tab_section_positions(request.url, html_content)
        if bounds:
            pos_start, pos_end = bounds
            urls_in_section = _image_urls_in_section(html_content, request.url, pos_start, pos_end)
            for full_url in urls_in_section:
                if _is_probably_icon(full_url):
                    continue
                if len(images_payload) >= 25:
                    break
                images_payload.append({"url": full_url, "alt": "", "description": "", "annotations": {"index": len(images_payload)}})
            if images_payload:
                logger.info("Изображения взяты по позициям секции вкладки (галерея вкладки), count=%s", len(images_payload))
        if not images_payload:
            # Нет вкладки или в секции не нашлось img — собираем из всего HTML (ограничение 25)
            image_matches = re.findall(
                r'<img[^>]+(?:src|data-src|data-original)\s*=\s*["\']([^"\']+)["\']',
                html_content,
                flags=re.IGNORECASE,
            )
            for src in image_matches:
                full_url = urljoin(request.url, src)
                if _is_probably_icon(full_url):
                    continue
                if len(images_payload) >= 25:
                    break
                images_payload.append({"url": full_url, "alt": "", "description": "", "annotations": {"index": len(images_payload)}})
        for idx, img in enumerate(images_payload):
            img["annotations"]["index"] = idx

        # 4. Формируем черновой документ
        draft_document: Dict[str, Any] = {
            "title": request.url,
            "content": text_content,
            "section": request.section,
            "tags": request.tags,
            "source_url": request.url,
            "raw_html_length": len(html_content),
            "images": images_payload,
        }

        # 5. Прогоняем через библиотекаря
        import time
        start_time = time.time()
        logger.info(f"Начало анализа через библиотекаря (analyze_images={request.analyze_images}, images_count={len(images_payload)})")
        
        librarian_result_dict = await _librarian.review_document(
            title=draft_document["title"],
            content=draft_document["content"],
            section=request.section,
            tags=request.tags,
            images=images_payload,
            metadata={"source_url": request.url},
            analyze_images=request.analyze_images,
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Библиотекарь завершил анализ за {elapsed_time:.2f} секунд")

        librarian_result = _coerce_librarian_result(librarian_result_dict)

        return MMKBImportFromURLResponse(
            success=True,
            method="html_fetch_and_librarian_v1",
            url=request.url,
            draft_document=draft_document,
            librarian_result=librarian_result,
        )
    except Exception as e:
        logger.error(f"Ошибка в /api/mmkb/import_from_url: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка импорта по URL: {str(e)}")



