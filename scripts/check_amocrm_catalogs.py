#!/usr/bin/env python3
"""
Скрипт для проверки каталогов в amoCRM через API
"""
import os
import sys
import httpx
from dotenv import load_dotenv

# Отключаем прокси для этого скрипта
os.environ.pop('all_proxy', None)
os.environ.pop('ALL_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('https_proxy', None)
os.environ.pop('HTTPS_PROXY', None)

# Загрузка переменных окружения
load_dotenv('../config.env')

AMOCRM_SUBDOMAIN = os.getenv("AMOCRM_SUBDOMAIN")
AMOCRM_ACCESS_TOKEN = os.getenv("AMOCRM_ACCESS_TOKEN")

if not AMOCRM_SUBDOMAIN or not AMOCRM_ACCESS_TOKEN:
    print("❌ Ошибка: AMOCRM_SUBDOMAIN и AMOCRM_ACCESS_TOKEN должны быть в config.env")
    sys.exit(1)

def check_catalogs():
    """Проверка каталогов в amoCRM"""
    url = f"https://{AMOCRM_SUBDOMAIN}.amocrm.ru/api/v4/catalogs"
    
    headers = {
        "Authorization": f"Bearer {AMOCRM_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print(f"🔍 Проверка каталогов в amoCRM...")
    print(f"URL: {url}")
    print()
    
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=30)
        
        print(f"Статус ответа: {response.status_code}")
        
        # Статус 204 означает "No Content" - каталогов нет
        if response.status_code == 204:
            print()
            print("⚠️  Каталоги не найдены в amoCRM (статус 204 - No Content)")
            print()
            print("💡 Совет: Создайте каталог товаров в amoCRM:")
            print("   1. В основном меню слева найдите раздел 'Каталоги' или 'Товары'")
            print("   2. Или перейдите: Настройки → Каталоги (если доступно)")
            print("   3. Создайте каталог")
            print("   4. Добавьте элементы (товары)")
            return
        
        response.raise_for_status()
        
        try:
            data = response.json()
        except Exception as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            print(f"Полный ответ: {response.text}")
            return
        
        print(f"✅ Запрос успешен (статус {response.status_code})")
        print()
        
        # Проверяем структуру ответа
        print("Структура ответа:")
        print(f"  Ключи в ответе: {list(data.keys())}")
        print()
        
        catalogs = data.get("_embedded", {}).get("catalogs", [])
        
        if not catalogs:
            print("⚠️  Каталоги не найдены в amoCRM")
            print()
            print("Полный ответ API:")
            print(response.text)
            print()
            print("💡 Совет: Создайте каталог товаров в amoCRM:")
            print("   1. В основном меню слева найдите раздел 'Каталоги' или 'Товары'")
            print("   2. Или перейдите: Настройки → Каталоги (если доступно)")
            print("   3. Создайте каталог")
            print("   4. Добавьте элементы (товары)")
        else:
            print(f"✅ Найдено каталогов: {len(catalogs)}")
            print()
            
            for i, catalog in enumerate(catalogs, 1):
                print(f"Каталог {i}:")
                print(f"  ID: {catalog.get('id')}")
                print(f"  Название: {catalog.get('name')}")
                print(f"  Тип: {catalog.get('type')}")
                print()
                
                # Проверяем элементы каталога
                catalog_id = catalog.get('id')
                if catalog_id:
                    check_catalog_elements(catalog_id, catalog.get('name'))
                print("-" * 50)
                print()
    
    except httpx.HTTPStatusError as e:
        print(f"❌ Ошибка HTTP {e.response.status_code}: {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

def check_catalog_elements(catalog_id, catalog_name):
    """Проверка элементов каталога"""
    url = f"https://{AMOCRM_SUBDOMAIN}.amocrm.ru/api/v4/catalogs/{catalog_id}/elements"
    
    headers = {
        "Authorization": f"Bearer {AMOCRM_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers, params={"limit": 10}, timeout=30)
        
        response.raise_for_status()
        
        data = response.json()
        elements = data.get("_embedded", {}).get("elements", [])
        
        print(f"  Элементов в каталоге '{catalog_name}': {len(elements)}")
        
        if elements:
            print("  Первые элементы:")
            for elem in elements[:5]:
                print(f"    - {elem.get('name')} (ID: {elem.get('id')}, SKU: {elem.get('sku', 'N/A')})")
        else:
            print(f"  ⚠️  Каталог '{catalog_name}' пустой")
    
    except Exception as e:
        print(f"  ⚠️  Не удалось получить элементы: {e}")

if __name__ == "__main__":
    check_catalogs()
