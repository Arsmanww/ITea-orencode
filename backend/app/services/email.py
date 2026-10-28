"""Внешний канал уведомлений: электронная почта через SMTP.

Проще, чем был бот в мессенджере: адрес уже известен – это email пользователя, с которым он
зарегистрирован. Отдельной процедуры привязки не нужно, пользователь может только выключить канал
в профиле (``User.email_notifications_enabled``). Отправка идёт фоновой задачей из очереди
``NotificationDelivery`` (см. ``services/notifications.py``), поэтому запрос пользователя
не ждёт ответа почтового сервера.

Письмо восстановления пароля («Забыли пароль?») отправляется отдельно, сразу внутри запроса
(see ``services/password_reset.py``) – там токен живёт ограниченное время, и нет смысла класть
отправку в общую очередь, у которой задержка до нескольких секунд не критична, но зачем лишняя
задержка там, где пользователь ждёт письмо прямо сейчас.
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_maker
from app.models import User
from app.models.enums import Channel
from app.services.notifications import dispatch_channel

logger = logging.getLogger("fsp.email")
DISPATCH_INTERVAL_SECONDS = 3


def email_enabled() -> bool:
    return bool(settings.smtp_host)


def _send_sync(to: str, subject: str, text: str) -> None:
    """Блокирующая отправка через stdlib smtplib; вызывается в отдельном потоке."""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    message.set_content(text)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
        if settings.smtp_use_tls:
            client.starttls()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message)


async def send_email(to: str, subject: str, text: str) -> tuple[bool, str | None]:
    """Отправляет письмо. Возвращает (успех, текст ошибки)."""
    if not email_enabled():
        return False, "Почта на платформе не настроена (SMTP_HOST)"
    try:
        await asyncio.to_thread(_send_sync, to, subject, text)
    except (OSError, smtplib.SMTPException) as e:
        return False, f"Ошибка отправки почты: {type(e).__name__}: {e}"[:500]
    return True, None


async def notify_account_event(user: User, subject: str, text: str) -> None:
    """Прямая отправка письма о событии аккаунта (регистрация, вход) – сразу внутри запроса,
    как и восстановление пароля. В отличие от общей очереди уведомлений, не создаёт запись в
    личном кабинете: это чисто внешний сигнал, а не событие, которое нужно хранить в истории.
    Уважает тумблер пользователя – как и остальная почта, в отличие от письма сброса пароля."""
    if not email_enabled() or not user.email_notifications_enabled:
        return
    ok, error = await send_email(user.email, subject, text)
    if not ok:
        logger.warning("Письмо о событии аккаунта не отправлено (%s): %s", error, user.email)


async def dispatch_pending(session: AsyncSession) -> int:
    """Отправляет накопленные уведомления. Возвращает число обработанных."""

    def address(user: User) -> str | None:
        return user.email if user.email_notifications_enabled else None

    async def send(to: str, body: str) -> tuple[bool, str | None]:
        subject, _, text = body.partition("\n\n")
        return await send_email(to, subject or "Уведомление", body)

    return await dispatch_channel(session, Channel.EMAIL, address, send)


async def email_loop() -> None:
    """Фоновая задача: раз в несколько секунд отправляет очередь, если SMTP настроен."""
    if not email_enabled():
        logger.info("SMTP не настроен: канал почты отключён")
        return
    while True:
        try:
            async with async_session_maker() as session:
                await dispatch_pending(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка отправки почты")
        await asyncio.sleep(DISPATCH_INTERVAL_SECONDS)
