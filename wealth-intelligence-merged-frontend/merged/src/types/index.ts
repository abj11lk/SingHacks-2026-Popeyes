// ============================================================
// Core Enums & Base Types
// ============================================================

export type Priority =
    | "CRITICAL"
    | "HIGH"
    | "MEDIUM"
    | "LOW";

export interface Client {
    client_id: string;
    client_name: string;
    wealth_band?: string;
    risk_profile?: string;
    booking_centre?: string;

    aum_usd_from_holdings?: number;
    aum_usd_client_record?: number;

    kyc_review_due?: string;

    mandate_breach_flag?: boolean;
    ltv_breach_flag?: boolean;
    upcoming_cash_need_90d_flag?: boolean;
}

export interface ClientProfile {
    client_id: string;
    client_name: string;
    age: number;
    gender: string;
    nationality: string;
    country_of_residence: string;
    tax_domicile: string;
    booking_centre: string;
    rm_name: string;
    base_currency: string;
    wealth_band: string;
    life_stage: string;
    source_of_wealth: string;
    risk_profile: string;
    risk_tolerance_score: number;
    investment_horizon_years: number;
    liquidity_needs: string;
    objectives: string;
    kyc_review_due: string;
}

// ============================================================
// Portfolio & Holdings
// ============================================================

export interface MandateBreach {
    asset_class?: string;
    instrument_name?: string;
    [key: string]: unknown;
}

export interface Portfolio {
    portfolio_id: string;
    portfolio_name: string;
    service_model: string;
    mandate_name?: string;

    aum_usd_from_holdings: number;

    mandate_status: "within_mandate" | "breach" | "not_applicable" | "unknown" | string;
    mandate_breaches: MandateBreach[] | any[];
}

export interface Holding {
    instrument_id: string;
    instrument_name: string;
    asset_class: string;
    sub_asset_class?: string;

    market_value_usd: number;
    weight_pct: number;

    liquidity_tier?: string;
    unrealised_pnl_pct?: number | null;
}

export interface RmNote {
    note_id: string;
    note_date: string;
    channel: string;
    note: string;
}

export interface CashNeed {
    need_id: string;
    description: string;
    currency: string;
    amount: number;
    due_from: string;
    due_to: string;
}

// ============================================================
// Liquidity & Lookthrough Concentration
// ============================================================

export interface LiquidityTier {
    liquidity_tier: string;
    market_value_usd: number;
    pct_of_portfolio: number;
    cumulative_sellable_pct: number;
}

export interface Liquidity {
    total_market_value_usd: number;
    tier_breakdown: LiquidityTier[];
    credit_facility_headroom_usd: number;
    near_term_cash_needs_usd_only: number;
}

export interface ConcentrationInstrument {
    instrument_id: string;
    instrument_name: string;
    weight_pct: number;
}

export interface ConcentrationTheme {
    label_guess: string;
    instruments: ConcentrationInstrument[];
    combined_market_value_usd: number;
    combined_pct_of_client_aum: number;
}

export interface Lookthrough {
    candidate_concentration_themes: ConcentrationTheme[];
}

// ============================================================
// Mandate Compliance (actual vs. target band per asset class)
// ============================================================

export interface AssetClassBand {
    asset_class: string;
    actual_pct: number;
    min_pct: number;
    target_pct: number;
    max_pct: number;
    breach: boolean;
    drift_vs_target_pct: number;
}

export interface MandateBreachDetail {
    portfolio_id: string;
    mandate_name?: string;
    status: "within_mandate" | "breach" | "not_applicable" | "unknown" | string;
    asset_class_detail?: AssetClassBand[];
    reason?: string;
}

// ============================================================
// AUM Trend
// ============================================================

export interface AumTrendPoint {
    as_of: string;
    aum_usd: number;
}

export interface AumTrend {
    client_id: string;
    points: AumTrendPoint[];
}

// ============================================================
// Snapshot & Client Workspace
// ============================================================

export interface ClientSnapshot {
    client_id: string;
    as_of: string;

    profile: ClientProfile | Client;

    portfolios: Portfolio[];

    aum_usd_from_holdings_all_portfolios: number;
    aum_usd_client_record?: number;

    holdings: Holding[];

    credit_facilities: any[];
    commitments?: any[];
    planned_cash_needs: CashNeed[] | any[];

    notes: RmNote[] | any[];

    sources?: Record<string, any>;
    daily_liquid_usd?: number;
}

export interface ClientWorkspace {
    snapshot: ClientSnapshot;
    liquidity: Liquidity;
    lookthrough: Lookthrough;
    mandate_breach_by_portfolio: Record<string, MandateBreachDetail>;
}

// ============================================================
// Agent Execution Runs
// ============================================================

export interface AgentRun {
    available: boolean;
    output?: { answer: string };
    model?: string;
    created_at?: string;
    langsmith_trace_url?: string | null;
    recommendations?: Recommendation[];
}

// ============================================================
// Prioritisation ("twenty clients, one RM, who calls first")
// ============================================================

export interface PrioritySignal {
    type: string;
    title: string;
    detail: string;
    score: number;
    portfolio_id?: string | null;
    portfolio_name?: string | null;
}

export type PriorityLabel = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "CLEAR";

export interface PriorityRow {
    client_id: string;
    client_name: string;
    aum_usd_from_holdings: number;
    score: number;
    priority: PriorityLabel;
    signals: PrioritySignal[];
}

export interface PrioritiesResponse {
    as_of: string;
    book: PriorityRow[];
}

// ============================================================
// Recommendations & Actions
// ============================================================

export interface Recommendation {
    id?: string;
    client_id?: string;
    signal_id?: string;

    title: string;
    issue?: string;

    recommendation?: string;
    rationale: string;

    priority?: Priority;
    priority_score?: number;

    status?: "pending" | "accepted" | "edited" | "rejected" | string;
    created_at?: string;
    updated_at?: string;

    evidence?: any[];
    source?: string;
    as_of?: string;
    heuristic?: boolean;
    requires_rm_review?: boolean;
}

