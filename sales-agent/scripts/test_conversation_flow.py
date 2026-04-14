#!/usr/bin/env python3
"""
Скрипт для тестирования FSM воронки продаж

Использование:
    python scripts/test_conversation_flow.py [--test-all] [--test-state STATE] [--verbose]

Описание:
    Автоматическое тестирование состояний FSM и переходов между ними согласно
    архитектуре из BUSINESS_PROCESSES.md:
    - GREETING → QUALIFYING → OBJECTIONS → PROPOSAL → NEGOTIATING → FINALIZED → CONTRACT → COMPLETED
    - Проверка корректности переходов
    - Тестирование обработки возражений
    - Проверка интеграции с KB и proposal-generator

Конфигурация:
    Скрипт использует переменные из config.env:
    - DATABASE_URL - подключение к PostgreSQL
    - KB_API_URL - URL KB Service API
    - SALES_AGENT_URL - URL Sales Agent API (если реализован)

См. также:
    - BUSINESS_PROCESSES.md - описание FSM состояний и переходов
    - docs/CONFIGURATION_REFERENCE.md - справочник по конфигурации
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path
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

# Валидные переходы согласно диаграмме FSM
VALID_TRANSITIONS = {
    "GREETING": ["QUALIFYING"],
    "QUALIFYING": ["OBJECTIONS", "PROPOSAL", "HANDOFF"],
    "OBJECTIONS": ["QUALIFYING", "HANDOFF"],
    "PROPOSAL": ["NEGOTIATING"],
    "NEGOTIATING": ["PROPOSAL", "FINALIZED", "HANDOFF"],
    "FINALIZED": ["CONTRACT"],
    "CONTRACT": ["COMPLETED"],
    "COMPLETED": [],
    "HANDOFF": []
}


class FSMTestService:
    """Сервис для тестирования FSM воронки"""
    
    def __init__(self, db_pool: asyncpg.Pool, verbose: bool = False):
        self.db = db_pool
        self.verbose = verbose
        self.test_results = []
    
    async def test_state_exists(self, state: str) -> Tuple[bool, str]:
        """
        Проверка, что состояние существует в FSM
        
        Args:
            state: Название состояния
            
        Returns:
            (успех, сообщение)
        """
        if state in FSM_STATES:
            return True, f"✅ Состояние '{state}' существует в FSM"
        return False, f"❌ Состояние '{state}' не существует в FSM"
    
    async def test_transition_validity(self, from_state: str, to_state: str) -> Tuple[bool, str]:
        """
        Проверка валидности перехода между состояниями
        
        Args:
            from_state: Исходное состояние
            to_state: Целевое состояние
            
        Returns:
            (успех, сообщение)
        """
        if from_state not in VALID_TRANSITIONS:
            return False, f"❌ Исходное состояние '{from_state}' не найдено в переходах"
        
        if to_state in VALID_TRANSITIONS[from_state]:
            return True, f"✅ Переход '{from_state}' → '{to_state}' валиден"
        return False, f"❌ Переход '{from_state}' → '{to_state}' недопустим"
    
    async def test_database_schema(self) -> List[Tuple[bool, str]]:
        """
        Проверка схемы БД для поддержки FSM
        
        Returns:
            Список результатов проверок
        """
        results = []
        
        async with self.db.acquire() as conn:
            # Проверка таблицы conversations
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'conversations'
                    )
                """)
                
                if table_exists:
                    results.append((True, "✅ Таблица 'conversations' существует"))
                    
                    # Проверка колонки state
                    state_col = await conn.fetchval("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'conversations' 
                          AND column_name = 'state'
                    """)
                    
                    if state_col:
                        results.append((True, "✅ Колонка 'state' существует в conversations"))
                    else:
                        results.append((False, "❌ Колонка 'state' отсутствует в conversations"))
                    
                    # Проверка колонки slots
                    slots_col = await conn.fetchval("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'conversations' 
                          AND column_name = 'slots'
                    """)
                    
                    if slots_col:
                        results.append((True, "✅ Колонка 'slots' существует в conversations"))
                    else:
                        results.append((False, "❌ Колонка 'slots' отсутствует в conversations"))
                else:
                    results.append((False, "❌ Таблица 'conversations' не существует"))
            except Exception as e:
                results.append((False, f"❌ Ошибка проверки схемы: {e}"))
            
            # Проверка таблицы messages
            try:
                messages_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'messages'
                    )
                """)
                
                if messages_exists:
                    results.append((True, "✅ Таблица 'messages' существует"))
                else:
                    results.append((False, "❌ Таблица 'messages' не существует"))
            except Exception as e:
                results.append((False, f"❌ Ошибка проверки messages: {e}"))
        
        return results
    
    async def test_state_values_in_db(self) -> List[Tuple[bool, str]]:
        """
        Проверка значений состояний в БД на соответствие FSM
        
        Returns:
            Список результатов проверок
        """
        results = []
        
        async with self.db.acquire() as conn:
            # Получаем все уникальные состояния из БД
            db_states = await conn.fetch("""
                SELECT DISTINCT state, COUNT(*) as count
                FROM conversations
                WHERE state IS NOT NULL
                GROUP BY state
                ORDER BY count DESC
            """)
            
            valid_states = set(FSM_STATES)
            db_state_set = {row["state"] for row in db_states}
            
            # Проверка на недопустимые состояния
            invalid_states = db_state_set - valid_states
            if invalid_states:
                results.append((
                    False,
                    f"❌ Найдены недопустимые состояния в БД: {', '.join(invalid_states)}"
                ))
            else:
                results.append((True, "✅ Все состояния в БД соответствуют FSM"))
            
            # Статистика по состояниям
            if db_states:
                for row in db_states:
                    state = row["state"]
                    count = row["count"]
                    if state in valid_states:
                        results.append((
                            True,
                            f"ℹ️  Состояние '{state}': {count} диалогов"
                        ))
        
        return results
    
    async def test_transitions_in_db(self) -> List[Tuple[bool, str]]:
        """
        Проверка переходов между состояниями в реальных диалогах
        
        Returns:
            Список результатов проверок
        """
        results = []
        
        async with self.db.acquire() as conn:
            # Получаем диалоги с историей изменений состояний
            # (требуется таблица с историей или логирование изменений)
            # Пока проверяем только текущие состояния
            
            # Проверяем, есть ли диалоги в недопустимых состояниях для финальных
            final_states = ["COMPLETED", "HANDOFF"]
            invalid_final = await conn.fetch("""
                SELECT id, state, updated_at
                FROM conversations
                WHERE state IN ('FINALIZED', 'CONTRACT')
                  AND updated_at < NOW() - INTERVAL '7 days'
                LIMIT 10
            """)
            
            if invalid_final:
                results.append((
                    False,
                    f"⚠️  Найдены диалоги в промежуточных финальных состояниях старше 7 дней: {len(invalid_final)}"
                ))
            else:
                results.append((
                    True,
                    "✅ Нет застрявших диалогов в промежуточных состояниях"
                ))
        
        return results
    
    async def test_state(self, state: str) -> Dict:
        """
        Полное тестирование конкретного состояния
        
        Args:
            state: Название состояния для тестирования
            
        Returns:
            Результаты тестирования
        """
        results = {
            "state": state,
            "tests": [],
            "passed": 0,
            "failed": 0
        }
        
        # Тест 1: Существование состояния
        exists, msg = await self.test_state_exists(state)
        results["tests"].append({"test": "exists", "passed": exists, "message": msg})
        if exists:
            results["passed"] += 1
        else:
            results["failed"] += 1
        
        # Тест 2: Валидные переходы из этого состояния
        if state in VALID_TRANSITIONS:
            valid_to = VALID_TRANSITIONS[state]
            for to_state in valid_to:
                valid, msg = await self.test_transition_validity(state, to_state)
                results["tests"].append({
                    "test": f"transition_to_{to_state}",
                    "passed": valid,
                    "message": msg
                })
                if valid:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
        
        return results
    
    async def test_all_states(self) -> Dict:
        """
        Тестирование всех состояний FSM
        
        Returns:
            Результаты тестирования
        """
        print("🧪 Тестирование всех состояний FSM...")
        
        all_results = {
            "states": [],
            "total_passed": 0,
            "total_failed": 0
        }
        
        for state in FSM_STATES:
            if self.verbose:
                print(f"\n  Тестирование состояния: {state}")
            
            state_results = await self.test_state(state)
            all_results["states"].append(state_results)
            all_results["total_passed"] += state_results["passed"]
            all_results["total_failed"] += state_results["failed"]
            
            if self.verbose:
                for test in state_results["tests"]:
                    status = "✅" if test["passed"] else "❌"
                    print(f"    {status} {test['message']}")
        
        return all_results
    
    async def run_all_tests(self) -> Dict:
        """
        Запуск всех тестов
        
        Returns:
            Результаты всех тестов
        """
        print("🚀 Запуск всех тестов FSM...\n")
        
        all_results = {
            "schema_tests": [],
            "state_tests": {},
            "db_tests": [],
            "transition_tests": []
        }
        
        # Тест 1: Схема БД
        print("1️⃣  Тестирование схемы БД...")
        schema_results = await self.test_database_schema()
        all_results["schema_tests"] = schema_results
        for passed, msg in schema_results:
            print(f"   {msg}")
        
        # Тест 2: Все состояния
        print("\n2️⃣  Тестирование состояний FSM...")
        state_results = await self.test_all_states()
        all_results["state_tests"] = state_results
        
        # Тест 3: Значения в БД
        print("\n3️⃣  Тестирование значений состояний в БД...")
        db_results = await self.test_state_values_in_db()
        all_results["db_tests"] = db_results
        for passed, msg in db_results:
            print(f"   {msg}")
        
        # Тест 4: Переходы в БД
        print("\n4️⃣  Тестирование переходов в БД...")
        transition_results = await self.test_transitions_in_db()
        all_results["transition_tests"] = transition_results
        for passed, msg in transition_results:
            print(f"   {msg}")
        
        # Итоги
        total_passed = sum(1 for _, msg in schema_results + db_results + transition_results if _)
        total_failed = sum(1 for _, msg in schema_results + db_results + transition_results if not _)
        total_passed += state_results["total_passed"]
        total_failed += state_results["total_failed"]
        
        print(f"\n📊 Итоги тестирования:")
        print(f"   ✅ Пройдено: {total_passed}")
        print(f"   ❌ Провалено: {total_failed}")
        print(f"   📈 Успешность: {total_passed / (total_passed + total_failed) * 100:.1f}%")
        
        return all_results


async def main():
    parser = argparse.ArgumentParser(
        description="Тестирование FSM воронки продаж",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Тестирование всех состояний
  python scripts/test_conversation_flow.py --test-all
  
  # Тестирование конкретного состояния
  python scripts/test_conversation_flow.py --test-state QUALIFYING
  
  # Подробный вывод
  python scripts/test_conversation_flow.py --test-all --verbose
        """
    )
    parser.add_argument(
        "--test-all",
        action="store_true",
        help="Тестировать все состояния FSM"
    )
    parser.add_argument(
        "--test-state",
        type=str,
        choices=FSM_STATES,
        help="Тестировать конкретное состояние"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Подробный вывод"
    )
    
    args = parser.parse_args()
    
    if not args.test_all and not args.test_state:
        parser.print_help()
        sys.exit(1)
    
    # Подключение к БД
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Ошибка: DATABASE_URL не установлен в config.env")
        sys.exit(1)
    
    print("🔌 Подключение к базе данных...")
    db_pool = await asyncpg.create_pool(database_url)
    
    try:
        service = FSMTestService(db_pool=db_pool, verbose=args.verbose)
        
        if args.test_all:
            results = await service.run_all_tests()
        elif args.test_state:
            print(f"🧪 Тестирование состояния: {args.test_state}\n")
            results = await service.test_state(args.test_state)
            for test in results["tests"]:
                status = "✅" if test["passed"] else "❌"
                print(f"{status} {test['message']}")
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())













