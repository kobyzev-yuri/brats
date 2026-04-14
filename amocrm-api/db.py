"""
Запись в PostgreSQL (conversations, messages) при создании лида из чата и для памяти диалога.
Использует DATABASE_URL из config.env в корне репо (загружается через client.py).
"""
import os
import json
from typing import Optional, List, Tuple

# DATABASE_URL подхватывается из окружения (config.env грузится в client при импорте)


def get_or_create_conversation_by_external(
    channel: str = "website",
    external_id: Optional[str] = None,
) -> Tuple[Optional[int], List[dict]]:
    """
    Находит или создаёт диалог по channel + external_id.
    Возвращает (conversation_id, список последних сообщений [{role, content}, ...], до 20 шт).
    Если external_id пустой — возвращает (None, []).
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not (external_id or "").strip():
        return None, []
    try:
        import psycopg2
        ext = (external_id or "").strip()[:200]
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM conversations
                    WHERE channel = %s AND external_id = %s
                    LIMIT 1
                    """,
                    (channel, ext),
                )
                row = cur.fetchone()
                if row:
                    cid = row[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO conversations (channel, external_id, state)
                        VALUES (%s, %s, 'GREETING')
                        RETURNING id
                        """,
                        (channel, ext),
                    )
                    r = cur.fetchone()
                    cid = r[0] if r else None
                    conn.commit()
                if not cid:
                    return None, []
                cur.execute(
                    """
                    SELECT role, content FROM messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (cid,),
                )
                rows = cur.fetchall()
                messages = [{"role": r[0], "content": (r[1] or "").strip()} for r in reversed(rows)]
                return cid, messages
    except Exception:
        return None, []


def append_message(conversation_id: int, role: str, content: str) -> bool:
    """Добавляет сообщение в диалог. role: 'user' | 'assistant' | 'system'."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id:
        return False
    role = (role or "user").lower()
    if role not in ("user", "assistant", "system"):
        role = "user"
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                    (conversation_id, role, (content or "").strip()[:50000]),
                )
                conn.commit()
                return True
    except Exception:
        return False


def append_messages_bulk(conversation_id: int, messages: List[dict]) -> int:
    """Добавляет несколько сообщений. Каждое: {role, content}. Возвращает количество сохранённых."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id or not messages:
        return 0
    n = 0
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                for m in messages:
                    role = (m.get("role") or "user").lower()
                    if role not in ("user", "assistant", "system"):
                        role = "user"
                    content = (m.get("content") or "").strip()[:50000]
                    cur.execute(
                        "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                        (conversation_id, role, content),
                    )
                    n += 1
                conn.commit()
                return n
    except Exception:
        return 0


def get_conversation_by_external(
    channel: str = "website",
    external_id: Optional[str] = None,
) -> Optional[Tuple[int, Optional[int], Optional[int]]]:
    """
    Находит диалог по channel + external_id.
    Возвращает (conversation_id, amocrm_lead_id, amocrm_contact_id) или None.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not (external_id or "").strip():
        return None
    try:
        import psycopg2
        ext = (external_id or "").strip()[:200]
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, amocrm_lead_id, amocrm_contact_id
                    FROM conversations
                    WHERE channel = %s AND external_id = %s
                    LIMIT 1
                    """,
                    ((channel or "website").strip() or "website", ext),
                )
                row = cur.fetchone()
                if row:
                    return (row[0], row[1], row[2])
                return None
    except Exception:
        return None


def update_conversation_lead(
    conversation_id: int,
    lead_id: int,
    contact_id: Optional[int],
    slots: Optional[dict] = None,
) -> bool:
    """Обновляет существующий диалог после создания лида в AmoCRM."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id or not lead_id:
        return False
    try:
        import psycopg2
        slots_json = json.dumps(slots or {}, ensure_ascii=False)
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE conversations
                    SET amocrm_lead_id = %s, amocrm_contact_id = %s, state = 'QUALIFYING',
                        slots = %s::jsonb, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (lead_id, contact_id, slots_json, conversation_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception:
        return False


def insert_conversation_from_chat(
    lead_id: int,
    contact_id: Optional[int],
    channel: str = "website",
    phone: str = "",
    name: str = "",
    email: Optional[str] = None,
    note: Optional[str] = None,
) -> Optional[int]:
    """
    Вставляет запись в conversations и возвращает conversation_id.
    Если DATABASE_URL не задан или ошибка — возвращает None.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    try:
        import psycopg2
        slots = {"phone": phone, "client_name": name}
        if email:
            slots["email"] = email
        if note:
            slots["note_preview"] = (note[:200] + "…") if len(note) > 200 else note
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (
                        amocrm_lead_id, amocrm_contact_id, channel, state, slots
                    ) VALUES (%s, %s, %s, %s, %s::jsonb)
                    RETURNING id
                    """,
                    (lead_id, contact_id, channel, "QUALIFYING", json.dumps(slots, ensure_ascii=False)),
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
    except Exception:
        return None


def get_conversation_by_id(conversation_id: int) -> Optional[dict]:
    """
    Возвращает диалог по id: id, state, slots, amocrm_lead_id, amocrm_contact_id, channel.
    Для вкладки «Чат менеджера» и возврата диалога агенту.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id:
        return None
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, state, slots, amocrm_lead_id, amocrm_contact_id, channel, created_at, updated_at, user_id
                    FROM conversations WHERE id = %s
                    """,
                    (conversation_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "state": row[1],
                    "slots": row[2] or {},
                    "amocrm_lead_id": row[3],
                    "amocrm_contact_id": row[4],
                    "channel": row[5],
                    "created_at": row[6].isoformat() if row[6] else None,
                    "updated_at": row[7].isoformat() if row[7] else None,
                    "user_id": row[8] if len(row) > 8 else None,
                }
    except Exception:
        return None


def get_messages(conversation_id: int, limit: int = 200) -> List[dict]:
    """Возвращает сообщения диалога для отображения в чате менеджера."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id:
        return []
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content, created_at FROM messages
                    WHERE conversation_id = %s ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (conversation_id, limit),
                )
                rows = cur.fetchall()
                return [
                    {"role": r[0], "content": (r[1] or "").strip(), "created_at": r[2].isoformat() if r[2] else None}
                    for r in rows
                ]
    except Exception:
        return []


def update_conversation_slots(conversation_id: int, slots_update: dict) -> bool:
    """Обновляет слоты диалога: мержит slots_update с существующими slots (для ЛК — данные для шаблонов)."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id or not isinstance(slots_update, dict):
        return False
    try:
        import psycopg2
        conv = get_conversation_by_id(conversation_id)
        if not conv:
            return False
        current = dict(conv.get("slots") or {})
        for k, v in slots_update.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                current.pop(k, None)
            else:
                current[k] = v
        slots_json = json.dumps(current, ensure_ascii=False)
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET slots = %s::jsonb, updated_at = NOW() WHERE id = %s",
                    (slots_json, conversation_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception:
        return False


def update_conversation_state(conversation_id: int, new_state: str) -> bool:
    """Обновляет state диалога (для возврата из HANDOFF агенту: PROPOSAL, FINALIZED и т.д.)."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id or not (new_state or "").strip():
        return False
    try:
        import psycopg2
        state = (new_state or "").strip()[:50]
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET state = %s, updated_at = NOW() WHERE id = %s",
                    (state, conversation_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception:
        return False


# --- Личный кабинет (ЛК): пользователи, пароль = телефон ---

_LK_PASSWORD_PREFIX = "brats_lk_"


def _lk_hash(password: str) -> str:
    """Хэш пароля для ЛК (телефон как пароль)."""
    import hashlib
    return hashlib.sha256((_LK_PASSWORD_PREFIX + (password or "").strip()).encode()).hexdigest()


def create_lk_user(
    login: str,
    phone: str,
    password_hash: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> Optional[int]:
    """Создаёт пользователя ЛК. login — уникальный (email или телефон). Возвращает user_id или None."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not (login or "").strip() or not (phone or "").strip() or not password_hash:
        return None
    try:
        import psycopg2
        login = (login or "").strip()[:255]
        phone = (phone or "").strip()[:50]
        email = (email or "").strip()[:255] or None
        name = (name or "").strip()[:200] or None
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lk_users (login, phone, email, password_hash, name)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (login) DO NOTHING
                    RETURNING id
                    """,
                    (login, phone, email, password_hash, name),
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
    except Exception:
        return None


def get_lk_user_by_login(login: str) -> Optional[Tuple[int, str, str, Optional[str], Optional[str]]]:
    """Возвращает (id, phone, password_hash, email, name) по login (email или телефон) или None."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not (login or "").strip():
        return None
    try:
        import psycopg2
        login = (login or "").strip()[:255]
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, phone, password_hash, email, name FROM lk_users WHERE login = %s LIMIT 1",
                    (login,),
                )
                row = cur.fetchone()
                return tuple(row) if row else None
    except Exception:
        return None


def set_conversation_user_id(conversation_id: int, user_id: int) -> bool:
    """Привязывает диалог к пользователю ЛК."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id or not user_id:
        return False
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE conversations SET user_id = %s, updated_at = NOW() WHERE id = %s",
                    (user_id, conversation_id),
                )
                conn.commit()
                return cur.rowcount > 0
    except Exception:
        return False


def get_conversation_id_by_user_id(user_id: int) -> Optional[int]:
    """Возвращает conversation_id, привязанный к пользователю ЛК (последний по updated_at)."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not user_id:
        return None
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM conversations WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1",
                    (user_id,),
                )
                row = cur.fetchone()
                return row[0] if row else None
    except Exception:
        return None


def get_or_link_conversation_for_lk_user(user_id: int) -> Optional[int]:
    """
    Возвращает conversation_id для пользователя ЛК. Если диалог уже привязан — возвращает его.
    Иначе ищет диалог по совпадению логина (телефон/email) в slots и привязывает к пользователю.
    """
    cid = get_conversation_id_by_user_id(user_id)
    if cid is not None:
        return cid
    user = get_lk_user_by_id(user_id)
    if not user or not (user.get("login") or "").strip():
        return None
    login = (user.get("login") or "").strip()[:255]
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM conversations
                    WHERE user_id IS NULL
                      AND (slots->>'phone' = %s OR slots->>'email' = %s)
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (login, login),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cid = row[0]
                set_conversation_user_id(cid, user_id)
                return cid
    except Exception:
        return None


def create_lk_session(user_id: int, token_hash: str, expires_at) -> bool:
    """Сохраняет сессию ЛК (token_hash = хэш выданного токена)."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not user_id or not token_hash:
        return False
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO lk_sessions (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
                    (user_id, token_hash, expires_at),
                )
                conn.commit()
                return True
    except Exception:
        return False


def get_lk_user_id_by_token(token_hash: str) -> Optional[int]:
    """Возвращает user_id по хэшу токена, если сессия не истекла. Удаляет просроченные."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not token_hash:
        return None
    try:
        import psycopg2
        from datetime import datetime
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM lk_sessions WHERE expires_at < NOW()"
                )
                cur.execute(
                    "SELECT user_id FROM lk_sessions WHERE token_hash = %s AND expires_at > NOW() LIMIT 1",
                    (token_hash,),
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
    except Exception:
        return None


def get_lk_user_by_id(user_id: int) -> Optional[dict]:
    """Возвращает данные пользователя ЛК по id (без password_hash)."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not user_id:
        return None
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, login, phone, email, name, created_at FROM lk_users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "id": row[0],
                    "login": row[1],
                    "phone": row[2],
                    "email": row[3],
                    "name": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
    except Exception:
        return None


def ensure_lk_user_for_contact(
    conversation_id: int,
    phone: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> Optional[int]:
    """
    Создаёт пользователя ЛК при создании контакта из чата (запись на просмотр).
    Логин = email если есть, иначе телефон. Пароль = телефон (клиенту передать в чате).
    Привязывает диалог к пользователю. Возвращает user_id или None.
    """
    if not (phone or "").strip():
        return None
    phone = (phone or "").strip()[:50]
    login = (email or "").strip()[:255] if email else phone
    if not login:
        login = phone
    password_hash = _lk_hash(phone)
    user_id = create_lk_user(
        login=login,
        phone=phone,
        password_hash=password_hash,
        email=(email or "").strip()[:255] or None,
        name=(name or "").strip()[:200] or None,
    )
    if user_id is None:
        row = get_lk_user_by_login(login)
        user_id = row[0] if row else None
    if user_id:
        set_conversation_user_id(conversation_id, user_id)
    return user_id


# --- Вложения ЛК (скан паспорта и др.) ---

def insert_lk_attachment(conversation_id: int, filename: str, content_type: str, file_data: bytes) -> Optional[int]:
    """Сохраняет загруженный файл. Возвращает id вложения или None."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id or not (filename or "").strip() or file_data is None:
        return None
    try:
        import psycopg2
        fn = (filename or "").strip()[:255]
        ct = (content_type or "application/octet-stream").strip()[:128]
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lk_attachments (conversation_id, filename, content_type, file_data)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (conversation_id, fn, ct, file_data),
                )
                row = cur.fetchone()
                conn.commit()
                return row[0] if row else None
    except Exception:
        return None


def get_lk_attachments(conversation_id: int) -> List[dict]:
    """Список вложений диалога (id, filename, content_type, created_at)."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not conversation_id:
        return []
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, filename, content_type, created_at
                    FROM lk_attachments
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC
                    """,
                    (conversation_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "filename": r[1],
                        "content_type": r[2] or "",
                        "created_at": r[3].isoformat() if r[3] else None,
                    }
                    for r in rows
                ]
    except Exception:
        return []


def get_lk_attachment_content(attachment_id: int, conversation_id: int) -> Optional[Tuple[bytes, str, str]]:
    """Возвращает (file_data, content_type, filename) или None если не найден/не тот диалог."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not attachment_id or not conversation_id:
        return None
    try:
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT file_data, content_type, filename
                    FROM lk_attachments
                    WHERE id = %s AND conversation_id = %s
                    """,
                    (attachment_id, conversation_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return (row[0], row[1] or "application/octet-stream", row[2] or "file")
    except Exception:
        return None
