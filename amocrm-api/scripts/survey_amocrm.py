#!/usr/bin/env python3
"""
Предварительное обследование amoCRM: какие объекты и структура есть, чего не хватает.
Запуск из корня репозитория: python amocrm-api/scripts/survey_amocrm.py
Либо из amocrm-api: python scripts/survey_amocrm.py (подгружает config из корня репо).
"""
import os
import sys
from pathlib import Path

# Корень репозитория и amocrm-api
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AMOCRM_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AMOCRM_API_ROOT))
os.chdir(REPO_ROOT)

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "config.env")
load_dotenv(REPO_ROOT / ".env")

from client import AmoCRMClient


def main():
    print("=" * 70)
    print("ОБСЛЕДОВАНИЕ amoCRM: структура и наличие объектов")
    print("=" * 70)

    try:
        client = AmoCRMClient()
    except Exception as e:
        print(f"\n❌ Не удалось инициализировать клиент: {e}")
        print("   Проверьте config.env: AMOCRM_SUBDOMAIN, AMOCRM_ACCESS_TOKEN, AMOCRM_REFRESH_TOKEN")
        sys.exit(1)

    if not client.subdomain or not client._access_token:
        print("\n❌ Задайте AMOCRM_SUBDOMAIN и AMOCRM_ACCESS_TOKEN в config.env (в корне репозитория)")
        sys.exit(1)

    print(f"\nПоддомен: {client.subdomain}")
    print()

    # --- Воронки и статусы ---
    print("-" * 70)
    print("1. ВОРОНКИ ПРОДАЖ (pipelines) И СТАТУСЫ")
    print("-" * 70)
    try:
        data = client.get_pipelines()
        pipelines = data.get("_embedded", {}).get("pipelines", [])
        if not pipelines:
            print("   ⚠️  Воронок не найдено (пустой список или 204).")
        else:
            print(f"   Найдено воронок: {len(pipelines)}\n")
            for p in pipelines:
                name = p.get("name", "—")
                pid = p.get("id", "—")
                statuses = p.get("_embedded", {}).get("statuses", []) or p.get("statuses", [])
                print(f"   • {name} (id={pid})")
                print(f"     Статусов: {len(statuses)}")
                for s in statuses[:8]:
                    print(f"       - {s.get('name', '—')} (id={s.get('id')})")
                if len(statuses) > 8:
                    print(f"       ... и ещё {len(statuses) - 8}")
                print()
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # --- Сделки (лиды) ---
    print("-" * 70)
    print("2. СДЕЛКИ (лиды)")
    print("-" * 70)
    try:
        data = client.get_leads(limit=250, page=1)
        leads = data.get("_embedded", {}).get("leads", [])
        total = len(leads)
        if total == 0:
            print("   ⚠️  Сделок нет (пустой список или 204).")
        else:
            print(f"   Получено сделок (первая страница, до 250): {total}")
            # Примеры
            for i, lead in enumerate(leads[:5], 1):
                print(f"   {i}. id={lead.get('id')} | {lead.get('name', '—')[:50]} | pipeline_id={lead.get('pipeline_id')} | status_id={lead.get('status_id')}")
            if total > 5:
                print(f"   ... и ещё {total - 5}")
        print()
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # --- Контакты ---
    print("-" * 70)
    print("3. КОНТАКТЫ")
    print("-" * 70)
    try:
        data = client.get_contacts(limit=250, page=1)
        contacts = data.get("_embedded", {}).get("contacts", [])
        total = len(contacts)
        if total == 0:
            print("   ⚠️  Контактов нет (пустой список или 204).")
        else:
            print(f"   Получено контактов (первая страница, до 250): {total}")
            for i, c in enumerate(contacts[:5], 1):
                print(f"   {i}. id={c.get('id')} | {c.get('name', '—')[:50]}")
            if total > 5:
                print(f"   ... и ещё {total - 5}")
        print()
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # --- Каталоги (в т.ч. товары/продукты) ---
    print("-" * 70)
    print("4. КАТАЛОГИ (товары / продукты)")
    print("-" * 70)
    try:
        data = client.get_catalogs()
        catalogs = data.get("_embedded", {}).get("catalogs", [])
        if not catalogs:
            print("   ⚠️  Каталогов нет. Продуктов в amoCRM не настроено.")
        else:
            print(f"   Найдено каталогов: {len(catalogs)}\n")
            for cat in catalogs:
                cid = cat.get("id")
                name = cat.get("name", "—")
                print(f"   • {name} (id={cid})")
                try:
                    el = client.get_catalog_elements(cid, limit=10, page=1)
                    elements = el.get("_embedded", {}).get("elements", [])
                    total_el = len(elements)
                    if total_el == 0:
                        print(f"     Элементов: 0 (каталог пуст)")
                    else:
                        print(f"     Элементов на первой странице: {total_el}")
                        for e in elements[:3]:
                            print(f"       - id={e.get('id')} | name={e.get('name', '—')[:40]}")
                except Exception as e2:
                    print(f"     Ошибка чтения элементов: {e2}")
                print()
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # --- Итоговая сводка: чего не хватает ---
    print("=" * 70)
    print("СВОДКА: ЧЕГО НЕ ХВАТАЕТ ДЛЯ ИНТЕГРАЦИИ")
    print("=" * 70)
    missing = []
    try:
        if not client.get_pipelines().get("_embedded", {}).get("pipelines"):
            missing.append("Воронки продаж не найдены — нужна хотя бы одна воронка для создания сделок.")
    except Exception:
        missing.append("Не удалось прочитать воронки — проверьте права доступа API.")
    try:
        catalogs = client.get_catalogs().get("_embedded", {}).get("catalogs", [])
        if not catalogs:
            missing.append("Каталог товаров/продуктов отсутствует — позиции КП и договоров формируем из PostgreSQL (таблица products).")
        else:
            has_elements = False
            for c in catalogs:
                try:
                    el = client.get_catalog_elements(c["id"], limit=1)
                    if el.get("_embedded", {}).get("elements"):
                        has_elements = True
                        break
                except Exception:
                    pass
            if not has_elements:
                missing.append("Каталоги есть, но пустые — товары можно вести в PostgreSQL.")
    except Exception:
        missing.append("Не удалось прочитать каталоги.")
    if not missing:
        print("   Все ключевые объекты присутствуют.")
    else:
        for m in missing:
            print(f"   • {m}")
    print()
    print("Обследование завершено.")
    print("=" * 70)


if __name__ == "__main__":
    main()
