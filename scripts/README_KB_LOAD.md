# Загрузка базы знаний из data в KB (векторная БЗ)

Скрипт **load_kb_from_data.py** автоматически загружает текстовые файлы и документы из папки `data/` в базу знаний через API kb-service.

## Структура data (анализ)

| Путь | Содержимое | Категория KB |
|------|------------|--------------|
| `data/БЗ/` | Основная папка с материалами для БЗ | — |
| `data/БЗ/*.txt` | price, adress, social_net, clients, interest_script, presentation_* | pricing, location, contacts, sales_script, product_info |
| `data/БЗ/*.docx`, `*.pdf`, `*.pptx` | Синтетическая БЗ, презентации КП, описания | product_info |
| `data/БЗ/photo_descriptions/*.docx` | Описания по типам отделки (дизайнерский ремонт, планировка и т.д.) | product_info |
| `data/БЗ/вопросы_neurocrm.txt` | **Тестовые вопросы для проверки релевантности** — по умолчанию **не загружаются** в KB; используются скриптом `check_kb_relevance.py` | — |
| `data/БЗ/Сторисы/` | Сторисы (если есть txt/docx) | product_info |
| `data/Работа_AMOCRM` | Материалы по AmoCRM | по умолчанию product_info |

Маппинг имени файла/пути на категорию и целевую аудиторию задаётся в скрипте (FILE_MAPPING). При необходимости его можно расширить.

## Требования

- Запущенный **kb-service** (порт 8001 по умолчанию).
- В корне проекта настроен **config.env** с `KB_API_URL=http://localhost:8001` (или переменная окружения).
- Python 3.9+ с установленным `requests`: `pip install requests`.

## Использование

```bash
cd /projects/brats

# Подгрузить конфиг (KB_API_URL и др.)
set -a; source config.env; set +a   # bash
# или export KB_API_URL=http://localhost:8001

# Список файлов без загрузки (проверка маппинга)
python scripts/load_kb_from_data.py --dry-run

# Загрузка в KB (папка data по умолчанию)
python scripts/load_kb_from_data.py

# Другая папка, свои параметры chunk
python scripts/load_kb_from_data.py --data-dir data/БЗ --chunk-size 2500 --overlap 400
```

## Повторная загрузка «вместо первой попытки»

Чтобы **очистить KB и заново загрузить** все материалы из data (например, после добавления формата .pptx или изменения маппинга):

```bash
cd /projects/brats
set -a; source config.env; set +a   # нужен DATABASE_URL и KB_API_URL

# Сначала убедитесь, что kb-service запущен (порт 8001)
python scripts/reset_and_load_kb.py
```

Скрипт **reset_and_load_kb.py**:
1. Подключается к БД по `DATABASE_URL` из config.env и выполняет `TRUNCATE knowledge_base`.
2. Запускает `load_kb_from_data.py` с теми же параметрами (поддерживаются `--data-dir`, `--chunk-size`, `--overlap`, `--dry-run` и т.д.).

Без `DATABASE_URL` в config.env скрипт выдаст ошибку и не будет очищать таблицу.

## Проверка релевантности после загрузки

Файл **вопросы_neurocrm.txt** не импортируется в KB по умолчанию — он используется как набор тестовых запросов для проверки, что загруженная БЗ возвращает релевантные ответы.

После загрузки данных запустите:

```bash
python scripts/check_kb_relevance.py
```

Скрипт читает `data/БЗ/вопросы_neurocrm.txt`, отправляет каждый вопрос в `POST /api/kb/search` и выводит топ-N найденных chunks (similarity и превью текста). Так можно оценить, насколько релевантна загрузка.

Опции: `--questions` (путь к файлу), `--limit` (сколько топ-результатов выводить), `--top` (сколько запрашивать у API), `--max-questions` (ограничить число вопросов для прогона).

## Параметры load_kb_from_data.py

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `--data-dir` | `data` | Корневая папка с файлами (.txt, .md, .docx, .pdf, .pptx) |
| `--kb-url` | из config.env / `http://localhost:8001` | URL API kb-service |
| `--chunk-size` | 3000 | Размер chunk при разбиении текста |
| `--overlap` | 300 | Перекрытие между chunks |
| `--dry-run` | — | Только вывести список файлов и категорий, не вызывать API |
| `--encoding` | utf-8 | Кодировка для .txt (при ошибке пробуется cp1251) |
| `--include-test-questions` | — | Включить в загрузку вопросы_neurocrm.txt (по умолчанию исключён) |

## API KB, которые использует скрипт

1. **POST /api/kb/import** — для готового текста (.txt, .md): в body передаётся `content`, `category`, `target_audience`, `source`, `chunk_size`, `chunk_overlap`. Сервис сам разбивает текст на chunks и создаёт эмбеддинги.

2. **POST /api/kb/import_document** — для файлов .docx, .pdf и .pptx: multipart/form-data (файл + те же параметры). Сервис извлекает текст из документа (из PPTX — текст со всех слайдов), затем разбивает и добавляет в KB.

Категории: `product_info`, `sales_script`, `objection_handling`, `target_audience`, `contacts`, `pricing`, `location`, `tone_of_voice`.  
Целевая аудитория: `end_buyer`, `realtor`, `both`.
