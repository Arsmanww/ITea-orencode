from decimal import Decimal

from app.models import Result
from app.models.enums import ResultStatus

_INF = Decimal("Infinity")


def sort_key(r: Result) -> tuple[Decimal, Decimal, Decimal]:
    """Больше баллов лучше, больше решённых задач лучше, меньше времени лучше; пустые значения – в конец."""
    return (
        -r.score if r.score is not None else _INF,
        Decimal(-r.tasks_solved) if r.tasks_solved is not None else _INF,
        r.time_seconds if r.time_seconds is not None else _INF,
    )


def assign_places(results: list[Result]) -> None:
    """Проставляет места всем участникам в зачёте.

    Равные результаты делят место (1, 2, 2, 4). Неявка и дисквалификация места не получают,
    но остаются в протоколе после ранжированных.
    """
    ranked = sorted((r for r in results if r.status == ResultStatus.RANKED), key=sort_key)
    place = 0
    previous = None
    for index, result in enumerate(ranked, start=1):
        key = sort_key(result)
        if key != previous:
            place = index
            previous = key
        result.place = place
    for result in results:
        if result.status != ResultStatus.RANKED:
            result.place = None
