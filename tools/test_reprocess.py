#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функционала вторичной обработки
"""

import sys
from pathlib import Path

print("=" * 60)
print("Проверка функционала вторичной обработки")
print("=" * 60)

# 1. Проверка импорта приложения
print("\n1. Проверка импорта Flask приложения...")
try:
    from kb_admin_app import app
    print("   ✅ Приложение импортировано успешно")
except Exception as e:
    print(f"   ❌ Ошибка импорта: {e}")
    sys.exit(1)

# 2. Проверка роутов
print("\n2. Проверка роутов...")
routes = [str(r) for r in app.url_map.iter_rules()]
reprocess_routes = [r for r in routes if 'reprocess' in r.lower()]
if reprocess_routes:
    print(f"   ✅ Найдено роутов reprocess: {len(reprocess_routes)}")
    for route in reprocess_routes:
        print(f"      - {route}")
else:
    print("   ❌ Роуты reprocess не найдены!")
    sys.exit(1)

# 3. Проверка шаблонов
print("\n3. Проверка шаблонов...")
templates = {
    'reprocess.html': 'Страница вторичной обработки',
    'blocks_list.html': 'Список блоков',
    'base.html': 'Базовый шаблон',
    'block_detail.html': 'Детали блока'
}

all_ok = True
for template, desc in templates.items():
    path = Path(f'templates/{template}')
    if path.exists():
        size = path.stat().st_size
        print(f"   ✅ {template} ({desc}) - {size} bytes")
    else:
        print(f"   ❌ {template} ({desc}) - НЕ НАЙДЕН!")
        all_ok = False

if not all_ok:
    sys.exit(1)

# 4. Проверка наличия кнопок в шаблонах
print("\n4. Проверка наличия кнопок в шаблонах...")
import re

checks = [
    ('templates/blocks_list.html', 'reprocessSelected', 'Кнопка массовой обработки'),
    ('templates/blocks_list.html', 'reprocessBlocks', 'Кнопка обработки одного блока'),
    ('templates/block_detail.html', 'reprocessBlocks', 'Кнопка на странице деталей'),
    ('templates/base.html', 'reprocessBlocks', 'Глобальная функция'),
    ('templates/base.html', 'reprocess_page', 'Ссылка в меню'),
]

all_checks_ok = True
for file_path, pattern, desc in checks:
    if Path(file_path).exists():
        content = Path(file_path).read_text()
        if pattern in content:
            print(f"   ✅ {desc} - найдено в {file_path}")
        else:
            print(f"   ❌ {desc} - НЕ найдено в {file_path}")
            all_checks_ok = False
    else:
        print(f"   ❌ Файл {file_path} не существует")
        all_checks_ok = False

if not all_checks_ok:
    sys.exit(1)

# 5. Проверка Gemini интеграции
print("\n5. Проверка интеграции с Gemini...")
try:
    sys.path.insert(0, str(Path('kb-service')))
    from services.gemini_text_service import get_gemini_text_service
    print("   ✅ GeminiTextService доступен")
    GEMINI_AVAILABLE = True
except ImportError:
    print("   ⚠️  GeminiTextService не доступен (режим демо)")
    GEMINI_AVAILABLE = False

print("\n" + "=" * 60)
print("РЕЗУЛЬТАТ: Все проверки пройдены успешно!")
print("=" * 60)
print("\nДля использования:")
print("1. Перезапустите Flask приложение: python3 kb_admin_app.py")
print("2. Откройте http://localhost:5000/blocks")
print("3. Выберите блоки и нажмите 'Вторичная обработка'")
print("4. Или перейдите в меню -> 'Вторичная обработка'")
print("\nЕсли кнопки не видны:")
print("- Очистите кэш браузера (Ctrl+Shift+R)")
print("- Проверьте консоль браузера на ошибки (F12)")



