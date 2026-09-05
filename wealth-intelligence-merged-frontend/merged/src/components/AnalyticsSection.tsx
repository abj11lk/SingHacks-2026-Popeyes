import { useEffect, useMemo, useState } from "react";
import {
    PieChart,
    Pie,
    Cell,
    LineChart,
    Line,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from "recharts";
import { Loader2 } from "lucide-react";

import { getAumTrend } from "../api/client";
import type { ClientWorkspace, AumTrendPoint } from "../types";
import { formatCurrency, formatCompactNumber } from "../lib/format";

const CARD_STYLE: React.CSSProperties = {
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "8px",
    padding: "18px 20px",
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
};

const CARD_TITLE_STYLE: React.CSSProperties = {
    fontSize: "11px",
    fontWeight: 700,
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    margin: "0 0 14px 0",
};

const ASSET_CLASS_COLORS: Record<string, string> = {
    "Equity": "#6d5ef1",
    "Fixed Income": "#10b981",
    "Cash and Equivalents": "#94a3b8",
    "Alternatives": "#f59e0b",
    "Commodities": "#ef4444",
    "Structured Products": "#0ea5e9",
};
const FALLBACK_COLORS = ["#6d5ef1", "#10b981", "#f59e0b", "#ef4444", "#0ea5e9", "#94a3b8", "#ec4899"];

function colorFor(key: string, idx: number): string {
    return ASSET_CLASS_COLORS[key] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
}

interface Props {
    clientId: string;
    workspace: ClientWorkspace;
}

// Four charts, each backed by data we already compute deterministically
// (get_client_snapshot / check_mandate_breach / get_lookthrough_exposure) --
// only the AUM trend needed a new backend endpoint (five real snapshot
// dates, no interpolation). No chart here invents a number that isn't
// already produced by tools.py.
export default function AnalyticsSection({ clientId, workspace }: Props) {
    const { snapshot, lookthrough, mandate_breach_by_portfolio } = workspace;

    const [trend, setTrend] = useState<AumTrendPoint[] | null>(null);
    const [trendError, setTrendError] = useState<string | null>(null);

    useEffect(() => {
        setTrend(null);
        setTrendError(null);
        getAumTrend(clientId)
            .then((res) => setTrend(res.points))
            .catch((err) => setTrendError(err instanceof Error ? err.message : "Failed to load AUM trend."));
    }, [clientId]);

    const allocationData = useMemo(() => {
        const byClass = new Map<string, number>();
        for (const h of snapshot.holdings || []) {
            byClass.set(h.asset_class, (byClass.get(h.asset_class) || 0) + h.market_value_usd);
        }
        return Array.from(byClass.entries())
            .map(([asset_class, value]) => ({ asset_class, value }))
            .sort((a, b) => b.value - a.value);
    }, [snapshot.holdings]);

    const trendChartData = useMemo(
        () => (trend || []).map((p) => ({ ...p, label: p.as_of.slice(5) })),
        [trend]
    );

    const mandatePortfolios = useMemo(
        () =>
            Object.values(mandate_breach_by_portfolio || {}).filter(
                (m) => m.status !== "not_applicable" && m.asset_class_detail?.length
            ),
        [mandate_breach_by_portfolio]
    );

    const concentrationData = useMemo(
        () =>
            (lookthrough?.candidate_concentration_themes || []).map((theme, idx) => ({
                label: theme.label_guess || `Theme ${idx + 1}`,
                pct: theme.combined_pct_of_client_aum,
            })),
        [lookthrough]
    );

    return (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>

            {/* Asset Allocation */}
            <div style={CARD_STYLE}>
                <h2 style={CARD_TITLE_STYLE}>Asset Allocation</h2>
                {allocationData.length === 0 ? (
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>No holdings data.</div>
                ) : (
                    <ResponsiveContainer width="100%" height={240}>
                        <PieChart>
                            <Pie
                                data={allocationData}
                                dataKey="value"
                                nameKey="asset_class"
                                innerRadius={55}
                                outerRadius={90}
                                paddingAngle={2}
                            >
                                {allocationData.map((entry, idx) => (
                                    <Cell key={entry.asset_class} fill={colorFor(entry.asset_class, idx)} />
                                ))}
                            </Pie>
                            <Tooltip formatter={(value: any) => formatCurrency(value)} />
                            <Legend wrapperStyle={{ fontSize: "11px" }} />
                        </PieChart>
                    </ResponsiveContainer>
                )}
            </div>

            {/* AUM Trend */}
            <div style={CARD_STYLE}>
                <h2 style={CARD_TITLE_STYLE}>AUM Trend</h2>
                {trendError ? (
                    <div style={{ fontSize: "12px", color: "#b91c1c" }}>{trendError}</div>
                ) : !trend ? (
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#94a3b8", fontSize: "12px", padding: "40px 0", justifyContent: "center" }}>
                        <Loader2 className="animate-spin" size={16} />
                        Loading trend...
                    </div>
                ) : (
                    <ResponsiveContainer width="100%" height={240}>
                        <LineChart data={trendChartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `$${formatCompactNumber(v)}`} width={55} />
                            <Tooltip formatter={(value: any) => formatCurrency(value)} labelFormatter={(_, entry) => entry?.[0]?.payload?.as_of} />
                            <Line type="monotone" dataKey="aum_usd" stroke="#6d5ef1" strokeWidth={2} dot={{ r: 3 }} name="AUM (USD)" />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </div>

            {/* Mandate: Actual vs Target */}
            <div style={CARD_STYLE}>
                <h2 style={CARD_TITLE_STYLE}>Actual vs. Mandate Target</h2>
                {mandatePortfolios.length === 0 ? (
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>No mandate-managed portfolios for this client.</div>
                ) : (
                    mandatePortfolios.map((m) => (
                        <div key={m.portfolio_id} style={{ marginBottom: "18px" }}>
                            <div style={{ fontSize: "11px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                                {m.mandate_name || m.portfolio_id}
                            </div>
                            <ResponsiveContainer width="100%" height={Math.max(120, (m.asset_class_detail?.length || 0) * 34)}>
                                <BarChart
                                    data={m.asset_class_detail}
                                    layout="vertical"
                                    margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
                                >
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                    <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10 }} />
                                    <YAxis type="category" dataKey="asset_class" width={110} tick={{ fontSize: 10 }} />
                                    <Tooltip formatter={(value: any) => `${value}%`} />
                                    <Legend wrapperStyle={{ fontSize: "11px" }} />
                                    <Bar dataKey="target_pct" name="Target" fill="#cbd5e1" radius={[0, 3, 3, 0]} />
                                    <Bar dataKey="actual_pct" name="Actual" radius={[0, 3, 3, 0]}>
                                        {m.asset_class_detail!.map((row) => (
                                            <Cell key={row.asset_class} fill={row.breach ? "#ef4444" : "#6d5ef1"} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    ))
                )}
            </div>

            {/* Concentration Themes */}
            <div style={CARD_STYLE}>
                <h2 style={CARD_TITLE_STYLE}>Concentration Exposure</h2>
                {concentrationData.length === 0 ? (
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>No cross-instrument concentration themes detected.</div>
                ) : (
                    <ResponsiveContainer width="100%" height={Math.max(120, concentrationData.length * 40)}>
                        <BarChart data={concentrationData} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                            <XAxis type="number" tickFormatter={(v) => `${v}%`} tick={{ fontSize: 10 }} />
                            <YAxis type="category" dataKey="label" width={150} tick={{ fontSize: 10 }} />
                            <Tooltip formatter={(value: any) => `${value}% of client AUM`} />
                            <Bar dataKey="pct" name="% of client AUM" fill="#f59e0b" radius={[0, 3, 3, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                )}
            </div>

        </div>
    );
}
