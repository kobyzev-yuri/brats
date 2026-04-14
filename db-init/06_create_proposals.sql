-- Создание таблицы proposals для коммерческих предложений

CREATE TABLE IF NOT EXISTS proposals (
    id SERIAL PRIMARY KEY,
    
    -- Связь с диалогом и лидом
    conversation_id INTEGER REFERENCES conversations(id),
    amocrm_lead_id INTEGER,  -- ID лида в amoCRM
    
    -- Версионирование
    version INTEGER DEFAULT 1,  -- Версия КП (1, 2, 3...)
    parent_proposal_id INTEGER REFERENCES proposals(id),  -- Ссылка на родительскую версию (для модификаций)
    
    -- Статус КП
    status VARCHAR(50) DEFAULT 'draft',  -- 'draft', 'sent', 'modified', 'finalized', 'accepted', 'rejected', 'contract_created'
    
    -- Структурированное содержимое КП
    content_structured JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {
                                                            --   "header": {...},
                                                            --   "client_info": {...},
                                                            --   "objects": [...],
                                                            --   "pricing": {...},
                                                            --   "terms": {...},
                                                            --   "footer": {...}
                                                            -- }
    
    -- Текстовое представление (для отправки клиенту)
    content_text TEXT,  -- Сгенерированный текст КП
    
    -- Связанные объекты
    product_ids INTEGER[],  -- Массив ID объектов из таблицы products
    
    -- История изменений
    changes_history JSONB DEFAULT '[]'::jsonb,  -- [
                                                --   {
                                                --     "version": 2,
                                                --     "changed_at": "2026-02-03T10:00:00",
                                                --     "changes": {"price": {"old": 5000000, "new": 4800000}},
                                                --     "reason": "Клиент попросил снизить цену"
                                                --   }
                                                -- ]
    
    -- Даты
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,  -- Когда отправлено клиенту
    finalized_at TIMESTAMP,  -- Когда финализировано
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proposals_conversation ON proposals(conversation_id);
CREATE INDEX IF NOT EXISTS idx_proposals_amocrm_lead ON proposals(amocrm_lead_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_proposals_parent ON proposals(parent_proposal_id);
CREATE INDEX IF NOT EXISTS idx_proposals_created ON proposals(created_at);

COMMENT ON TABLE proposals IS 'Коммерческие предложения. Версионируются при модификации.';
COMMENT ON COLUMN proposals.content_structured IS 'Структурированное содержимое КП в формате JSON';
COMMENT ON COLUMN proposals.changes_history IS 'История изменений КП (для каждой версии)';

















