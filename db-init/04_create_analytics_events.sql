-- Создание таблицы analytics_events для событий аналитики

CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,
    
    -- Связь с лидом (может быть NULL для анонимных)
    amocrm_lead_id INTEGER,
    
    -- Тип события
    event_type VARCHAR(50) NOT NULL,  -- 'page_view', 'goal', 'hot_lead', 'question_asked', 'objection_detected', 'form_submitted', 'chat_message', ...
    
    -- Детали события
    event_data JSONB DEFAULT '{}'::jsonb,  -- {
                                            --   "url": "...",
                                            --   "time_on_page": 120,
                                            --   "goal_id": 12345,
                                            --   "message_text": "...",
                                            --   "objection_type": "price",
                                            --   "form_data": {...}
                                            -- }
    
    -- Источник события
    source VARCHAR(50) NOT NULL,  -- 'yandex_metrika', 'agent_conversation', 'amocrm_note', 'site_chat', 'form', 'avito', 'telegram'
    
    -- Метаданные
    settlement_id INTEGER,  -- ID поселка для мультитенантности
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_events_lead ON analytics_events(amocrm_lead_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_events_source ON analytics_events(source);
CREATE INDEX IF NOT EXISTS idx_analytics_events_created ON analytics_events(created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_events_settlement ON analytics_events(settlement_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_data_gin ON analytics_events USING GIN (event_data);

COMMENT ON TABLE analytics_events IS 'Агрегатор событий из разных источников для анализа поведения и обогащения KB';
COMMENT ON COLUMN analytics_events.event_type IS 'Тип события: page_view, goal, hot_lead, question_asked, objection_detected и т.д.';
COMMENT ON COLUMN analytics_events.source IS 'Источник события: yandex_metrika, agent_conversation, amocrm_note, site_chat, form и т.д.';

















