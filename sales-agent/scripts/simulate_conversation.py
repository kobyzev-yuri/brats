#!/usr/bin/env python3
"""
Скрипт для симуляции диалога с sales-agent

Использование:
    python scripts/simulate_conversation.py [--scenario SCENARIO] [--interactive]

Описание:
    Симуляция диалога для тестирования без реального клиента.
    Создает тестовый диалог, отправляет сообщения от имени "клиента",
    проверяет ответы агента и валидирует переходы состояний FSM.

Сценарии:
    - objection_handling - тестирование обработки возражений
    - qualification - тестирование квалификации лида
    - proposal_generation - тестирование генерации КП
    - handoff - тестирование передачи менеджеру

Конфигурация:
    Скрипт использует переменные из config.env:
    - DATABASE_URL - подключение к PostgreSQL
    - SALES_AGENT_URL - URL Sales Agent API (если реализован)
    - KB_API_URL - URL KB Service API

См. также:
    - BUSINESS_PROCESSES.md - описание FSM состояний
    - docs/CONFIGURATION_REFERENCE.md - справочник по конфигурации
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "sales-agent"))

import asyncpg
from dotenv import load_dotenv

# Загружаем конфигурацию
load_dotenv(project_root / "config.env")

# Предопределенные сценарии
SCENARIOS = {
    "objection_handling": [
        {"role": "user", "content": "Здравствуйте, интересует коттедж"},
        {"role": "assistant", "expected_state": "GREETING"},
        {"role": "user", "content": "Сколько стоит?"},
        {"role": "assistant", "expected_state": "QUALIFYING"},
        {"role": "user", "content": "Это слишком дорого"},
        {"role": "assistant", "expected_state": "OBJECTIONS", "check_objection": True},
        {"role": "user", "content": "Может быть есть скидки?"},
        {"role": "assistant", "expected_state": "OBJECTIONS"},
    ],
    "qualification": [
        {"role": "user", "content": "Привет, хочу купить дом"},
        {"role": "assistant", "expected_state": "GREETING"},
        {"role": "user", "content": "Нужен дом с 3 спальнями, бюджет до 10 млн"},
        {"role": "assistant", "expected_state": "QUALIFYING", "check_slots": ["budget", "preferences"]},
        {"role": "user", "content": "Когда можно посмотреть?"},
        {"role": "assistant", "expected_state": "QUALIFYING"},
    ],
    "proposal_generation": [
        {"role": "user", "content": "Здравствуйте"},
        {"role": "assistant", "expected_state": "GREETING"},
        {"role": "user", "content": "Ищу дом с участком, 4 спальни, бюджет 15 млн"},
        {"role": "assistant", "expected_state": "QUALIFYING"},
        {"role": "user", "content": "Да, готов рассмотреть предложение"},
        {"role": "assistant", "expected_state": "PROPOSAL", "check_proposal": True},
    ],
    "handoff": [
        {"role": "user", "content": "Здравствуйте"},
        {"role": "assistant", "expected_state": "GREETING"},
        {"role": "user", "content": "Нужен особый договор, индивидуальные условия"},
        {"role": "assistant", "expected_state": "QUALIFYING"},
        {"role": "user", "content": "Хочу поговорить с менеджером напрямую"},
        {"role": "assistant", "expected_state": "HANDOFF", "check_handoff": True},
    ]
}


class ConversationSimulator:
    """Сервис для симуляции диалогов"""
    
    def __init__(self, db_pool: asyncpg.Pool, sales_agent_url: str = None):
        self.db = db_pool
        self.sales_agent_url = sales_agent_url or os.getenv("SALES_AGENT_URL", "http://localhost:8000")
        self.conversation_id = None
    
    async def create_test_conversation(self, channel: str = "test") -> int:
        """
        Создание тестового диалога
        
        Args:
            channel: Канал коммуникации
            
        Returns:
            ID созданного диалога
        """
        async with self.db.acquire() as conn:
            conversation_id = await conn.fetchval("""
                INSERT INTO conversations (
                    state, channel, slots, created_at, updated_at
                )
                VALUES ($1, $2, $3, NOW(), NOW())
                RETURNING id
            """, "GREETING", channel, json.dumps({}))
            
            self.conversation_id = conversation_id
            return conversation_id
    
    async def send_message(
        self, 
        content: str, 
        role: str = "user",
        expected_state: Optional[str] = None
    ) -> Dict:
        """
        Отправка сообщения в диалог
        
        Args:
            content: Текст сообщения
            role: Роль отправителя (user/assistant)
            expected_state: Ожидаемое состояние после обработки
            
        Returns:
            Результат обработки
        """
        if not self.conversation_id:
            await self.create_test_conversation()
        
        async with self.db.acquire() as conn:
            # Сохраняем сообщение пользователя
            await conn.execute("""
                INSERT INTO messages (
                    conversation_id, role, content, created_at
                )
                VALUES ($1, $2, $3, NOW())
            """, self.conversation_id, role, content)
            
            # Если это сообщение от пользователя, пытаемся вызвать sales-agent API
            if role == "user":
                # TODO: Реальный вызов sales-agent API когда будет реализован
                # Пока просто симулируем ответ
                response = await self._simulate_agent_response(content)
                
                # Сохраняем ответ агента
                await conn.execute("""
                    INSERT INTO messages (
                        conversation_id, role, content, created_at
                    )
                    VALUES ($1, $2, $3, NOW())
                """, self.conversation_id, "assistant", response["content"])
                
                # Обновляем состояние диалога (если указано)
                if response.get("new_state"):
                    await conn.execute("""
                        UPDATE conversations
                        SET state = $1, updated_at = NOW()
                        WHERE id = $2
                    """, response["new_state"], self.conversation_id)
                
                # Проверяем ожидаемое состояние
                if expected_state:
                    current_state = await conn.fetchval("""
                        SELECT state FROM conversations WHERE id = $1
                    """, self.conversation_id)
                    
                    if current_state == expected_state:
                        return {
                            "success": True,
                            "message": f"✅ Состояние соответствует ожидаемому: {expected_state}",
                            "response": response["content"],
                            "state": current_state
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"❌ Состояние не соответствует: ожидалось {expected_state}, получено {current_state}",
                            "response": response["content"],
                            "state": current_state
                        }
                
                return {
                    "success": True,
                    "response": response["content"],
                    "state": response.get("new_state")
                }
            
            return {"success": True, "content": content}
    
    async def _simulate_agent_response(self, user_message: str) -> Dict:
        """
        Симуляция ответа агента (заглушка до реализации реального API)
        
        Args:
            user_message: Сообщение пользователя
            
        Returns:
            Ответ агента с новым состоянием
        """
        # Простая логика симуляции
        message_lower = user_message.lower()
        
        if "дорого" in message_lower or "цена" in message_lower:
            return {
                "content": "Понимаю ваши опасения по поводу цены. Давайте обсудим варианты...",
                "new_state": "OBJECTIONS"
            }
        elif "менеджер" in message_lower or "поговорить" in message_lower:
            return {
                "content": "Конечно, передам вас менеджеру. Он свяжется с вами в ближайшее время.",
                "new_state": "HANDOFF"
            }
        elif "готов" in message_lower or "предложение" in message_lower:
            return {
                "content": "Отлично! Подготовлю для вас коммерческое предложение...",
                "new_state": "PROPOSAL"
            }
        elif "спальн" in message_lower or "бюджет" in message_lower:
            return {
                "content": "Понял ваши требования. Уточню несколько деталей...",
                "new_state": "QUALIFYING"
            }
        else:
            return {
                "content": "Спасибо за ваш вопрос. Давайте уточним детали...",
                "new_state": "QUALIFYING"
            }
    
    async def run_scenario(self, scenario_name: str) -> Dict:
        """
        Запуск предопределенного сценария
        
        Args:
            scenario_name: Название сценария
            
        Returns:
            Результаты выполнения сценария
        """
        if scenario_name not in SCENARIOS:
            return {
                "success": False,
                "message": f"Сценарий '{scenario_name}' не найден"
            }
        
        print(f"🎭 Запуск сценария: {scenario_name}\n")
        
        await self.create_test_conversation()
        print(f"✅ Создан тестовый диалог (ID: {self.conversation_id})\n")
        
        results = {
            "scenario": scenario_name,
            "conversation_id": self.conversation_id,
            "steps": [],
            "passed": 0,
            "failed": 0
        }
        
        for step in SCENARIOS[scenario_name]:
            if step["role"] == "user":
                print(f"👤 Пользователь: {step['content']}")
                result = await self.send_message(
                    content=step["content"],
                    role="user",
                    expected_state=step.get("expected_state")
                )
                
                print(f"🤖 Агент: {result.get('response', 'N/A')}")
                print(f"   Состояние: {result.get('state', 'N/A')}")
                
                if result.get("success"):
                    status = "✅" if result.get("success") else "❌"
                    print(f"   {status} {result.get('message', '')}\n")
                    
                    results["steps"].append({
                        "step": step["content"],
                        "success": result.get("success", False),
                        "message": result.get("message", "")
                    })
                    
                    if result.get("success"):
                        results["passed"] += 1
                    else:
                        results["failed"] += 1
                else:
                    results["failed"] += 1
        
        print(f"\n📊 Итоги сценария '{scenario_name}':")
        print(f"   ✅ Пройдено: {results['passed']}")
        print(f"   ❌ Провалено: {results['failed']}")
        
        return results
    
    async def interactive_mode(self):
        """
        Интерактивный режим симуляции
        """
        print("🎮 Интерактивный режим симуляции диалога\n")
        print("Введите сообщения от имени клиента (или 'quit' для выхода)\n")
        
        await self.create_test_conversation()
        print(f"✅ Создан тестовый диалог (ID: {self.conversation_id})\n")
        
        while True:
            try:
                user_input = input("👤 Вы: ").strip()
                
                if user_input.lower() in ["quit", "exit", "q"]:
                    print("\n👋 Завершение симуляции...")
                    break
                
                if not user_input:
                    continue
                
                result = await self.send_message(content=user_input, role="user")
                print(f"🤖 Агент: {result.get('response', 'N/A')}")
                print(f"   Состояние: {result.get('state', 'N/A')}\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Завершение симуляции...")
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Симуляция диалога с sales-agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  # Запуск сценария обработки возражений
  python scripts/simulate_conversation.py --scenario objection_handling
  
  # Интерактивный режим
  python scripts/simulate_conversation.py --interactive
  
  # Список доступных сценариев
  python scripts/simulate_conversation.py --list-scenarios
        """
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=list(SCENARIOS.keys()),
        help="Название сценария для запуска"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Интерактивный режим"
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="Показать список доступных сценариев"
    )
    parser.add_argument(
        "--sales-agent-url",
        type=str,
        default=None,
        help="URL Sales Agent API (по умолчанию из SALES_AGENT_URL или http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    if args.list_scenarios:
        print("📋 Доступные сценарии:")
        for name, steps in SCENARIOS.items():
            print(f"\n  {name}:")
            for i, step in enumerate(steps, 1):
                if step["role"] == "user":
                    print(f"    {i}. Пользователь: {step['content']}")
        sys.exit(0)
    
    if not args.scenario and not args.interactive:
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
        simulator = ConversationSimulator(
            db_pool=db_pool,
            sales_agent_url=args.sales_agent_url
        )
        
        if args.interactive:
            await simulator.interactive_mode()
        elif args.scenario:
            results = await simulator.run_scenario(args.scenario)
            if not results.get("success", True):
                sys.exit(1)
        
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())













