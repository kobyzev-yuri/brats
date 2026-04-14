"""
Настройки сервиса аналитики
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8002
    
    # База данных
    database_url: str
    
    # Redis (опционально)
    redis_url: Optional[str] = None
    
    # Яндекс.Метрика
    yandex_metrika_oauth_token: str
    yandex_metrika_counter_id: str = "103165578"
    
    # Пороги для определения горячих лидов
    intent_threshold_critical: float = 0.9
    intent_threshold_high: float = 0.7
    intent_threshold_medium: float = 0.5
    
    # Интервал опроса Realtime API (секунды)
    realtime_polling_interval: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()














