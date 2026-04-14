# Maybe Create Lead: извлечение телефона, имени и email

Если лид в AmoCRM **не создаётся** при сообщении вида «Я оставил заявку: Василиса Премудрая, тел. 79106337788, email vp@example.com», скорее всего узел **Maybe Create Lead** не распознаёт номер в формате **тел. 79106337788** (без плюса и пробелов). Ниже — готовая логика для Code-узла в n8n.

---

## 1. Откуда брать данные

- Вход: **исходное** сообщение пользователя из узла **Normalize Input** (не обезличенное), а также `external_id`, `channel` из webhook/merge.
- В Code-узле обратитесь к выходу Normalize Input, например: `const input = $('Normalize Input').first().json;` и возьмите `input.body?.message` или `input.message` (в зависимости от того, как ваш Webhook отдаёт тело).

---

## 2. Телефон: какие форматы учитывать

Нужно распознавать все типичные варианты:

| Пример в тексте | Нужно извлечь (нормализовать в цифры) |
|-----------------|----------------------------------------|
| тел. 79106337788 | 79106337788 или 9106337788 |
| +7 910 633 77 88 | 79106337788 |
| 8 910 633-77-88 | 89106337788 или 9106337788 |
| 9106337788 | 9106337788 |
| 79106337788 | 79106337788 |

**Рекомендуемая регулярка:** российский мобильный — 10 цифр, начинаются с 9 (код 9xx), либо перед ними 7 или 8.

```javascript
// Извлечение телефона: 79106337788, 89106337788, 9106337788, +7 910..., тел. 79106337788
function extractPhone(text) {
  if (!text || typeof text !== 'string') return null;
  // Убираем всё, кроме цифр, плюса и пробелов для поиска паттерна
  const cleaned = text.replace(/\s+/g, ' ');
  // Вариант 1: 10 или 11 цифр подряд, при 11 — первая 7 или 8, вторая 9
  const m = cleaned.match(/(?:^|\D)((?:[78])?9\d{9})(?:\D|$)/);
  if (m) {
    let digits = m[1].replace(/\D/g, '');
    if (digits.length === 10) digits = '7' + digits; // для amocrm-api можно и 10 цифр
    return digits;
  }
  // Вариант 2: любые 10+ подряд цифр (последняя надежда)
  const m2 = text.match(/(\d{10,11})/);
  if (m2) {
    let d = m2[1].replace(/\D/g, '');
    if (d.length === 10 && d.startsWith('9')) return '7' + d;
    if (d.length === 11 && (d.startsWith('7') || d.startsWith('8'))) return d.startsWith('8') ? '7' + d.slice(1) : d;
    return d;
  }
  return null;
}
```

Нормализация для API: amocrm-api принимает строку из цифр (10 или 11). Лучше отдавать **11 цифр с ведущей 7** (например `79106337788`).

---

## 3. Имя

Из фразы «Я оставил заявку: **Василиса Премудрая**, тел.» имя можно взять:

- по шаблону «заявку: X, тел.» или «зовут X»;
- или два подряд слова (ФИО) перед «тел.» / перед телефоном.

```javascript
function extractName(text) {
  if (!text || typeof text !== 'string') return null;
  const t = text.trim();
  // «Я оставил заявку: Василиса Премудрая, тел.»
  let m = t.match(/(?:заявк[уа]:|зовут|имя\s*[:\-]?)\s*([А-Яа-яЁёA-Za-z]+\s+[А-Яа-яЁёA-Za-z]+(?:\s+[А-Яа-яЁёA-Za-z]+)?)/i);
  if (m) return m[1].trim();
  // «Василиса Премудрая, тел. 79...» — два-три слова перед запятой и тел.
  m = t.match(/([А-Яа-яЁёA-Za-z]+\s+[А-Яа-яЁёA-Za-z]+(?:\s+[А-Яа-яЁёA-Za-z]+)?)\s*,\s*тел\./i);
  if (m) return m[1].trim();
  return null;
}
```

---

## 4. Email

```javascript
function extractEmail(text) {
  if (!text || typeof text !== 'string') return null;
  const m = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  return m ? m[0] : null;
}
```

---

## 5. Пример выхода узла Maybe Create Lead (n8n Code)

Вход: из Webhook/Normalize Input приходит объект с полями `message` (или `body.message`), `external_id`, `channel`. Подставьте свои имена полей.

```javascript
const input = $('Normalize Input').first().json;
const body = input.body || input;
const rawMessage = (body.message || body.text || '').trim();
const externalId = body.external_id || input.external_id || '';
const channel = (body.channel || input.channel || 'website').trim() || 'website';

const phone = extractPhone(rawMessage);
const name = extractName(rawMessage) || extractName(body.name) || null;
const email = extractEmail(rawMessage) || (body.email || '').trim() || null;

function extractPhone(text) {
  if (!text || typeof text !== 'string') return null;
  const cleaned = text.replace(/\s+/g, ' ');
  const m = cleaned.match(/(?:^|\D)((?:[78])?9\d{9})(?:\D|$)/);
  if (m) {
    let digits = m[1].replace(/\D/g, '');
    if (digits.length === 10) digits = '7' + digits;
    return digits;
  }
  const m2 = text.match(/(\d{10,11})/);
  if (m2) {
    let d = m2[1];
    if (d.length === 10 && d.startsWith('9')) return '7' + d;
    if (d.length === 11 && d.startsWith('8')) return '7' + d.slice(1);
    if (d.length === 11 && d.startsWith('7')) return d;
    return d;
  }
  return null;
}
function extractName(text) {
  if (!text || typeof text !== 'string') return null;
  const t = text.trim();
  let m = t.match(/(?:заявк[уа]:|зовут|имя\s*[:\-]?)\s*([А-Яа-яЁёA-Za-z]+\s+[А-Яа-яЁёA-Za-z]+(?:\s+[А-Яа-яЁёA-Za-z]+)?)/i);
  if (m) return m[1].trim();
  m = t.match(/([А-Яа-яЁёA-Za-z]+\s+[А-Яа-яЁёA-Za-z]+(?:\s+[А-Яа-яЁёA-Za-z]+)?)\s*,\s*тел\./i);
  if (m) return m[1].trim();
  return null;
}
function extractEmail(text) {
  if (!text || typeof text !== 'string') return null;
  const m = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  return m ? m[0] : null;
}

const should_create = !!phone;
const note = rawMessage.substring(0, 500);

return [{
  json: {
    should_create,
    lead_payload: should_create ? {
      phone,
      name: name || 'Клиент с сайта',
      client_name: name || undefined,
      email: email || undefined,
      note,
      external_id: externalId || undefined,
      channel,
    } : null,
  },
}];
```

Дальше узел **Create Lead If Phone** проверяет `should_create === true`, а **AmoCRM Create Lead** отправляет `lead_payload` в `POST http://localhost:8010/api/test-lead-from-chat` (или `AMOCRM_API_BASE_URL` из переменных).

---

## 6. Проверка

После правок в Maybe Create Lead отправьте в чат:

«Я оставил заявку: Василиса Премудрая, тел. 79106337788, email vp@example.com.»

В n8n в **Executions** у последнего запуска откройте узел Maybe Create Lead: на выходе должны быть `should_create: true` и в `lead_payload` — `phone: "79106337788"`, `name: "Василиса Премудрая"`, `email: "vp@example.com"`. Затем выполнится AmoCRM Create Lead — в AmoCRM появится контакт и сделка с Василисой Премудрой.
