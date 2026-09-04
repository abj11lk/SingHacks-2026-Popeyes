"""
Application-state store: recommendations, the RM's accept/edit/reject
decisions on them, and an audit log of agent runs.

This is deliberately separate from backend/db.py (the reference dataset,
local SQLite, read-only). This module holds the *stateful* half of the
system -- what an agent proposed and what a human did about it -- which is
the part that actually needs to persist across sessions and be queryable
for compliance review.

Uses the service_role key, so it bypasses Row Level Security. That's
correct for a trusted backend; this key must never reach a frontend build
(see supabase/schema.sql for the RLS posture that protects against exactly
that mistake).
"""
from datetime import datetime, timezone

from supabase import Client, create_client

from . import config

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        config.require("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


# ---------------------------------------------------------------------------
# recommendations
# ---------------------------------------------------------------------------

def create_recommendation(
    client_id: str,
    agent_type: str,
    title: str,
    rationale: str,
    supporting_data: dict,
    as_of: str | None = None,
    rm_id: str = "RM-SG-014",
) -> dict:
    """Records a new agent-generated recommendation, pending RM review."""
    row = {
        "client_id": client_id,
        "agent_type": agent_type,
        "title": title,
        "rationale": rationale,
        "supporting_data": supporting_data,
        "as_of": as_of,
        "rm_id": rm_id,
    }
    res = get_client().table("recommendations").insert(row).execute()
    return res.data[0]


def list_recommendations(client_id: str | None = None, status: str | None = None) -> list:
    q = get_client().table("recommendations").select("*")
    if client_id:
        q = q.eq("client_id", client_id)
    if status:
        q = q.eq("status", status)
    return q.order("created_at", desc=True).execute().data


def get_recommendation(recommendation_id: str) -> dict | None:
    res = (
        get_client().table("recommendations")
        .select("*").eq("id", recommendation_id).execute()
    )
    return res.data[0] if res.data else None


# ---------------------------------------------------------------------------
# recommendation_actions -- the human-in-the-loop record
# ---------------------------------------------------------------------------

def record_action(
    recommendation_id: str,
    action: str,
    actor: str = "RM-SG-014",
    edited_text: str | None = None,
    note: str | None = None,
) -> dict:
    """
    Records what the RM did with a recommendation (accept / edit / reject)
    and updates the recommendation's status to match. This is the only way
    a recommendation's status changes -- there is no path where an agent's
    output is applied without this being written first.
    """
    if action not in ("accepted", "edited", "rejected"):
        raise ValueError(f"Invalid action: {action}")
    if action == "edited" and not edited_text:
        raise ValueError("edited_text is required when action='edited'")

    client = get_client()
    action_row = {
        "recommendation_id": recommendation_id,
        "action": action,
        "actor": actor,
        "edited_text": edited_text,
        "note": note,
    }
    result = client.table("recommendation_actions").insert(action_row).execute()
    client.table("recommendations").update({"status": action}).eq(
        "id", recommendation_id
    ).execute()
    return result.data[0]


def get_action_history(recommendation_id: str) -> list:
    return (
        get_client().table("recommendation_actions")
        .select("*").eq("recommendation_id", recommendation_id)
        .order("created_at").execute().data
    )


# ---------------------------------------------------------------------------
# agent_runs -- audit trail
# ---------------------------------------------------------------------------

def log_agent_run(
    agent_type: str,
    client_id: str | None = None,
    model: str | None = None,
    input_summary: dict | None = None,
    output: dict | None = None,
    tool_calls: list | None = None,
    langsmith_trace_url: str | None = None,
    latency_ms: int | None = None,
) -> dict:
    row = {
        "client_id": client_id,
        "agent_type": agent_type,
        "model": model,
        "input": input_summary or {},
        "output": output or {},
        "tool_calls": tool_calls or [],
        "langsmith_trace_url": langsmith_trace_url,
        "latency_ms": latency_ms,
    }
    res = get_client().table("agent_runs").insert(row).execute()
    return res.data[0]


def list_agent_runs(client_id: str | None = None, agent_type: str | None = None, limit: int = 50) -> list:
    q = get_client().table("agent_runs").select("*")
    if client_id:
        q = q.eq("client_id", client_id)
    if agent_type:
        q = q.eq("agent_type", agent_type)
    return q.order("created_at", desc=True).limit(limit).execute().data
