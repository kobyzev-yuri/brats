#!/usr/bin/env python3
"""
Скрипт для анализа популярных вопросов и добавления ответов в KB

Использование:
    python scripts/analyze_questions.py [--days 30] [--min-frequency 5] [--dry-run]

Описание:
    Анализирует события question_asked из analytics_events и автоматически
    добавляет ответы на популярные вопросы в базу знаний.

Конфигурация:
    Скрипт использует переменные из config.env:
    - DATABASE_URL - подключение к PostgreSQL
    - KB_API_URL - URL KB Service API (по умолчанию http://localhost:8001)
    - OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL - для LLM
    - EMBEDDING_PROVIDER, EMBEDDING_MODEL или HF_MODEL_NAME - для embeddings

См. также:
    - docs/CONFIGURATION_REFERENCE.md - справочник по конфигурации
    - docs/ANALYTICS_EVENTS_FOR_KB.md - подробное описание процесса
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "sales-analytic"))

import asyncpg
from dotenv import load_dotenv

# Загружаем конфигурацию
load_dotenv(project_root / "config.env")
load_dotenv(project_root / "kb-service" / "config.env")

# Импорты из kb-service (если доступны)
try:
    from kb_service.services.embedding_service import EmbeddingService
    from kb_service.services.llm_service import LLMService
except ImportError:
    EmbeddingService = None
    LLMService = None


class QuestionAnalysisService:
    """Сервис для анализа популярных вопросов"""
    
    def __init__(self, db_pool: asyncpg.Pool, kb_api_url: str = None, dry_run: bool = False):
        self.db = db_pool
        self.kb_api_url = kb_api_url or os.getenv("KB_API_URL", "http://localhost:8001")
        self.dry_run = dry_run
        
        # Инициализация сервисов (если доступны)
        self.embedding_service = None
        self.llm_service = None
        
        if EmbeddingService:
            try:
                self.embedding_service = EmbeddingService()
            except Exception as e:
                print(f"⚠️  Не удалось инициализировать EmbeddingService: {e}")
        
        if LLMService:
            try:
                self.llm_service = LLMService()
            except Exception as e:
                print(f"⚠️  Не удалось инициализировать LLMService: {e}")
    
    async def analyze_frequent_questions(self, days: int = 30, min_frequency: int = 5) -> List[Dict]:
        """
        Анализ популярных вопросов для добавления в KB
        
        Args:
            days: Количество дней для анализа
            min_frequency: Минимальная частота вопроса для включения
            
        Returns:
            Список популярных вопросов с метаданными
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Получение вопросов из событий
            questions = await conn.fetch("""
                SELECT 
                    event_data->>'question' as question,
                    event_data->>'category' as category,
                    COUNT(*) as frequency
                FROM analytics_events
                WHERE event_type = 'question_asked'
                  AND created_at >= $1
                  AND event_data->>'question' IS NOT NULL
                  AND event_data->>'question' != ''
                GROUP BY event_data->>'question', event_data->>'category'
                HAVING COUNT(*) >= $2
                ORDER BY frequency DESC
            """, cutoff_date, min_frequency)
            
            if not questions:
                return []
            
            # Получение существующих вопросов из KB
            existing_questions = await conn.fetch("""
                SELECT content
                FROM knowledge_base
                WHERE metadata->>'category' IN ('product_info', 'contacts', 'pricing', 'general')
            """)
            
            existing_texts = {q["content"].lower() for q in existing_questions}
            
            # Фильтрация новых вопросов
            new_questions = []
            for q in questions:
                question_lower = q["question"].lower() if q["question"] else ""
                # Простая проверка на дубликаты
                is_new = not any(
                    question_lower in existing.lower() or existing.lower() in question_lower
                    for existing in existing_texts
                )
                
                if is_new:
                    new_questions.append({
                        "question": q["question"],
                        "category": q["category"] or "product_info",
                        "frequency": q["frequency"]
                    })
        
        return new_questions
    
    async def get_relevant_kb_context(self, question: str, limit: int = 3) -> str:
        """
        Получение релевантного контекста из KB для ответа на вопрос
        
        Args:
            question: Текст вопроса
            limit: Количество релевантных chunks
            
        Returns:
            Контекст из KB
        """
        async with self.db.acquire() as conn:
            # Простой поиск по ключевым словам (можно улучшить векторным поиском)
            results = await conn.fetch("""
                SELECT content
                FROM knowledge_base
                WHERE content ILIKE '%' || $1 || '%'
                   OR content ILIKE '%' || $2 || '%'
                LIMIT $3
            """, question, question.split()[0] if question.split() else "", limit)
            
            if results:
                return "\n".join([r["content"] for r in results])
            return ""
    
    async def add_questions_to_kb(self, new_questions: List[Dict], village_id: Optional[int] = None):
        """
        Добавление ответов на популярные вопросы в KB
        
        Args:
            new_questions: Список новых вопросов
            village_id: ID поселка (опционально)
        """
        if not new_questions:
            return
        
        print(f"📝 Добавление {len(new_questions)} ответов на популярные вопросы в KB...")
        
        async with self.db.acquire() as conn:
            for q in new_questions:
                if self.dry_run:
                    print(f"  [DRY-RUN] Вопрос: {q['question'][:50]}...")
                    continue
                
                # Получение релевантного контекста из KB
                kb_context = await self.get_relevant_kb_context(q["question"])
                
                # Генерация ответа через LLM (если доступен)
                answer = "Ответ будет сгенерирован автоматически."
                if self.llm_service:
                    try:
                        system_prompt = "Ты продавец недвижимости. Отвечай на вопросы клиентов, используя информацию из базы знаний."
                        user_prompt = f"Контекст из KB:\n{kb_context}\n\nВопрос клиента: {q['question']}\n\nДай полный ответ."
                        
                        response = await self.llm_service.generate_response(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.7
                        )
                        answer = response.get("response", answer) if isinstance(response, dict) else str(response)
                    except Exception as e:
                        print(f"  ⚠️  Ошибка генерации ответа: {e}")
                        answer = f"Ответ на вопрос: '{q['question']}'. Необходимо добавить ответ вручную."
                
                # Создание chunk'а
                content = f"""Вопрос: {q['question']}

Ответ:
{answer}"""
                
                # Генерация embedding (если доступен сервис)
                embedding_str = None
                if self.embedding_service:
                    try:
                        embedding = self.embedding_service.generate_embedding(content)
                        if embedding:
                            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                    except Exception as e:
                        print(f"  ⚠️  Ошибка генерации embedding: {e}")
                
                # Метаданные
                metadata = {
                    "category": q["category"],
                    "subcategory": "frequent_questions",
                    "target_audience": "end_buyer",
                    "priority": "high" if q["frequency"] >= 20 else "medium",
                    "tags": ["вопрос", "часто_задаваемый", "автоматически_добавлено"],
                    "source": "analytics_events",
                    "frequency": q["frequency"]
                }
                
                if village_id:
                    metadata["settlement_id"] = village_id
                
                # Сохранение в KB
                if embedding_str:
                    await conn.execute("""
                        INSERT INTO knowledge_base (
                            content, embedding, metadata, version, village_id
                        )
                        VALUES ($1, $2::vector, $3::jsonb, '1.0', $4)
                    """, content, embedding_str, json.dumps(metadata), village_id)
                else:
                    # Если embedding не сгенерирован, используем API KB Service
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.kb_api_url}/api/kb/add",
                            json={
                                "content": content,
                                "metadata": metadata,
                                "version": "1.0",
                                "village_id": village_id
                            }
                        )
                        if response.status_code != 200:
                            print(f"  ❌ Ошибка добавления в KB: {response.text}")
                
                print(f"  ✅ Добавлен ответ на вопрос: {q['question'][:50]}...")
    
    async def analyze_and_add_questions(self, days: int = 30, min_frequency: int = 5):
        """
        Основная функция анализа и добавления вопросов
        
        Args:
            days: Количество дней для анализа
            min_frequency: Минимальная частота вопроса
        """
        print(f"🔍 Анализ популярных вопросов за последние {days} дней...")
        print(f"   Минимальная частота: {min_frequency}")
        
        new_questions = await self.analyze_frequent_questions(days=days, min_frequency=min_frequency)
        
        if new_questions:
            print(f"   ✅ Найдено {len(new_questions)} новых популярных вопросов")
            await self.add_questions_to_kb(new_questions)
        else:
            print("   ℹ️  Новых популярных вопросов не найдено")
        
        return len(new_questions)


async def main():
    parser = argparse.ArgumentParser(
        description="Анализ популярных вопросов и добавление ответов в KB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Анализ за последние 30 дней (dry-run)
  python scripts/analyze_questions.py --days 30 --min-frequency 5 --dry-run
  
  # Анализ за последние 7 дней с реальным добавлением в KB
  python scripts/analyze_questions.py --days 7 --min-frequency 3
  
  # Указать другой URL KB Service
  KB_API_URL=http://localhost:8001 python scripts/analyze_questions.py
        """
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Количество дней для анализа (по умолчанию: 30)"
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=5,
        help="Минимальная частота вопроса для включения (по умолчанию: 5)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только анализ, без добавления в KB"
    )
    parser.add_argument(
        "--kb-api-url",
        type=str,
        default=None,
        help="URL KB Service API (по умолчанию из KB_API_URL или http://localhost:8001)"
    )
    
    args = parser.parse_args()
    
    # Подключение к БД
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Ошибка: DATABASE_URL не установлен в config.env")
        sys.exit(1)
    
    print("🔌 Подключение к базе данных...")
    db_pool = await asyncpg.create_pool(database_url)
    
    try:
        service = QuestionAnalysisService(
            db_pool=db_pool,
            kb_api_url=args.kb_api_url,
            dry_run=args.dry_run
        )
        
        count = await service.analyze_and_add_questions(
            days=args.days,
            min_frequency=args.min_frequency
        )
        
        if args.dry_run:
            print("\n⚠️  Режим dry-run: изменения не были применены")
        else:
            print(f"\n✅ Обработано {count} вопросов")
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())













