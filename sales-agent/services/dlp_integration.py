"""
Интеграция DLP сервиса для нейропродажника
Переиспользование DLP из kb-service
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Добавляем путь к kb-service для импорта DLP
KB_SERVICE_PATH = Path(__file__).resolve().parent.parent.parent / "kb-service"
if KB_SERVICE_PATH.exists():
    sys.path.insert(0, str(KB_SERVICE_PATH))
    try:
        from services.dlp_service import get_dlp_service
        DLP_AVAILABLE = True
    except ImportError:
        logging.warning("DLP сервис недоступен. Убедитесь, что kb-service установлен.")
        DLP_AVAILABLE = False
        get_dlp_service = None
else:
    logging.warning(f"kb-service не найден по пути: {KB_SERVICE_PATH}")
    DLP_AVAILABLE = False
    get_dlp_service = None

logger = logging.getLogger(__name__)


class SalesAgentDLP:
    """
    Обёртка DLP сервиса для нейропродажника
    Переиспользует DLP из kb-service
    """
    
    def __init__(self):
        """
        Инициализация DLP для нейропродажника
        """
        if not DLP_AVAILABLE:
            raise RuntimeError(
                "DLP сервис недоступен. "
                "Убедитесь, что kb-service установлен и доступен."
            )
        
        self.dlp = get_dlp_service()
        logger.info("✅ SalesAgentDLP инициализирован (использует DLP из kb-service)")
    
    def sanitize_conversation_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обезличивание слотов диалога
        
        Args:
            slots: Слоты диалога с персональными данными
            
        Returns:
            Обезличенные слоты
        """
        if not slots:
            return {}
        
        sanitized_context = self.dlp.sanitize_conversation_context({
            "slots": slots
        })
        
        return sanitized_context.get("slots", {})
    
    def sanitize_message(self, message: str) -> str:
        """
        Обезличивание текста сообщения
        
        Args:
            message: Текст сообщения (может содержать ПДн)
            
        Returns:
            Обезличенный текст
        """
        if not message:
            return ""
        
        return self.dlp._mask_text(message)
    
    def sanitize_amocrm_data(self, amocrm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обезличивание данных из amoCRM
        
        Args:
            amocrm_data: Данные из amoCRM (lead, contact, deal)
            
        Returns:
            Обезличенные данные
        """
        if not amocrm_data:
            return {}
        
        return self.dlp.sanitize_for_llm(amocrm_data)
    
    def sanitize_conversation_context(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Обезличивание полного контекста диалога
        
        Args:
            context: Контекст диалога (slots, metadata, visitor_id и т.д.)
            
        Returns:
            Обезличенный контекст
        """
        if not context:
            return {}
        
        return self.dlp.sanitize_conversation_context(context)
    
    def sanitize_for_llm(self, data: Any) -> Any:
        """
        Универсальный метод обезличивания для любых данных
        
        Args:
            data: Данные для обезличивания (dict, list, str)
            
        Returns:
            Обезличенные данные
        """
        return self.dlp.sanitize_for_llm(data)


# Глобальный экземпляр
_sales_agent_dlp: Optional[SalesAgentDLP] = None


def get_sales_agent_dlp() -> SalesAgentDLP:
    """
    Получить глобальный экземпляр DLP для нейропродажника
    """
    global _sales_agent_dlp
    if _sales_agent_dlp is None:
        _sales_agent_dlp = SalesAgentDLP()
    return _sales_agent_dlp















