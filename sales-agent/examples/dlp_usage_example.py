"""
Пример использования DLP в нейропродажнике
"""

import asyncio
import json
from services.dlp_integration import get_sales_agent_dlp


async def example_dialogue_with_dlp():
    """
    Пример диалога с использованием DLP
    """
    dlp = get_sales_agent_dlp()
    
    # Исходные данные диалога (с персональными данными)
    conversation_slots = {
        "client_name": "Иван Иванов",
        "phone": "+7 (988) 199-89-98",
        "email": "ivan@example.com",
        "budget": 10000000,
        "preferred_location": "Краснодар",
        "property_type": "коттедж"
    }
    
    user_message = "Меня зовут Иван, телефон +7 (988) 199-89-98, хочу купить коттедж за 10 миллионов"
    
    amocrm_data = {
        "lead_id": 12345,
        "contact_id": 67890,
        "deal_id": 11111,
        "contact": {
            "name": "Иван Иванов",
            "phone": "+7 (988) 199-89-98",
            "email": "ivan@example.com"
        }
    }
    
    print("=" * 60)
    print("Пример использования DLP в нейропродажнике")
    print("=" * 60)
    
    # Обезличивание слотов
    print("\n1. Обезличивание слотов диалога:")
    print(f"Исходные слоты: {json.dumps(conversation_slots, ensure_ascii=False, indent=2)}")
    
    sanitized_slots = dlp.sanitize_conversation_slots(conversation_slots)
    print(f"\nОбезличенные слоты: {json.dumps(sanitized_slots, ensure_ascii=False, indent=2)}")
    
    # Обезличивание сообщения
    print("\n2. Обезличивание сообщения пользователя:")
    print(f"Исходное сообщение: {user_message}")
    sanitized_message = dlp.sanitize_message(user_message)
    print(f"Обезличенное сообщение: {sanitized_message}")
    
    # Обезличивание данных amoCRM
    print("\n3. Обезличивание данных из amoCRM:")
    print(f"Исходные данные: {json.dumps(amocrm_data, ensure_ascii=False, indent=2)}")
    sanitized_amocrm = dlp.sanitize_amocrm_data(amocrm_data)
    print(f"\nОбезличенные данные: {json.dumps(sanitized_amocrm, ensure_ascii=False, indent=2)}")
    
    # Проверка обезличивания
    print("\n4. Проверка обезличивания:")
    all_sanitized = json.dumps({
        "slots": sanitized_slots,
        "message": sanitized_message,
        "amocrm": sanitized_amocrm
    })
    
    checks = [
        ("+7 (988) 199-89-98" not in all_sanitized, "Телефон обезличен"),
        ("ivan@example.com" not in all_sanitized, "Email обезличен"),
        ("Иван Иванов" not in all_sanitized, "Имя обезличено"),
        ("12345" not in all_sanitized or "LEAD_" in all_sanitized, "Lead ID обезличен"),
    ]
    
    for check, description in checks:
        status = "✅" if check else "❌"
        print(f"  {status} {description}")
    
    print("\n" + "=" * 60)
    print("Пример завершен")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(example_dialogue_with_dlp())















