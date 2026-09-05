import Link from "next/link";
import { listClients } from "@/lib/api";
import { formatUsd } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default async function BookOverviewPage() {
  const clients = await listClients();
  const sorted = [...clients].sort((a, b) => b.aum_usd_from_holdings - a.aum_usd_from_holdings);
  const totalAum = clients.reduce((sum, c) => sum + c.aum_usd_from_holdings, 0);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Book Overview</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Priscilla Ong &middot; Asia desk &middot; {clients.length} clients &middot;{" "}
            {formatUsd(totalAum)} total AUM
          </p>
        </div>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Client</TableHead>
              <TableHead>Booking Centre</TableHead>
              <TableHead>Risk Profile</TableHead>
              <TableHead className="text-right">AUM</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((c) => (
              <TableRow key={c.client_id}>
                <TableCell>
                  <Link
                    href={`/clients/${c.client_id}`}
                    className="font-medium hover:underline"
                  >
                    {c.client_name}
                  </Link>
                  <div className="text-muted-foreground text-xs">{c.client_id}</div>
                </TableCell>
                <TableCell className="text-muted-foreground">{c.booking_centre}</TableCell>
                <TableCell className="text-muted-foreground">{c.risk_profile}</TableCell>
                <TableCell className="text-right tabular-nums font-medium">
                  {formatUsd(c.aum_usd_from_holdings)}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1.5">
                    <Badge
                      variant={c.mandate_breach_flag ? "destructive" : "secondary"}
                      className="text-xs"
                    >
                      {c.mandate_breach_flag ? "Mandate breach" : "Mandate ok"}
                    </Badge>
                    {c.ltv_breach_flag && (
                      <Badge variant="destructive" className="text-xs">
                        LTV breach
                      </Badge>
                    )}
                    {c.upcoming_cash_need_90d_flag && (
                      <Badge variant="outline" className="text-xs">
                        Cash need 90d
                      </Badge>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </main>
  );
}
