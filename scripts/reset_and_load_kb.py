#!/usr/bin/env python3
"""
Очистка таблицы knowledge_base и повторная загрузка БЗ из папки data (вместо первой попытки).

Шаги:
  1. Загружает config.env из корня проекта, подключается к БД по DATABASE_URL.
  2. Выполняет TRUNCATE knowledge_base RESTART IDENTITY; (полная очистка).
  3. Запускает scripts/load_kb_from_data.py с теми же параметрами (--data-dir, --chunk-size, --overlap и т.д.).

Требования:
  - В config.env задан DATABASE_URL (та же БД, что использует kb-service).
  - kb-service запущен на KB_API_URL (по умолчанию http://localhost:8001).

Использование:
  cd /projects/brats
  python scripts/reset_and_load_kb.py [--data-dir data] [--dry-run] [--chunk-size 3000] [--overlap 300]
  Флаги передаются в load_kb_from_data.py; --dry-run только выводит список файлов, не очищает и не загружает.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ENV = PROJECT_ROOT / "config.env"


def load_config_env():
    if not CONFIG_ENV.exists():
        return
    with open(CONFIG_ENV) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key:
                    os.environ[key] = value


def truncate_knowledge_base():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Ошибка: DATABASE_URL не задан. Укажите в config.env в корне проекта.")
        sys.exit(1)
    print("Очистка таблицы knowledge_base...")
    # Пробуем psycopg, иначе — psql
    try:
        import psycopg
        with psycopg.connect(url) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE knowledge_base RESTART IDENTITY;")
            conn.commit()
    except ImportError:
        import subprocess
        # psql принимает URI: psql "postgresql://..."
        rc = subprocess.run(
            ["psql", url, "-c", "TRUNCATE TABLE knowledge_base RESTART IDENTITY;"],
            capture_output=True,
            text=True,
        )
        if rc.returncode != 0:
            print("Ошибка psql:", rc.stderr or rc.stdout)
            print("Установите psycopg: pip install 'psycopg[binary]' — или настройте psql и DATABASE_URL.")
            sys.exit(1)
    print("Таблица knowledge_base очищена.")


def main():
    load_config_env()
    parser = argparse.ArgumentParser(
        description="Очистить KB и заново загрузить БЗ из data (вместо первой попытки)."
    )
    parser.add_argument("--data-dir", default="data", help="Корневая папка с файлами (по умолчанию data)")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет загружено; не очищать и не загружать")
    parser.add_argument("--chunk-size", type=int, default=3000, help="Размер chunk (по умолчанию 3000)")
    parser.add_argument("--overlap", type=int, default=300, help="Перекрытие chunks (по умолчанию 300)")
    parser.add_argument("--encoding", default="utf-8", help="Кодировка текстовых файлов")
    parser.add_argument("--include-test-questions", action="store_true", help="Включить файл вопросы_neurocrm.txt в загрузку")
    args = parser.parse_args()

    if args.dry_run:
        # Только прогон load_kb_from_data в dry-run, без очистки
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "load_kb_from_data.py"),
            "--data-dir", args.data_dir,
            "--dry-run",
            "--chunk-size", str(args.chunk_size),
            "--overlap", str(args.overlap),
            "--encoding", args.encoding,
        ]
        if args.include_test_questions:
            cmd.append("--include-test-questions")
        subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        return

    truncate_knowledge_base()
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "load_kb_from_data.py"),
        "--data-dir", args.data_dir,
        "--chunk-size", str(args.chunk_size),
        "--overlap", str(args.overlap),
        "--encoding", args.encoding,
    ]
    if args.include_test_questions:
        cmd.append("--include-test-questions")
    print("Запуск загрузки из data...")
    rc = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if rc.returncode != 0:
        sys.exit(rc.returncode)
    # Проверка: тот ли сервис видит данные (та же БД)
    kb_url = os.environ.get("KB_API_URL", "http://localhost:8001")
    try:
        import urllib.request
        req = urllib.request.Request(kb_url.rstrip("/") + "/api/kb/stats")
        with urllib.request.urlopen(req, timeout=5) as r:
            import json
            stats = json.loads(r.read().decode())
        total = stats.get("total_chunks", 0)
        active = stats.get("active_chunks", 0)
        print("")
        if total == 0:
            print("Внимание: kb-service сообщает 0 chunks. Возможно, сервис использует другую БД (проверьте DATABASE_URL в config.env и откуда запущен kb-service).")
        else:
            print("Проверка KB: total_chunks=%s, active_chunks=%s" % (total, active))
    except Exception as e:
        print("")
        print("Не удалось проверить /api/kb/stats: %s" % e)
    sys.exit(0)


if __name__ == "__main__":
    main()
