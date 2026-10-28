from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from random import Random

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    AthleteEnrollment,
    AthleteProfile,
    CoachAthleteLink,
    CoachLinkHistory,
    CoachProfile,
    JudgeProfile,
    User,
    UserRole,
)
from app.models.enums import Gender, LinkStatus, RoleCode, TrainingStage
from app.seed import data
from app.seed.reference import Refs

OREN = timezone(timedelta(hours=5))


def at(d: date, hour: int = 12) -> datetime:
    return datetime.combine(d, time(hour), tzinfo=OREN)


def age_on(birth: date, d: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))


@dataclass
class Athlete:
    user: User
    birth: date
    skill: float
    enrollments: list[AthleteEnrollment] = field(default_factory=list)


@dataclass
class People:
    admin: User
    federation: list[User]
    coaches: list[User]
    judges: list[User]
    athletes: list[Athlete]
    athlete_by_id: dict[int, Athlete]
    user_by_id: dict[int, User]
    coach_org: dict[int, int | None]
    # (athlete_id, discipline_id) -> [(coach_id, с, по)] только по активным и завершённым связям
    links: dict[tuple[int, int], list[tuple[int, date, date | None]]]

    def coach_at(self, athlete_id: int, discipline_id: int, d: date) -> int | None:
        for coach_id, start, end in self.links.get((athlete_id, discipline_id), []):
            if start <= d and (end is None or d <= end):
                return coach_id
        return None


class Factory:
    def __init__(self, rnd: Random, pwd_hash: str) -> None:
        self.rnd = rnd
        self.pwd_hash = pwd_hash
        self.used: set[str] = set()

    def person(self, gender: Gender, birth: date, email: str, municipality_id: int, created: date) -> User:
        rnd = self.rnd
        for _ in range(50):
            surname = rnd.choice(data.MALE_SURNAMES)
            name = rnd.choice(data.MALE_NAMES if gender == Gender.MALE else data.FEMALE_NAMES)
            patr_m, patr_f = rnd.choice(data.PATRONYMICS)
            if gender == Gender.FEMALE:
                surname = surname[:-2] + "ая" if surname.endswith("ский") else surname + "а"
            fio = (surname, name)
            if fio not in self.used:
                self.used.add(fio)
                break
        return User(
            email=email,
            password_hash=self.pwd_hash,
            last_name=surname,
            first_name=name,
            patronymic=patr_m if gender == Gender.MALE else patr_f,
            birth_date=birth,
            gender=gender,
            phone=f"+7 (900) {rnd.randint(100, 999)}-{rnd.randint(10, 99)}-{rnd.randint(10, 99)}",
            municipality_id=municipality_id,
            created_at=at(created),
        )

    def birth(self, year_from: int, year_to: int, weights: list[int] | None = None) -> date:
        year = self.rnd.choices(range(year_from, year_to + 1), weights=weights)[0]
        return date(year, self.rnd.randint(1, 12), self.rnd.randint(1, 28))


async def seed_people(session: AsyncSession, refs: Refs, rnd: Random, today: date) -> People:
    f = Factory(rnd, hash_password(data.PASSWORD))
    mun = [m.id for m in refs.municipalities]
    org_ids = [o.id for o in refs.organizations]
    org_mun = {o.id: o.municipality_id for o in refs.organizations}
    domain = data.EMAIL_DOMAIN
    role_of = refs.roles

    # --- сотрудники федерации ---
    admin = f.person(Gender.FEMALE, date(1984, 5, 17), f"admin@{domain}", mun[0], date(2022, 12, 1))
    fed2 = f.person(Gender.MALE, date(1990, 2, 3), f"federation2@{domain}", mun[0], date(2022, 12, 1))
    federation = [admin, fed2]

    # --- тренеры (coach01 одновременно судья) ---
    coaches: list[User] = []
    coach_org: dict[int, int | None] = {}
    coach_orgs = [org_ids[i % len(org_ids)] for i in range(14)]
    for i in range(14):
        g = Gender.MALE if i % 3 else Gender.FEMALE
        coaches.append(f.person(g, f.birth(1976, 2000), f"coach{i + 1:02d}@{domain}", org_mun[coach_orgs[i]], date(2022, 12, 5)))

    # --- судьи ---
    judges = [
        f.person(Gender.MALE if i % 2 else Gender.FEMALE, f.birth(1970, 2002), f"judge{i + 1:02d}@{domain}", mun[i % 4], date(2022, 12, 10))
        for i in range(12)
    ]

    # --- спортсмены: round-robin по основной дисциплине, чтобы все 6 были представлены ---
    athlete_users: list[tuple[User, int, date, int | None]] = []
    weights = [2, 3, 4, 6, 8, 10, 12, 12, 11, 9, 7, 5, 3]
    for i in range(170):
        birth = f.birth(2004, 2016, weights)
        g = Gender.MALE if rnd.random() < 0.72 else Gender.FEMALE
        org = None if rnd.random() < 0.08 else rnd.choice(org_ids)
        municipality = org_mun[org] if org else rnd.choice(mun)
        base = rnd.choices([2021, 2022, 2023, 2024, 2025, 2026], weights=[6, 14, 22, 28, 30, 18])[0]
        start_year = max(base, birth.year + 8)
        start = date(start_year, rnd.randint(1, 12), rnd.randint(1, 28))
        if start > today:
            start = today - timedelta(days=rnd.randint(5, 60))
        user = f.person(g, birth, f"athlete{i + 1:03d}@{domain}", municipality, start)
        athlete_users.append((user, i % 6, start, org))

    # спортсмен-тренер (мульти-роль athlete + coach)
    ac_birth = date(2004, 8, 21)
    ac_user = f.person(Gender.MALE, ac_birth, f"athlete.coach@{domain}", mun[0], date(2022, 12, 12))
    athlete_users.append((ac_user, 0, date(2021, 9, 1), org_ids[5]))
    coaches.append(ac_user)
    coach_orgs.append(org_ids[5])

    all_users = [*federation, *coaches[:14], *judges, *(u for u, *_ in athlete_users)]
    session.add_all(all_users)
    await session.flush()
    for c, o in zip(coaches, coach_orgs, strict=True):
        coach_org[c.id] = o

    # --- роли и профили ---
    def add_roles(user: User, *codes: RoleCode) -> None:
        session.add_all(UserRole(user_id=user.id, role_id=role_of[c].id) for c in codes)

    judge_users = [*judges, admin, coaches[0]]
    add_roles(admin, RoleCode.FEDERATION, RoleCode.JUDGE)
    add_roles(fed2, RoleCode.FEDERATION)
    for c in coaches[:14]:
        add_roles(c, RoleCode.COACH, *([RoleCode.JUDGE] if c is coaches[0] else []))
    for j in judges:
        add_roles(j, RoleCode.JUDGE)
    add_roles(ac_user, RoleCode.ATHLETE, RoleCode.COACH)

    session.add_all(CoachProfile(user_id=c.id, organization_id=coach_org[c.id], bio="Тренер по спортивному программированию") for c in coaches)
    session.add_all(JudgeProfile(user_id=j.id, organization_id=rnd.choice(org_ids)) for j in judge_users)

    athletes: list[Athlete] = []
    disc_list = list(refs.disciplines.values())
    stars = set(rnd.sample(range(len(athlete_users)), 14))
    for idx, (user, primary, start, org) in enumerate(athlete_users):
        if user is not ac_user:
            add_roles(user, RoleCode.ATHLETE)
        skill = rnd.uniform(0.85, 0.97) if idx in stars else rnd.betavariate(2, 3)
        a = Athlete(user=user, birth=user.birth_date, skill=skill)
        minor = age_on(user.birth_date, today) < 18
        cert = rnd.random() < 0.6
        session.add(
            AthleteProfile(
                user_id=user.id,
                guardian_name=f"{user.last_name} {rnd.choice(data.MALE_NAMES)[0]}.{rnd.choice(data.MALE_NAMES)[0]}." if minor else None,
                guardian_phone=f"+7 (900) {rnd.randint(100, 999)}-{rnd.randint(10, 99)}-{rnd.randint(10, 99)}" if minor else None,
                guardian_email=f"parent{user.id}@{domain}" if minor else None,
                antidoping_course_date=today - timedelta(days=rnd.randint(10, 400)) if cert else None,
                antidoping_cert_url=f"https://rusada.ru/demo-certificate/{user.id}" if cert else None,
            )
        )
        discs = [disc_list[primary]]
        if rnd.random() < 0.3:
            discs.append(rnd.choice([d for d in disc_list if d is not disc_list[primary]]))
        for n, d in enumerate(discs):
            s = start if n == 0 else start + timedelta(days=rnd.randint(100, 500))
            if s > today:
                continue
            end = None
            if s < today - timedelta(days=540) and rnd.random() < 0.12:
                end = s + timedelta(days=rnd.randint(365, 900))
                end = None if end > today - timedelta(days=30) else end
            years = ((end or today) - s).days / 365
            stage = TrainingStage.INITIAL if years < 1 else TrainingStage.TRAINING if years < 3 else TrainingStage.IMPROVEMENT
            a.enrollments.append(
                AthleteEnrollment(
                    athlete_id=user.id, discipline_id=d.id, organization_id=org,
                    training_stage=stage, start_date=s, end_date=end, created_at=at(s),
                )
            )
        athletes.append(a)
    await session.flush()
    session.add_all(e for a in athletes for e in a.enrollments)
    await session.flush()

    # --- связки тренер–спортсмен ---
    links: dict[tuple[int, int], list[tuple[int, date, date | None]]] = {}
    by_org: dict[int | None, list[User]] = {}
    for c in coaches:
        by_org.setdefault(coach_org[c.id], []).append(c)

    for a in athletes:
        for e in a.enrollments:
            if rnd.random() > 0.8:
                continue
            pool = by_org.get(e.organization_id) or coaches
            coach = rnd.choice([c for c in pool if c.id != a.user.id] or coaches[:1])
            requested = e.start_date + timedelta(days=rnd.randint(0, 10))
            confirmed = requested + timedelta(days=rnd.randint(1, 10))
            ended = e.end_date
            roll = rnd.random()
            status = LinkStatus.ENDED if ended else LinkStatus.SUSPENDED if roll < 0.03 else LinkStatus.ACTIVE
            link = CoachAthleteLink(
                coach_id=coach.id, athlete_id=a.user.id, discipline_id=e.discipline_id, status=status,
                initiated_by_user_id=coach.id, requested_at=at(requested), confirmed_at=at(confirmed),
                ended_at=at(ended) if ended else None, created_at=at(requested),
            )
            session.add(link)
            await session.flush()
            hist = [
                (None, LinkStatus.PENDING, coach.id, requested, "Запрос на привязку"),
                (LinkStatus.PENDING, LinkStatus.ACTIVE, a.user.id, confirmed, "Привязка подтверждена спортсменом"),
            ]
            if status == LinkStatus.ENDED:
                hist.append((LinkStatus.ACTIVE, LinkStatus.ENDED, coach.id, ended, "Занятия завершены"))
            if status == LinkStatus.SUSPENDED:
                hist.append((LinkStatus.ACTIVE, LinkStatus.SUSPENDED, coach.id, today - timedelta(days=rnd.randint(20, 120)), "Пауза в занятиях"))
            session.add_all(
                CoachLinkHistory(link_id=link.id, old_status=o, new_status=n, changed_by=by, changed_at=at(d), comment=c, created_at=at(d))
                for o, n, by, d, c in hist
            )
            if status in (LinkStatus.ACTIVE, LinkStatus.ENDED):
                links.setdefault((a.user.id, e.discipline_id), []).append((coach.id, confirmed, ended))

    # запросы на привязку, ожидающие подтверждения (спортсмены без активного тренера)
    free = [a for a in athletes if a.enrollments and not any((a.user.id, e.discipline_id) in links for e in a.enrollments)]
    for a in rnd.sample(free, min(6, len(free))):
        e = a.enrollments[0]
        coach = rnd.choice(coaches[:14])
        d = today - timedelta(days=rnd.randint(1, 6))
        link = CoachAthleteLink(
            coach_id=coach.id, athlete_id=a.user.id, discipline_id=e.discipline_id, status=LinkStatus.PENDING,
            initiated_by_user_id=coach.id, requested_at=at(d), created_at=at(d),
        )
        session.add(link)
        await session.flush()
        session.add(CoachLinkHistory(link_id=link.id, old_status=None, new_status=LinkStatus.PENDING, changed_by=coach.id, changed_at=at(d), comment="Запрос на привязку", created_at=at(d)))
    await session.flush()

    return People(
        admin=admin, federation=federation, coaches=coaches, judges=judge_users, athletes=athletes,
        athlete_by_id={a.user.id: a for a in athletes},
        user_by_id={u.id: u for u in [*all_users]},
        coach_org=coach_org, links=links,
    )
