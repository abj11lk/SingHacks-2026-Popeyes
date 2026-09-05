"""
Checkpoint driver for the Scenario Agent (step 2 of the build order).

Runs it for real against CL-0019 (Abdullah Al-Mansoori -- the client whose
own RM note says "asked for a view on what happens to his portfolio if the
Strait reopens and normalises. We have not modelled this."), and prints the
answer plus the full traceability record.

Run from the repo root:  python run_scenario_agent.py
"""
from backend.agents import scenario

result = scenario.analyze("CL-0019")

print("=" * 78)
print(f"Client: {result['client_id']}")
print(f"Question: {result['question']}")
print("=" * 78)
print()
print(result["answer"])
print()
print("=" * 78)
print(f"Latency: {result['latency_ms']} ms")
print(f"LangSmith trace: {result['langsmith_trace_url'] or '(tracing unavailable)'}")
print(f"Supabase agent_run id: {result['agent_run_id'] or '(logging unavailable)'}")
print(f"Tool calls made: {len(result['tool_calls'])}")
for c in result["tool_calls"]:
    print(f"  - {c['tool_name']}({c['args']})")
