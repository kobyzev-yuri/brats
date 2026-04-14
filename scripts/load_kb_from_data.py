#!/usr/bin/env python3
"""
Автоматическая загрузка базы знаний из папки data в KB через API.

Структура data (ожидаемая):
  data/
  data/БЗ/                    — основная папка с материалами для БЗ
    *.txt, *.docx, *.pdf, *.pptx — текстовые файлы и документы (в т.ч. презентации)
    photo_descriptions/       — описания по типам отделки (docx)
    Сторисы/                  — сторисы (если есть txt/docx)
  data/БЗ/вопросы_neurocrm.txt — тестовые вопросы для проверки релевантности БЗ
    (по умолчанию не загружаются в KB; используются скриптом check_kb_relevance.py)

API KB (kb-service на порту 8001):
  POST /api/kb/import         — текст в body (content, category, source, metadata с images/documents)
  POST /api/kb/import_document — multipart: file; из текста извлекаются URL картинок и документов в metadata.

При загрузке из текста/файлов URL картинок (.jpg, .png, …) и документов (.pdf, .docx, …) попадают
в metadata.images и metadata.documents — тогда запросы по картинкам/ссылкам релевантно возвращают медиа в ответе агента.

Использование:
  cd /projects/brats
  source config.env  # или export KB_API_URL=http://localhost:8001
  python scripts/load_kb_from_data.py [--data-dir data] [--dry-run] [--chunk-size 3000] [--overlap 300]
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Корень проекта: на уровень выше scripts/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Загрузка config.env из корня проекта
CONFIG_ENV = PROJECT_ROOT / "config.env"
if CONFIG_ENV.exists():
    with open(CONFIG_ENV) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and value and not os.environ.get(key):
                    os.environ[key] = value

KB_API_URL = os.environ.get("KB_API_URL", "http://localhost:8001")
CHUNK_SIZE_DEFAULT = 3000
CHUNK_OVERLAP_DEFAULT = 300

# Маппинг: подстрока в имени файла или путь -> (category, target_audience)
# category: product_info, sales_script, objection_handling, target_audience, contacts, pricing, location, tone_of_voice
# target_audience: end_buyer, realtor, both
# Порядок важен: более специфичные правила первыми (photo_descriptions до interest_script, иначе "script" совпадёт с "de*script*ions")
FILE_MAPPING = [
    (["price", "прайс", "pricing"], "pricing", "both"),
    (["adress", "address", "адрес", "location"], "location", "both"),
    (["social_net", "contacts", "контакт", "clients"], "contacts", "both"),
    (["photo_descriptions", "Детально_"], "product_info", "both"),
    (["interest_script", "скрипт"], "sales_script", "both"),
    (["presentation_realtor", "realtor", "риелтор"], "product_info", "realtor"),
    (["presentation_final_client", "client", "клиент"], "product_info", "end_buyer"),
    (["вопросы_neurocrm", "objection", "возражен"], "objection_handling", "both"),
    (["СИНТЕТИЧЕСКАЯ", "база-знаний"], "product_info", "both"),
    (["Презентация_КП", "КП", "инноватор"], "product_info", "both"),
    (["Сторисы", "сторисы"], "product_info", "both"),
]


def _category_for_path(file_path: Path, rel_path: str) -> Tuple[str, str]:
    """Определяет category и target_audience по пути/имени файла."""
    name_lower = (rel_path + " " + file_path.name).lower()
    for keys, cat, aud in FILE_MAPPING:
        if any(k.lower() in name_lower or k in rel_path or k in file_path.name for k in keys):
            return cat, aud
    return "product_info", "both"


def _source_label(file_path: Path, data_dir: Path) -> str:
    """Короткий источник для метки в KB (относительный путь от data_dir)."""
    try:
        rel = file_path.resolve().relative_to(data_dir.resolve())
        return str(rel).replace("\\", "/")
    except ValueError:
        return file_path.name


def extract_media_urls_from_text(text: str) -> Dict[str, Any]:
    """Извлекает из текста URL картинок и документов для metadata (релевантный ответ агента с медиа)."""
    url_pattern = re.compile(r"https?://[^\s\)\]\"\'\>]+", re.IGNORECASE)
    seen: set = set()
    images: List[Dict[str, Any]] = []
    documents: List[Dict[str, Any]] = []
    image_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")
    doc_ext = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".pptx")
    for m in url_pattern.finditer(text):
        raw = m.group(0).rstrip(".,;:)")
        if raw in seen:
            continue
        seen.add(raw)
        lower = raw.lower()
        if any(lower.endswith(ext) or ext + "?" in lower or ext + "&" in lower for ext in image_ext):
            images.append({"url": raw, "description": "", "alt": ""})
        elif any(lower.endswith(ext) or ext + "?" in lower or ext + "&" in lower for ext in doc_ext):
            documents.append({"url": raw, "title": "Документ", "description": ""})
    result: Dict[str, Any] = {}
    if images:
        result["images"] = images[:20]
    if documents:
        result["documents"] = documents[:10]
    return result


def load_config_env():
    """Подгрузить переменные из config.env в os.environ."""
    if CONFIG_ENV.exists():
        with open(CONFIG_ENV) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key:
                        os.environ[key] = value


# Имя файла с тестовыми вопросами: не загружаем в KB, используем для проверки релевантности
TEST_QUESTIONS_FILENAME = "вопросы_neurocrm.txt"


def collect_files(data_dir: Path, include_test_questions: bool = False) -> List[Tuple[Path, str, str, str]]:
    """Собирает список (путь, category, target_audience, source).
    По умолчанию исключает вопросы_neurocrm.txt (они нужны для проверки релевантности, см. check_kb_relevance.py).
    """
    data_dir = data_dir.resolve()
    if not data_dir.is_dir():
        return []
    out = []
    exts = {".txt", ".md", ".docx", ".pdf", ".pptx"}
    for f in data_dir.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        if not include_test_questions and f.name == TEST_QUESTIONS_FILENAME:
            continue
        try:
            rel = f.relative_to(data_dir)
            rel_str = str(rel).replace("\\", "/")
        except ValueError:
            rel_str = f.name
        cat, aud = _category_for_path(f, rel_str)
        source = _source_label(f, data_dir)
        out.append((f, cat, aud, source))
    return sorted(out, key=lambda x: str(x[0]))


def import_text(content: str, category: str, target_audience: str, source: str,
                chunk_size: int, chunk_overlap: int, base_url: str,
                metadata: Optional[Dict[str, Any]] = None) -> dict:
    """POST /api/kb/import. metadata.images / metadata.documents — для релевантного ответа агента с медиа."""
    import requests
    url = f"{base_url.rstrip('/')}/api/kb/import"
    payload = {
        "content": content,
        "category": category,
        "target_audience": target_audience,
        "source": source or "data",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    if metadata:
        payload["metadata"] = metadata
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def import_document(file_path: Path, category: str, target_audience: str, source: str,
                    chunk_size: int, chunk_overlap: int, base_url: str) -> dict:
    """POST /api/kb/import_document (multipart)."""
    import requests
    url = f"{base_url.rstrip('/')}/api/kb/import_document"
    with open(file_path, "rb") as f:
        data = f.read()
    name = file_path.name
    files = {"file": (name, data)}
    form = {
        "category": category,
        "target_audience": target_audience,
        "source": source or name,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    r = requests.post(url, files=files, data=form, timeout=120)
    if not r.ok:
        try:
            err = r.json()
            msg = err.get("detail", err)
        except Exception:
            msg = r.text or r.reason
        raise RuntimeError("API %s: %s" % (r.status_code, msg))
    return r.json()


def main():
    load_config_env()
    parser = argparse.ArgumentParser(description="Загрузка БЗ из data в KB через API")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data",
                        help="Корневая папка с данными (по умолчанию data)")
    parser.add_argument("--kb-url", default=os.environ.get("KB_API_URL", KB_API_URL),
                        help="URL KB API (или KB_API_URL из config.env)")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE_DEFAULT,
                        help="Размер chunk для разбиения")
    parser.add_argument("--overlap", type=int, default=CHUNK_OVERLAP_DEFAULT,
                        help="Перекрытие между chunks")
    parser.add_argument("--dry-run", action="store_true", help="Только список файлов, без отправки")
    parser.add_argument("--encoding", default="utf-8", help="Кодировка для .txt (fallback: cp1251)")
    parser.add_argument("--include-test-questions", action="store_true",
                        help="Включить в загрузку вопросы_neurocrm.txt (по умолчанию исключён — используется для проверки релевантности)")
    args = parser.parse_args()

    data_dir = args.data_dir if args.data_dir.is_absolute() else PROJECT_ROOT / args.data_dir
    base_url = args.kb_url.rstrip("/")

    files = collect_files(data_dir, include_test_questions=args.include_test_questions)
    if not files:
        print("Файлы для загрузки не найдены (ожидаются .txt, .md, .docx, .pdf, .pptx в %s)" % data_dir)
        return 2

    print("Найдено файлов: %d" % len(files))
    print("KB API: %s" % base_url)
    print("chunk_size=%s, chunk_overlap=%s" % (args.chunk_size, args.overlap))
    if args.dry_run:
        for path, cat, aud, src in files:
            print("  [%s|%s] %s -> source=%s" % (cat, aud, path, src))
        return 0

    try:
        import requests
    except ImportError:
        print("Установите requests: pip install requests")
        return 1

    total_added = 0
    total_failed = 0
    errors = []

    for path, category, target_audience, source in files:
        meta_note = ""
        try:
            suf = path.suffix.lower()
            if suf in (".txt", ".md"):
                with open(path, "r", encoding=args.encoding) as f:
                    content = f.read()
                metadata = extract_media_urls_from_text(content)
                try:
                    res = import_text(
                        content, category, target_audience, source,
                        args.chunk_size, args.overlap, base_url,
                        metadata=metadata if metadata else None,
                    )
                except Exception as e:
                    try:
                        with open(path, "r", encoding="cp1251") as f2:
                            content = f2.read()
                        metadata = extract_media_urls_from_text(content)
                        res = import_text(
                            content, category, target_audience, source,
                            args.chunk_size, args.overlap, base_url,
                            metadata=metadata if metadata else None,
                        )
                    except Exception as e2:
                        errors.append("%s: %s" % (path, e2))
                        total_failed += 1
                        continue
            else:
                res = import_document(
                    path, category, target_audience, source,
                    args.chunk_size, args.overlap, base_url
                )
            added = res.get("chunks_added", 0)
            failed = res.get("chunks_failed", 0)
            total_added += added
            total_failed += failed
            if suf in (".txt", ".md") and metadata:
                ni = len(metadata.get("images") or [])
                nd = len(metadata.get("documents") or [])
                if ni or nd:
                    meta_note = ", metadata: %d images, %d docs" % (ni, nd)
            elif suf not in (".txt", ".md"):
                meta_note = " (URLs из текста → metadata)"
            print("  OK %s: +%d chunks (category=%s, audience=%s%s)" % (path.name, added, category, target_audience, meta_note))
            if failed:
                errors.append("%s: %d failed" % (path, failed))
        except Exception as e:
            errors.append("%s: %s" % (path, e))
            total_failed += 1
            print("  FAIL %s: %s" % (path.name, e))

    print("")
    print("Итого: добавлено chunks %d, ошибок %d" % (total_added, total_failed))
    if errors:
        for err in errors:
            print("  ", err)
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
