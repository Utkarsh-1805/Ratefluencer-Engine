"""
utils/env.py — tiny zero-dependency .env loader.

Reads key=value lines from a `.env` file at the repo root and puts them into
os.environ (without overwriting variables already set in the real environment).
No external package needed. Call load_env() once at app startup.
"""
from __future__ import annotations

import os
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[1]


def load_env(path: str | Path | None = None) -> None:
    """Load .env into os.environ. Existing env vars win (never overwritten)."""
    env_path = Path(path) if path else (_ENGINE_ROOT / ".env")
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            # strip surrounding quotes if present
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception as e:
        print(f"[env] could not load {env_path}: {e}")
