"""Runtime configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path


def get_openai_api_key() -> str | None:
    """Return OpenAI API key from environment or local .env file.

    The official variable is OPENAI_API_KEY. OPENAPI_API_KEY is accepted as a
    compatibility alias because it is an easy typo to make.
    """

    return get_env_value("OPENAI_API_KEY", aliases=("OPENAPI_API_KEY",))


def get_env_value(name: str, aliases: tuple[str, ...] = ()) -> str | None:
    for key in (name, *aliases):
        value = os.environ.get(key)
        if value:
            return value

    env_path = find_env_file()
    if env_path is None:
        return None

    wanted = {name, *aliases}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        if key not in wanted:
            continue
        value = value.strip().strip('"').strip("'")
        return value or None
    return None


def find_env_file() -> Path | None:
    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None
