from datetime import date
from typing import Any

from app.reports.docx_common import (
    ORGANIZATION,
    add_table,
    fmt_date,
    fmt_num,
    footer_with_page_number,
    new_document,
    para,
    signature_block,
    to_bytes,
)


def build_squad_order_docx(info: dict[str, Any]) -> bytes:
    """Проект приказа о включении спортсменов в состав сборной команды региона."""
    members = info["members"]
    doc = new_document()
    footer_with_page_number(doc, "Проект приказа о составе сборной команды")

    para(doc, ORGANIZATION.upper(), bold=True, size=12, align="center", after=4)
    para(doc, "ПРИКАЗ (ПРОЕКТ)", bold=True, size=16, align="center", after=12)
    number = info["order_number"] or "____"
    p = para(doc, f"«____» ______________ {date.today().year} г.", after=0)
    p.add_run(f"\t\t\t\t\t№ {number}")
    para(doc, "г. Оренбург", after=14)

    scope = f"дисциплина «{info['discipline']}»" + (f", возрастная группа «{info['age_group']}»" if info["age_group"] else "") + f", сезон {info['season']}"
    para(doc, f"О формировании сборной команды Оренбургской области по виду спорта «спортивное программирование» ({scope})",
         bold=True, align="justify", after=12)
    para(doc, "В целях подготовки и участия спортсменов региона во всероссийских и межрегиональных соревнованиях, "
              "на основании рейтинга спортсменов Оренбургской области по итогам сезона, приказываю:", align="justify", after=6)
    para(doc, f"1. Включить в состав сборной команды Оренбургской области «{info['title']}» следующих спортсменов:", align="justify", after=6)

    rows = [[str(m["position"]), m["athlete_name"], fmt_date(m["birth_date"]), m["organization"] or "–", m["rank"] or "–",
             fmt_num(m["rating_points"]), m["coach"] or "–"] for m in members]
    add_table(doc, ["№", "Фамилия, имя, отчество", "Дата рожд.", "Организация", "Разряд", "Рейт. баллы", "Тренер"],
              rows, [0.9, 4.2, 2.0, 3.6, 2.4, 1.6, 3.0], font_size=9, center_cols={0, 2, 5})
    para(doc, "", after=4)
    para(doc, "2. Тренерам, закреплённым за спортсменами, обеспечить подготовку к соревнованиям и своевременную подачу заявок на участие.",
         align="justify")
    para(doc, "3. Ответственному за календарные планы подготовить документы для финансирования выезда сборной команды "
              "в министерство физической культуры и спорта Оренбургской области.", align="justify")
    para(doc, "4. Контроль за исполнением настоящего приказа оставляю за собой.", align="justify", after=14)
    signature_block(doc, "Председатель регионального отделения")
    para(doc, "Проект сформирован автоматически платформой ФСП Оренбургской области на основании рейтинга спортсменов.",
         italic=True, size=9, before=14)
    return to_bytes(doc)
