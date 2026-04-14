import os
import urllib.parse
import asyncio

import httpx
from dotenv import load_dotenv


# Загружаем переменные из config.env в корне проекта
load_dotenv("config.env")


CLIENT_ID = os.getenv("YANDEX_OAUTH_CLIENT_ID")
CLIENT_SECRET = os.getenv("YANDEX_OAUTH_CLIENT_SECRET")
REDIRECT_URI = os.getenv("YANDEX_OAUTH_REDIRECT_URI")


def _require_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise SystemExit(f"Переменная окружения {var_name} не задана. Заполните её в .env.")
    return value


def build_authorize_url() -> str:
    """
    Формирует ссылку для авторизации пользователя в Яндекс OAuth.
    """
    client_id = _require_env("YANDEX_OAUTH_CLIENT_ID")
    redirect_uri = _require_env("YANDEX_OAUTH_REDIRECT_URI")

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        # Пробуем запросить права к Метрике
        # Если не работает, возможно нужно создать новое приложение
        "scope": "metrika:read metrika:write",  # Запрашиваем права на чтение и запись Метрики
    }
    return "https://oauth.yandex.ru/authorize?" + urllib.parse.urlencode(params)


async def exchange_code_for_token(code: str) -> dict:
    """
    Обменивает authorization code на OAuth access_token.
    """
    client_id = _require_env("YANDEX_OAUTH_CLIENT_ID")
    client_secret = _require_env("YANDEX_OAUTH_CLIENT_SECRET")

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


async def main() -> None:
    authorize_url = build_authorize_url()

    print("1) Открой в браузере эту ссылку и разреши доступ приложению:\n")
    print(authorize_url)
    print("\n2) После редиректа скопируй из адресной строки значение параметра 'code'.\n")

    auth_code = input("3) Вставь сюда значение code: ").strip()
    if not auth_code:
        raise SystemExit("Пустой code. Авторизация не выполнена.")

    token_data = await exchange_code_for_token(auth_code)
    access_token = token_data.get("access_token")
    scope = token_data.get("scope", "не указан")

    print("\nГотово. Твой OAuth токен:")
    print(access_token)
    print(f"\nПрава доступа (scope): {scope}")
    
    if "metrika:read" not in scope:
        print("\n⚠️  ВНИМАНИЕ: Токен не имеет прав 'metrika:read'!")
        print("   Переполучите токен, убедившись, что при авторизации")
        print("   вы разрешили доступ к Яндекс.Метрике.")
    
    print("\nДобавь его в config.env как строку:")
    print(f"YANDEX_METRIKA_OAUTH_TOKEN={access_token}")


if __name__ == "__main__":
    asyncio.run(main())


