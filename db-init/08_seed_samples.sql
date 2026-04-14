-- Минимальные образцы: каталог объектов, шаблоны КП/договора, календарь показов
-- Разгружает менеджеров от рутины, задаёт стандарты (STANDARDS_IMPLEMENTATION_PLAN.md)

-- ========== 1. Продуктовый каталог (образцы объектов) ==========
INSERT INTO products (
    code, name, category,
    price_base, price_current, price_currency,
    area_total, area_living, area_land, rooms_count, floors_count,
    features, description_short, description, status, settlement_id
) VALUES
(
    'INN-140-BB',
    'Дом 140 м² с черновой отделкой Black Box',
    'BLACK_BOX',
    8350000.00, 8350000.00, 'RUB',
    140.00, 80.00, 4.00, 5, 2,
    '{"finishing": "BLACK_BOX", "heating": "автономное", "water": "скважина", "sewerage": "септик"}'::jsonb,
    '1 этаж 80 м², 2 этаж 60 м². Черновая отделка. Стены и перегородки, коммуникации, окна и двери.',
    'Коттеджный посёлок «Инноваторы Клуб», Краснодар. Дом 140 м² (1 этаж 80 м², 2 этаж 60 м²) с черновой отделкой Black Box: возведённые стены и перегородки, подведённые коммуникации без чистовой отделки, голые бетонные стены и пол, установленные окна и входные двери. Удобно для самостоятельного ремонта по своему вкусу.',
    'available',
    1
),
(
    'INN-120-WB',
    'Дом 120 м² с отделкой White Box',
    'WHITE_BOX',
    10200000.00, 10200000.00, 'RUB',
    120.00, 75.00, 4.00, 4, 2,
    '{"finishing": "WHITE_BOX", "heating": "автономное", "water": "скважина"}'::jsonb,
    'Готовая отделка под ключ. 120 м², 4 комнаты.',
    'Дом с отделкой White Box в посёлке «Инноваторы Клуб». Под ключ: стены, пол, санузлы, кухня. Участок 4 сотки.',
    'available',
    1
)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    price_current = EXCLUDED.price_current,
    description_short = EXCLUDED.description_short,
    updated_at = NOW();

-- ========== 2. Шаблоны документов (КП и договор) ==========
-- Плейсхолдеры: {{client_name}}, {{object_name}}, {{price}}, {{price_words}}, {{valid_until}}, {{settlement}}, {{date}}, {{city}}, {{seller_name}}, {{seller_basis}}, {{client_passport}}, {{area_total}}
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM document_templates LIMIT 1) THEN
        INSERT INTO document_templates (type, name, body, body_structured, is_active) VALUES
        (
            'proposal',
            'КП на объект недвижимости (типовой)',
            E'КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ\n\nКлиент: {{client_name}}\nДата: {{date}}\n\nОбъект: {{object_name}}\nПосёлок: {{settlement}}\n\nСтоимость: {{price}} руб. ({{price_words}}).\n\nУсловия: предоплата по согласованию, возможность ипотеки. Срок действия предложения — до {{valid_until}}.\n\nПри принятии решения просим связаться с менеджером для оформления договора и записи на просмотр.\n\nС уважением,\nОтдел продаж',
            '{"sections": ["header", "client", "object", "pricing", "terms", "footer"]}'::jsonb,
            true
        ),
        (
            'contract',
            'Типовой договор купли-продажи объекта',
            E'ДОГОВОР КУПЛИ-ПРОДАЖИ\n\nг. {{city}}, {{date}}\n\nПродавец: {{seller_name}}, действующий на основании {{seller_basis}}, с одной стороны, и\nПокупатель: {{client_name}}, паспорт {{client_passport}}, с другой стороны, заключили договор о нижеследующем.\n\n1. Предмет договора\nПродавец обязуется передать в собственность Покупателя объект недвижимости: {{object_name}}, расположенный в {{settlement}}, общей площадью {{area_total}} кв.м, за цену {{price}} ({{price_words}}) рублей.\n\n2. Порядок расчётов и передачи\nРасчёты и передача объекта — в соответствии с утверждённым графиком. Подписание акта приёма-передачи — в течение 5 рабочих дней после полной оплаты.\n\n3. Прочие условия\nСпоры разрешаются в соответствии с законодательством РФ.\n\nПодписи сторон:\n\nПродавец: _________________\nПокупатель: _________________',
            '{"sections": ["preamble", "subject", "payment", "other", "signatures"]}'::jsonb,
            true
        );
    END IF;
END $$;

-- ========== 3. Календарь показов (образцы слотов на ближайшие дни) ==========
-- Слоты создаём только если будущих слотов ещё нет (повторный запуск не дублирует).
-- Один объект — много слотов по времени: повторы object_name нормальны (клиент выбирает время просмотра одного дома).
DO $$
DECLARE
    pid INTEGER;
    slot_ts TIMESTAMP;
    i INT := 0;
BEGIN
    SELECT id INTO pid FROM products WHERE code = 'INN-140-BB' LIMIT 1;
    IF pid IS NULL THEN RETURN; END IF;

    IF EXISTS (SELECT 1 FROM viewing_slots WHERE slot_start > NOW() LIMIT 1) THEN
        RETURN; -- уже есть будущие слоты
    END IF;

    FOR slot_ts IN
        SELECT (d::date + (10 + n * 2) * interval '1 hour')::timestamp
        FROM generate_series((CURRENT_DATE + 1)::timestamp, (CURRENT_DATE + 5)::timestamp, '1 day'::interval) AS d,
             generate_series(0, 3) AS n
        LIMIT 15
    LOOP
        INSERT INTO viewing_slots (settlement_id, object_id, object_name, slot_start, slot_end, status)
        SELECT 1, pid, (SELECT name FROM products WHERE id = pid), slot_ts, slot_ts + interval '1 hour', 'free'
        WHERE NOT EXISTS (SELECT 1 FROM viewing_slots WHERE object_id = pid AND slot_start = slot_ts);
        i := i + 1;
        EXIT WHEN i >= 12;
    END LOOP;
END $$;
