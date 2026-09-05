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
# whenever the API key is being rejected upstream (403). Silencing the *log
# output* only, not the tracing attempt itself, so fixing the key needs no
# code change here to start working.
logging.getLogger("langsmith").setLevel(logging.CRITICAL)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Postgres connection (Supabase session pooler) for the reference dataset.
# Optional by design: if unset, or unreachable at process start, backend/db.py
# falls back to the local SQLite build so the app still runs offline.
DATABASE_URL = os.environ.get("DATABASE_URL")

# LangSmith renamed its env vars from LANGCHAIN_* to LANGSMITH_* -- accept
# either so a .env written against either generation of docs works, and
# make sure the *current* names end up in os.environ, since langsmith/
# langchain-core read LANGSMITH_* directly at call time, not through this
# module.
LANGSMITH_TRACING = os.environ.get("LANGSMITH_TRACING") or os.environ.get("LANGCHAIN_TRACING_V2")
LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
LANGSMITH_PROJECT = (
    os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT") or "wealth-intelligence"
)
# Only relevant for an org-scoped key on a multi-workspace account (the
# documented cause of a bare 403 on trace ingestion: org_scoped_key_requires_workspace).
# A workspace-scoped key doesn't need this set at all.
LANGSMITH_WORKSPACE_ID = os.environ.get("LANGSMITH_WORKSPACE_ID")

# LangSmith has region-separated deployments (US default, EU, APAC, ...). A
# key from a non-US-region workspace will 403 against the default
# api.smith.langchain.com host with no useful error message -- this was the
# actual root cause here (account is APAC-region), not the key, project, or
# workspace ID, all of which checked out fine beforehand.
LANGSMITH_ENDPOINT = os.environ.get("LANGSMITH_ENDPOINT")

for _name, _value in (
    ("LANGSMITH_TRACING", LANGSMITH_TRACING),
    ("LANGSMITH_API_KEY", LANGSMITH_API_KEY),
    ("LANGSMITH_PROJECT", LANGSMITH_PROJECT),
    ("LANGSMITH_WORKSPACE_ID", LANGSMITH_WORKSPACE_ID),
    ("LANGSMITH_ENDPOINT", LANGSMITH_ENDPOINT),
):
    if _value:
        os.environ[_name] = _value

# kept for any code still reading the old names directly
LANGCHAIN_TRACING_V2 = LANGSMITH_TRACING
LANGCHAIN_API_KEY = LANGSMITH_API_KEY
LANGCHAIN_PROJECT = LANGSMITH_PROJECT


def require(*names: str) -> None:
    """Raise clearly if config needed for the calling code isn't set, instead of failing deep inside a client library."""
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise RuntimeError(
            f"Missing required config: {', '.join(missing)}. Set them in .env (see .env.example)."
        )
