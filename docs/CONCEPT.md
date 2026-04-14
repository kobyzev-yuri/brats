# Концепция: база знаний, воронка продаж и медиа

Единый документ по принципам организации KB, скриптам, админке, ведению клиента по воронке и показу релевантных картинок/документов в ответе агента.

**Диаграммы и потоки:** [BUSINESS_PROCESSES.md](./BUSINESS_PROCESSES.md). **AmoCRM и API:** [docs/AMOCRM.md](./AMOCRM.md).

---

## 1. Принципы организации KB

- **Хранение:** PostgreSQL, таблица `knowledge_base` (pgvector). Текст — `content`, вектор — `embedding`, остальное — **`metadata`** (JSONB). Схему не меняем: картинки и документы в `metadata.images` и `metadata.documents`.
- **Категории и аудитория:** product_info, sales_script, objection_handling, contacts, pricing, location, tone_of_voice; target_audience: end_buyer, realtor, both; приоритет и источник (`source`) — в metadata, используются при поиске.
- **Источники контента:** (1) скрипты из папки `data/`, (2) импорт по URL через библиотекаря (`/api/mmkb/import_from_url`, `/api/mmkb/save`), (3) KB Admin. При импорте из текста/файлов URL картинок и документов извлекаются автоматически в metadata.
- **Идентификация посетителя:** сайт передаёт в n8n **`external_id`** (cookie или Yandex Metrika ID). amocrm-api при создании лида ищет диалог по `external_id`+`channel`; если лид уже есть — новый не создаётся. Один посетитель = один диалог и один лид.

---

## 2. Медиа в ответе агента (картинки и документы)

- **`metadata.images`** — массив `{ url, description?, alt? }`. **`metadata.documents`** — массив `{ url, title?, description? }`. Картинки с диска раздаются по HTTP, в KB хранится только URL.
- Поиск (`POST /api/kb/search`) возвращает metadata. В n8n нода Format KB Context собирает из результатов медиа и добавляет в контекст LLM блок «Релевантные медиа»; Prepare Response добавляет в ответ поле **`media`** (`images`, `documents`). Чат на сайте по `response.media` отображает под ответом картинки и ссылки на документы.
- Промпт агента: при наличии «Релевантные медиа» — кратко упомянуть приложенные фото/документы, длинные URL в текст не вставлять.

---

## 3. Скрипты загрузки KB и аналоги в админке

| Скрипт | Назначение |
|--------|------------|
| **`scripts/load_kb_from_data.py`** | Загрузка из `data/` в KB (без очистки). Параметры: `--data-dir`, `--chunk-size`, `--overlap`, `--encoding`, `--dry-run`, `--include-test-questions`. |
| **`scripts/reset_and_load_kb.py`** | TRUNCATE `knowledge_base` + запуск `load_kb_from_data.py`. Требует `DATABASE_URL` и запущенный kb-service. |
| **`scripts/check_kb_relevance.py`** | Вопросы из файла (по умолчанию `data/БЗ/вопросы_neurocrm.txt`) → `/api/kb/search`, вывод топов и схожести. |

**.txt/.md:** текст читается локально, URL медиа извлекаются, в `/api/kb/import` передаётся `content` и при наличии `metadata: { images, documents }`. **.docx/.pdf/.pptx:** файл в `POST /api/kb/import_document`; kb-service извлекает текст и URL медиа в metadata. Категория/аудитория — по имени и пути файла (маппинг в скрипте).

**Админка KB (Streamlit, 8501):** обзор и поиск по чанкам; редактирование chunk (контент, категория, приоритет, теги, источник) и блока «Медиа» (images/documents) с сохранением через API; импорт по URL с библиотекарём. Очистки всей KB в UI нет — только скрипт.

---

## 4. Ведение клиента по воронке

1. Лид появляется (сайт, Telegram, Avito) → n8n webhook sales-agent-kb.
2. Нормализация + Resolve Conversation по `external_id`/`channel` (история, без дубликата лида).
3. DLP обезличивание → поиск в KB → контекст + медиа + слоты календаря → ответ LLM + `media`.
4. При телефоне в сообщении — `POST /api/test-lead-from-chat` с `external_id`/`channel`; при существующем диалоге с лидом — новый лид не создаётся.
5. Запись на просмотр — слоты из funnel-api; далее по BUSINESS_PROCESSES: квалификация → показ → КП/смета → согласование → ипотека → документы → оплата.

**Роль KB:** до контакта — ответы и привлечение оставить контакт, показ медиа; после контакта — те же чанки + память диалога, запись на просмотр, передача менеджеру по запросу. Обогащение KB — из диалогов и примечаний (раздел 9 BUSINESS_PROCESSES).

---

## 5. Сводка

| Тема | Решение |
|------|---------|
| KB | Одна таблица `knowledge_base`, медиа в `metadata.images` и `metadata.documents`. |
| Медиа в ответе | Поиск → n8n собирает медиа → `response.media` → чат отображает. |
| Загрузка | `load_kb_from_data.py` / `reset_and_load_kb.py`; URL из текста/файлов → metadata. |
| Админка | Поиск, редактирование чанков и медиа, импорт по URL. |
| Воронка и лиды | Один лид на диалог при телефоне; дубликата нет при том же `external_id`+`channel`. |
