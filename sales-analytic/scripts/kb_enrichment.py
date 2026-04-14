#!/usr/bin/env python3
"""
Скрипт для автоматического обогащения KB из analytics_events

Использование:
    python scripts/kb_enrichment.py [--days 30] [--dry-run]

Описание:
    Анализирует события из analytics_events и автоматически обогащает базу знаний:
    - Обнаруживает новые возражения
    - Анализирует популярные вопросы
    - Обновляет информацию о продуктах
    - Улучшает скрипты продаж

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
    # Если kb-service не установлен, используем прямые вызовы API
    EmbeddingService = None
    LLMService = None


class KBEnrichmentService:
    """Сервис для обогащения KB из analytics_events"""
    
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
                print("   Будет использоваться API KB Service")
        
        if LLMService:
            try:
                self.llm_service = LLMService()
            except Exception as e:
                print(f"⚠️  Не удалось инициализировать LLMService: {e}")
                print("   Будет использоваться API KB Service")
    
    async def discover_new_objections(self, days: int = 30) -> List[Dict]:
        """
        Обнаружение новых возражений из событий для добавления в KB
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Список новых возражений с метаданными
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Получение сообщений с возражениями
            objections = await conn.fetch("""
                SELECT 
                    event_data->>'message' as message,
                    event_data->>'objection_type' as objection_type,
                    COUNT(*) as frequency
                FROM analytics_events
                WHERE event_type = 'objection_detected'
                  AND created_at >= $1
                GROUP BY event_data->>'message', event_data->>'objection_type'
                HAVING COUNT(*) >= 3
                ORDER BY frequency DESC
            """, cutoff_date)
            
            if not objections:
                return []
            
            # Получение существующих возражений из KB
            existing_objections = await conn.fetch("""
                SELECT content
                FROM knowledge_base
                WHERE metadata->>'category' = 'objection_handling'
            """)
            
            existing_texts = {obj["content"].lower() for obj in existing_objections}
            
            # Фильтрация новых возражений (упрощенная проверка)
            new_objections = []
            for obj in objections:
                message_lower = obj["message"].lower() if obj["message"] else ""
                # Простая проверка на дубликаты
                is_new = not any(
                    message_lower in existing.lower() or existing.lower() in message_lower
                    for existing in existing_texts
                )
                
                if is_new:
                    new_objections.append({
                        "message": obj["message"],
                        "type": obj["objection_type"] or "general",
                        "frequency": obj["frequency"]
                    })
        
        return new_objections
    
    async def add_objections_to_kb(self, new_objections: List[Dict], village_id: Optional[int] = None):
        """
        Добавление новых возражений в KB с автоматической генерацией ответов
        
        Args:
            new_objections: Список новых возражений
            village_id: ID поселка (опционально)
        """
        if not new_objections:
            return
        
        print(f"📝 Добавление {len(new_objections)} новых возражений в KB...")
        
        async with self.db.acquire() as conn:
            for obj in new_objections:
                if self.dry_run:
                    print(f"  [DRY-RUN] Возражение: {obj['message'][:50]}...")
                    continue
                
                # Генерация ответа через LLM (если доступен)
                answer = "Ответ будет сгенерирован автоматически."
                if self.llm_service:
                    try:
                        # Используем async метод LLMService
                        response = await self.llm_service.generate_response(
                            messages=[
                                {"role": "system", "content": "Ты опытный продавец недвижимости. Отвечай на возражения клиентов профессионально и убедительно."},
                                {"role": "user", "content": f"Клиент говорит: '{obj['message']}'. Как ответить?"}
                            ],
                            temperature=0.7
                        )
                        answer = response.get("response", answer) if isinstance(response, dict) else str(response)
                    except Exception as e:
                        print(f"  ⚠️  Ошибка генерации ответа: {e}")
                        # Используем заглушку
                        answer = f"Стандартный ответ на возражение: '{obj['message']}'. Необходимо добавить ответ вручную."
                
                # Создание chunk'а для KB
                content = f"""Возражение: "{obj['message']}"

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
                
                # Сохранение в KB
                metadata = {
                    "category": "objection_handling",
                    "subcategory": obj["type"],
                    "target_audience": "end_buyer",
                    "priority": "high" if obj["frequency"] >= 10 else "medium",
                    "tags": ["возражение", obj["type"], "автоматически_обнаружено"],
                    "source": "analytics_events",
                    "frequency": obj["frequency"]
                }
                
                if village_id:
                    metadata["settlement_id"] = village_id
                
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
                
                print(f"  ✅ Добавлено возражение: {obj['message'][:50]}...")
    
    async def enrich_kb_from_analytics(self, days: int = 30):
        """
        Основная функция обогащения KB из analytics_events
        
        Args:
            days: Количество дней для анализа
        """
        print(f"🔍 Анализ analytics_events за последние {days} дней...")
        
        results = {
            "new_objections": 0,
            "new_questions": 0,
            "updated_scripts": 0,
            "updated_products": 0
        }
        
        # 1. Обнаружение новых возражений
        print("\n1️⃣  Обнаружение новых возражений...")
        new_objections = await self.discover_new_objections(days=days)
        if new_objections:
            await self.add_objections_to_kb(new_objections)
            results["new_objections"] = len(new_objections)
            print(f"   ✅ Найдено {len(new_objections)} новых возражений")
        else:
            print("   ℹ️  Новых возражений не найдено")
        
        # 2. Анализ популярных вопросов
        print("\n2️⃣  Анализ популярных вопросов...")
        try:
            # Импортируем модуль динамически
            import importlib.util
            script_path = Path(__file__).parent / "analyze_questions.py"
            spec = importlib.util.spec_from_file_location("analyze_questions", script_path)
            analyze_questions_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(analyze_questions_module)
            
            question_service = analyze_questions_module.QuestionAnalysisService(
                db_pool=self.db,
                kb_api_url=self.kb_api_url,
                dry_run=self.dry_run
            )
            questions_count = await question_service.analyze_and_add_questions(days=days, min_frequency=5)
            results["new_questions"] = questions_count
        except Exception as e:
            print(f"   ⚠️  Ошибка анализа вопросов: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. Обновление информации о продуктах
        print("\n3️⃣  Обновление информации о продуктах...")
        try:
            import importlib.util
            script_path = Path(__file__).parent / "update_product_info.py"
            spec = importlib.util.spec_from_file_location("update_product_info", script_path)
            update_product_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(update_product_module)
            
            product_service = update_product_module.ProductInfoUpdateService(
                db_pool=self.db,
                kb_api_url=self.kb_api_url,
                dry_run=self.dry_run
            )
            products_count = await product_service.analyze_and_update(days=days, min_views=10)
            results["updated_products"] = products_count
        except Exception as e:
            print(f"   ⚠️  Ошибка обновления продуктов: {e}")
            import traceback
            traceback.print_exc()
        
        # 4. Улучшение скриптов продаж
        print("\n4️⃣  Улучшение скриптов продаж...")
        try:
            import importlib.util
            script_path = Path(__file__).parent / "improve_sales_scripts.py"
            spec = importlib.util.spec_from_file_location("improve_sales_scripts", script_path)
            improve_scripts_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(improve_scripts_module)
            
            script_service = improve_scripts_module.SalesScriptImprovementService(
                db_pool=self.db,
                kb_api_url=self.kb_api_url,
                dry_run=self.dry_run
            )
            scripts_count = await script_service.analyze_and_improve(days=days)
            results["updated_scripts"] = scripts_count
        except Exception as e:
            print(f"   ⚠️  Ошибка улучшения скриптов: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n📊 Результаты обогащения KB:")
        for key, value in results.items():
            print(f"   {key}: {value}")
        
        return results


async def main():
    parser = argparse.ArgumentParser(
        description="Обогащение KB из analytics_events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Анализ за последние 30 дней (dry-run)
  python scripts/kb_enrichment.py --days 30 --dry-run
  
  # Анализ за последние 7 дней с реальным добавлением в KB
  python scripts/kb_enrichment.py --days 7
  
  # Указать другой URL KB Service
  KB_API_URL=http://localhost:8001 python scripts/kb_enrichment.py
        """
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Количество дней для анализа (по умолчанию: 30)"
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
        service = KBEnrichmentService(
            db_pool=db_pool,
            kb_api_url=args.kb_api_url,
            dry_run=args.dry_run
        )
        
        results = await service.enrich_kb_from_analytics(days=args.days)
        
        if args.dry_run:
            print("\n⚠️  Режим dry-run: изменения не были применены")
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())

