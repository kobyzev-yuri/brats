-- Создание таблицы products для каталога объектов недвижимости

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    
    -- Связь с каталогом amoCRM
    amocrm_catalog_id INTEGER UNIQUE,  -- ID товара в каталоге amoCRM
    amocrm_sku VARCHAR(100),  -- SKU из amoCRM (для синхронизации)
    sync_status VARCHAR(50) DEFAULT 'synced',  -- 'synced', 'pending', 'error'
    last_synced_at TIMESTAMP,  -- Дата последней синхронизации
    
    -- Базовые данные (синхронизируются из amoCRM)
    code VARCHAR(50) UNIQUE,  -- Внутренний код (может совпадать с SKU)
    name VARCHAR(200),  -- Название из amoCRM
    category VARCHAR(100),  -- Тип объекта (например, "BLACK_BOX", "WHITE_BOX", "STANDARD", "DESIGN")
    
    -- Ценовая информация (из amoCRM, может быть переопределена)
    price_base DECIMAL(12, 2),  -- Базовая цена из amoCRM
    price_current DECIMAL(12, 2),  -- Текущая цена (может быть со скидкой)
    price_currency VARCHAR(3) DEFAULT 'RUB',
    discount_percent DECIMAL(5, 2),  -- Процент скидки (если есть)
    
    -- Технические характеристики (структурированные)
    area_total DECIMAL(8, 2),  -- Общая площадь (кв.м)
    area_living DECIMAL(8, 2),  -- Жилая площадь (кв.м)
    area_land DECIMAL(8, 2),  -- Площадь участка (соток или кв.м)
    rooms_count INTEGER,  -- Количество комнат
    floors_count INTEGER,  -- Количество этажей
    
    -- Дополнительные характеристики (JSONB для гибкости)
    features JSONB DEFAULT '{}'::jsonb,  -- {
                                         --   "finishing": "BLACK_BOX",
                                         --   "heating": "автономное",
                                         --   "water": "скважина",
                                         --   "sewerage": "септик",
                                         --   "parking": true,
                                         --   "terrace": true,
                                         --   "fireplace": false
                                         -- }
    
    -- Описание для LLM (расширенное, может быть дополнено)
    description TEXT,  -- Полное описание объекта для промптов (из amoCRM + дополнения)
    description_short TEXT,  -- Краткое описание из amoCRM
    advantages TEXT[],  -- Массив преимуществ (для обработки возражений)
    objections_handling JSONB DEFAULT '{}'::jsonb,  -- Типовые возражения и ответы
    
    -- Векторное представление для семантического поиска
    description_embedding vector(1536),  -- Эмбеддинг описания для RAG
    
    -- Статус и доступность
    status VARCHAR(50),  -- 'available', 'reserved', 'sold', 'construction'
    availability_date DATE,  -- Дата готовности/сдачи
    
    -- Метаданные
    location JSONB DEFAULT '{}'::jsonb,  -- {"address": "...", "coordinates": {...}, "district": "..."}
    photos_urls TEXT[],  -- Ссылки на фото
    floor_plan_url VARCHAR(500),  -- Ссылка на планировку
    
    -- Данные из amoCRM (JSONB для гибкости)
    amocrm_data JSONB DEFAULT '{}'::jsonb,  -- Полные данные из amoCRM (custom_fields и т.д.)
    
    -- Мультитенантность
    settlement_id INTEGER,  -- ID поселка
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для синхронизации с amoCRM
CREATE INDEX IF NOT EXISTS idx_products_amocrm_catalog ON products(amocrm_catalog_id);
CREATE INDEX IF NOT EXISTS idx_products_amocrm_sku ON products(amocrm_sku);
CREATE INDEX IF NOT EXISTS idx_products_sync_status ON products(sync_status, last_synced_at);

-- Индекс для векторного поиска объектов по описанию
CREATE INDEX IF NOT EXISTS idx_products_description_embedding 
    ON products USING ivfflat (description_embedding vector_cosine_ops)
    WITH (lists = 100);

-- Индексы для быстрого поиска по характеристикам
CREATE INDEX IF NOT EXISTS idx_products_category_status ON products(category, status);
CREATE INDEX IF NOT EXISTS idx_products_features_gin ON products USING GIN (features);
CREATE INDEX IF NOT EXISTS idx_products_price ON products(price_current);
CREATE INDEX IF NOT EXISTS idx_products_settlement ON products(settlement_id);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);

COMMENT ON TABLE products IS 'Каталог объектов недвижимости. Синхронизируется с каталогом товаров amoCRM.';
COMMENT ON COLUMN products.description_embedding IS 'Векторное представление описания для семантического поиска через pgvector';

















