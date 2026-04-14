"""
Утилиты для управления блоками в PostgreSQL KB
Поддержка пометки как неактивные и удаления
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Optional, Dict, Any
from datetime import datetime

class KBPostgreSQLManager:
    """Менеджер для работы с KB в PostgreSQL"""
    
    def __init__(self, connection_string: str):
        """
        Инициализация менеджера
        
        Args:
            connection_string: Строка подключения к PostgreSQL
                Пример: "postgresql://user:password@localhost:5432/kb_db"
        """
        self.conn_string = connection_string
        self.conn = None
    
    def connect(self):
        """Установить соединение с БД"""
        self.conn = psycopg2.connect(self.conn_string)
        return self.conn
    
    def close(self):
        """Закрыть соединение"""
        if self.conn:
            self.conn.close()
    
    def mark_as_inactive(self, block_ids: List[int]) -> int:
        """
        Пометить блоки как неактивные
        
        Args:
            block_ids: Список ID блоков для пометки
            
        Returns:
            Количество обновленных блоков
        """
        if not self.conn:
            self.connect()
        
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE kb_blocks 
                SET is_active = FALSE,
                    updated_at = NOW()
                WHERE id = ANY(%s)
            """, (block_ids,))
            
            count = cur.rowcount
            self.conn.commit()
            return count
    
    def delete_blocks(self, block_ids: List[int], create_backup: bool = True) -> int:
        """
        Удалить блоки из БД
        
        Args:
            block_ids: Список ID блоков для удаления
            create_backup: Создать бэкап перед удалением
            
        Returns:
            Количество удаленных блоков
        """
        if not self.conn:
            self.connect()
        
        with self.conn.cursor() as cur:
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
            self.conn.commit()
            return count
    
    def find_duplicates(self, block_type: Optional[str] = None) -> List[Dict]:
        """
        Найти дубликаты блоков
        
        Args:
            block_type: Тип блока для фильтрации (опционально)
            
        Returns:
            Список дубликатов
        """
        if not self.conn:
            self.connect()
        
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
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def get_block_info(self, block_ids: List[int]) -> List[Dict]:
        """
        Получить информацию о блоках
        
        Args:
            block_ids: Список ID блоков
            
        Returns:
            Информация о блоках
        """
        if not self.conn:
            self.connect()
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, block_id, block_type, tab_name, is_active, 
                       created_at, updated_at
                FROM kb_blocks
                WHERE id = ANY(%s)
                ORDER BY id
            """, (block_ids,))
            return cur.fetchall()
    
    def restore_from_backup(self, block_ids: List[int]) -> int:
        """
        Восстановить блоки из бэкапа
        
        Args:
            block_ids: Список ID блоков для восстановления
            
        Returns:
            Количество восстановленных блоков
        """
        if not self.conn:
            self.connect()
        
        with self.conn.cursor() as cur:
            # Проверить существование таблицы бэкапа
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'kb_blocks_backup'
                )
            """)
            
            if not cur.fetchone()[0]:
                raise Exception("Таблица бэкапа не найдена")
            
            # Восстановить блоки
            cur.execute("""
                INSERT INTO kb_blocks
                SELECT * FROM kb_blocks_backup
                WHERE id = ANY(%s)
                ON CONFLICT (block_id) DO NOTHING
            """, (block_ids,))
            
            count = cur.rowcount
            self.conn.commit()
            return count
    
    def ensure_is_active_column(self):
        """Убедиться, что колонка is_active существует"""
        if not self.conn:
            self.connect()
        
        with self.conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE kb_blocks 
                ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE
            """)
            self.conn.commit()


# Пример использования
if __name__ == "__main__":
    # Настройки подключения
    CONNECTION_STRING = "postgresql://user:password@localhost:5432/kb_db"
    
    # Создать менеджер
    manager = KBPostgreSQLManager(CONNECTION_STRING)
    
    try:
        # Убедиться, что колонка is_active существует
        manager.ensure_is_active_column()
        
        # Получить информацию о проблемных блоках
        print("Информация о блоках 45, 46, 47:")
        blocks_info = manager.get_block_info([45, 46, 47])
        for block in blocks_info:
            print(f"ID: {block['id']}, Type: {block['block_type']}, "
                  f"Tab: {block['tab_name']}, Active: {block['is_active']}")
        
        # Вариант 1: Пометить как неактивные
        print("\nПомечаем блоки как неактивные...")
        count = manager.mark_as_inactive([45, 46, 47])
        print(f"Обновлено блоков: {count}")
        
        # Вариант 2: Удалить блоки (раскомментируй если нужно)
        # print("\nУдаляем блоки...")
        # count = manager.delete_blocks([45, 46, 47], create_backup=True)
        # print(f"Удалено блоков: {count}")
        
        # Найти дубликаты
        print("\nПоиск дубликатов типа product_info...")
        duplicates = manager.find_duplicates(block_type='product_info')
        for dup in duplicates:
            print(f"Тип: {dup['block_type']}, "
                  f"Вкладка: {dup['tab_name']}, "
                  f"Количество: {dup['count']}, "
                  f"IDs: {dup['ids']}")
        
    finally:
        manager.close()



