"""
Скрипт для получения OAuth токена Яндекс.Метрики с проверкой доступа к конкретному счётчику.

Этот скрипт:
1. Получает токен через OAuth
2. Проверяет, что токен видит нужный счётчик
3. Если не видит - подсказывает, что делать
"""

import os
import sys
import urllib.parse
import asyncio

import httpx
from dotenv import load_dotenv

# Настройка импорта
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Загружаем config.env
config_path = os.path.join(PROJECT_ROOT, "config.env")
if not os.path.exists(config_path):
    raise SystemExit(f"Файл config.env не найден: {config_path}")

load_dotenv(config_path)


def build_authorize_url(client_id: str, redirect_uri: str) -> str:
    """Формирует URL для авторизации с правами к Метрике"""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "metrika:read",  # Права на чтение Метрики
    }
    return "https://oauth.yandex.ru/authorize?" + urllib.parse.urlencode(params)


async def exchange_code_for_token(code: str, client_id: str, client_secret: str) -> dict:
    """Обменивает authorization code на OAuth token"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth.yandex.ru/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def check_token_access(token: str, target_counter_id: str) -> tuple[bool, list]:
    """
    Проверяет, видит ли токен нужный счётчик.
    
    Returns:
        (found, all_counters) - найден ли счётчик и список всех доступных
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api-metrika.yandex.net/management/v1/counters",
                headers={"Authorization": f"OAuth {token}"}
            )
            response.raise_for_status()
            data = response.json()
            counters = data.get("counters", [])
            
            # Ищем нужный счётчик
            found = any(str(c.get("id")) == str(target_counter_id) for c in counters)
            return found, counters
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                return False, []
            raise


async def main():
    print("=" * 60)
    print("Получение OAuth токена для Яндекс.Метрики")
    print("=" * 60)
    print()
    
    # Получаем настройки
    client_id = os.getenv("YANDEX_OAUTH_CLIENT_ID")
    client_secret = os.getenv("YANDEX_OAUTH_CLIENT_SECRET")
    redirect_uri = os.getenv("YANDEX_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/yandex/callback")
    target_counter_id = os.getenv("YANDEX_METRIKA_COUNTER_ID", "106736061")
    
    if not client_id or not client_secret:
        print("❌ Ошибка: YANDEX_OAUTH_CLIENT_ID и YANDEX_OAUTH_CLIENT_SECRET должны быть в config.env")
        print("\nИспользуй данные из приложения brats или brats_api:")
        print("  - Зайди на https://oauth.yandex.ru")
        print("  - Открой своё приложение")
        print("  - Скопируй Client ID и Client Secret")
        return
    
    print(f"📋 Настройки:")
    print(f"   Client ID: {client_id[:20]}...")
    print(f"   Redirect URI: {redirect_uri}")
    print(f"   Целевой счётчик: {target_counter_id}")
    print()
    
    # Формируем URL авторизации
    auth_url = build_authorize_url(client_id, redirect_uri)
    
    print("🔗 Шаг 1: Авторизация")
    print("   Открой эту ссылку в браузере (убедись, что авторизован под kobyzevyuri):")
    print()
    print(f"   {auth_url}")
    print()
    print("   ⚠️  ВАЖНО:")
    print("   - Убедись, что в браузере авторизован аккаунт kobyzevyuri")
    print("   - При авторизации разреши доступ к Яндекс.Метрике")
    print("   - После редиректа скопируй 'code' из адресной строки")
    print()
    
    code = input("📝 Шаг 2: Вставь сюда значение 'code' из URL: ").strip()
    if not code:
        print("❌ Пустой code. Прерываю.")
        return
    
    print()
    print("🔄 Шаг 3: Обмениваю code на токен...")
    try:
        token_data = await exchange_code_for_token(code, client_id, client_secret)
        token = token_data.get("access_token")
        scope = token_data.get("scope", "не указан")
        
        print(f"✅ Токен получен!")
        print(f"   Scope: {scope}")
        print()
        
        if "metrika:read" not in scope:
            print("⚠️  ВНИМАНИЕ: Токен не имеет прав 'metrika:read'!")
            print("   Это может означать, что приложение не поддерживает эти права.")
            print()
        
        print("🔍 Шаг 4: Проверяю доступ к счётчику...")
        found, counters = await check_token_access(token, target_counter_id)
        
        if found:
            print(f"✅ Отлично! Токен видит счётчик {target_counter_id}")
            print()
            print("📝 Добавь в config.env:")
            print(f"YANDEX_METRIKA_OAUTH_TOKEN={token}")
            print()
            print("🎉 Готово! Теперь можно запускать get_today_metrika_stats.py")
        else:
            print(f"❌ Токен НЕ видит счётчик {target_counter_id}")
            print()
            print("Доступные счётчики для этого токена:")
            if counters:
                for c in counters:
                    print(f"   - ID: {c.get('id')}, Имя: {c.get('name')}, Сайт: {c.get('site', 'N/A')}")
            else:
                print("   (нет доступных счётчиков)")
            print()
            print("Возможные причины:")
            print("1. Токен получен для другого аккаунта")
            print("2. Счётчик принадлежит другому аккаунту")
            print("3. Приложение не имеет прав metrika:read")
            print()
            print("Решение:")
            print("- Убедись, что авторизуешься под аккаунтом kobyzevyuri")
            print("- Убедись, что счётчик 106736061 создан под этим же аккаунтом")
            print()
            if counters:
                print(f"Или временно используй один из доступных счётчиков:")
                for c in counters[:3]:
                    print(f"   YANDEX_METRIKA_COUNTER_ID={c.get('id')}")
    
    except httpx.HTTPStatusError as e:
        print(f"❌ Ошибка при обмене code на токен: {e}")
        print(f"   Ответ: {e.response.text}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())












