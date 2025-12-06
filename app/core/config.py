from functools import lru_cache
import os
from typing import Optional


class Settings:
    def __init__(self) -> None:
        self.app_name: str = os.getenv("APP_NAME", "Daily CRM Backend")
        self.debug: bool = os.getenv("DEBUG", "true").lower() == "true"

        # Database
        # По умолчанию используем SQLite в файле, чтобы проект запускался "из коробки"
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./daily_crm.db")

        # GigaChat
        self.gigachat_base_url: Optional[str] = os.getenv("GIGACHAT_BASE_URL")
        self.gigachat_client_id: Optional[str] = os.getenv("GIGACHAT_CLIENT_ID")
        self.gigachat_client_secret: Optional[str] = os.getenv("GIGACHAT_CLIENT_SECRET")

        # Auth
        self.auth_secret: str = os.getenv("AUTH_SECRET", "CHANGE_ME_SECRET_KEY")
        self.access_token_exp_minutes: int = int(os.getenv("ACCESS_TOKEN_EXP_MINUTES", "10080"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
