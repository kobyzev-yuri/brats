"""
Сервис для разбиения текста на chunks с умными границами
Адаптировано из ~/sql4A/
"""

import os
import re
import logging
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / "config.env", override=True)

logger = logging.getLogger(__name__)


class ChunkingService:
    """
    Сервис для разбиения текста на chunks с сохранением контекста
    """
    
    def __init__(self):
        """
        Инициализация сервиса chunking
        """
        self.use_smart_boundaries = os.getenv("CHUNK_USE_SMART_BOUNDARIES", "true").lower() == "true"
        logger.info(f"✅ ChunkingService инициализирован (smart_boundaries={self.use_smart_boundaries})")
    
    def chunk_text(
        self,
        text: str,
        chunk_size: int = 3000,
        chunk_overlap: int = 300,
        category: str = "documentation"
    ) -> List[Dict[str, Any]]:
        """
        Разбивает текст на chunks с умными границами
        
        Args:
            text: Текст для разбиения
            chunk_size: Максимальный размер chunk (в символах)
            chunk_overlap: Перекрытие между chunks (в символах)
            category: Категория контента (для выбора стратегии chunking)
            
        Returns:
            Список словарей с полями: content, start_pos, end_pos
        """
        if not text or len(text.strip()) == 0:
            return []
        
        chunks = []
        
        if self.use_smart_boundaries:
            chunks = self._chunk_with_smart_boundaries(text, chunk_size, chunk_overlap)
        else:
            chunks = self._chunk_simple(text, chunk_size, chunk_overlap)
        
        logger.info(f"Текст разбит на {len(chunks)} chunks (размер: {chunk_size}, overlap: {chunk_overlap})")
        return chunks
    
    def _chunk_with_smart_boundaries(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int
    ) -> List[Dict[str, any]]:
        """
        Разбиение с умными границами (по предложениям и абзацам)
        """
        chunks = []
        current_pos = 0
        text_length = len(text)
        
        # Разбиваем на абзацы
        paragraphs = re.split(r'\n\s*\n', text)
        
        current_chunk = ""
        current_start = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Если абзац помещается в текущий chunk
            if len(current_chunk) + len(para) + 1 <= chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                    current_start = text.find(para, current_pos)
            else:
                # Сохраняем текущий chunk
                if current_chunk:
                    chunks.append({
                        "content": current_chunk.strip(),
                        "start_pos": current_start,
                        "end_pos": current_start + len(current_chunk)
                    })
                
                # Если абзац сам по себе больше chunk_size, разбиваем по предложениям
                if len(para) > chunk_size:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    current_chunk = ""
                    current_start = text.find(para, current_pos)
                    
                    for sent in sentences:
                        if len(current_chunk) + len(sent) + 1 <= chunk_size:
                            if current_chunk:
                                current_chunk += " " + sent
                            else:
                                current_chunk = sent
                        else:
                            if current_chunk:
                                chunks.append({
                                    "content": current_chunk.strip(),
                                    "start_pos": current_start,
                                    "end_pos": current_start + len(current_chunk)
                                })
                            current_chunk = sent
                            current_start = text.find(sent, current_pos)
                else:
                    # Абзац помещается в один chunk
                    current_chunk = para
                    current_start = text.find(para, current_pos)
            
            current_pos = text.find(para, current_pos) + len(para)
        
        # Добавляем последний chunk
        if current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "start_pos": current_start,
                "end_pos": current_start + len(current_chunk)
            })
        
        # Применяем overlap между соседними chunks
        if chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks, text, chunk_overlap)
        
        return chunks
    
    def _chunk_simple(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int
    ) -> List[Dict[str, any]]:
        """
        Простое разбиение по фиксированному размеру
        """
        chunks = []
        current_pos = 0
        text_length = len(text)
        
        while current_pos < text_length:
            chunk_end = min(current_pos + chunk_size, text_length)
            chunk_text = text[current_pos:chunk_end]
            
            chunks.append({
                "content": chunk_text.strip(),
                "start_pos": current_pos,
                "end_pos": chunk_end
            })
            
            # Перемещаемся с учетом overlap
            current_pos = chunk_end - chunk_overlap
            if current_pos >= text_length:
                break
        
        return chunks
    
    def _apply_overlap(
        self,
        chunks: List[Dict[str, any]],
        text: str,
        overlap: int
    ) -> List[Dict[str, any]]:
        """
        Применяет overlap между соседними chunks
        """
        if len(chunks) <= 1:
            return chunks
        
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            start_pos = chunk["start_pos"]
            end_pos = chunk["end_pos"]
            
            # Добавляем overlap с предыдущим chunk (если есть)
            if i > 0:
                prev_end = chunks[i-1]["end_pos"]
                overlap_start = max(start_pos - overlap, 0)
                if overlap_start < start_pos:
                    overlap_text = text[overlap_start:start_pos]
                    chunk["content"] = overlap_text + chunk["content"]
                    chunk["start_pos"] = overlap_start
            
            # Добавляем overlap со следующим chunk (если есть)
            if i < len(chunks) - 1:
                next_start = chunks[i+1]["start_pos"]
                overlap_end = min(end_pos + overlap, len(text))
                if overlap_end > end_pos:
                    overlap_text = text[end_pos:overlap_end]
                    chunk["content"] = chunk["content"] + overlap_text
                    chunk["end_pos"] = overlap_end
            
            overlapped_chunks.append(chunk)
        
        return overlapped_chunks

