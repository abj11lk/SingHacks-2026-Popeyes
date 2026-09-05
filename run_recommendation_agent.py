"""
Checkpoint driver for the Recommendation Agent (step 3 of the build order).

Runs it for real against CL-0014 (Lau Chi Ming -- the concentrated HK
property bet across 4 wrappers, plus the HKD 60m redevelopment liquidity
mismatch), prints the full answer, and shows how it parsed into discrete
recommendations.

Run from the repo root:  python run_recommendation_agent.py
"""
from backend.agents import recommendation

result = recommendation.recommend("CL-0014")

print("=" * 78)
print(f"Client: {result['client_id']}")
print(f"Question: {result['question']}")
print("=" * 78)
print()
print(result["answer"])
print()
print("=" * 78)
print(f"Parsed {len(result['recommendations'])} discrete recommendation(s):")
for i, item in enumerate(result["recommendations"], 1):
    print(f"\n--- {i}. {item['title']} ---")
    print(item["rationale"][:300])
print()
print("=" * 78)
print(f"Latency: {result['latency_ms']} ms")
print(f"LangSmith trace: {result['langsmith_trace_url'] or '(tracing unavailable)'}")
print(f"Supabase agent_run id: {result['agent_run_id'] or '(logging unavailable)'}")
print(f"Tool calls made: {len(result['tool_calls'])}")
for c in result["tool_calls"]:
    print(f"  - {c['tool_name']}({c['args']})")
