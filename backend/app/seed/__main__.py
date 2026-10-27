"""Заполнение БД: python -m app.seed [--reset]

Без флага заполняет только пустую БД. --reset очищает все таблицы и заполняет заново.
"""

import asyncio
import sys
from datetime import date
from random import Random

from sqlalchemy import func, select, text

from app.core.database import async_session_maker, engine
from app.models import Base, Discipline, User
from app.seed.history import History
from app.seed.people import seed_people
from app.seed.reference import seed_references


async def main(reset: bool) -> None:
    async with async_session_maker() as session:
        if reset:
            tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            await session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))
        elif await session.scalar(select(func.count()).select_from(Discipline)):
            print("Seed пропущен: БД уже заполнена (используйте --reset для пересоздания данных)")
            return

        rnd, today = Random(2026), date.today()
        refs = await seed_references(session)
        people = await seed_people(session, refs, rnd, today)
        stats = await History(session, refs, people, rnd, today).run()
        await session.commit()

        users = await session.scalar(select(func.count()).select_from(User))
        print(f"Seed готов: пользователей {users}, спортсменов {len(people.athletes)}, " + ", ".join(f"{k} {v}" for k, v in stats.items()))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main("--reset" in sys.argv))
