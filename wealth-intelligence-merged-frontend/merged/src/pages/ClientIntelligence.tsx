import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Loader2, AlertCircle } from "lucide-react";

import { getClientWorkspace } from "../api/client";
import type { ClientWorkspace } from "../types";
import { formatCurrency, formatWealthBand } from "../lib/format";
import OverviewSection from "../components/OverviewSection";
import AiInsightsSection from "../components/AiInsightsSection";
import AnalyticsSection from "../components/AnalyticsSection";

const TOP_TABS = [
    { id: "overview", label: "Overview" },
    { id: "ai", label: "AI Insights" },
    { id: "analytics", label: "Analytics" },
] as const;
type TopTab = (typeof TOP_TABS)[number]["id"];

export default function ClientIntelligence() {
    const { clientId: routeClientId } = useParams<{ clientId: string }>();
    const clientId = routeClientId!;

    const [workspace, setWorkspace] = useState<ClientWorkspace | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [topTab, setTopTab] = useState<TopTab>("overview");

    useEffect(() => {
        async function loadData() {
            setLoading(true);
            setError(null);
            setWorkspace(null);
            setTopTab("overview");
            try {
                const data = await getClientWorkspace(clientId);
                setWorkspace(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load client workspace.");
            } finally {
                setLoading(false);
            }
        }
        loadData();
    }, [clientId]);

    if (loading) {
        return (
            <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f8fafc", fontFamily: "system-ui, -apple-system, sans-serif" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#475569", fontWeight: 500 }}>
                    <Loader2 className="animate-spin" size={20} />
                    <span>Loading client intelligence workspace...</span>
                </div>
            </div>
        );
    }

    if (error || !workspace) {
        return (
            <div style={{ minHeight: "100vh", padding: "40px", background: "#f8fafc", fontFamily: "system-ui, -apple-system, sans-serif" }}>
                <div style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c", padding: "16px", borderRadius: "8px", display: "flex", alignItems: "center", gap: "10px" }}>
                    <AlertCircle size={20} />
                    <span>{error || "No client workspace data found."}</span>
                </div>
            </div>
        );
    }

    const { snapshot } = workspace;
    const profile = snapshot.profile as any;

    return (
        <div style={{ minHeight: "100vh", background: "#f8fafc", color: "#0f172a", fontFamily: "system-ui, -apple-system, sans-serif", paddingBottom: "60px" }}>
            <div style={{ maxWidth: "1160px", margin: "0 auto", padding: "24px 20px" }}>

                {/* Hero Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", paddingBottom: "18px", marginBottom: "16px" }}>
                    <div>
                        <h1 style={{ fontSize: "28px", fontWeight: 800, color: "#020617", margin: "0 0 8px 0", letterSpacing: "-0.02em" }}>
                            {profile.client_name}
                        </h1>
                        <div style={{ display: "flex", gap: "8px" }}>
                            <span style={{ background: "#f1f5f9", color: "#334155", fontSize: "11px", fontWeight: 700, padding: "2px 8px", borderRadius: "4px", border: "1px solid #e2e8f0" }}>
                                {formatWealthBand(profile.wealth_band) || "—"}
                            </span>
                            <span style={{ background: "#fff1f2", color: "#e11d48", fontSize: "11px", fontWeight: 700, padding: "2px 8px", borderRadius: "4px", border: "1px solid #fecdd3" }}>
                                {profile.risk_profile || "—"}
                            </span>
                            <span style={{ background: "#eff6ff", color: "#2563eb", fontSize: "11px", fontWeight: 700, padding: "2px 8px", borderRadius: "4px", border: "1px solid #dbeafe" }}>
                                {profile.booking_centre}
                            </span>
                        </div>
                    </div>

                    <div style={{ textAlign: "right" }}>
                        <span style={{ display: "block", fontSize: "11px", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                            Total Client AUM
                        </span>
                        <span style={{ fontSize: "30px", fontWeight: 800, color: "#020617", fontFamily: "monospace", letterSpacing: "-0.03em" }}>
                            {formatCurrency(snapshot.aum_usd_from_holdings_all_portfolios)}
                        </span>
                    </div>
                </div>

                {/* Top-level tabs */}
                <div style={{ display: "flex", gap: "4px", borderBottom: "1px solid #e2e8f0", marginBottom: "20px" }}>
                    {TOP_TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setTopTab(tab.id)}
                            style={{
                                fontSize: "13px",
                                fontWeight: 600,
                                padding: "10px 16px",
                                border: "none",
                                borderBottom: topTab === tab.id ? "2px solid #0f172a" : "2px solid transparent",
                                background: "none",
                                cursor: "pointer",
                                color: topTab === tab.id ? "#0f172a" : "#94a3b8",
                                marginBottom: "-1px",
                            }}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                {topTab === "overview" && <OverviewSection workspace={workspace} />}
                {topTab === "ai" && <AiInsightsSection clientId={clientId} />}
                {topTab === "analytics" && <AnalyticsSection clientId={clientId} workspace={workspace} />}

            </div>
        </div>
    );
}
