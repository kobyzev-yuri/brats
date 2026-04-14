"""
DLP (Data Loss Prevention) сервис для обезличивания персональных данных
Перед отправкой в зарубежные LLM (GPT-4o через proxyapi.ru)
"""

import re
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional, Union
from copy import deepcopy

logger = logging.getLogger(__name__)


class DLPService:
    """
    Сервис для обезличивания персональных данных перед отправкой в LLM
    """
    
    # Запрещенные ключи, которые должны быть удалены
    FORBIDDEN_KEYS = {
        "phone", "telephone", "mobile", "phone_number",
        "email", "e_mail", "email_address",
        "passport", "passport_number", "passport_series",
        "inn", "tax_id", "tax_number",
        "kpp", "kpp_number",
        "bank_account", "account_number", "bank_account_number",
        "card_number", "credit_card", "card",
        "contract_number", "contract_id",
        "amocrm_lead_id", "amocrm_contact_id", "amocrm_deal_id",
        "visitor_id", "user_id", "client_id",
        "full_name", "first_name", "last_name", "middle_name",
        "address", "postal_address", "home_address",
        "snils", "snils_number",
        "birth_date", "birthday", "date_of_birth"
    }
    
    # Паттерны для маскирования в тексте
    PHONE_PATTERN = re.compile(r'\+?\d[\d\-\s\(\)]{8,}\d')
    EMAIL_PATTERN = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}')
    LONG_NUMBER_PATTERN = re.compile(r'\b\d{10,20}\b')
    PASSPORT_PATTERN = re.compile(r'\d{4}\s?\d{6}')
    INN_PATTERN = re.compile(r'\b\d{10,12}\b')
    CARD_PATTERN = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')
    
    def __init__(self, enable_pseudonymization: bool = True):
        """
        Инициализация DLP сервиса
        
        Args:
            enable_pseudonymization: Включить псевдонимизацию (замена на токены)
        """
        self.enable_pseudonymization = enable_pseudonymization
        self.pseudonym_map: Dict[str, str] = {}  # Хранит маппинг реальных значений на псевдонимы
        logger.info("✅ DLPService инициализирован")
    
    def sanitize_for_llm(self, payload: Union[Dict, List, str, Any]) -> Union[Dict, List, str, Any]:
        """
        Основной метод для обезличивания данных перед отправкой в LLM
        
        Args:
            payload: Данные для обезличивания (dict, list, str или любой другой тип)
            
        Returns:
            Обезличенные данные
        """
        if isinstance(payload, dict):
            return self._sanitize_dict(payload)
        elif isinstance(payload, list):
            return [self.sanitize_for_llm(item) for item in payload]
        elif isinstance(payload, str):
            return self._mask_text(payload)
        else:
            # Для других типов (int, float, bool, None) возвращаем как есть
            return payload
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обезличивание словаря
        """
        sanitized = {}
        
        for key, value in data.items():
            # Проверяем, не является ли ключ запрещенным
            key_lower = key.lower()
            is_forbidden = any(forbidden in key_lower for forbidden in self.FORBIDDEN_KEYS)
            
            if is_forbidden:
                # Удаляем запрещенные ключи
                logger.debug(f"Удален запрещенный ключ: {key}")
                continue
            
            # Обезличиваем значение
            if isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self.sanitize_for_llm(item) for item in value]
            elif isinstance(value, str):
                # Маскируем текст
                sanitized[key] = self._mask_text(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _mask_text(self, text: str) -> str:
        """
        Маскирование чувствительных паттернов в тексте
        """
        if not isinstance(text, str):
            return text
        
        masked = text
        
        # Маскируем телефоны
        masked = self.PHONE_PATTERN.sub("+7 *** ***-**-**", masked)
        
        # Маскируем email
        masked = self.EMAIL_PATTERN.sub("user***@example.com", masked)
        
        # Маскируем паспорта
        masked = self.PASSPORT_PATTERN.sub("**** ******", masked)
        
        # Маскируем ИНН
        masked = self.INN_PATTERN.sub("***", masked)
        
        # Маскируем номера карт
        masked = self.CARD_PATTERN.sub("**** **** **** ****", masked)
        
        # Маскируем длинные номера (счета, договоры и т.д.)
        masked = self.LONG_NUMBER_PATTERN.sub("***", masked)
        
        return masked
    
    def pseudonymize(self, value: str, namespace: str = "default") -> str:
        """
        Псевдонимизация значения (замена на токен)
        
        Args:
            value: Значение для псевдонимизации
            namespace: Пространство имен для токена
            
        Returns:
            Псевдоним (токен)
        """
        if not self.enable_pseudonymization:
            return value
        
        # Создаем уникальный ключ
        key = f"{namespace}:{value}"
        
        # Проверяем, есть ли уже псевдоним
        if key in self.pseudonym_map:
            return self.pseudonym_map[key]
        
        # Генерируем новый псевдоним
        digest = hashlib.sha256(key.encode()).hexdigest()[:8]
        pseudonym = f"{namespace.upper()}_{digest}"
        
        # Сохраняем маппинг
        self.pseudonym_map[key] = pseudonym
        
        logger.debug(f"Псевдонимизация: {value[:20]}... -> {pseudonym}")
        
        return pseudonym
    
    def restore_from_pseudonym(self, pseudonym: str) -> Optional[str]:
        """
        Восстановление реального значения из псевдонима
        
        Args:
            pseudonym: Псевдоним для восстановления
            
        Returns:
            Реальное значение или None, если не найдено
        """
        # Ищем обратный маппинг
        for key, value in self.pseudonym_map.items():
            if value == pseudonym:
                # Извлекаем реальное значение из ключа
                namespace, real_value = key.split(":", 1)
                return real_value
        
        return None
    
    def sanitize_conversation_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Специализированный метод для обезличивания контекста диалога
        
        Args:
            context: Контекст диалога (slots, metadata, и т.д.)
            
        Returns:
            Обезличенный контекст
        """
        sanitized = deepcopy(context)
        
        # Обезличиваем slots
        if "slots" in sanitized:
            sanitized["slots"] = self._sanitize_dict(sanitized["slots"])
        
        # Обезличиваем metadata
        if "metadata" in sanitized:
            sanitized["metadata"] = self._sanitize_dict(sanitized["metadata"])
        
        # Обезличиваем visitor_id, session_id и т.д.
        if "visitor_id" in sanitized:
            sanitized["visitor_id"] = self.pseudonymize(sanitized["visitor_id"], "visitor")
        
        if "session_id" in sanitized:
            sanitized["session_id"] = self.pseudonymize(sanitized["session_id"], "session")
        
        return sanitized
    
    def sanitize_kb_results(self, kb_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Обезличивание результатов поиска в KB
        
        Args:
            kb_results: Результаты поиска из KB
            
        Returns:
            Обезличенные результаты
        """
        sanitized = []
        
        for result in kb_results:
            sanitized_result = {
                "id": result.get("id"),
                "content": self._mask_text(result.get("content", "")),
                "metadata": self._sanitize_dict(result.get("metadata", {})),
                "similarity": result.get("similarity")
            }
            sanitized.append(sanitized_result)
        
        return sanitized
    
    def get_sanitization_report(self) -> Dict[str, Any]:
        """
        Получить отчет об обезличивании (для отладки)
        
        Returns:
            Отчет с количеством псевдонимов и т.д.
        """
        return {
            "pseudonyms_count": len(self.pseudonym_map),
            "pseudonyms": list(self.pseudonym_map.values())[:10]  # Первые 10 для примера
        }


# Глобальный экземпляр для использования в других модулях
_dlp_service: Optional[DLPService] = None


def get_dlp_service() -> DLPService:
    """
    Получить глобальный экземпляр DLP сервиса
    """
    global _dlp_service
    if _dlp_service is None:
        _dlp_service = DLPService(enable_pseudonymization=True)
    return _dlp_service















