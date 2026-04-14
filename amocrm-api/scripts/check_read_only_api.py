#!/usr/bin/env python3
"""
Проверка всех read-only эндпоинтов amocrm-api (без создания объектов).
Запуск из корня репо: python amocrm-api/scripts/check_read_only_api.py
Или через API (сервер на :8010): python amocrm-api/scripts/check_read_only_api.py --base-url http://localhost:8010
"""
import argparse
import sys
from pathlib import Path

# Корень репо для импорта client
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "amocrm-api"))

def check_via_client() -> list[tuple[str, bool, str]]:
    """Проверка через AmoCRMClient (напрямую к amoCRM)."""
    from client import AmoCRMClient
    results = []
    client = AmoCRMClient()
    if not client.subdomain or not client._access_token:
        return [("config", False, "AMOCRM_SUBDOMAIN/AMOCRM_ACCESS_TOKEN не заданы")]
    lead_id = contact_id = None
    # 1. Воронки
    try:
        data = client.get_pipelines()
        n = len(data.get("_embedded", {}).get("pipelines", []))
        results.append(("GET /api/pipelines", True, f"воронок: {n}"))
    except Exception as e:
        results.append(("GET /api/pipelines", False, str(e)))
    # 2. Список лидов
    try:
        data = client.get_leads(limit=2)
        leads = data.get("_embedded", {}).get("leads", [])
        if leads:
            lead_id = leads[0]["id"]
        results.append(("GET /api/leads", True, f"получено лидов: {len(leads)}"))
    except Exception as e:
        results.append(("GET /api/leads", False, str(e)))
    # 3. Один лид
    if lead_id:
        try:
            data = client.get_lead(lead_id)
            results.append((f"GET /api/leads/{lead_id}", True, "ok"))
        except Exception as e:
            results.append((f"GET /api/leads/{{id}}", False, str(e)))
    else:
        results.append(("GET /api/leads/{id}", False, "нет id для проверки"))
    # 4. Список контактов
    try:
        data = client.get_contacts(limit=2)
        contacts = data.get("_embedded", {}).get("contacts", [])
        if contacts:
            contact_id = contacts[0]["id"]
        results.append(("GET /api/contacts", True, f"получено контактов: {len(contacts)}"))
    except Exception as e:
        results.append(("GET /api/contacts", False, str(e)))
    # 5. Один контакт
    if contact_id:
        try:
            client.get_contact(contact_id)
            results.append((f"GET /api/contacts/{contact_id}", True, "ok"))
        except Exception as e:
            results.append(("GET /api/contacts/{id}", False, str(e)))
    else:
        results.append(("GET /api/contacts/{id}", False, "нет id для проверки"))
    # 6. Примечания к сделке
    if lead_id:
        try:
            data = client.get_lead_notes(lead_id, limit=5)
            notes = data.get("_embedded", {}).get("notes", [])
            results.append((f"GET /api/leads/{{id}}/notes", True, f"примечаний: {len(notes)}"))
        except Exception as e:
            results.append(("GET /api/leads/{id}/notes", False, str(e)))
    else:
        results.append(("GET /api/leads/{id}/notes", False, "нет lead_id"))
    # 7. Каталоги
    try:
        data = client.get_catalogs()
        catalogs = data.get("_embedded", {}).get("catalogs", [])
        results.append(("GET /api/catalogs", True, f"каталогов: {len(catalogs)}"))
    except Exception as e:
        results.append(("GET /api/catalogs", False, str(e)))
    return results


def check_via_http(base_url: str) -> list[tuple[str, bool, str]]:
    """Проверка через HTTP (сервис amocrm-api на base_url)."""
    import urllib.request
    import json
    results = []
    base = base_url.rstrip("/")
    lead_id = contact_id = None
    def get(path):
        req = urllib.request.Request(f"{base}{path}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    # health
    try:
        d = get("/health")
        results.append(("GET /health", d.get("status") == "ok", d.get("service", "")))
    except Exception as e:
        results.append(("GET /health", False, str(e)))
    # pipelines
    try:
        d = get("/api/pipelines")
        n = len(d.get("_embedded", {}).get("pipelines", []))
        results.append(("GET /api/pipelines", True, f"воронок: {n}"))
    except Exception as e:
        results.append(("GET /api/pipelines", False, str(e)))
    # leads
    try:
        d = get("/api/leads?limit=2")
        leads = d.get("_embedded", {}).get("leads", [])
        if leads:
            lead_id = leads[0]["id"]
        results.append(("GET /api/leads", True, f"получено лидов: {len(leads)}"))
    except Exception as e:
        results.append(("GET /api/leads", False, str(e)))
    if lead_id:
        try:
            get(f"/api/leads/{lead_id}")
            results.append((f"GET /api/leads/{{id}}", True, "ok"))
        except Exception as e:
            results.append(("GET /api/leads/{id}", False, str(e)))
    else:
        results.append(("GET /api/leads/{id}", False, "нет id"))
    # contacts
    try:
        d = get("/api/contacts?limit=2")
        contacts = d.get("_embedded", {}).get("contacts", [])
        if contacts:
            contact_id = contacts[0]["id"]
        results.append(("GET /api/contacts", True, f"получено контактов: {len(contacts)}"))
    except Exception as e:
        results.append(("GET /api/contacts", False, str(e)))
    if contact_id:
        try:
            get(f"/api/contacts/{contact_id}")
            results.append((f"GET /api/contacts/{{id}}", True, "ok"))
        except Exception as e:
            results.append(("GET /api/contacts/{id}", False, str(e)))
    else:
        results.append(("GET /api/contacts/{id}", False, "нет id"))
    if lead_id:
        try:
            d = get(f"/api/leads/{lead_id}/notes?limit=5")
            notes = d.get("_embedded", {}).get("notes", [])
            results.append(("GET /api/leads/{id}/notes", True, f"примечаний: {len(notes)}"))
        except Exception as e:
            results.append(("GET /api/leads/{id}/notes", False, str(e)))
    else:
        results.append(("GET /api/leads/{id}/notes", False, "нет lead_id"))
    try:
        d = get("/api/catalogs")
        n = len(d.get("_embedded", {}).get("catalogs", []))
        results.append(("GET /api/catalogs", True, f"каталогов: {n}"))
    except Exception as e:
        results.append(("GET /api/catalogs", False, str(e)))
    return results


def main():
    ap = argparse.ArgumentParser(description="Проверка read-only API amoCRM")
    ap.add_argument("--base-url", default="", help="Если задан — проверка через HTTP (иначе через client)")
    args = ap.parse_args()
    if args.base_url:
        results = check_via_http(args.base_url)
    else:
        results = check_via_client()
    ok = sum(1 for _, passed, _ in results if passed)
    total = len(results)
    for name, passed, msg in results:
        status = "OK" if passed else "FAIL"
        print(f"  [{status}] {name} — {msg}")
    print()
    if ok == total:
        print(f"Проверки чтения: {ok}/{total} пройдены.")
        return 0
    print(f"Проверки чтения: {ok}/{total} пройдены, {total - ok} неудач.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
