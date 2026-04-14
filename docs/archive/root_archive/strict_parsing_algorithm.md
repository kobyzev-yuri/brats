# Строгий алгоритм парсинга вкладок

## Пошаговый алгоритм с проверками

### Шаг 1: Определение активной вкладки

```python
def get_active_tab_from_url(url):
    """Извлекает номер вкладки из URL"""
    # URL: https://innovatory-club.ru/katalog#!/tab/1063728081-3
    hash_part = url.split('#!')[1] if '#!' in url else ''
    # hash_part = "/tab/1063728081-3"
    
    tab_number = hash_part.split('-')[-1]  # "3"
    
    tab_map = {
        '1': 'BLACK BOX',
        '2': 'WHITE BOX',
        '3': 'STANDARD',
        '4': 'DESIGN'
    }
    
    return tab_map.get(tab_number, 'UNKNOWN')
```

### Шаг 2: Идентификация индикаторов активной вкладки

```python
def get_tab_indicators(tab_name):
    """Возвращает индикаторы для идентификации вкладки"""
    indicators = {
        'BLACK BOX': {
            'title': 'BLACK BOX (черновой ремонт)',
            'price': '8 350 000 Р',
            'includes_text': 'черновой ремонт включает',
            'button': 'Коттедж с черновой отделкой'
        },
        'WHITE BOX': {
            'title': 'WHITE BOX (предчистовой ремонт)',
            'price': '8 950 000 Р',
            'includes_text': 'предчистовой ремонт включает',
            'button': 'Коттедж с предчистовой отделкой'
        },
        'STANDARD': {
            'title': 'STANDARD (стандартный ремонт)',
            'price': "8'950'000 Р + ремонт-700'000 Р",
            'description_text': 'Просторный, уютный дом с качественным ремонтом',
            'includes_text': 'стандартный ремонт включает',
            'button': 'Коттедж со стандартным ремонтом'
        },
        'DESIGN': {
            'title': 'DESIGN (дизайнерский ремонт)',
            'price': "8'950'000 Р + дизайнерский ремонт-1'500'000 Р",
            'includes_text': 'дизайнерский ремонт включает',
            'description_text': 'Дизайн-проект — выбор из 3 готовых вариантов',
            'button': 'Коттедж с дизайнерским ремонтом'
        }
    }
    return indicators.get(tab_name, {})
```

### Шаг 3: Строгая фильтрация контента

```python
def extract_tab_content(snapshot, active_tab):
    """Извлекает ТОЛЬКО контент активной вкладки"""
    indicators = get_tab_indicators(active_tab)
    
    blocks = {
        'title': None,
        'description': None,
        'includes': None,
        'price': None,
        'gallery': []
    }
    
    # Найти заголовок активной вкладки
    title_element = find_element_by_text(snapshot, indicators['title'])
    if title_element:
        blocks['title'] = extract_title_block(title_element, active_tab)
    
    # Найти описание после заголовка
    description_element = find_element_after(title_element, 
                                             indicators.get('description_text', ''))
    if description_element:
        # ПРОВЕРКА: не содержит ли индикаторы других вкладок?
        if not contains_other_tabs(description_element, active_tab):
            blocks['description'] = extract_description_block(description_element, active_tab)
    
    # Найти "Что включает"
    includes_element = find_element_by_text(snapshot, indicators['includes_text'])
    if includes_element:
        # ПРОВЕРКА: список относится к активной вкладке?
        if is_correct_tab_includes(includes_element, active_tab):
            blocks['includes'] = extract_includes_block(includes_element, active_tab)
    
    # Найти стоимость
    price_element = find_element_by_text(snapshot, indicators['price'])
    if price_element:
        # ПРОВЕРКА: цена соответствует активной вкладке?
        if matches_tab_price(price_element, active_tab):
            blocks['price'] = extract_price_block(price_element, active_tab)
    
    return blocks
```

### Шаг 4: Проверка на смешивание

```python
def contains_other_tabs(element, active_tab):
    """Проверяет, содержит ли элемент индикаторы других вкладок"""
    other_tabs = ['BLACK BOX', 'WHITE BOX', 'STANDARD', 'DESIGN']
    other_tabs.remove(active_tab)
    
    element_text = element.get('name', '').lower()
    
    for other_tab in other_tabs:
        indicators = get_tab_indicators(other_tab)
        for indicator in indicators.values():
            if isinstance(indicator, str) and indicator.lower() in element_text:
                return True
    
    return False

def is_correct_tab_includes(element, active_tab):
    """Проверяет, относится ли список "Что включает" к активной вкладке"""
    indicators = get_tab_indicators(active_tab)
    includes_text = indicators.get('includes_text', '').lower()
    
    element_text = element.get('name', '').lower()
    
    # Должен содержать индикатор активной вкладки
    if includes_text not in element_text:
        return False
    
    # НЕ должен содержать индикаторы других вкладок
    if contains_other_tabs(element, active_tab):
        return False
    
    return True

def matches_tab_price(element, active_tab):
    """Проверяет, соответствует ли цена активной вкладке"""
    indicators = get_tab_indicators(active_tab)
    expected_price = normalize_price(indicators['price'])
    
    element_text = element.get('name', '')
    actual_price = normalize_price(element_text)
    
    return expected_price == actual_price
```

### Шаг 5: Разделение на смысловые блоки

```python
def create_semantic_blocks(tab_content, active_tab):
    """Создает четко разделенные смысловые блоки"""
    blocks = []
    
    # Блок 1: Заголовок
    if tab_content['title']:
        blocks.append({
            'type': 'heading',
            'content': tab_content['title'],
            'tab': active_tab,
            'block_id': f"title_{active_tab}"
        })
    
    # Блок 2: Описание
    if tab_content['description']:
        blocks.append({
            'type': 'description',
            'content': tab_content['description'],
            'tab': active_tab,
            'block_id': f"description_{active_tab}_{hash_content(tab_content['description'])}"
        })
    
    # Блок 3: Что включает
    if tab_content['includes']:
        blocks.append({
            'type': 'includes',
            'title': 'Что включает',
            'items': tab_content['includes'],
            'tab': active_tab,
            'block_id': f"includes_{active_tab}_{hash_items(tab_content['includes'])}"
        })
    
    # Блок 4: Стоимость
    if tab_content['price']:
        blocks.append({
            'type': 'price',
            'value': tab_content['price'],
            'tab': active_tab,
            'block_id': f"price_{active_tab}_{normalize_price(tab_content['price'])}"
        })
    
    return blocks
```

## Полный алгоритм для Gemini

```
АЛГОРИТМ СТРОГОГО ПАРСИНГА ВКЛАДКИ:

1. ИЗВЛЕЧЬ активную вкладку из URL:
   - URL содержит #!/tab/1063728081-X
   - X = 1 → BLACK BOX
   - X = 2 → WHITE BOX
   - X = 3 → STANDARD
   - X = 4 → DESIGN

2. НАЙТИ индикаторы активной вкладки в snapshot:
   - Заголовок (BLACK BOX / WHITE BOX / STANDARD / DESIGN)
   - Цена (8 350 000 Р / 8 950 000 Р / 8'950'000 Р + ремонт...)
   - Текст "Что включает" (черновой / предчистовой / стандартный / дизайнерский)

3. ИЗВЛЕЧЬ ТОЛЬКО контент с индикаторами активной вкладки:
   - Найти элемент с заголовком активной вкладки
   - Извлечь описание после этого заголовка
   - Извлечь "Что включает" для активной вкладки
   - Извлечь стоимость активной вкладки
   - Извлечь галерею активной вкладки

4. ПРОВЕРИТЬ каждый извлеченный блок:
   - Содержит ли индикаторы активной вкладки? ✅
   - НЕ содержит ли индикаторы других вкладок? ✅
   - Если содержит другие вкладки → ОТБРОСИТЬ блок

5. РАЗДЕЛИТЬ на смысловые блоки:
   - Блок 1: Заголовок
   - Блок 2: Описание
   - Блок 3: Что включает
   - Блок 4: Стоимость
   - Блок 5: Галерея
   - Каждый блок = отдельная сущность с четкими границами

6. ПОМЕТИТЬ каждый блок:
   - tab = активная вкладка
   - block_id = уникальный идентификатор
   - type = тип блока

7. ЗАПИСАТЬ в KB только блоки активной вкладки

ВАЖНО:
- НЕ извлекай контент других вкладок
- НЕ смешивай контент разных вкладок
- НЕ создавай один большой блок
- РАЗДЕЛЯЙ на четкие смысловые блоки
- ПРОВЕРЯЙ каждый блок перед записью
```

## Пример строгого промпта для Gemini

```
СТРОГИЙ ПАРСИНГ ВКЛАДКИ STANDARD:

URL: https://innovatory-club.ru/katalog#!/tab/1063728081-3

ШАГИ:

1. Определи активную вкладку: STANDARD (из URL)

2. Найди индикаторы STANDARD в snapshot:
   - Заголовок: "STANDARD (стандартный ремонт)"
   - Цена: "8'950'000 Р + ремонт-700'000 Р"
   - Текст: "стандартный ремонт включает"
   - Описание: "Просторный, уютный дом с качественным ремонтом"

3. Извлеки ТОЛЬКО контент со индикаторами STANDARD:
   - Найди заголовок "STANDARD (стандартный ремонт)"
   - Извлеки описание после этого заголовка
   - Извлеки список "стандартный ремонт включает"
   - Извлеки цену "8'950'000 Р + ремонт-700'000 Р"
   - ИГНОРИРУЙ все остальное

4. Проверь каждый блок:
   - Блок содержит "STANDARD" или "стандартный"? ✅
   - Блок НЕ содержит "BLACK BOX", "WHITE BOX", "DESIGN"? ✅
   - Если содержит другие вкладки → ОТБРОСЬ

5. Раздели на смысловые блоки:
   - Блок 1: Заголовок "STANDARD (стандартный ремонт)"
   - Блок 2: Описание "Просторный, уютный дом..."
   - Блок 3: Что включает [список]
   - Блок 4: Стоимость "8'950'000 Р + ремонт-700'000 Р"

6. Запиши в KB только эти блоки с tab = "STANDARD"

РЕЗУЛЬТАТ ДОЛЖЕН БЫТЬ:
- Только контент STANDARD
- Четко разделен на блоки
- Каждый блок помечен tab = "STANDARD"
- Нет упоминаний других вкладок
```

## Резюме

**Критически важно:**

1. ✅ Определять активную вкладку из URL
2. ✅ Использовать индикаторы для идентификации
3. ✅ Извлекать ТОЛЬКО контент активной вкладки
4. ✅ Проверять каждый блок на отсутствие смешивания
5. ✅ Разделять на четкие смысловые блоки
6. ✅ Помечать каждый блок tab = активная вкладка

**НЕ ДОПУСКАТЬ:**
- ❌ Смешивание контента разных вкладок
- ❌ Парсинг всех вкладок одновременно
- ❌ Создание одного большого блока
- ❌ Отсутствие проверок перед записью



