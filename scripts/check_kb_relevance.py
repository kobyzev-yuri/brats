#!/usr/bin/env python3
"""
Проверка релевантности загрузки БЗ: прогон тестовых вопросов из вопросы_neurocrm.txt
через POST /api/kb/search и вывод топ-N результатов по каждому вопросу.

Использование:
  cd /projects/brats
  source config.env
  python scripts/check_kb_relevance.py [--questions data/БЗ/вопросы_neurocrm.txt] [--limit 3] [--top 5]
"""

import argparse
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ENV = PROJECT_ROOT / "config.env"
DEFAULT_QUESTIONS_FILE = PROJECT_ROOT / "data" / "БЗ" / "вопросы_neurocrm.txt"

if CONFIG_ENV.exists():
    with open(CONFIG_ENV) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and not os.environ.get(key):
                    os.environ[key] = value

KB_API_URL = os.environ.get("KB_API_URL", "http://localhost:8001")


def extract_questions(path: Path, encoding: str = "utf-8") -> list[str]:
    """Извлекает строки-вопросы из файла (строки с ?, не пустые, не только +N, не заголовки секций)."""
    questions = []
    try:
        text = path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1251")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Пропускаем метки сложности и номера
        if re.match(r"^\+?\d+$", line):
            continue
        # Пропускаем заголовки вида "1. Простые вопросы..."
        if re.match(r"^\d+\.\s+[А-Яа-яA-Za-z]", line) and "?" not in line:
            continue
        # Пропускаем поясняющие строки без вопроса
        if line.startswith("Эти вопросы") or line.startswith("Вопросы,"):
            continue
        # Берём строки с вопросительным знаком или длинные (считаем вопросом)
        if "?" in line or (len(line) > 25 and line[0].isupper()):
            questions.append(line)
    return questions


def search_kb(query: str, base_url: str, limit: int = 5, min_similarity: float = 0.0) -> dict:
    """POST /api/kb/search. min_similarity=0 — показывать все найденные chunks (для проверки релевантности)."""
    import requests
    url = f"{base_url.rstrip('/')}/api/kb/search"
    payload = {"query": query, "limit": limit, "min_similarity": min_similarity}
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Проверка релевантности KB по тестовым вопросам")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_FILE,
                        help="Файл с вопросами (по умолчанию data/БЗ/вопросы_neurocrm.txt)")
    parser.add_argument("--kb-url", default=KB_API_URL, help="URL KB API")
    parser.add_argument("--limit", type=int, default=3,
                        help="Сколько топ-результатов выводить по каждому вопросу")
    parser.add_argument("--top", type=int, default=5, help="Сколько результатов запрашивать у API (limit в search)")
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--max-questions", type=int, default=0,
                        help="Макс. число вопросов (0 = все)")
    parser.add_argument("--min-similarity", type=float, default=0.0,
                        help="Минимальная схожесть (0–1). По умолчанию 0 — вывести все найденные chunks для оценки релевантности; в проде обычно 0.5–0.6")
    args = parser.parse_args()

    path = args.questions if args.questions.is_absolute() else PROJECT_ROOT / args.questions
    if not path.exists():
        print("Файл не найден: %s" % path)
        return 2

    questions = extract_questions(path, args.encoding)
    if args.max_questions > 0:
        questions = questions[: args.max_questions]
    if not questions:
        print("Вопросы не найдены в файле.")
        return 1

    try:
        import requests
    except ImportError:
        print("Установите requests: pip install requests")
        return 1

    base_url = args.kb_url.rstrip("/")
    print("Проверка релевантности KB")
    print("  Файл вопросов: %s" % path)
    print("  Вопросов: %d" % len(questions))
    print("  KB API: %s" % base_url)
    print("  Топ результатов по запросу: %d" % args.limit)
    print("  min_similarity: %s" % args.min_similarity)
    print("")

    ok = 0
    fail = 0
    for i, q in enumerate(questions, 1):
        q_short = (q[:80] + "…") if len(q) > 80 else q
        print("--- [%d] %s" % (i, q_short))
        try:
            data = search_kb(q, base_url, limit=args.top, min_similarity=args.min_similarity)
            results = data.get("results") or []
            if not results:
                print("  (нет результатов)")
                if args.min_similarity > 0:
                    print("  Подсказка: попробуйте --min-similarity 0, чтобы увидеть все найденные chunks.")
                fail += 1
            else:
                for j, r in enumerate(results[: args.limit], 1):
                    sim = r.get("similarity", 0)
                    content = (r.get("content") or "")[:200].replace("\n", " ")
                    if len((r.get("content") or "")) > 200:
                        content += "…"
                    print("  %d. similarity=%.3f | %s" % (j, sim, content))
                ok += 1
        except Exception as e:
            print("  Ошибка: %s" % e)
            fail += 1
        print("")

    print("Итого: обработано %d, с результатами %d, без результатов/ошибок %d" % (len(questions), ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
