import { useEffect, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";

import { listRecommendations } from "../api/client";
import { generateAgentRun } from "../api/agentClient";
import type { Recommendation } from "../types";
import RecommendationCard from "./RecommendationCard";

interface Props {
    clientId: string;
}

// Distinct from the Explanation/Scenario tabs on purpose: those are one report
// to read, this is a set of discrete, individually-decidable items -- the
// actual point of the Recommendation Agent ("RM stays in control", not just
// reads a bundled page). Mirrors the Next.js frontend's RecommendationPanel.
export default function RecommendationsSection({ clientId }: Props) {
    const [items, setItems] = useState<Recommendation[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [generating, setGenerating] = useState(false);
    const [genError, setGenError] = useState<string | null>(null);

    useEffect(() => {
        setLoading(true);
        setLoadError(null);
        listRecommendations(clientId)
            .then(setItems)
            .catch((err) => setLoadError(err instanceof Error ? err.message : "Failed to load recommendations."))
            .finally(() => setLoading(false));
    }, [clientId]);

    async function handleGenerate() {
        setGenerating(true);
        setGenError(null);
        try {
            const result = await generateAgentRun(clientId, "recommendation");
            const fresh = result.recommendations ?? [];
            setItems((prev) => [...fresh, ...prev]);
        } catch (err) {
            setGenError(err instanceof Error ? err.message : "Generation failed.");
        } finally {
            setGenerating(false);
        }
    }

    function updateItem(id: string, patch: Partial<Recommendation>) {
        setItems((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
    }

    return (
        <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <p style={{ margin: 0, fontSize: "12px", color: "var(--ink-faint)" }}>
                    {loading
                        ? "Loading recommendations..."
                        : items.length === 0
                          ? "No recommendations generated yet."
                          : `${items.length} recommendation${items.length > 1 ? "s" : ""} on record for this client.`}
                </p>
                <button className="primary-button" onClick={handleGenerate} disabled={generating}>
                    {generating ? (
                        <>
                            <Loader2 className="animate-spin" size={13} />
                            <span>Generating... (up to a minute)</span>
                        </>
                    ) : (
                        <>
                            <Sparkles size={13} />
                            <span>{items.length === 0 ? "Generate" : "Generate more"}</span>
                        </>
                    )}
                </button>
            </div>

            {loadError && <p style={{ color: "var(--danger)", fontSize: "12px" }}>{loadError}</p>}
            {genError && <p style={{ color: "var(--danger)", fontSize: "12px" }}>{genError}</p>}

            {!loading && items.length === 0 && !generating && (
                <div className="empty-state">
                    <p style={{ margin: 0 }}>Not yet generated for this client.</p>
                </div>
            )}

            <div className="recommendation-grid">
                {items.map((item) => (
                    <RecommendationCard key={item.id} recommendation={item} onChange={updateItem} />
                ))}
            </div>
        </div>
    );
}
