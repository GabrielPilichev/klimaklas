from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-secret-change-me"  # noqa: S105 – само за разработка, забранен в production


class Settings(BaseSettings):
    """Настройки от променливи на средата с префикс KK_ (напр. KK_DATABASE_URL)."""

    model_config = SettingsConfigDict(env_prefix="KK_", env_file=".env", extra="ignore")

    environment: str = "development"  # development | production | test
    database_url: str = "sqlite:///./klimaklas.db"
    secret_key: str = DEFAULT_SECRET
    token_ttl_minutes: int = 12 * 60
    cookie_secure: bool = False
    timezone: str = "Europe/Sofia"

    # Прагове за CO2 (ppm)
    co2_warn: int = 800
    co2_alert: int = 1200
    alert_after_seconds: int = 300
    offline_after_seconds: int = 600

    # Rate limiting (заявки в минута)
    login_rate_limit: int = 5
    reading_rate_limit: int = 30

    # Известия (празно = изключено)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "klimaklas@localhost"
    public_url: str = "http://localhost:5173"

    def check(self) -> None:
        if self.environment == "production":
            if self.secret_key == DEFAULT_SECRET or len(self.secret_key) < 32:
                raise RuntimeError("KK_SECRET_KEY трябва да е зададен (поне 32 символа) в production.")
            if not self.cookie_secure:
                raise RuntimeError("KK_COOKIE_SECURE трябва да е true в production (HTTPS).")


settings = Settings()
