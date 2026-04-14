"""
Простой web-интерфейс (Streamlit) для управления базой знаний (KB).

Функции:
- Просмотр списка chunks с фильтрами (category, source, search по тексту)
- Просмотр/редактирование одного chunk (content, category, priority, target_audience, is_active)
- Ручной импорт текста/файла в KB
- Просмотр базовой статистики KB

Использует REST API KB Service (http://localhost:8001 по умолчанию).
"""

import os
import re
from typing import List, Dict, Any, Optional

import requests
import streamlit as st
from dotenv import load_dotenv


# Загружаем конфигурацию
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, "config.env"))


def get_api_base_url() -> str:
    # Можно переопределить через переменную окружения KB_API_URL
    return os.getenv("KB_API_URL", "http://localhost:8001")


API_BASE = get_api_base_url()


def _fetch_image_bytes(url: str, timeout: int = 10) -> Optional[bytes]:
    """Загружает изображение по URL и возвращает байты для отображения в UI."""
    if not url or not url.startswith("http"):
        return None
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible; KB-Admin/1.0)"})
        resp.raise_for_status()
        ct = (resp.headers.get("Content-Type") or "").lower()
        if "image/" not in ct and not url.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            return None
        return resp.content
    except Exception:
        return None


def kb_health() -> Dict[str, Any]:
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        if resp.status_code == 200:
            return resp.json()
        return {"status": "error", "detail": resp.text}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def kb_search(query: str, limit: int = 20, category: Optional[str] = None,
              target_audience: Optional[str] = None,
              min_similarity: float = 0.0) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "query": query or "",
        "limit": limit,
        "min_similarity": min_similarity,
    }
    if category:
        payload["category"] = category
    if target_audience:
        payload["target_audience"] = target_audience

    resp = requests.post(
        f"{API_BASE}/api/kb/search",
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()


def kb_list_chunks(limit: int = 2000) -> List[Dict[str, Any]]:
    """Список активных chunk (id + title) — только существующие в базе."""
    resp = requests.get(f"{API_BASE}/api/kb/list", params={"limit": limit}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("chunks", [])


def kb_get_chunk(chunk_id: int) -> Dict[str, Any]:
    resp = requests.get(f"{API_BASE}/api/kb/{chunk_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def kb_update_chunk(chunk_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.put(
        f"{API_BASE}/api/kb/{chunk_id}",
        json=payload,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def kb_delete_chunk(chunk_id: int, soft_delete: bool = True) -> Dict[str, Any]:
    resp = requests.delete(
        f"{API_BASE}/api/kb/{chunk_id}",
        params={"soft_delete": "true" if soft_delete else "false"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def kb_import_text(content: str, category: str, target_audience: str = "both",
                   chunk_size: int = 3000, chunk_overlap: int = 300,
                   settlement_id: Optional[int] = None,
                   source: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Импорт текста в KB. metadata.images / metadata.documents — для релевантного ответа агента с медиа."""
    payload: Dict[str, Any] = {
        "content": content,
        "category": category,
        "target_audience": target_audience,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    if settlement_id is not None:
        payload["settlement_id"] = settlement_id
    if source:
        payload["source"] = source
    if metadata:
        payload["metadata"] = metadata

    resp = requests.post(
        f"{API_BASE}/api/kb/import",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def kb_import_document(
    file_bytes: bytes,
    filename: str,
    category: str = "product_info",
    target_audience: str = "both",
    source: str = "",
    chunk_size: int = 3000,
    chunk_overlap: int = 300,
) -> Dict[str, Any]:
    """Импорт документа (TXT, PDF, Word, PowerPoint) в KB через POST /api/kb/import_document."""
    API_BASE = get_api_base_url()
    with requests.post(
        f"{API_BASE}/api/kb/import_document",
        files={"file": (filename, file_bytes)},
        data={
            "category": category,
            "target_audience": target_audience,
            "source": source or filename,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        },
        timeout=120,
    ) as resp:
        resp.raise_for_status()
        return resp.json()


def kb_stats() -> Dict[str, Any]:
    resp = requests.get(f"{API_BASE}/api/kb/stats", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ===== Мультимодальная KB: вызовы API =====

def mmkb_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вызов /api/mmkb/review для прогонки материала через библиотекаря
    без сохранения в KB.
    """
    resp = requests.post(
        f"{API_BASE}/api/mmkb/review",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def mmkb_save(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вызов /api/mmkb/save для сохранения мультимодального материала в KB.
    """
    resp = requests.post(
        f"{API_BASE}/api/mmkb/save",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def mmkb_upload_image(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Загрузка изображения на сервер KB. Возвращает {url, filename}."""
    API_BASE = get_api_base_url()
    with requests.post(
        f"{API_BASE}/api/mmkb/upload_image",
        files={"file": (filename, file_bytes)},
        timeout=30,
    ) as resp:
        resp.raise_for_status()
        return resp.json()


def mmkb_import_from_url(payload: Dict[str, Any], timeout: int = 600) -> Dict[str, Any]:
    """
    Вызов /api/mmkb/import_from_url для импорта чернового материала по URL
    с последующей проверкой библиотекарем.
    
    Args:
        payload: Данные для импорта (url, section, tags, analyze_images)
        timeout: Таймаут в секундах (по умолчанию 600 = 10 минут для анализа изображений)
    """
    resp = requests.post(
        f"{API_BASE}/api/mmkb/import_from_url",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def sidebar_health():
    st.sidebar.header("KB Service")
    health = kb_health()
    status = health.get("status", "unknown")
    if status == "healthy":
        st.sidebar.success("KB Service: healthy")
    else:
        st.sidebar.error(f"KB Service: {status}")
        st.sidebar.write(health.get("detail"))

    st.sidebar.markdown("---")
    st.sidebar.write("API base URL:")
    st.sidebar.code(API_BASE, language="bash")


def page_overview():
    st.title("KB Admin — Обзор и поиск")

    # Сохраняем параметры поиска в session_state, чтобы не терять их при rerun
    if "search_query" not in st.session_state:
        st.session_state["search_query"] = ""
    if "search_category" not in st.session_state:
        st.session_state["search_category"] = ""
    if "search_min_sim" not in st.session_state:
        st.session_state["search_min_sim"] = 0.3
    if "search_limit" not in st.session_state:
        st.session_state["search_limit"] = 20

    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        query = st.text_input("Поисковый запрос", value=st.session_state["search_query"])
    with col2:
        category = st.selectbox(
            "Категория (фильтр)",
            options=["", "product_info", "sales_script", "objection_handling",
                     "target_audience", "tone_of_voice", "contacts", "pricing", "location"],
            index=0
            if not st.session_state["search_category"]
            else ["", "product_info", "sales_script", "objection_handling",
                  "target_audience", "tone_of_voice", "contacts", "pricing", "location"]
            .index(st.session_state["search_category"]),
        )
    with col3:
        min_sim = st.slider(
            "min_similarity",
            0.0,
            1.0,
            float(st.session_state["search_min_sim"]),
            0.05,
        )

    limit = st.slider(
        "Лимит результатов",
        5,
        100,
        int(st.session_state["search_limit"]),
        5,
    )

    # Показываем результаты поиска, если они есть в session_state (после rerun)
    if "last_search_results" in st.session_state and st.session_state.get("last_search_results"):
        total = st.session_state.get("last_search_total", 0)
        results = st.session_state["last_search_results"]
        st.write(f"Найдено: **{total}**")
        
        for r in results:
            with st.expander(
                f"[{r['id']}] {r['metadata'].get('category', '')} "
                f"(sim={r.get('similarity', 0):.3f})"
            ):
                st.write("**Категория**:", r["metadata"].get("category"))
                st.write("**Целевая аудитория**:", r["metadata"].get("target_audience"))
                st.write("**Приоритет**:", r["metadata"].get("priority"))
                st.write("**Источник**:", r["metadata"].get("source"))
                st.write("**Содержимое:**")
                st.text(r["content"])

                if st.button(f"Открыть для редактирования #{r['id']}", key=f"edit_{r['id']}"):
                    # Сохраняем ID для редактирования и делаем rerun
                    st.session_state["edit_chunk_id"] = r["id"]
                    # Делаем rerun для отображения формы редактирования
                    if hasattr(st, 'rerun'):
                        st.rerun()
                    else:
                        st.experimental_rerun()

    if st.button("Искать", type="primary"):
        try:
            # сохраняем последние параметры поиска
            st.session_state["search_query"] = query
            st.session_state["search_category"] = category
            st.session_state["search_min_sim"] = min_sim
            st.session_state["search_limit"] = limit

            data = kb_search(
                query=query or "*",
                limit=limit,
                category=category or None,
                min_similarity=min_sim,
            )
            total = data.get("total_found", 0)
            results: List[Dict[str, Any]] = data.get("results", [])
            
            # Сохраняем результаты в session_state для отображения после rerun
            st.session_state["last_search_results"] = results
            st.session_state["last_search_total"] = total
            
            st.write(f"Найдено: **{total}**")

            for r in results:
                with st.expander(
                    f"[{r['id']}] {r['metadata'].get('category', '')} "
                    f"(sim={r.get('similarity', 0):.3f})"
                ):
                    st.write("**Категория**:", r["metadata"].get("category"))
                    st.write("**Целевая аудитория**:", r["metadata"].get("target_audience"))
                    st.write("**Приоритет**:", r["metadata"].get("priority"))
                    st.write("**Источник**:", r["metadata"].get("source"))
                    st.write("**Содержимое:**")
                    st.text(r["content"])

                    if st.button(f"Открыть для редактирования #{r['id']}", key=f"edit_new_{r['id']}"):
                        # Сохраняем ID для редактирования и делаем rerun
                        st.session_state["edit_chunk_id"] = r["id"]
                        # Делаем rerun для отображения формы редактирования
                        if hasattr(st, 'rerun'):
                            st.rerun()
                        else:
                            st.experimental_rerun()
        except Exception as e:
            st.error(f"Ошибка поиска: {e}")

    # Если выбран chunk для редактирования — показываем форму редактирования ниже результатов
    edit_id = st.session_state.get("edit_chunk_id")
    if edit_id:
        st.markdown("---")
        st.subheader(f"Редактирование chunk #{edit_id}")
        render_edit_chunk(edit_id)


def render_edit_chunk(chunk_id: int):
    """
    Рендерит форму редактирования chunk.
    Используется как на отдельной странице, так и под результатами поиска.
    Поддерживает чанки с изображениями (metadata.images): они отображаются и сохраняются при сохранении.
    """
    try:
        chunk = kb_get_chunk(chunk_id)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            st.error(
                f"**Chunk с ID {chunk_id} не найден (404).**\n\n"
                "Возможные причины: запись удалена; ID введён вручную и не совпадает с базой; "
                "используется другой сервер/БД.\n\n"
                "**Что сделать:** откройте «Обзор и поиск», введите в поиск запрос (например `*` или тег `operator_block`), "
                "нажмите «Искать». В результатах нажмите «Открыть для редактирования #ID» у нужной записи — тогда подставляется актуальный ID из текущей БД."
            )
        else:
            st.error(f"Не удалось загрузить chunk {chunk_id}: {e}")
        return
    except Exception as e:
        st.error(f"Не удалось загрузить chunk {chunk_id}: {e}")
        return

    st.write(f"**ID chunk:** {chunk['id']}")

    metadata: Dict[str, Any] = chunk.get("metadata") or {}
    sk_img = f"edit_images_{chunk_id}"
    sk_doc = f"edit_documents_{chunk_id}"
    if sk_img not in st.session_state:
        raw = metadata.get("images") or []
        st.session_state[sk_img] = [
            dict(x) if isinstance(x, dict) else {"url": x, "description": "", "alt": ""}
            for x in raw
        ]
    if sk_doc not in st.session_state:
        raw = metadata.get("documents") or []
        st.session_state[sk_doc] = [
            dict(x) if isinstance(x, dict) else {"url": x, "title": "Документ", "description": ""}
            for x in raw
        ]
    images_list = st.session_state[sk_img]
    documents_list = st.session_state[sk_doc]

    st.markdown("**Медиа (картинки и документы)** — попадают в ответ агента при релевантном запросе.")
    for i, img in enumerate(images_list):
        if isinstance(img, str):
            img = {"url": img, "alt": "", "description": ""}
        url = img.get("url") or ""
        alt = img.get("alt") or ""
        desc = img.get("description") or ""
        with st.expander(f"Фото {i + 1}: {(url[:60] + '…') if len(url) > 60 else url or '—'}"):
            if url:
                try:
                    st.image(url, caption=alt or None, use_container_width=True)
                except Exception:
                    st.code(url, language=None)
            st.caption(f"Alt: {alt or '—'} | Описание: {desc or '—'}")
            if st.button("Удалить изображение", key=f"delimg_{chunk_id}_{i}"):
                st.session_state[sk_img] = [x for j, x in enumerate(images_list) if j != i]
                st.rerun()
    with st.expander("➕ Добавить изображение (URL)"):
        new_img_url = st.text_input("URL изображения", placeholder="https://...", key=f"newimg_url_{chunk_id}")
        new_img_desc = st.text_input("Подпись (описание)", key=f"newimg_desc_{chunk_id}")
        if st.button("Добавить", key=f"addimg_{chunk_id}") and (new_img_url or "").strip():
            st.session_state[sk_img] = images_list + [{"url": new_img_url.strip(), "description": new_img_desc.strip(), "alt": new_img_desc.strip()[:200]}]
            st.rerun()

    for i, doc in enumerate(documents_list):
        if isinstance(doc, str):
            doc = {"url": doc, "title": "Документ", "description": ""}
        url = doc.get("url") or ""
        title = doc.get("title") or "Документ"
        with st.expander(f"Документ {i + 1}: {title}"):
            st.caption(url[:80] + ("…" if len(url) > 80 else ""))
            if st.button("Удалить документ", key=f"deldoc_{chunk_id}_{i}"):
                st.session_state[sk_doc] = [x for j, x in enumerate(documents_list) if j != i]
                st.rerun()
    with st.expander("➕ Добавить документ (URL)"):
        new_doc_url = st.text_input("URL документа", placeholder="https://...", key=f"newdoc_url_{chunk_id}")
        new_doc_title = st.text_input("Название (для отображения)", value="Документ", key=f"newdoc_title_{chunk_id}")
        if st.button("Добавить документ", key=f"adddoc_{chunk_id}") and (new_doc_url or "").strip():
            st.session_state[sk_doc] = documents_list + [{"url": new_doc_url.strip(), "title": (new_doc_title or "Документ").strip(), "description": ""}]
            st.rerun()

    content = st.text_area("Контент", value=chunk["content"], height=250, key=f"content_{chunk_id}")

    col1, col2, col3 = st.columns(3)
    with col1:
        category = st.selectbox(
            "Категория",
            options=[
                "product_info",
                "sales_script",
                "objection_handling",
                "target_audience",
                "tone_of_voice",
                "contacts",
                "pricing",
                "location",
            ],
            index=0 if not metadata.get("category") else
            max(0, ["product_info", "sales_script", "objection_handling",
                    "target_audience", "tone_of_voice", "contacts", "pricing", "location"]
                .index(metadata.get("category"))),
            key=f"category_{chunk_id}",
        )
    with col2:
        target_audience = st.selectbox(
            "Целевая аудитория",
            options=["end_buyer", "realtor", "both"],
            index=2 if metadata.get("target_audience") is None else
            max(0, ["end_buyer", "realtor", "both"].index(metadata.get("target_audience"))),
            key=f"audience_{chunk_id}",
        )
    with col3:
        priority = st.selectbox(
            "Приоритет",
            options=["high", "medium", "low"],
            index=1 if metadata.get("priority") is None else
            max(0, ["high", "medium", "low"].index(metadata.get("priority"))),
            key=f"priority_{chunk_id}",
        )

    is_active = st.checkbox("Активен", value=chunk.get("is_active", True), key=f"is_active_{chunk_id}")

    tags_str = ", ".join(metadata.get("tags", [])) if metadata.get("tags") else ""
    tags_input = st.text_input("Теги (через запятую)", value=tags_str, key=f"tags_{chunk_id}")

    source = st.text_input("Источник (source)", value=metadata.get("source", ""), key=f"source_{chunk_id}")

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("Сохранить изменения", type="primary", key=f"save_{chunk_id}"):
            try:
                update_payload: Dict[str, Any] = {
                    "content": content,
                    "category": category,
                    "target_audience": target_audience,
                    "priority": priority,
                    "is_active": is_active,
                }
                if tags_input.strip():
                    update_payload["tags"] = [t.strip() for t in tags_input.split(",") if t.strip()]
                if source.strip():
                    update_payload["source"] = source.strip()
                # Сохраняем медиа (картинки и документы) для релевантного ответа агента
                update_payload["metadata"] = {
                    "images": st.session_state.get(sk_img, images_list),
                    "documents": st.session_state.get(sk_doc, documents_list),
                }

                resp = kb_update_chunk(chunk_id, update_payload)
                st.success(f"Chunk {chunk_id} обновлён: {resp.get('message')}")
            except Exception as e:
                st.error(f"Ошибка сохранения: {e}")
    with col_cancel:
        if st.button("Закрыть редактор", key=f"cancel_{chunk_id}"):
            # Сбрасываем выбор chunk для редактирования
            st.session_state["edit_chunk_id"] = None

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Деактивировать (soft delete)", key=f"soft_delete_{chunk_id}"):
            try:
                kb_delete_chunk(chunk_id, soft_delete=True)
                st.success(f"Chunk {chunk_id} деактивирован")
            except Exception as e:
                st.error(f"Ошибка деактивации: {e}")
    with col_b:
        if st.button("Удалить навсегда", key=f"hard_delete_{chunk_id}"):
            try:
                kb_delete_chunk(chunk_id, soft_delete=False)
                st.success(f"Chunk {chunk_id} удалён")
            except Exception as e:
                st.error(f"Ошибка удаления: {e}")


def page_edit_chunk():
    st.title("KB Admin — Редактирование chunk")

    chunk_id_from_state = st.session_state.get("edit_chunk_id")

    st.subheader("Выбор chunk для редактирования")
    st.caption("Доступны только chunk, существующие в базе (выбор из списка).")

    try:
        chunks = kb_list_chunks()
    except Exception as e:
        st.error(f"Не удалось загрузить список записей: {e}")
        return

    if not chunks:
        st.info("В базе нет активных записей для редактирования. Добавьте блоки на странице «Блоки оператора» или импортируйте документ.")
        return

    # Варианты: "42 — Заголовок или начало текста"
    options = [f"{c['id']} — {(c['title'] or '')[:70]}{'…' if len(c.get('title') or '') > 70 else ''}" for c in chunks]
    id_to_index = {c["id"]: i for i, c in enumerate(chunks)}
    default_index = id_to_index.get(chunk_id_from_state, 0)

    selected = st.selectbox(
        "Chunk для редактирования",
        options=options,
        index=default_index,
        key="edit_chunk_select",
    )
    if not selected:
        return
    chunk_id = int(selected.split(" — ", 1)[0].strip())
    st.session_state["edit_chunk_id"] = chunk_id

    st.markdown("---")
    st.subheader(f"Редактирование chunk #{chunk_id}")
    render_edit_chunk(chunk_id)


def page_stats():
    st.title("KB Admin — Статистика")

    try:
        stats = kb_stats()
    except Exception as e:
        st.error(f"Ошибка получения статистики: {e}")
        return

    st.write("**Общая статистика:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Всего chunks", stats.get("total_chunks", 0))
    with col2:
        st.metric("Активных chunks", stats.get("active_chunks", 0))
    with col3:
        st.metric("Категорий", len(stats.get("chunks_by_category", {})))

    st.markdown("---")
    st.write("**По категориям:**")
    st.json(stats.get("chunks_by_category", {}))

    st.markdown("---")
    st.write("**По целевой аудитории:**")
    st.json(stats.get("chunks_by_target_audience", {}))

    st.markdown("---")
    st.write("**По приоритету:**")
    st.json(stats.get("chunks_by_priority", {}))


def page_operator_blocks():
    """
    Ручное добавление смысловых блоков оператором: описание (текст), картинка (загрузка файла)
    или ссылка на картинку (URL + описание). По формату — как блоки при автоматическом парсинге по URL.
    """
    st.title("Блоки оператора")
    st.caption(
        "Добавление смысловых блоков вручную: текст, одна картинка (загрузить файл) или ссылка на картинку (URL). "
        "Сохранённые блоки попадают в KB в том же виде, что и при импорте по URL."
    )

    block_type = st.radio(
        "Тип блока",
        options=["Описание (текст)", "Картинка (загрузить файл)", "Ссылка на картинку (URL)"],
        key="op_block_type",
    )

    title = st.text_input("Заголовок блока", placeholder="Например: Контакты, STANDARD (стандартный ремонт)", key="op_title")
    section = st.selectbox(
        "Раздел",
        options=["", "settlement_info", "product_info", "pricing_offers", "faq", "objections", "legal_finance"],
        key="op_section",
    )
    tags_str = st.text_input("Теги (через запятую)", placeholder="contacts, standard", key="op_tags")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    tags.append("operator_block")

    content = ""
    images_payload: List[Dict[str, Any]] = []

    if block_type == "Описание (текст)":
        content = st.text_area("Текст блока", height=200, placeholder="Полное описание для KB", key="op_content_text")
    elif block_type == "Картинка (загрузить файл)":
        uploaded = st.file_uploader("Изображение", type=["jpg", "jpeg", "png", "gif", "webp"], key="op_file")
        desc_img = st.text_area("Описание картинки", height=100, placeholder="Что на фото (для поиска и отображения)", key="op_desc_img")
        if uploaded and desc_img.strip():
            content = desc_img.strip()
            # Загрузим при нажатии «Добавить»
        elif uploaded:
            st.info("Заполните описание картинки.")
    else:
        # Ссылка на картинку
        img_url = st.text_input("URL изображения", placeholder="https://...", key="op_img_url")
        desc_link = st.text_area("Описание картинки", height=100, placeholder="Что на фото", key="op_desc_link")
        if img_url.strip() and desc_link.strip():
            content = desc_link.strip()
            images_payload = [{"url": img_url.strip(), "description": desc_link.strip(), "alt": desc_link.strip()[:200]}]
        elif img_url.strip():
            st.info("Заполните описание картинки.")

    if st.button("Добавить блок в KB", type="primary", key="op_save_btn"):
        save_content = content
        save_images = list(images_payload)
        if not title.strip():
            st.warning("Укажите заголовок блока.")
        elif block_type == "Описание (текст)":
            if not save_content.strip():
                st.warning("Введите текст блока.")
        elif block_type == "Картинка (загрузить файл)":
            uploaded = st.session_state.get("op_file")
            desc_img = (st.session_state.get("op_desc_img") or "").strip()
            if not uploaded:
                st.warning("Загрузите изображение.")
            elif not desc_img:
                st.warning("Заполните описание картинки.")
            else:
                try:
                    data = mmkb_upload_image(uploaded.getvalue(), uploaded.name)
                    img_url = data.get("url", "")
                    if img_url:
                        save_images = [{"url": img_url, "description": desc_img, "alt": desc_img[:200]}]
                        save_content = desc_img
                except Exception as e:
                    st.error(f"Ошибка загрузки изображения: {e}")
        elif block_type == "Ссылка на картинку (URL)":
            if not save_content.strip() or not save_images:
                st.warning("Укажите URL изображения и описание.")

        if title.strip() and save_content.strip():
            try:
                op_source = "operator_block"
                if block_type == "Картинка (загрузить файл)":
                    op_file = st.session_state.get("op_file")
                    if op_file and getattr(op_file, "name", None):
                        op_source = op_file.name
                elif block_type == "Ссылка на картинку (URL)" and save_images:
                    url = save_images[0].get("url", "")
                    if url:
                        op_source = url
                payload: Dict[str, Any] = {
                    "title": title.strip(),
                    "content": save_content[:15000],
                    "section": section or None,
                    "tags": tags,
                    "images": save_images,
                    "metadata": {
                        "operator_block": True,
                        "block_type": block_type,
                        "source": op_source,
                    },
                    "category": "product_info",
                    "target_audience": "both",
                    "priority": "medium",
                }
                resp = mmkb_save(payload)
                st.success(f"Блок добавлен в KB (chunk_id={resp.get('chunk_id')}). {resp.get('message', '')}")
            except Exception as e:
                st.error(f"Ошибка сохранения в KB: {e}")

    st.markdown("---")
    st.caption("После добавления можно найти блок в «Обзор и поиск» по заголовку или тегу operator_block.")

    # Импорт документа (Word, PDF, PPTX, TXT) в KB
    st.markdown("### Импорт документа в KB (Word, PDF, PowerPoint, TXT)")
    doc_file = st.file_uploader(
        "Документ для импорта",
        type=["txt", "pdf", "docx", "pptx"],
        key="op_doc_upload",
    )
    if doc_file:
        col_cat, col_aud, col_src = st.columns(3)
        with col_cat:
            doc_category = st.selectbox(
                "Категория",
                options=["product_info", "sales_script", "objection_handling", "target_audience", "tone_of_voice", "contacts", "pricing", "location"],
                index=0,
                key="op_doc_category",
            )
        with col_aud:
            doc_audience = st.selectbox(
                "Целевая аудитория",
                options=["end_buyer", "realtor", "both"],
                index=2,
                key="op_doc_audience",
            )
        with col_src:
            doc_source = st.text_input(
                "Источник (source)",
                value=doc_file.name,
                key="op_doc_source",
                help="По умолчанию — имя файла (для поиска по источнику). Можно заменить на URL или свой текст.",
            )
        doc_chunk_size = st.number_input("Размер chunk", min_value=500, max_value=10000, value=3000, step=100, key="op_doc_chunk_size")
        doc_chunk_overlap = st.number_input("Перекрытие chunks", min_value=0, max_value=1000, value=300, step=50, key="op_doc_chunk_overlap")
        if st.button("📄 Импортировать документ в KB", type="primary", key="op_doc_import_btn"):
            try:
                result = kb_import_document(
                    file_bytes=doc_file.getvalue(),
                    filename=doc_file.name,
                    category=doc_category,
                    target_audience=doc_audience,
                    source=doc_source,
                    chunk_size=doc_chunk_size,
                    chunk_overlap=doc_chunk_overlap,
                )
                st.success(
                    f"Импорт завершён: добавлено {result.get('chunks_added', 0)} chunks, "
                    f"ошибок {result.get('chunks_failed', 0)}"
                )
            except Exception as e:
                st.error(f"Ошибка импорта документа: {e}")

    st.markdown("---")
    # Быстрый импорт по URL (черновик) — тот же раздел, где оператор формирует KB
    st.markdown("### Быстрый импорт по URL (черновик)")
    if "mmkb_import_result" not in st.session_state:
        st.session_state["mmkb_import_result"] = None

    col_url, col_url_meta = st.columns([2, 1])
    with col_url:
        import_url = st.text_input(
            "URL страницы сайта заказчика",
            placeholder="https://example.com/page",
            key="mmkb_import_url",
        )
    with col_url_meta:
        import_section = st.selectbox(
            "Раздел для URL‑импорта (опционально)",
            options=[
                "",
                "settlement_info",
                "product_info",
                "pricing_offers",
                "faq",
                "objections",
                "legal_finance",
            ],
            key="mmkb_import_section",
        )
        import_tags_str = st.text_input(
            "Теги для URL‑импорта (через запятую)",
            placeholder="url, автопарсинг",
            key="mmkb_import_tags",
        )

    col_imp1, col_imp2 = st.columns([1, 1])
    with col_imp1:
        if st.button("🤖 Импортировать по URL через библиотекаря", key="mmkb_import_run"):
            if not import_url.strip():
                st.warning("Укажите URL для импорта.")
            else:
                try:
                    import_tags = [
                        t.strip() for t in import_tags_str.split(",") if t.strip()
                    ] if import_tags_str else []
                    payload = {
                        "url": import_url.strip(),
                        "section": import_section or None,
                        "tags": import_tags,
                        "analyze_images": True,
                        "llm_timeout": 300,
                    }
                    with st.spinner("⏳ Импорт и анализ URL... Это может занять несколько минут (особенно при анализе изображений)"):
                        resp = mmkb_import_from_url(payload, timeout=600)
                        st.session_state["mmkb_import_result"] = resp
                    st.success("✅ URL обработан, черновой документ и решение библиотекаря получены.")
                except requests.exceptions.Timeout:
                    st.error("⏱️ Таймаут при импорте URL. Страница слишком большая или анализ изображений занял слишком много времени. Попробуйте позже или уменьшите количество изображений на странице.")
                except Exception as e:
                    st.error(f"❌ Ошибка импорта по URL: {e}")

    with col_imp2:
        if st.session_state.get("mmkb_import_result"):
            st.caption("Результат последнего импорта. Для свежих данных нажмите «Импортировать» ещё раз (страница запрашивается без кэша).")
        if st.button("Сбросить результат импорта", key="mmkb_import_reset"):
            st.session_state["mmkb_import_result"] = None
            try:
                import streamlit as st_mod
                if hasattr(st_mod, "rerun"):
                    st_mod.rerun()
                else:
                    st.experimental_rerun()
            except Exception:
                pass

    import_result = st.session_state.get("mmkb_import_result")
    if import_result:
        st.markdown("---")
        st.markdown("#### Результат импорта и решение библиотекаря")

        st.subheader("Черновой документ")
        draft = import_result.get("draft_document", {})
        st.write(f"**Title:** {draft.get('title')}")
        st.text_area(
            "Извлечённый текст (сырой HTML→текст)",
            value=draft.get("content", ""),
            height=160,
        )

        lr2 = import_result.get("librarian_result") or {}
        decision2 = lr2.get("decision", "needs_review")
        if decision2 == "approve":
            st.success(f"Решение: **{decision2}** — материал можно добавлять в KB")
        elif decision2 == "reject":
            st.error(f"Решение: **{decision2}** — материал не рекомендован к добавлению")
        else:
            st.warning(f"Решение: **{decision2}** — требуется ручная проверка")

        semantic_blocks = lr2.get("semantic_blocks") or {}
        blocks = list(semantic_blocks.get("blocks") or [])
        abstract_text = (lr2.get("abstract") or "").strip()
        filtered_text = (lr2.get("filtered_content") or "").strip()
        if abstract_text:
            blocks.append({
                "type": "OTHER",
                "title": "Краткое изложение (Abstract)",
                "description": abstract_text,
                "price": "",
                "gallery": [],
                "_virtual": "abstract",
            })
        if filtered_text:
            blocks.append({
                "type": "OTHER",
                "title": "Фильтрованный текст (для KB)",
                "description": filtered_text,
                "price": "",
                "gallery": [],
                "_virtual": "filtered",
            })
        if blocks:
            st.subheader("Смысловые блоки (по одному блоку в KB)")
            for i, block in enumerate(blocks):
                block_type = block.get("type") or "OTHER"
                default_title = block.get("title", "")
                default_desc = block.get("description") or block.get("raw_text") or ""
                default_price = block.get("price", "")
                key_suffix = block.get("_virtual") if block.get("_virtual") else i

                with st.expander(f"[{i}] {block_type} — {default_title}"):
                    edt_title = st.text_input(
                        "Заголовок блока",
                        value=default_title,
                        key=f"sb_title_{key_suffix}",
                    )
                    edt_body = st.text_area(
                        "Текст блока (для клиента)",
                        value=default_desc,
                        height=180,
                        key=f"sb_body_{key_suffix}",
                    )
                    edt_price = st.text_input(
                        "Цена/условия (опционально)",
                        value=default_price,
                        key=f"sb_price_{key_suffix}",
                    )

                    gallery_items = block.get("gallery") or []
                    block_images_payload = []
                    if gallery_items:
                        st.markdown("**Изображения блока**")
                        for j, g in enumerate(gallery_items):
                            if isinstance(g, str):
                                g = {"url": g, "image_url": g, "description": "", "alt": ""}
                            img_url = g.get("image_url") or g.get("url")
                            img_desc = g.get("description") or ""
                            img_alt = g.get("alt") or ""
                            if not img_url or not img_desc.strip():
                                continue
                            col_g1, col_g2 = st.columns([2, 3])
                            with col_g1:
                                img_bytes = _fetch_image_bytes(img_url)
                                if img_bytes:
                                    st.image(img_bytes, caption=img_desc[:80] + ("…" if len(img_desc) > 80 else ""))
                                else:
                                    st.image(img_url, caption=img_desc[:80])
                                st.caption(f"[{img_url[:60]}…]" if len(img_url) > 60 else img_url)
                            with col_g2:
                                st.write(f"ALT: {img_alt}")
                                st.write(f"Описание: {img_desc}")
                            block_images_payload.append({
                                "url": img_url,
                                "alt": img_alt,
                                "description": img_desc,
                                "annotations": {"block_index": i, "gallery_index": j, "block_type": block_type},
                            })

                    if st.button("➕ Добавить этот блок в KB", key=f"sb_save_{key_suffix}"):
                        if not edt_body.strip():
                            st.warning("Текст блока пустой — сначала заполните описание.")
                        else:
                            try:
                                block_content = edt_body.strip()
                                if edt_price.strip():
                                    block_content += f"\n\nЦена / условия: {edt_price.strip()}"

                                base_section = draft.get("section") or (import_section or None)
                                if block_type == "CONTACTS":
                                    inferred_section = base_section or "settlement_info"
                                elif block_type in ("BLACK_BOX", "WHITE_BOX", "STANDARD", "DESIGN", "ADVANTAGES", "LAYOUTS"):
                                    inferred_section = base_section or "product_info"
                                else:
                                    inferred_section = base_section

                                base_tags = draft.get("tags") or []
                                extra_tags = []
                                if block_type:
                                    extra_tags.append(f"block_type:{str(block_type).lower()}")
                                block_tab = block.get("tab") or semantic_blocks.get("tab")
                                if block_tab:
                                    extra_tags.append(f"tab:{str(block_tab)}")
                                source_url = draft.get("source_url", import_result.get("url"))
                                if source_url:
                                    extra_tags.append("source:url_import")

                                dedup_tags: List[str] = []
                                for t in base_tags + extra_tags:
                                    if t and t not in dedup_tags:
                                        dedup_tags.append(t)

                                source_url = draft.get("source_url", import_result.get("url"))
                                save_payload_block: Dict[str, Any] = {
                                    "title": edt_title or default_title or draft.get("title") or import_result.get("url"),
                                    "content": block_content,
                                    "section": inferred_section,
                                    "tags": dedup_tags,
                                    "images": block_images_payload,
                                    "metadata": {
                                        "source": source_url or "url_import",
                                        "source_url": source_url,
                                        "raw_html_length": draft.get("raw_html_length"),
                                        "semantic_block": block,
                                        "semantic_block_index": i,
                                        "semantic_block_type": block_type,
                                    },
                                    "librarian_result": lr2,
                                }
                                resp_block = mmkb_save(save_payload_block)
                                st.success(
                                    f"Блок сохранён в KB (chunk_id={resp_block.get('chunk_id')}). "
                                    f"Сообщение: {resp_block.get('message', '')}"
                                )
                            except Exception as e:
                                st.error(f"Ошибка сохранения блока в KB: {e}")

        images_from_draft = draft.get("images") or []
        img_ann2 = lr2.get("image_annotations") or []
        gallery_images_payload: List[Dict[str, Any]] = []
        st.subheader("Изображения, найденные на странице (отфильтрованные)")
        if not images_from_draft:
            st.info("Изображений не извлечено. Проверьте, что URL открывается и на странице есть картинки в секции выбранной вкладки.")
        else:
            for idx, img in enumerate(images_from_draft):
                url = img.get("url") or ""
                url_lower = url.lower()
                if "/resize/" in url_lower and re.search(r"/\d+x", url_lower):
                    continue
                if any(x in url_lower for x in ("icons8", "strelka", "strela", "for_site.png")):
                    continue

                matching_ann = next((a for a in img_ann2 if a.get("index") == idx), None)
                alt = (matching_ann.get("alt") if matching_ann else None) or img.get("alt", "")
                desc = (matching_ann.get("description") if matching_ann else None) or img.get("description", "")

                gallery_images_payload.append({
                    "url": url,
                    "alt": alt or "",
                    "description": desc or "",
                    "annotations": dict(matching_ann) if matching_ann else {"index": idx},
                })

                col_img, col_meta = st.columns([2, 3])
                with col_img:
                    if url:
                        img_bytes = _fetch_image_bytes(url)
                        if img_bytes:
                            st.image(img_bytes, caption=f"#{idx}" + (f" — {desc[:50]}…" if desc else ""))
                        else:
                            st.image(url, caption=f"#{idx}")
                        st.caption(f"[Открыть в новой вкладке]({url})")
                with col_meta:
                    st.write("**URL:**")
                    st.code(url, language=None)
                    st.write("**ALT:** " + (alt or "—"))
                    st.write("**Описание:** " + (desc or "—"))
                    if matching_ann:
                        st.caption("Аннотация vision")
                        st.json(matching_ann)

            if gallery_images_payload:
                st.markdown("**Добавить эту галерею в KB** (все изображения выше с описаниями — одной записью):")
                if st.button("➕ Добавить галерею в KB", key="mmkb_add_gallery_btn"):
                    try:
                        gallery_content = "Галерея изображений с описаниями.\n\n" + "\n\n".join(
                            f"#{i+1}: {p.get('description') or p.get('url') or ''}" for i, p in enumerate(gallery_images_payload)
                        )
                        gallery_source_url = draft.get("source_url", import_result.get("url"))
                        save_gallery_payload: Dict[str, Any] = {
                            "title": f"Галерея: {draft.get('title') or import_result.get('url') or 'Импорт по URL'}",
                            "content": gallery_content[:15000],
                            "section": draft.get("section") or import_section or "product_info",
                            "tags": ["gallery", "source:url_import"],
                            "images": gallery_images_payload,
                            "metadata": {
                                "source": gallery_source_url or "url_import",
                                "source_url": gallery_source_url,
                                "gallery_from_import": True,
                            },
                            "category": "product_info",
                            "target_audience": "both",
                            "priority": "medium",
                        }
                        resp_g = mmkb_save(save_gallery_payload)
                        st.success(f"Галерея добавлена в KB (chunk_id={resp_g.get('chunk_id')}). {resp_g.get('message', '')}")
                    except Exception as e:
                        st.error(f"Ошибка сохранения галереи в KB: {e}")

        st.subheader("Проверка дубликатов")
        dup2 = lr2.get("duplicate_check", {})
        if dup2:
            st.json(dup2)
        else:
            st.write("Информация о дубликатах отсутствует.")

        st.markdown("---")
        with st.expander("Опционально: сохранить весь URL одной записью в KB", expanded=False):
            st.caption(
                "Нужно только если хотите одну запись со всей страницей (фильтрованный текст + все картинки). "
                "Обычно удобнее добавлять по смыслу: смысловые блоки выше и галерею — по кнопкам «Добавить этот блок в KB» и «Добавить галерею в KB»."
            )
            col_cat2, col_aud2, col_prio2 = st.columns(3)
            with col_cat2:
                kb_category2 = st.selectbox(
                    "KB category",
                    options=[
                        "product_info",
                        "sales_script",
                        "objection_handling",
                        "target_audience",
                        "tone_of_voice",
                        "contacts",
                        "pricing",
                        "location",
                    ],
                    index=0,
                    key="mmkb_import_kb_category",
                )
            with col_aud2:
                kb_audience2 = st.selectbox(
                    "Целевая аудитория",
                    options=["end_buyer", "realtor", "both"],
                    index=2,
                    key="mmkb_import_kb_audience",
                )
            with col_prio2:
                kb_priority2 = st.selectbox(
                    "Приоритет",
                    options=["high", "medium", "low"],
                    index=1,
                    key="mmkb_import_kb_priority",
                )

            if st.button("💾 Сохранить весь URL одной записью в KB", type="primary", key="mmkb_import_save"):
                try:
                    kb_content = lr2.get("filtered_content") or draft.get("content", "")
                    images_payload2 = []
                    for idx, img in enumerate(images_from_draft):
                        base_img = {
                            "url": img.get("url"),
                            "alt": img.get("alt", ""),
                            "description": img.get("description", ""),
                            "annotations": img.get("annotations") or {"index": idx},
                        }
                        matching = next((a for a in img_ann2 if a.get("index") == idx), None)
                        if matching:
                            ann = dict(base_img["annotations"])
                            ann.update(matching)
                            base_img["annotations"] = ann
                            if matching.get("alt"):
                                base_img["alt"] = matching.get("alt", "")
                            if matching.get("description"):
                                base_img["description"] = matching.get("description", "")
                        images_payload2.append(base_img)

                    full_url_source = draft.get("source_url", import_result.get("url"))
                    save_payload2: Dict[str, Any] = {
                        "title": draft.get("title") or import_result.get("url"),
                        "content": kb_content,
                        "section": draft.get("section") or (import_section or None),
                        "tags": [],
                        "images": images_payload2,
                        "metadata": {
                            "source": full_url_source or "url_import",
                            "source_url": full_url_source,
                            "raw_html_length": draft.get("raw_html_length"),
                            "semantic_blocks": semantic_blocks,
                        },
                        "category": kb_category2,
                        "target_audience": kb_audience2,
                        "priority": kb_priority2,
                        "librarian_result": lr2,
                    }
                    resp2 = mmkb_save(save_payload2)
                    st.success(
                        f"Материал из URL сохранён в KB (chunk_id={resp2.get('chunk_id')}). "
                        f"Сообщение: {resp2.get('message', '')}"
                    )
                except Exception as e:
                    st.error(f"Ошибка сохранения в KB: {e}")



def main():
    st.set_page_config(
        page_title="KB Admin",
        page_icon="📚",
        layout="wide",
    )

    sidebar_health()

    pages = {
        "Обзор и поиск": page_overview,
        "Редактирование chunk": page_edit_chunk,
        "Статистика": page_stats,
        "Блоки оператора": page_operator_blocks,
    }

    # Инициализируем состояние для выбранной страницы и редактирования
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Обзор и поиск"
    if "edit_chunk_id" not in st.session_state:
        st.session_state["edit_chunk_id"] = None

    page_names = list(pages.keys())
    
    # Важно: используем значение из session_state как источник истины
    current_page_value = st.session_state["current_page"]
    if current_page_value not in page_names:
        current_page_value = "Обзор и поиск"
        st.session_state["current_page"] = current_page_value
    
    # Используем radio для навигации - он лучше синхронизируется с session_state
    st.sidebar.markdown("### Навигация")
    # Используем radio с key, который синхронизируется с session_state
    # При программном изменении current_page radio автоматически обновится
    selected_page = st.sidebar.radio(
        "Раздел",
        page_names,
        index=page_names.index(st.session_state["current_page"]),
        key="page_nav_radio",
        label_visibility="collapsed"
    )
    
    # Если пользователь изменил выбор через radio, обновляем session_state
    if selected_page != st.session_state["current_page"]:
        st.session_state["current_page"] = selected_page
        # Если переключились на другую страницу, сбрасываем edit_chunk_id
        if selected_page != "Редактирование chunk":
            st.session_state["edit_chunk_id"] = None
    
    # Всегда используем current_page из session_state для отображения страницы
    # Это гарантирует, что программное изменение current_page будет работать
    pages[st.session_state["current_page"]]()


if __name__ == "__main__":
    main()



