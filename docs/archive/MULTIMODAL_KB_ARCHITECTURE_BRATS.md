## Мультимодальная база знаний BRATS

### 1. Цели

- **Мультимодальная KB**: хранить структурированные знания по проекту заказчика (тексты + изображения, ссылки, метаданные).
- **Агент‑библиотекарь (на Gemini 3 через proxyapi.ru)**: проверяет релевантность материалов, качество, дубликаты и делает аннотации к изображениям перед сохранением в KB.
- **Гибкий ввод контента**: 
  - автоматический сбор по URL с сайта заказчика,
  - ручное добавление/редактирование записей,
  - поддержка записей с картинками и без.

### 2. Основные компоненты

- **Multimodal KB API (FastAPI, `kb-service`)**
  - новые эндпоинты `mmkb` для работы с мультимодальными документами;
  - хранение в PostgreSQL/pgvector в таблице `knowledge_base` c расширенными `metadata` (изображения, аннотации, разделы).

- **Агент‑библиотекарь**
  - реализован как сервис в `kb-service` (`services/mm_librarian.py`);
  - использует `LLMService` и конфигурацию Gemini (`GEMINI_*` через proxyapi.ru);
  - выполняет:
    - анализ документа (текст + список изображений),
    - проверку релевантности к домену заказчика,
    - проверку на дубликаты через `KBService.search`,
    - генерацию краткого abstract,
    - очистку "воды",
    - генерацию аннотаций и описаний к изображениям.

- **Агент сбора по URL (Gemini 3)**
  - FastAPI‑эндпоинт `POST /api/mmkb/import_from_url`;
  - получает URL сайта заказчика, вызывает LLM (Gemini 3 через proxyapi.ru) по аналогии с `3dtoday/backend/app/main.py::parse_url_with_llm`;
  - формирует черновой документ (title, text, images, metadata), передаёт его библиотекарю.

- **Веб-админка KB (реализовано)**
  - Streamlit-приложение `kb-service/web/kb_admin_app.py` поверх API kb-service и `mmkb`‑эндпоинтов.
  - Уже поддерживает аннотирование картинок с сайта и смысловые блоки:
    - **Импорт по URL через библиотекаря** — загрузка страницы, анализ библиотекарём, извлечение смысловых блоков и галереи изображений; для картинок формируются аннотации (vision: 3dtoday / Gemini / GPT-4o в зависимости от конфига).
    - В интерфейсе отображаются смысловые блоки (по одному в KB), к каждому — заголовок, текст, изображения с аннотациями; кнопки «Добавить этот блок в KB» и «Добавить галерею в KB».
    - Ручной ввод материала (заголовок, раздел, текст, URL картинок) → проверка библиотекарём → просмотр abstract, аннотаций к изображениям, решения (approve/reject/needs_review) → сохранение в KB.
  - Подробнее: `kb-service/web/KB_ADMIN_USER_GUIDE.md`, `docs/KB_ADMINISTRATION_AND_MULTITENANCY.md`.

### 3. Сетевые настройки (config.env)

В корневом `config.env` / `config.env.example`:

- **Multimodal KB API**
  - `MMKB_API_URL=http://localhost:8001`  
    (используем существующий `kb-service` как хост мультимодальной KB).

- **Агент‑библиотекарь**
  - вызывается через те же FastAPI‑эндпоинты, отдельный сервис не нужен;
  - для интеграции с n8n:
    - `LIBRARIAN_API_URL=http://localhost:8001/api/mmkb/review`.

В `kb-service/config.env.example`:

- **Провайдер LLM**
  - `LLM_PROVIDER=openai` (по умолчанию), планируется поддержка `gemini`.

- **Gemini через proxyapi.ru**
  - `GEMINI_API_KEY=your_proxyapi_key_here`
  - `GEMINI_BASE_URL=https://api.proxyapi.ru/google`
  - `GEMINI_MODEL=gemini-3-pro-preview`
  - `GEMINI_TEMPERATURE=0.2`
  - `GEMINI_TIMEOUT=120`

> Примечание: сейчас `LLMService` работает через OpenAI‑совместимый клиент (GPT‑4o через proxyapi.ru). Для реального использования Gemini 3 потребуется расширить `LLMService` по аналогии с `3dtoday/backend/app/services/llm_client.py` (провайдер `gemini` и REST‑вызов `.../v1beta/models/{model}:generateContent`).

### 4. Структура разделов мультимодальной KB (руссифицированная)

Аналогично `3dtoday/docs/KB_SECTIONS_STRUCTURE.md`, но под домен заказчика:

- **1. Посёлок и инфраструктура (`settlement_info`)**
  - описание посёлка, инфраструктура, дороги, коммуникации;
  - карты, схемы, визуализации.

- **2. Объекты и планировки (`product_info`)**
  - типы домов, участков, планировки;
  - визуализации, 3D‑туры, план-схемы;
  - технические характеристики.

- **3. Цены, акции и условия (`pricing_offers`)**
  - базовые цены, акции, спецпредложения;
  - ипотечные программы, рассрочки;
  - примеры расчётов.

- **4. Частые вопросы (`faq`)**
  - FAQ по сделке, инфраструктуре, строительству;
  - сценарии ответов для бота/продажника.

- **5. Возражения и отработки (`objections`)**
  - типовые возражения клиентов;
  - варианты ответов и сценарии диалога;
  - примеры удачных кейсов.

- **6. Юридические и финансы (`legal_finance`)**
  - документы, этапы сделки, безопасность;
  - налоги, маткапитал, субсидии.

Все разделы хранятся в `metadata` KB:

- `metadata.section`: один из перечисленных разделов;
- `metadata.content_type`: `article|documentation|faq|case|howto`;
- `metadata.images`: список изображений (URL, alt, annotations);
- `metadata.abstract`: краткое изложение;
- `metadata.source_url`: исходный URL с сайта заказчика;
- `metadata.relevance_score`, `metadata.quality_score`.

### 5. Потоки данных

#### 5.1. Автоматический сбор по URL

1. n8n или админ UI вызывает  
   `POST /api/mmkb/import_from_url` (FastAPI, `kb-service`).
2. Эндпоинт:
   - загружает страницу по URL,
   - вызывает LLM (Gemini 3 / GPT‑4o) для извлечения структуры: `title`, `text`, `images[]`, `metadata`.
3. Полученный черновой документ отправляется в библиотекарь‑сервис:
   - `MultimodalLibrarian.review_document(...)`.
4. Библиотекарь возвращает JSON‑решение:
   - `decision`: `approve|reject|needs_review`,
   - `abstract`, `filtered_text`, `relevance_score`, `image_annotations[]`, `duplicate_check`.
5. Админ (или workflow) либо:
   - подтверждает и вызывает `/api/mmkb/save`,
   - либо отклоняет/редактирует.

#### 5.2. Ручное добавление/редактирование

1. UI отправляет `POST /api/mmkb/review` с:
   - `title`, `text`, `section`, `images[] (URL/base64)`, `metadata`.
2. Библиотекарь:
   - проверяет релевантность и дубликаты,
   - формирует structured summary и аннотации к изображениям.
3. После подтверждения вызывается `/api/mmkb/save`:
   - создаётся запись в KB через `KBService.add_chunk(...)`,
   - текст хранится в `content`, всё остальное — в `metadata`.

### 6. Использование существующих FastAPI‑сервисов

- **База знаний и поиск**: используется текущий `KBService` (PostgreSQL + pgvector), без изменения схемы таблицы:
  - мультимодальные данные (картинки, аннотации, разделы) добавляются в `metadata`.
- **RAG**: существующий `RAGService` продолжает работать, но получает более богатый `metadata` для фильтрации и отображения источников (включая изображения).
- **DLP**: сохраняется существующий DLP‑слой перед вызовами зарубежных моделей через proxyapi.ru.

**Аннотирование изображений (vision):** приоритет выбора провайдера:
1. **3dtoday** — если заданы `VISION_3DTODAY_PATH` (путь к backend 3dtoday) и `USE_3DTODAY_VISION=true`. Используется `VisionAnalyzer` из `~/3dtoday/backend` (Gemini + fallback Ollama/llava), адаптер — `kb-service/services/vision_3dtoday_adapter.py`.
2. **Встроенный Gemini** — если `USE_GEMINI_FOR_VISION=true` и настроен `gemini_vision_service`.
3. **LLMService (GPT-4o)** — по умолчанию.

### 7. Следующие шаги реализации

1. **Расширить конфиг**:
   - добавить `MMKB_API_URL`, `LIBRARIAN_API_URL`, `GEMINI_*` в `config.env.example`.
2. **Добавить FastAPI‑роутер** `kb-service/api/mmkb_endpoints.py`:
   - `POST /api/mmkb/review` — работа библиотекаря;
   - `POST /api/mmkb/save` — запись/обновление в KB;
   - `POST /api/mmkb/import_from_url` — LLM‑парсинг URL.
3. **Реализовать `services/mm_librarian.py`**:
   - адаптация логики из `3dtoday/backend/app/agents/kb_librarian.py` под домен недвижимости;
   - системные промпты и структура ответа — по `docs/LIBRARIAN_DECISION.md` (3dtoday), но с новыми разделами.
4. **(Опционально) Поддержка vision‑эмбеддингов**:
   - добавить отдельную таблицу/коллекцию для векторов изображений (OpenCLIP или Gemini embeddings);
   - связывать изображения с текстовыми chunk’ами через `metadata.image_ids`.












