import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"

PASSWORD_SPECIAL_CHARS = r"!\"#$%&'()*+,\-./:;<=>?@[\]^_`{|}~"
PASSWORD_RULES = (
    (re.compile(r"[a-zа-яё]"), "строчную букву"),
    (re.compile(r"[A-ZА-ЯЁ]"), "заглавную букву"),
    (re.compile(r"\d"), "цифру"),
    (re.compile(f"[{PASSWORD_SPECIAL_CHARS}]"), "специальный символ (например, !?#@$%)"),
)


def password_strength_error(password: str) -> str | None:
    """Проверяет пароль на стандартные требования сложности: длина, регистр, цифра, спецсимвол.

    Возвращает текст первой нарушенной проверки или None, если пароль им соответствует."""
    if len(password) < 8:
        return "Пароль должен быть не короче 8 символов"
    if password.strip() != password:
        return "Пароль не должен начинаться или заканчиваться пробелом"
    missing = [label for pattern, label in PASSWORD_RULES if not pattern.search(password)]
    if missing:
        return "В пароле не хватает: " + ", ".join(missing)
    return None


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user_id: int, roles: list[str], active_role: str) -> tuple[str, int]:
    """Возвращает (токен, срок жизни в секундах). Активная роль хранится в токене."""
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "roles": roles,
        "active_role": active_role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM), expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """Бросает jwt.PyJWTError при неверной подписи или истёкшем сроке."""
    return jwt.decode(token, settings.secret_key, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp", "active_role"]})
