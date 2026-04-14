#!/usr/bin/env python3
"""
Тестовый скрипт для проверки RAG + DLP + LLM интеграции
"""

import asyncio
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Загружаем конфигурацию
load_dotenv(dotenv_path=Path(__file__).parent / "config.env", override=True)

API_URL = "http://localhost:8001"


async def test_rag_webhook():
    """Тест RAG через webhook endpoint"""
    print("\n" + "="*60)
    print("Тест 1: RAG через webhook endpoint")
    print("="*60)
    
    # Тестовый запрос с персональными данными (для проверки DLP)
    test_request = {
        "query": "Расскажите о ценах на коттеджи",
        "context": {
            "visitor_id": "visitor_12345",
            "session_id": "session_67890",
            "slots": {
                "client_name": "Иван Иванов",
                "phone": "+7 (988) 199-89-98",
                "email": "ivan@example.com",
                "budget": 10000000
            },
            "metadata": {
                "source": "site",
                "utm_source": "yandex"
            }
        },
        "category": "product_info",
        "target_audience": "end_buyer",
        "limit": 3,
        "sanitize_context": True  # Включаем DLP
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/rag/webhook",
                json=test_request
            )
            response.raise_for_status()
            
            result = response.json()
            
            print(f"\n✅ Запрос успешен!")
            print(f"\nОтвет LLM:")
            print(f"{result['response']}")
            print(f"\nИсточники из KB: {len(result['sources'])}")
            for i, source in enumerate(result['sources'], 1):
                print(f"  {i}. [ID: {source['id']}, similarity: {source.get('similarity', 0):.2f}]")
                print(f"     {source['content'][:100]}...")
            
            print(f"\nМетаданные:")
            print(f"  - Модель: {result['metadata']['model']}")
            print(f"  - Токены: {result['metadata']['llm_usage']['total_tokens']}")
            print(f"  - Результатов из KB: {result['metadata']['kb_results_count']}")
            
            # Проверяем, что персональные данные обезличены
            print(f"\n🔒 Проверка DLP:")
            response_text = result['response'].lower()
            context_str = json.dumps(test_request['context']).lower()
            
            # Проверяем, что в ответе нет реальных персональных данных
            if "+7 (988) 199-89-98" not in result['response']:
                print("  ✅ Телефон обезличен в ответе")
            else:
                print("  ⚠️  Телефон найден в ответе (возможна утечка)")
            
            if "ivan@example.com" not in result['response']:
                print("  ✅ Email обезличен в ответе")
            else:
                print("  ⚠️  Email найден в ответе (возможна утечка)")
            
            if "Иван Иванов" not in result['response']:
                print("  ✅ Имя обезличено в ответе")
            else:
                print("  ⚠️  Имя найдено в ответе (возможна утечка)")
            
        except httpx.HTTPStatusError as e:
            print(f"\n❌ HTTP ошибка: {e.response.status_code}")
            print(f"Ответ: {e.response.text}")
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()


async def test_rag_generate():
    """Тест RAG через generate endpoint"""
    print("\n" + "="*60)
    print("Тест 2: RAG через /api/rag/generate endpoint")
    print("="*60)
    
    test_request = {
        "query": "Какие варианты отделки доступны?",
        "category": "product_info",
        "limit": 5,
        "min_similarity": 0.6
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/rag/generate",
                json=test_request
            )
            response.raise_for_status()
            
            result = response.json()
            
            print(f"\n✅ Запрос успешен!")
            print(f"\nОтвет LLM:")
            print(f"{result['response']}")
            print(f"\nИсточники: {len(result['sources'])}")
            
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()


async def test_dlp_service():
    """Тест DLP сервиса напрямую"""
    print("\n" + "="*60)
    print("Тест 3: DLP сервис (прямой тест)")
    print("="*60)
    
    from services.dlp_service import DLPService
    
    dlp = DLPService()
    
    # Тестовые данные с персональной информацией
    test_data = {
        "name": "Иван Иванов",
        "phone": "+7 (988) 199-89-98",
        "email": "ivan@example.com",
        "message": "Хочу купить коттедж за 10 миллионов рублей. Мой телефон +7 (988) 199-89-98",
        "visitor_id": "visitor_12345",
        "metadata": {
            "source": "site",
            "utm_source": "yandex"
        }
    }
    
    print("\nИсходные данные:")
    print(json.dumps(test_data, ensure_ascii=False, indent=2))
    
    sanitized = dlp.sanitize_for_llm(test_data)
    
    print("\nОбезличенные данные:")
    print(json.dumps(sanitized, ensure_ascii=False, indent=2))
    
    # Проверки
    print("\n🔒 Проверка обезличивания:")
    if "+7 (988) 199-89-98" not in json.dumps(sanitized):
        print("  ✅ Телефон обезличен")
    else:
        print("  ❌ Телефон не обезличен!")
    
    if "ivan@example.com" not in json.dumps(sanitized):
        print("  ✅ Email обезличен")
    else:
        print("  ❌ Email не обезличен!")
    
    if "visitor_12345" not in json.dumps(sanitized):
        print("  ✅ visitor_id обезличен")
    else:
        print("  ⚠️  visitor_id не обезличен (может быть псевдонимизирован)")


async def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("Тестирование RAG + DLP + LLM интеграции")
    print("="*60)
    
    # Проверяем доступность API
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{API_URL}/health")
            if response.status_code == 200:
                print(f"\n✅ KB Service доступен на {API_URL}")
            else:
                print(f"\n⚠️  KB Service вернул статус {response.status_code}")
        except Exception as e:
            print(f"\n❌ KB Service недоступен на {API_URL}")
            print(f"   Ошибка: {e}")
            print(f"   Убедитесь, что сервис запущен: cd kb-service && python api/main.py")
            return
    
    # Запускаем тесты
    await test_dlp_service()
    await test_rag_generate()
    await test_rag_webhook()
    
    print("\n" + "="*60)
    print("Тестирование завершено")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())















