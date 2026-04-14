#!/usr/bin/env python3
"""Проверить, что DLP маршруты зарегистрированы в приложении (перед запуском сервера)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api.main import app

dlp_routes = [r for r in app.routes if hasattr(r, "path") and "dlp" in r.path]
if not dlp_routes:
    print("ERROR: No DLP routes found")
    sys.exit(1)
print("DLP routes registered:")
for r in dlp_routes:
    methods = getattr(r, "methods", set()) or set()
    print("  ", methods, r.path)
print("OK")
