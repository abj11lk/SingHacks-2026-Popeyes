import type { ClientWorkspace } from "../types";
import { formatCurrency, formatPercent } from "../lib/format";

const TIER_COLORS = ["#10b981", "#f59e0b", "#ef4444", "#6d5ef1", "#94a3b8"];

interface Props {
    workspace: ClientWorkspace;
}

// The plain-data half of the client page -- profile, portfolios, liquidity,
// concentration, RM notes, planned cash needs. No AI involved; everything
// here is a direct read of get_client_snapshot / get_liquidity_map /
// get_lookthrough_exposure.
export default function OverviewSection({ workspace }: Props) {
    const { snapshot, liquidity, lookthrough } = workspace;
    const profile = snapshot.profile as any;
    const concentrationTheme = lookthrough?.candidate_concentration_themes?.[0];

    return (
        <>
            {/* Row 1: Profile & Concentration */}
            <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: "16px", marginBottom: "16px" }}>

                {/* Profile Card */}
                <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "18px 20px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)" }}>
                    <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 14px 0" }}>
                        Profile
                    </h2>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 20px", fontSize: "12px", marginBottom: "14px" }}>
                        <div>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Age</span>
                            <span style={{ fontWeight: 600, color: "#1e293b" }}>{profile.age}</span>
                        </div>
                        <div>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Life stage</span>
                            <span style={{ fontWeight: 600, color: "#1e293b" }}>{profile.life_stage || "—"}</span>
                        </div>
                        <div>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Tax domicile</span>
                            <span style={{ fontWeight: 600, color: "#1e293b" }}>{profile.tax_domicile}</span>
                        </div>
                        <div>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Residence</span>
                            <span style={{ fontWeight: 600, color: "#1e293b" }}>{profile.country_of_residence}</span>
                        </div>
                        <div>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Booking centre</span>
                            <span style={{ fontWeight: 600, color: "#1e293b" }}>{profile.booking_centre}</span>
                        </div>
                        <div>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Liquidity need</span>
                            <span style={{ fontWeight: 600, color: "#e11d48" }}>{profile.liquidity_needs || "—"}</span>
                        </div>
                    </div>

                    <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: "12px", fontSize: "12px" }}>
                        <div style={{ marginBottom: "8px" }}>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Source of wealth</span>
                            <span style={{ color: "#334155", fontWeight: 500 }}>{profile.source_of_wealth}</span>
                        </div>
                        <div>
                            <span style={{ color: "#94a3b8", display: "block", marginBottom: "2px" }}>Objectives</span>
                            <p style={{ margin: 0, fontStyle: "italic", color: "#334155", background: "#f8fafc", padding: "8px 10px", borderRadius: "6px", border: "1px solid #f1f5f9" }}>
                                "{profile.objectives}"
                            </p>
                        </div>
                    </div>
                </div>

                {/* Concentration Card */}
                <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "18px 20px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)" }}>
                    <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 8px 0" }}>
                        Concentration
                    </h2>
                    <div style={{ fontSize: "30px", fontWeight: 800, color: "#020617", fontFamily: "monospace", margin: "0 0 4px 0" }}>
                        {concentrationTheme ? `${concentrationTheme.combined_pct_of_client_aum.toFixed(1)}%` : "0.0%"}
                    </div>
                    <p style={{ fontSize: "12px", color: "#64748b", margin: "0 0 14px 0", lineHeight: 1.45 }}>
                        {concentrationTheme
                            ? "of client AUM is concentrated in instruments referencing the same underlying theme."
                            : "No cross-instrument concentration theme detected for this client."}
                    </p>

                    {concentrationTheme && (
                        <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                            {concentrationTheme.instruments?.map((inst, idx) => (
                                <div key={`${inst.instrument_id}-${idx}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12px" }}>
                                    <span style={{ color: "#334155", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "210px" }}>
                                        {inst.instrument_name}
                                    </span>
                                    <span style={{ fontWeight: 700, fontFamily: "monospace", color: "#020617" }}>
                                        {formatPercent(inst.weight_pct)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

            </div>

            {/* Row 2: Portfolios & Liquidity */}
            <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: "16px", marginBottom: "16px" }}>

                {/* Portfolios Card */}
                <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "18px 20px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)" }}>
                    <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 14px 0" }}>
                        Portfolios
                    </h2>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {snapshot.portfolios?.map((port) => (
                            <div
                                key={port.portfolio_id}
                                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", background: "#f8fafc", border: "1px solid #f1f5f9", borderRadius: "6px" }}
                            >
                                <div>
                                    <strong style={{ fontSize: "13px", color: "#0f172a", display: "block" }}>{port.portfolio_name}</strong>
                                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>{port.portfolio_id} · {port.service_model}</span>
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                                    <span style={{ fontSize: "13px", fontWeight: 700, fontFamily: "monospace", color: "#0f172a" }}>
                                        {formatCurrency(port.aum_usd_from_holdings)}
                                    </span>
                                    <span
                                        style={{
                                            fontSize: "10px",
                                            fontWeight: 700,
                                            padding: "2px 7px",
                                            borderRadius: "4px",
                                            textTransform: "uppercase",
                                            letterSpacing: "0.04em",
                                            background: port.mandate_status === "breach" ? "#fee2e2" : "#dcfce7",
                                            color: port.mandate_status === "breach" ? "#b91c1c" : "#15803d",
                                            border: `1px solid ${port.mandate_status === "breach" ? "#fca5a5" : "#86efac"}`
                                        }}
                                    >
                                        {port.mandate_status || "within mandate"}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Liquidity Card -- tier_breakdown/totals come straight from
                    get_liquidity_map, no placeholder numbers */}
                <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "18px 20px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)" }}>
                    <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 14px 0" }}>
                        Liquidity
                    </h2>

                    <div style={{ width: "100%", height: "9px", background: "#f1f5f9", borderRadius: "9999px", display: "flex", overflow: "hidden", marginBottom: "10px" }}>
                        {liquidity?.tier_breakdown?.map((tier, idx) => (
                            <div
                                key={tier.liquidity_tier}
                                style={{ width: `${tier.pct_of_portfolio}%`, background: TIER_COLORS[idx % TIER_COLORS.length] }}
                                title={`${tier.liquidity_tier}: ${tier.pct_of_portfolio.toFixed(1)}%`}
                            />
                        ))}
                    </div>

                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 14px", fontSize: "11px", color: "#64748b", marginBottom: "16px" }}>
                        {liquidity?.tier_breakdown?.map((tier, idx) => (
                            <span key={tier.liquidity_tier} style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                                <span style={{ width: "7px", height: "7px", borderRadius: "50%", background: TIER_COLORS[idx % TIER_COLORS.length] }} />
                                {tier.liquidity_tier}: {tier.pct_of_portfolio.toFixed(1)}%
                            </span>
                        ))}
                    </div>

                    <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: "12px", display: "flex", flexDirection: "column", gap: "8px", fontSize: "12px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <span style={{ color: "#64748b" }}>Total sellable within 30 days:</span>
                            <span style={{ fontWeight: 700, fontFamily: "monospace", color: "#0f172a" }}>
                                {formatCurrency(liquidity?.total_market_value_usd)}
                            </span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <span style={{ color: "#64748b" }}>Facility headroom available:</span>
                            <span style={{ fontWeight: 700, fontFamily: "monospace", color: "#10b981" }}>
                                {formatCurrency(liquidity?.credit_facility_headroom_usd)}
                            </span>
                        </div>
                    </div>
                </div>

            </div>

            {/* Row 3: RM Notes */}
            <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "18px 20px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)", marginBottom: "16px" }}>
                <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 14px 0" }}>
                    RM Notes
                </h2>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    {snapshot.notes?.map((note: any) => (
                        <div key={note.note_id} style={{ borderLeft: "3px solid #cbd5e1", paddingLeft: "12px", fontSize: "12px" }}>
                            <div style={{ fontWeight: 700, color: "#1e293b", marginBottom: "2px" }}>
                                {note.note_date} — <span style={{ color: "#64748b", textTransform: "uppercase" }}>{note.channel}</span>
                            </div>
                            <p style={{ margin: 0, color: "#475569", lineHeight: 1.5 }}>{note.note}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Row 4: Planned Cash Needs */}
            {snapshot.planned_cash_needs && snapshot.planned_cash_needs.length > 0 && (
                <div style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px", padding: "18px 20px", boxShadow: "0 1px 2px rgba(0,0,0,0.04)" }}>
                    <h2 style={{ fontSize: "11px", fontWeight: 700, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 10px 0" }}>
                        Planned Cash Needs
                    </h2>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {snapshot.planned_cash_needs.map((need: any) => (
                            <div key={need.need_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "12px", padding: "10px 12px", borderRadius: "6px", background: "#f8fafc", border: "1px solid #e2e8f0" }}>
                                <div>
                                    <strong style={{ color: "#0f172a", display: "block" }}>{need.description}</strong>
                                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>Due: {need.due_from} to {need.due_to}</span>
                                </div>
                                <span style={{ fontWeight: 800, fontFamily: "monospace", color: "#020617" }}>
                                    {need.currency} {need.amount?.toLocaleString()}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </>
    );
}
