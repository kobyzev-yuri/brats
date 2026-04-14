#!/usr/bin/env python3
"""
Скрипт для анализа эффективности диалогов

Использование:
    python scripts/analyze_conversations.py [--days 30] [--output report.json] [--format json|html]

Описание:
    Анализирует завершенные диалоги из таблицы conversations для выявления:
    - Паттернов успеха/неудачи
    - Статистики по диалогам (количество, средняя длительность, конверсия)
    - Причин handoff (частота, категории)
    - Топ успешных фраз/паттернов
    - Рекомендации по улучшению

Конфигурация:
    Скрипт использует переменные из config.env:
    - DATABASE_URL - подключение к PostgreSQL

См. также:
    - BUSINESS_PROCESSES.md - описание процессов и FSM
    - docs/CONFIGURATION_REFERENCE.md - справочник по конфигурации
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
sys.path.insert(0, str(project_root / "sales-agent"))

import asyncpg
from dotenv import load_dotenv

# Загружаем конфигурацию
load_dotenv(project_root / "config.env")


class ConversationAnalyzer:
    """Сервис для анализа диалогов"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
    
    async def get_conversation_stats(self, days: int = 30) -> Dict:
        """
        Получение статистики по диалогам
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Словарь со статистикой
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Общая статистика
            total = await conn.fetchval("""
                SELECT COUNT(*)
                FROM conversations
                WHERE created_at >= $1
            """, cutoff_date)
            
            # Статистика по состояниям
            by_state = await conn.fetch("""
                SELECT state, COUNT(*) as count
                FROM conversations
                WHERE created_at >= $1
                GROUP BY state
                ORDER BY count DESC
            """, cutoff_date)
            
            # Статистика по каналам
            by_channel = await conn.fetch("""
                SELECT channel, COUNT(*) as count
                FROM conversations
                WHERE created_at >= $1
                  AND channel IS NOT NULL
                GROUP BY channel
                ORDER BY count DESC
            """, cutoff_date)
            
            # Успешные диалоги (привели к КП/сделке)
            successful = await conn.fetchval("""
                SELECT COUNT(DISTINCT c.id)
                FROM conversations c
                JOIN proposals p ON p.conversation_id = c.id
                WHERE c.created_at >= $1
                  AND p.status IN ('sent', 'accepted', 'finalized')
            """, cutoff_date)
            
            # Handoff диалоги
            handoff = await conn.fetchval("""
                SELECT COUNT(*)
                FROM conversations
                WHERE created_at >= $1
                  AND state = 'HANDOFF'
            """, cutoff_date)
            
            # Средняя длительность диалога
            avg_duration = await conn.fetchval("""
                SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at)))
                FROM conversations
                WHERE created_at >= $1
                  AND updated_at > created_at
            """, cutoff_date)
            
            return {
                "period_days": days,
                "total_conversations": total,
                "successful_conversations": successful,
                "handoff_conversations": handoff,
                "conversion_rate": (successful / total * 100) if total > 0 else 0,
                "handoff_rate": (handoff / total * 100) if total > 0 else 0,
                "avg_duration_seconds": avg_duration,
                "by_state": {row["state"]: row["count"] for row in by_state},
                "by_channel": {row["channel"]: row["count"] for row in by_channel}
            }
    
    async def analyze_handoff_reasons(self, days: int = 30) -> List[Dict]:
        """
        Анализ причин handoff
        
        Args:
            days: Количество дней для анализа
            
        Returns:
            Список причин handoff с частотой
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Получаем диалоги с handoff и их последние сообщения
            handoff_conversations = await conn.fetch("""
                SELECT 
                    c.id,
                    c.state,
                    c.slots,
                    m.content as last_message
                FROM conversations c
                LEFT JOIN LATERAL (
                    SELECT content
                    FROM messages
                    WHERE conversation_id = c.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) m ON true
                WHERE c.created_at >= $1
                  AND c.state = 'HANDOFF'
            """, cutoff_date)
            
            # Анализируем причины (упрощенный анализ по ключевым словам)
            reasons = Counter()
            for conv in handoff_conversations:
                last_msg = (conv["last_message"] or "").lower()
                
                if "менеджер" in last_msg or "поговорить" in last_msg:
                    reasons["request_for_manager"] += 1
                elif "сложн" in last_msg or "особ" in last_msg:
                    reasons["complex_case"] += 1
                elif "договор" in last_msg or "услови" in last_msg:
                    reasons["contract_negotiation"] += 1
                elif "возражен" in last_msg or "не подходит" in last_msg:
                    reasons["objection_escalation"] += 1
                else:
                    reasons["other"] += 1
            
            return [
                {"reason": reason, "count": count, "percentage": count / len(handoff_conversations) * 100}
                for reason, count in reasons.most_common()
            ]
    
    async def get_top_successful_phrases(self, days: int = 30, limit: int = 10) -> List[Dict]:
        """
        Получение топ успешных фраз из диалогов
        
        Args:
            days: Количество дней для анализа
            limit: Количество фраз для возврата
            
        Returns:
            Список успешных фраз
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self.db.acquire() as conn:
            # Получаем сообщения из успешных диалогов
            successful_messages = await conn.fetch("""
                SELECT m.content
                FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                JOIN proposals p ON p.conversation_id = c.id
                WHERE c.created_at >= $1
                  AND m.role = 'assistant'
                  AND p.status IN ('sent', 'accepted', 'finalized')
                ORDER BY m.created_at DESC
                LIMIT 100
            """, cutoff_date)
            
            # Простой анализ частых фраз (можно улучшить)
            phrases = Counter()
            for msg in successful_messages:
                content = msg["content"].lower()
                # Извлекаем короткие фразы (2-4 слова)
                words = content.split()
                for i in range(len(words) - 2):
                    phrase = " ".join(words[i:i+3])
                    if len(phrase) > 10 and len(phrase) < 50:
                        phrases[phrase] += 1
            
            return [
                {"phrase": phrase, "frequency": count}
                for phrase, count in phrases.most_common(limit)
            ]
    
    async def generate_recommendations(self, stats: Dict, handoff_reasons: List[Dict]) -> List[str]:
        """
        Генерация рекомендаций по улучшению
        
        Args:
            stats: Статистика по диалогам
            handoff_reasons: Причины handoff
            
        Returns:
            Список рекомендаций
        """
        recommendations = []
        
        # Анализ конверсии
        if stats["conversion_rate"] < 20:
            recommendations.append(
                f"⚠️  Низкая конверсия ({stats['conversion_rate']:.1f}%). "
                "Рекомендуется улучшить квалификацию лидов и обработку возражений."
            )
        
        # Анализ handoff
        if stats["handoff_rate"] > 30:
            recommendations.append(
                f"⚠️  Высокий процент handoff ({stats['handoff_rate']:.1f}%). "
                "Рекомендуется улучшить обработку сложных случаев."
            )
        
        # Анализ причин handoff
        if handoff_reasons:
            top_reason = handoff_reasons[0]
            if top_reason["percentage"] > 40:
                recommendations.append(
                    f"💡 Основная причина handoff: {top_reason['reason']} ({top_reason['percentage']:.1f}%). "
                    "Рекомендуется добавить специальную обработку для этого случая."
                )
        
        # Анализ длительности
        if stats["avg_duration_seconds"] and stats["avg_duration_seconds"] > 3600:
            recommendations.append(
                f"⏱️  Длительные диалоги (средняя длительность: {stats['avg_duration_seconds']/60:.1f} мин). "
                "Рекомендуется оптимизировать процесс квалификации."
            )
        
        return recommendations
    
    async def generate_report(
        self, 
        days: int = 30, 
        format: str = "json"
    ) -> Dict:
        """
        Генерация полного отчета
        
        Args:
            days: Количество дней для анализа
            format: Формат отчета (json/html)
            
        Returns:
            Отчет в виде словаря
        """
        print(f"📊 Генерация отчета за последние {days} дней...\n")
        
        # Собираем данные
        stats = await self.get_conversation_stats(days=days)
        handoff_reasons = await self.analyze_handoff_reasons(days=days)
        top_phrases = await self.get_top_successful_phrases(days=days)
        recommendations = await self.generate_recommendations(stats, handoff_reasons)
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "statistics": stats,
            "handoff_analysis": {
                "total": stats["handoff_conversations"],
                "reasons": handoff_reasons
            },
            "top_successful_phrases": top_phrases,
            "recommendations": recommendations
        }
        
        return report
    
    async def print_report(self, report: Dict):
        """
        Вывод отчета в консоль
        
        Args:
            report: Отчет
        """
        stats = report["statistics"]
        
        print("=" * 60)
        print("📊 ОТЧЕТ ПО АНАЛИЗУ ДИАЛОГОВ")
        print("=" * 60)
        print(f"\nПериод: последние {report['period_days']} дней")
        print(f"Дата генерации: {report['generated_at']}\n")
        
        print("📈 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего диалогов: {stats['total_conversations']}")
        print(f"   Успешных диалогов: {stats['successful_conversations']}")
        print(f"   Конверсия: {stats['conversion_rate']:.1f}%")
        print(f"   Handoff: {stats['handoff_conversations']} ({stats['handoff_rate']:.1f}%)")
        if stats['avg_duration_seconds']:
            print(f"   Средняя длительность: {stats['avg_duration_seconds']/60:.1f} минут")
        
        print("\n📊 ПО СОСТОЯНИЯМ:")
        for state, count in stats['by_state'].items():
            percentage = (count / stats['total_conversations'] * 100) if stats['total_conversations'] > 0 else 0
            print(f"   {state}: {count} ({percentage:.1f}%)")
        
        print("\n📱 ПО КАНАЛАМ:")
        for channel, count in stats['by_channel'].items():
            percentage = (count / stats['total_conversations'] * 100) if stats['total_conversations'] > 0 else 0
            print(f"   {channel}: {count} ({percentage:.1f}%)")
        
        if report['handoff_analysis']['reasons']:
            print("\n🚨 ПРИЧИНЫ HANDOFF:")
            for reason_data in report['handoff_analysis']['reasons']:
                print(f"   {reason_data['reason']}: {reason_data['count']} ({reason_data['percentage']:.1f}%)")
        
        if report['top_successful_phrases']:
            print("\n💬 ТОП УСПЕШНЫХ ФРАЗ:")
            for i, phrase_data in enumerate(report['top_successful_phrases'][:5], 1):
                print(f"   {i}. \"{phrase_data['phrase']}\" (использовано {phrase_data['frequency']} раз)")
        
        if report['recommendations']:
            print("\n💡 РЕКОМЕНДАЦИИ:")
            for i, rec in enumerate(report['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        print("\n" + "=" * 60)


async def main():
    parser = argparse.ArgumentParser(
        description="Анализ эффективности диалогов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Анализ за последние 30 дней
  python scripts/analyze_conversations.py --days 30
  
  # Сохранение отчета в JSON
  python scripts/analyze_conversations.py --days 30 --output report.json --format json
  
  # Вывод в HTML (когда будет реализовано)
  python scripts/analyze_conversations.py --days 30 --output report.html --format html
        """
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Количество дней для анализа (по умолчанию: 30)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь для сохранения отчета (по умолчанию: вывод в консоль)"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "html"],
        default="json",
        help="Формат отчета (по умолчанию: json)"
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
        analyzer = ConversationAnalyzer(db_pool=db_pool)
        
        report = await analyzer.generate_report(days=args.days, format=args.format)
        
        # Вывод в консоль
        await analyzer.print_report(report)
        
        # Сохранение в файл
        if args.output:
            if args.format == "json":
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                print(f"\n💾 Отчет сохранен в {args.output}")
            elif args.format == "html":
                # TODO: Реализовать генерацию HTML
                print(f"\n⚠️  Генерация HTML пока не реализована")
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())













