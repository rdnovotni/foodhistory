"""Runtime configuration loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    public_base_url: str = "http://localhost:8000"
    debug: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://food_history:food_history@127.0.0.1:5432/food_history",
            ),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000"),
            debug=os.getenv("DEBUG", "").lower() in {"1", "true", "yes"},
        )
