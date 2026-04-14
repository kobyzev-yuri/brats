#!/usr/bin/env python3
"""
Скрипт для импорта данных из 'Саммари встречи.odt' в KB
Конвертирует ODT в текст и импортирует через KB Service API
"""

import os
import sys
import json
import requests
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def convert_odt_to_text(odt_path: str) -> str:
    """
    Конвертирует ODT файл в текст
    Использует различные методы в зависимости от доступных библиотек
    """
    odt_path = Path(odt_path)
    
    if not odt_path.exists():
        raise FileNotFoundError(f"Файл не найден: {odt_path}")
    
    # Метод 1: Использование odfpy (если установлен)
    try:
        from odf import text, teletype
        from odf.opendocument import load
        
        doc = load(str(odt_path))
        paragraphs = []
        
        for para in doc.getElementsByType(text.P):
            para_text = teletype.extractText(para)
            if para_text.strip():
                paragraphs.append(para_text)
        
        return "\n\n".join(paragraphs)
    except ImportError:
        pass
    
    # Метод 2: Использование python-docx (для DOCX, но может работать с ODT через конвертацию)
    # Пропускаем, так как это для DOCX
    
    # Метод 3: Использование pandoc (если установлен)
    import subprocess
    try:
        result = subprocess.run(
            ['pandoc', '-f', 'odt', '-t', 'plain', str(odt_path)],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Метод 4: Простое чтение как ZIP и извлечение content.xml
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        
        with zipfile.ZipFile(odt_path, 'r') as odt_file:
            content_xml = odt_file.read('content.xml')
        
        root = ET.fromstring(content_xml)
        
        # Простое извлечение текста из XML
        # ODF использует пространство имён text
        ns = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
        
        paragraphs = []
        for para in root.findall('.//text:p', ns):
            text_content = ''.join(para.itertext())
            if text_content.strip():
                paragraphs.append(text_content.strip())
        
        return "\n\n".join(paragraphs)
    except Exception as e:
        print(f"Ошибка при извлечении текста из ODT: {e}")
        raise
    
    raise RuntimeError("Не удалось конвертировать ODT. Установите одну из библиотек: odfpy, pandoc")


def categorize_content(text: str) -> list:
    """
    Разбивает текст на категории для импорта в KB
    Возвращает список словарей с категориями и содержимым
    """
    chunks = []
    
    # Простая эвристика для определения категорий
    # Можно улучшить с помощью LLM или более сложной логики
    
    lines = text.split('\n')
    current_category = None
    current_content = []
    
    category_keywords = {
        'product_info': ['продукт', 'посёлок', 'дом', 'характеристики', 'преимущества', 'инфраструктура'],
        'sales_script': ['скрипт', 'диалог', 'разговор', 'коммуникация', 'как говорить', 'что сказать'],
        'objection_handling': ['возражение', 'сомнение', 'вопрос', 'ответ', 'как ответить'],
        'target_audience': ['клиент', 'аудитория', 'целевая', 'портрет', 'потребности', 'триггер'],
        'tone_of_voice': ['тон', 'стиль', 'манера', 'общение', 'этикет'],
        'pricing': ['цена', 'стоимость', 'оплата', 'скидка', 'акция', 'финансирование'],
        'contacts': ['контакт', 'телефон', 'адрес', 'график', 'показ', 'встреча']
    }
    
    for line in lines:
        line_lower = line.lower()
        
        # Определяем категорию по ключевым словам
        detected_category = None
        for cat, keywords in category_keywords.items():
            if any(keyword in line_lower for keyword in keywords):
                detected_category = cat
                break
        
        # Если нашли новую категорию, сохраняем предыдущий блок
        if detected_category and detected_category != current_category:
            if current_content and current_category:
                chunks.append({
                    'category': current_category,
                    'content': '\n'.join(current_content).strip()
                })
            current_category = detected_category
            current_content = [line]
        elif current_category:
            current_content.append(line)
        elif not current_category:
            # Если категория не определена, используем sales_script по умолчанию
            if not current_content:
                current_category = 'sales_script'
            current_content.append(line)
    
    # Добавляем последний блок
    if current_content and current_category:
        chunks.append({
            'category': current_category,
            'content': '\n'.join(current_content).strip()
        })
    
    # Если не удалось определить категории, возвращаем весь текст как sales_script
    if not chunks:
        chunks.append({
            'category': 'sales_script',
            'content': text
        })
    
    return chunks


def import_to_kb(chunks: list, api_url: str = "http://localhost:8001"):
    """
    Импортирует chunks в KB через API
    """
    imported = 0
    failed = 0
    
    # Отключаем proxy для локальных запросов
    import os
    proxy_env_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 
                      'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
    original_proxies = {}
    for var in proxy_env_vars:
        if var in os.environ:
            original_proxies[var] = os.environ[var]
            del os.environ[var]
    
    # Добавляем localhost в NO_PROXY
    os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
    os.environ['no_proxy'] = 'localhost,127.0.0.1'
    
    try:
        for chunk in chunks:
            try:
                response = requests.post(
                    f"{api_url}/api/kb/add",
                    json={
                        "content": chunk['content'],
                        "category": chunk['category'],
                        "target_audience": "both",
                        "priority": "high",
                        "source": "Саммари встречи.odt"
                    },
                    timeout=30,
                    proxies={'http': None, 'https': None}  # Явно отключаем proxy
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Импортирован chunk: {chunk['category']} (id={result.get('chunk_id')})")
                    imported += 1
                else:
                    print(f"❌ Ошибка импорта: {response.status_code} - {response.text}")
                    failed += 1
            except Exception as e:
                print(f"❌ Ошибка при импорте chunk: {e}")
                failed += 1
    finally:
        # Восстанавливаем proxy переменные
        for var, value in original_proxies.items():
            os.environ[var] = value
    
    return imported, failed


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Импорт данных из Саммари встречи.odt в KB')
    parser.add_argument('--file', '-f', default='docs/Саммари встречи.odt',
                       help='Путь к ODT файлу')
    parser.add_argument('--api-url', default='http://localhost:8001',
                       help='URL KB Service API')
    parser.add_argument('--output', '-o',
                       help='Сохранить извлечённый текст в файл (опционально)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Только извлечь текст, не импортировать')
    
    args = parser.parse_args()
    
    print(f"📄 Чтение файла: {args.file}")
    
    try:
        # Конвертируем ODT в текст
        text_content = convert_odt_to_text(args.file)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(text_content)
            print(f"✅ Текст сохранён в: {args.output}")
        
        # Разбиваем на категории
        print("\n📋 Разбиение на категории...")
        chunks = categorize_content(text_content)
        
        print(f"✅ Найдено {len(chunks)} chunks:")
        for i, chunk in enumerate(chunks, 1):
            preview = chunk['content'][:100].replace('\n', ' ')
            print(f"  {i}. {chunk['category']}: {preview}...")
        
        if args.dry_run:
            print("\n🔍 Dry-run режим: импорт не выполнен")
            return
        
        # Импортируем в KB
        print(f"\n📤 Импорт в KB через {args.api_url}...")
        imported, failed = import_to_kb(chunks, args.api_url)
        
        print(f"\n✅ Импорт завершён:")
        print(f"  Импортировано: {imported}")
        print(f"  Ошибок: {failed}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

