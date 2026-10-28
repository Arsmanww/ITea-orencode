import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from random import Random
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Competition,
    CompetitionAgeGroup,
    CompetitionApplication,
    CompetitionJudge,
    CompetitionStage,
    JudgeCategoryAssignment,
    JudgeCategoryRequest,
    ParticipationCertificate,
    Protocol,
    RankAssignment,
    RankRequest,
    Result,
    Sanction,
    Team,
)
from app.models.enums import (
    ApplicationStatus,
    CalendarPlan,
    CompetitionLevel,
    CompetitionStatus,
    ProtocolStatus,
    RatingTier,
    RequestKind,
    RequestStatus,
    ResultStatus,
    RoleCode,
    SanctionKind,
    StageFormat,
)
from app.seed import data
from app.seed.people import OREN, Athlete, People, age_on, at
from app.seed.reference import Refs

KINDS: dict[str, dict[str, Any]] = {
    "reg_champ": dict(type="Чемпионат", level=CompetitionLevel.REGIONAL, tier=RatingTier.REGIONAL, plan=CalendarPlan.OREN_REGIONAL,
                      groups=["14-17", "18+"], title="Чемпионат Оренбургской области", cap=4),
    "reg_first": dict(type="Первенство", level=CompetitionLevel.REGIONAL, tier=RatingTier.REGIONAL, plan=CalendarPlan.OREN_REGIONAL,
                      groups=["9-13", "14-17"], title="Первенство Оренбургской области", cap=4),
    "interreg": dict(type="Кубок", level=CompetitionLevel.INTERREGIONAL, tier=RatingTier.INTERREGIONAL, plan=CalendarPlan.EKP_MINSPORT,
                     groups=["14-17", "18+"], title="Кубок Приволжского федерального округа", cap=6),
    "rus_champ": dict(type="Чемпионат", level=CompetitionLevel.ALL_RUSSIAN, tier=RatingTier.RUSSIA_CHAMPIONSHIP, plan=CalendarPlan.EKP_MINSPORT,
                      groups=["18+"], title="Чемпионат России", cap=7),
    "rus_first": dict(type="Первенство", level=CompetitionLevel.ALL_RUSSIAN, tier=RatingTier.RUSSIA_FIRST, plan=CalendarPlan.EKP_MINSPORT,
                      groups=["14-17"], title="Первенство России", cap=7),
}
# в календарь следующего года федерация вносит региональный чемпионат и выездные соревнования
FUTURE_KINDS = {"reg_champ", "interreg", "rus_champ"}
MONTH_DAY = {
    "reg_champ": lambda i: (3 + i % 2, 14 + i),
    "reg_first": lambda i: (10 + i % 2, 10 + i),
    "interreg": lambda i: (6 + i % 2, 8 + i),
    "rus_champ": lambda i: (8 + i % 2, 5 + i),
    "rus_first": lambda i: (11 + i % 2, 6 + i),
}
ONLINE_NAME = {
    "algorithmic": "Отборочный онлайн-контест", "product": "Разработка проекта (онлайн)",
    "infosec": "Отборочный CTF (онлайн)", "ai": "Онлайн-этап: решение по метрике",
    "robotics": "Квалификация в симуляторе (онлайн)", "uas": "Квалификация в симуляторе (онлайн)",
}
OFFLINE_NAME = {
    "algorithmic": "Очный финал", "product": "Защита проектов (очно)", "infosec": "Очный финал (атака–защита)",
    "ai": "Очная защита решений", "robotics": "Финал с реальными роботами", "uas": "Финал: полёты на полигоне",
}


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def dt(d: date, hour: int) -> datetime:
    return datetime.combine(d, time(hour), tzinfo=OREN)


def q2(x: float) -> Decimal:
    return Decimal(str(round(x, 2)))


def performance(code: str, skill: float, rnd: Random) -> dict[str, Any]:
    """Результат участника по правилам дисциплины: (score, время, решено, details, ключ сортировки)."""
    q = min(1.0, max(0.0, skill + rnd.gauss(0, 0.12)))
    if code == "algorithmic":
        solved = round(q * 9)
        penalty = solved * rnd.randint(900, 2400) + rnd.randint(0, 1200)
        letters = rnd.sample("ABCDEFGHIJ", solved)
        details = {"tasks": [{"task": c, "solved": c in letters, "attempts": rnd.randint(1, 4)} for c in "ABCDEFGHIJ"]}
        return dict(score=Decimal(solved * 100), time=Decimal(penalty), solved=solved, details=details, key=(-solved, penalty))
    if code == "product":
        score = round(40 + q * 58, 1)
        crit = {k: round(min(100, max(0, score + rnd.uniform(-6, 6))), 1) for k in ("идея", "реализация", "презентация", "UX")}
        return dict(score=q2(score), time=None, solved=None, details={"criteria": crit}, key=(-score, 0))
    if code == "infosec":
        flags = round(q * 12)
        score = flags * 75
        t = rnd.randint(3600, 21000)
        return dict(score=Decimal(score), time=Decimal(t), solved=flags, details={"flags": flags}, key=(-score, t))
    if code == "ai":
        metric = round(50 + q * 47 + rnd.uniform(0, 2), 2)
        return dict(score=q2(metric), time=None, solved=None,
                    details={"metric": "F1", "public": round(metric - rnd.uniform(0, 2), 2), "private": metric}, key=(-metric, 0))
    score = int(q * (280 if code == "robotics" else 250)) + rnd.randint(0, 20)
    t = round(rnd.uniform(40, 170) - q * 20 if code == "robotics" else rnd.uniform(60, 240) - q * 30, 3)
    details = {"runs": [{"run": 1, "score": score - rnd.randint(0, 15)}, {"run": 2, "score": score}]}
    if code == "uas":
        details["penalties"] = rnd.randint(0, 3)
    return dict(score=Decimal(score), time=Decimal(str(t)), solved=None, details=details, key=(-score, t))


@dataclass
class Spec:
    year: int
    i: int
    code: str
    kind: str
    start: date
    end: date


class History:
    def __init__(self, session: AsyncSession, refs: Refs, people: People, rnd: Random, today: date) -> None:
        self.session, self.refs, self.people, self.rnd, self.today = session, refs, people, rnd, today
        self.sanctions: dict[int, list[tuple[date, date | None]]] = {}
        self.rank_state: dict[tuple[int, int], int] = {}
        self.pending_rank: set[tuple[int, int]] = set()
        self.last_asg: dict[tuple[int, int], tuple[RankAssignment, Athlete]] = {}
        self.latest: dict[tuple[int, int], tuple[Result, Competition]] = {}
        self.finished: list[tuple[Result, Competition, Athlete, dict[str, Any]]] = []
        self.org_name = {o.id: o.name for o in refs.organizations}
        self.stats = dict(competitions=0, applications=0, results=0, protocols=0, rank_requests=0, rank_assignments=0)

    # ---------- помощники ----------
    def sanctioned(self, athlete_id: int, d: date) -> bool:
        return any(a <= d and (b is None or d <= b) for a, b in self.sanctions.get(athlete_id, []))

    def org_of(self, a: Athlete, disc_id: int) -> int | None:
        return next((e.organization_id for e in a.enrollments if e.discipline_id == disc_id), None)

    def enrolled(self, a: Athlete, disc_id: int, start: date, end: date) -> bool:
        return any(e.discipline_id == disc_id and e.start_date <= start and (e.end_date is None or e.end_date >= end) for e in a.enrollments)

    # ---------- основной проход ----------
    async def run(self) -> dict[str, int]:
        specs = self.build_specs()
        for spec in specs:
            await self.process(spec, is_last_upcoming=spec is self.last_upcoming(specs))
        await self.confirm_requests()
        await self.judge_categories()
        await self.certificates()
        await self.session.flush()
        return self.stats

    def build_specs(self) -> list[Spec]:
        specs = []
        for year in range(2023, 2028):
            for i, code in enumerate(c for c, *_ in data.DISCIPLINES):
                for kind, md in MONTH_DAY.items():
                    if year == 2027 and kind not in FUTURE_KINDS:
                        continue
                    month, day = md(i)
                    start = date(year, month, day)
                    specs.append(Spec(year, i, code, kind, start, start + timedelta(days=1 if kind == "reg_first" else 2)))
        specs.sort(key=lambda s: (s.start, s.code))
        return specs

    def last_upcoming(self, specs: list[Spec]) -> Spec | None:
        up = [s for s in specs if s.start > self.today]
        return up[-1] if up else None

    def stages(self, spec: Spec) -> list[tuple[str, StageFormat, datetime, datetime, str]]:
        code, kind = spec.code, spec.kind
        online = (ONLINE_NAME[code], StageFormat.ONLINE, dt(spec.start - timedelta(days=10), 10), dt(spec.start - timedelta(days=10), 14),
                  f"https://contest.fsp-demo.example.com/{code}-{spec.year}")
        place = self.place(spec)
        offline = (OFFLINE_NAME[code], StageFormat.OFFLINE, dt(spec.start, 10), dt(spec.end, 18), place)
        if kind == "reg_first":
            return [online if code in ("infosec", "ai") else offline]
        if kind == "interreg" and code not in ("robotics", "uas"):
            return [offline]
        if kind == "reg_champ" or kind in ("rus_champ", "rus_first") or code in ("robotics", "uas"):
            return [online, offline]
        return [offline]

    def place(self, spec: Spec) -> str:
        rnd = Random(spec.year * 1000 + spec.i * 10 + list(KINDS).index(spec.kind))
        if spec.kind.startswith("reg"):
            return rnd.choice(data.MUNICIPALITIES[:6]) + ", площадка «Алгоритм»"
        return rnd.choice(data.INTERREGIONAL_CITIES if spec.kind == "interreg" else data.RUSSIA_CITIES)

    async def process(self, spec: Spec, is_last_upcoming: bool) -> None:
        rnd, today, refs, people = self.rnd, self.today, self.refs, self.people
        cfg = KINDS[spec.kind]
        disc = refs.disciplines[spec.code]
        groups = [refs.age_groups[g] for g in cfg["groups"]]
        stages = self.stages(spec)
        online_only = all(s[1] == StageFormat.ONLINE for s in stages)
        opens, deadline = dt(spec.start - timedelta(days=45), 9), dt(spec.start - timedelta(days=7), 23)

        if spec.end < today:
            status = CompetitionStatus.FINISHED
        elif spec.start <= today:
            status = CompetitionStatus.IN_PROGRESS
        elif is_last_upcoming:
            status = CompetitionStatus.DRAFT
        elif opens.date() > today:
            status = CompetitionStatus.PUBLISHED
        else:
            status = CompetitionStatus.REGISTRATION_OPEN if deadline.date() >= today else CompetitionStatus.REGISTRATION_CLOSED

        is_regional = cfg["plan"] == CalendarPlan.OREN_REGIONAL
        n = self.stats["competitions"] + 1
        comp = Competition(
            title=f"{cfg['title']} по спортивному программированию ({refs.short_names[spec.code]}), {spec.year}",
            discipline_id=disc.id, type_id=refs.types[cfg["type"]].id, level=cfg["level"], rating_tier=cfg["tier"],
            status=status, calendar_plan=cfg["plan"],
            plan_number=f"ОО-{spec.year}-{n:03d}" if is_regional else f"ЕКП-{spec.year}/{1000 + n * 7}",
            start_date=spec.start, end_date=spec.end,
            location="Онлайн" if online_only else self.place(spec),
            registration_opens_at=opens, registration_deadline=deadline,
            is_team=spec.code == "product" and spec.kind == "reg_champ",
            description="Соревнование проводится по правилам вида спорта «спортивное программирование». Положение прикреплено к соревнованию.",
            created_by=people.admin.id, created_at=at(spec.start - timedelta(days=60)),
        )
        self.session.add(comp)
        await self.session.flush()
        self.stats["competitions"] += 1
        self.session.add_all(CompetitionAgeGroup(competition_id=comp.id, age_group_id=g.id) for g in groups)
        self.session.add_all(
            CompetitionStage(competition_id=comp.id, order_no=k, name=nm, format=fm, starts_at=s, ends_at=e, place_or_url=pl)
            for k, (nm, fm, s, e, pl) in enumerate(stages, start=1)
        )

        # судейская коллегия: у региональных соревнований, у выездных – иногда
        if is_regional or rnd.random() < 0.3:
            k = rnd.randint(3, 5) if is_regional else 1
            chosen = rnd.sample(people.judges, k)
            main_positions = [refs.positions[0], refs.positions[1]]
            for idx, j in enumerate(chosen):
                pos = main_positions[idx] if idx < 2 and is_regional else rnd.choice(refs.positions[2:])
                self.session.add(CompetitionJudge(competition_id=comp.id, judge_id=j.id, position_id=pos.id, assigned_by=people.admin.id,
                                                  created_at=at(spec.start - timedelta(days=30))))

        eligible = [a for a in people.athletes if self.is_eligible(a, disc.id, spec, groups)]
        if status == CompetitionStatus.FINISHED:
            await self.finished_competition(comp, spec, disc.id, eligible, groups)
        elif status in (CompetitionStatus.REGISTRATION_OPEN, CompetitionStatus.REGISTRATION_CLOSED, CompetitionStatus.IN_PROGRESS):
            await self.open_applications(comp, spec, disc.id, eligible)

    def is_eligible(self, a: Athlete, disc_id: int, spec: Spec, groups: list[Any]) -> bool:
        age = age_on(a.birth, spec.start)
        return (
            any(g.min_age <= age <= g.max_age for g in groups)
            and self.enrolled(a, disc_id, spec.start, spec.start)
            and not self.sanctioned(a.user.id, spec.start)
        )

    def pick_participants(self, spec: Spec, eligible: list[Athlete]) -> list[Athlete]:
        rnd = self.rnd
        if spec.kind.startswith("reg"):
            chosen = [a for a in eligible if rnd.random() < 0.8]
            return chosen if len(chosen) >= 4 else eligible[: max(4, len(chosen))]
        n = rnd.randint(3, 6) if spec.kind == "interreg" else rnd.randint(2, 4)
        return sorted(eligible, key=lambda a: a.skill + rnd.gauss(0, 0.1), reverse=True)[:n]

    def make_app(self, comp: Competition, a: Athlete, spec: Spec, status: ApplicationStatus, team: Team | None, comment: str | None = None) -> CompetitionApplication:
        rnd = self.rnd
        coach_id = self.people.coach_at(a.user.id, comp.discipline_id, spec.start)
        submitted = spec.start - timedelta(days=rnd.randint(8, 40))
        moderated = status != ApplicationStatus.PENDING
        return CompetitionApplication(
            competition_id=comp.id, athlete_id=a.user.id, team_id=team.id if team else None,
            submitted_by_user_id=coach_id or a.user.id, submitted_by_role=RoleCode.COACH if coach_id else RoleCode.ATHLETE,
            coach_id=coach_id, status=status, age_on_start=age_on(a.birth, spec.start),
            moderated_by=self.people.admin.id if moderated else None,
            moderated_at=at(submitted + timedelta(days=rnd.randint(1, 3))) if moderated else None,
            moderation_comment=comment, created_at=at(submitted),
        )

    async def make_teams(self, comp: Competition, athletes: list[Athlete]) -> dict[int, Team]:
        by_org: dict[int | None, list[Athlete]] = {}
        for a in athletes:
            by_org.setdefault(self.org_of(a, comp.discipline_id), []).append(a)
        mapping: dict[int, Team] = {}
        teams: list[tuple[Team, list[Athlete]]] = []
        for org, members in by_org.items():
            for k in range(0, len(members), 3):
                chunk = members[k : k + 3]
                label = self.org_name.get(org, "Без организации") if org else "Без организации"
                team = Team(competition_id=comp.id, name=f"«{label}» #{k // 3 + 1}",
                            coach_id=self.people.coach_at(chunk[0].user.id, comp.discipline_id, comp.start_date))
                teams.append((team, chunk))
        self.session.add_all(t for t, _ in teams)
        await self.session.flush()
        for team, chunk in teams:
            for a in chunk:
                mapping[a.user.id] = team
        return mapping

    async def open_applications(self, comp: Competition, spec: Spec, disc_id: int, eligible: list[Athlete]) -> None:
        applicants = [a for a in eligible if self.rnd.random() < 0.45]
        teams = await self.make_teams(comp, applicants) if comp.is_team else {}
        apps = []
        for a in applicants:
            r = self.rnd.random()
            st = ApplicationStatus.PENDING if r < 0.5 else ApplicationStatus.APPROVED
            apps.append(self.make_app(comp, a, spec, st, teams.get(a.user.id)))
        self.session.add_all(apps)
        self.stats["applications"] += len(apps)

    async def finished_competition(self, comp: Competition, spec: Spec, disc_id: int, eligible: list[Athlete], groups: list[Any]) -> None:
        rnd, session = self.rnd, self.session
        participants = self.pick_participants(spec, eligible)
        teams = await self.make_teams(comp, participants) if comp.is_team else {}

        apps: list[tuple[CompetitionApplication, Athlete]] = []
        for a in participants:
            apps.append((self.make_app(comp, a, spec, ApplicationStatus.APPROVED, teams.get(a.user.id)), a))
        # отклонённые заявки: не проходят по возрасту
        too_young_old = [
            a for a in self.people.athletes
            if self.enrolled(a, disc_id, spec.start, spec.start) and not any(g.min_age <= age_on(a.birth, spec.start) <= g.max_age for g in groups)
        ]
        for a in rnd.sample(too_young_old, min(len(too_young_old), rnd.randint(0, 2))):
            apps.append((self.make_app(comp, a, spec, ApplicationStatus.REJECTED, None,
                                       "Возраст спортсмена не соответствует возрастным группам соревнования"), a))
        session.add_all(app for app, _ in apps)
        await session.flush()
        self.stats["applications"] += len(apps)

        approved = [(app, a) for app, a in apps if app.status == ApplicationStatus.APPROVED]
        code = spec.code
        # неявка и дисквалификация
        status_of: dict[int, ResultStatus] = {}
        for app, a in approved:
            r = rnd.random()
            if r < 0.04:
                status_of[a.user.id] = ResultStatus.DID_NOT_START
            elif r < 0.055 and spec.year >= 2024:
                status_of[a.user.id] = ResultStatus.DISQUALIFIED

        perf: dict[int, dict[str, Any]] = {}
        if comp.is_team:
            team_perf: dict[int, dict[str, Any]] = {}
            for app, a in approved:
                t = teams[a.user.id]
                members = [x for _, x in approved if teams[x.user.id].id == t.id]
                team_perf.setdefault(t.id, performance(code, sum(m.skill for m in members) / len(members), rnd))
                perf[a.user.id] = team_perf[t.id]
        else:
            for app, a in approved:
                perf[a.user.id] = performance(code, a.skill, rnd)

        ranked = [(app, a) for app, a in approved if a.user.id not in status_of]
        place_of: dict[int, int] = {}
        if comp.is_team:
            order = sorted({teams[a.user.id].id: perf[a.user.id]["key"] for _, a in ranked}.items(), key=lambda kv: kv[1])
            team_place = {tid: n for n, (tid, _) in enumerate(order, start=1)}
            for _, a in ranked:
                place_of[a.user.id] = team_place[teams[a.user.id].id]
        else:
            for n, (_, a) in enumerate(sorted(ranked, key=lambda x: perf[x[1].user.id]["key"]), start=1):
                place_of[a.user.id] = n

        results: list[tuple[Result, Athlete]] = []
        for app, a in approved:
            st = status_of.get(a.user.id, ResultStatus.RANKED)
            p = perf[a.user.id]
            res = Result(
                competition_id=comp.id, application_id=app.id, athlete_id=a.user.id,
                place=place_of.get(a.user.id), status=st,
                score=p["score"] if st == ResultStatus.RANKED else None,
                time_seconds=p["time"] if st == ResultStatus.RANKED else None,
                tasks_solved=p["solved"] if st == ResultStatus.RANKED else None,
                details={**p["details"], **({"team": teams[a.user.id].name} if comp.is_team else {})} if st == ResultStatus.RANKED else None,
                note={ResultStatus.DID_NOT_START: "Не явился", ResultStatus.DISQUALIFIED: "Нарушение правил соревнования"}.get(st),
                created_at=at(spec.end),
            )
            results.append((res, a))
            if st == ResultStatus.DISQUALIFIED:
                end_sanction = spec.end + timedelta(days=365)
                self.sanctions.setdefault(a.user.id, []).append((spec.end, end_sanction))
                session.add(Sanction(athlete_id=a.user.id, kind=SanctionKind.DISQUALIFICATION, date_from=spec.end, date_to=end_sanction,
                                     reason="Нарушение правил соревнования, дисквалификация по решению судейской коллегии",
                                     competition_id=comp.id, created_at=at(spec.end)))
        session.add_all(r for r, _ in results)
        await session.flush()
        self.stats["results"] += len(results)

        self.protocol(comp, spec, results, teams)
        for res, a in results:
            if res.status == ResultStatus.RANKED:
                self.latest[(a.user.id, disc_id)] = (res, comp)
                self.finished.append((res, comp, a, perf[a.user.id]))
        await self.rank_progression(comp, spec, disc_id, results)

    def protocol(self, comp: Competition, spec: Spec, results: list[tuple[Result, Athlete]], teams: dict[int, Team]) -> None:
        ordered = sorted(results, key=lambda x: (x[0].place is None, x[0].place or 0, x[1].user.last_name))
        rows = [
            {
                "place": r.place, "athlete_id": a.user.id,
                "full_name": f"{a.user.last_name} {a.user.first_name} {a.user.patronymic or ''}".strip(),
                "birth_date": a.birth.isoformat(),
                "team": teams[a.user.id].name if a.user.id in teams else None,
                "score": str(r.score) if r.score is not None else None,
                "time_seconds": str(r.time_seconds) if r.time_seconds is not None else None,
                "tasks_solved": r.tasks_solved, "status": r.status.value,
            }
            for r, a in ordered
        ]
        published = spec.end + timedelta(days=2)
        recent = published > self.today
        self.session.add(Protocol(
            competition_id=comp.id, number=f"П-{comp.id:04d}/{spec.year}", version=1,
            status=ProtocolStatus.DRAFT if recent else ProtocolStatus.PUBLISHED,
            generated_by=self.people.admin.id, generated_at=at(spec.end, 19),
            published_at=None if recent else at(published),
            snapshot={"competition": comp.title, "start_date": spec.start.isoformat(), "end_date": spec.end.isoformat(),
                      "location": comp.location, "rows": rows},
            created_at=at(spec.end, 19),
        ))
        self.stats["protocols"] += 1

    async def rank_progression(self, comp: Competition, spec: Spec, disc_id: int, results: list[tuple[Result, Athlete]]) -> None:
        rnd, today, refs = self.rnd, self.today, self.refs
        cap = KINDS[spec.kind]["cap"]
        if len([1 for r, _ in results if r.status == ResultStatus.RANKED]) < 6:
            return
        for res, a in results:
            if res.status != ResultStatus.RANKED or res.place is None or res.place > 3 or rnd.random() > 0.85:
                continue
            key = (a.user.id, disc_id)
            if key in self.pending_rank:
                continue
            nxt = self.rank_state.get(key, 0) + 1
            if nxt <= 3 and age_on(a.birth, spec.end) >= 18:
                nxt = 4
            if nxt > cap:
                continue
            req_date = spec.end + timedelta(days=rnd.randint(5, 20))
            if req_date > today:
                continue
            decide = req_date + timedelta(days=rnd.randint(7, 25))
            coach_id = self.people.coach_at(a.user.id, disc_id, req_date)
            rank = refs.ranks[nxt - 1]
            if decide > today:
                status = RequestStatus.SUBMITTED
            else:
                status = RequestStatus.APPROVED if rnd.random() < 0.92 else RequestStatus.REJECTED
            req = RankRequest(
                athlete_id=a.user.id, rank_id=rank.id, discipline_id=disc_id, kind=RequestKind.ASSIGN,
                competition_id=comp.id, result_id=res.id,
                submitted_by_user_id=coach_id or a.user.id, submitted_by_role=RoleCode.COACH if coach_id else RoleCode.ATHLETE,
                coach_id=coach_id, status=status,
                decided_by=None if status == RequestStatus.SUBMITTED else self.people.admin.id,
                decided_at=None if status == RequestStatus.SUBMITTED else at(decide),
                decision_comment="Результат соответствует требованиям ЕВСК" if status == RequestStatus.APPROVED
                else "Недостаточно оснований по результату" if status == RequestStatus.REJECTED else None,
                created_at=at(req_date),
            )
            self.session.add(req)
            await self.session.flush()
            self.stats["rank_requests"] += 1
            if status == RequestStatus.SUBMITTED:
                self.pending_rank.add(key)
            elif status == RequestStatus.APPROVED:
                valid = add_months(decide, rank.validity_months) if rank.validity_months else None
                asg = RankAssignment(
                    athlete_id=a.user.id, rank_id=rank.id, discipline_id=disc_id, assigned_at=decide, valid_until=valid,
                    order_number=f"{rnd.randint(40, 480)}-р", order_date=decide, request_id=req.id, created_at=at(decide),
                )
                self.session.add(asg)
                self.last_asg[key] = (asg, a)
                self.rank_state[key] = nxt
                self.stats["rank_assignments"] += 1

    async def confirm_requests(self) -> None:
        """Заявки на подтверждение разряда у тех, чей разряд скоро истекает."""
        rnd, today = self.rnd, self.today
        for key, (asg, a) in self.last_asg.items():
            disc_id = key[1]
            if asg.valid_until is None or not (today <= asg.valid_until <= today + timedelta(days=90)):
                continue
            if key in self.pending_rank or key not in self.latest:
                continue
            if rnd.random() > 0.85:
                continue
            res, comp = self.latest[key]
            coach_id = self.people.coach_at(a.user.id, disc_id, today)
            d = today - timedelta(days=rnd.randint(0, 5))
            self.session.add(RankRequest(
                athlete_id=a.user.id, rank_id=asg.rank_id, discipline_id=disc_id, kind=RequestKind.CONFIRM,
                competition_id=comp.id, result_id=res.id,
                submitted_by_user_id=coach_id or a.user.id, submitted_by_role=RoleCode.COACH if coach_id else RoleCode.ATHLETE,
                coach_id=coach_id, status=RequestStatus.SUBMITTED, created_at=at(d),
            ))
            self.pending_rank.add(key)
            self.stats["rank_requests"] += 1
        await self.session.flush()

    async def judge_categories(self) -> None:
        rnd, today, cats = self.rnd, self.today, self.refs.categories
        admin = self.people.admin.id
        special = {
            2: add_months(today, -48) + timedelta(days=20),   # истекает через 20 дней
            4: add_months(today, -60),                        # уже истекла
            6: add_months(today, -48) + timedelta(days=55),   # истекает через 55 дней
        }
        for idx, j in enumerate(self.people.judges):
            cat = cats[1 + idx % 4]
            assigned = special.get(idx, date(2022, 1, 1) + timedelta(days=rnd.randint(0, 1300)))
            request_id = None
            if idx in (0, 1, 3, 5):
                req = JudgeCategoryRequest(judge_id=j.id, category_id=cat.id, kind=RequestKind.ASSIGN, status=RequestStatus.APPROVED,
                                           comment="Прошу присвоить категорию", decided_by=admin, decided_at=at(assigned),
                                           decision_comment="Одобрено", created_at=at(assigned - timedelta(days=14)))
                self.session.add(req)
                await self.session.flush()
                request_id = req.id
            self.session.add(JudgeCategoryAssignment(
                judge_id=j.id, category_id=cat.id, assigned_at=assigned, valid_until=add_months(assigned, cat.validity_months or 48),
                order_number=f"{rnd.randint(10, 300)}-с", order_date=assigned, request_id=request_id, created_at=at(assigned),
            ))
        judges = self.people.judges
        pending = [
            (2, RequestKind.CONFIRM, cats[1 + 2 % 4], RequestStatus.SUBMITTED, "Подтверждение категории, срок истекает"),
            (7, RequestKind.ASSIGN, cats[3], RequestStatus.SUBMITTED, "Прошу присвоить первую категорию"),
            (8, RequestKind.ASSIGN, cats[4], RequestStatus.REJECTED, "Прошу присвоить всероссийскую категорию"),
        ]
        for idx, kind, cat, st, comment in pending:
            d = today - timedelta(days=rnd.randint(1, 6) if st == RequestStatus.SUBMITTED else 90)
            self.session.add(JudgeCategoryRequest(
                judge_id=judges[idx].id, category_id=cat.id, kind=kind, status=st, comment=comment,
                decided_by=admin if st == RequestStatus.REJECTED else None,
                decided_at=at(d + timedelta(days=10)) if st == RequestStatus.REJECTED else None,
                decision_comment="Недостаточно судейской практики" if st == RequestStatus.REJECTED else None,
                created_at=at(d),
            ))

    async def certificates(self) -> None:
        by_athlete: dict[int, list[tuple[Result, Competition, Athlete, dict[str, Any]]]] = {}
        for item in self.finished:
            if item[0].place is not None and item[0].place <= 3:
                by_athlete.setdefault(item[2].user.id, []).append(item)
        top = sorted(by_athlete.values(), key=len, reverse=True)[:3]
        n = 0
        for items in top:
            for res, comp, a, _ in items[:2]:
                n += 1
                self.session.add(ParticipationCertificate(
                    number=f"ФСП-56-{comp.end_date.year}-{n:05d}", athlete_id=a.user.id, result_id=res.id,
                    snapshot={
                        "athlete": f"{a.user.last_name} {a.user.first_name} {a.user.patronymic or ''}".strip(),
                        "birth_date": a.birth.isoformat(), "competition": comp.title, "level": comp.level.value,
                        "dates": f"{comp.start_date.isoformat()} – {comp.end_date.isoformat()}", "place": res.place,
                        "score": str(res.score) if res.score is not None else None,
                    },
                    issued_at=at(comp.end_date + timedelta(days=5)), created_at=at(comp.end_date + timedelta(days=5)),
                ))
