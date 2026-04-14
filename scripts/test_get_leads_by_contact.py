#!/usr/bin/env python3
"""
Тест получения сделок по contact_id через amoCRM API
"""
import os
import sys
import httpx
from dotenv import load_dotenv

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

# Используем contact_id из предыдущей проверки
CONTACT_ID = 46692527

print(f"🔍 Тест получения сделок для контакта ID: {CONTACT_ID}")
print()

# Вариант 1: filter[contacts][id]
print("Вариант 1: filter[contacts][id]")
url1 = f"{BASE_URL}/leads?filter[contacts][id]={CONTACT_ID}"
print(f"URL: {url1}")

try:
    with httpx.Client() as client:
        response = client.get(url1, headers=headers, params={"limit": 10}, timeout=30)
    
    print(f"Статус: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        leads = data.get("_embedded", {}).get("leads", [])
        print(f"✅ Найдено сделок: {len(leads)}")
        if leads:
            print(f"Первая сделка: {leads[0].get('name')} (ID: {leads[0].get('id')})")
    else:
        print(f"❌ Ошибка: {response.text[:200]}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print()

# Вариант 2: через with=contacts и фильтрация на клиенте
print("Вариант 2: Получить все сделки и фильтровать по контакту")
url2 = f"{BASE_URL}/leads"

try:
    with httpx.Client() as client:
        response = client.get(url2, headers=headers, params={"limit": 50, "with": "contacts"}, timeout=30)
    
    print(f"Статус: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        all_leads = data.get("_embedded", {}).get("leads", [])
        print(f"Всего сделок получено: {len(all_leads)}")
        
        # Фильтруем по контакту
        filtered_leads = []
        for lead in all_leads:
            contacts = lead.get("_embedded", {}).get("contacts", [])
            contact_ids = [c.get("id") for c in contacts]
            if CONTACT_ID in contact_ids:
                filtered_leads.append(lead)
        
        print(f"✅ Сделок для контакта {CONTACT_ID}: {len(filtered_leads)}")
        if filtered_leads:
            print(f"Первая сделка: {filtered_leads[0].get('name')} (ID: {filtered_leads[0].get('id')})")
    else:
        print(f"❌ Ошибка: {response.text[:200]}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

print()

# Вариант 3: через /contacts/{id}/leads (если поддерживается)
print("Вариант 3: /contacts/{id}/leads")
url3 = f"{BASE_URL}/contacts/{CONTACT_ID}/leads"

try:
    with httpx.Client() as client:
        response = client.get(url3, headers=headers, params={"limit": 10}, timeout=30)
    
    print(f"Статус: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        leads = data.get("_embedded", {}).get("leads", [])
        print(f"✅ Найдено сделок: {len(leads)}")
        if leads:
            print(f"Первая сделка: {leads[0].get('name')} (ID: {leads[0].get('id')})")
    elif response.status_code == 404:
        print("⚠️  Endpoint не поддерживается")
    else:
        print(f"❌ Ошибка: {response.text[:200]}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
