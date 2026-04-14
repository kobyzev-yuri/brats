-- Календарь показов и шаблоны документов (КП, договоры)
-- Соответствует STANDARDS_IMPLEMENTATION_PLAN.md

-- Календарь показов: слоты для записи на просмотр
CREATE TABLE IF NOT EXISTS viewing_slots (
    id SERIAL PRIMARY KEY,
    settlement_id INTEGER,
    object_id INTEGER REFERENCES products(id),
    object_name VARCHAR(200),
    slot_start TIMESTAMP NOT NULL,
    slot_end TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'free' CHECK (status IN ('free', 'booked', 'completed', 'cancelled')),
    contact_name VARCHAR(200),
    contact_phone VARCHAR(50),
    amocrm_lead_id INTEGER,
    conversation_id INTEGER REFERENCES conversations(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_viewing_slots_settlement ON viewing_slots(settlement_id);
CREATE INDEX IF NOT EXISTS idx_viewing_slots_start ON viewing_slots(slot_start);
CREATE INDEX IF NOT EXISTS idx_viewing_slots_status ON viewing_slots(status);
CREATE INDEX IF NOT EXISTS idx_viewing_slots_amocrm_lead ON viewing_slots(amocrm_lead_id);

COMMENT ON TABLE viewing_slots IS 'Слоты для записи на просмотр объектов. Стандарт ведения в PostgreSQL.';

-- Шаблоны документов (КП, договоры)
CREATE TABLE IF NOT EXISTS document_templates (
    id SERIAL PRIMARY KEY,
    type VARCHAR(30) NOT NULL CHECK (type IN ('proposal', 'contract')),
    name VARCHAR(200) NOT NULL,
    body TEXT,
    body_structured JSONB DEFAULT '{}'::jsonb,
    settlement_id INTEGER,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_templates_type ON document_templates(type);
CREATE INDEX IF NOT EXISTS idx_document_templates_active ON document_templates(is_active) WHERE is_active = true;

COMMENT ON TABLE document_templates IS 'Шаблоны КП и договоров. Генерация по данным из products/conversation/lead.';
