import Link from "next/link";
import { notFound } from "next/navigation";
import { getAgentRun, getClientWorkspace, listRecommendations } from "@/lib/api";
import { formatUsd, formatPct, daysUntil } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AgentPanel } from "@/components/agent-panel";
import { RecommendationPanel } from "@/components/recommendation-panel";

function mandateBadge(status: string) {
  if (status === "breach") return <Badge variant="destructive">Breach</Badge>;
  if (status === "within_mandate") return <Badge variant="secondary">Within mandate</Badge>;
  if (status === "not_applicable") return <Badge variant="outline">Custody (n/a)</Badge>;
  return <Badge variant="outline">Unknown</Badge>;
}

function kycBadge(dueDate: string) {
  const days = daysUntil(dueDate);
  if (days < 0) return <Badge variant="destructive">KYC overdue</Badge>;
  if (days <= 60) return <Badge className="bg-amber-500 text-white">KYC due in {days}d</Badge>;
  return null;
}

const TIER_COLORS: Record<string, string> = {
  Daily: "bg-emerald-500",
  Weekly: "bg-lime-500",
  Monthly: "bg-amber-500",
  "Quarterly Gate": "bg-orange-500",
  Illiquid: "bg-red-500",
};


export default async function ClientWorkspacePage({
  params,
}: {
  params: Promise<{ clientId: string }>;
}) {
  const { clientId } = await params;

  let workspace;
  try {
    workspace = await getClientWorkspace(clientId);
  } catch {
    notFound();
  }

  const { snapshot, liquidity, lookthrough } = workspace;
  const { profile, portfolios, notes, planned_cash_needs: cashNeeds } = snapshot;

  const explanation = await getAgentRun(clientId, "explanation");
  const scenario = await getAgentRun(clientId, "scenario");
  const recommendations = await listRecommendations(clientId);

  const topTheme = lookthrough.candidate_concentration_themes[0];

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <Link href="/" className="text-sm text-muted-foreground hover:underline">
        ← Book overview
      </Link>

      {/* Header */}
      <div className="mt-3 mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{profile.client_name}</h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge variant="outline">{profile.wealth_band}</Badge>
            <Badge variant="outline">{profile.booking_centre}</Badge>
            <Badge variant="outline">{profile.risk_profile}</Badge>
            {kycBadge(profile.kyc_review_due)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold tabular-nums">
            {formatUsd(snapshot.aum_usd_from_holdings_all_portfolios)}
          </div>
          <div className="text-xs text-muted-foreground">as of {snapshot.as_of}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Essentials */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Profile</CardTitle>
            </CardHeader>
            <CardContent className="text-sm space-y-2">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                <div><span className="text-muted-foreground">Age</span> {profile.age}</div>
                <div><span className="text-muted-foreground">Life stage</span> {profile.life_stage}</div>
                <div><span className="text-muted-foreground">Tax domicile</span> {profile.tax_domicile}</div>
                <div><span className="text-muted-foreground">Residence</span> {profile.country_of_residence}</div>
                <div><span className="text-muted-foreground">Horizon</span> {profile.investment_horizon_years}y</div>
                <div><span className="text-muted-foreground">Liquidity need</span> {profile.liquidity_needs}</div>
              </div>
              <Separator className="my-2" />
              <div>
                <span className="text-muted-foreground">Source of wealth</span>
                <p className="mt-0.5">{profile.source_of_wealth}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Objectives</span>
                <p className="mt-0.5 italic">&ldquo;{profile.objectives}&rdquo;</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Portfolios</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {portfolios.map((p) => (
                <div key={p.portfolio_id} className="flex items-center justify-between rounded-md border p-3">
                  <div>
                    <div className="font-medium text-sm">{p.portfolio_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {p.mandate_name} &middot; {p.service_model} &middot; {formatUsd(p.aum_usd_from_holdings)}
                    </div>
                  </div>
                  <div className="text-right">
                    {mandateBadge(p.mandate_status)}
                    {p.mandate_breaches.length > 0 && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {p.mandate_breaches.length} issue{p.mandate_breaches.length > 1 ? "s" : ""}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">RM Notes</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[...notes].reverse().map((n) => (
                <div key={n.note_id} className="text-sm">
                  <div className="text-xs text-muted-foreground">
                    {n.note_date} &middot; {n.channel}
                  </div>
                  <p className="mt-0.5">{n.note}</p>
                </div>
              ))}
              {notes.length === 0 && (
                <p className="text-sm text-muted-foreground">No notes on file.</p>
              )}
            </CardContent>
          </Card>

          {cashNeeds.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Planned Cash Needs</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {cashNeeds.map((c) => (
                  <div key={c.need_id} className="flex justify-between text-sm">
                    <span>{c.description}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {c.currency} {c.amount.toLocaleString()} &middot; due {c.due_from}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Risk & Liquidity */}
        <div className="space-y-6">
          {topTheme && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Concentration</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-semibold tabular-nums">
                  {formatPct(topTheme.combined_pct_of_client_aum)}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  of AUM across {topTheme.instruments.length} instruments referencing the same
                  underlying exposure
                </p>
                <ul className="mt-3 space-y-1 text-xs">
                  {topTheme.instruments.map((i, idx) => (
                    <li key={`${i.instrument_id}-${idx}`} className="flex justify-between">
                      <span className="truncate pr-2">{i.instrument_name}</span>
                      <span className="tabular-nums text-muted-foreground shrink-0">
                        {formatPct(i.weight_pct)}
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Liquidity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex h-3 w-full overflow-hidden rounded-full">
                {liquidity.tier_breakdown.map((t) => (
                  <div
                    key={t.liquidity_tier}
                    className={TIER_COLORS[t.liquidity_tier] ?? "bg-gray-400"}
                    style={{ width: `${t.pct_of_portfolio}%` }}
                    title={`${t.liquidity_tier}: ${formatPct(t.pct_of_portfolio)}`}
                  />
                ))}
              </div>
              <ul className="mt-3 space-y-1 text-xs">
                {liquidity.tier_breakdown
                  .filter((t) => t.pct_of_portfolio > 0)
                  .map((t) => (
                    <li key={t.liquidity_tier} className="flex justify-between">
                      <span className="flex items-center gap-1.5">
                        <span
                          className={`h-2 w-2 rounded-full ${TIER_COLORS[t.liquidity_tier] ?? "bg-gray-400"}`}
                        />
                        {t.liquidity_tier}
                      </span>
                      <span className="tabular-nums text-muted-foreground">
                        {formatPct(t.pct_of_portfolio)}
                      </span>
                    </li>
                  ))}
              </ul>
              {liquidity.credit_facility_headroom_usd > 0 && (
                <>
                  <Separator className="my-3" />
                  <div className="text-xs text-muted-foreground">
                    Facility headroom available:{" "}
                    <span className="font-medium text-foreground">
                      {formatUsd(liquidity.credit_facility_headroom_usd)}
                    </span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* AI Intelligence */}
      <div className="mt-8">
        <h2 className="text-base font-semibold mb-3">AI Intelligence</h2>
        <Tabs defaultValue="explanation">
          <TabsList>
            <TabsTrigger value="explanation">Explanation</TabsTrigger>
            <TabsTrigger value="scenario">Scenario</TabsTrigger>
            <TabsTrigger value="recommendation">Recommendation</TabsTrigger>
          </TabsList>
          <TabsContent value="explanation" keepMounted>
            <Card>
              <CardContent className="pt-6">
                <AgentPanel
                  clientId={clientId}
                  agentType="explanation"
                  label="Explanation"
                  initial={explanation}
                />
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="scenario" keepMounted>
            <Card>
              <CardContent className="pt-6">
                <AgentPanel
                  clientId={clientId}
                  agentType="scenario"
                  label="Scenario analysis"
                  initial={scenario}
                />
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="recommendation" keepMounted>
            <Card>
              <CardContent className="pt-6">
                <RecommendationPanel clientId={clientId} initial={recommendations} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
