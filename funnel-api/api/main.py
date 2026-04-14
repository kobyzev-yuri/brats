"""
funnel-api: календарь просмотров (9–18), КП, шаблоны договоров.
Работает с PostgreSQL: viewing_slots, proposals, document_templates.
См. docs/FUNNEL_CALENDAR_CP_CONTRACT.md.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db import get_conn, SLOT_START_HOUR, SLOT_END_HOUR, SLOT_DURATION_MINUTES


def _amocrm_move_lead_to_status(lead_id: int, status_id: int) -> bool:
    """Переводит сделку в AmoCRM на этап status_id. Возвращает True при успехе, False при ошибке/не настроено."""
    base = (os.getenv("AMOCRM_API_BASE_URL") or "").strip().rstrip("/")
    if not base or not lead_id or not status_id:
        return False
    url = f"{base}/api/leads/{lead_id}/status"
    try:
        r = httpx.patch(url, json={"status_id": status_id}, timeout=10.0)
        return r.status_code == 200
    except Exception:
        return False

app = FastAPI(
    title="Funnel API",
    description="Календарь просмотров (9–18), КП, шаблоны документов. PostgreSQL: viewing_slots, proposals, document_templates.",
    version="0.1.0",
)


# --- Модели ---

class BookSlotRequest(BaseModel):
    conversation_id: int
    slot_start: str  # ISO datetime
    slot_end: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    amocrm_lead_id: Optional[int] = None
    object_id: Optional[int] = None
    object_name: Optional[str] = None
    notes: Optional[str] = None


class CreateProposalRequest(BaseModel):
    """Создание КП: связь с диалогом/лидом, объекты, опционально шаблон для подстановки текста."""
    conversation_id: int
    amocrm_lead_id: Optional[int] = None
    product_ids: Optional[List[int]] = None
    template_id: Optional[int] = None


class PrepareContractEmailRequest(BaseModel):
    """Подготовка письма с договором: conversation_id и опционально template_id."""
    conversation_id: int
    template_id: Optional[int] = None
    to_email_override: Optional[str] = None  # если передан — использовать вместо slots.email


# --- Календарь: свободные слоты ---

@app.get("/api/viewing-slots/available", summary="Свободные слоты на просмотр (9–18)")
def list_available_slots(
    days: int = Query(7, ge=1, le=30, description="На сколько дней вперёд"),
    settlement_id: Optional[int] = Query(None),
    object_id: Optional[int] = Query(None),
) -> Any:
    """
    Возвращает слоты со статусом free в рабочем окне 9–18.
    Если слотов в БД нет — можно вызвать POST /api/viewing-slots/seed для создания на неделю.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days)
        cur.execute(
            """
            SELECT id, slot_start, slot_end, object_name, status
            FROM viewing_slots
            WHERE status = 'free'
              AND slot_start >= NOW()
              AND slot_start < %s
            ORDER BY slot_start
            """,
            (end_date,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "slots": [
                {
                    "id": r[0],
                    "slot_start": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
                    "slot_end": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
                    "object_name": r[3],
                    "status": r[4],
                }
                for r in rows
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/viewing-slots/book", summary="Записать клиента на просмотр")
def book_slot(body: BookSlotRequest) -> Any:
    """Создаёт или обновляет слот в viewing_slots со статусом booked, привязывает к conversation_id."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        slot_start = datetime.fromisoformat(body.slot_start.replace("Z", "+00:00"))
        slot_end = datetime.fromisoformat(body.slot_end.replace("Z", "+00:00"))
        cur.execute(
            """
            INSERT INTO viewing_slots (
                conversation_id, slot_start, slot_end, status,
                contact_name, contact_phone, amocrm_lead_id, object_id, object_name, notes
            ) VALUES (%s, %s, %s, 'booked', %s, %s, %s, %s, %s, %s)
            RETURNING id, slot_start, slot_end
            """,
            (
                body.conversation_id,
                slot_start,
                slot_end,
                body.contact_name,
                body.contact_phone,
                body.amocrm_lead_id,
                body.object_id,
                body.object_name,
                body.notes,
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if not row:
            raise HTTPException(status_code=500, detail="Не удалось создать запись")
        return {
            "id": row[0],
            "slot_start": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
            "slot_end": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
            "booked": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/viewing-slots/seed", summary="Создать свободные слоты на N дней (9–18)")
def seed_slots(
    days: int = Query(7, ge=1, le=30),
    settlement_id: Optional[int] = Query(None),
) -> Any:
    """Создаёт слоты по часу в окне 9–18 (только free). Один объект — много слотов по времени, повторы object_name нормальны."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        created = 0
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if start.hour >= SLOT_END_HOUR:
            start += timedelta(days=1)
        for d in range(days):
            day = start + timedelta(days=d)
            for hour in range(SLOT_START_HOUR, SLOT_END_HOUR):
                slot_start = day.replace(hour=hour, minute=0, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
                if slot_start < datetime.now():
                    continue
                cur.execute(
                    "SELECT 1 FROM viewing_slots WHERE slot_start = %s AND slot_end = %s LIMIT 1",
                    (slot_start, slot_end),
                )
                if cur.fetchone():
                    continue
                cur.execute(
                    """
                    INSERT INTO viewing_slots (settlement_id, slot_start, slot_end, status)
                    VALUES (%s, %s, %s, 'free')
                    """,
                    (settlement_id, slot_start, slot_end),
                )
                created += 1
        conn.commit()
        cur.close()
        conn.close()
        return {"created": created, "message": f"Добавлено слотов: {created}"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- Шаблоны документов (КП, договор) ---

@app.get("/api/document-templates", summary="Список шаблонов КП и договоров")
def list_document_templates(
    type_filter: Optional[str] = Query(None, description="proposal | contract"),
) -> Any:
    """Возвращает активные шаблоны из document_templates."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        if type_filter and type_filter in ("proposal", "contract"):
            cur.execute(
                "SELECT id, type, name, LEFT(body, 200) as body_preview FROM document_templates WHERE is_active = true AND type = %s ORDER BY id",
                (type_filter,),
            )
        else:
            cur.execute(
                "SELECT id, type, name, LEFT(body, 200) as body_preview FROM document_templates WHERE is_active = true ORDER BY type, id",
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "templates": [
                {"id": r[0], "type": r[1], "name": r[2], "body_preview": (r[3] or "")[:200]}
                for r in rows
            ],
        }
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- КП ---

@app.post("/api/proposals", summary="Создать КП (черновик)")
def create_proposal(body: CreateProposalRequest) -> Any:
    """
    Создаёт КП в статусе draft. При указании template_id подставляет body шаблона в content_text.
    Возвращает id, status, created_at для подстановки ссылки/ответа клиенту.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        content_text = None
        if body.template_id:
            cur.execute(
                "SELECT body FROM document_templates WHERE id = %s AND type = 'proposal' AND is_active = true",
                (body.template_id,),
            )
            row = cur.fetchone()
            if row:
                content_text = row[0]
        product_ids_arr = body.product_ids if body.product_ids else None
        cur.execute(
            """
            INSERT INTO proposals (conversation_id, amocrm_lead_id, status, content_structured, content_text, product_ids)
            VALUES (%s, %s, 'draft', '{}', %s, %s)
            RETURNING id, status, created_at
            """,
            (body.conversation_id, body.amocrm_lead_id, content_text, product_ids_arr),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if not row:
            raise HTTPException(status_code=500, detail="Не удалось создать КП")
        # Продвижение сделки в AmoCRM: этап «КП отправлена»
        if body.amocrm_lead_id:
            kp_status = os.getenv("AMOCRM_STATUS_KP_SENT")
            if kp_status and str(kp_status).isdigit():
                _amocrm_move_lead_to_status(body.amocrm_lead_id, int(kp_status))
        return {
            "id": row[0],
            "status": row[1],
            "created_at": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
            "message": "КП создано. Отправьте клиенту ссылку или content_text (GET /api/proposals/{id} при реализации).",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/proposals/{proposal_id}", summary="Один КП (для выдачи ссылки/текста клиенту)")
def get_proposal(proposal_id: int) -> Any:
    """Возвращает КП по id: status, content_text, created_at (для подстановки в ответ клиенту)."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status, content_text, created_at FROM proposals WHERE id = %s",
            (proposal_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="КП не найдено")
        return {
            "id": row[0],
            "status": row[1],
            "content_text": row[2],
            "created_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/proposals", summary="Список КП по диалогу или лиду")
def list_proposals(
    conversation_id: Optional[int] = Query(None),
    amocrm_lead_id: Optional[int] = Query(None),
) -> Any:
    """Возвращает КП из таблицы proposals по conversation_id или amocrm_lead_id."""
    if not conversation_id and not amocrm_lead_id:
        raise HTTPException(status_code=400, detail="Укажите conversation_id или amocrm_lead_id")
    try:
        conn = get_conn()
        cur = conn.cursor()
        if conversation_id:
            cur.execute(
                "SELECT id, status, created_at FROM proposals WHERE conversation_id = %s ORDER BY created_at DESC",
                (conversation_id,),
            )
        else:
            cur.execute(
                "SELECT id, status, created_at FROM proposals WHERE amocrm_lead_id = %s ORDER BY created_at DESC",
                (amocrm_lead_id,),
            )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "proposals": [
                {"id": r[0], "status": r[1], "created_at": str(r[2]) if r[2] else None}
                for r in rows
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# --- Договор: подготовка письма для отправки по email ---

def _fill_template(text: str, slots: dict) -> str:
    """Подставляет в шаблон значения из slots. Поддерживает плейсхолдеры договора: city, date, seller_*, client_*, object_*, settlement, area_total, price, price_words и любые {{key}} из slots."""
    if not text:
        return ""
    from datetime import datetime
    out = text
    s = slots or {}
    # Алиасы: подстановка из слотов с резервными ключами
    def _v(*keys, default=""):
        for k in keys:
            if k in s and s[k] not in (None, ""):
                return str(s[k])
        return default
    # Дата по умолчанию — сегодня
    date_val = _v("date", default=datetime.now().strftime("%d.%m.%Y"))
    # Явный список плейсхолдеров договора (значения из slots или пусто)
    replacements = [
        ("client_name", _v("client_name", "name")),
        ("email", _v("email")),
        ("phone", _v("phone")),
        ("object_address", _v("object_address")),
        ("lot_number", _v("lot_number")),
        ("object_description", _v("object_description")),
        ("city", _v("city")),
        ("date", date_val),
        ("seller_name", _v("seller_name")),
        ("seller_basis", _v("seller_basis")),
        ("client_passport", _v("client_passport", "passport")),
        ("object_name", _v("object_name", "object_description", "object_address")),
        ("settlement", _v("settlement")),
        ("area_total", _v("area_total", "area")),
        ("price", _v("price", "budget")),
        ("price_words", _v("price_words")),
    ]
    for key, val in replacements:
        out = out.replace("{{" + key + "}}", val)
    # Все остальные ключи из slots
    for key, val in s.items():
        if isinstance(key, str) and isinstance(val, (str, int, float)):
            out = out.replace("{{" + key + "}}", str(val))
    return out


@app.get("/api/contracts/preview", summary="Превью договора по conversation_id (для отображения в ЛК без email)")
def contract_preview(conversation_id: int = Query(..., description="ID диалога")) -> Any:
    """Возвращает тело договора с подстановкой из слотов (body, subject, template_name) для показа в ЛК."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT slots FROM conversations WHERE id = %s", (conversation_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Диалог не найден")
        slots = row[0] or {}
        if not isinstance(slots, dict):
            slots = {}
        cur.execute(
            "SELECT id, name, body FROM document_templates WHERE type = 'contract' AND is_active = true ORDER BY id LIMIT 1",
            (),
        )
        tpl = cur.fetchone()
        cur.close()
        conn.close()
        if not tpl:
            raise HTTPException(status_code=404, detail="Шаблон договора не найден")
        tpl_id, tpl_name, tpl_body = tpl[0], tpl[1], tpl[2] or ""
        body_text = _fill_template(tpl_body, slots)
        return {"body": body_text, "subject": f"Договор: {tpl_name}", "template_name": tpl_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/api/contracts/prepare-email", summary="Подготовить письмо с договором (для отправки из n8n)")
def prepare_contract_email(body: PrepareContractEmailRequest) -> Any:
    """
    По conversation_id берёт email из conversations.slots и шаблон договора (type=contract),
    подставляет в body шаблона client_name, email, phone. Возвращает to_email, subject, body
    для узла Send Email в n8n. Если email нет в slots и не передан to_email_override — 400.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT slots, amocrm_lead_id FROM conversations WHERE id = %s",
            (body.conversation_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Диалог не найден")
        slots = row[0] or {}
        amocrm_lead_id = row[1] if len(row) > 1 else None
        if not isinstance(slots, dict):
            slots = {}
        to_email = (body.to_email_override or "").strip() or (slots.get("email") or "").strip()
        if not to_email:
            cur.close()
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="email_not_in_slots: укажите email для отправки договора (в слотах диалога или to_email_override).",
            )
        if body.template_id:
            cur.execute(
                "SELECT id, name, body FROM document_templates WHERE id = %s AND type = 'contract' AND is_active = true",
                (body.template_id,),
            )
        else:
            cur.execute(
                "SELECT id, name, body FROM document_templates WHERE type = 'contract' AND is_active = true ORDER BY id LIMIT 1",
                (),
            )
        tpl = cur.fetchone()
        cur.close()
        conn.close()
        if not tpl:
            raise HTTPException(status_code=404, detail="Шаблон договора не найден. Добавьте запись в document_templates с type=contract.")
        tpl_id, tpl_name, tpl_body = tpl[0], tpl[1], tpl[2] or ""
        body_text = _fill_template(tpl_body, slots)
        subject = f"Договор: {tpl_name}"
        # Продвижение сделки в AmoCRM: этап «Договор/документы отправлены»
        if amocrm_lead_id:
            contract_status = os.getenv("AMOCRM_STATUS_CONTRACT_SENT")
            if contract_status and str(contract_status).isdigit():
                _amocrm_move_lead_to_status(amocrm_lead_id, int(contract_status))
        return {
            "to_email": to_email,
            "subject": subject,
            "body": body_text,
            "template_id": tpl_id,
            "conversation_id": body.conversation_id,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "funnel-api"}
