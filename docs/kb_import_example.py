"""
Пример скрипта для импорта данных из kb_info.txt в базу знаний

Этот скрипт демонстрирует, как структурировать информацию из kb_info.txt
для загрузки в таблицу knowledge_base с правильными метаданными.
"""

from typing import List, Dict
import json


def create_kb_chunks() -> List[Dict]:
    """
    Создаёт структурированные chunks для базы знаний
    на основе информации из kb_info.txt
    """
    chunks = []
    
    # ============================================
    # 1. ОБЩЕЕ ОПИСАНИЕ ПОСЁЛКА
    # ============================================
    
    chunks.append({
        "content": """60 современных домов в зелёной части Краснодара — с автономными коммуникациями, продуманными планировками и комфортной инфраструктурой для жизни и отдыха.""",
        "metadata": {
            "category": "product_info",
            "subcategory": "general_description",
            "target_audience": "both",
            "priority": "high",
            "tags": ["посёлок", "описание", "общая информация"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "greeting",
                "stage": "early"
            }
        }
    })
    
    chunks.append({
        "content": """КОММУНИКАЦИИ В КАЖДОМ ДОМЕ:
• Электричество — 15 кВт
• Скважина — 40 м
• Септик — 8 м³
• Интернет — оптоволокно
• Участки — от 4 до 7 соток""",
        "metadata": {
            "category": "product_info",
            "subcategory": "communications",
            "target_audience": "both",
            "priority": "high",
            "tags": ["коммуникации", "электричество", "скважина", "септик", "интернет"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "qualification",
                "stage": "early"
            }
        }
    })
    
    # ============================================
    # 2. ПРЕИМУЩЕСТВА (разбиты по отдельным chunks)
    # ============================================
    
    advantages = [
        {
            "title": "Закрытая территория",
            "content": """Закрытая территория
— Контроль доступа и охрана
— Тишина, порядок и спокойствие""",
            "tags": ["безопасность", "охрана", "закрытая территория"]
        },
        {
            "title": "Зона отдыха",
            "content": """Зона отдыха
— Подогреваемый бассейн, шезлонги
— Детская и спортивная площадки""",
            "tags": ["инфраструктура", "бассейн", "отдых", "детская площадка"]
        },
        {
            "title": "Экологичность",
            "content": """Экологичность
— Рядом красивая река, свежий воздух
— Идеально для прогулок и активной жизни""",
            "tags": ["экология", "природа", "река", "прогулки"]
        },
        {
            "title": "Современные дома",
            "content": """Современные дома
— Энергоэффективность, стиль, комфорт
— Полноценный второй этаж""",
            "tags": ["дома", "энергоэффективность", "комфорт", "второй этаж"]
        },
        {
            "title": "Активный образ жизни",
            "content": """Активный образ жизни
— Велодорожки, спорт, пикники
— Дружное сообщество соседей""",
            "tags": ["активный образ жизни", "велодорожки", "спорт", "сообщество"]
        }
    ]
    
    for adv in advantages:
        chunks.append({
            "content": adv["content"],
            "metadata": {
                "category": "product_info",
                "subcategory": "advantages",
                "target_audience": "both",
                "priority": "high",
                "tags": adv["tags"],
                "source": "kb_info.txt",
                "version": "1.0",
                "context": {
                    "use_case": "qualification",
                    "stage": "early"
                }
            }
        })
    
    # ============================================
    # 3. ЦЕНЫ (отдельные chunks для каждого варианта)
    # ============================================
    
    pricing_options = [
        {
            "name": "Черновая отделка",
            "price": "8 350 000 ₽",
            "link": "https://innovatory-club.ru/katalog#!/tab/1063728081-1"
        },
        {
            "name": "Предчистовая отделка",
            "price": "8 950 000 ₽",
            "link": "https://innovatory-club.ru/katalog#!/tab/1063728081-2"
        },
        {
            "name": "Стандартный ремонт",
            "price": "9 650 000 ₽",
            "link": "https://innovatory-club.ru/katalog#!/tab/1063728081-3"
        },
        {
            "name": "Дизайнерский ремонт",
            "price": "10 450 000 ₽",
            "link": "https://innovatory-club.ru/katalog#!/tab/1063728081-4"
        },
        {
            "name": "Отделка второго этажа",
            "price": "1 500 000 ₽",
            "link": "https://disk.yandex.ru/i/Ydv1kgQApW3Kxw",
            "is_option": True
        }
    ]
    
    for option in pricing_options:
        content = f"""{option['name']} — {option['price']}"""
        if option.get('is_option'):
            content += f"\nФото: {option['link']}"
        else:
            content += f"\nПодробнее: {option['link']}"
        
        chunks.append({
            "content": content,
            "metadata": {
                "category": "product_info",
                "subcategory": "pricing",
                "target_audience": "end_buyer",
                "priority": "high",
                "tags": ["цена", "отделка", option['name'].lower()],
                "source": "kb_info.txt",
                "version": "1.0",
                "related_links": [option['link']],
                "context": {
                    "use_case": "proposal",
                    "stage": "middle"
                }
            }
        })
    
    # ============================================
    # 4. МЕСТОПОЛОЖЕНИЕ
    # ============================================
    
    chunks.append({
        "content": """Адрес посёлка: хутор Октябрьский, городской округ Краснодар
Гренадерская, дом 10/2
Карта: https://yandex.ru/maps/?text=45.190746,39.076412""",
        "metadata": {
            "category": "product_info",
            "subcategory": "location",
            "target_audience": "both",
            "priority": "high",
            "tags": ["адрес", "локация", "карта", "Краснодар"],
            "source": "kb_info.txt",
            "version": "1.0",
            "related_links": ["https://yandex.ru/maps/?text=45.190746,39.076412"],
            "context": {
                "use_case": "qualification",
                "stage": "early"
            }
        }
    })
    
    # ============================================
    # 5. ЦЕЛЕВАЯ АУДИТОРИЯ
    # ============================================
    
    chunks.append({
        "content": """Портрет главной целевой аудитории: Семьи с детьми (30-45 лет, средний+ доход, активный образ жизни)

Кто они:
Работающие родители, ценящие безопасность, комфорт и природу для своих детей.
Ищут закрытую территорию с детскими площадками, развитой инфраструктурой и возможностью создать уютный семейный уголок.
Важны доступность школ, садов, медучреждений и транспортная развязка.""",
        "metadata": {
            "category": "target_audience",
            "subcategory": "end_buyer_profile",
            "target_audience": "end_buyer",
            "priority": "medium",
            "tags": ["ЦА", "портрет", "семьи", "дети"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "qualification",
                "stage": "early"
            }
        }
    })
    
    chunks.append({
        "content": """Триггеры покупки для семей с детьми:
• Закрытая охраняемая территория – безопасность детей
• Большие участки – место для игр, сада, бассейна
• Развитая инфраструктура – детская площадка, аквазона, парковые зоны
• Автономные коммуникации – стабильное отопление и водоснабжение
• Финансовая доступность – ипотека, материнский капитал, рассрочка""",
        "metadata": {
            "category": "target_audience",
            "subcategory": "purchase_triggers",
            "target_audience": "end_buyer",
            "priority": "medium",
            "tags": ["триггеры", "покупка", "мотивация"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "qualification",
                "stage": "early"
            }
        }
    })
    
    chunks.append({
        "content": """Дополнительные сегменты целевой аудитории:

1. Апгрейд из квартиры (IT/предприниматели, самозанятые)
   Хотят приватность, рабочее пространство дома, экономичность инженерии.

2. Переезд в Краснодар (из регионов/севера)
   Ищут «мягкий старт»: понятные условия сделки, сопровождение, наглядные преимущества локации.

3. Партнёры‑риелторы
   Важны актуальные прайсы/наличие, правила расчётов и чёткая коммуникация.""",
        "metadata": {
            "category": "target_audience",
            "subcategory": "additional_segments",
            "target_audience": "both",
            "priority": "medium",
            "tags": ["ЦА", "сегменты", "риелторы"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "qualification",
                "stage": "early"
            }
        }
    })
    
    # ============================================
    # 6. TONE OF VOICE
    # ============================================
    
    chunks.append({
        "content": """Tone of Voice: «Аспиративный тёплый» (база бренда)

Как звучит: уверенно‑спокойно, дружелюбно, с лёгкой ноткой lifestyle.

Когда применять: презентации объекта, ленты VK/Instagram, сторис о жизни в посёлке.

Языковые приёмы: короткие фразы, визуальные образы («утро у бассейна», «вечер на террасе»), 1–2 эмодзи максимум.

Опора на факты: включайте конкретику — «закрытая территория», «аквазона», «экотропа».

Пример мини‑сообщения:
«Свежий воздух, тишина и собственная аквазона — место, где будни действительно ощущаются как отдых. Дома 80–140 кв. м, варианты отделки — от Black Box до Design. Записаться на просмотр: ежедневно 10:00–17:00.»""",
        "metadata": {
            "category": "tone_of_voice",
            "subcategory": "aspirational_warm",
            "target_audience": "end_buyer",
            "priority": "high",
            "tags": ["стиль", "tone", "коммуникация", "бренд"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "greeting",
                "stage": "early"
            }
        }
    })
    
    chunks.append({
        "content": """Tone of Voice: «Технологичный практичный»

Как звучит: структурно, делово, «язык преимуществ» без эмо‑излишков.

Когда применять: карусели с характеристиками, посты про инженерные решения, ответы на вопросы.

Языковые приёмы: маркеры/списки, цифры и измеримые эффекты (энергоэффективность → «ниже расходы»), точные формулировки отделки и метража.

Пример мини‑сообщения:
«Автономные коммуникации → регулируемая температура и горячая вода круглый год. Энергоэффективность → ниже коммунальные платежи. Бетонные дороги → комфортный проезд в любую погоду. Просмотры: 10:00–17:00 (по записи).»""",
        "metadata": {
            "category": "tone_of_voice",
            "subcategory": "technological_practical",
            "target_audience": "end_buyer",
            "priority": "high",
            "tags": ["стиль", "tone", "технические характеристики"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "proposal",
                "stage": "middle"
            }
        }
    })
    
    chunks.append({
        "content": """Редакционные принципы (для всех каналов):

Стиль: вежливый «вы», короткие абзацы, маркеры; избегать пафоса и штампов.

Конкретика > эпитеты: опираемся на проверяемые факты (закрытая территория, аквазона, экотропа, отделки, метраж, график показов).

CTA‑паттерн: «Записаться на просмотр / Узнать актуальную цену» + указание графика 10:00–17:00.

Числа и единицы: метраж — «кв. м», цена — «руб.» (с точкой).

Эмодзи: умеренно (0–2 на пост), только по делу.

Юридическая точность: при упоминании сделок — «расчёты по договору с застройщиком (ИП Сухарева)» и напоминание, что партнёры не принимают оплату. Реквизиты подтверждены на сайте.""",
        "metadata": {
            "category": "tone_of_voice",
            "subcategory": "editorial_principles",
            "target_audience": "both",
            "priority": "high",
            "tags": ["стиль", "правила", "редакция"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "all",
                "stage": "all"
            }
        }
    })
    
    # ============================================
    # 7. КЛЮЧЕВЫЕ ЦЕННОСТИ
    # ============================================
    
    chunks.append({
        "content": """Ключевые ценности для клиента:

1. Повышение качества жизни
2. Оптимальная цена за комфорт+
3. Инновационность, другой - качественный подход к решению вопросов коммуникаций""",
        "metadata": {
            "category": "key_values",
            "subcategory": "client_values",
            "target_audience": "end_buyer",
            "priority": "high",
            "tags": ["ценности", "преимущества", "позиционирование"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "qualification",
                "stage": "middle"
            }
        }
    })
    
    # ============================================
    # 8. ОБРАБОТКА ВОЗРАЖЕНИЙ
    # ============================================
    
    chunks.append({
        "content": """Возражение: "Это дорого для меня"

Ответ:
Понимаю ваши опасения. Давайте посмотрим на ценность:
• Автономные коммуникации — экономия на коммунальных платежах
• Закрытая территория — безопасность для семьи
• Готовая инфраструктура — бассейн, детские площадки
• Участок от 4 до 7 соток — место для отдыха и сада

Также доступны варианты финансирования: ипотека, материнский капитал, рассрочка.
Можем обсудить варианты отделки — от черновой (8 350 000 ₽) до дизайнерского ремонта (10 450 000 ₽).""",
        "metadata": {
            "category": "objection_handling",
            "subcategory": "price_objection",
            "target_audience": "end_buyer",
            "priority": "high",
            "tags": ["возражение", "цена", "дорого", "финансирование"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "objection",
                "stage": "middle"
            }
        }
    })
    
    chunks.append({
        "content": """Возражение: "Далеко от города"

Ответ:
Посёлок находится в зелёной части Краснодара, хутор Октябрьский. 
Близость к транспортной развязке обеспечивает удобный доступ в город.
При этом вы получаете:
• Свежий воздух и тишину
• Красивую реку в 3 кварталах
• Зелёную зону вокруг
• Комфортную жизнь без городского шума

Это оптимальный баланс между близостью к городу и качеством жизни на природе.""",
        "metadata": {
            "category": "objection_handling",
            "subcategory": "location_objection",
            "target_audience": "end_buyer",
            "priority": "high",
            "tags": ["возражение", "локация", "расстояние", "город"],
            "source": "kb_info.txt",
            "version": "1.0",
            "context": {
                "use_case": "objection",
                "stage": "middle"
            }
        }
    })
    
    # ============================================
    # 9. КОНТАКТЫ
    # ============================================
    
    chunks.append({
        "content": """Контакты отдела продаж:
Сергей, отдел продаж: +7 (988) 199-89-98
Показы ежедневно с 10:00 до 17:00
Сайт: https://innovatory-club.ru/""",
        "metadata": {
            "category": "contacts",
            "subcategory": "sales_contact",
            "target_audience": "both",
            "priority": "high",
            "tags": ["контакты", "показы", "график", "телефон"],
            "source": "kb_info.txt",
            "version": "1.0",
            "related_links": ["https://innovatory-club.ru/"],
            "context": {
                "use_case": "closing",
                "stage": "late"
            }
        }
    })
    
    chunks.append({
        "content": """Контакты для риелторов:
Telegram: https://t.me/innovatory_club
Max: https://max.ru/join/TGHth3P8Ge4klCf9U8OuQTO03w26B7OOW0r3Qc-CS3s

В закрытых группах оказываем информационную поддержку партнёров, делимся актуальными материалами и эффективными инструментами продаж.""",
        "metadata": {
            "category": "contacts",
            "subcategory": "realtor_contact",
            "target_audience": "realtor",
            "priority": "high",
            "tags": ["контакты", "риелторы", "партнёрство", "telegram"],
            "source": "kb_info.txt",
            "version": "1.0",
            "related_links": [
                "https://t.me/innovatory_club",
                "https://max.ru/join/TGHth3P8Ge4klCf9U8OuQTO03w26B7OOW0r3Qc-CS3s"
            ],
            "context": {
                "use_case": "closing",
                "stage": "late"
            }
        }
    })
    
    # ============================================
    # 10. МАТЕРИАЛЫ (ссылки)
    # ============================================
    
    materials = [
        {
            "name": "Видео о посёлке",
            "link": "https://innovatory-club.ru/#video",
            "target": "both"
        },
        {
            "name": "Планировки (конечный покупатель)",
            "link": "https://innovatory-club.ru/katalog/#service",
            "target": "end_buyer"
        },
        {
            "name": "Планировки (риелтор)",
            "link": "https://disk.yandex.ru/d/md-JXgsbLw1wdw",
            "target": "realtor"
        },
        {
            "name": "Общая презентация PDF (риелтор)",
            "link": "https://disk.yandex.ru/i/Guaox0dwfIoRZQ",
            "target": "realtor"
        },
        {
            "name": "Видеопрезентация (риелтор)",
            "link": "https://disk.yandex.ru/i/VwGDPtLFJyKSZg",
            "target": "realtor"
        }
    ]
    
    for material in materials:
        chunks.append({
            "content": f"""{material['name']}: {material['link']}""",
            "metadata": {
                "category": "materials",
                "subcategory": "media_links",
                "target_audience": material['target'],
                "priority": "medium",
                "tags": ["материалы", "ссылки", material['name'].lower()],
                "source": "kb_info.txt",
                "version": "1.0",
                "related_links": [material['link']],
                "context": {
                    "use_case": "proposal",
                    "stage": "middle"
                }
            }
        })
    
    return chunks


def export_to_json(chunks: List[Dict], filename: str = "kb_chunks.json"):
    """Экспорт chunks в JSON файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"Экспортировано {len(chunks)} chunks в {filename}")


def print_summary(chunks: List[Dict]):
    """Вывод статистики по chunks"""
    categories = {}
    for chunk in chunks:
        cat = chunk['metadata']['category']
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\n=== Статистика по категориям ===")
    for cat, count in sorted(categories.items()):
        print(f"{cat}: {count} chunks")
    
    print(f"\nВсего chunks: {len(chunks)}")


if __name__ == "__main__":
    # Создание chunks
    chunks = create_kb_chunks()
    
    # Вывод статистики
    print_summary(chunks)
    
    # Экспорт в JSON
    export_to_json(chunks, "kb_chunks.json")
    
    print("\n✅ Chunks готовы для импорта в базу знаний!")
    print("Следующий шаг: генерация embeddings и загрузка в PostgreSQL")





















