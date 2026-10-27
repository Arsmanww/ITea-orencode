"""Внешний канал уведомлений: бот в мессенджере MAX (Bot API, platform-api2.max.ru).

Привязка без ручного ввода идентификаторов: кабинет выдаёт одноразовую ссылку
https://max.ru/<бот>?start=<код>. Пользователь открывает её и нажимает «Начать», бот получает
событие bot_started с этим кодом, и платформа запоминает user_id получателя. Если диалог с ботом
уже был, код можно просто отправить боту сообщением.

События бот забирает long polling'ом (GET /updates), поэтому вебхук и публичный HTTPS-адрес
стенду не нужны. Отправка идёт фоновой задачей из очереди NotificationDelivery.
"""

import asyncio
import logging
import re
import secrets
import ssl
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import certifi
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.models import AuditLog, User
from app.models.enums import Channel
from app.services.common import full_name
from app.services.notifications import dispatch_channel

logger = logging.getLogger("fsp.max")
DISPATCH_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 25
LINK_TTL = timedelta(minutes=15)
MAX_TEXT = 4000
# корневой и промежуточный сертификаты НУЦ Минцифры: ими подписан сертификат API MAX
BUNDLED_CA = Path(__file__).with_name("certs") / "russian_trusted_ca.pem"
CODE_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")

HELP_TEXT = ("Это бот уведомлений платформы ФСП Оренбургской области. Чтобы получать уведомления, "
             "войдите в личный кабинет, откройте «Уведомления во внешних каналах» и нажмите «Подключить MAX».")


def max_enabled() -> bool:
    return bool(settings.max_bot_token)


def deep_link(code: str) -> str | None:
    return f"https://max.ru/{settings.max_bot_username}?start={code}" if settings.max_bot_username else None


def new_link_code() -> tuple[str, datetime]:
    """Одноразовый код привязки (символы, допустимые в start-параметре MAX) и срок его действия."""
    return secrets.token_urlsafe(12), datetime.now(timezone.utc) + LINK_TTL


@lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    """Обычные доверенные центры плюс сертификаты Минцифры. Проверка сертификата не отключается."""
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=settings.max_ca_file or str(BUNDLED_CA))
    return context


def _client(timeout: float = 10) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.max_api_base.rstrip("/"), headers={"Authorization": settings.max_bot_token},
                             verify=_ssl_context(), timeout=timeout)


def _error_text(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        data = {}
    return str(data.get("message") or data.get("code") or f"HTTP {response.status_code}")[:500]


async def send_message(user_id: str, text: str) -> tuple[bool, str | None]:
    """Отправляет личное сообщение пользователю MAX. Возвращает (успех, текст ошибки)."""
    if not max_enabled():
        return False, "Бот MAX не настроен (MAX_BOT_TOKEN)"
    try:
        async with _client() as client:
            response = await client.post("/messages", params={"user_id": user_id, "disable_link_preview": "true"},
                                         json={"text": text[:MAX_TEXT]})
    except httpx.HTTPError as e:
        return False, f"Ошибка соединения с MAX: {type(e).__name__}"
    if response.status_code == 200:
        return True, None
    return False, _error_text(response)


def _extract(update: dict[str, Any]) -> tuple[str | None, str | None]:
    """Из события MAX достаёт (user_id отправителя, код привязки или None)."""
    kind = update.get("update_type")
    if kind == "bot_started":
        user_id = (update.get("user") or {}).get("user_id")
        text = update.get("payload") or ""
    elif kind == "message_created":
        message = update.get("message") or {}
        user_id = (message.get("sender") or {}).get("user_id")
        text = (message.get("body") or {}).get("text") or ""
    else:
        return None, None
    text = text.strip().removeprefix("/start").strip()
    return (str(user_id) if user_id is not None else None), (text if CODE_RE.fullmatch(text) else None)


async def handle_update(session: AsyncSession, update: dict[str, Any]) -> str | None:
    """Обрабатывает событие бота: по действующему коду привязывает MAX к аккаунту.

    Возвращает текст ответа пользователю в MAX (None — отвечать не нужно)."""
    max_user_id, code = _extract(update)
    if max_user_id is None:
        return None
    if code is not None:
        user = await session.scalar(select(User).where(User.max_link_code == code))
        if user is not None and user.max_link_expires_at and user.max_link_expires_at > datetime.now(timezone.utc):
            user.max_user_id = max_user_id
            user.max_link_code = user.max_link_expires_at = None
            session.add(AuditLog(user_id=user.id, active_role=None, action="profile.max_bind", entity_type="user", entity_id=user.id,
                                 diff={"max_user_id": max_user_id}))
            await session.commit()
            return (f"Готово, {user.first_name}! MAX привязан к аккаунту {full_name(user)} на платформе ФСП Оренбургской области. "
                    "Сюда будут приходить уведомления о заявках, протоколах, разрядах, категориях и сроках.")
        return "Код привязки не найден или устарел. Получите новую ссылку в личном кабинете и откройте её ещё раз."
    bound = await session.scalar(select(User).where(User.max_user_id == max_user_id).limit(1))
    if bound is not None:
        return f"Уведомления подключены к аккаунту {full_name(bound)}. Отключить их можно в личном кабинете."
    return HELP_TEXT


async def dispatch_pending(session: AsyncSession) -> int:
    """Отправляет накопленные уведомления. Возвращает число обработанных."""
    return await dispatch_channel(session, Channel.MAX, lambda user: user.max_user_id, send_message)


async def _poll_updates() -> None:
    """Long polling событий бота: маркер хранится в памяти, после рестарта MAX отдаёт неподтверждённые события."""
    marker: int | None = None
    while True:
        try:
            params: dict[str, Any] = {"timeout": POLL_TIMEOUT_SECONDS, "types": "bot_started,message_created"}
            if marker is not None:
                params["marker"] = marker
            async with _client(timeout=POLL_TIMEOUT_SECONDS + 10) as client:
                response = await client.get("/updates", params=params)
            if response.status_code != 200:
                logger.warning("MAX /updates: %s", _error_text(response))
                await asyncio.sleep(5)
                continue
            data = response.json()
            marker = data.get("marker", marker)
            for update in data.get("updates") or []:
                async with async_session_maker() as session:
                    reply = await handle_update(session, update)
                max_user_id, _ = _extract(update)
                if reply and max_user_id:
                    ok, error = await send_message(max_user_id, reply)
                    if not ok:
                        logger.warning("MAX: не удалось ответить пользователю: %s", error)
        except asyncio.CancelledError:
            raise
        except httpx.HTTPError as e:
            logger.warning("MAX недоступен (%s), повтор через 5 с", type(e).__name__)
            await asyncio.sleep(5)
        except Exception:
            logger.exception("Ошибка получения событий MAX")
            await asyncio.sleep(5)


async def _dispatch_forever() -> None:
    while True:
        try:
            async with async_session_maker() as session:
                await dispatch_pending(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка отправки в MAX")
        await asyncio.sleep(DISPATCH_INTERVAL_SECONDS)


async def max_loop() -> None:
    """Фоновая задача: приём событий бота (привязка) и отправка очереди уведомлений."""
    if not max_enabled():
        logger.info("Бот MAX не настроен: канал отключён")
        return
    await asyncio.gather(_poll_updates(), _dispatch_forever())
