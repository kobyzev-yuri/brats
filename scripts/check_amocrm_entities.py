#!/usr/bin/env python3
"""
Скрипт для проверки различных объектов в amoCRM через API:
- Контакты
- Сделки
- Статусы (воронки)
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

BASE_URL = f"https://{AMOCRM_SUBDOMAIN}.amocrm.ru/api/v4"

headers = {
    "Authorization": f"Bearer {AMOCRM_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def check_entity(entity_name, endpoint, limit=5):
    """Проверка объекта в amoCRM"""
    url = f"{BASE_URL}/{endpoint}"
    
    print(f"\n{'='*60}")
    print(f"🔍 Проверка: {entity_name}")
    print(f"URL: {url}")
    print('='*60)
    
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers, params={"limit": limit}, timeout=30)
        
        print(f"Статус ответа: {response.status_code}")
        
        # Статус 204 означает "No Content" - объектов нет
        if response.status_code == 204:
            print(f"⚠️  {entity_name} не найдены (статус 204 - No Content)")
            return
        
        response.raise_for_status()
        
        try:
            data = response.json()
        except Exception as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            print(f"Полный ответ: {response.text[:500]}")
            return
        
        # Определяем ключ для списка объектов
        embedded_key = None
        if "_embedded" in data:
            # Пробуем разные возможные ключи
            for key in ["contacts", "leads", "pipelines", "statuses", "items"]:
                if key in data["_embedded"]:
                    embedded_key = key
                    break
        
        if embedded_key:
            items = data["_embedded"][embedded_key]
            total = len(items)
            print(f"✅ Найдено {entity_name}: {total}")
            print()
            
            if total > 0:
                print(f"Первые {min(limit, total)} {entity_name}:")
                print()
                
                for i, item in enumerate(items[:limit], 1):
                    print(f"{i}. ID: {item.get('id')}")
                    
                    # Для контактов
                    if 'name' in item:
                        print(f"   Название: {item.get('name')}")
                    
                    # Для сделок
                    if 'name' in item and entity_name == "Сделки":
                        print(f"   Название: {item.get('name')}")
                        if 'price' in item:
                            print(f"   Цена: {item.get('price')}")
                        if 'status_id' in item:
                            print(f"   Статус ID: {item.get('status_id')}")
                        if 'pipeline_id' in item:
                            print(f"   Воронка ID: {item.get('pipeline_id')}")
                    
                    # Для воронок
                    if entity_name == "Воронки (Pipelines)":
                        print(f"   Название: {item.get('name')}")
                        if '_embedded' in item and 'statuses' in item['_embedded']:
                            statuses = item['_embedded']['statuses']
                            print(f"   Статусов в воронке: {len(statuses)}")
                            if statuses:
                                print(f"   Статусы:")
                                for status in statuses[:5]:
                                    status_name = status.get('name', 'N/A')
                                    status_id = status.get('id', 'N/A')
                                    print(f"     - {status_name} (ID: {status_id})")
                        elif 'statuses' in item:
                            statuses = item.get('statuses', [])
                            print(f"   Статусов в воронке: {len(statuses)}")
                            if statuses:
                                print(f"   Статусы:")
                                for status in statuses[:5]:
                                    if isinstance(status, dict):
                                        status_name = status.get('name', 'N/A')
                                        status_id = status.get('id', 'N/A')
                                        print(f"     - {status_name} (ID: {status_id})")
                                    else:
                                        print(f"     - {status}")
                    
                    # Общие поля
                    if 'created_at' in item:
                        from datetime import datetime
                        try:
                            dt = datetime.fromtimestamp(item.get('created_at'))
                            print(f"   Создано: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                        except:
                            pass
                    
                    print()
        else:
            # Если структура нестандартная, показываем что есть
            print(f"✅ Запрос успешен")
            print(f"Структура ответа:")
            print(f"  Ключи: {list(data.keys())}")
            if "_embedded" in data:
                print(f"  Ключи в _embedded: {list(data['_embedded'].keys())}")
            print()
            print("Полный ответ (первые 1000 символов):")
            print(str(data)[:1000])
        
    except httpx.HTTPStatusError as e:
        print(f"❌ Ошибка HTTP {e.response.status_code}")
        print(f"Ответ: {e.response.text[:500]}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("="*60)
    print("Проверка объектов в amoCRM")
    print("="*60)
    
    # Проверяем контакты
    check_entity("Контакты", "contacts", limit=5)
    
    # Проверяем сделки
    check_entity("Сделки", "leads", limit=5)
    
    # Проверяем воронки (pipelines) - они содержат статусы
    check_entity("Воронки (Pipelines)", "leads/pipelines", limit=10)
    
    print("\n" + "="*60)
    print("✅ Проверка завершена")
    print("="*60)

if __name__ == "__main__":
    main()
