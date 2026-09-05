"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  actOnRecommendation,
  generateAgentRun,
  type Recommendation,
} from "@/lib/api";

// Distinct from AgentPanel on purpose: Explanation/Scenario are one report
// to read; this is a set of discrete, individually-decidable items, which
// is the actual point of this capability ("RM stays in control" -- she can
// accept one proposal and reject another, not just the whole page).
export function RecommendationPanel({
  clientId,
  initial,
}: {
  clientId: string;
  initial: Recommendation[];
}) {
  const [items, setItems] = useState<Recommendation[]>(initial);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateAgentRun(clientId, "recommendation");
      const fresh = result.recommendations ?? [];
      setItems((prev) => [...fresh, ...prev]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  function updateItem(id: string, patch: Partial<Recommendation>) {
    setItems((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {items.length === 0
            ? "No recommendations generated yet."
            : `${items.length} recommendation${items.length > 1 ? "s" : ""} on record for this client.`}
        </p>
        <Button size="sm" onClick={handleGenerate} disabled={generating}>
          {generating ? "Generating… (up to a minute)" : items.length === 0 ? "Generate" : "Generate more"}
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {items.length === 0 && !generating && (
        <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
          Not yet generated for this client.
        </div>
      )}

      <div className="space-y-3">
        {items.map((item) => (
          <RecommendationCard key={item.id} item={item} onChange={updateItem} />
        ))}
      </div>
    </div>
  );
}

const STATUS_BADGE: Record<Recommendation["status"], { label: string; className?: string; variant?: "secondary" | "destructive" | "outline" }> = {
  pending: { label: "Pending review", variant: "outline" },
  accepted: { label: "Accepted", className: "bg-emerald-600 text-white" },
  edited: { label: "Edited & accepted", className: "bg-blue-600 text-white" },
  rejected: { label: "Rejected", variant: "secondary" },
};

function RecommendationCard({
  item,
  onChange,
}: {
  item: Recommendation;
  onChange: (id: string, patch: Partial<Recommendation>) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.rationale);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const badge = STATUS_BADGE[item.status];

  async function act(action: "accepted" | "rejected") {
    setBusy(true);
    setError(null);
    try {
      await actOnRecommendation(item.id, action);
      onChange(item.id, { status: action });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit() {
    setBusy(true);
    setError(null);
    try {
      await actOnRecommendation(item.id, "edited", { editedText: draft });
      onChange(item.id, { status: "edited", rationale: draft });
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border p-4">
      <div className="flex items-start justify-between gap-3">
        <h4 className="font-medium text-sm">{item.title}</h4>
        <Badge variant={badge.variant} className={badge.className}>
          {badge.label}
        </Badge>
      </div>

      {editing ? (
        <div className="mt-2 space-y-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            className="text-sm"
          />
          <div className="flex gap-2">
            <Button size="sm" onClick={saveEdit} disabled={busy}>
              Save edit
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-2 text-sm whitespace-pre-wrap">{item.rationale}</p>
      )}

      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}

      {item.status === "pending" && !editing && (
        <>
          <Separator className="my-3" />
          <div className="flex gap-2">
            <Button size="sm" onClick={() => act("accepted")} disabled={busy}>
              Accept
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(true)} disabled={busy}>
              Edit
            </Button>
            <Button size="sm" variant="destructive" onClick={() => act("rejected")} disabled={busy}>
              Reject
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
