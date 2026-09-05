import { useEffect, useState } from "react";
import { Sparkles, Loader2, AlertCircle } from "lucide-react";

import { getAgentRun, generateAgentRun } from "../api/agentClient";
import type { AgentRun } from "../types";
import AgentMarkdown from "./AgentMarkdown";
import RecommendationsSection from "./RecommendationsSection";

interface Props {
    clientId: string;
}

// Explanation / Scenario / Recommendation -- the three LLM agents, each a
// report to read except Recommendation, which is a set of discrete,
// individually accept/edit/reject-able items (see RecommendationsSection).
export default function AiInsightsSection({ clientId }: Props) {
    const [activeTab, setActiveTab] = useState<"explanation" | "scenario" | "recommendation">("explanation");
    const [agentRuns, setAgentRuns] = useState<Record<string, AgentRun>>({});
    const [agentLoading, setAgentLoading] = useState(false);
    const [agentError, setAgentError] = useState<string | null>(null);

    useEffect(() => {
        if (activeTab === "recommendation") return;
        async function loadAgent() {
            if (agentRuns[activeTab]) return;
            try {
                const run = await getAgentRun(clientId, activeTab);
                setAgentRuns((prev) => ({ ...prev, [activeTab]: run }));
            } catch {
                // Run has not been executed yet
            }
        }
        loadAgent();
    }, [clientId, activeTab]);

    async function handleGenerate() {
        setAgentLoading(true);
        setAgentError(null);
        try {
            const run = await generateAgentRun(clientId, activeTab);
            setAgentRuns((prev) => ({ ...prev, [activeTab]: run }));
        } catch (err) {
            setAgentError(err instanceof Error ? err.message : "Failed to generate run.");
        } finally {
            setAgentLoading(false);
        }
    }

    const currentRun = agentRuns[activeTab];

    return (
        <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)", overflow: "hidden" }}>

            <div style={{ padding: "16px 20px", borderBottom: "1px solid #e2e8f0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", gap: "6px" }}>
                    {(["explanation", "scenario", "recommendation"] as const).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            style={{
                                fontSize: "12px",
                                fontWeight: 600,
                                padding: "5px 12px",
                                borderRadius: "5px",
                                border: "none",
                                cursor: "pointer",
                                textTransform: "capitalize",
                                background: activeTab === tab ? "#0f172a" : "#f1f5f9",
                                color: activeTab === tab ? "#ffffff" : "#475569",
                            }}
                        >
                            {tab}
                        </button>
                    ))}
                </div>

                {activeTab !== "recommendation" && (
                    <button
                        onClick={handleGenerate}
                        disabled={agentLoading}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                            background: "#0f172a",
                            color: "#ffffff",
                            fontSize: "12px",
                            fontWeight: 600,
                            padding: "7px 14px",
                            borderRadius: "5px",
                            border: "none",
                            cursor: agentLoading ? "not-allowed" : "pointer",
                            opacity: agentLoading ? 0.6 : 1,
                            boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
                        }}
                    >
                        {agentLoading ? (
                            <>
                                <Loader2 className="animate-spin" size={13} />
                                <span>Running Agent...</span>
                            </>
                        ) : (
                            <>
                                <Sparkles size={13} color="#fcd34d" />
                                <span>{currentRun?.available ? "Regenerate" : "Generate"}</span>
                            </>
                        )}
                    </button>
                )}
            </div>

            <div style={{ padding: "20px" }}>
                {activeTab === "recommendation" ? (
                    <RecommendationsSection clientId={clientId} />
                ) : (
                    <>
                        {agentError && (
                            <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", padding: "10px 14px", borderRadius: "6px", fontSize: "12px", display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
                                <AlertCircle size={15} />
                                <span>{agentError}</span>
                            </div>
                        )}

                        {currentRun?.available && currentRun?.output?.answer ? (
                            <AgentMarkdown content={currentRun.output.answer} />
                        ) : (
                            <div style={{ textAlign: "center", padding: "40px 16px", color: "#94a3b8", fontSize: "13px" }}>
                                <Sparkles size={32} color="#cbd5e1" style={{ margin: "0 auto 10px auto", display: "block" }} />
                                <p style={{ margin: 0, fontWeight: 500 }}>No output available for this agent view.</p>
                                <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#64748b" }}>Click <strong>Generate</strong> to execute the agent pipeline.</p>
                            </div>
                        )}
                    </>
                )}
            </div>

        </div>
    );
}
