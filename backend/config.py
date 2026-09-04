"""
Loads .env once and exposes settings as module-level constants. Every other
module reads config from here rather than calling os.environ directly, so
there's one place that knows what's required vs optional.
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

# LangSmith retries failed trace ingestion in a background thread and logs
# each attempt regardless of whether calling code catches anything -- noisy
# right now because LANGCHAIN_API_KEY is being rejected (403) upstream.
# Silencing the *log output* only, not the tracing attempt itself, so
# fixing the key needs no code change here to start working.
logging.getLogger("langsmith").setLevel(logging.CRITICAL)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Postgres connection (Supabase session pooler) for the reference dataset.
# Optional by design: if unset, or unreachable at process start, backend/db.py
# falls back to the local SQLite build so the app still runs offline.
DATABASE_URL = os.environ.get("DATABASE_URL")

LANGCHAIN_TRACING_V2 = os.environ.get("LANGCHAIN_TRACING_V2")
LANGCHAIN_API_KEY = os.environ.get("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.environ.get("LANGCHAIN_PROJECT", "wealth-intelligence")


def require(*names: str) -> None:
    """Raise clearly if config needed for the calling code isn't set, instead of failing deep inside a client library."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise RuntimeError(
            f"Missing required config: {', '.join(missing)}. Set them in .env (see .env.example)."
        )
