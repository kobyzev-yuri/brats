#!/bin/bash
# Создание контакта из диалога и привязка к ЛК (личный кабинет).
# Использование: ./create_contact_and_lk.sh [AMOCRM_API_BASE_URL]
# Требуется: миграция 10_create_users_and_lk.sql применена (таблицы lk_users, lk_sessions, conversations.user_id).

BASE="${1:-http://localhost:8010}"

RESP=$(curl -s -X POST "${BASE}/api/test-lead-from-chat" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+79104558214",
    "name": "Юрий Кобызев",
    "email": "yuri.kobyzev@mail.ru",
    "note": "Технический специалист. #54223003 #тегировать",
    "channel": "website"
  }')

echo "$RESP" | python3 -m json.tool

echo ""
echo "--- Данные для входа в ЛК (если применена миграция 10) ---"
echo "  Логин:    yuri.kobyzev@mail.ru"
echo "  Пароль:   +79104558214"
echo "  Ссылка:   ${BASE}/lk/login.html"
echo ""
echo "Контакты: lead_id и conversation_id — в JSON выше."
