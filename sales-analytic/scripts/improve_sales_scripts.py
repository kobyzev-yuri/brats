#!/usr/bin/env python3
"""
Скрипт для улучшения скриптов продаж на основе успешных диалогов

Использование:
    python scripts/improve_sales_scripts.py [--days 30] [--dry-run]

Описание:
    Анализирует успешные диалоги (привели к КП) и автоматически улучшает
    скрипты продаж в базе знаний на основе успешных паттернов.

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
from collections import Counter

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


class SalesScriptImprovementService:
    """Сервис для улучшения скриптов продаж"""
    
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
    
    async def analyze_conversation_effectiveness(self, days: int = 30) -> Dict[str, List[str]]:
        """
        Анализ эффективности диалогов для улучшения скриптов
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Словарь с паттернами успешных сообщений по этапам
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Получение успешных диалогов (привели к КП)
            successful_conversations = await conn.fetch("""
                SELECT DISTINCT c.id
                FROM conversations c
                JOIN proposals p ON p.conversation_id = c.id
                WHERE c.created_at >= $1
                  AND p.status IN ('sent', 'accepted')
            """, cutoff_date)
            
            if not successful_conversations:
                return {}
            
            conversation_ids = [c["id"] for c in successful_conversations]
            
            # Получение сообщений из успешных диалогов
            successful_messages = await conn.fetch("""
                SELECT m.content, m.metadata
                FROM messages m
                WHERE m.conversation_id = ANY($1)
                  AND m.role = 'assistant'
                  AND m.metadata->>'stage' IS NOT NULL
            """, conversation_ids)
            
            # Анализ паттернов успешных сообщений по этапам
            patterns = {}
            for msg in successful_messages:
                stage = msg["metadata"].get("stage") if isinstance(msg["metadata"], dict) else None
                if not stage:
                    continue
                
                if stage not in patterns:
                    patterns[stage] = []
                
                content = msg["content"]
                if content and len(content) > 10:  # Игнорируем очень короткие сообщения
                    patterns[stage].append(content)
            
            # Подсчет частоты использования фраз в каждом этапе
            stage_patterns = {}
            for stage, messages in patterns.items():
                # Простой анализ: ищем общие фразы (можно улучшить)
                word_freq = Counter()
                for msg in messages:
                    words = msg.lower().split()
                    word_freq.update(words)
                
                # Топ-10 наиболее частых слов/фраз
                top_words = [word for word, count in word_freq.most_common(10) if count >= 2]
                stage_patterns[stage] = {
                    "messages_count": len(messages),
                    "top_phrases": top_words[:5]  # Топ-5 фраз
                }
            
            return stage_patterns
    
    async def update_sales_scripts(self, patterns: Dict, village_id: Optional[int] = None):
        """
        Обновление скриптов продаж на основе успешных паттернов
        
        Args:
            patterns: Паттерны успешных сообщений по этапам
            village_id: ID поселка (опционально)
        """
        if not patterns:
            print("ℹ️  Паттернов для улучшения не найдено")
            return
        
        print(f"📝 Обновление скриптов продаж для {len(patterns)} этапов...")
        
        async with self.db.acquire() as conn:
            for stage, pattern_data in patterns.items():
                if self.dry_run:
                    print(f"  [DRY-RUN] Этап: {stage}")
                    print(f"     Сообщений: {pattern_data['messages_count']}")
                    print(f"     Топ фразы: {', '.join(pattern_data['top_phrases'][:3])}")
                    continue
                
                # Получение текущего скрипта для этапа
                current_script = await conn.fetchrow("""
                    SELECT id, content, metadata
                    FROM knowledge_base
                    WHERE metadata->>'category' = 'sales_script'
                      AND metadata->>'context'->>'stage' = $1
                    LIMIT 1
                """, stage)
                
                if not current_script:
                    print(f"  ℹ️  Скрипт для этапа '{stage}' не найден в KB")
                    continue
                
                # Улучшение скрипта с учётом успешных паттернов
                current_content = current_script["content"]
                top_phrases = ", ".join(pattern_data["top_phrases"][:3])
                
                # Генерация улучшенного скрипта через LLM (если доступен)
                updated_content = current_content
                if self.llm_service:
                    try:
                        prompt = f"""Ты эксперт по продажам недвижимости. Улучши следующий скрипт продаж для этапа '{stage}', учитывая что успешные диалоги часто используют следующие фразы: {top_phrases}.

Текущий скрипт:
{current_content}

Создай улучшенную версию скрипта, которая включает успешные паттерны, но сохраняет структуру и стиль."""
                        
                        response = await self.llm_service.generate_response(
                            messages=[
                                {"role": "system", "content": "Ты эксперт по продажам недвижимости. Улучшай скрипты продаж на основе успешных паттернов."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.7
                        )
                        
                        updated_content = response.get("response", current_content) if isinstance(response, dict) else str(response)
                    except Exception as e:
                        print(f"  ⚠️  Ошибка генерации улучшенного скрипта: {e}")
                        # Используем текущий контент
                
                # Генерация нового embedding
                embedding_str = None
                if self.embedding_service:
                    try:
                        embedding = self.embedding_service.generate_embedding(updated_content)
                        if embedding:
                            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                    except Exception as e:
                        print(f"  ⚠️  Ошибка генерации embedding: {e}")
                
                # Обновление метаданных
                metadata = json.loads(current_script["metadata"]) if isinstance(current_script["metadata"], str) else current_script["metadata"]
                current_version = float(metadata.get("version", "1.0"))
                new_version = current_version + 0.1
                
                metadata["version"] = str(new_version)
                metadata["improved_from_patterns"] = {
                    "stage": stage,
                    "messages_analyzed": pattern_data["messages_count"],
                    "top_phrases": pattern_data["top_phrases"]
                }
                
                # Обновление в KB
                if embedding_str:
                    await conn.execute("""
                        UPDATE knowledge_base
                        SET content = $1, embedding = $2::vector,
                            metadata = $3::jsonb,
                            version = $4,
                            updated_at = NOW()
                        WHERE id = $5
                    """, updated_content, embedding_str, json.dumps(metadata), str(new_version), current_script["id"])
                else:
                    # Если embedding не сгенерирован, обновляем без него
                    await conn.execute("""
                        UPDATE knowledge_base
                        SET content = $1,
                            metadata = $2::jsonb,
                            version = $3,
                            updated_at = NOW()
                        WHERE id = $4
                    """, updated_content, json.dumps(metadata), str(new_version), current_script["id"])
                
                print(f"  ✅ Обновлен скрипт для этапа '{stage}' (версия {new_version})")
    
    async def analyze_and_improve(self, days: int = 30):
        """
        Основная функция анализа и улучшения
        
        Args:
            days: Количество дней для анализа
        """
        print(f"🔍 Анализ успешных диалогов за последние {days} дней...")
        
        patterns = await self.analyze_conversation_effectiveness(days=days)
        
        if patterns:
            print(f"   ✅ Найдены паттерны для {len(patterns)} этапов")
            await self.update_sales_scripts(patterns)
        else:
            print("   ℹ️  Паттернов для улучшения не найдено")
        
        return len(patterns)


async def main():
    parser = argparse.ArgumentParser(
        description="Улучшение скриптов продаж на основе успешных диалогов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Анализ за последние 30 дней (dry-run)
  python scripts/improve_sales_scripts.py --days 30 --dry-run
  
  # Анализ за последние 7 дней с реальным обновлением
  python scripts/improve_sales_scripts.py --days 7
  
  # Указать другой URL KB Service
  KB_API_URL=http://localhost:8001 python scripts/improve_sales_scripts.py
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
        service = SalesScriptImprovementService(
            db_pool=db_pool,
            kb_api_url=args.kb_api_url,
            dry_run=args.dry_run
        )
        
        count = await service.analyze_and_improve(days=args.days)
        
        if args.dry_run:
            print("\n⚠️  Режим dry-run: изменения не были применены")
        else:
            print(f"\n✅ Обработано {count} этапов")
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())













