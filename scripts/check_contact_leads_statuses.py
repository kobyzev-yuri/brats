#!/usr/bin/env python3
"""
Проверка всех сделок контакта и их статусов
"""
import os
import sys
import httpx
from dotenv import load_dotenv
from datetime import datetime

# Отключаем прокси
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

CONTACT_ID = 46692527  # Из предыдущих проверок

print(f"🔍 Проверка всех сделок контакта ID: {CONTACT_ID}")
print("="*60)

try:
    with httpx.Client() as client:
        # Получаем сделки контакта
        url = f"{BASE_URL}/leads?filter[contacts][id]={CONTACT_ID}"
        response = client.get(url, headers=headers, params={"limit": 250}, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        leads = data.get("_embedded", {}).get("leads", [])
        
        print(f"✅ Всего сделок найдено: {len(leads)}")
        print()
        
        if len(leads) == 0:
            print("⚠️  Сделок не найдено для этого контакта")
            sys.exit(0)
        
        # Группируем по статусам
        statuses = {}
        closed_statuses = [142, 143]  # Стандартные закрытые статусы
        
        for lead in leads:
            status_id = lead.get('status_id')
            status_name = lead.get('status_name', 'Неизвестно')
            
            if status_id not in statuses:
                statuses[status_id] = {
                    'name': status_name,
                    'count': 0,
                    'leads': []
                }
            
            statuses[status_id]['count'] += 1
            statuses[status_id]['leads'].append({
                'id': lead.get('id'),
                'name': lead.get('name'),
                'price': lead.get('price', 0) / 100 if lead.get('price') else 0,
                'closed_at': lead.get('closed_at'),
                'created_at': lead.get('created_at')
            })
        
        print("📊 Статистика по статусам:")
        print()
        
        closed_count = 0
        open_count = 0
        
        for status_id, info in sorted(statuses.items(), key=lambda x: x[1]['count'], reverse=True):
            is_closed = status_id in closed_statuses
            marker = "🔒" if is_closed else "🔓"
            
            print(f"{marker} Статус ID {status_id}: {info['name']}")
            print(f"   Количество сделок: {info['count']}")
            
            if is_closed:
                closed_count += info['count']
                print(f"   ✅ Это ЗАКРЫТЫЙ статус")
            else:
                open_count += info['count']
                print(f"   ⚠️  Это ОТКРЫТЫЙ статус")
            
            # Показываем первые 3 сделки
            if info['leads']:
                print(f"   Примеры сделок:")
                for lead in info['leads'][:3]:
                    created = datetime.fromtimestamp(lead['created_at']).strftime('%Y-%m-%d') if lead['created_at'] else 'N/A'
                    closed = datetime.fromtimestamp(lead['closed_at']).strftime('%Y-%m-%d') if lead['closed_at'] else 'N/A'
                    print(f"     - {lead['name']} (ID: {lead['id']}, цена: {lead['price']:,.0f} руб., создано: {created}, закрыто: {closed})")
            print()
        
        print("="*60)
        print(f"📈 Итого:")
        print(f"   Всего сделок: {len(leads)}")
        print(f"   Закрытых (статусы 142, 143): {closed_count}")
        print(f"   Открытых: {open_count}")
        print()
        
        if closed_count == 0:
            print("⚠️  ВНИМАНИЕ: У этого контакта нет сделок со статусами 142 или 143!")
            print()
            print("💡 Возможные решения:")
            print("   1. Проверьте, есть ли у контакта другие закрытые статусы")
            print("   2. Используйте параметр closed_statuses для указания других статусов")
            print("   3. Или получите все сделки (не только закрытые)")
            print()
            print("Пример запроса с кастомными статусами:")
            print(f'   {{"contact_id": {CONTACT_ID}, "closed_statuses": {list(statuses.keys())[:5]}}}')
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
