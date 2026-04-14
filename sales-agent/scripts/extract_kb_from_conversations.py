#!/usr/bin/env python3
"""
Скрипт для извлечения знаний из диалогов и добавления в KB

Использование:
    python scripts/extract_kb_from_conversations.py [--days 30] [--min-success-rate 0.7] [--dry-run]

Описание:
    Анализирует успешные диалоги (привели к КП/сделке) и автоматически извлекает
    полезную информацию для обогащения базы знаний (KB):
    - Эффективные ответы на вопросы
    - Успешные паттерны обработки возражений
    - Улучшенные скрипты продаж по этапам FSM

Конфигурация:
    Скрипт использует переменные из config.env:
    - DATABASE_URL - подключение к PostgreSQL
    - KB_API_URL - URL KB Service API (по умолчанию http://localhost:8001)
    - OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL - для LLM
    - EMBEDDING_PROVIDER, EMBEDDING_MODEL или HF_MODEL_NAME - для embeddings

См. также:
    - docs/CONFIGURATION_REFERENCE.md - справочник по конфигурации
    - BUSINESS_PROCESSES.md - описание FSM состояний и процессов
    - sales-analytic/scripts/kb_enrichment.py - аналогичный скрипт для analytics_events
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "sales-agent"))

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


class KBExtractionService:
    """Сервис для извлечения знаний из диалогов"""
    
    # FSM состояния согласно BUSINESS_PROCESSES.md
    FSM_STATES = [
        "GREETING",
        "QUALIFYING", 
        "OBJECTIONS",
        "PROPOSAL",
        "NEGOTIATING",
        "FINALIZED",
        "CONTRACT",
        "COMPLETED",
        "HANDOFF"
    ]
    
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
    
    async def get_successful_conversations(
        self, 
        days: int = 30, 
        min_success_rate: float = 0.7
    ) -> List[Dict]:
        """
        Получение успешных диалогов (привели к КП/сделке)
        
        Args:
            days: Количество дней для анализа
            min_success_rate: Минимальный показатель успешности (0.0-1.0)
            
        Returns:
            Список успешных диалогов с метаданными
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Получаем диалоги, которые привели к КП или сделке
            conversations = await conn.fetch("""
                SELECT 
                    c.id,
                    c.state,
                    c.slots,
                    c.channel,
                    c.settlement_id,
                    c.created_at,
                    c.updated_at,
                    COUNT(DISTINCT p.id) as proposal_count,
                    MAX(CASE WHEN p.status IN ('sent', 'accepted', 'finalized') THEN 1 ELSE 0 END) as has_successful_proposal
                FROM conversations c
                LEFT JOIN proposals p ON p.conversation_id = c.id
                WHERE c.created_at >= $1
                  AND c.state NOT IN ('HANDOFF', 'GREETING')
                GROUP BY c.id, c.state, c.slots, c.channel, c.settlement_id, c.created_at, c.updated_at
                HAVING COUNT(DISTINCT p.id) > 0
                   OR c.state IN ('FINALIZED', 'CONTRACT', 'COMPLETED')
                ORDER BY c.created_at DESC
            """, cutoff_date)
            
            successful = []
            for conv in conversations:
                # Определяем успешность диалога
                has_proposal = conv["proposal_count"] > 0
                has_successful = conv["has_successful_proposal"] == 1
                final_state = conv["state"] in ["FINALIZED", "CONTRACT", "COMPLETED"]
                
                success_score = 0.0
                if has_successful:
                    success_score = 1.0
                elif has_proposal:
                    success_score = 0.5
                elif final_state:
                    success_score = 0.8
                
                if success_score >= min_success_rate:
                    successful.append({
                        "id": conv["id"],
                        "state": conv["state"],
                        "slots": conv["slots"] if isinstance(conv["slots"], dict) else json.loads(conv["slots"] or "{}"),
                        "channel": conv["channel"],
                        "settlement_id": conv["settlement_id"],
                        "created_at": conv["created_at"],
                        "success_score": success_score
                    })
        
        return successful
    
    async def get_conversation_messages(self, conversation_id: int) -> List[Dict]:
        """
        Получение сообщений из диалога
        
        Args:
            conversation_id: ID диалога
            
        Returns:
            Список сообщений с ролями и контентом
        """
        async with self.db.acquire() as conn:
            messages = await conn.fetch("""
                SELECT 
                    role,
                    content,
                    metadata,
                    created_at
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
            """, conversation_id)
            
            return [
                {
                    "role": msg["role"],
                    "content": msg["content"],
                    "metadata": msg["metadata"] if isinstance(msg["metadata"], dict) else json.loads(msg["metadata"] or "{}"),
                    "created_at": msg["created_at"]
                }
                for msg in messages
            ]
    
    async def extract_successful_patterns(
        self, 
        conversations: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Извлечение успешных паттернов из диалогов
        
        Args:
            conversations: Список успешных диалогов
            
        Returns:
            Словарь с паттернами по категориям
        """
        patterns = {
            "greeting": [],
            "qualifying": [],
            "objection_handling": [],
            "proposal_presentation": [],
            "negotiation": []
        }
        
        for conv in conversations[:50]:  # Ограничиваем для производительности
            messages = await self.get_conversation_messages(conv["id"])
            
            # Группируем сообщения по этапам FSM
            state_messages = {}
            current_state = "GREETING"
            
            for msg in messages:
                if msg["role"] == "assistant":
                    # Определяем этап по состоянию диалога или метаданным
                    msg_state = msg["metadata"].get("state") or current_state
                    if msg_state not in state_messages:
                        state_messages[msg_state] = []
                    state_messages[msg_state].append(msg["content"])
            
            # Извлекаем паттерны по этапам
            if "GREETING" in state_messages and state_messages["GREETING"]:
                patterns["greeting"].append({
                    "conversation_id": conv["id"],
                    "messages": state_messages["GREETING"],
                    "success_score": conv["success_score"]
                })
            
            if "QUALIFYING" in state_messages and state_messages["QUALIFYING"]:
                patterns["qualifying"].append({
                    "conversation_id": conv["id"],
                    "messages": state_messages["QUALIFYING"],
                    "success_score": conv["success_score"]
                })
            
            # Обработка возражений
            objection_messages = [
                msg for msg in messages 
                if msg["role"] == "assistant" and "возражен" in msg["content"].lower()
            ]
            if objection_messages:
                patterns["objection_handling"].append({
                    "conversation_id": conv["id"],
                    "messages": [m["content"] for m in objection_messages],
                    "success_score": conv["success_score"]
                })
        
        return patterns
    
    async def add_patterns_to_kb(
        self, 
        patterns: Dict[str, List[Dict]], 
        village_id: Optional[int] = None
    ):
        """
        Добавление извлеченных паттернов в KB
        
        Args:
            patterns: Словарь с паттернами по категориям
            village_id: ID поселка (опционально)
        """
        if not patterns:
            return
        
        print(f"📝 Добавление извлеченных паттернов в KB...")
        
        async with self.db.acquire() as conn:
            for category, pattern_list in patterns.items():
                if not pattern_list:
                    continue
                
                # Берем топ-3 наиболее успешных паттерна
                top_patterns = sorted(
                    pattern_list, 
                    key=lambda x: x["success_score"], 
                    reverse=True
                )[:3]
                
                for pattern in top_patterns:
                    if self.dry_run:
                        print(f"  [DRY-RUN] {category}: {len(pattern['messages'])} сообщений")
                        continue
                    
                    # Формируем контент для KB
                    content = "\n\n".join(pattern["messages"])
                    
                    # Генерация улучшенного текста через LLM (если доступен)
                    if self.llm_service and len(content) > 100:
                        try:
                            prompt = f"""Ты эксперт по продажам недвижимости. Улучши следующий текст для использования в базе знаний как пример успешного взаимодействия на этапе '{category}'.

Исходный текст:
{content}

Создай улучшенную версию, которая может быть использована как шаблон для других диалогов."""
                            
                            response = await self.llm_service.generate_response(
                                messages=[
                                    {"role": "system", "content": "Ты эксперт по продажам недвижимости. Улучшай тексты для базы знаний."},
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=0.7
                            )
                            
                            improved_content = response.get("response", content) if isinstance(response, dict) else str(response)
                            content = improved_content
                        except Exception as e:
                            print(f"  ⚠️  Ошибка улучшения текста: {e}")
                    
                    # Генерация embedding
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
                        "category": "sales_script" if category != "objection_handling" else "objection_handling",
                        "subcategory": category,
                        "target_audience": "end_buyer",
                        "priority": "high" if pattern["success_score"] >= 0.8 else "medium",
                        "tags": ["успешный_паттерн", category, "извлечено_из_диалогов"],
                        "source": "conversations",
                        "success_score": pattern["success_score"],
                        "conversation_id": pattern["conversation_id"]
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
                            ON CONFLICT DO NOTHING
                        """, content, embedding_str, json.dumps(metadata), village_id)
                    else:
                        # Используем API KB Service
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
                    
                    print(f"  ✅ Добавлен паттерн {category} (score: {pattern['success_score']:.2f})")
    
    async def extract_and_add_to_kb(
        self, 
        days: int = 30, 
        min_success_rate: float = 0.7
    ):
        """
        Основная функция извлечения и добавления в KB
        
        Args:
            days: Количество дней для анализа
            min_success_rate: Минимальный показатель успешности
        """
        print(f"🔍 Анализ успешных диалогов за последние {days} дней...")
        print(f"   Минимальный показатель успешности: {min_success_rate}")
        
        # Получаем успешные диалоги
        successful_conversations = await self.get_successful_conversations(
            days=days,
            min_success_rate=min_success_rate
        )
        
        if not successful_conversations:
            print("   ℹ️  Успешных диалогов не найдено")
            return 0
        
        print(f"   ✅ Найдено {len(successful_conversations)} успешных диалогов")
        
        # Извлекаем паттерны
        print("\n📊 Извлечение успешных паттернов...")
        patterns = await self.extract_successful_patterns(successful_conversations)
        
        # Добавляем в KB
        await self.add_patterns_to_kb(patterns)
        
        total_added = sum(len(p) for p in patterns.values())
        return total_added


async def main():
    parser = argparse.ArgumentParser(
        description="Извлечение знаний из диалогов и добавление в KB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Анализ за последние 30 дней (dry-run)
  python scripts/extract_kb_from_conversations.py --days 30 --min-success-rate 0.7 --dry-run
  
  # Анализ за последние 7 дней с реальным добавлением в KB
  python scripts/extract_kb_from_conversations.py --days 7 --min-success-rate 0.8
  
  # Указать другой URL KB Service
  KB_API_URL=http://localhost:8001 python scripts/extract_kb_from_conversations.py
        """
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Количество дней для анализа (по умолчанию: 30)"
    )
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=0.7,
        help="Минимальный показатель успешности (0.0-1.0, по умолчанию: 0.7)"
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
        service = KBExtractionService(
            db_pool=db_pool,
            kb_api_url=args.kb_api_url,
            dry_run=args.dry_run
        )
        
        count = await service.extract_and_add_to_kb(
            days=args.days,
            min_success_rate=args.min_success_rate
        )
        
        if args.dry_run:
            print("\n⚠️  Режим dry-run: изменения не были применены")
        else:
            print(f"\n✅ Извлечено и добавлено {count} паттернов в KB")
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())













