import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BACKEND_DIR / 'edupilot.db').as_posix()}",
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b").strip()
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
AUTH_COOKIE_NAME = "edupilot_session"
AUTH_COOKIE_SECURE = os.getenv(
    "AUTH_COOKIE_SECURE",
    "true" if APP_ENV == "production" else "false",
).strip().lower() == "true"
AUTH_SESSION_TTL_HOURS = int(os.getenv("AUTH_SESSION_TTL_HOURS", "12"))
SEED_DEMO_DATA = os.getenv("EDUPILOT_SEED_DEMO_DATA", "false").strip().lower() == "true"
STUDENT_SETUP_TOKEN_TTL_HOURS = int(
    os.getenv("STUDENT_SETUP_TOKEN_TTL_HOURS", "24")
)
ALLOW_LOCAL_STUDENT_SETUP_LINKS = (
    os.getenv("ALLOW_LOCAL_STUDENT_SETUP_LINKS", "false").strip().lower() == "true"
)
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").strip().lower() == "true"
SMTP_USE_STARTTLS = os.getenv("SMTP_USE_STARTTLS", "true").strip().lower() == "true"

if APP_ENV == "production" and not AUTH_COOKIE_SECURE:
    raise RuntimeError("AUTH_COOKIE_SECURE must be true in production.")

if APP_ENV == "production" and ALLOW_LOCAL_STUDENT_SETUP_LINKS:
    raise RuntimeError(
        "Local student setup links must not be enabled in production."
    )

if APP_ENV == "production" and not FRONTEND_BASE_URL.startswith("https://"):
    raise RuntimeError("FRONTEND_BASE_URL must use HTTPS in production.")

if (
    APP_ENV == "production"
    and SMTP_HOST
    and not (SMTP_USE_SSL or SMTP_USE_STARTTLS)
):
    raise RuntimeError("Production SMTP delivery must use TLS.")

if STUDENT_SETUP_TOKEN_TTL_HOURS < 1 or STUDENT_SETUP_TOKEN_TTL_HOURS > 168:
    raise RuntimeError("Student setup token lifetime must be between 1 and 168 hours.")
