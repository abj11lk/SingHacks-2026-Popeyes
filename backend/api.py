"""
FastAPI layer over the tool functions -- the only thing new here is HTTP
plumbing. Every endpoint calls a function that already exists in tools.py
(verified against all 20 clients), reads a past agent report from Supabase,
or triggers a real one; no business logic lives in this file.

GET /agent-runs/{agent_type} reads the most recent report from Supabase
(agent_runs) -- fast, no LLM call, used to render whatever was last
generated (if anything) the instant a client page loads.

POST /agent-runs/{agent_type}/generate runs the agent live, right now, and
persists the result. This is deliberately RM-triggered rather than automatic
on page load: the Groq account backing this has an 8,000 tokens/minute cap,
so a live run needs to happen when someone chooses to run it, not silently
on every page view. Every run -- past or freshly generated -- is real; there
is no cached/hardcoded report anywhere, only "already ran" vs "run it now".

Run with:  uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import supabase_client, tools

app = FastAPI(title="Wealth Intelligence API")

# Dev-only: the frontend runs on a different port (Next.js dev server).
# Tighten this to the actual frontend origin before this goes anywhere real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/clients")
def list_clients():
    """Book overview: one row per client, for the landing page table."""
    return tools.list_clients()


@app.get("/api/clients/{client_id}")
def get_client_workspace(client_id: str):
    """
    Everything the client workspace page needs, in one call: profile,
    portfolios (with mandate status already embedded), holdings, notes,
    cash needs, plus the two deterministic risk panels (liquidity,
    concentration look-through).
    """
    try:
        snapshot = tools.get_client_snapshot(client_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown client_id: {client_id}")

    return {
        "snapshot": snapshot,
        "liquidity": tools.get_liquidity_map(client_id),
        "lookthrough": tools.get_lookthrough_exposure(client_id),
    }


@app.get("/api/clients/{client_id}/agent-runs/{agent_type}")
def get_latest_agent_run(client_id: str, agent_type: str):
    """
    Most recent pre-generated report of a given type (explanation, scenario,
    recommendation) for a client. Returns available=False rather than an
    error or fabricated content if none has been generated yet -- the
    frontend renders an honest empty state for that case.
    """
    runs = supabase_client.list_agent_runs(client_id=client_id, agent_type=agent_type, limit=1)
    if not runs:
        return {"available": False}
    run = runs[0]
    return {
        "available": True,
        "output": run["output"],
        "model": run["model"],
        "created_at": run["created_at"],
        "langsmith_trace_url": run["langsmith_trace_url"],
    }


@app.post("/api/clients/{client_id}/agent-runs/{agent_type}/generate")
def generate_agent_run(client_id: str, agent_type: str):
    """
    Runs an agent live and persists the result -- this is the only place an
    agent actually executes; nothing runs automatically on page load. Takes
    roughly 30-100 seconds (a real Groq call over several tool round-trips),
    so the frontend shows a loading state, not an instant response.
    """
    # heavy import (langgraph/langchain-groq); kept local to this endpoint
    from .agents import explanation, recommendation, scenario

    runners = {
        "explanation": explanation.explain,
        "scenario": scenario.analyze,
        "recommendation": recommendation.recommend,
    }
    if agent_type not in runners:
        raise HTTPException(
            status_code=501,
            detail=f"'{agent_type}' agent isn't built yet -- only {list(runners)} are live so far.",
        )

    try:
        tools.get_client_snapshot(client_id)  # cheap existence check, same 404 behaviour as the GET endpoint
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown client_id: {client_id}")

    result = runners[agent_type](client_id)

    response = {
        "available": True,
        "output": {"answer": result["answer"]},
        "model": explanation.MODEL,  # all three agents share the same model constant
        "created_at": None,  # the fresh run's own timestamp isn't round-tripped here; re-fetch via GET to get it
        "langsmith_trace_url": result["langsmith_trace_url"],
    }

    if agent_type == "recommendation":
        # Persist each parsed item as its own row -- this is what makes them
        # independently accept/edit/reject-able, unlike the single-blob
        # reports the other two agents produce.
        response["recommendations"] = [
            supabase_client.create_recommendation(
                client_id=client_id,
                agent_type="recommendation",
                title=item["title"],
                rationale=item["rationale"],
                supporting_data={
                    "tool_calls": result["tool_calls"],
                    "langsmith_trace_url": result["langsmith_trace_url"],
                },
                as_of=None,
            )
            for item in result["recommendations"]
        ]

    return response


@app.get("/api/clients/{client_id}/recommendations")
def list_client_recommendations(client_id: str):
    """
    Every recommendation ever generated for a client, newest first --
    each one independently accept/edit/reject-able, with its own status
    (pending/accepted/edited/rejected). This is the audit trail; nothing
    here is deleted when a new recommendation is generated.
    """
    return supabase_client.list_recommendations(client_id=client_id)


class RecommendationActionRequest(BaseModel):
    action: str  # "accepted" | "edited" | "rejected"
    edited_text: str | None = None
    note: str | None = None


@app.post("/api/recommendations/{recommendation_id}/actions")
def act_on_recommendation(recommendation_id: str, body: RecommendationActionRequest):
    """
    Records the RM's decision on a single recommendation -- the only way a
    recommendation's status changes. There is no path where a
    recommendation gets "applied" without this being called first.
    """
    try:
        return supabase_client.record_action(
            recommendation_id=recommendation_id,
            action=body.action,
            edited_text=body.edited_text,
            note=body.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/health")
def health():
    return {"status": "ok", "backend": tools.db.backend_name()}
