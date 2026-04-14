-- Создание таблицы knowledge_base для базы знаний
-- Используется для хранения chunks с векторными embeddings

CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    
    -- Контент chunk'а
    content TEXT NOT NULL,  -- Текстовая информация для RAG
    
    -- Векторное представление для семантического поиска
    -- Размерность зависит от модели: 
    -- - OpenAI text-embedding-3-small: 1536
    -- - multilingual-e5-base: 768
    -- Используем 1536 для совместимости с OpenAI, но можно изменить на 768 для HF моделей
    embedding vector(1536),  -- Эмбеддинг контента
    
    -- Метаданные для фильтрации и контекста
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {
                                                    --   "category": "product_info | sales_script | objection_handling | target_audience | tone_of_voice | contacts | pricing | location",
                                                    --   "subcategory": "опциональная подкатегория",
                                                    --   "target_audience": "end_buyer | realtor | both",
                                                    --   "priority": "high | medium | low",
                                                    --   "tags": ["дом", "цена", "коммуникации"],
                                                    --   "source": "kb_info.txt",
                                                    --   "version": "1.0",
                                                    --   "related_links": ["https://..."],
                                                    --   "settlement_id": 1,
                                                    --   "context": {
                                                    --     "use_case": "greeting | qualification | proposal | objection | closing",
                                                    --     "stage": "early | middle | late"
                                                    --   }
                                                    -- }
    
    -- Версионирование и обновления
    version VARCHAR(20) DEFAULT '1.0',
    last_updated TIMESTAMP DEFAULT NOW(),
    
    -- Статус
    is_active BOOLEAN DEFAULT TRUE,  -- Для мягкого удаления/отключения
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индекс для векторного поиска (IVFFlat для быстрого поиска)
-- IVFFlat индекс требует минимум 1000 векторов для эффективной работы
-- Если данных меньше, можно временно использовать обычный индекс или создать позже
CREATE INDEX IF NOT EXISTS idx_knowledge_base_embedding 
    ON knowledge_base USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);  -- Количество списков зависит от размера данных
                         -- Рекомендуется: lists = rows / 1000 (минимум 10, максимум 1000)

-- Индексы для фильтрации по метаданным
CREATE INDEX IF NOT EXISTS idx_knowledge_base_metadata_gin 
    ON knowledge_base USING GIN (metadata);  -- Для поиска по JSONB

CREATE INDEX IF NOT EXISTS idx_knowledge_base_category_audience 
    ON knowledge_base ((metadata->>'category'), (metadata->>'target_audience'));

CREATE INDEX IF NOT EXISTS idx_knowledge_base_priority 
    ON knowledge_base ((metadata->>'priority'));

CREATE INDEX IF NOT EXISTS idx_knowledge_base_settlement 
    ON knowledge_base ((metadata->>'settlement_id'));

CREATE INDEX IF NOT EXISTS idx_knowledge_base_active_updated 
    ON knowledge_base (is_active, last_updated);

-- Индекс для полнотекстового поиска по content (опционально)
CREATE INDEX IF NOT EXISTS idx_knowledge_base_content_fts 
    ON knowledge_base USING GIN (to_tsvector('russian', content));

-- Комментарии для документации
COMMENT ON TABLE knowledge_base IS 'База знаний для RAG (Retrieval Augmented Generation). Хранит chunks с векторными embeddings для семантического поиска.';
COMMENT ON COLUMN knowledge_base.content IS 'Текстовое содержимое chunk для использования в RAG';
COMMENT ON COLUMN knowledge_base.embedding IS 'Векторное представление контента для семантического поиска через pgvector';
COMMENT ON COLUMN knowledge_base.metadata IS 'Метаданные chunk: категория, целевая аудитория, приоритет, теги, источник и т.д.';
COMMENT ON COLUMN knowledge_base.is_active IS 'Флаг активности chunk (для мягкого удаления)';

















