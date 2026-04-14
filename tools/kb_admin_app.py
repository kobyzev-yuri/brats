"""
Веб-админка для управления блоками Knowledge Base
Flask приложение с веб-интерфейсом
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import List, Dict, Optional
import os
import asyncio
import hashlib
import json
import sys
from pathlib import Path

# Добавляем путь к kb-service для импорта GeminiTextService
sys.path.insert(0, str(Path(__file__).parent / 'kb-service'))
try:
    from services.gemini_text_service import get_gemini_text_service
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ GeminiTextService не доступен. Вторичная обработка будет работать в режиме демо.")

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Настройки подключения к БД
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_NAME', 'kb_db'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'password')
}


def get_db_connection():
    """Получить соединение с БД"""
    return psycopg2.connect(**DB_CONFIG)


@app.route('/')
def index():
    """Главная страница - список блоков"""
    return redirect(url_for('blocks_list'))


@app.route('/blocks')
def blocks_list():
    """Список всех блоков с фильтрацией"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    block_type = request.args.get('block_type', '')
    tab_name = request.args.get('tab_name', '')
    is_active = request.args.get('is_active', '')
    search = request.args.get('search', '')
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Построение запроса
    query = "SELECT id, block_id, block_type, tab_name, is_active, created_at, updated_at FROM kb_blocks WHERE 1=1"
    params = []
    
    if block_type:
        query += " AND block_type = %s"
        params.append(block_type)
    
    if tab_name:
        query += " AND tab_name = %s"
        params.append(tab_name)
    
    if is_active != '':
        query += " AND is_active = %s"
        params.append(is_active == 'true')
    
    if search:
        query += " AND (block_id ILIKE %s OR block_type ILIKE %s OR tab_name ILIKE %s)"
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern])
    
    # Подсчет общего количества
    count_query = f"SELECT COUNT(*) as total FROM ({query}) as filtered"
    cur.execute(count_query, params)
    total = cur.fetchone()['total']
    
    # Пагинация
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])
    
    cur.execute(query, params)
    blocks = cur.fetchall()
    
    # Получить уникальные типы и вкладки для фильтров
    cur.execute("SELECT DISTINCT block_type FROM kb_blocks ORDER BY block_type")
    block_types = [row['block_type'] for row in cur.fetchall()]
    
    cur.execute("SELECT DISTINCT tab_name FROM kb_blocks WHERE tab_name IS NOT NULL ORDER BY tab_name")
    tab_names = [row['tab_name'] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return render_template('blocks_list.html',
                         blocks=blocks,
                         block_types=block_types,
                         tab_names=tab_names,
                         page=page,
                         per_page=per_page,
                         total=total,
                         block_type=block_type,
                         tab_name=tab_name,
                         is_active=is_active,
                         search=search)


@app.route('/blocks/<int:block_id>')
def block_detail(block_id):
    """Детальная информация о блоке"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT * FROM kb_blocks WHERE id = %s
    """, (block_id,))
    
    block = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if not block:
        flash('Блок не найден', 'error')
        return redirect(url_for('blocks_list'))
    
    return render_template('block_detail.html', block=block)


@app.route('/api/blocks/mark-inactive', methods=['POST'])
def api_mark_inactive():
    """API: Пометить блоки как неактивные"""
    data = request.json
    block_ids = data.get('block_ids', [])
    
    if not block_ids:
        return jsonify({'error': 'Не указаны ID блоков'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE kb_blocks 
            SET is_active = FALSE,
                updated_at = NOW()
            WHERE id = ANY(%s)
        """, (block_ids,))
        
        count = cur.rowcount
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Помечено как неактивных: {count}',
            'count': count
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/blocks/mark-active', methods=['POST'])
def api_mark_active():
    """API: Пометить блоки как активные"""
    data = request.json
    block_ids = data.get('block_ids', [])
    
    if not block_ids:
        return jsonify({'error': 'Не указаны ID блоков'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE kb_blocks 
            SET is_active = TRUE,
                updated_at = NOW()
            WHERE id = ANY(%s)
        """, (block_ids,))
        
        count = cur.rowcount
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Помечено как активных: {count}',
            'count': count
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/blocks/delete', methods=['POST'])
def api_delete():
    """API: Удалить блоки"""
    data = request.json
    block_ids = data.get('block_ids', [])
    create_backup = data.get('create_backup', True)
    
    if not block_ids:
        return jsonify({'error': 'Не указаны ID блоков'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Создать бэкап
        if create_backup:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kb_blocks_backup AS
                SELECT * FROM kb_blocks WHERE FALSE
            """)
            
            cur.execute("""
                INSERT INTO kb_blocks_backup
                SELECT * FROM kb_blocks WHERE id = ANY(%s)
            """, (block_ids,))
        
        # Удалить блоки
        cur.execute("""
            DELETE FROM kb_blocks
            WHERE id = ANY(%s)
        """, (block_ids,))
        
        count = cur.rowcount
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Удалено блоков: {count}',
            'count': count
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/duplicates')
def duplicates_list():
    """Список дубликатов"""
    block_type = request.args.get('block_type', '')
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT block_type, 
               tab_name,
               content_hash,
               COUNT(*) as count,
               ARRAY_AGG(id ORDER BY created_at) as ids,
               ARRAY_AGG(created_at ORDER BY created_at) as created_dates
        FROM kb_blocks
        WHERE is_active = TRUE
    """
    
    params = []
    if block_type:
        query += " AND block_type = %s"
        params.append(block_type)
    
    query += """
        GROUP BY block_type, tab_name, content_hash
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """
    
    cur.execute(query, params)
    duplicates = cur.fetchall()
    
    # Получить уникальные типы для фильтра
    cur.execute("SELECT DISTINCT block_type FROM kb_blocks ORDER BY block_type")
    block_types = [row['block_type'] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return render_template('duplicates_list.html',
                         duplicates=duplicates,
                         block_types=block_types,
                         block_type=block_type)


@app.route('/api/duplicates/cleanup', methods=['POST'])
def api_cleanup_duplicates():
    """API: Автоматическая очистка дубликатов"""
    data = request.json
    block_type = data.get('block_type', None)
    keep_oldest = data.get('keep_oldest', True)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        query = """
            WITH duplicates AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY block_type, content_hash 
                           ORDER BY created_at ASC
                       ) as rn
                FROM kb_blocks
                WHERE is_active = TRUE
        """
        
        params = []
        if block_type:
            query += " AND block_type = %s"
            params.append(block_type)
        
        query += """
            )
            UPDATE kb_blocks kb
            SET is_active = FALSE,
                updated_at = NOW()
            FROM duplicates d
            WHERE kb.id = d.id
              AND d.rn > 1
        """
        
        cur.execute(query, params)
        count = cur.rowcount
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Помечено как неактивных дубликатов: {count}',
            'count': count
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/statistics')
def statistics():
    """Статистика по блокам"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Статистика по типам
    cur.execute("""
        SELECT 
            block_type,
            COUNT(*) FILTER (WHERE is_active = TRUE) as active_count,
            COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_count,
            COUNT(*) as total_count
        FROM kb_blocks
        GROUP BY block_type
        ORDER BY total_count DESC
    """)
    stats_by_type = cur.fetchall()
    
    # Статистика по вкладкам
    cur.execute("""
        SELECT 
            tab_name,
            COUNT(*) FILTER (WHERE is_active = TRUE) as active_count,
            COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_count,
            COUNT(*) as total_count
        FROM kb_blocks
        WHERE tab_name IS NOT NULL
        GROUP BY tab_name
        ORDER BY total_count DESC
    """)
    stats_by_tab = cur.fetchall()
    
    # Общая статистика
    cur.execute("""
        SELECT 
            COUNT(*) as total_blocks,
            COUNT(*) FILTER (WHERE is_active = TRUE) as active_blocks,
            COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_blocks
        FROM kb_blocks
    """)
    total_stats = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return render_template('statistics.html',
                         stats_by_type=stats_by_type,
                         stats_by_tab=stats_by_tab,
                         total_stats=total_stats)


@app.route('/reprocess')
def reprocess_page():
    """Страница вторичной обработки"""
    block_ids = request.args.get('block_ids', '')
    block_ids_list = [int(id.strip()) for id in block_ids.split(',') if id.strip()] if block_ids else []
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    blocks = []
    if block_ids_list:
        cur.execute("""
            SELECT id, block_id, block_type, tab_name, content, is_active
            FROM kb_blocks
            WHERE id = ANY(%s)
            ORDER BY id
        """, (block_ids_list,))
        blocks = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('reprocess.html', blocks=blocks, block_ids=block_ids)


@app.route('/api/blocks/reprocess', methods=['POST'])
def api_reprocess():
    """API: Вторичная обработка блоков через Gemini"""
    data = request.json
    block_ids = data.get('block_ids', [])
    additional_instructions = data.get('additional_instructions', '')
    
    if not block_ids:
        return jsonify({'error': 'Не указаны ID блоков'}), 400
    
    if not additional_instructions:
        return jsonify({'error': 'Не указаны дополнительные инструкции'}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Получить блоки для обработки
        cur.execute("""
            SELECT id, block_id, block_type, tab_name, content, content_hash
            FROM kb_blocks
            WHERE id = ANY(%s)
            ORDER BY id
        """, (block_ids,))
        
        blocks = cur.fetchall()
        
        if not blocks:
            return jsonify({'error': 'Блоки не найдены'}), 404
        
        # Подготовить данные для Gemini
        blocks_data = []
        for block in blocks:
            blocks_data.append({
                'id': block['id'],
                'block_id': block['block_id'],
                'type': block['block_type'],
                'tab': block['tab_name'],
                'content': block['content']
            })
        
        # Создать промпт для Gemini
        prompt = create_reprocess_prompt(blocks_data, additional_instructions)
        system_prompt = create_reprocess_system_prompt()
        
        # Вызвать Gemini API
        if GEMINI_AVAILABLE:
            try:
                # Запускаем асинхронную функцию в синхронном контексте
                processed_result = asyncio.run(
                    call_gemini_reprocess(system_prompt, prompt)
                )
                
                if processed_result and 'blocks' in processed_result:
                    # Обновить блоки в БД
                    updated_count = update_blocks_from_reprocess(cur, processed_result['blocks'])
                    conn.commit()
                    
                    return jsonify({
                        'success': True,
                        'message': f'Обработано блоков: {updated_count} из {len(blocks)}',
                        'blocks_count': len(blocks),
                        'updated_count': updated_count,
                        'instructions': additional_instructions
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Gemini вернул некорректный ответ',
                        'prompt': prompt  # Для отладки
                    }), 500
                    
            except Exception as e:
                conn.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Ошибка при вызове Gemini: {str(e)}',
                    'prompt': prompt  # Для отладки
                }), 500
        else:
            # Режим демо - возвращаем промпт без реальной обработки
            return jsonify({
                'success': False,
                'error': 'Gemini API не доступен. Установите kb-service и настройте GEMINI_API_KEY.',
                'prompt': prompt,
                'demo_mode': True
            }), 503
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


async def call_gemini_reprocess(system_prompt: str, prompt: str) -> Dict:
    """Вызов Gemini API для вторичной обработки"""
    gemini_service = get_gemini_text_service()
    result = await gemini_service.generate_json(
        prompt=prompt,
        system_prompt=system_prompt,
        max_output_tokens=8192
    )
    return result


def update_blocks_from_reprocess(cur, processed_blocks: List[Dict]) -> int:
    """Обновить блоки в БД на основе результатов обработки"""
    updated_count = 0
    
    for processed_block in processed_blocks:
        block_id = processed_block.get('id')
        new_content = processed_block.get('content', '')
        new_type = processed_block.get('type')
        new_tab = processed_block.get('tab')
        
        if not block_id or not new_content:
            continue
        
        # Вычислить новый hash
        content_hash = hashlib.sha256(new_content.encode('utf-8')).hexdigest()
        
        # Обновить блок
        cur.execute("""
            UPDATE kb_blocks
            SET content = %s,
                content_hash = %s,
                block_type = COALESCE(%s, block_type),
                tab_name = COALESCE(%s, tab_name),
                updated_at = NOW()
            WHERE id = %s
        """, (new_content, content_hash, new_type, new_tab, block_id))
        
        if cur.rowcount > 0:
            updated_count += 1
    
    return updated_count


def create_reprocess_system_prompt() -> str:
    """Создает системный промпт для вторичной обработки"""
    return """
Ты - эксперт по обработке и улучшению контента для Knowledge Base.

Твоя задача:
1. Получить блоки контента из KB
2. Обработать их согласно дополнительным инструкциям пользователя
3. Улучшить, дополнить или изменить контент
4. Сохранить структуру и метаданные (тип, вкладка)
5. Вернуть результат в строгом JSON формате

Важно:
- Сохраняй все важные детали из исходного контента
- Не теряй информацию
- Улучшай качество, но не меняй смысл без необходимости
- Сохраняй тип блока (block_type) и вкладку (tab_name)
"""


def create_reprocess_prompt(blocks_data: List[Dict], additional_instructions: str) -> str:
    """Создает промпт для вторичной обработки блоков"""
    
    blocks_text = "\n\n".join([
        f"=== Блок {i+1} ===\nID: {block['id']}\nBlock ID: {block['block_id']}\nType: {block['type']}\nTab: {block['tab'] or 'N/A'}\nContent:\n{block['content']}"
        for i, block in enumerate(blocks_data)
    ])
    
    # Формируем пример JSON для каждого блока
    example_blocks = ",\n    ".join([
        f'{{\n      "id": {block["id"]},\n      "block_id": "{block["block_id"]}",\n      "type": "{block["type"]}",\n      "tab": "{block["tab"] or ""}",\n      "content": "...обработанный контент...",\n      "changes": "Описание внесенных изменений"\n    }}'
        for block in blocks_data
    ])
    
    prompt = f"""
ВТОРИЧНАЯ ОБРАБОТКА БЛОКОВ ИЗ KNOWLEDGE BASE

Исходные блоки для обработки:

{blocks_text}

ДОПОЛНИТЕЛЬНЫЕ ИНСТРУКЦИИ ОТ ПОЛЬЗОВАТЕЛЯ:
{additional_instructions}

ЗАДАЧА:
1. Обработать каждый блок согласно дополнительным инструкциям
2. Улучшить, дополнить или изменить контент
3. Сохранить метаданные (id, block_id, type, tab) для каждого блока
4. Вернуть все блоки в формате JSON

ТРЕБОВАНИЯ:
- Сохранить id, block_id, type, tab для каждого блока
- Улучшить content согласно инструкциям
- Не терять важную информацию из исходного контента
- Добавить новую информацию, если требуется
- В поле "changes" опиши кратко, что было изменено

Верни результат ТОЛЬКО в формате JSON (без дополнительного текста):
{{
  "blocks": [
    {example_blocks}
  ]
}}
"""
    
    return prompt


if __name__ == '__main__':
    # Убедиться, что колонка is_active существует
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE kb_blocks 
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE
    """)
    conn.commit()
    cur.close()
    conn.close()
    
    app.run(debug=True, host='0.0.0.0', port=5000)

