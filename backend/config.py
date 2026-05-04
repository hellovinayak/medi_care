"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./mediconnect.db"

    # JWT
    JWT_SECRET: str = "mediconnect-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    # Gemini AI
    GEMINI_API_KEY: str = ""

    # Google Calendar
    GOOGLE_CALENDAR_CREDENTIALS_PATH: str = ""
    GOOGLE_CALENDAR_ENABLED: bool = False

    # Email
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "mediconnect@example.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
