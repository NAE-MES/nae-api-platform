import os
from dotenv import load_dotenv

load_dotenv()

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value.strip()


def _require_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def _require_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "si", "sí", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"Environment variable {name} must be true or false")


DB_HOST = _require_env("DB_HOST")
DB_PORT = _require_int_env("DB_PORT", 5432)
DB_NAME = _require_env("DB_NAME")
DB_USER = _require_env("DB_USER")
DB_PASSWORD = _require_env("DB_PASSWORD")
API_TOKEN = _require_env("API_TOKEN")
ANALYTICS_USERNAME = os.getenv("ANALYTICS_USERNAME", "admin").strip() or "admin"
ANALYTICS_PASSWORD = os.getenv("ANALYTICS_PASSWORD", API_TOKEN).strip() or API_TOKEN
ANALYTICS_USERS = os.getenv("ANALYTICS_USERS", "").strip()
ANALYTICS_REVIEW_USERS = os.getenv("ANALYTICS_REVIEW_USERS", "").strip()
SESSION_SECRET = os.getenv("SESSION_SECRET", API_TOKEN).strip() or API_TOKEN
SESSION_MAX_AGE_SECONDS = _require_int_env("SESSION_MAX_AGE_SECONDS", 8 * 60 * 60)
SESSION_COOKIE_SECURE = _require_bool_env("SESSION_COOKIE_SECURE", False)

