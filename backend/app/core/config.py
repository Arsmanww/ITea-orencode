from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    secret_key: str
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "/srv/uploads"
    max_upload_mb: int = 10
    # внешний канал уведомлений – email через SMTP; без хоста канал отключён (уведомления остаются в кабинете)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from: str = "ФСП Оренбургской области <noreply@fsp-orenburg.example>"
    # адрес фронтенда для ссылок в QR-кодах справок и в письмах (восстановление пароля)
    public_base_url: str = "http://localhost:3000"
    password_reset_ttl_minutes: int = 60

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
