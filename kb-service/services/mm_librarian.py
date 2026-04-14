"""
Мультимодальный агент‑библиотекарь для анализа материалов перед добавлением в KB.

Задачи:
- проверить релевантность материала домену заказчика (недвижимость, коттеджные посёлки);
- оценить качество и наличие полезной информации;
- проверить дубликаты через KBService.search;
- сгенерировать краткое изложение (abstract) и ключевые пункты;
- при наличии изображений — сгенерировать аннотации и описания;
- вернуть структурированное решение: approve / reject / needs_review.

По подходу опирается на проект /mnt/ai/cnn/3dtoday (KBLibrarianAgent),
но адаптирован под текущую архитектуру kb-service (PostgreSQL + pgvector, LLMService).
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from services.kb_service import KBService
from services.llm_service import get_llm_service
from services.gemini_text_service import get_gemini_text_service
from utils.db import get_db_pool

try:
    from services.vision_3dtoday_adapter import describe_images_via_3dtoday, is_3dtoday_vision_available
except ImportError:
    describe_images_via_3dtoday = None
    is_3dtoday_vision_available = lambda: False

logger = logging.getLogger(__name__)

# Соответствие номера вкладки в URL (#!/tab/...-N) типу ремонта
_URL_TAB_TO_LABEL = {"1": "BLACK BOX", "2": "WHITE BOX", "3": "STANDARD", "4": "DESIGN"}
# Для сопоставления вкладки с type блока (в блоке type = BLACK_BOX, STANDARD и т.д.)
_TAB_LABEL_TO_BLOCK_TYPE = {"BLACK BOX": "BLACK_BOX", "WHITE BOX": "WHITE_BOX", "STANDARD": "STANDARD", "DESIGN": "DESIGN"}


def _tab_from_url(url: Optional[str]) -> Optional[str]:
    """Извлекает метку вкладки из source_url (например ...#!/tab/1063728081-3 -> STANDARD)."""
    if not url or "#!" not in url:
        return None
    match = re.search(r"#!/tab/[^\-]+\-(\d+)", url)
    if not match:
        return None
    return _URL_TAB_TO_LABEL.get(match.group(1))


def _extract_section_text(text: str, start_marker: str, end_marker: str, max_len: int = 2000) -> str:
    """Извлекает фрагмент текста между start_marker и end_marker (для блока вкладки)."""
    if not text:
        return ""
    lower = text.lower()
    i = lower.find(start_marker.lower())
    if i < 0:
        return ""
    j = lower.find(end_marker.lower(), i + len(start_marker))
    if j < 0:
        j = len(text)
    return text[i:j].strip()[:max_len]


def _extract_phone_email(text: str) -> tuple:
    """Извлекает первый телефон и первый email из текста. Возвращает (phone, email)."""
    phone, email = "", ""
    if not text:
        return phone, email
    # Телефон: +7 (999) 123-45-67 или 8 (999) 123-45-67 и т.п.
    m = re.search(r"\+?7\s*\(?\d{3}\)?\s*\d{3}[-\s]?\d{2}[-\s]?\d{2}", text)
    if m:
        phone = m.group(0).strip()
    # Email
    m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    if m:
        email = m.group(0).strip()
    return phone, email


def _postprocess_librarian_result(
    result: Dict[str, Any],
    content: str,
    tab_label: Optional[str],
    image_annotations: List[Dict[str, Any]],
) -> None:
    """
    Постобработка результата библиотекаря:
    - filtered_content собираем из текста смысловых блоков (для KB).
    - Для вкладки из URL подменяем gallery блока только изображениями с непустым description от vision.
    - В блок CONTACTS дописываем телефон/email из сырого текста, если их там нет.
    """
    blocks = (result.get("semantic_blocks") or {}).get("blocks") or []
    if not blocks:
        return

    # 1. filtered_content — полезный текст для KB из блоков
    parts = []
    for b in blocks:
        desc = (b.get("description") or "").strip()
        if desc:
            parts.append(desc)
        price = (b.get("price") or "").strip()
        if price:
            parts.append(f"Цена/условия: {price}")
        inc = b.get("includes") or []
        if inc:
            parts.append("Включает: " + "; ".join(str(x) for x in inc if x))
    if parts:
        result["filtered_content"] = "\n\n".join(parts)

    # 2. Gallery активной вкладки и блок вкладки, если его нет
    if tab_label and image_annotations:
        block_type = _TAB_LABEL_TO_BLOCK_TYPE.get(tab_label)
        if block_type:
            gallery = [
                {"url": a.get("url"), "image_url": a.get("url"), "description": a.get("description") or "", "alt": a.get("alt") or ""}
                for a in image_annotations
            ]
            found = False
            for b in blocks:
                if (b.get("type") or "").strip() == block_type:
                    b["gallery"] = gallery
                    found = True
                    break
            # Если блока вкладки нет (Gemini не вернул) — добавляем
            if not found:
                desc = _extract_section_text(content or "", "STANDARD (стандартный ремонт)", "DESIGN (дизайнерский ремонт)")
                if not desc:
                    desc = f"Вариант отделки {tab_label}: готовый ремонт под ключ. Галерея фотографий объекта."
                blocks.append({
                    "type": block_type,
                    "title": f"{tab_label} (стандартный ремонт)" if block_type == "STANDARD" else tab_label,
                    "description": desc,
                    "includes": [],
                    "price": "",
                    "gallery": gallery,
                })

    # 3. CONTACTS — дописать телефон и email из сырого текста, если в блоке их нет
    phone, email = _extract_phone_email(content)
    for b in blocks:
        if (b.get("type") or "").strip() != "CONTACTS":
            continue
        desc = (b.get("description") or "").strip()
        need_append = []
        if phone and phone not in desc:
            need_append.append(f"Телефон: {phone}")
        if email and email not in desc:
            need_append.append(f"Email: {email}")
        if need_append:
            b["description"] = (desc + "\n\n" + "\n".join(need_append)).strip()
        break


class MultimodalLibrarian:
    """
    Агент‑библиотекарь для мультимодальной базы знаний.

    Работает поверх:
    - KBService (поиск дубликатов в PostgreSQL + pgvector);
    - LLMService (GPT‑4o через proxyapi.ru; далее может быть расширен до Gemini 3).
    """

    def __init__(self) -> None:
        self.kb_service = KBService()
        # GPT‑4o сервис оставляем для vision‑анализа картинок,
        # а текстовый анализ и решение библиотекаря переносим на Gemini.
        self.llm_service = get_llm_service()
        self.gemini_service = get_gemini_text_service()
        logger.info("✅ MultimodalLibrarian инициализирован (Gemini + GPT-4o vision)")

    async def review_document(
        self,
        title: str,
        content: str,
        section: Optional[str] = None,
        tags: Optional[List[str]] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        analyze_images: bool = False,
    ) -> Dict[str, Any]:
        """
        Полный цикл анализа документа и принятия решения о публикации.

        Возвращает словарь с полями:
        - decision: approve|reject|needs_review
        - reason: строка
        - relevance_score, quality_score, is_relevant, has_valuable_info
        - duplicate_check: информация о дубликатах
        - abstract, summary, filtered_content, key_points, recommendations
        - image_annotations: аннотации к изображениям (если есть)
        - semantic_blocks: структурированные смысловые блоки страницы
        """
        try:
            base_metadata = metadata or {}
            tags_list = tags or []
            images_list = images or []

            # Явно вытаскиваем source_url из metadata (если есть).
            source_url = base_metadata.get("source_url")
            tab_label = _tab_from_url(source_url)

            # Шаг 1. Проверка дубликатов через KBService
            duplicate_check = await self._check_duplicates(
                title=title,
                content=content,
                section=section,
                source_url=source_url,
            )

            # Шаг 2. Вызов Gemini для текстовой оценки и структурирования
            llm_result = await self._call_llm_librarian(
                title=title,
                content=content,
                section=section,
                tags=tags_list,
                images=images_list,
                metadata=base_metadata,
                duplicate_check=duplicate_check,
            )

            # Шаг 3. Анализ изображений (vision): приоритет — 3dtoday (если настроен), иначе Gemini, иначе GPT-4o
            image_annotations: List[Dict[str, Any]] = llm_result.get("image_annotations", [])
            if analyze_images and images_list:
                image_urls = [img.get("url") for img in images_list if img.get("url")]
                if image_urls:
                    vision_context = (content or "").strip()
                    if tab_label:
                        vision_context = (
                            "[Вкладка страницы: "
                            + tab_label
                            + ". Кратко опиши каждое фото для базы знаний: интерьер, отделка, помещение.] "
                            + vision_context
                        )
                    batch_size = 8
                    all_annotations: List[Dict[str, Any]] = []
                    use_3dtoday = is_3dtoday_vision_available()
                    use_gemini_vision = not use_3dtoday and __import__("os").environ.get("USE_GEMINI_FOR_VISION", "").lower() in ("1", "true", "yes")
                    gemini_vision = get_gemini_vision_service() if use_gemini_vision else None
                    for start in range(0, len(image_urls), batch_size):
                        chunk = image_urls[start : start + batch_size]
                        try:
                            if use_3dtoday and describe_images_via_3dtoday:
                                vision_result = await describe_images_via_3dtoday(
                                    image_urls=chunk,
                                    context_text=vision_context[:1500],
                                )
                            elif gemini_vision:
                                vision_result = await gemini_vision.describe_images(
                                    image_urls=chunk,
                                    context_text=vision_context[:1500],
                                )
                            else:
                                vision_result = await self.llm_service.describe_images(
                                    image_urls=chunk,
                                    context_text=vision_context[:1500],
                                )
                            raw = vision_result.get("images", []) or []
                            for ann in raw:
                                idx = ann.get("index")
                                if isinstance(idx, int) and 0 <= idx < len(chunk):
                                    global_idx = start + idx
                                    ann = dict(ann)
                                    ann["index"] = global_idx
                                    ann["url"] = image_urls[global_idx]
                                    all_annotations.append(ann)
                        except Exception as e:
                            logger.warning(f"Vision батч {start}-{start + len(chunk)}: {e}")
                            for i in range(len(chunk)):
                                all_annotations.append({
                                    "index": start + i,
                                    "url": image_urls[start + i],
                                    "description": "",
                                    "alt": "",
                                })
                    if all_annotations:
                        image_annotations = all_annotations
                    # Дополняем аннотации для картинок, которые vision не вернул
                    by_idx = {a["index"]: a for a in image_annotations}
                    for i in range(len(image_urls)):
                        if i not in by_idx:
                            image_annotations.append({
                                "index": i,
                                "url": image_urls[i],
                                "description": "",
                                "alt": "",
                            })
                    image_annotations.sort(key=lambda a: a.get("index", 0))

            # Объединяем данные, гарантируем наличие ключевых полей
            result: Dict[str, Any] = {
                "decision": llm_result.get("decision", "needs_review"),
                "reason": llm_result.get("reason", "Нет явного решения, требуется ручная проверка."),
                "relevance_score": float(llm_result.get("relevance_score", 0.0)),
                "quality_score": float(llm_result.get("quality_score", 0.0)),
                "is_relevant": bool(llm_result.get("is_relevant", False)),
                "has_valuable_info": bool(llm_result.get("has_valuable_info", False)),
                "duplicate_check": duplicate_check or llm_result.get("duplicate_check", {}),
                "abstract": llm_result.get("abstract", ""),
                "summary": llm_result.get("summary", {}),
                "filtered_content": llm_result.get("filtered_content", content[:500] + "..." if content else ""),
                "recommendations": llm_result.get("recommendations", []),
                "key_points": llm_result.get("key_points", []),
                "image_annotations": image_annotations,
                "semantic_blocks": llm_result.get("semantic_blocks", {}),
            }

            # Постобработка: filtered_content из блоков, gallery вкладки из vision, CONTACTS + телефон/email
            _postprocess_librarian_result(result, content or "", tab_label, image_annotations)

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка в MultimodalLibrarian.review_document: {e}", exc_info=True)
            return {
                "decision": "needs_review",
                "reason": f"Ошибка анализа: {str(e)}",
                "relevance_score": 0.0,
                "quality_score": 0.0,
                "is_relevant": False,
                "has_valuable_info": False,
                "duplicate_check": {"is_duplicate": False},
                "abstract": "",
                "summary": {},
                "filtered_content": content[:500] + "..." if content else "",
                "recommendations": ["Требуется ручная проверка администратором."],
                "key_points": [],
                "image_annotations": [],
            }

    async def _check_duplicates(
        self,
        title: str,
        content: str,
        section: Optional[str],
        source_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Простейшая проверка дубликатов: ищем похожие документы по заголовку.
        Использует KBService.search с запросом = title (и частью контента).
        """
        try:
            query = title.strip() or content[:200]
            if not query:
                return {"is_duplicate": False}

            # Используем прямой доступ к KBService.search
            results = await self.kb_service.search(
                query=query,
                limit=5,
                category=None,
                target_audience=None,
                priority=None,
                settlement_id=None,
                min_similarity=0.7,
                use_case=None,
                stage=None,
            )

            # Семантические (по тексту) результаты
            sem_results = results or []

            similar_docs = []
            similarity_scores = []
            is_duplicate_semantic = False
            duplicate_reason_semantic = ""

            for row in sem_results:
                sim = float(row.get("similarity", 0.0))
                similarity_scores.append(sim)
                similar_docs.append(
                    {
                        "id": row.get("id"),
                        "title": row.get("metadata", {}).get("title"),
                        "section": row.get("metadata", {}).get("section"),
                        "similarity": sim,
                    }
                )
                # Порог для "почти точного" дубликата
                if sim >= 0.9:
                    is_duplicate_semantic = True
                    duplicate_reason_semantic = "Найден документ с очень высокой семантической схожестью (>= 0.9)."

            # Дополнительно проверяем дубликаты по source_url (если указан)
            is_duplicate_url = False
            url_matches: List[Dict[str, Any]] = []
            if source_url:
                # Ищем документы, где metadata->>'source_url' совпадает
                pool = await get_db_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        f"""
                        SELECT id, metadata
                        FROM {self.kb_service.kb_table}
                        WHERE metadata->>'source_url' = $1
                        """,
                        source_url,
                    )
                    for row in rows:
                        meta = (
                            row["metadata"]
                            if isinstance(row["metadata"], dict)
                            else json.loads(row["metadata"])
                            if row["metadata"]
                            else {}
                        )
                        url_matches.append(
                            {
                                "id": row["id"],
                                "title": meta.get("title"),
                                "section": meta.get("section"),
                                "source_url": meta.get("source_url"),
                            }
                        )
                if url_matches:
                    is_duplicate_url = True

            is_duplicate = is_duplicate_semantic or is_duplicate_url
            reasons = []
            if duplicate_reason_semantic:
                reasons.append(duplicate_reason_semantic)
            if is_duplicate_url:
                reasons.append("Найден документ с тем же source_url.")
            duplicate_reason = " ".join(reasons)

            recommendation = "merge" if is_duplicate else "approve"

            return {
                "is_duplicate": is_duplicate,
                "duplicate_reason": duplicate_reason,
                "similar_docs": similar_docs,
                "similarity_scores": similarity_scores,
                "url_matches": url_matches,
                "is_duplicate_by_url": is_duplicate_url,
                "recommendation": recommendation,
            }

        except Exception as e:
            logger.error(f"Ошибка проверки дубликатов: {e}", exc_info=True)
            return {"is_duplicate": False, "error": str(e)}

    async def _call_llm_librarian(
        self,
        title: str,
        content: str,
        section: Optional[str],
        tags: List[str],
        images: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        duplicate_check: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Вызов LLM с промптом библиотекаря.
        Ожидается, что модель вернёт корректный JSON со структурой результата.
        """
        system_prompt = (
            "Ты — библиотекарь мультимодальной базы знаний для отдела продаж недвижимости.\n"
            "Главная цель: смысловые блоки (semantic_blocks.blocks) должны содержать ВСЮ полезную информацию из страницы, "
            "чтобы каждый блок можно было сразу сохранить в KB без обращения к сырому тексту.\n\n"
            "КОНТАКТЫ (блок CONTACTS):\n"
            "Обязательно скопируй из сырого текста в точности: полный адрес, телефон (например +7 (988) 199-89-98 — цифры и скобки как на сайте), "
            "email (например innovatory-club@yandex.ru), график просмотра (например «ежедневно с 10:00 до 17:00»). "
            "Телефон и email не заменяй и не пропускай — они должны быть в description или в отдельном поле блока.\n\n"
            "ОСТАЛЬНЫЕ БЛОКИ:\n"
            "- description: полный текст. includes: полный список «что включает». price: полная строка с примечаниями.\n"
            "- BLACK_BOX, WHITE_BOX, STANDARD, DESIGN: полное описание, площади (140 м², 80 м², 60 м²), полный список «что включает», полная цена.\n"
            "- STANDARD: добавь варианты отделки (2 керамогранита, 6 ламинатов, 6 оттенков стен, 50 потолков, 6 плиток санузла).\n"
            "- ADVANTAGES, LAYOUTS: полные списки.\n"
            "- Добавь один блок с type OTHER, title «Краткое изложение», description = твой abstract (2–4 предложения сути страницы). Так абстракт можно сохранить в KB.\n\n"
            "ВКЛАДКА ИЗ URL (metadata.source_url):\n"
            "Если в URL есть хэш вкладки (#!/tab/...-1 = BLACK BOX, ...-2 = WHITE BOX, ...-3 = STANDARD, ...-4 = DESIGN), страница открыта на этой вкладке. "
            "В галерею блока этой вкладки включай только изображения, которые по смыслу соответствуют этому типу ремонта. "
            "Для вкладки STANDARD не включай в галерею STANDARD фото с черновой отделкой (только готовый/предчистовой/стандартный ремонт). "
            "В image_annotations: для картинок, которые явно с другой вкладки (например черновая отделка при URL с ...-3 STANDARD), оставь description пустым или не включай их.\n\n"
            "key_points оставь []. Игнорируй навигацию, кнопки, формы, футер.\n\n"
            "Верни строго один JSON без пояснений:\n"
            "{\n"
            '  \"decision\": \"approve|reject|needs_review\",\n'
            '  \"reason\": \"кратко\",\n'
            '  \"relevance_score\": 0.0-1.0,\n'
            '  \"quality_score\": 0.0-1.0,\n'
            '  \"is_relevant\": true/false,\n'
            '  \"has_valuable_info\": true/false,\n'
            '  \"abstract\": \"2-4 предложения\",\n'
            '  \"summary\": {},\n'
            '  \"filtered_content\": \"...\",\n'
            '  \"key_points\": [],\n'
            '  \"recommendations\": [],\n'
            '  \"image_annotations\": [ {\"index\": N, \"description\": \"... или пусто если не та вкладка\", \"alt\": \"\"} ],\n'
            '  \"semantic_blocks\": {\n'
            '    \"blocks\": [\n'
            '      {\"type\": \"...\", \"title\": \"...\", \"description\": \"ПОЛНЫЙ текст\", \"includes\": [], \"price\": \"\", \"gallery\": []},\n'
            '      {\"type\": \"OTHER\", \"title\": \"Краткое изложение\", \"description\": \"abstract текст\", \"includes\": [], \"price\": \"\", \"gallery\": []}\n'
            "    ]\n"
            "  }\n"
            "}\n"
        )

        doc_payload = {
            "title": title,
            "section": section,
            "tags": tags,
            "source_url": metadata.get("source_url"),
            "metadata": metadata,
            "content_preview": content[:4000] if content else "",
            "images": images,
            "duplicate_check": duplicate_check,
        }

        user_message = (
            "Проанализируй следующий материал для базы знаний и верни только JSON со структурой, "
            "описанной в системном сообщении.\n\n"
            f"ДОКУМЕНТ:\n{json.dumps(doc_payload, ensure_ascii=False, indent=2)}"
        )

        prompt = (
            "Проанализируй следующий материал для базы знаний и верни только JSON со структурой, "
            "описанной в системном сообщении.\n\n"
            f"ДОКУМЕНТ:\n{json.dumps(doc_payload, ensure_ascii=False, indent=2)}"
        )

        llm_result = await self.gemini_service.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            max_output_tokens=8192,
        )
        return llm_result

    @staticmethod
    def _safe_parse_json(text: str) -> Dict[str, Any]:
        """
        Безопасный парсинг JSON: пытаемся найти первый и последний символы фигурных скобок.
        """
        if not text:
            return {}

        text = text.strip()
        # Если уже выглядит как чистый JSON
        try:
            return json.loads(text)
        except Exception:
            pass

        # Пытаемся вырезать подстроку между первой и последней фигурной скобкой
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = text[start : end + 1]
                return json.loads(candidate)
        except Exception:
            logger.warning("Не удалось распарсить JSON из ответа LLM")

        return {}


# Глобальный экземпляр библиотекаря (по аналогии с LLMService/RAGService)
_mm_librarian: Optional[MultimodalLibrarian] = None


def get_multimodal_librarian() -> MultimodalLibrarian:
    """
    Получить (или создать) глобальный экземпляр мультимодального библиотекаря.
    """
    global _mm_librarian
    if _mm_librarian is None:
        _mm_librarian = MultimodalLibrarian()
    return _mm_librarian


