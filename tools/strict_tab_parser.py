"""
Строгий парсер вкладок с проверками на смешивание контента
"""

import re
from typing import Dict, List, Optional, Any

class StrictTabParser:
    """Строгий парсер для извлечения контента только активной вкладки"""
    
    # Индикаторы для каждой вкладки
    TAB_INDICATORS = {
        'BLACK BOX': {
            'title': r'BLACK BOX\s*\(черновой ремонт\)',
            'price': r'8\s*350\s*000\s*Р',
            'includes_text': r'черновой ремонт включает',
            'button': r'Коттедж с черновой отделкой',
            'exclude': ['WHITE BOX', 'STANDARD', 'DESIGN', 'предчистовой', 'стандартный', 'дизайнерский']
        },
        'WHITE BOX': {
            'title': r'WHITE BOX\s*\(предчистовой ремонт\)',
            'price': r'8\s*950\s*000\s*Р(?!\s*\+)',  # Точная цена без доплат
            'includes_text': r'предчистовой ремонт включает',
            'button': r'Коттедж с предчистовой отделкой',
            'exclude': ['BLACK BOX', 'STANDARD', 'DESIGN', 'черновой', 'стандартный', 'дизайнерский']
        },
        'STANDARD': {
            'title': r'STANDARD\s*\(стандартный ремонт\)',
            'price': r"8['\s]*950['\s]*000\s*Р\s*\+\s*ремонт-700['\s]*000\s*Р",
            'includes_text': r'стандартный ремонт включает',
            'description_text': r'Просторный, уютный дом с качественным ремонтом',
            'button': r'Коттедж со стандартным ремонтом',
            'exclude': ['BLACK BOX', 'WHITE BOX', 'DESIGN', 'черновой', 'предчистовой', 'дизайнерский']
        },
        'DESIGN': {
            'title': r'DESIGN\s*\(дизайнерский ремонт\)',
            'price': r"8['\s]*950['\s]*000\s*Р\s*\+\s*дизайнерский ремонт-1['\s]*500['\s]*000\s*Р",
            'includes_text': r'дизайнерский ремонт включает',
            'description_text': r'Дизайн-проект — выбор из 3 готовых вариантов',
            'button': r'Коттедж с дизайнерским ремонтом',
            'exclude': ['BLACK BOX', 'WHITE BOX', 'STANDARD', 'черновой', 'предчистовой', 'стандартный']
        }
    }
    
    def __init__(self, active_tab: str):
        """
        Инициализация парсера
        
        Args:
            active_tab: Активная вкладка (BLACK BOX, WHITE BOX, STANDARD, DESIGN)
        """
        if active_tab not in self.TAB_INDICATORS:
            raise ValueError(f"Неизвестная вкладка: {active_tab}")
        
        self.active_tab = active_tab
        self.indicators = self.TAB_INDICATORS[active_tab]
    
    def parse_snapshot(self, snapshot: Dict) -> Dict[str, Any]:
        """
        Строго парсит snapshot, извлекая ТОЛЬКО контент активной вкладки
        
        Args:
            snapshot: Результат browser_snapshot()
            
        Returns:
            Словарь с извлеченными блоками
        """
        blocks = {
            'tab': self.active_tab,
            'blocks': {}
        }
        
        # Найти заголовок активной вкладки
        title_block = self._extract_title(snapshot)
        if title_block:
            blocks['blocks']['title'] = title_block
        
        # Найти описание
        description_block = self._extract_description(snapshot)
        if description_block:
            blocks['blocks']['description'] = description_block
        
        # Найти "Что включает"
        includes_block = self._extract_includes(snapshot)
        if includes_block:
            blocks['blocks']['includes'] = includes_block
        
        # Найти стоимость
        price_block = self._extract_price(snapshot)
        if price_block:
            blocks['blocks']['price'] = price_block
        
        return blocks
    
    def _extract_title(self, snapshot: Dict) -> Optional[Dict]:
        """Извлекает заголовок активной вкладки"""
        title_text = self._find_text_in_snapshot(snapshot, self.indicators['title'])
        
        if not title_text:
            return None
        
        # Проверка: не содержит ли другие вкладки?
        if self._contains_other_tabs(title_text):
            return None
        
        return {
            'type': 'heading',
            'content': title_text,
            'tab': self.active_tab
        }
    
    def _extract_description(self, snapshot: Dict) -> Optional[Dict]:
        """Извлекает описание активной вкладки"""
        # Найти заголовок
        title_element = self._find_element_by_text(snapshot, self.indicators['title'])
        if not title_element:
            return None
        
        # Найти описание после заголовка
        description_text = self._find_text_after_element(
            snapshot, 
            title_element,
            self.indicators.get('description_text', '')
        )
        
        if not description_text:
            return None
        
        # СТРОГАЯ ПРОВЕРКА: не содержит ли другие вкладки?
        if self._contains_other_tabs(description_text):
            return None
        
        # Проверка: содержит ли индикаторы активной вкладки?
        if not self._contains_active_tab_indicators(description_text):
            return None
        
        return {
            'type': 'description',
            'content': description_text,
            'tab': self.active_tab
        }
    
    def _extract_includes(self, snapshot: Dict) -> Optional[Dict]:
        """Извлекает список 'Что включает' активной вкладки"""
        includes_text = self._find_text_in_snapshot(snapshot, self.indicators['includes_text'])
        
        if not includes_text:
            return None
        
        # СТРОГАЯ ПРОВЕРКА: не содержит ли другие вкладки?
        if self._contains_other_tabs(includes_text):
            return None
        
        # Извлечь элементы списка
        items = self._extract_list_items(snapshot, includes_text)
        
        # Проверить каждый элемент списка
        filtered_items = []
        for item in items:
            if not self._contains_other_tabs(item):
                filtered_items.append(item)
        
        return {
            'type': 'includes',
            'title': 'Что включает',
            'items': filtered_items,
            'tab': self.active_tab
        }
    
    def _extract_price(self, snapshot: Dict) -> Optional[Dict]:
        """Извлекает стоимость активной вкладки"""
        price_text = self._find_text_in_snapshot(snapshot, self.indicators['price'])
        
        if not price_text:
            return None
        
        # Проверка: соответствует ли цена активной вкладке?
        if not self._matches_tab_price(price_text):
            return None
        
        return {
            'type': 'price',
            'value': price_text,
            'tab': self.active_tab
        }
    
    def _contains_other_tabs(self, text: str) -> bool:
        """Проверяет, содержит ли текст индикаторы других вкладок"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Проверить исключающие слова
        for exclude_word in self.indicators['exclude']:
            if exclude_word.lower() in text_lower:
                return True
        
        return False
    
    def _contains_active_tab_indicators(self, text: str) -> bool:
        """Проверяет, содержит ли текст индикаторы активной вкладки"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Проверить наличие индикаторов активной вкладки
        if self.indicators.get('description_text'):
            if self.indicators['description_text'].lower() in text_lower:
                return True
        
        # Проверить заголовок
        title_match = re.search(self.indicators['title'], text, re.IGNORECASE)
        if title_match:
            return True
        
        return False
    
    def _matches_tab_price(self, price_text: str) -> bool:
        """Проверяет, соответствует ли цена активной вкладке"""
        if not price_text:
            return False
        
        # Нормализовать цену
        normalized_price = self._normalize_price(price_text)
        expected_price = self._normalize_price(self.indicators['price'])
        
        return normalized_price == expected_price
    
    def _normalize_price(self, price: str) -> str:
        """Нормализует цену для сравнения"""
        # Удалить все кроме цифр и знаков
        normalized = re.sub(r'[^\d+\-]', '', price)
        return normalized
    
    def _find_text_in_snapshot(self, snapshot: Dict, pattern: str) -> Optional[str]:
        """Находит текст в snapshot по паттерну"""
        # Рекурсивный поиск в snapshot
        def search_recursive(element):
            name = element.get('name', '')
            if re.search(pattern, name, re.IGNORECASE):
                return name
            
            for child in element.get('children', []):
                result = search_recursive(child)
                if result:
                    return result
            
            return None
        
        return search_recursive(snapshot)
    
    def _find_element_by_text(self, snapshot: Dict, pattern: str) -> Optional[Dict]:
        """Находит элемент в snapshot по тексту"""
        def search_recursive(element):
            name = element.get('name', '')
            if re.search(pattern, name, re.IGNORECASE):
                return element
            
            for child in element.get('children', []):
                result = search_recursive(child)
                if result:
                    return result
            
            return None
        
        return search_recursive(snapshot)
    
    def _find_text_after_element(self, snapshot: Dict, start_element: Dict, indicator: str) -> Optional[str]:
        """Находит текст после указанного элемента"""
        # Упрощенная версия - в реальности нужен более сложный алгоритм
        # для поиска текста после элемента в DOM дереве
        return None
    
    def _extract_list_items(self, snapshot: Dict, includes_text: str) -> List[str]:
        """Извлекает элементы списка 'Что включает'"""
        # Упрощенная версия - в реальности нужен парсинг списка из snapshot
        return []


# Пример использования
if __name__ == "__main__":
    # Парсинг вкладки STANDARD
    parser = StrictTabParser('STANDARD')
    
    # В реальности snapshot будет получен из browser_snapshot()
    # snapshot = browser_snapshot()
    
    # Для примера создаем упрощенный snapshot
    example_snapshot = {
        'role': 'generic',
        'name': 'STANDARD (стандартный ремонт)',
        'children': [
            {
                'role': 'generic',
                'name': 'Просторный, уютный дом с качественным ремонтом...'
            }
        ]
    }
    
    result = parser.parse_snapshot(example_snapshot)
    print(result)



