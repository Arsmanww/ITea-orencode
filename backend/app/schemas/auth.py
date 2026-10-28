from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import password_strength_error
from app.models.enums import Gender, RoleCode


class LoginIn(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)
    role: RoleCode | None = Field(default=None, description="Желаемая активная роль; по умолчанию выбирается автоматически")


class SwitchRoleIn(BaseModel):
    role: RoleCode


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    roles: list[RoleCode]
    active_role: RoleCode


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    last_name: str
    first_name: str
    patronymic: str | None
    birth_date: date
    gender: Gender
    phone: str | None
    municipality_id: int | None


class MeOut(BaseModel):
    user: UserOut
    roles: list[RoleCode]
    active_role: RoleCode


class RbacCheckOut(BaseModel):
    ok: bool
    required_role: RoleCode
    active_role: RoleCode
    user_id: int


class RegisterIn(BaseModel):
    """Быстрая регистрация спортсмена. Для несовершеннолетних обязательны данные законного представителя."""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    patronymic: str | None = Field(default=None, max_length=100)
    birth_date: date
    gender: Gender
    municipality_id: int | None = None
    organization_id: int | None = Field(default=None, description="Пусто — «без организации»")
    discipline_ids: list[int] = Field(min_length=1, max_length=6)
    consent: bool = Field(description="Согласие на обработку персональных данных")
    guardian_name: str | None = Field(default=None, max_length=255)
    guardian_phone: str | None = Field(default=None, max_length=32)
    guardian_email: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        error = password_strength_error(v)
        if error:
            raise ValueError(error)
        return v

    @model_validator(mode="after")
    def _rules(self) -> "RegisterIn":
        if not self.consent:
            raise ValueError("Для регистрации необходимо согласие на обработку персональных данных")
        today = date.today()
        age = today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        if age < 6 or age > 90:
            raise ValueError("Проверьте дату рождения")
        if age < 18 and not (self.guardian_name and self.guardian_name.strip() and self.guardian_phone and self.guardian_phone.strip()):
            raise ValueError("Для несовершеннолетнего укажите ФИО и телефон законного представителя")
        return self


class ForgotPasswordIn(BaseModel):
    email: EmailStr = Field(max_length=255)


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        error = password_strength_error(v)
        if error:
            raise ValueError(error)
        return v
