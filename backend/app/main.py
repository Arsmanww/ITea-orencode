import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, get_session
from app.routers import (
    analytics,
    applications,
    athlete_profile,
    athletes,
    auth,
    certificates,
    coach_links,
    competitions,
    documents,
    federation,
    judges,
    notifications,
    profile,
    public,
    rating,
    ranks,
    rbac,
    reference,
    registry,
    results,
    sanctions,
)
from app.services.email import email_loop
from app.services.expiry import expiry_loop


class HealthOut(BaseModel):
    status: str
    database: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    tasks = [asyncio.create_task(expiry_loop()), asyncio.create_task(email_loop())]
    yield
    for task in tasks:
        task.cancel()
    await engine.dispose()


app = FastAPI(
    title="Единая цифровая платформа ФСП Оренбургской области",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/api/v1")
app.include_router(rbac.router, prefix="/api/v1")
app.include_router(competitions.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(results.router, prefix="/api/v1")
app.include_router(athletes.router, prefix="/api/v1")
for _router in (
    coach_links.coach_router,
    coach_links.athlete_router,
    coach_links.links_router,
    judges.collegium_router,
    judges.judge_router,
    judges.federation_router,
    ranks.router,
    notifications.router,
    reference.router,
    analytics.router,
    rating.router,
    documents.router,
    profile.router,
    certificates.router,
    athlete_profile.router,
    public.router,
    federation.router,
    registry.router,
    sanctions.router,
):
    app.include_router(_router, prefix="/api/v1")


@app.get("/api/v1/health", response_model=HealthOut)
async def health(
    response: Response, session: Annotated[AsyncSession, Depends(get_session)]
) -> HealthOut:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="error", database="unavailable")
    return HealthOut(status="ok", database="ok")
