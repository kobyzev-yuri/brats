#!/usr/bin/env python3
"""
Тест логики фильтрации закрытых сделок (как в workflow)
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

BASE_URL = f"https://{AMOCRM_SUBDOMAIN}.amocrm.ru/api/v4"
headers = {
    "Authorization": f"Bearer {AMOCRM_ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

CONTACT_ID = 46692527
closedStatuses = [142, 143]

print(f"🔍 Тест логики фильтрации (как в workflow)")
print(f"Контакта ID: {CONTACT_ID}")
print(f"Закрытые статусы: {closedStatuses}")
print("="*60)

try:
    with httpx.Client() as client:
        url = f"{BASE_URL}/leads?filter[contacts][id]={CONTACT_ID}"
        response = client.get(url, headers=headers, params={"limit": 250}, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        leads = data.get("_embedded", {}).get("leads", [])
        
        print(f"✅ Получено сделок: {len(leads)}")
        print()
        
        # Проверяем структуру первой сделки
        if leads:
            first_lead = leads[0]
            print("📋 Структура первой сделки:")
            print(f"  Ключи: {list(first_lead.keys())[:20]}")
            print(f"  status_id: {first_lead.get('status_id')} (тип: {type(first_lead.get('status_id'))})")
            print(f"  status_name: {first_lead.get('status_name')}")
            print(f"  closed_at: {first_lead.get('closed_at')}")
            print()
        
        # Фильтруем закрытые сделки (как в workflow)
        closedLeads = []
        for lead in leads:
            statusId = lead.get('status_id')
            # Проверяем разные варианты типа данных
            if statusId in closedStatuses:
                closedLeads.append(lead)
            elif str(statusId) in [str(s) for s in closedStatuses]:
                print(f"⚠️  Найдено совпадение через строковое сравнение: {statusId}")
                closedLeads.append(lead)
        
        print(f"🔒 Закрытых сделок найдено: {len(closedLeads)}")
        print()
        
        if closedLeads:
            print("✅ Закрытые сделки:")
            for lead in closedLeads[:5]:
                closedDate = datetime.fromtimestamp(lead['closed_at']).strftime('%Y-%m-%d') if lead.get('closed_at') else 'N/A'
                print(f"  - {lead.get('name')} (ID: {lead.get('id')}, статус: {lead.get('status_id')}, закрыто: {closedDate})")
        else:
            print("❌ Закрытые сделки не найдены!")
            print()
            print("🔍 Проверяем все статусы:")
            status_ids = set()
            for lead in leads:
                status_id = lead.get('status_id')
                status_ids.add(status_id)
                if status_id in [142, 143] or str(status_id) in ['142', '143']:
                    print(f"  ⚠️  Найдена сделка со статусом {status_id}: {lead.get('name')}")
            
            print(f"\nВсе уникальные статусы: {sorted(status_ids)}")
            print(f"Ищем статусы: {closedStatuses}")
            
            # Проверяем точное совпадение
            found_142 = [l for l in leads if l.get('status_id') == 142]
            found_143 = [l for l in leads if l.get('status_id') == 143]
            print(f"Сделок со статусом 142: {len(found_142)}")
            print(f"Сделок со статусом 143: {len(found_143)}")
            
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
