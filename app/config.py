"""Runtime configuration loaded from environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    public_base_url: str = "http://localhost:8000"
    debug: bool = False
    app_mode: str = "public"
    editor_session_hours: int = 12
    editor_cookie_secure: bool = True
    media_root: str = "var/media"
    media_max_bytes: int = 10 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        app_mode = os.getenv("APP_MODE", "public").lower()
        if app_mode not in {"public", "editorial"}:
            raise ValueError("APP_MODE must be 'public' or 'editorial'")
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://food_history:food_history@127.0.0.1:5432/food_history",
            ),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000"),
            debug=os.getenv("DEBUG", "").lower() in {"1", "true", "yes"},
            app_mode=app_mode,
            editor_session_hours=int(os.getenv("EDITOR_SESSION_HOURS", "12")),
            editor_cookie_secure=os.getenv("EDITOR_COOKIE_SECURE", "true").lower()
            in {"1", "true", "yes"},
            media_root=os.getenv("MEDIA_ROOT", "var/media"),
            media_max_bytes=int(os.getenv("MEDIA_MAX_BYTES", str(10 * 1024 * 1024))),
        )
