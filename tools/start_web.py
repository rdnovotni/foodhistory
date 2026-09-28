#!/usr/bin/env python3
"""Start the ASGI service on the platform-provided port."""

import os
import subprocess
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent


def main() -> None:
    if os.getenv("RUN_DB_BOOTSTRAP", "").lower() in {"1", "true", "yes"}:
        subprocess.run([sys.executable, str(ROOT / "bootstrap_db.py")], check=True)

    uvicorn.run(
        "app.main:app",
        app_dir=str(ROOT.parent),
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
