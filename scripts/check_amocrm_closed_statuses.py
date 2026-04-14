#!/usr/bin/env python3
"""
Скрипт для проверки статусов сделок в amoCRM и определения закрытых статусов
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

def check_pipelines_and_statuses():
    """Проверка воронок и их статусов для определения закрытых"""
    url = f"{BASE_URL}/leads/pipelines"
    
    print("🔍 Проверка воронок и статусов...")
    print()
    
    try:
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        pipelines = data.get("_embedded", {}).get("pipelines", [])
        
        print(f"✅ Найдено воронок: {len(pipelines)}")
        print()
        
        closed_statuses = []
        
        for pipeline in pipelines:
            pipeline_id = pipeline.get('id')
            pipeline_name = pipeline.get('name')
            
            print(f"Воронка: {pipeline_name} (ID: {pipeline_id})")
            
            # Статусы могут быть в _embedded или напрямую
            statuses = []
            if "_embedded" in pipeline and "statuses" in pipeline["_embedded"]:
                statuses = pipeline["_embedded"]["statuses"]
            elif "statuses" in pipeline:
                statuses = pipeline["statuses"]
            
            if statuses:
                print(f"  Статусов: {len(statuses)}")
                
                for status in statuses:
                    status_id = status.get('id')
                    status_name = status.get('name')
                    is_closed = status.get('is_editable', True) == False  # Обычно закрытые статусы не редактируются
                    # Но лучше проверить по типу или названию
                    
                    # Проверяем по названию (типичные закрытые статусы)
                    closed_keywords = ['закрыт', 'реализован', 'успешно', 'выполнен', 'завершен', 'отказ']
                    is_closed_by_name = any(keyword in status_name.lower() for keyword in closed_keywords)
                    
                    if is_closed_by_name or not status.get('is_editable', True):
                        closed_statuses.append({
                            'id': status_id,
                            'name': status_name,
                            'pipeline_id': pipeline_id,
                            'pipeline_name': pipeline_name
                        })
                        print(f"    ✅ ЗАКРЫТЫЙ: {status_name} (ID: {status_id})")
                    else:
                        print(f"    - {status_name} (ID: {status_id})")
            print()
        
        print("="*60)
        print("📋 Сводка закрытых статусов:")
        print("="*60)
        if closed_statuses:
            for status in closed_statuses:
                print(f"  {status['name']} (ID: {status['id']}) в воронке '{status['pipeline_name']}'")
        else:
            print("  ⚠️  Закрытые статусы не найдены автоматически")
            print("  💡 Совет: Проверьте статусы вручную в amoCRM")
        
        return closed_statuses
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    closed_statuses = check_pipelines_and_statuses()
    
    if closed_statuses:
        print()
        print("💡 Используйте эти ID статусов для фильтрации закрытых сделок:")
        status_ids = [str(s['id']) for s in closed_statuses]
        print(f"   {', '.join(status_ids)}")
