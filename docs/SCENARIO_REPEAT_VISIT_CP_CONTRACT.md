,# Сценарий: повторный заход — КП — окончательный договор

Проигрывание варианта, когда клиент **возвращается** (гипотетически после осмотра и выбора недвижимости): ему высылается **КП**, после согласования — **окончательный договор**.

Соответствует разделу 5 документа [FUNNEL_CALENDAR_CP_CONTRACT.md](./FUNNEL_CALENDAR_CP_CONTRACT.md) (выбор объекта, резерв, КП, договор).

---

## 1. Роли и предпосылки

| Роль | Действие |
|------|----------|
| **Клиент** | Уже был на сайте/в чате, оставил контакт; (гипотетически) посетил объект, выбрал дом/участок. При повторном заходе просит КП, затем согласовывает условия и запрашивает договор. |
| **Система** | По `conversation_id` / `amocrm_lead_id` знает клиента; по запросу создаёт КП, затем по согласованию отдаёт шаблон/сгенерированный договор. |

**Предпосылки для проигрывания:**
- В БД есть запись в `conversations` (и при необходимости лид в AmoCRM), т.е. контакт уже создан из чата.
- В `viewing_slots` может быть запись о просмотре (опционально).
- В `document_templates` есть хотя бы один шаблон с `type = 'proposal'` и один с `type = 'contract'`.
- Запущены **funnel-api** (порт 8011) и при необходимости **amocrm-api** (8010).

---

## 2. Пошаговый сценарий (как проиграть)

### Шаг 0. Подготовка

1. **Создать лид/контакт из чата** (если ещё нет):
   ```bash
   curl -s -X POST http://localhost:8010/api/test-lead-from-chat \
     -H "Content-Type: application/json" \
     -d '{"phone": "+79991234567", "name": "Иван Повторный", "note": "Повторный заход после осмотра", "channel": "website", "external_id": "visitor_repeat_1"}'
   ```
   В ответе — `conversation_id`, `lead_id`, `contact_id`. Сохраните `conversation_id` и `lead_id` для следующих шагов.

2. **Проверить шаблоны КП и договора:**
   ```bash
   curl -s "http://localhost:8011/api/document-templates?type_filter=proposal"
   curl -s "http://localhost:8011/api/document-templates?type_filter=contract"
   ```
   Если пусто — добавить шаблоны в таблицу `document_templates` (см. db-init/08_seed_samples.sql или вручную).

3. **При необходимости создать слоты просмотра** (для полноты сценария «после осмотра»):
   ```bash
   curl -s -X POST "http://localhost:8011/api/viewing-slots/seed?days=7"
   ```

---

### Шаг 1. Клиент повторно заходит и просит КП

**Действие клиента (в чате или гипотетически):** «Хочу коммерческое предложение по дому, который смотрел» / «Пришлите КП».

**Действие системы (n8n или прямой вызов API):**

1. Определить `conversation_id` (из сессии чата — Resolve Conversation) и при необходимости `amocrm_lead_id` из `conversations`.
2. Создать КП:
   ```bash
   curl -s -X POST http://localhost:8011/api/proposals \
     -H "Content-Type: application/json" \
     -d '{"conversation_id": 1, "amocrm_lead_id": 38128467, "product_ids": [1], "template_id": 1}'
   ```
   (Подставьте свои `conversation_id`, `amocrm_lead_id`, `product_ids` — ID объектов из каталога, `template_id` — id шаблона КП из `document_templates`.)
3. В ответе — `id` КП и при наличии `link` или `content_preview`. Ответ клиенту в чате: «Отправил вам КП по выбранному объекту. Ссылка: …» или текст КП.

**Проверка:** `GET http://localhost:8011/api/proposals?conversation_id=1` — в списке появилось новое КП со статусом `draft` или `sent`.

---

### Шаг 2. Клиент согласовывает условия

**Действие клиента:** «Устраивает» / «Согласен» / «Готов подписать» / «Пришлите договор».

**Действие системы:**
- Обновить статус КП на `finalized` или `accepted` (при наличии соответствующего API или через БД).
- Подготовить следующий шаг — выдача договора.

(Опционально: если в системе есть модификация КП по запросу клиента — новая версия КП, затем снова отправка и только после согласия — переход к договору.)

---

### Шаг 3. Выдача договора (ссылка или текст)

**Действие системы:**
1. Получить шаблон договора:
   ```bash
   curl -s "http://localhost:8011/api/document-templates?type_filter=contract"
   ```
2. Либо отдать клиенту **ссылку на шаблон/форму** (если договор — статичная страница или форма на сайте).
3. Либо сгенерировать документ по шаблону и данным из КП/conversation и вернуть ссылку на файл или текст.

**Ответ клиенту в чате:** «Вот окончательный договор: [ссылка или прикреплённый файл]. В договоре указан ваш объект: [адрес дома или номер лота — из слотов или выбранных позиций]. Подпишите и отправьте нам, после этого ожидайте подтверждения и инструкции по оплате.»

---

### Шаг 4. Высылка договора по email

**Предпосылка:** в диалоге есть email (в `conversations.slots.email` или передан при создании лида из чата). Если нет — запросить у клиента и сохранить в слоты.

**Действие системы (n8n или прямой вызов):**

1. Подготовить письмо с договором (funnel-api подставляет в шаблон договора данные из слотов):
   ```bash
   curl -s -X POST http://localhost:8011/api/contracts/prepare-email \
     -H "Content-Type: application/json" \
     -d '{"conversation_id": 1}'
   ```
   В ответе: `to_email`, `subject`, `body` — текст письма с подстановкой из слотов: {{client_name}}, {{email}}, {{phone}}, {{object_address}}, {{lot_number}}, {{object_description}}. Рекомендуется при высылке договора указывать в письме/шаблоне купленный объект (адрес дома или номер лота): сохраняйте в слоты диалога выбранный объект (например `object_address`, `lot_number` или `object_description`), тогда они подставятся в шаблон договора.
   Если email отсутствует в слотах — ответ 400 с `detail: "email_not_in_slots"`; тогда ответить клиенту: «Укажите, пожалуйста, ваш email для отправки договора».

2. Отправить письмо: в n8n — узел **Send Email** (SMTP или почтовый API), подставив `to_email`, `subject`, `body` из ответа prepare-email.

3. (Опционально) Добавить примечание к сделке в AmoCRM: «Договор отправлен на email …» (amocrm-api: добавление примечания к лиду).

**Ответ клиенту:** «Договор отправлен на указанный email. После подписания мы свяжемся с вами.»

---

### Шаг 5. Закрытие сделки

После отправки договора по email (и при необходимости после подтверждения подписания) сделку переводят в этап «Успешно реализовано».

**Действие системы:**
```bash
curl -s -X POST "http://localhost:8010/api/leads/38128467/close"
```
(Подставьте свой `lead_id`; этап по умолчанию — 142, либо передайте `?status_id=142` явно.)

В ответе — обновлённый лид. В AmoCRM сделка переходит в выбранный закрытый этап воронки (см. [AMOCRM.md](./AMOCRM.md): этап 142 — «Успешно реализовано»).

**Ответ клиенту (если нужно):** «Сделка оформлена. Спасибо за сотрудничество.»

---

## 3. API, используемые в сценарии

| Этап | Метод | URL | Назначение |
|------|--------|-----|------------|
| Контакт уже есть | POST | amocrm-api: `/api/test-lead-from-chat` | Создание лида/контакта из чата (если ещё не создан). |
| Слоты | POST | funnel-api: `/api/viewing-slots/seed?days=7` | Создание свободных слотов (опционально). |
| Шаблоны | GET | funnel-api: `/api/document-templates?type_filter=proposal` | Список шаблонов КП. |
| Шаблоны | GET | funnel-api: `/api/document-templates?type_filter=contract` | Список шаблонов договора. |
| Создание КП | POST | funnel-api: `/api/proposals` | Создание КП (тело: conversation_id, amocrm_lead_id?, product_ids?, template_id?). |
| Один КП | GET | funnel-api: `/api/proposals/{id}` | Получить КП (content_text для выдачи клиенту). |
| Список КП | GET | funnel-api: `/api/proposals?conversation_id=` | Список КП по диалогу. |
| Договор | GET | funnel-api: `/api/document-templates?type_filter=contract` | Получение шаблона договора. |
| Подготовка письма с договором | POST | funnel-api: `/api/contracts/prepare-email` | Тело: `conversation_id`, опционально `template_id`, `to_email_override`. Возврат: `to_email`, `subject`, `body` для Send Email в n8n. |
| Закрытие сделки | POST | amocrm-api: `/api/leads/{lead_id}/close` | Переводит сделку в этап «Успешно реализовано» (по умолчанию status_id=142). Опционально: `?status_id=...`. |

---

## 4. Интеграция с n8n и чатом

- **Повторный заход:** тот же webhook чата; по `external_id` (visitor_id) n8n вызывает Resolve Conversation и получает `conversation_id` (и при необходимости amocrm_lead_id из БД). Контекст «уже был контакт, возможно был просмотр» можно передавать в промпт LLM.
- **Интент «КП»:** в workflow добавить ветку: при фразах «КП», «коммерческое предложение», «пришлите предложение» → вызов `POST /api/proposals` (funnel-api), подстановка ссылки/текста КП в ответ клиенту.
- **Интент «договор» / «согласен»:** ветка: при фразах «договор», «готов подписать», «согласен» → обновление статуса КП (если есть API), вызов `GET /api/document-templates?type_filter=contract` и подстановка ссылки на договор или сгенерированного документа в ответ.
- **Интент «договор на email»:** ветка: при фразах «вышлите договор на почту», «пришлите договор на email» → вызов `POST /api/contracts/prepare-email` (funnel-api), затем узел **Send Email** в n8n с данными из ответа; при успехе — опционально `POST /api/leads/{id}/close` (amocrm-api) и примечание к сделке.

Подробнее по узлам и промпту — [FUNNEL_CALENDAR_CP_CONTRACT.md](./FUNNEL_CALENDAR_CP_CONTRACT.md), разделы 3–4 и 5.2 (высылка договора по email и закрытие сделки).

---

## 5. Краткий чек-лист проигрывания

1. [ ] Создать контакт из чата (test-lead-from-chat), сохранить `conversation_id`, `lead_id`.
2. [ ] Убедиться, что в `document_templates` есть шаблоны `proposal` и `contract`.
3. [ ] Запросить КП: `POST /api/proposals` с conversation_id, amocrm_lead_id, product_ids, template_id.
4. [ ] Проверить список КП: `GET /api/proposals?conversation_id=...`.
5. [ ] Имитировать согласование (вручную обновить статус КП в БД или через API, когда будет реализован).
6. [ ] Выдать договор: `GET /api/document-templates?type_filter=contract`, подставить ссылку/текст в ответ клиенту.
7. [ ] Убедиться, что в слотах диалога есть email (или передать в test-lead-from-chat при создании лида).
8. [ ] Подготовить письмо с договором: `POST /api/contracts/prepare-email` с `conversation_id`; в n8n — отправить письмо (Send Email) по данным из ответа.
9. [ ] Закрыть сделку: `POST /api/leads/{lead_id}/close` (amocrm-api).

После этого сценарий «повторный заход → КП → согласование → договор → высылка по email → закрытие сделки» проигран до конца; остаётся подключить ветки в n8n и формулировки в промпте агента.

---

### 5.1 Пример заполнения слотов для договора (seller_name, object_name и др.)

Шаблон договора подставляет в плейсхолдеры значения из `conversations.slots`. Ниже — пример полного набора слотов и способ их задать.

**Пример слотов для договора:**

| Ключ в slots | Пример значения | Плейсхолдер в шаблоне |
|--------------|-----------------|------------------------|
| `seller_name` | ООО «СтройДом» | {{seller_name}} |
| `seller_basis` | Устава | {{seller_basis}} |
| `client_name` или `name` | Иванов Юрий | {{client_name}} |
| `client_passport` или `passport` | 4512 123456, выдан ОВД 01.02.2020 | {{client_passport}} |
| `object_name` | Жилой дом с участком, лот 15 | {{object_name}} |
| `settlement` | КП «Родные берега» | {{settlement}} |
| `area_total` или `area` | 120 | {{area_total}} |
| `price` или `budget` | 5 200 000 | {{price}} |
| `price_words` | пять миллионов двести тысяч | {{price_words}} |
| `city` | Москва | {{city}} |
| `date` | 09.03.2026 | {{date}} (если не задан — подставляется текущая дата) |
| `phone` | +7 999 123-45-67 | {{phone}} |
| `email` | ivan@example.com | {{email}} |

**Пример JSON слотов для одного диалога:**

```json
{
  "phone": "+79991234567",
  "email": "ivan@example.com",
  "client_name": "Иванов Юрий",
  "seller_name": "ООО «СтройДом»",
  "seller_basis": "Устава",
  "client_passport": "4512 123456, выдан ОВД 01.02.2020",
  "object_name": "Жилой дом с участком, лот 15",
  "settlement": "КП «Родные берега»",
  "area_total": "120",
  "price": "5 200 000",
  "price_words": "пять миллионов двести тысяч",
  "city": "Москва"
}
```

**Запись слотов в БД (SQL):** обновить или дополнить слоты диалога можно так (подставьте свой `conversation_id`):

```sql
-- Дополнить существующие слоты (не затирая phone, email, client_name)
UPDATE conversations
SET slots = slots || '{
  "seller_name": "ООО «СтройДом»",
  "seller_basis": "Устава",
  "object_name": "Жилой дом с участком, лот 15",
  "settlement": "КП «Родные берега»",
  "area_total": "120",
  "price": "5 200 000",
  "city": "Москва"
}'::jsonb,
updated_at = NOW()
WHERE id = 1;
```

Данные для `seller_name`, `object_name`, `settlement`, `price` и т.д. могут поступать из карточки сделки AmoCRM (синхронизация полей в слоты) или из ответов клиента в чате (агент уточняет и сохраняет в слоты через workflow/n8n).

---

## 6. Проигрывание цепочки до закрытия сделки (один прогон)

Ниже — последовательность вызовов, которую можно выполнить подряд, подставив свои идентификаторы. Сервисы: **amocrm-api** на 8010, **funnel-api** на 8011; в БД должны быть шаблоны КП и договора в `document_templates`.

**1. Создать лид и диалог (если ещё нет)**

```bash
RESP=$(curl -s -X POST http://localhost:8010/api/test-lead-from-chat \
  -H "Content-Type: application/json" \
  -d '{"phone": "+79991234567", "name": "Иван Клиент", "email": "ivan@example.com", "note": "Тест цепочки до закрытия", "channel": "website", "external_id": "lk_play_1"}')
echo $RESP | python3 -m json.tool
# Из ответа взять lead_id и conversation_id
export LEAD_ID=12345678    # подставить из ответа
export CONV_ID=1            # подставить conversation_id из ответа
```

**2. Создать КП**

```bash
curl -s -X POST "http://localhost:8011/api/proposals" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\": $CONV_ID, \"amocrm_lead_id\": $LEAD_ID, \"product_ids\": [1], \"template_id\": 1}" | python3 -m json.tool
```

**3. Подготовить письмо с договором** (email берётся из слотов диалога — он уже передан в шаге 1)

```bash
curl -s -X POST "http://localhost:8011/api/contracts/prepare-email" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\": $CONV_ID}" | python3 -m json.tool
# В ответе: to_email, subject, body — эти данные передать в узел Send Email в n8n (или отправить письмо вручную для теста).
```

**4. Закрыть сделку в AmoCRM**

```bash
curl -s -X POST "http://localhost:8010/api/leads/$LEAD_ID/close" | python3 -m json.tool
```

Цепочка проиграна: контакт → КП → подготовка договора на email → закрытие сделки. В реальном сценарии между шагами 2 и 3 клиент «согласовывает» КП (можно обновить статус КП в БД при наличии API), а отправку письма выполняет n8n по интенту «вышлите договор на почту».
