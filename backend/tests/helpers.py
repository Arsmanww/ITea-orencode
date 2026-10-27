"""Фабрики тестовых данных. Все данные вымышленные."""

import itertools
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models import (
    AgeGroup,
    AthleteEnrollment,
    AthleteProfile,
    Competition,
    CompetitionAgeGroup,
    CompetitionApplication,
    CompetitionStage,
    CompetitionType,
    Discipline,
    Protocol,
    Result,
    Role,
    User,
    UserRole,
)
from app.models.enums import (
    ApplicationStatus,
    CalendarPlan,
    CompetitionLevel,
    CompetitionStatus,
    Gender,
    ProtocolStatus,
    RatingTier,
    ResultStatus,
    RoleCode,
    StageFormat,
)

PASSWORD = "Demo12345!"
PASSWORD_HASH = hash_password(PASSWORD)  # bcrypt считаем один раз на весь прогон
_counter = itertools.count(1)


async def get_role(session, code: RoleCode) -> Role:
    role = await session.scalar(select(Role).where(Role.code == code))
    if role is None:
        role = Role(code=code, name=code.value)
        session.add(role)
        await session.flush()
    return role


async def make_user(session, roles: list[RoleCode], *, email: str | None = None, birth: date = date(1990, 1, 1), last_name: str = "Тестов") -> User:
    n = next(_counter)
    user = User(email=email or f"user{n}@test.example.com", password_hash=PASSWORD_HASH, last_name=f"{last_name}{n}", first_name="Тест",
                patronymic="Тестович", birth_date=birth, gender=Gender.MALE)
    session.add(user)
    await session.flush()
    for code in roles:
        session.add(UserRole(user_id=user.id, role_id=(await get_role(session, code)).id))
    await session.flush()
    return user


async def make_discipline(session, code: str = "algorithmic", name: str = "Программирование алгоритмическое") -> Discipline:
    existing = await session.scalar(select(Discipline).where(Discipline.code == code))
    if existing:
        return existing
    d = Discipline(code=code, name=name)
    session.add(d)
    await session.flush()
    return d


async def make_age_group(session, name: str, lo: int, hi: int) -> AgeGroup:
    g = AgeGroup(name=name, min_age=lo, max_age=hi)
    session.add(g)
    await session.flush()
    return g


async def make_athlete(session, discipline: Discipline | None, *, birth: date, enrolled_since: date = date(2018, 1, 1)) -> User:
    user = await make_user(session, [RoleCode.ATHLETE], birth=birth, last_name="Спортсменов")
    session.add(AthleteProfile(user_id=user.id))
    await session.flush()
    if discipline is not None:
        session.add(AthleteEnrollment(athlete_id=user.id, discipline_id=discipline.id, start_date=enrolled_since))
        await session.flush()
    return user


async def make_competition(
    session,
    discipline: Discipline,
    groups: list[AgeGroup],
    admin: User,
    *,
    start: date,
    status: CompetitionStatus = CompetitionStatus.REGISTRATION_OPEN,
    tier: RatingTier = RatingTier.REGIONAL,
    title: str = "Тестовое первенство",
) -> Competition:
    ctype = await session.scalar(select(CompetitionType).limit(1))
    if ctype is None:
        ctype = CompetitionType(name="Первенство")
        session.add(ctype)
        await session.flush()
    now = datetime.now(timezone.utc)
    comp = Competition(
        title=title, discipline_id=discipline.id, type_id=ctype.id, level=CompetitionLevel.REGIONAL, rating_tier=tier, status=status,
        calendar_plan=CalendarPlan.OREN_REGIONAL, plan_number="ОО-ТЕСТ", start_date=start, end_date=start + timedelta(days=1),
        location="г. Оренбург", registration_opens_at=now - timedelta(days=30), registration_deadline=now + timedelta(days=30),
        created_by=admin.id,
    )
    session.add(comp)
    await session.flush()
    session.add_all(CompetitionAgeGroup(competition_id=comp.id, age_group_id=g.id) for g in groups)
    session.add(CompetitionStage(competition_id=comp.id, order_no=1, name="Очный тур", format=StageFormat.OFFLINE,
                                 starts_at=datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                                 ends_at=datetime.combine(start, datetime.max.time(), tzinfo=timezone.utc)))
    await session.flush()
    return comp


async def add_result(session, comp: Competition, athlete: User, place: int, *, score: int = 100) -> Result:
    """Одобренная заявка и результат участника в зачёте."""
    app = CompetitionApplication(
        competition_id=comp.id, athlete_id=athlete.id, submitted_by_user_id=athlete.id, submitted_by_role=RoleCode.ATHLETE,
        status=ApplicationStatus.APPROVED, age_on_start=15,
    )
    session.add(app)
    await session.flush()
    result = Result(competition_id=comp.id, application_id=app.id, athlete_id=athlete.id, place=place, score=score, status=ResultStatus.RANKED)
    session.add(result)
    await session.flush()
    return result


async def publish_protocol(session, comp: Competition, admin: User) -> Protocol:
    protocol = Protocol(competition_id=comp.id, number=f"П-{comp.id}", version=1, status=ProtocolStatus.PUBLISHED, generated_by=admin.id,
                        published_at=datetime.now(timezone.utc), snapshot={"rows": []})
    session.add(protocol)
    comp.status = CompetitionStatus.FINISHED
    await session.flush()
    return protocol


def auth(user: User, role: RoleCode, roles: list[RoleCode] | None = None) -> dict[str, str]:
    token, _ = create_access_token(user.id, [r.value for r in (roles or [role])], role.value)
    return {"Authorization": f"Bearer {token}"}
