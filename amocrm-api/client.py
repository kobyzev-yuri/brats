"""
Клиент amoCRM API v4 с автоматическим обновлением токена.
Использует те же переменные окружения, что и n8n (config.env / .env).
Директория amocrm-api — отдельная для разработки и тестирования интеграции с amoCRM.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

# Загрузка конфига: config.env из корня репо (приоритет), затем .env
_repo_root = Path(__file__).resolve().parent.parent  # amocrm-api -> родитель = корень репо
_config_env = Path(os.getenv("BRATS_CONFIG", "") or _repo_root / "config.env")
if _config_env.exists():
    load_dotenv(_config_env, override=True)
load_dotenv(_repo_root / ".env")
load_dotenv()  # .env в amocrm-api


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or default


class AmoCRMClient:
    """Клиент amoCRM с автообновлением access token."""

    def __init__(
        self,
        subdomain: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ):
        self.subdomain = subdomain or _env("AMOCRM_SUBDOMAIN")
        self.client_id = client_id or _env("AMOCRM_CLIENT_ID")
        self.client_secret = client_secret or _env("AMOCRM_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or _env("AMOCRM_REDIRECT_URI")
        self._access_token = access_token or _env("AMOCRM_ACCESS_TOKEN")
        self._refresh_token = refresh_token or _env("AMOCRM_REFRESH_TOKEN")
        expires_at_str = _env("AMOCRM_TOKEN_EXPIRES_AT")
        self._token_expires_at = token_expires_at
        if expires_at_str:
            try:
                self._token_expires_at = datetime.fromisoformat(
                    expires_at_str.replace("Z", "+00:00")
                )
            except Exception:
                pass
        self._base = f"https://{self.subdomain}.amocrm.ru" if self.subdomain else ""

    def _ensure_valid_token(self) -> None:
        if not self._access_token:
            raise ValueError(
                "AMOCRM_ACCESS_TOKEN не задан. Выполните OAuth2 авторизацию (см. docs/AMOCRM_API_SETUP.md)."
            )
        if self._token_expires_at and datetime.now() >= self._token_expires_at - timedelta(
            minutes=5
        ):
            self._refresh()

    def _refresh(self) -> None:
        if not self._refresh_token:
            raise ValueError(
                "AMOCRM_REFRESH_TOKEN не задан. Переавторизуйтесь в amoCRM."
            )
        url = f"{self._base}/oauth2/access_token"
        with httpx.Client() as client:
            r = client.post(
                url,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "redirect_uri": self.redirect_uri,
                },
            )
            r.raise_for_status()
            data = r.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        expires_in = data.get("expires_in", 86400)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[Any] = None,
    ) -> dict:
        self._ensure_valid_token()
        url = f"{self._base}/api/v4/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        with httpx.Client() as client:
            r = client.request(
                method, url, headers=headers, params=params, json=json, timeout=30
            )
            if r.status_code == 401:
                self._refresh()
                headers["Authorization"] = f"Bearer {self._access_token}"
                r = client.request(
                    method, url, headers=headers, params=params, json=json, timeout=30
                )
            r.raise_for_status()
            if r.status_code == 204:
                return {}
            return r.json()

    # --- Чтение (без ограничений по бизнес-плану) ---

    def get_leads(
        self,
        limit: int = 50,
        page: int = 1,
        with_: Optional[list] = None,
        query: Optional[str] = None,
        pipeline_ids: Optional[list] = None,
    ) -> dict:
        params = {"limit": min(limit, 250), "page": page}
        if with_:
            params["with"] = ",".join(with_)
        if query:
            params["query"] = query
        # Фильтр по воронкам: filter[pipeline_id][]=id1&filter[pipeline_id][]=id2
        if pipeline_ids:
            params["filter[pipeline_id][]"] = pipeline_ids
        return self._request("GET", "leads", params=params)

    def get_lead(self, lead_id: int) -> dict:
        return self._request("GET", f"leads/{lead_id}")

    def get_contacts(
        self,
        limit: int = 50,
        page: int = 1,
        query: Optional[str] = None,
    ) -> dict:
        params = {"limit": min(limit, 250), "page": page}
        if query:
            params["query"] = query
        return self._request("GET", "contacts", params=params)

    def get_contact(self, contact_id: int) -> dict:
        return self._request("GET", f"contacts/{contact_id}")

    def get_pipelines(self) -> dict:
        return self._request("GET", "leads/pipelines")

    def get_lead_notes(self, lead_id: int, limit: int = 50, page: int = 1) -> dict:
        return self._request(
            "GET", f"leads/{lead_id}/notes", params={"limit": limit, "page": page}
        )

    def get_catalogs(self) -> dict:
        return self._request("GET", "catalogs")

    def get_catalog_elements(self, catalog_id: int, limit: int = 250, page: int = 1) -> dict:
        return self._request(
            "GET",
            f"catalogs/{catalog_id}/elements",
            params={"limit": limit, "page": page},
        )

    def get_lead_custom_fields(self) -> dict:
        """Список доп. полей сделок (лидов). Ответ: _embedded.custom_fields с id, name, type, code."""
        return self._request("GET", "leads/custom_fields")

    def get_contact_custom_fields(self) -> dict:
        """Список доп. полей контактов. Ответ: _embedded.custom_fields с id, name, type, code."""
        return self._request("GET", "contacts/custom_fields")

    # --- Запись: только тестовые лиды по соглашению AMOCRM_TEST_OBJECTS.md ---

    def create_contact(
        self,
        first_name: str,
        last_name: str = "",
        phone: Optional[str] = None,
        phone_field_id: Optional[int] = None,
        email: Optional[str] = None,
        email_field_id: Optional[int] = None,
        custom_fields_values: Optional[list] = None,
    ) -> dict:
        """Создание контакта. Телефон/email — по field_id или через custom_fields_values (список {field_id, values})."""
        name = (first_name or "").strip() or "Клиент"
        body: dict = {
            "first_name": name.split()[0] if name else "Клиент",
            "last_name": " ".join(name.split()[1:]) if len(name.split()) > 1 else (last_name or ""),
        }
        cf = list(custom_fields_values) if custom_fields_values else []
        if phone and phone_field_id and not any(c["field_id"] == phone_field_id for c in cf):
            cf.append({
                "field_id": phone_field_id,
                "values": [{"value": phone.strip(), "enum_code": "WORK"}],
            })
        if email and email_field_id and not any(c["field_id"] == email_field_id for c in cf):
            cf.append({
                "field_id": email_field_id,
                "values": [{"value": email.strip()}],
            })
        if cf:
            body["custom_fields_values"] = cf
        resp = self._request("POST", "contacts", json=[body])
        emb = resp.get("_embedded", {})
        contacts = emb.get("contacts", [])
        if not contacts:
            raise ValueError("AmoCRM не вернул созданный контакт")
        return contacts[0]

    def update_contact(
        self,
        contact_id: int,
        first_name: str,
        last_name: str = "",
        phone: Optional[str] = None,
        phone_field_id: Optional[int] = None,
        email: Optional[str] = None,
        email_field_id: Optional[int] = None,
        custom_fields_values: Optional[list] = None,
    ) -> dict:
        """Обновление контакта (PATCH). Имя и телефон/email — как в create_contact."""
        name = (first_name or "").strip() or "Клиент"
        body: dict = {
            "id": contact_id,
            "first_name": name.split()[0] if name else "Клиент",
            "last_name": " ".join(name.split()[1:]) if len(name.split()) > 1 else (last_name or ""),
        }
        cf = list(custom_fields_values) if custom_fields_values else []
        if phone and phone_field_id and not any(c["field_id"] == phone_field_id for c in cf):
            cf.append({
                "field_id": phone_field_id,
                "values": [{"value": phone.strip(), "enum_code": "WORK"}],
            })
        if email is not None and email_field_id and not any(c["field_id"] == email_field_id for c in cf):
            cf.append({
                "field_id": email_field_id,
                "values": [{"value": (email or "").strip()}],
            })
        if cf:
            body["custom_fields_values"] = cf
        resp = self._request("PATCH", "contacts", json=[body])
        contacts = (resp.get("_embedded") or {}).get("contacts", [])
        if not contacts:
            raise ValueError("AmoCRM не вернул обновлённый контакт")
        return contacts[0]

    def create_lead(
        self,
        name: str,
        price: int = 0,
        pipeline_id: Optional[int] = None,
        status_id: Optional[int] = None,
        tags: Optional[list] = None,
        custom_fields_values: Optional[list] = None,
        contact_ids: Optional[list] = None,
    ) -> dict:
        """Создание лида. Для тестовых используйте префикс [BRATS-TEST] и тег brats_test. contact_ids — привязка контактов."""
        body: dict = {"name": name, "price": price}
        if pipeline_id is not None:
            body["pipeline_id"] = pipeline_id
        if status_id is not None:
            body["status_id"] = status_id
        if custom_fields_values:
            body["custom_fields_values"] = custom_fields_values
        if tags or contact_ids:
            body["_embedded"] = body.get("_embedded") or {}
            if tags:
                body["_embedded"]["tags"] = [{"name": t} for t in tags]
            if contact_ids:
                body["_embedded"]["contacts"] = [{"id": cid, "is_main": i == 0} for i, cid in enumerate(contact_ids)]
        resp = self._request("POST", "leads", json=[body])
        leads = (resp.get("_embedded") or {}).get("leads", [])
        if not leads:
            raise ValueError("AmoCRM не вернул созданный лид")
        return leads[0]

    def update_lead(self, lead_id: int, status_id: Optional[int] = None, **kwargs: Any) -> dict:
        """Обновить сделку (PATCH). status_id — переход в этап воронки (например 142 «Успешно реализовано»)."""
        payload: dict = {"id": lead_id}
        if status_id is not None:
            payload["status_id"] = status_id
        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v
        resp = self._request("PATCH", "leads", json=[payload])
        leads = (resp.get("_embedded") or {}).get("leads", [])
        if not leads:
            raise ValueError("AmoCRM не вернул обновлённый лид")
        return leads[0]

    def add_lead_note(self, lead_id: int, note_type: str, text: str) -> dict:
        """Добавить примечание к сделке. note_type: common, call, ..."""
        body = [{"entity_id": lead_id, "note_type": note_type, "params": {"text": text}}]
        return self._request("POST", "leads/notes", json=body)

    def delete_lead(self, lead_id: int) -> None:
        self._request("DELETE", f"leads/{lead_id}")
