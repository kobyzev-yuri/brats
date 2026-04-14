-- Привязка диалога к сессии чата (сайт/Telegram/Avito) для памяти диалога
-- Позволяет находить conversation по channel + external_id и хранить историю в messages

ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS external_id VARCHAR(200);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_channel_external
  ON conversations (channel, external_id)
  WHERE external_id IS NOT NULL AND external_id != '';

COMMENT ON COLUMN conversations.external_id IS 'Идентификатор сессии чата (user_id, chat_id с сайта/Telegram/Avito) для загрузки истории.';
