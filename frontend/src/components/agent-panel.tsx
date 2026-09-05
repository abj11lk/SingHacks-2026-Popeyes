"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { AgentMarkdown } from "@/components/markdown";
import { generateAgentRun, type AgentRun } from "@/lib/api";

// Client component because it needs interactive state (loading, the
// generate/regenerate button) -- everything else on the page is server-
// rendered. Reused across Explanation/Scenario/Recommendation tabs; only
// agentType="explanation" has a live agent behind it so far, the others
// will get one when those agents are built (same component, no change
// needed here).
export function AgentPanel({
  clientId,
  agentType,
  label,
  initial,
}: {
  clientId: string;
  agentType: string;
  label: string;
  initial: AgentRun;
}) {
  const [run, setRun] = useState<AgentRun>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    try {
      const fresh = await generateAgentRun(clientId, agentType);
      setRun(fresh);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  }

  if (run.available && run.output) {
    return (
      <div>
        <AgentMarkdown content={run.output.answer} />
        <div className="mt-4 flex items-center justify-between border-t pt-3 text-xs text-muted-foreground">
          <div>
            {run.created_at && (
              <>Generated {new Date(run.created_at).toLocaleString()} &middot; </>
            )}
            {run.langsmith_trace_url && (
              <a
                href={run.langsmith_trace_url}
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                View trace
              </a>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={handleGenerate} disabled={loading}>
            {loading ? "Regenerating…" : "Regenerate"}
          </Button>
        </div>
        {error && <p className="mt-2 text-destructive">{error}</p>}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-dashed p-8 text-center">
      <p className="text-sm text-muted-foreground mb-3">
        {label} not yet generated for this client.
      </p>
      <Button size="sm" onClick={handleGenerate} disabled={loading}>
        {loading ? "Generating… (up to a minute)" : "Generate"}
      </Button>
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
    </div>
  );
}
