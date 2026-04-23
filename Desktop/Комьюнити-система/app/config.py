from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    database_url: str
    redis_url: str

    bot_token: str

    admin_secret_path: str = "change-me"

    yookassa_shop_id: Optional[str] = None
    yookassa_secret_key: Optional[str] = None

    community_chat_url: str = ""
    track_career_url: str = ""
    track_business_url: str = ""
    track_selfdev_url: str = ""

    support_username: str = ""
    offer_url: str = ""

    default_funnel_key: str = "welcome"


def get_settings() -> Settings:
    return Settings()


settings = get_settings()