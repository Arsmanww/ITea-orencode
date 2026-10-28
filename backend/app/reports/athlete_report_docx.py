from datetime import date
from typing import Any

from app.reports.docx_common import (
    LEVEL_LABELS,
    ORGANIZATION,
    STATUS_LABELS,
    add_table,
    fmt_date,
    fmt_num,
    fmt_time,
    footer_with_page_number,
    new_document,
    para,
    signature_block,
    to_bytes,
)


def build_athlete_report_docx(info: dict[str, Any]) -> bytes:
    """Справка о выступлениях спортсмена: профиль, все соревнования, места, присвоенные разряды."""
    athlete, history, ranks = info["athlete"], info["history"], info["ranks"]
    doc = new_document(landscape=True)
    footer_with_page_number(doc, f"Справка о выступлениях: {athlete['full_name']}")

    para(doc, ORGANIZATION.upper(), bold=True, size=12, align="center", after=10)
    para(doc, "СПРАВКА", bold=True, size=18, align="center", after=2)
    para(doc, "о выступлениях спортсмена в соревнованиях по спортивному программированию", size=13, align="center", after=10)

    profile = [
        ["Спортсмен", athlete["full_name"]],
        ["Дата рождения", f"{fmt_date(athlete['birth_date'])} ({athlete['age']} лет)"],
        ["Муниципальное образование", athlete["municipality"] or "–"],
        ["Дисциплины и организации", "; ".join(athlete["enrollments"]) or "–"],
        ["Тренеры", "; ".join(athlete["coaches"]) or "самостоятельная подготовка"],
    ]
    add_table(doc, ["Сведения", ""], profile, [6.0, 20.0], font_size=10.5)

    prizes = sum(1 for h in history if h["place"] and h["place"] <= 3)
    wins = sum(1 for h in history if h["place"] == 1)
    para(doc, f"Участий в соревнованиях: {len(history)}; призовых мест: {prizes}; побед: {wins}; "
              f"присвоено и подтверждено разрядов: {len(ranks)}.", bold=True, size=11, before=10, after=6)

    para(doc, "Выступления в соревнованиях", bold=True, size=13, before=6, after=4)
    if history:
        rows = []
        for i, h in enumerate(history, start=1):
            result = STATUS_LABELS.get(h["status"]) or ""
            place = f"{h['place']} из {h['participants']}" if h["place"] else (result or "–")
            score = " / ".join(x for x in (fmt_num(h["score"]) if h["score"] is not None else "",
                                           f"{h['tasks_solved']} зад." if h["tasks_solved"] is not None else "",
                                           fmt_time(h["time_seconds"])) if x) or "–"
            rows.append([str(i), f"{fmt_date(h['start_date'])} – {fmt_date(h['end_date'])}", h["title"], h["discipline_short"],
                         LEVEL_LABELS[h["level"]], place, score, h["protocol_number"]])
        add_table(doc, ["№", "Даты", "Соревнование", "Дисциплина", "Статус", "Место", "Результат", "Протокол"], rows,
                  [0.9, 3.6, 9.0, 3.2, 2.7, 2.1, 3.0, 2.3], font_size=9, center_cols={0, 1, 4, 5, 6, 7})
    else:
        para(doc, "Результатов опубликованных протоколов пока нет.", italic=True)

    para(doc, "Спортивные разряды", bold=True, size=13, before=14, after=4)
    if ranks:
        add_table(doc, ["Разряд", "Дисциплина", "Приказ", "Присвоен", "Действует до", "Основание (соревнование, место)"],
                  [[r["rank"], r["discipline"], f"№ {r['order_number']} от {fmt_date(r['order_date'])}", fmt_date(r["assigned_at"]),
                    fmt_date(r["valid_until"]) if r["valid_until"] else "бессрочно", r["basis"] or "–"] for r in ranks],
                  [4.2, 4.2, 4.0, 2.6, 2.7, 8.3], font_size=9, center_cols={3, 4})
    else:
        para(doc, "Разряды не присваивались.", italic=True)

    para(doc, f"Справка выдана {fmt_date(date.today())} для предъявления по месту требования.", size=11, before=14)
    signature_block(doc, "Председатель регионального отделения")
    para(doc, "М.П.", size=10, before=6)
    para(doc, "Сведения сформированы автоматически из опубликованных протоколов и приказов в системе ФСП Оренбургской области.",
         italic=True, size=9, before=6)
    return to_bytes(doc)
