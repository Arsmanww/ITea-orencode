"""Восстановление пароля («Забыли пароль?»).

Токен выдаётся один раз, живёт settings.password_reset_ttl_minutes (по умолчанию 60) и хранится
в БД только в виде sha256-хеша (``PasswordResetToken.token_hash``) — сам токен в открытом виде
нигде, кроме письма пользователю, не появляется.

Письмо уходит сразу внутри запроса, а не через общую очередь уведомлений: пользователь ждёт его
прямо сейчас, и отдельная очередь с интервалом в несколько секунд тут не нужна. Если SMTP на
стенде не настроен (частый случай на хакатоне без боевой почты), ссылка не теряется — она
печатается в лог приложения, так демонстрационный сценарий можно пройти и без реального почтового
ящика: `docker compose logs api`.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import PasswordResetToken, User
from app.services.email import send_email

logger = logging.getLogger("fsp.password_reset")
TOKEN_BYTES = 32


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def reset_link(raw_token: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/reset-password?token={raw_token}"


async def issue_reset_token(session: AsyncSession, user: User) -> None:
    """Создаёт токен и отправляет письмо со ссылкой. Коммит делает вызывающий код."""
    raw_token = secrets.token_urlsafe(TOKEN_BYTES)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_ttl_minutes)
    session.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw_token), expires_at=expires_at))

    link = reset_link(raw_token)
    text = (
        f"Здравствуйте, {user.first_name}!\n\n"
        "Поступил запрос на сброс пароля от аккаунта платформы ФСП Оренбургской области.\n"
        f"Ссылка действует {settings.password_reset_ttl_minutes} минут:\n{link}\n\n"
        "Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо — пароль останется прежним."
    )
    ok, error = await send_email(user.email, "Восстановление пароля — ФСП Оренбургской области", text)
    if not ok:
        # SMTP не настроен или недоступен — печатаем ссылку в лог, чтобы демо-сценарий был проходим и так
        logger.warning("Письмо восстановления пароля не отправлено (%s). Ссылка для %s: %s", error, user.email, link)


async def consume_reset_token(session: AsyncSession, raw_token: str) -> User | None:
    """Проверяет токен (существует, не использован, не истёк) и помечает его использованным.

    Возвращает пользователя или None, если токен недействителен. Коммит делает вызывающий код."""
    row = await session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token)))
    if row is None or row.used_at is not None or row.expires_at < datetime.now(timezone.utc):
        return None
    row.used_at = datetime.now(timezone.utc)
    return await session.get(User, row.user_id)
