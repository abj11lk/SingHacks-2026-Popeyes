from . import config, db, supabase_client, tools

__all__ = ["config", "db", "supabase_client", "tools"]

# agents/ pulls in langgraph/langchain-groq -- imported lazily via
# `from backend import agents` or `from backend.agents import explanation`
# rather than eagerly here, so tool-layer-only workflows (the FastAPI GET
# endpoints in api.py that never touch an agent) don't pay that import cost
# or need GROQ_API_KEY set just to start up.
