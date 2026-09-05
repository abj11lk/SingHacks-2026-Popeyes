const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ClientListRow {
  client_id: string;
  client_name: string;
  wealth_band: string;
  risk_profile: string;
  booking_centre: string;
  aum_usd_from_holdings: number;
  aum_usd_client_record: number;
  kyc_review_due: string;
  mandate_breach_flag: boolean;
  ltv_breach_flag: boolean;
  upcoming_cash_need_90d_flag: boolean;
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

export interface MandateBreach {
  asset_class?: string;
  instrument_name?: string;
  [key: string]: unknown;
}

export interface Portfolio {
  portfolio_id: string;
  portfolio_name: string;
  mandate_name: string;
  service_model: string;
  base_currency: string;
  aum_usd_from_holdings: number;
  mandate_status: "within_mandate" | "breach" | "not_applicable" | "unknown";
  mandate_breaches: MandateBreach[];
}

export interface Holding {
  instrument_id: string;
  instrument_name: string;
  asset_class: string;
  sub_asset_class: string;
  weight_pct: number;
  market_value_usd: number;
  liquidity_tier: string;
  unrealised_pnl_pct: number | null;
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

export interface ClientSnapshot {
  client_id: string;
  as_of: string;
  profile: ClientProfile;
  portfolios: Portfolio[];
  aum_usd_from_holdings_all_portfolios: number;
  holdings: Holding[];
  notes: RmNote[];
  planned_cash_needs: CashNeed[];
}

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

export interface ConcentrationTheme {
  label_guess: string;
  instruments: { instrument_id: string; instrument_name: string; weight_pct: number }[];
  combined_market_value_usd: number;
  combined_pct_of_client_aum: number;
}

export interface Lookthrough {
  candidate_concentration_themes: ConcentrationTheme[];
}

export interface ClientWorkspace {
  snapshot: ClientSnapshot;
  liquidity: Liquidity;
  lookthrough: Lookthrough;
}

export interface AgentRun {
  available: boolean;
  output?: { answer: string };
  model?: string;
  created_at?: string;
  langsmith_trace_url?: string | null;
  recommendations?: Recommendation[];
}

export interface Recommendation {
  id: string;
  client_id: string;
  title: string;
  rationale: string;
  status: "pending" | "accepted" | "edited" | "rejected";
  created_at: string;
  updated_at: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${path} -> HTTP ${res.status}`);
  }
  return res.json();
}

export function listClients(): Promise<ClientListRow[]> {
  return getJSON("/api/clients");
}

export function getClientWorkspace(clientId: string): Promise<ClientWorkspace> {
  return getJSON(`/api/clients/${clientId}`);
}

export function getAgentRun(clientId: string, agentType: string): Promise<AgentRun> {
  return getJSON(`/api/clients/${clientId}/agent-runs/${agentType}`);
}

// Runs the agent live -- called from the browser (Generate/Regenerate
// button), not during server rendering. Takes ~30-100s: a real Groq call,
// not a cache read.
export async function generateAgentRun(clientId: string, agentType: string): Promise<AgentRun> {
  const res = await fetch(`${API_URL}/api/clients/${clientId}/agent-runs/${agentType}/generate`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Generate failed: HTTP ${res.status}`);
  }
  return res.json();
}

export function listRecommendations(clientId: string): Promise<Recommendation[]> {
  return getJSON(`/api/clients/${clientId}/recommendations`);
}

export async function actOnRecommendation(
  recommendationId: string,
  action: "accepted" | "edited" | "rejected",
  opts?: { editedText?: string; note?: string },
): Promise<void> {
  const res = await fetch(`${API_URL}/api/recommendations/${recommendationId}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      edited_text: opts?.editedText ?? null,
      note: opts?.note ?? null,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Action failed: HTTP ${res.status}`);
  }
}
