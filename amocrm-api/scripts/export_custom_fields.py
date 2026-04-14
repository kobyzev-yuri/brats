#!/usr/bin/env python3
"""
Выгрузка ID и названий доп. полей сделок и контактов из AmoCRM.
Читает config.env из корня репо. Результат в консоль и опционально в файл.

Использование:
  cd /projects/brats && python amocrm-api/scripts/export_custom_fields.py
  python amocrm-api/scripts/export_custom_fields.py --out amocrm_fields.txt
"""
import json
import sys
from pathlib import Path

# корень репо для config.env и импорта client
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "amocrm-api"))

from client import AmoCRMClient


def _load_client():
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / "config.env", override=True)
    load_dotenv(REPO_ROOT / ".env")
    return AmoCRMClient()


def _format_fields(entities: list, title: str) -> str:
    lines = [f"\n=== {title} ===", "id\tname\ttype\tcode"]
    for f in entities:
        fid = f.get("id", "")
        name = (f.get("name") or "").replace("\t", " ")
        typ = (f.get("type") or "").replace("\t", " ")
        code = (f.get("code") or "").replace("\t", " ")
        lines.append(f"{fid}\t{name}\t{typ}\t{code}")
    return "\n".join(lines)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Выгрузка доп. полей сделок и контактов AmoCRM")
    p.add_argument("--out", "-o", help="Путь к файлу для сохранения вывода")
    p.add_argument("--json", action="store_true", help="Вывести сырой JSON (сделки и контакты)")
    args = p.parse_args()

    try:
        client = _load_client()
    except Exception as e:
        print("Ошибка инициализации клиента (проверьте config.env и AMOCRM_*):", e, file=sys.stderr)
        sys.exit(1)

    out_lines = []
    try:
        lead_data = client.get_lead_custom_fields()
        contact_data = client.get_contact_custom_fields()
    except Exception as e:
        print("Ошибка запроса к AmoCRM:", e, file=sys.stderr)
        sys.exit(2)

    leads_embedded = (lead_data.get("_embedded") or {}).get("custom_fields") or []
    contacts_embedded = (contact_data.get("_embedded") or {}).get("custom_fields") or []

    if args.json:
        text = json.dumps(
            {"leads": lead_data, "contacts": contact_data},
            ensure_ascii=False,
            indent=2,
        )
    else:
        text = _format_fields(leads_embedded, "Сделки (лиды) — AMOCRM_LEAD_PHONE_FIELD_ID")
        text += _format_fields(contacts_embedded, "Контакты — AMOCRM_CONTACT_PHONE_FIELD_ID")
        text += "\n"

    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Сохранено в {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
