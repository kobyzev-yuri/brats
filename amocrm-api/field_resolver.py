"""
Определение ID полей контакта и сделки (телефон, email и др.) из AmoCRM custom_fields
с подстановкой по code/name и запасным вариантом из переменных окружения.
"""
import os
from typing import Any, Dict, List, Optional

from client import AmoCRMClient


# Коды и подстроки названий для сопоставления полей
PHONE_CODES = ("PHONE", "phone", "PHONES")
PHONE_NAMES = ("телефон", "phone", "source phone", "раб. тел.", "моб", "тел.")
EMAIL_CODES = ("EMAIL", "email", "EMAILS", "WORK_EMAIL")
EMAIL_NAMES = ("email", "почт", "e-mail", "mail", "раб", "рабочий")


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _match_field(field: dict, codes: tuple, names: tuple) -> bool:
    code = _normalize(field.get("code") or "")
    name = _normalize(field.get("name") or "")
    if code and code in codes:
        return True
    if name and any(n in name for n in names):
        return True
    return False


def _find_field_id(fields: List[dict], codes: tuple, names: tuple) -> Optional[int]:
    for f in fields:
        if _match_field(f, codes, names):
            fid = f.get("id")
            if fid is not None:
                return int(fid)
    return None


def resolve_contact_lead_field_ids(client: AmoCRMClient) -> Dict[str, Optional[int]]:
    """
    Возвращает словарь: contact_phone_id, contact_email_id, lead_phone_id, lead_email_id.
    Сначала проверяются переменные окружения (AMOCRM_CONTACT_PHONE_FIELD_ID и т.д.),
    затем подбор по custom_fields из AmoCRM по code/name.
    """
    result = {
        "contact_phone_id": None,
        "contact_email_id": None,
        "lead_phone_id": None,
        "lead_email_id": None,
    }

    def env_int(name: str) -> Optional[int]:
        v = os.getenv(name)
        if v and str(v).strip().isdigit():
            return int(str(v).strip())
        return None

    result["contact_phone_id"] = env_int("AMOCRM_CONTACT_PHONE_FIELD_ID")
    result["contact_email_id"] = env_int("AMOCRM_CONTACT_EMAIL_FIELD_ID")
    result["lead_phone_id"] = env_int("AMOCRM_LEAD_PHONE_FIELD_ID")
    result["lead_email_id"] = env_int("AMOCRM_LEAD_EMAIL_FIELD_ID")

    try:
        lead_cf = client.get_lead_custom_fields()
        contact_cf = client.get_contact_custom_fields()
    except Exception:
        return result

    lead_fields = (lead_cf.get("_embedded") or {}).get("custom_fields") or []
    contact_fields = (contact_cf.get("_embedded") or {}).get("custom_fields") or []

    if result["contact_phone_id"] is None:
        result["contact_phone_id"] = _find_field_id(contact_fields, PHONE_CODES, PHONE_NAMES)
    if result["contact_email_id"] is None:
        result["contact_email_id"] = _find_field_id(contact_fields, EMAIL_CODES, EMAIL_NAMES)
    if result["lead_phone_id"] is None:
        result["lead_phone_id"] = _find_field_id(lead_fields, PHONE_CODES, PHONE_NAMES)
    if result["lead_email_id"] is None:
        result["lead_email_id"] = _find_field_id(lead_fields, EMAIL_CODES, EMAIL_NAMES)

    return result


def build_contact_custom_values(
    field_ids: Dict[str, Optional[int]],
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Формирует custom_fields_values для контакта (телефон, email)."""
    out = []
    if phone and field_ids.get("contact_phone_id"):
        out.append({
            "field_id": field_ids["contact_phone_id"],
            "values": [{"value": phone.strip(), "enum_code": "WORK"}],
        })
    if email and field_ids.get("contact_email_id"):
        out.append({
            "field_id": field_ids["contact_email_id"],
            "values": [{"value": email.strip()}],
        })
    return out


def build_lead_custom_values(
    field_ids: Dict[str, Optional[int]],
    phone: Optional[str] = None,
    email: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Формирует custom_fields_values для сделки (телефон, email)."""
    out = []
    if phone and field_ids.get("lead_phone_id"):
        out.append({
            "field_id": field_ids["lead_phone_id"],
            "values": [{"value": phone.strip()}],
        })
    if email and field_ids.get("lead_email_id"):
        out.append({
            "field_id": field_ids["lead_email_id"],
            "values": [{"value": email.strip()}],
        })
    return out


if __name__ == "__main__":
    """При запуске из корня репо: python amocrm-api/field_resolver.py — выводит подобранные ID полей."""
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        from dotenv import load_dotenv
        load_dotenv(repo_root / "config.env", override=True)
        load_dotenv(repo_root / ".env")
    except Exception:
        pass
    from client import AmoCRMClient

    print("Загрузка custom_fields из AmoCRM...")
    try:
        client = AmoCRMClient()
        ids = resolve_contact_lead_field_ids(client)
    except Exception as e:
        print("Ошибка:", e)
        print("Проверьте config.env: AMOCRM_SUBDOMAIN, AMOCRM_ACCESS_TOKEN (или REFRESH_TOKEN).")
        sys.exit(1)

    print("\nПодобранные ID полей (телефон, email):")
    for key, val in ids.items():
        print(f"  {key}: {val}")
    print("\nЭти id можно задать в config.env (AMOCRM_CONTACT_PHONE_FIELD_ID и т.д.).")
    print("Если id не заданы в config.env, amocrm-api при создании лида из чата использует эти значения автоматически.")
