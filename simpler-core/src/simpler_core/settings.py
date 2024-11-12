from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(secrets_dir='.', env_prefix='fairlead_')

    cors_origins: List[str] = Field(default_factory=lambda: [
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:5173"
    ])

