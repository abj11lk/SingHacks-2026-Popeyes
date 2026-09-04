-- Wealth Intelligence -- application-state schema.
--
-- This is deliberately NOT the reference dataset (clients/portfolios/
-- holdings/etc.) -- that stays in local SQLite, rebuilt from the CSVs on
-- every process start (see backend/db.py). It never changes during the
-- hackathon, so there is nothing to gain from putting it in a hosted DB,
-- and every risk from the demo depending on network/Supabase uptime.
--
-- What belongs here is genuinely stateful application data: what the
-- Recommendation Agent proposed, what the RM (Priscilla) actually did with
-- it, and an audit trail of every agent run -- the "human in the loop,
-- traceably" story for the judging criteria (explainability, compliance).
--
-- Run this once in the Supabase SQL Editor (Project -> SQL Editor -> New
-- query -> paste -> Run). Idempotent: safe to re-run.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- recommendations: what an agent proposed for a client
-- ---------------------------------------------------------------------
create table if not exists recommendations (
    id              uuid primary key default gen_random_uuid(),
    client_id       text not null,               -- e.g. 'CL-0014'
    agent_type      text not null,                -- 'recommendation' | 'concentration' | 'liquidity' | 'scenario' | 'explanation'
    title           text not null,                -- short, client-ready headline
    rationale       text not null,                -- the "why", must be traceable to tool output
    supporting_data jsonb not null default '{}',  -- snapshot of the tool call(s) and sources cited
    status          text not null default 'pending'
                        check (status in ('pending', 'accepted', 'edited', 'rejected')),
    rm_id           text not null default 'RM-SG-014',
    as_of           text,                          -- snapshot_date this was generated against
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists idx_recommendations_client on recommendations(client_id);
create index if not exists idx_recommendations_status on recommendations(status);

-- ---------------------------------------------------------------------
-- recommendation_actions: append-only log of what the RM did with each one
-- (human-in-the-loop: review, accept, edit, or reject -- never silently
-- auto-applied)
-- ---------------------------------------------------------------------
create table if not exists recommendation_actions (
    id                  uuid primary key default gen_random_uuid(),
    recommendation_id   uuid not null references recommendations(id) on delete cascade,
    action              text not null check (action in ('accepted', 'edited', 'rejected')),
    edited_text         text,                     -- populated when action = 'edited'
    actor               text not null default 'RM-SG-014',
    note                text,                     -- optional RM comment (e.g. why rejected)
    created_at          timestamptz not null default now()
);

create index if not exists idx_rec_actions_recommendation on recommendation_actions(recommendation_id);

-- ---------------------------------------------------------------------
-- agent_runs: audit log of every agent invocation, for compliance and
-- explainability review -- what was asked, what tools were called, what
-- came back, and a link to the full LangSmith trace.
-- ---------------------------------------------------------------------
create table if not exists agent_runs (
    id                  uuid primary key default gen_random_uuid(),
    client_id           text,
    agent_type          text not null,
    model               text,                     -- Groq model used
    input               jsonb,                     -- prompt / task summary
    output              jsonb,                     -- structured result returned to the caller
    tool_calls          jsonb not null default '[]', -- [{tool_name, args, result_summary}, ...]
    langsmith_trace_url text,
    latency_ms          integer,
    created_at          timestamptz not null default now()
);

create index if not exists idx_agent_runs_client on agent_runs(client_id);
create index if not exists idx_agent_runs_agent_type on agent_runs(agent_type);

-- ---------------------------------------------------------------------
-- keep updated_at current on recommendations
-- ---------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_recommendations_updated_at on recommendations;
create trigger trg_recommendations_updated_at
    before update on recommendations
    for each row
    execute function set_updated_at();

-- ---------------------------------------------------------------------
-- Row Level Security: this schema is only ever touched by our backend
-- using the service_role key (which bypasses RLS by design). Enabling RLS
-- with no permissive policy for anon/authenticated means that if this
-- project's anon key ever ends up in a frontend build, it cannot read or
-- write client-linked recommendation data -- only the backend can.
-- ---------------------------------------------------------------------
alter table recommendations enable row level security;
alter table recommendation_actions enable row level security;
alter table agent_runs enable row level security;
