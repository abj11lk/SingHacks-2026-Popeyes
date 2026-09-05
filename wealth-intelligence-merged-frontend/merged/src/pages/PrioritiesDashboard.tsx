import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Loader2, AlertCircle, ChevronRight } from "lucide-react";

import { getPriorities } from "../api/client";
import { getPrioritiesRun, generatePrioritiesRun } from "../api/agentClient";
import type { PriorityRow, AgentRun } from "../types";
import { formatCurrency } from "../lib/format";
import AgentMarkdown from "../components/AgentMarkdown";

// The book-wide "twenty clients, one RM -- who does she call first" view.
// The ranking/scores below come from a pure deterministic pass (zero Groq
// tokens, safe on every load); the briefing card is the one thing that
// costs a real LLM call, so it's RM-triggered like every other agent run.
export default function PrioritiesDashboard() {
    const navigate = useNavigate();

    const [book, setBook] = useState<PriorityRow[] | null>(null);
    const [bookError, setBookError] = useState<string | null>(null);

    const [briefing, setBriefing] = useState<AgentRun | null>(null);
    const [briefingLoading, setBriefingLoading] = useState(false);
    const [briefingError, setBriefingError] = useState<string | null>(null);

    useEffect(() => {
        getPriorities()
            .then((res) => setBook(res.book))
            .catch((err) => setBookError(err instanceof Error ? err.message : "Failed to load priorities."));

        getPrioritiesRun()
            .then(setBriefing)
            .catch(() => {
                // No briefing generated yet -- not an error.
            });
    }, []);

    async function handleGenerateBriefing() {
        setBriefingLoading(true);
        setBriefingError(null);
        try {
            const run = await generatePrioritiesRun();
            setBriefing(run);
        } catch (err) {
            setBriefingError(err instanceof Error ? err.message : "Failed to generate briefing.");
        } finally {
            setBriefingLoading(false);
        }
    }

    return (
        <div style={{ minHeight: "100vh", background: "#f8fafc", color: "#0f172a", fontFamily: "system-ui, -apple-system, sans-serif", paddingBottom: "60px" }}>
            <div style={{ maxWidth: "1160px", margin: "0 auto", padding: "24px 20px" }}>

                <div style={{ marginBottom: "20px" }}>
                    <h1 style={{ fontSize: "28px", fontWeight: 800, color: "#020617", margin: "0 0 6px 0", letterSpacing: "-0.02em" }}>
                        Book Priorities
                    </h1>
                    <p style={{ fontSize: "13px", color: "#64748b", margin: 0 }}>
                        Twenty clients, one RM. Who does she call first, and can you defend the ranking?
                    </p>
                </div>

                {/* Briefing */}
                <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)", overflow: "hidden", marginBottom: "20px" }}>
                    <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: 0 }}>
                            Triage Briefing
                        </h2>
                        <button
                            onClick={handleGenerateBriefing}
                            disabled={briefingLoading}
                            style={{
                                display: "inline-flex", alignItems: "center", gap: "6px",
                                background: "#0f172a", color: "#ffffff", fontSize: "12px", fontWeight: 600,
                                padding: "7px 14px", borderRadius: "5px", border: "none",
                                cursor: briefingLoading ? "not-allowed" : "pointer",
                                opacity: briefingLoading ? 0.6 : 1, boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                            }}
                        >
                            {briefingLoading ? (
                                <>
                                    <Loader2 className="animate-spin" size={13} />
                                    <span>Running Agent...</span>
                                </>
                            ) : (
                                <>
                                    <Sparkles size={13} color="#fcd34d" />
                                    <span>{briefing?.available ? "Regenerate" : "Generate"}</span>
                                </>
                            )}
                        </button>
                    </div>
                    <div style={{ padding: "20px" }}>
                        {briefingError && (
                            <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", padding: "10px 14px", borderRadius: "6px", fontSize: "12px", display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
                                <AlertCircle size={15} />
                                <span>{briefingError}</span>
                            </div>
                        )}
                        {briefing?.available && briefing?.output?.answer ? (
                            <AgentMarkdown content={briefing.output.answer} />
                        ) : (
                            <div style={{ textAlign: "center", padding: "30px 16px", color: "#94a3b8", fontSize: "13px" }}>
                                <Sparkles size={28} color="#cbd5e1" style={{ margin: "0 auto 10px auto", display: "block" }} />
                                <p style={{ margin: 0, fontWeight: 500 }}>No triage briefing generated yet.</p>
                                <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#64748b" }}>
                                    The ranking below is already real and live -- Generate adds a narrative explaining it.
                                </p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Ranked list */}
                <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)", overflow: "hidden" }}>
                    <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0" }}>
                        <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: 0 }}>
                            Ranked Book
                        </h2>
                    </div>

                    {bookError && (
                        <div style={{ padding: "20px" }}>
                            <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", padding: "10px 14px", borderRadius: "6px", fontSize: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                                <AlertCircle size={15} />
                                <span>{bookError}</span>
                            </div>
                        </div>
                    )}

                    {!book && !bookError && (
                        <div style={{ padding: "40px", textAlign: "center", color: "#94a3b8", fontSize: "13px", display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
                            <Loader2 className="animate-spin" size={16} />
                            Loading priorities...
                        </div>
                    )}

                    {book?.map((row) => (
                        <div
                            key={row.client_id}
                            onClick={() => navigate(`/client/${encodeURIComponent(row.client_id)}`)}
                            style={{
                                display: "flex", alignItems: "center", gap: "16px",
                                padding: "14px 20px", borderBottom: "1px solid #f1f5f9", cursor: "pointer",
                            }}
                        >
                            <span className={`priority-badge priority-${row.priority.toLowerCase()}`} style={{ flex: "0 0 auto" }}>
                                {row.priority}
                            </span>

                            <div style={{ flex: "0 0 200px" }}>
                                <div style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>{row.client_name}</div>
                                <div style={{ fontSize: "11px", color: "#94a3b8" }}>{row.client_id}</div>
                            </div>

                            <div style={{ flex: "1 1 auto", minWidth: 0 }}>
                                {row.signals.length === 0 ? (
                                    <span style={{ fontSize: "12px", color: "#94a3b8" }}>No active signals.</span>
                                ) : (
                                    <span style={{ fontSize: "12px", color: "#475569", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
                                        {row.signals[0].title}
                                        {row.signals.length > 1 ? ` (+${row.signals.length - 1} more)` : ""}
                                    </span>
                                )}
                            </div>

                            <div style={{ flex: "0 0 auto", textAlign: "right", fontSize: "13px", fontWeight: 700, fontFamily: "monospace", color: "#0f172a" }}>
                                {formatCurrency(row.aum_usd_from_holdings)}
                            </div>

                            <ChevronRight size={16} color="#cbd5e1" />
                        </div>
                    ))}
                </div>

            </div>
        </div>
    );
}
