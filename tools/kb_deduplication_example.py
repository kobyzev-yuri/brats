"""
Пример дедупликации смысловых блоков при записи в Knowledge Base
"""

import hashlib
import re
from typing import Dict, Optional, List, Any
from difflib import SequenceMatcher

class KBDeduplicator:
    """Класс для проверки и исключения дубликатов при записи в KB"""
    
    def __init__(self, kb_connection):
        """
        Инициализация дедупликатора
        
        Args:
            kb_connection: Соединение с Knowledge Base
        """
        self.kb = kb_connection
        self.similarity_threshold = 0.9  # Порог семантического сходства
    
    def save_block(self, block: Dict, tab_name: str) -> bool:
        """
        Сохраняет блок в KB с проверкой на дубликаты
        
        Args:
            block: Смысловой блок для сохранения
            tab_name: Название вкладки (STANDARD, BLACK BOX и т.д.)
            
        Returns:
            True если блок записан, False если пропущен как дубликат
        """
        # Генерация идентификатора
        block_id = self._generate_block_id(block, tab_name)
        
        # Проверка существования
        existing_block = self.kb.get_block(block_id)
        
        if existing_block:
            # Проверка на точный дубликат
            if self._is_exact_duplicate(block, existing_block):
                print(f"⏭️  Пропуск точного дубликата: {block_id}")
                return False
            
            # Проверка на семантическое сходство
            similarity = self._calculate_similarity(block, existing_block)
            if similarity >= self.similarity_threshold:
                print(f"⏭️  Пропуск семантически похожего блока: {block_id} (similarity: {similarity:.2f})")
                return False
            
            # Проверка на обновление
            if self._should_update(block, existing_block):
                print(f"🔄 Обновление существующего блока: {block_id}")
                self.kb.update_block(block_id, block)
                return True
        
        # Запись нового блока
        print(f"✅ Запись нового блока: {block_id}")
        self.kb.save_block(block_id, block)
        return True
    
    def _generate_block_id(self, block: Dict, tab_name: str) -> str:
        """Генерирует уникальный идентификатор блока"""
        block_type = block.get('type', 'unknown')
        
        if block_type == 'heading':
            # Заголовок: комбинация типа отделки и вкладки
            block_text = self._normalize_text(block.get('text', ''))
            block_type_short = self._extract_block_type(block_text)
            return f"title_{tab_name}_{block_type_short}"
        
        elif block_type == 'text' or block_type == 'description':
            # Описание: хэш от нормализованного текста + вкладка
            content = self._normalize_text(block.get('content', ''))
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            return f"description_{tab_name}_{content_hash}"
        
        elif block_type == 'list':
            # Список: хэш от отсортированных элементов + вкладка
            items = block.get('items', [])
            normalized_items = sorted([self._normalize_text(item) for item in items])
            items_str = '|'.join(normalized_items)
            items_hash = hashlib.md5(items_str.encode()).hexdigest()[:8]
            
            # Определить тип списка
            list_type = block.get('title', '').lower()
            if 'что включает' in list_type or 'includes' in list_type:
                return f"includes_{tab_name}_{items_hash}"
            elif 'преимущества' in list_type or 'advantages' in list_type:
                # Преимущества одинаковы для всех вкладок
                return f"advantages_{items_hash}"
            else:
                return f"list_{tab_name}_{items_hash}"
        
        elif block_type == 'price':
            # Цена: нормализованная цена + вкладка
            price_value = self._normalize_price(block.get('value', ''))
            return f"price_{tab_name}_{price_value}"
        
        elif block_type == 'contacts':
            # Контакты: хэш от контактных данных (один раз для всех)
            phone = self._normalize_phone(block.get('phone', ''))
            email = self._normalize_email(block.get('email', ''))
            address = self._normalize_text(block.get('address', ''))
            contacts_str = f"{phone}|{email}|{address}"
            contacts_hash = hashlib.md5(contacts_str.encode()).hexdigest()[:8]
            return f"contacts_{contacts_hash}"
        
        elif block_type == 'gallery':
            # Галерея: хэш от URL изображений + вкладка
            images = block.get('images', [])
            image_urls = sorted([img.get('url', '') for img in images])
            urls_str = '|'.join(image_urls)
            urls_hash = hashlib.md5(urls_str.encode()).hexdigest()[:8]
            return f"gallery_{tab_name}_{urls_hash}"
        
        else:
            # Общий случай: хэш от всего содержимого
            content_str = str(block)
            content_hash = hashlib.md5(content_str.encode()).hexdigest()[:8]
            return f"{block_type}_{tab_name}_{content_hash}"
    
    def _is_exact_duplicate(self, block1: Dict, block2: Dict) -> bool:
        """Проверяет точное совпадение блоков"""
        # Нормализовать оба блока и сравнить
        norm1 = self._normalize_block(block1)
        norm2 = self._normalize_block(block2)
        return norm1 == norm2
    
    def _calculate_similarity(self, block1: Dict, block2: Dict) -> float:
        """Вычисляет семантическое сходство между блоками"""
        # Для текстовых блоков
        if block1.get('type') in ['text', 'description']:
            text1 = self._normalize_text(block1.get('content', ''))
            text2 = self._normalize_text(block2.get('content', ''))
            return SequenceMatcher(None, text1, text2).ratio()
        
        # Для списков
        elif block1.get('type') == 'list':
            items1 = set([self._normalize_text(item) for item in block1.get('items', [])])
            items2 = set([self._normalize_text(item) for item in block2.get('items', [])])
            
            if not items1 or not items2:
                return 0.0
            
            intersection = len(items1 & items2)
            union = len(items1 | items2)
            return intersection / union if union > 0 else 0.0
        
        # Для других типов - точное сравнение
        return 1.0 if self._is_exact_duplicate(block1, block2) else 0.0
    
    def _should_update(self, block1: Dict, block2: Dict) -> bool:
        """Определяет, нужно ли обновить существующий блок"""
        # Цена может изменяться - это обновление
        if block1.get('type') == 'price':
            return True
        
        # Галерея может обновляться - это обновление
        if block1.get('type') == 'gallery':
            return True
        
        # Для остальных - не обновлять
        return False
    
    def _normalize_text(self, text: str) -> str:
        """Нормализует текст для сравнения"""
        if not text:
            return ""
        
        # Привести к нижнему регистру
        text = text.lower()
        
        # Удалить лишние пробелы
        text = re.sub(r'\s+', ' ', text)
        
        # Удалить HTML-теги
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()
    
    def _normalize_price(self, price_str: str) -> str:
        """Нормализует цену для сравнения"""
        # Удалить все кроме цифр
        digits = re.sub(r'\D', '', price_str)
        return digits
    
    def _normalize_phone(self, phone_str: str) -> str:
        """Нормализует телефон для сравнения"""
        # Удалить все кроме цифр и +
        phone = re.sub(r'[^\d+]', '', phone_str)
        return phone
    
    def _normalize_email(self, email_str: str) -> str:
        """Нормализует email для сравнения"""
        return email_str.lower().strip()
    
    def _normalize_block(self, block: Dict) -> str:
        """Нормализует весь блок для сравнения"""
        # Создать строковое представление нормализованного блока
        normalized = {}
        for key, value in block.items():
            if isinstance(value, str):
                normalized[key] = self._normalize_text(value)
            elif isinstance(value, list):
                normalized[key] = [self._normalize_text(str(item)) for item in value]
            else:
                normalized[key] = value
        return str(sorted(normalized.items()))
    
    def _extract_block_type(self, text: str) -> str:
        """Извлекает тип блока из текста"""
        text_lower = text.lower()
        if 'black box' in text_lower:
            return 'blackbox'
        elif 'white box' in text_lower:
            return 'whitebox'
        elif 'standard' in text_lower:
            return 'standard'
        elif 'design' in text_lower:
            return 'design'
        return 'unknown'


# Пример использования
class MockKB:
    """Моковая реализация KB для примера"""
    
    def __init__(self):
        self.blocks = {}
    
    def get_block(self, block_id: str) -> Optional[Dict]:
        return self.blocks.get(block_id)
    
    def save_block(self, block_id: str, block: Dict):
        self.blocks[block_id] = block
    
    def update_block(self, block_id: str, block: Dict):
        self.blocks[block_id] = block


if __name__ == "__main__":
    # Создание дедупликатора
    kb = MockKB()
    deduplicator = KBDeduplicator(kb)
    
    # Пример 1: Запись нового блока
    block1 = {
        'type': 'description',
        'content': 'Просторный, уютный дом с качественным ремонтом'
    }
    deduplicator.save_block(block1, 'STANDARD')
    
    # Пример 2: Попытка записать дубликат
    block2 = {
        'type': 'description',
        'content': 'Просторный, уютный дом с качественным ремонтом'  # То же самое
    }
    deduplicator.save_block(block2, 'STANDARD')  # Пропустится как дубликат
    
    # Пример 3: Запись контактов (один раз для всех вкладок)
    contacts = {
        'type': 'contacts',
        'phone': '+7 (988) 199-89-98',
        'email': 'innovatory-club@yandex.ru',
        'address': 'г. Краснодар, хутор Октябрьский'
    }
    deduplicator.save_block(contacts, 'STANDARD')
    deduplicator.save_block(contacts, 'BLACK BOX')  # Пропустится как дубликат
    
    print(f"\nВсего блоков в KB: {len(kb.blocks)}")



