#!/usr/bin/env python3
"""
Анализ этапов сделки, КП, ипотеки и договора на реальных данных amoCRM.
Строит карту воронок/статусов, находит примеры сделок по этапам, разбирает примечания
(как высылаются КП, как работают с ипотекой, заключение договора).
Запуск из корня репо: python amocrm-api/scripts/analyze_deal_lifecycle.py
"""
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AMOCRM_API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AMOCRM_API_ROOT))
os.chdir(REPO_ROOT)

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "config.env")
load_dotenv(REPO_ROOT / ".env")

from client import AmoCRMClient


# Воронки для анализа: продажи + квалификация (часто сделки сначала в Квалификации, потом переносят в продажи)
SALES_PIPELINE_IDS = (10140478, 10140482)  # Продажа домов с участками, Продажа услуг по строительству
QUALIFICATION_PIPELINE_ID = 10112058  # Квалификация — добавляем к сбору примеров, если в продажах пусто
PIPELINES_FOR_COLLECT = (10140478, 10140482, 10112058)  # продажи + квалификация
# Ключевые статусы по этапам (id из обследования innovatoryclub)
STAGE_KEYWORDS = {
    "квалификация": (80341102, 80341146),
    "показ_встреча": (80341106, 80341110),
    "кп_смета_проект": (80341114,),
    "согласован_проект": (80341118, 80341154),
    "ипотека_брокер": (80341122, 80341158),
    "ипотека_документы": (80341126, 80341162),
    "документы_оформлены": (80341166,),
    "оплата_успешно": (80341170, 142),
}


def get_status_map(client: AmoCRMClient) -> Tuple[Dict, Dict]:
    """Возвращает status_id -> (pipeline_id, pipeline_name, status_name), pipeline_id -> name."""
    data = client.get_pipelines()
    pipelines = data.get("_embedded", {}).get("pipelines", [])
    status_map = {}
    pipeline_names = {}
    for p in pipelines:
        pid = p.get("id")
        pname = p.get("name", "")
        pipeline_names[pid] = pname
        for s in p.get("_embedded", {}).get("statuses", []) or p.get("statuses", []):
            sid = s.get("id")
            sname = s.get("name", "")
            if sid is not None:
                status_map[sid] = (pid, pname, sname)
    return status_map, pipeline_names


def collect_leads_by_stage(client: AmoCRMClient, status_map: Dict, max_pages: int = 10) -> Dict:
    """Собирает сделки по (pipeline_id, status_id), только из воронок продаж.
    Сначала запрос с filter[pipeline_id][] по воронкам продаж; если пусто — без фильтра с фильтрацией в коде."""
    by_stage = defaultdict(list)
    pipeline_ids = list(PIPELINES_FOR_COLLECT)

    def process_page_leads(leads: list) -> None:
        for lead in leads:
            pid = lead.get("pipeline_id")
            if pid not in PIPELINES_FOR_COLLECT:
                continue
            sid = lead.get("status_id")
            by_stage[(pid, sid)].append({
                "id": lead.get("id"),
                "name": (lead.get("name") or "")[:60],
                "price": lead.get("price"),
                "status_id": sid,
                "pipeline_id": pid,
            })

    # Попытка 1: с фильтром по воронкам (меньше запросов, только нужные сделки)
    page = 1
    while page <= max_pages:
        try:
            data = client.get_leads(limit=250, page=page, pipeline_ids=pipeline_ids)
        except Exception:
            break
        leads = data.get("_embedded", {}).get("leads", [])
        if not leads:
            break
        process_page_leads(leads)
        page += 1

    # Попытка 2: если с фильтром ничего не нашли — без фильтра, фильтруем в коде (больше страниц)
    if not by_stage:
        page = 1
        while page <= max_pages * 2:  # больше страниц, т.к. сделки продаж могут идти не в начале
            data = client.get_leads(limit=250, page=page)
            leads = data.get("_embedded", {}).get("leads", [])
            if not leads:
                break
            process_page_leads(leads)
            page += 1

    return by_stage


def get_note_texts(notes_payload: dict) -> Tuple[List[str], int, List[str]]:
    """Из ответа GET /leads/{id}/notes извлекает тексты примечаний.
    Возвращает (список текстов, всего примечаний, список типов примечаний для отладки)."""
    texts = []
    notes = notes_payload.get("_embedded", {}).get("notes", [])
    if not notes and isinstance(notes_payload.get("_embedded"), list):
        notes = notes_payload["_embedded"]
    if not notes and isinstance(notes_payload.get("notes"), list):
        notes = notes_payload["notes"]
    note_types = []
    for n in notes:
        note_type = n.get("note_type", "?")
        note_types.append(note_type)
        params = n.get("params") or {}
        if isinstance(params, dict):
            text = (
                params.get("text")
                or params.get("message")
                or params.get("content")
                or ""
            )
            if not text and note_type == "amomail_message":
                raw = params.get("html") or params.get("body") or params.get("raw_html") or ""
                if raw:
                    text = re.sub(r"<[^>]+>", " ", raw)
                    text = " ".join(text.split())
            if not text and note_type == "attachment":
                name = params.get("original_name") or params.get("filename") or ""
                if name:
                    texts.append(f"[Вложение: {name}]")
        else:
            text = str(params) if params else ""
        if not text and "text" in n:
            text = n.get("text", "")
        if text and str(text).strip() and not str(text).strip().startswith("[Вложение:"):
            texts.append(str(text).strip())
    return texts, len(notes), note_types


def analyze_notes_for_keywords(texts: List[str]) -> dict:
    """Ищет в текстах примечаний ключевые слова (КП, ипотека, договор и т.д.)."""
    keywords = ["КП", "коммерческое предложение", "смета", "проект", "ипотека", "договор", "оплата", "подпись", "брокер"]
    found = defaultdict(list)
    for i, t in enumerate(texts):
        t_lower = t.lower()
        for kw in keywords:
            if kw.lower() in t_lower:
                snippet = t[:200].replace("\n", " ") if len(t) > 200 else t.replace("\n", " ")
                found[kw].append((i, snippet))
    return dict(found)


def main():
    print("=" * 72)
    print("АНАЛИЗ ЭТАПОВ СДЕЛКИ, КП, ИПОТЕКИ И ДОГОВОРА (реальные кейсы amoCRM)")
    print("=" * 72)

    try:
        client = AmoCRMClient()
    except Exception as e:
        print(f"\n❌ Ошибка инициализации клиента: {e}")
        sys.exit(1)
    if not client.subdomain or not client._access_token:
        print("\n❌ Задайте AMOCRM_SUBDOMAIN и AMOCRM_ACCESS_TOKEN в config.env")
        sys.exit(1)

    print(f"\nПоддомен: {client.subdomain}\n")

    # 1. Карта статусов
    status_map, pipeline_names = get_status_map(client)
    print("-" * 72)
    print("1. КАРТА ВОРОНОК И СТАТУСОВ (продажи + квалификация)")
    print("-" * 72)
    for pid in PIPELINES_FOR_COLLECT:
        pname = pipeline_names.get(pid, f"Pipeline {pid}")
        print(f"\n   {pname} (id={pid})")
        for sid, (p, pn, sn) in sorted(status_map.items(), key=lambda x: x[0]):
            if p != pid:
                continue
            print(f"      • {sn} (id={sid})")
    print()

    # 2. Сделки по этапам
    by_stage = collect_leads_by_stage(client, status_map)
    print("-" * 72)
    print("2. ПРИМЕРЫ СДЕЛОК ПО ЭТАПАМ (воронки продаж и квалификация)")
    print("-" * 72)
    if not by_stage:
        print("\n   Сделок в выбранных воронках не найдено. Проверьте filter[pipeline_id][] или что в аккаунте есть сделки в «Продажа домов», «Продажа услуг» или «Квалификация».")
    example_lead_ids = []
    for (pid, sid), leads in sorted(by_stage.items(), key=lambda x: (x[0][0], x[0][1])):
        if not leads:
            continue
        _, pname, sname = status_map.get(sid, (pid, "", f"status_{sid}"))
        print(f"\n   {pname} → {sname} (id={sid}): сделок {len(leads)}")
        for lead in leads[:3]:
            print(f"      lead_id={lead['id']} | {lead['name']} | price={lead['price']}")
            example_lead_ids.append((lead["id"], pname, sname))

    # Приоритет этапов, где чаще есть примечания (переписка, показы, КП)
    priority_stages = ("Прямой покутель", "Групповые чаты", "Обратная связь после показа", "ВСТРЕЧА - Показы", "Риелторы")
    def order_key(item):
        _, pname, sname = item
        for i, stage in enumerate(priority_stages):
            if stage in sname or stage in pname:
                return (i, pname, sname)
        return (len(priority_stages), pname, sname)
    example_lead_ids.sort(key=order_key)

    print()
    print("-" * 72)
    print("3. АНАЛИЗ ПРИМЕЧАНИЙ: КП, ИПОТЕКА, ДОГОВОР")
    print("-" * 72)
    seen = set()
    chosen = []
    for lead_id, pname, sname in example_lead_ids:
        if lead_id in seen or len(chosen) >= 8:
            continue
        seen.add(lead_id)
        chosen.append((lead_id, pname, sname))

    for lead_id, pname, sname in chosen:
        print(f"\n   Сделка id={lead_id} ({pname} → {sname})")
        try:
            notes_data = client.get_lead_notes(lead_id, limit=50, page=1)
            texts, total_notes, note_types = get_note_texts(notes_data)
            if total_notes == 0:
                print("      Примечаний нет.")
                continue
            print(f"      Всего примечаний: {total_notes} (типы: {', '.join(sorted(set(note_types))[:8])}{'…' if len(set(note_types)) > 8 else ''})")
            if not texts:
                print("      Текстовых примечаний нет (возможно, только вложения или служебные).")
                continue
            print(f"      Примечаний с текстом: {len(texts)}")
            found = analyze_notes_for_keywords(texts)
            if not found:
                print("      Ключевые слова (КП/ипотека/договор) в примечаниях не найдены.")
            else:
                for kw, occurrences in found.items():
                    print(f"      Найдено «{kw}»: {len(occurrences)} раз(а)")
                    for idx, snippet in occurrences[:2]:
                        short = (snippet[:120] + "…") if len(snippet) > 120 else snippet
                        print(f"         [{idx}] {short}")
        except Exception as e:
            print(f"      Ошибка чтения примечаний: {e}")
    print()

    # 4. Сводка по бизнес-процессам
    print("=" * 72)
    print("4. СВОДКА: КАК ОТРАЖЕНЫ БИЗНЕС-ПРОЦЕССЫ В amoCRM")
    print("=" * 72)
    print("""
   • Этапы сделки: задаются воронкой (pipeline_id) и статусом (status_id).
     Продажа домов/услуг: квалификация → показ/встреча → КП/смета/проект →
     согласование проекта → ипотечный брокер → документы на ипотеку →
     документы оформлены → полная оплата.

   • КП (коммерческое предложение): отправка отражается сменой статуса
     «Отправили смету / КП / проект». Текст/файлы КП обычно в примечаниях
     к сделке (примечание типа common или вложение). Выше показаны примеры
     примечаний, где встречаются слова КП/смета/проект.

   • Ипотека: этапы «Передано ипотечному брокеру» и «Подали документы на ипотеку»
     (соответствующие status_id в карте выше). Детали — в примечаниях к сделке.

   • Договор и продажа: статусы «Документы оформлены», «Поступила полная оплата»
     и финальные («Успешно реализовано» в воронке маркетинг — id=142). Договор
     может храниться в примечаниях (файл) или во внешней системе; в amoCRM
     фиксируется факт перехода в статус оплаты/закрытия.

   Для точного формата КП (PDF, письмо, примечание) смотрите примечания
   к сделкам в статусе «Отправили смету/КП/проект» в интерфейсе amoCRM.
""")
    print("=" * 72)


if __name__ == "__main__":
    main()
