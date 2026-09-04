"""
Checkpoint driver for the Explanation Agent (step 2).

Runs it for real against CL-0012 (Cheung Kwok Wing -- duration/income risk,
the client this capability is built around) and prints the answer plus the
full traceability record, so we can eyeball whether it actually produced the
"understood the client" explanation the judging criteria ask for, not just
correct arithmetic.

Run from the repo root:  python run_explanation_agent.py
"""
from backend.agents import explanation

result = explanation.explain("CL-0012")

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
