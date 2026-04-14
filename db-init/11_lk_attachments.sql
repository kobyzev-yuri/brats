-- Документы, загруженные клиентом в ЛК (скан паспорта и т.д.). Привязаны к диалогу.

CREATE TABLE IF NOT EXISTS lk_attachments (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(128) DEFAULT 'application/octet-stream',
    file_data BYTEA NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lk_attachments_conversation ON lk_attachments(conversation_id);

COMMENT ON TABLE lk_attachments IS 'Файлы, загруженные клиентом в ЛК (паспорт, СНИЛС и т.д.). Используются для сделки и шаблонов.';
