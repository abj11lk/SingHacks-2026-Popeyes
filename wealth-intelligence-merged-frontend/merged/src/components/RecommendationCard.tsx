import { Check, Pencil, X, Save } from "lucide-react";
import { useState } from "react";

import type { Recommendation } from "../types";
import { actOnRecommendation } from "../api/client";

interface Props {
    recommendation: Recommendation;
    onChange: (id: string, patch: Partial<Recommendation>) => void;
}

const STATUS_LABEL: Record<string, string> = {
    pending: "Pending review",
    accepted: "Accepted",
    edited: "Edited & accepted",
    rejected: "Rejected",
};

// Mirrors the Next.js frontend's RecommendationCard 1:1 (same actOnRecommendation
// call, same pending/accepted/edited/rejected states) -- restyled with this app's
// existing .recommendation-card CSS instead of shadcn components. Recommendations
// here only ever have {title, rationale, status}: no priority score, "issue" text,
// or heuristic flag -- our backend doesn't produce those, so nothing here invents
// them the way the original (unwired) version of this component did.
export default function RecommendationCard({ recommendation, onChange }: Props) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(recommendation.rationale);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const id = recommendation.id!;
    const status = recommendation.status || "pending";

    async function act(action: "accepted" | "rejected") {
        setBusy(true);
        setError(null);
        try {
            await actOnRecommendation(id, action);
            onChange(id, { status: action });
        } catch (e) {
            setError(e instanceof Error ? e.message : "Action failed.");
        } finally {
            setBusy(false);
        }
    }

    async function saveEdit() {
        setBusy(true);
        setError(null);
        try {
            await actOnRecommendation(id, "edited", { editedText: draft });
            onChange(id, { status: "edited", rationale: draft });
            setEditing(false);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Save failed.");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="recommendation-card">
            <div className="recommendation-header">
                <h3>{recommendation.title}</h3>
                <span className={`status-badge status-${status}`}>
                    {STATUS_LABEL[status] || status}
                </span>
            </div>

            <div className="recommendation-section">
                <div className="section-label">Rationale</div>

                {editing ? (
                    <textarea
                        value={draft}
                        onChange={(event) => setDraft(event.target.value)}
                        rows={4}
                    />
                ) : (
                    <p className="recommendation-text">{recommendation.rationale}</p>
                )}
            </div>

            {error && <p style={{ color: "var(--danger)", fontSize: "12px", margin: "8px 0 0" }}>{error}</p>}

            {status === "pending" && (
                <div className="recommendation-actions">
                    {editing ? (
                        <>
                            <button className="action-button edit" disabled={busy} onClick={saveEdit}>
                                <Save size={16} />
                                Save edit
                            </button>
                            <button
                                className="action-button reject"
                                disabled={busy}
                                onClick={() => {
                                    setEditing(false);
                                    setDraft(recommendation.rationale);
                                }}
                            >
                                <X size={16} />
                                Cancel
                            </button>
                        </>
                    ) : (
                        <>
                            <button className="action-button accept" disabled={busy} onClick={() => act("accepted")}>
                                <Check size={16} />
                                Accept
                            </button>
                            <button className="action-button edit" disabled={busy} onClick={() => setEditing(true)}>
                                <Pencil size={16} />
                                Edit
                            </button>
                            <button className="action-button reject" disabled={busy} onClick={() => act("rejected")}>
                                <X size={16} />
                                Reject
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
