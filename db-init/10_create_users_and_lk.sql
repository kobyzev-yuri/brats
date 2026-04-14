-- Личный кабинет (ЛК): пользователи и привязка диалогов
-- Логин: email или телефон. Пароль по умолчанию — номер телефона (передаётся клиенту при записи на просмотр).

CREATE TABLE IF NOT EXISTS lk_users (
    id SERIAL PRIMARY KEY,
    login VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lk_users_phone ON lk_users(phone);
CREATE INDEX IF NOT EXISTS idx_lk_users_email ON lk_users(email) WHERE email IS NOT NULL AND email != '';

COMMENT ON TABLE lk_users IS 'Пользователи личного кабинета. Создаются при создании контакта из чата (запись на просмотр). Логин: email или телефон, пароль: телефон.';

-- Сессии для входа в ЛК (токен возвращается при логине, проверяется в API)
CREATE TABLE IF NOT EXISTS lk_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES lk_users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_lk_sessions_token ON lk_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_lk_sessions_user ON lk_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_lk_sessions_expires ON lk_sessions(expires_at);

COMMENT ON TABLE lk_sessions IS 'Сессии входа в ЛК. token_hash = хэш выданного токена.';

-- Привязка диалога к пользователю ЛК (один пользователь — один активный диалог с агентом)
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES lk_users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id) WHERE user_id IS NOT NULL;

COMMENT ON COLUMN conversations.user_id IS 'Пользователь ЛК, к которому привязан диалог. Заполняется при создании контакта из чата (создаётся пользователь ЛК и связь).';
