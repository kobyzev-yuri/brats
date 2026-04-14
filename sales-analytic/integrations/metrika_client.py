"""
Клиент для работы с API Яндекс.Метрики
"""
import os
import httpx
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class YandexMetrikaClient:
    """Клиент для работы с API Яндекс.Метрики"""
    
    def __init__(self):
        self.counter_id = os.getenv("YANDEX_METRIKA_COUNTER_ID", "103165578")
        self.oauth_token = os.getenv("YANDEX_METRIKA_OAUTH_TOKEN")
        self.base_url = "https://api-metrika.yandex.net/management/v1"
        
        if not self.oauth_token:
            raise ValueError("YANDEX_METRIKA_OAUTH_TOKEN not set")
    
    async def get_counter_info(self) -> Dict:
        """
        Получить информацию о счётчике (для проверки доступа)
        
        Returns:
            Dict с информацией о счётчике
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_realtime_visitors(self) -> Dict:
        """
        Получить онлайн посетителей
        
        Returns:
            Dict с данными о посетителях
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/realtime",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            response.raise_for_status()
            return response.json()
    
    async def get_counters_list(self) -> List[Dict]:
        """
        Получить список всех доступных счётчиков для этого токена
        
        Returns:
            List[Dict] со списком счётчиков
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counters",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("counters", [])
    
    async def get_goals(self) -> List[Dict]:
        """Получить список целей"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/goals",
                headers={"Authorization": f"OAuth {self.oauth_token}"}
            )
            response.raise_for_status()
            return response.json().get("goals", [])
    
    async def get_conversions(
        self,
        date_from: str,
        date_to: str,
        metrics: Optional[List[str]] = None,
    ) -> Dict:
        """
        Получить статистику за период через stat API.

        Args:
            date_from: Дата начала (YYYY-MM-DD)
            date_to: Дата окончания (YYYY-MM-DD)
            metrics: Список метрик (опционально)

        Returns:
            Dict с данными о статистике
        """
        if metrics is None:
            metrics = ["ym:s:visits", "ym:s:pageviews"]

        # stat API: https://api-metrika.yandex.net/stat/v1/data
        url = "https://api-metrika.yandex.net/stat/v1/data"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"OAuth {self.oauth_token}",
                    "Content-Type": "application/json",
                },
                params={
                    "ids": self.counter_id,
                    "date1": date_from,
                    "date2": date_to,
                    "metrics": ",".join(metrics),
                },
            )

            response.raise_for_status()
            return response.json()
    
    async def get_clickmap_data(
        self,
        date_from: str,
        date_to: str
    ) -> Dict:
        """Получить данные карты кликов"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/counter/{self.counter_id}/clmap",
                headers={"Authorization": f"OAuth {self.oauth_token}"},
                params={
                    "date1": date_from,
                    "date2": date_to
                }
            )
            response.raise_for_status()
            return response.json()



