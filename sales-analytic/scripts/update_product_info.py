#!/usr/bin/env python3
"""
Скрипт для обновления информации о продуктах в KB на основе аналитики

Использование:
    python scripts/update_product_info.py [--days 30] [--min-views 10] [--dry-run]

Описание:
    Анализирует события page_view и question_asked для определения популярных
    объектов и обновляет информацию о них в базе знаний.

Конфигурация:
    Скрипт использует переменные из config.env:
    - DATABASE_URL - подключение к PostgreSQL
    - KB_API_URL - URL KB Service API (по умолчанию http://localhost:8001)

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


class ProductInfoUpdateService:
    """Сервис для обновления информации о продуктах в KB"""
    
    def __init__(self, db_pool: asyncpg.Pool, kb_api_url: str = None, dry_run: bool = False):
        self.db = db_pool
        self.kb_api_url = kb_api_url or os.getenv("KB_API_URL", "http://localhost:8001")
        self.dry_run = dry_run
    
    async def analyze_product_interest(self, days: int = 30, min_views: int = 10) -> Dict:
        """
        Анализ интереса к объектам для обновления KB
        
        Args:
            days: Количество дней для анализа
            min_views: Минимальное количество просмотров
            
        Returns:
            Словарь с популярными объектами и вопросами по ним
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Получение популярных объектов
            popular_products = await conn.fetch("""
                SELECT 
                    event_data->>'product_id' as product_id,
                    event_data->>'product_name' as product_name,
                    COUNT(*) as view_count,
                    AVG((event_data->>'time_on_page')::int) as avg_time
                FROM analytics_events
                WHERE event_type = 'page_view'
                  AND event_data->>'url' LIKE '%product%'
                  AND created_at >= $1
                  AND event_data->>'product_id' IS NOT NULL
                GROUP BY event_data->>'product_id', event_data->>'product_name'
                HAVING COUNT(*) >= $2
                ORDER BY view_count DESC
            """, cutoff_date, min_views)
            
            # Получение вопросов по объектам
            product_questions = await conn.fetch("""
                SELECT 
                    event_data->>'product_id' as product_id,
                    event_data->>'question' as question,
                    COUNT(*) as frequency
                FROM analytics_events
                WHERE event_type = 'question_asked'
                  AND event_data->>'product_id' IS NOT NULL
                  AND created_at >= $1
                GROUP BY event_data->>'product_id', event_data->>'question'
                HAVING COUNT(*) >= 3
            """, cutoff_date)
        
        return {
            "popular_products": [dict(p) for p in popular_products],
            "product_questions": [dict(q) for q in product_questions)]
        }
    
    async def update_product_info_in_kb(self, analysis: Dict, village_id: Optional[int] = None):
        """
        Обновление информации о продуктах в KB на основе аналитики
        
        Args:
            analysis: Результаты анализа (популярные объекты и вопросы)
            village_id: ID поселка (опционально)
        """
        if not analysis["popular_products"]:
            print("ℹ️  Популярных объектов не найдено")
            return
        
        print(f"📝 Обновление информации о {len(analysis['popular_products'])} популярных объектах...")
        
        async with self.db.acquire() as conn:
            for product in analysis["popular_products"]:
                if self.dry_run:
                    print(f"  [DRY-RUN] Объект: {product.get('product_name', 'N/A')} ({product.get('view_count', 0)} просмотров)")
                    continue
                
                product_name = product.get("product_name") or f"Объект {product.get('product_id')}"
                
                # Проверка наличия информации в KB
                existing = await conn.fetchrow("""
                    SELECT id, content, metadata
                    FROM knowledge_base
                    WHERE metadata->>'category' = 'product_info'
                      AND content LIKE $1
                    LIMIT 1
                """, f"%{product_name}%")
                
                if not existing:
                    # Добавление информации о популярном объекте
                    print(f"  ℹ️  Информация об объекте '{product_name}' отсутствует в KB")
                    print(f"     Рекомендуется добавить информацию вручную или через импорт")
                else:
                    # Обновление метаданных (добавление тега "популярный")
                    metadata = json.loads(existing["metadata"]) if isinstance(existing["metadata"], str) else existing["metadata"]
                    tags = metadata.get("tags", [])
                    
                    if "популярный" not in tags:
                        tags.append("популярный")
                        metadata["tags"] = tags
                        metadata["view_count"] = product.get("view_count", 0)
                        metadata["avg_time"] = float(product.get("avg_time", 0))
                        
                        await conn.execute("""
                            UPDATE knowledge_base
                            SET metadata = $1::jsonb, updated_at = NOW()
                            WHERE id = $2
                        """, json.dumps(metadata), existing["id"])
                        
                        print(f"  ✅ Обновлены метаданные для объекта: {product_name}")
                    else:
                        print(f"  ℹ️  Объект '{product_name}' уже помечен как популярный")
                
                # Анализ вопросов по объекту
                product_questions = [
                    q for q in analysis["product_questions"]
                    if q.get("product_id") == product.get("product_id")
                ]
                
                if product_questions:
                    print(f"     Найдено {len(product_questions)} популярных вопросов по объекту")
    
    async def analyze_and_update(self, days: int = 30, min_views: int = 10):
        """
        Основная функция анализа и обновления
        
        Args:
            days: Количество дней для анализа
            min_views: Минимальное количество просмотров
        """
        print(f"🔍 Анализ интереса к объектам за последние {days} дней...")
        print(f"   Минимальное количество просмотров: {min_views}")
        
        analysis = await self.analyze_product_interest(days=days, min_views=min_views)
        
        if analysis["popular_products"]:
            print(f"   ✅ Найдено {len(analysis['popular_products'])} популярных объектов")
            await self.update_product_info_in_kb(analysis)
        else:
            print("   ℹ️  Популярных объектов не найдено")
        
        return len(analysis["popular_products"])


async def main():
    parser = argparse.ArgumentParser(
        description="Обновление информации о продуктах в KB на основе аналитики",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Анализ за последние 30 дней (dry-run)
  python scripts/update_product_info.py --days 30 --min-views 10 --dry-run
  
  # Анализ за последние 7 дней с реальным обновлением
  python scripts/update_product_info.py --days 7 --min-views 5
  
  # Указать другой URL KB Service
  KB_API_URL=http://localhost:8001 python scripts/update_product_info.py
        """
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Количество дней для анализа (по умолчанию: 30)"
    )
    parser.add_argument(
        "--min-views",
        type=int,
        default=10,
        help="Минимальное количество просмотров (по умолчанию: 10)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только анализ, без обновления KB"
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
        service = ProductInfoUpdateService(
            db_pool=db_pool,
            kb_api_url=args.kb_api_url,
            dry_run=args.dry_run
        )
        
        count = await service.analyze_and_update(
            days=args.days,
            min_views=args.min_views
        )
        
        if args.dry_run:
            print("\n⚠️  Режим dry-run: изменения не были применены")
        else:
            print(f"\n✅ Обработано {count} объектов")
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())













