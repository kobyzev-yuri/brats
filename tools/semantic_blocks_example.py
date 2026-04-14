"""
Пример извлечения смысловых блоков из страницы
Игнорирует служебную информацию (навигация, меню, формы)
"""

import json
import re
from typing import Dict, List, Optional, Any

class SemanticBlocksExtractor:
    """Извлекает смысловые блоки из страницы"""
    
    # Роли элементов, которые нужно игнорировать
    IGNORE_ROLES = [
        'navigation',
        'banner',
        'contentinfo',
        'complementary',  # sidebar
        'search'
    ]
    
    # Тексты, которые указывают на служебные элементы
    IGNORE_TEXTS = [
        'skip to main content',
        'закрыть диалоговое окно',
        'навигационное меню',
        'предыдущий слайд',
        'следующий слайд',
        'политика конфиденциальности',
        'отправить запрос',
        'в каталог'
    ]
    
    def extract_blocks(self, snapshot: Dict) -> Dict[str, Any]:
        """
        Извлекает смысловые блоки из snapshot страницы
        
        Args:
            snapshot: Результат browser_snapshot()
            
        Returns:
            Словарь с извлеченными блоками
        """
        blocks = {
            'title': None,
            'description': None,
            'includes': None,
            'price': None,
            'gallery': [],
            'advantages': None,
            'contacts': None,
            'layouts': None
        }
        
        ignored_blocks = []
        
        # Обход элементов snapshot
        self._process_element(snapshot, blocks, ignored_blocks)
        
        return {
            'semantic_blocks': blocks,
            'ignored_blocks': ignored_blocks
        }
    
    def _process_element(self, element: Dict, blocks: Dict, ignored: List[str]):
        """Рекурсивно обрабатывает элементы"""
        
        role = element.get('role', '')
        name = element.get('name', '')
        ref = element.get('ref', '')
        children = element.get('children', [])
        
        # Проверка на игнорирование
        if self._should_ignore(element):
            ignored.append(f"{role}: {name[:50]}")
            return
        
        # Извлечение блоков по типу
        if role == 'heading':
            self._extract_heading(element, blocks)
        elif role == 'img':
            self._extract_image(element, blocks)
        elif role == 'list':
            self._extract_list(element, blocks)
        elif 'text' in role.lower() or role == 'generic':
            self._extract_text(element, blocks)
        
        # Рекурсивная обработка дочерних элементов
        for child in children:
            self._process_element(child, blocks, ignored)
    
    def _should_ignore(self, element: Dict) -> bool:
        """Проверяет, нужно ли игнорировать элемент"""
        
        role = element.get('role', '').lower()
        name = element.get('name', '').lower()
        
        # Игнорировать по роли
        if role in self.IGNORE_ROLES:
            return True
        
        # Игнорировать по тексту
        for ignore_text in self.IGNORE_TEXTS:
            if ignore_text in name:
                return True
        
        # Игнорировать маленькие изображения (иконки)
        if role == 'img':
            # В реальности нужно проверять размер изображения
            # Здесь упрощенная проверка по контексту
            if 'icon' in name or 'logo' in name:
                return True
        
        return False
    
    def _extract_heading(self, element: Dict, blocks: Dict):
        """Извлекает заголовок"""
        name = element.get('name', '')
        
        # Определить тип заголовка
        if any(x in name.upper() for x in ['STANDARD', 'BLACK BOX', 'WHITE BOX', 'DESIGN']):
            blocks['title'] = {
                'type': 'heading',
                'text': name,
                'level': self._get_heading_level(element)
            }
    
    def _extract_image(self, element: Dict, blocks: Dict):
        """Извлекает изображение из галереи"""
        # В реальности нужно проверять размер и контекст
        # Здесь упрощенная версия
        
        # Игнорировать маленькие изображения
        # (в реальности проверять размер)
        
        # Добавить в галерею
        image_info = {
            'url': self._extract_image_url(element),
            'alt': element.get('name', '')
        }
        
        if image_info['url']:
            blocks['gallery'].append(image_info)
    
    def _extract_list(self, element: Dict, blocks: Dict):
        """Извлекает списки (что включает, преимущества)"""
        name = element.get('name', '').lower()
        
        # Определить тип списка
        if 'что включает' in name or 'includes' in name:
            blocks['includes'] = {
                'type': 'list',
                'title': 'Что включает',
                'items': self._extract_list_items(element)
            }
        elif 'преимущества' in name or 'advantages' in name:
            blocks['advantages'] = {
                'type': 'list',
                'title': 'Преимущества',
                'items': self._extract_list_items(element)
            }
    
    def _extract_text(self, element: Dict, blocks: Dict):
        """Извлекает текстовый контент"""
        name = element.get('name', '')
        
        # Извлечение описания
        if not blocks['description'] and len(name) > 100:
            # Проверить, что это описание, а не служебный текст
            if not any(ignore in name.lower() for ignore in self.IGNORE_TEXTS):
                blocks['description'] = {
                    'type': 'text',
                    'content': name
                }
        
        # Извлечение цены
        price_match = re.search(r'(\d+[\s\']*\d+[\s\']*\d+)\s*Р', name)
        if price_match and not blocks['price']:
            blocks['price'] = {
                'type': 'price',
                'value': price_match.group(0),
                'currency': 'RUB'
            }
        
        # Извлечение контактов
        if not blocks['contacts']:
            contacts = self._extract_contacts(name)
            if contacts:
                blocks['contacts'] = contacts
    
    def _extract_contacts(self, text: str) -> Optional[Dict]:
        """Извлекает контактную информацию"""
        phone_match = re.search(r'\+7\s*\(?\d{3}\)?\s*\d{3}[\s-]?\d{2}[\s-]?\d{2}', text)
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        
        if phone_match or email_match:
            return {
                'type': 'contacts',
                'phone': phone_match.group(0) if phone_match else None,
                'email': email_match.group(0) if email_match else None
            }
        return None
    
    def _extract_list_items(self, element: Dict) -> List[str]:
        """Извлекает элементы списка"""
        items = []
        children = element.get('children', [])
        
        for child in children:
            if child.get('role') == 'listitem':
                name = child.get('name', '')
                if name:
                    items.append(name)
        
        return items
    
    def _extract_image_url(self, element: Dict) -> Optional[str]:
        """Извлекает URL изображения"""
        # В реальности нужно искать атрибут src или data-src
        # Здесь упрощенная версия
        return None
    
    def _get_heading_level(self, element: Dict) -> int:
        """Определяет уровень заголовка"""
        # В реальности нужно проверять тег (h1, h2, h3)
        # Здесь упрощенная версия
        return 1


# Пример использования
if __name__ == "__main__":
    extractor = SemanticBlocksExtractor()
    
    # В реальности snapshot будет получен из browser_snapshot()
    # snapshot = browser_snapshot()
    
    # Для примера создаем упрощенный snapshot
    example_snapshot = {
        'role': 'generic',
        'children': [
            {
                'role': 'heading',
                'name': 'STANDARD (стандартный ремонт)'
            },
            {
                'role': 'generic',
                'name': 'Просторный, уютный дом с качественным ремонтом...'
            }
        ]
    }
    
    result = extractor.extract_blocks(example_snapshot)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))



