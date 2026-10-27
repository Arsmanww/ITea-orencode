from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Competition, User
from app.models.enums import CompetitionStatus, RoleCode


def full_name(user: User) -> str:
    return " ".join(p for p in (user.last_name, user.first_name, user.patronymic) if p)


async def get_competition_or_404(session: AsyncSession, competition_id: int, role: RoleCode) -> Competition:
    """Черновики видны только федерации."""
    comp = await session.get(Competition, competition_id)
    if comp is None or (comp.status == CompetitionStatus.DRAFT and role != RoleCode.FEDERATION):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Соревнование не найдено")
    return comp
