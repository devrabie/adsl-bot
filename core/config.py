import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
    ADMINS_ID: str = "123456789"
    ENCRYPTION_KEY: str = "your_fernet_key_here"
    REPORT_TIME: str = "21:00"
    TIMEZONE: str = "Asia/Aden"
    CHECK_INTERVAL_HOURS: int = 4
    DATABASE_URL: str = "sqlite+aiosqlite:///yemennet_dsl.db"
    HTTP_PROXY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def admins_list(self) -> List[int]:
        if not self.ADMINS_ID:
            return []
        ids = []
        for raw_id in str(self.ADMINS_ID).split(","):
            raw_id = raw_id.strip()
            if raw_id.isdigit():
                ids.append(int(raw_id))
        return ids

settings = Settings()
