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
    # бот в мессенджере MAX (токен выдаёт MasterBot); без токена канал отключён
    max_bot_token: str = ""
    max_api_base: str = "https://platform-api2.max.ru"
    max_bot_username: str = ""
    # API MAX использует сертификат НУЦ Минцифры; по умолчанию берётся корневой и промежуточный из app/services/certs
    max_ca_file: str = ""
    # адрес фронтенда для ссылок в QR-кодах справок
    public_base_url: str = "http://localhost:3000"

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
