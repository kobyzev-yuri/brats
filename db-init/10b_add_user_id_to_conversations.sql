-- Добавить user_id в conversations (если таблица в другой БД, чем lk_users).
-- Сначала в этой же БД должны быть lk_users (миграция 10 или 10a).
-- Запуск: psql $DATABASE_URL -f 10b_add_user_id_to_conversations.sql

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES lk_users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id) WHERE user_id IS NOT NULL;

COMMENT ON COLUMN conversations.user_id IS 'Пользователь ЛК, к которому привязан диалог.';
