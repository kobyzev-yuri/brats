-- Создание таблиц для диалогов и сообщений

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    
    -- Связь с amoCRM
    amocrm_lead_id INTEGER,  -- ID лида в amoCRM (может быть NULL для анонимных)
    amocrm_contact_id INTEGER,  -- ID контакта в amoCRM
    
    -- Состояние FSM
    state VARCHAR(50) DEFAULT 'GREETING',  -- Текущее состояние FSM (GREETING, QUALIFYING, OBJECTION_1/2/3, PROPOSAL, HANDOFF)
    
    -- Извлечённые данные (слоты)
    slots JSONB DEFAULT '{}'::jsonb,  -- {
                                       --   "budget": 5000000,
                                       --   "deadline": "2026-06-01",
                                       --   "preferences": {"rooms": 3, "area": 120},
                                       --   "client_name": "Иван",
                                       --   "phone": "+7...",
                                       --   "email": "..."
                                       -- }
    
    -- Счётчики возражений
    objection_count INTEGER DEFAULT 0,
    
    -- Метаданные
    channel VARCHAR(50),  -- 'telegram', 'website', 'avito', 'phone'
    settlement_id INTEGER,  -- ID поселка для мультитенантности
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_amocrm_lead ON conversations(amocrm_lead_id);
CREATE INDEX IF NOT EXISTS idx_conversations_amocrm_contact ON conversations(amocrm_contact_id);
CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(state);
CREATE INDEX IF NOT EXISTS idx_conversations_settlement ON conversations(settlement_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);

COMMENT ON TABLE conversations IS 'Диалоги с клиентами. Хранит состояние FSM и извлечённые данные (слоты).';
COMMENT ON COLUMN conversations.state IS 'Текущее состояние FSM агента продаж';
COMMENT ON COLUMN conversations.slots IS 'Извлечённые данные из диалога (бюджет, сроки, предпочтения, контакты)';


CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    
    -- Роль отправителя
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),  -- 'user' или 'assistant'
    
    -- Содержимое сообщения
    content TEXT NOT NULL,
    
    -- Метаданные сообщения
    metadata JSONB DEFAULT '{}'::jsonb,  -- {
                                         --   "intent": "greeting",
                                         --   "sentiment": "positive",
                                         --   "extracted_data": {...},
                                         --   "kb_chunks_used": [1, 2, 3],
                                         --   "products_searched": [10, 20]
                                         -- }
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

COMMENT ON TABLE messages IS 'История сообщений в диалогах. Каждое сообщение связано с conversation.';
COMMENT ON COLUMN messages.metadata IS 'Метаданные: интенты, sentiment, использованные chunks KB, найденные объекты';

















