# Справочные и устаревшие артефакты KB

Здесь лежат файлы, **не используемые** в текущем стеке. Цель — постепенно от них избавляться: либо удалять, либо явно оформлять как **примеры для понимания** (добавлять в описание пометку «Пример: …», не тащить в новый код).

**Правило при доработках:** трогая старый файл — решить: удалить (если точно не нужен), или оставить как документированный пример; не оставлять «просто так». Текущая база знаний — таблица **`knowledge_base`** (PostgreSQL + pgvector), админка — **kb-service/web/kb_admin_app.py** (Streamlit, работа через API на :8001).

| Файл | Назначение | Почему не в корне |
|------|------------|-------------------|
| **kb_admin_app.py** | Старая Flask-админка для управления «блоками» KB (прямое подключение к БД, таблица `kb_blocks`). | Актуальная админка — Streamlit в `kb-service/web/kb_admin_app.py`, схема — `knowledge_base`. |
| **kb_deduplication_example.py** | Пример класса дедупликации при записи блоков (по `block_id`, tab_name, семантическое сходство). | Дубликаты в текущем проекте проверяет библиотекарь (mm_librarian) при импорте; таблица — `knowledge_base`. |
| **kb_postgresql_cleanup.sql** | SQL для таблицы **kb_blocks** (is_active, бэкапы, удаление дубликатов по `content_hash`). | Схема `knowledge_base` другая (нет kb_blocks/content_hash); при необходимости очистка — `scripts/reset_and_load_kb.py` или прямой TRUNCATE. |
| **requirements_admin.txt** | Зависимости для старой Flask-админки (**kb_admin_app.py**). | Админка устарела; текущая — Streamlit в kb-service. |
| **kb_postgresql_management.py** | Утилита для пометки/удаления блоков в таблице **kb_blocks** (mark_as_inactive, delete). | Схема `knowledge_base` в kb-service; очистка — через scripts или TRUNCATE. |
| **test_reprocess.py** | Тест роутов reprocess и шаблонов старой Flask-админки (**kb_admin_app.py**). | Запуск из каталога `tools/`: `python test_reprocess.py`. |
| **gallery_analysis_example.py** | Пример анализа галереи изображений (Gemini Vision, браузерные инструменты). | Демо/справочник; не входит в текущий пайплайн. |
| **semantic_blocks_example.py** | Пример извлечения смысловых блоков со страницы (игнор навигации, меню). | Демо/справочник. |
| **strict_tab_parser.py** | Парсер вкладок тарифов (BLACK BOX, WHITE BOX, STANDARD, DESIGN) для контента сайта. | Специфичный парсер; при необходимости адаптировать под актуальные скрипты. |

Использовать только как справочник по старой схеме или идеям дедупликации. Для работы с KB: **scripts/load_kb_from_data.py**, **scripts/reset_and_load_kb.py**, **scripts/check_kb_relevance.py** и админка Streamlit (порт 8501).
