"""
Сервис для генерации embeddings через OpenAI API или HuggingFace модели
Адаптировано из ~/sql4A/
"""

import os
import logging
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

# Загружаем конфигурацию
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env", override=True)

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Сервис для генерации векторных представлений текста
    Поддерживает OpenAI API и HuggingFace модели через sentence-transformers
    """
    
    def __init__(self):
        """
        Инициализация сервиса embeddings
        """
        self.provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        
        if self.provider == "openai":
            self._init_openai()
        elif self.provider == "huggingface":
            self._init_huggingface()
        else:
            raise ValueError(f"Неизвестный провайдер embeddings: {self.provider}")
    
    def _init_openai(self):
        """Инициализация OpenAI клиента"""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", "60"))
        
        if not self.api_key:
            logger.warning("OPENAI_API_KEY не настроен, embeddings будут недоступны")
            self.client = None
        else:
            from openai import OpenAI

            # Отключаем использование системных proxy-переменных (HTTP(S)_PROXY, ALL_PROXY и т.п.),
            # т.к. они могут указывать на SOCKS-прокси, который httpx не поддерживает.
            for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
                if os.getenv(var):
                    logger.info(f"⚙️  Игнорируем системную proxy-переменную {var} для OpenAI клиента")
                    os.environ.pop(var, None)

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout
            )
            logger.info(f"✅ EmbeddingService (OpenAI) инициализирован (model={self.model}, dimension={self.dimension})")
    
    def _init_huggingface(self):
        """Инициализация HuggingFace модели через sentence-transformers"""
        self.model_name = os.getenv("HF_MODEL_NAME", "intfloat/multilingual-e5-base")
        self.dimension = int(os.getenv("HF_EMBEDDING_DIMENSION", "768"))
        
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Загрузка HuggingFace модели: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            self.client = "hf"  # Маркер для HuggingFace
            logger.info(f"✅ EmbeddingService (HuggingFace) инициализирован (model={self.model_name}, dimension={self.dimension})")
        except ImportError:
            logger.error("sentence-transformers не установлен. Установите: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Ошибка загрузки HuggingFace модели: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Генерирует embedding для одного текста
        
        Args:
            text: Текст для генерации embedding
            
        Returns:
            Список чисел (вектор embedding)
        """
        if self.provider == "openai":
            return self._generate_openai(text)
        elif self.provider == "huggingface":
            return self._generate_huggingface(text)
        else:
            raise ValueError(f"Неизвестный провайдер: {self.provider}")
    
    def _generate_openai(self, text: str) -> List[float]:
        """Генерация embedding через OpenAI API"""
        if not self.client:
            raise ValueError("OpenAI client не инициализирован. Проверьте OPENAI_API_KEY в config.env")
        
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimension
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Ошибка генерации embedding через OpenAI: {e}")
            raise
    
    def _generate_huggingface(self, text: str) -> List[float]:
        """Генерация embedding через HuggingFace модель"""
        if not hasattr(self, 'model') or self.model is None:
            raise ValueError("HuggingFace модель не загружена. Проверьте HF_MODEL_NAME в config.env")
        
        try:
            # Для multilingual-e5-base нужно добавить префикс для запросов
            if "e5" in self.model_name.lower():
                # Для запросов используем префикс "query:"
                text = f"query: {text}"
            
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Ошибка генерации embedding через HuggingFace: {e}")
            raise
    
    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Генерирует embeddings для списка текстов (батчами)
        
        Args:
            texts: Список текстов для генерации embeddings
            batch_size: Размер батча для обработки
            
        Returns:
            Список векторов embeddings
        """
        if self.provider == "openai":
            return self._generate_openai_batch(texts, batch_size)
        elif self.provider == "huggingface":
            return self._generate_huggingface_batch(texts, batch_size)
        else:
            raise ValueError(f"Неизвестный провайдер: {self.provider}")
    
    def _generate_openai_batch(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Генерация embeddings батчами через OpenAI API"""
        if not self.client:
            raise ValueError("OpenAI client не инициализирован. Проверьте OPENAI_API_KEY в config.env")
        
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimension
                )
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
                logger.info(f"Обработано {min(i + batch_size, len(texts))}/{len(texts)} текстов")
            except Exception as e:
                logger.error(f"Ошибка генерации embeddings для батча {i}-{i+len(batch)}: {e}")
                # В случае ошибки добавляем None для этого батча
                embeddings.extend([None] * len(batch))
        
        return embeddings
    
    def _generate_huggingface_batch(self, texts: List[str], batch_size: int) -> List[List[float]]:
        """Генерация embeddings батчами через HuggingFace модель"""
        if not hasattr(self, 'model') or self.model is None:
            raise ValueError("HuggingFace модель не загружена. Проверьте HF_MODEL_NAME в config.env")
        
        embeddings = []
        
        # Для multilingual-e5-base нужно добавить префикс для запросов
        if "e5" in self.model_name.lower():
            texts = [f"query: {text}" for text in texts]
        
        try:
            # sentence-transformers автоматически обрабатывает батчи
            batch_embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=True
            )
            embeddings = [emb.tolist() for emb in batch_embeddings]
            logger.info(f"Обработано {len(texts)} текстов через HuggingFace")
        except Exception as e:
            logger.error(f"Ошибка генерации embeddings через HuggingFace: {e}")
            raise
        
        return embeddings
    
    def is_available(self) -> bool:
        """
        Проверяет доступность сервиса embeddings
        """
        if self.provider == "openai":
            return self.client is not None
        elif self.provider == "huggingface":
            return hasattr(self, 'model') and self.model is not None
        return False

