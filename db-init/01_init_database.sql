-- Инициализация базы данных brats
-- Создание базы данных и расширений

-- Создание базы данных (выполняется от пользователя postgres)
-- CREATE DATABASE brats WITH ENCODING 'UTF8' LC_COLLATE='ru_RU.UTF-8' LC_CTYPE='ru_RU.UTF-8';

-- Подключение к базе данных brats
-- \c brats

-- Создание расширения pgvector для векторного поиска
CREATE EXTENSION IF NOT EXISTS vector;

-- Проверка установки расширения
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'Расширение pgvector не установлено. Установите его: CREATE EXTENSION vector;';
    END IF;
END $$;

-- Комментарий для документации
COMMENT ON EXTENSION vector IS 'Расширение pgvector для векторного поиска в базе знаний и каталоге объектов';

















