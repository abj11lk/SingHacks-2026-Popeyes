import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Search, AlertTriangle, LayoutDashboard } from "lucide-react";

import { getClients } from "../api/client";
import type { Client } from "../types";
import { formatCompactNumber, formatWealthBand } from "../lib/format";

interface LayoutProps {
    children: ReactNode;
}

// The sidebar IS the book overview -- every client, always visible, search
// on top -- rather than a separate "Radar" page you navigate away from and
// back to. Clicking a name just swaps what's in the main panel.
export default function Layout({ children }: LayoutProps) {
    const [clients, setClients] = useState<Client[]>([]);
    const [search, setSearch] = useState("");

    useEffect(() => {
        getClients()
            .then((result) => setClients(result.clients))
            .catch(() => {
                // Non-fatal: the sidebar list just stays empty.
            });
    }, []);

    const sorted = [...clients].sort((a, b) => a.client_id.localeCompare(b.client_id));

    const filtered = sorted.filter((client) => {
        const text = `${client.client_name} ${client.client_id}`.toLowerCase();
        return text.includes(search.toLowerCase());
    });

    return (
        <div className="app-shell">
            <aside className="sidebar">
                <Link to="/" className="brand" style={{ color: "inherit", textDecoration: "none" }}>
                    <div className="brand-mark">NB</div>
                    <div>
                        <div className="brand-title">North Bear</div>
                        <div className="brand-subtitle">RM Decision Support</div>
                    </div>
                </Link>

                <nav className="sidebar-nav" style={{ marginBottom: "14px" }}>
                    <NavLink
                        to="/"
                        end
                        className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
                    >
                        <LayoutDashboard size={16} />
                        <span>Dashboard</span>
                    </NavLink>
                </nav>

                <div className="sidebar-search">
                    <Search size={15} />
                    <input
                        placeholder="Search clients..."
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                    />
                </div>

                <nav className="sidebar-client-list">
                    {filtered.map((client) => {
                        const flagCount = [
                            client.mandate_breach_flag,
                            client.ltv_breach_flag,
                            client.upcoming_cash_need_90d_flag,
                        ].filter(Boolean).length;

                        return (
                            <NavLink
                                key={client.client_id}
                                to={`/client/${encodeURIComponent(client.client_id)}`}
                                className={({ isActive }) =>
                                    `sidebar-client-item ${isActive ? "active" : ""}`
                                }
                            >
                                <div className="sidebar-client-top">
                                    <span className="sidebar-client-name">{client.client_name}</span>
                                    {flagCount > 0 ? (
                                        <span className="sidebar-client-status flagged">
                                            <AlertTriangle size={11} />
                                            {flagCount}
                                        </span>
                                    ) : (
                                        <span className="sidebar-client-status clear">Clear</span>
                                    )}
                                </div>

                                <div className="sidebar-client-id">{client.client_id}</div>

                                <div className="sidebar-client-meta">
                                    {client.wealth_band && (
                                        <span className="sidebar-client-tag">{formatWealthBand(client.wealth_band)}</span>
                                    )}
                                    {client.risk_profile && (
                                        <span className="sidebar-client-tag">{client.risk_profile}</span>
                                    )}
                                </div>

                                <div className="sidebar-client-foot">
                                    <span>${formatCompactNumber(client.aum_usd_from_holdings)}</span>
                                    {client.kyc_review_due && (
                                        <span>KYC due {client.kyc_review_due}</span>
                                    )}
                                </div>
                            </NavLink>
                        );
                    })}

                    {clients.length > 0 && filtered.length === 0 && (
                        <div className="sidebar-client-empty">No clients match "{search}".</div>
                    )}
                </nav>

                <div className="sidebar-footer">
                    <div className="rm-profile">
                        <div className="rm-avatar">PO</div>
                        <div>
                            <div className="rm-name">Priscilla Ong</div>
                            <div className="rm-role">Relationship Manager</div>
                        </div>
                    </div>
                </div>
            </aside>

            <main className="main-content">{children}</main>
        </div>
    );
}
