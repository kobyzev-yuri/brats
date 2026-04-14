"""
FastAPI-сервис для доступа к amoCRM (чтение + создание тестовых лидов).
Использует те же токены, что и n8n (config.env / .env).
Директория amocrm-api — отдельная для разработки и тестирования интеграции с amoCRM.
"""
from pathlib import Path
import sys
from typing import Any, List, Optional  # noqa: F401 used in Optional[]

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Корень amocrm-api
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from client import AmoCRMClient
from field_resolver import resolve_contact_lead_field_ids, build_lead_custom_values
from db import (
    insert_conversation_from_chat,
    get_or_create_conversation_by_external,
    get_conversation_by_external,
    update_conversation_lead,
    append_message,
    append_messages_bulk,
    get_conversation_by_id,
    get_messages,
    update_conversation_state,
    update_conversation_slots,
    ensure_lk_user_for_contact,
    get_lk_user_by_login,
    create_lk_session,
    get_lk_user_id_by_token,
    get_lk_user_by_id,
    get_conversation_id_by_user_id,
    get_or_link_conversation_for_lk_user,
    insert_lk_attachment,
    get_lk_attachments,
    get_lk_attachment_content,
)
from db import _lk_hash

app = FastAPI(
    title="amoCRM Integration API",
    description="Чтение данных amoCRM и создание тестовых лидов. См. docs/AMOCRM_INTEGRATION_PLAN.md",
    version="0.1.0",
)

# Страницы личного кабинета (вход и чат) — раздаём из site-integration/lk
_lk_dir = _repo_root / "site-integration" / "lk"
if _lk_dir.is_dir():
    app.mount("/lk", StaticFiles(directory=str(_lk_dir), html=True), name="lk")

# Глобальный клиент (инициализация при первом запросе)
_client: Optional[AmoCRMClient] = None


def get_client() -> AmoCRMClient:
    global _client
    if _client is None:
        _client = AmoCRMClient()
        if not _client.subdomain or not _client._access_token:
            raise HTTPException(
                status_code=503,
                detail="amoCRM не настроен: задайте AMOCRM_SUBDOMAIN и AMOCRM_ACCESS_TOKEN в config.env в корне репозитория (или в .env в amocrm-api). Перезапустите amocrm-api после изменения.",
            )
    return _client


# --- Модели ---


class CreateTestLeadRequest(BaseModel):
    """Создание тестового лида (префикс [BRATS-TEST] и тег brats_test добавляются автоматически)."""
    name: str
    price: int = 0


class CreateTestLeadFromChatRequest(BaseModel):
    """Создание тестового лида и контакта из чата (контактные данные оставлены в диалоге)."""
    phone: str
    name: Optional[str] = None
    client_name: Optional[str] = None  # дубль имени на случай если name обрезается при передаче
    note: Optional[str] = None
    email: Optional[str] = None
    channel: Optional[str] = None  # для записи в conversations.channel, по умолчанию 'website'
    external_id: Optional[str] = None  # visitor_id с сайта — если передан и у диалога уже есть лид, новый не создаём


class UpdateLeadStatusRequest(BaseModel):
    """Перевод сделки на указанный этап воронки (КП отправлена, договор отправлен и т.д.)."""
    status_id: int


# --- Эндпоинты: чтение ---


@app.get("/api/leads", summary="Список лидов")
def list_leads(
    limit: int = Query(50, ge=1, le=250),
    page: int = Query(1, ge=1),
    query: Optional[str] = None,
) -> Any:
    """Чтение лидов из amoCRM."""
    try:
        data = get_client().get_leads(limit=limit, page=page, query=query)
        return data
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/leads/custom_fields", summary="Доп. поля сделок (ID и названия)")
def get_lead_custom_fields() -> Any:
    """Выгрузка всех кастомных полей сделок (лидов) — id, name, type, code. Нужно для AMOCRM_LEAD_PHONE_FIELD_ID."""
    return get_client().get_lead_custom_fields()


@app.get("/api/leads/{lead_id}", summary="Один лид")
def get_lead(lead_id: int) -> Any:
    """Получить лид по ID."""
    try:
        return get_client().get_lead(lead_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


def _closed_success_status_id() -> int:
    """ID этапа «Успешно реализовано» для закрытия сделки (воронка «Работы маркетинг»: 142)."""
    import os
    v = os.getenv("AMOCRM_CLOSED_SUCCESS_STATUS_ID")
    return int(v) if v and str(v).isdigit() else 142


@app.patch("/api/leads/{lead_id}/status", summary="Перевести сделку на этап воронки")
def update_lead_status(lead_id: int, body: UpdateLeadStatusRequest) -> Any:
    """
    Обновляет этап сделки на указанный status_id (КП отправлена, договор/документы отправлены и т.д.).
    Вызывается funnel-api при создании КП и при подготовке письма с договором (если заданы
    AMOCRM_STATUS_KP_SENT и AMOCRM_STATUS_CONTRACT_SENT в config.env).
    """
    try:
        lead = get_client().update_lead(lead_id, status_id=body.status_id)
        return {"lead_id": lead_id, "status_id": body.status_id, "lead": lead}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/leads/{lead_id}/close", summary="Закрыть сделку (перевести в успешный этап)")
def close_lead(
    lead_id: int,
    status_id: Optional[int] = Query(None, description="ID этапа воронки (по умолчанию — успешно реализовано)"),
) -> Any:
    """
    Обновляет статус сделки на «Успешно реализовано» (или переданный status_id).
    Вызывать из n8n после отправки договора по email и подтверждения клиентом.
    """
    sid = status_id if status_id is not None else _closed_success_status_id()
    try:
        lead = get_client().update_lead(lead_id, status_id=sid)
        return {"lead_id": lead_id, "status_id": sid, "lead": lead}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/contacts", summary="Список контактов")
def list_contacts(
    limit: int = Query(50, ge=1, le=250),
    page: int = Query(1, ge=1),
    query: Optional[str] = None,
) -> Any:
    """Чтение контактов из amoCRM."""
    try:
        return get_client().get_contacts(limit=limit, page=page, query=query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/contacts/custom_fields", summary="Доп. поля контактов (ID и названия)")
def get_contact_custom_fields() -> Any:
    """Выгрузка всех кастомных полей контактов — id, name, type, code. Нужно для AMOCRM_CONTACT_PHONE_FIELD_ID."""
    return get_client().get_contact_custom_fields()


@app.get("/api/contacts/{contact_id}", summary="Один контакт")
def get_contact(contact_id: int) -> Any:
    try:
        return get_client().get_contact(contact_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/pipelines", summary="Воронки и статусы")
def list_pipelines() -> Any:
    """Список воронок продаж и их статусов."""
    try:
        return get_client().get_pipelines()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/leads/{lead_id}/notes", summary="Примечания к сделке")
def get_lead_notes(
    lead_id: int,
    limit: int = Query(50, ge=1, le=250),
    page: int = Query(1, ge=1),
) -> Any:
    try:
        return get_client().get_lead_notes(lead_id, limit=limit, page=page)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/catalogs", summary="Каталоги")
def list_catalogs() -> Any:
    try:
        return get_client().get_catalogs()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- Эндпоинты: тестовые лиды (соглашение AMOCRM_TEST_OBJECTS.md) ---


TEST_PREFIX = "[BRATS-TEST]"
TEST_TAG = "brats_test"


@app.post("/api/test-leads", summary="Создать тестовый лид")
def create_test_lead(body: CreateTestLeadRequest) -> Any:
    """
    Создаёт лид с префиксом [BRATS-TEST] и тегом brats_test.
    Используйте для отладки. Удаление — см. docs/AMOCRM_TEST_OBJECTS.md.
    """
    name = body.name.strip()
    if not name.startswith(TEST_PREFIX):
        name = f"{TEST_PREFIX} {name}"
    try:
        data = get_client().create_lead(
            name=name,
            price=body.price,
            tags=[TEST_TAG],
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


def _test_pipeline_id() -> Optional[int]:
    import os
    v = os.getenv("AMOCRM_TEST_PIPELINE_ID")
    return int(v) if v and str(v).isdigit() else None


@app.post("/api/test-lead-from-chat", summary="Создать тестовый лид и контакт из чата")
def create_test_lead_from_chat(body: CreateTestLeadFromChatRequest) -> Any:
    """
    Создаёт контакт (имя + телефон) и тестовый лид с префиксом [BRATS-TEST], тегом brats_test.
    Если передан external_id (visitor_id с сайта) и у этого диалога уже есть лид — новый не создаём,
    возвращаем существующие lead_id и conversation_id (created: false).
    """
    phone = (body.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="phone обязателен")
    name = (body.name or body.client_name or "Клиент с сайта").strip() or "Клиент с сайта"
    if name in ("Заявка с сайта", "Заявка с", "Клиент с сайта", "Клиент") and (body.note or "").strip():
        import re
        note = (body.note or "").strip()
        m = re.search(r"Заявка с формы:\s*([^,]+),\s*тел\.", note)
        if m:
            name = m.group(1).strip() or name
        else:
            m = re.search(r"([А-Яа-яЁёA-Za-z]+\s+[А-Яа-яЁёA-Za-z]+)", note)
            if m:
                name = m.group(1).strip()
    channel = (body.channel or "website").strip() or "website"
    note_text = (body.note or "").strip() or "Контакт передан в чате."
    external_id = (body.external_id or "").strip() or None

    if external_id:
        row = get_conversation_by_external(channel=channel, external_id=external_id)
        if row:
            cid, existing_lead_id, existing_contact_id = row
            if existing_lead_id is not None:
                # Обновляем контакт и сделку в AmoCRM под новые имя/телефон/email (повторная заявка того же посетителя)
                lead_name = f"{TEST_PREFIX} {name}"
                try:
                    client = get_client()
                    field_ids = resolve_contact_lead_field_ids(client)
                    if existing_contact_id:
                        client.update_contact(
                            existing_contact_id,
                            first_name=name,
                            last_name="",
                            phone=phone,
                            phone_field_id=field_ids.get("contact_phone_id"),
                            email=email,
                            email_field_id=field_ids.get("contact_email_id"),
                        )
                    lead_cf = build_lead_custom_values(field_ids, phone=phone, email=email)
                    client.update_lead(
                        existing_lead_id,
                        name=lead_name,
                        custom_fields_values=lead_cf if lead_cf else None,
                    )
                    if note_text:
                        client.add_lead_note(
                            existing_lead_id,
                            "common",
                            f"Обновление из чата: {note_text}",
                        )
                    update_conversation_lead(
                        conversation_id=cid,
                        lead_id=existing_lead_id,
                        contact_id=existing_contact_id,
                        slots={
                            "phone": phone,
                            "client_name": name,
                            "note_preview": (note_text[:200] + "…") if len(note_text) > 200 else note_text,
                        },
                    )
                    ensure_lk_user_for_contact(
                        conversation_id=cid,
                        phone=phone,
                        email=(body.email or "").strip() or None,
                        name=name,
                    )
                except Exception:
                    pass  # ответ всё равно вернём с существующими id
                login = (body.email or "").strip() if (body.email or "").strip() else phone
                return {
                    "lead_id": existing_lead_id,
                    "contact_id": existing_contact_id,
                    "conversation_id": cid,
                    "created": False,
                    "message": "Лид уже создан для этого посетителя; контакт и сделка обновлены по новой заявке",
                    "lk_login": login,
                    "lk_password_hint": "пароль: ваш номер телефона (как в заявке)",
                }

    email = (body.email or "").strip() or None
    lead_name = f"{TEST_PREFIX} {name}"
    contact_first = (name.split()[0] if name.strip() else "Клиент")
    contact_last = (" ".join(name.split()[1:]) if len(name.split()) > 1 else "")
    try:
        client = get_client()
        field_ids = resolve_contact_lead_field_ids(client)
        contact = client.create_contact(
            first_name=name,
            last_name="",
            phone=phone,
            phone_field_id=field_ids.get("contact_phone_id"),
            email=email,
            email_field_id=field_ids.get("contact_email_id"),
        )
        contact_id = contact.get("id")
        pipeline_id = _test_pipeline_id()
        lead_cf = build_lead_custom_values(field_ids, phone=phone, email=email)
        lead = client.create_lead(
            name=lead_name,
            price=0,
            pipeline_id=pipeline_id,
            tags=[TEST_TAG],
            contact_ids=[contact_id] if contact_id else None,
            custom_fields_values=lead_cf if lead_cf else None,
        )
        lead_id = lead.get("id")
        if lead_id and note_text:
            client.add_lead_note(lead_id, "common", note_text)
        conversation_id = None
        try:
            if external_id:
                cid, _ = get_or_create_conversation_by_external(channel=channel, external_id=external_id)
                if cid:
                    update_conversation_lead(
                        conversation_id=cid,
                        lead_id=lead_id,
                        contact_id=contact_id,
                        slots={"phone": phone, "client_name": name, "note_preview": (note_text[:200] + "…") if len(note_text) > 200 else note_text},
                    )
                    conversation_id = cid
            if conversation_id is None:
                conversation_id = insert_conversation_from_chat(
                    lead_id=lead_id,
                    contact_id=contact_id,
                    channel=channel,
                    phone=phone,
                    name=name,
                    email=(body.email or "").strip() or None,
                    note=note_text,
                )
            if conversation_id:
                ensure_lk_user_for_contact(
                    conversation_id=conversation_id,
                    phone=phone,
                    email=(body.email or "").strip() or None,
                    name=name,
                )
        except Exception:
            pass
        login = (body.email or "").strip() if (body.email or "").strip() else phone
        return {
            "lead_id": lead_id,
            "contact_id": contact_id,
            "conversation_id": conversation_id,
            "created": True,
            "lead_name": lead_name,
            "contact_first_name": contact_first,
            "contact_last_name": contact_last,
            "phone": phone,
            "lk_login": login,
            "lk_password_hint": "пароль: ваш номер телефона (как в заявке)",
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- Память диалога (conversations + messages в PostgreSQL) ---


@app.get("/api/conversation/resolve", summary="Получить или создать диалог по сессии чата")
def resolve_conversation(
    channel: str = Query("website", description="Канал: website, telegram, avito, ..."),
    external_id: Optional[str] = Query(None, description="ID сессии/пользователя чата"),
) -> Any:
    """
    По channel + external_id находит или создаёт запись в conversations и возвращает
    conversation_id, последние сообщения и слоты (имя, телефон, email и др.) для контекста LLM.
    Вызывать из n8n в начале обработки. В системный промпт подставлять slots.client_name и slots.phone,
    чтобы агент не переспрашивал имя и контакты.
    """
    if not (external_id or "").strip():
        return {"conversation_id": None, "messages": [], "slots": {}}
    cid, messages = get_or_create_conversation_by_external(
        channel=(channel or "website").strip() or "website",
        external_id=external_id,
    )
    slots = {}
    state = None
    if cid:
        conv = get_conversation_by_id(cid)
        if conv:
            slots = conv.get("slots") or {}
            state = conv.get("state")
    return {"conversation_id": cid, "messages": messages, "slots": slots, "state": state}


class AppendMessageRequest(BaseModel):
    role: str = "user"  # user | assistant | system
    content: str = ""


class AppendMessagesBulkRequest(BaseModel):
    messages: List[dict]  # [{role, content}, ...]


@app.post("/api/conversation/{conversation_id}/messages", summary="Добавить сообщение в диалог")
def append_conversation_message(conversation_id: int, body: AppendMessageRequest) -> Any:
    """Добавляет одно сообщение (user или assistant). Вызывать из n8n после ответа бота."""
    ok = append_message(conversation_id, body.role, body.content)
    if not ok:
        raise HTTPException(status_code=400, detail="Не удалось сохранить сообщение")
    return {"saved": True, "conversation_id": conversation_id}


@app.post("/api/conversation/{conversation_id}/messages/bulk", summary="Добавить несколько сообщений")
def append_conversation_messages_bulk(conversation_id: int, body: AppendMessagesBulkRequest) -> Any:
    """Добавляет список сообщений (например user + assistant за один ответ)."""
    count = append_messages_bulk(conversation_id, body.messages or [])
    return {"saved": count, "conversation_id": conversation_id}


# --- Личный кабинет (ЛК): вход и текущий пользователь ---

import hashlib
import secrets
from datetime import datetime, timedelta

class LkLoginRequest(BaseModel):
    """Вход в ЛК: логин (email или телефон), пароль (номер телефона)."""
    login: str
    password: str


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@app.post("/api/lk/login", summary="Вход в личный кабинет")
def lk_login(body: LkLoginRequest) -> Any:
    """
    Логин = email или телефон (как при записи на просмотр).
    Пароль = номер телефона. Возвращает token для заголовка Authorization: Bearer <token>.
    """
    login = (body.login or "").strip()
    password = (body.password or "").strip()
    if not login or not password:
        raise HTTPException(status_code=400, detail="Укажите логин и пароль")
    row = get_lk_user_by_login(login)
    if not row:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    user_id, phone, stored_hash, email, name = row[0], row[1], row[2], row[3], row[4]
    if _lk_hash(password) != stored_hash:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=30)
    create_lk_session(user_id, _token_hash(token), expires_at)
    user = get_lk_user_by_id(user_id)
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    return {
        "token": token,
        "expires_in_days": 30,
        "user": user,
        "conversation_id": conversation_id,
    }


def _lk_user_from_token(authorization: Optional[str] = None) -> Optional[int]:
    """Из заголовка Authorization: Bearer <token> возвращает user_id или None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    return get_lk_user_id_by_token(_token_hash(token))


@app.get("/api/lk/me", summary="Текущий пользователь ЛК (по токену)")
def lk_me(authorization: Optional[str] = Header(None, alias="Authorization")) -> Any:
    """Заголовок: Authorization: Bearer <token>. Возвращает user и conversation_id для чата."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    user = get_lk_user_by_id(user_id)
    conversation_id = get_conversation_id_by_user_id(user_id)
    return {"user": user, "conversation_id": conversation_id}


@app.get("/api/lk/conversation", summary="Диалог и сообщения для чата в ЛК")
def lk_conversation(authorization: Optional[str] = Header(None, alias="Authorization")) -> Any:
    """Заголовок: Authorization: Bearer <token>. Возвращает диалог и историю сообщений."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден. Обратитесь в поддержку.")
    conv = get_conversation_by_id(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    conv["messages"] = get_messages(conversation_id, limit=200)
    return conv


@app.get("/api/lk/deal", summary="Статус сделки для ЛК")
def lk_deal(authorization: Optional[str] = Header(None, alias="Authorization")) -> Any:
    """Возвращает данные по сделке из amoCRM (название, этап воронки, статус), если у диалога есть amocrm_lead_id."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        return {"deal": None, "message": "Диалог не найден"}
    conv = get_conversation_by_id(conversation_id)
    lead_id = (conv or {}).get("amocrm_lead_id")
    if not lead_id:
        return {"deal": None, "message": "Сделка ещё не создана"}
    try:
        client = get_client()
        lead = client.get_lead(lead_id)
        pipelines = client.get_pipelines()
        status_name = None
        pipeline_name = None
        for pipe in (pipelines.get("_embedded") or {}).get("pipelines") or []:
            if pipe.get("id") == lead.get("pipeline_id"):
                pipeline_name = pipe.get("name")
                for st in pipe.get("statuses") or []:
                    if st.get("id") == lead.get("status_id"):
                        status_name = st.get("name")
                        break
                break
        return {
            "deal": {
                "lead_id": lead_id,
                "name": lead.get("name"),
                "price": lead.get("price"),
                "status_id": lead.get("status_id"),
                "status_name": status_name or "—",
                "pipeline_name": pipeline_name or "—",
            }
        }
    except Exception as e:
        return {"deal": None, "message": str(e)}


@app.get("/api/lk/slots", summary="Данные для сделки (слоты)")
def lk_slots_get(authorization: Optional[str] = Header(None, alias="Authorization")) -> Any:
    """Возвращает слоты диалога (данные для шаблонов КП/договора): имя, паспорт, объект и т.д."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    conv = get_conversation_by_id(conversation_id)
    return {"slots": (conv or {}).get("slots") or {}}


class LkSlotsUpdateRequest(BaseModel):
    """Обновление слотов (частичное). Любые строковые ключи — для шаблонов КП/договора."""
    model_config = {"extra": "allow"}

    client_name: Optional[str] = None
    name: Optional[str] = None
    passport: Optional[str] = None
    client_passport: Optional[str] = None
    object_address: Optional[str] = None
    object_name: Optional[str] = None
    object_description: Optional[str] = None
    budget: Optional[str] = None
    price: Optional[str] = None
    area_total: Optional[str] = None
    area: Optional[str] = None
    seller_name: Optional[str] = None
    seller_basis: Optional[str] = None
    city: Optional[str] = None
    settlement: Optional[str] = None
    lot_number: Optional[str] = None
    price_words: Optional[str] = None


@app.patch("/api/lk/slots", summary="Сохранить данные для сделки")
def lk_slots_patch(
    body: LkSlotsUpdateRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Any:
    """Обновляет слоты диалога (данные для шаблонов). Передайте только те поля, которые нужно изменить."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    raw = body.model_dump(exclude_none=True)
    slots_update = {}
    for k, v in raw.items():
        if v is not None and (not isinstance(v, str) or v.strip()):
            slots_update[k] = v.strip() if isinstance(v, str) else v
    if not slots_update:
        return {"updated": True, "message": "Нечего обновлять"}
    ok = update_conversation_slots(conversation_id, slots_update)
    return {"updated": ok}


class LkSendMessageRequest(BaseModel):
    content: str


@app.post("/api/lk/send", summary="Отправить сообщение агенту из ЛК")
def lk_send(
    body: LkSendMessageRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Any:
    """
    Добавляет сообщение пользователя в диалог и отправляет запрос в n8n (агент).
    Возвращает ответ агента. Требуется N8N_WEBHOOK_URL в config.env.
    """
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым")
    append_message(conversation_id, "user", content)
    import os
    webhook_url = (os.getenv("N8N_WEBHOOK_URL") or "").strip()
    if not webhook_url or "/webhook/" not in webhook_url:
        base = (os.getenv("N8N_URL") or "http://localhost:5678").strip().rstrip("/")
        webhook_url = f"{base}/webhook/sales-agent-kb"
    try:
        import httpx
        r = httpx.post(
            webhook_url,
            json={"message": content, "conversation_id": conversation_id, "channel": "lk"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        reply = (data.get("response") or data.get("agent_response") or data.get("reply") or "").strip()
        if reply:
            append_message(conversation_id, "assistant", reply)
        return {"saved": True, "response": reply or "Ответ не получен."}
    except Exception as e:
        return {"saved": True, "response": f"Сообщение сохранено. Ошибка при запросе к агенту: {e}"}


def _funnel_base() -> str:
    import os
    return (os.getenv("FUNNEL_API_BASE_URL") or "http://localhost:8011").rstrip("/")


@app.get("/api/lk/documents", summary="Список прикреплённых документов (КП и договор) для ЛК")
def lk_documents(authorization: Optional[str] = Header(None, alias="Authorization")) -> Any:
    """Возвращает список документов по диалогу пользователя: КП из funnel-api и пункт «Договор» (для просмотра в ЛК без email)."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    docs = []
    try:
        conversation_id = get_or_link_conversation_for_lk_user(user_id)
        if not conversation_id:
            return {"documents": []}
        import httpx
        base = _funnel_base()
        r = httpx.get(f"{base}/api/proposals", params={"conversation_id": conversation_id}, timeout=10)
        if r.is_success:
            data = r.json()
            for p in (data.get("proposals") or []):
                docs.append({
                    "type": "proposal",
                    "id": p.get("id"),
                    "name": f"КП от {(p.get('created_at') or '')[:10]}",
                    "created_at": p.get("created_at"),
                })
    except Exception:
        pass
    docs.append({"type": "contract", "name": "Договор"})
    return {"documents": docs}


@app.get("/api/lk/documents/proposal/{proposal_id}", summary="Получить один КП для просмотра в ЛК")
def lk_document_proposal(
    proposal_id: int,
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Any:
    """Проверяет, что КП принадлежит диалогу пользователя, возвращает content_text из funnel-api."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    import httpx
    base = _funnel_base()
    r = httpx.get(f"{base}/api/proposals", params={"conversation_id": conversation_id}, timeout=10)
    if not r.is_success:
        raise HTTPException(status_code=502, detail="Не удалось получить список КП")
    ids = [p["id"] for p in (r.json().get("proposals") or [])]
    if proposal_id not in ids:
        raise HTTPException(status_code=404, detail="КП не найден или доступ запрещён")
    r2 = httpx.get(f"{base}/api/proposals/{proposal_id}", timeout=10)
    if not r2.is_success:
        raise HTTPException(status_code=r2.status_code, detail=r2.text or "Ошибка funnel-api")
    return r2.json()


@app.get("/api/lk/documents/contract", summary="Превью договора для просмотра в ЛК")
def lk_document_contract(authorization: Optional[str] = Header(None, alias="Authorization")) -> Any:
    """Возвращает тело договора с подстановкой из слотов (для отображения в ЛК без высылки на email)."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    import httpx
    base = _funnel_base()
    r = httpx.get(f"{base}/api/contracts/preview", params={"conversation_id": conversation_id}, timeout=10)
    if not r.is_success:
        raise HTTPException(status_code=r.status_code, detail=r.text or "Ошибка funnel-api")
    return r.json()


@app.get("/api/lk/documents/uploaded", summary="Список загруженных клиентом документов")
def lk_documents_uploaded(authorization: Optional[str] = Header(None, alias="Authorization")) -> Any:
    """Список файлов, загруженных клиентом в ЛК (паспорт, СНИЛС и т.д.)."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        return {"uploaded": []}
    return {"uploaded": get_lk_attachments(conversation_id)}


@app.post("/api/lk/documents/upload", summary="Загрузить документ (скан паспорта и т.д.)")
async def lk_documents_upload(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    file: UploadFile = File(...),
) -> Any:
    """Принимает файл (multipart/form-data), сохраняет и привязывает к диалогу. Макс. размер — 10 МБ."""
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    MAX_SIZE = 10 * 1024 * 1024
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 10 МБ)")
    filename = (file.filename or "document").strip() or "document"
    content_type = file.content_type or "application/octet-stream"
    aid = insert_lk_attachment(conversation_id, filename, content_type, data)
    if not aid:
        raise HTTPException(status_code=500, detail="Не удалось сохранить файл")
    return {"id": aid, "filename": filename, "message": "Документ загружен"}


@app.get("/api/lk/documents/uploaded/{attachment_id}", summary="Скачать загруженный документ")
def lk_document_uploaded_get(
    attachment_id: int,
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Any:
    """Возвращает файл по id (проверяется принадлежность диалогу пользователя)."""
    from fastapi.responses import Response
    user_id = _lk_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход в личный кабинет")
    conversation_id = get_or_link_conversation_for_lk_user(user_id)
    if not conversation_id:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    content = get_lk_attachment_content(attachment_id, conversation_id)
    if not content:
        raise HTTPException(status_code=404, detail="Документ не найден")
    file_data, content_type, filename = content
    return Response(
        content=file_data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "amocrm-api"}
