"""
Скрипт для получения статистики Яндекс.Метрики за сегодня
для нейроаналитика (sales-analytic).

Использует:
- YANDEX_METRIKA_COUNTER_ID
- YANDEX_METRIKA_OAUTH_TOKEN
из config.env в корне проекта.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

# Настройка импорта для запуска скрипта из корня проекта (~/brats)
CURRENT_DIR = os.path.dirname(__file__)
PACKAGE_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PACKAGE_ROOT not in sys.path:
    sys.path.append(PACKAGE_ROOT)

from integrations.metrika_client import YandexMetrikaClient


def load_config() -> None:
    """
    Загружает конфигурацию из config.env и проверяет ключевые переменные.
    """
    # Ищем config.env в корне проекта (~/brats)
    # Скрипт находится в ~/brats/sales-analytic/scripts/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    config_path = os.path.join(project_root, "config.env")
    
    if not os.path.exists(config_path):
        raise SystemExit(f"Файл config.env не найден по пути: {config_path}")
    
    load_dotenv(config_path)

    missing = []
    for var in ("YANDEX_METRIKA_COUNTER_ID", "YANDEX_METRIKA_OAUTH_TOKEN"):
        if not os.getenv(var):
            missing.append(var)

    if missing:
        raise SystemExit(
            "Отсутствуют переменные окружения для Яндекс.Метрики: "
            + ", ".join(missing)
            + ". Заполните их в config.env."
        )


async def get_today_stats() -> None:
    """
    Получает базовую статистику за период (по умолчанию за последние 7 дней):
    - визиты
    - просмотры страниц
    - пользователи
    
    Если данных за выбранный период нет, печатает 0 без fallback на realtime.
    """
    load_config()

    # Проверяем токен
    token = os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
    counter_id = os.getenv("YANDEX_METRIKA_COUNTER_ID")
    
    print("Проверка конфигурации:")
    print(f"  Counter ID: {counter_id}")
    print(f"  Token (первые 20 символов): {token[:20] if token else 'НЕ ЗАДАН'}...")
    print(f"  Token длина: {len(token) if token else 0} символов")
    print()
    
    client = YandexMetrikaClient()
    
    # Сначала получаем список всех доступных счётчиков
    print("Получение списка доступных счётчиков...")
    try:
        counters = await client.get_counters_list()
        print(f"✓ Найдено доступных счётчиков: {len(counters)}")
        
        if counters:
            print("\nДоступные счётчики:")
            for counter in counters:
                counter_id = counter.get("id")
                name = counter.get("name", "N/A")
                site = counter.get("site", "N/A")
                is_target = "✓" if str(counter_id) == str(client.counter_id) else " "
                print(f"  {is_target} ID: {counter_id}, Имя: {name}, Сайт: {site}")
        
        # Проверяем, есть ли нужный счётчик в списке
        target_counter = next(
            (c for c in counters if str(c.get("id")) == str(client.counter_id)),
            None
        )
        
        if not target_counter:
            print(f"\n✗ Счётчик {client.counter_id} НЕ найден в списке доступных!")
            print("\nВозможные причины:")
            print("  1. Токен получен для другого аккаунта Яндекс")
            print("  2. Счётчик принадлежит другому аккаунту")
            print("  3. Токен не имеет прав 'metrika:read'")
            print("\nРешение:")
            print("  - Убедитесь, что OAuth токен получен для того же аккаунта,")
            print("    под которым создан счётчик 106736061")
            print("  - При получении токена выберите права 'metrika:read'")
            if counters:
                print(f"\n  Или используйте один из доступных счётчиков:")
                for c in counters[:3]:  # Показываем первые 3
                    print(f"    - ID: {c.get('id')}, Имя: {c.get('name')}")
            return
        
        print(f"\n✓ Счётчик {client.counter_id} найден и доступен!")
        print(f"  Имя: {target_counter.get('name', 'N/A')}")
        print(f"  Сайт: {target_counter.get('site', 'N/A')}")
        
    except Exception as e:
        print(f"✗ Ошибка при получении списка счётчиков: {e}")
        print("  Проверьте правильность YANDEX_METRIKA_OAUTH_TOKEN")
        return

    today = datetime.now().strftime("%Y-%m-%d")

    # Базовый набор метрик для нейроаналитика
    metrics = ["ym:s:visits", "ym:s:pageviews", "ym:s:users"]

    # Берём последние 7 дней (включая сегодня)
    date_to = datetime.now().date()
    date_from = date_to - timedelta(days=6)

    try:
        data = await client.get_conversions(
            date_from=date_from.strftime("%Y-%m-%d"),
            date_to=date_to.strftime("%Y-%m-%d"),
            metrics=metrics,
        )

        totals = data.get("totals", [0, 0, 0])
        visits, pageviews, users = totals[:3]

        print(
            "Статистика Яндекс.Метрики "
            f"за период {date_from.strftime('%Y-%m-%d')} — {date_to.strftime('%Y-%m-%d')}"
        )
        print(f"- Визиты   : {int(visits)}")
        print(f"- Просмотры: {int(pageviews)}")
        print(f"- Пользователи: {int(users)}")

    except Exception as e:
        print(f"Ошибка при получении статистики: {e}")


if __name__ == "__main__":
    asyncio.run(get_today_stats())


