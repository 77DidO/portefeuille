"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber } from "@/lib/format";
import { formatErrorDetail } from "@/lib/errors";

const COLORS = ["#1d4ed8", "#22c55e", "#f97316", "#6366f1"];

type Holding = {
  identifier: string;
  asset: string;
  symbol_or_isin?: string;
  quantity: number;
  pru_eur: number;
  invested_eur: number;
  market_price_eur: number;
  market_value_eur: number;
  pl_eur: number;
  pl_pct: number;
  type_portefeuille: string;
  as_of: string | null;
  account_id?: string | null;
};

type Summary = {
  total_value_eur: number;
  total_invested_eur: number;
  pnl_eur: number;
  pnl_pct: number;
};

type HoldingsApiResponse = {
  holdings: Array<
    Omit<Holding, "as_of"> & {
      as_of?: string | null;
    }
  >;
  summary: Summary;
};

type PnLResponse = {
  points: SnapshotPoint[];
};

type SnapshotPoint = {
  ts: string;
  value_total_eur: number;
  pnl_total_eur: number;
};

export default function DashboardPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const [holdingsRes, pnlRes] = await Promise.all([
          api.get<HoldingsApiResponse>("/portfolio/holdings"),
          api.get<PnLResponse>("/portfolio/pnl")
        ]);
        setHoldings(
          holdingsRes.data.holdings.map((holding) => ({
            ...holding,
            as_of: holding.as_of ?? null
          }))
        );
        setSummary(holdingsRes.data.summary);
        setSnapshots(pnlRes.data.points);
      } catch (err: any) {
        setError(formatErrorDetail(err.response?.data?.detail, "Erreur de chargement"));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const donutData = useMemo(() => {
    const groups: Record<string, number> = {
      "BTC & ETH": 0,
      Alts: 0,
      Cash: 0
    };

    holdings.forEach((holding) => {
      if (holding.type_portefeuille === "CRYPTO") {
        const symbol = (holding.symbol_or_isin ?? holding.asset).toUpperCase();
        if (symbol === "BTC" || symbol === "ETH") {
          groups["BTC & ETH"] += holding.market_value_eur;
        } else {
          groups.Alts += holding.market_value_eur;
        }
        return;
      }

      if (holding.asset.toUpperCase() === "EUR") {
        groups.Cash += holding.market_value_eur;
        return;
      }

      const key = holding.type_portefeuille.toUpperCase();
      groups[key] = (groups[key] ?? 0) + holding.market_value_eur;
    });

    return Object.entries(groups)
      .filter(([, value]) => value > 0)
      .map(([name, value]) => ({ name, value }));
  }, [holdings]);

  const lastUpdatedAt = useMemo(() => {
    let latest: string | null = null;
    let latestTimestamp = -Infinity;

    holdings.forEach((holding) => {
      if (!holding.as_of) {
        return;
      }
      const ts = new Date(holding.as_of).getTime();
      if (Number.isNaN(ts)) {
        return;
      }
      if (ts > latestTimestamp) {
        latestTimestamp = ts;
        latest = holding.as_of;
      }
    });

    return latest;
  }, [holdings]);

  const lastUpdatedLabel = lastUpdatedAt ? `Mise à jour ${formatDateTime(lastUpdatedAt)}` : "Date de mise à jour indisponible";

  return (
    <AppShell>
      <div className="space-y-8">
        {loading ? <p>Chargement…</p> : null}
        {error ? <p className="text-red-600">{error}</p> : null}
        {summary ? (
          <div className="grid gap-4 md:grid-cols-4">
            <Card title="Valeur totale" value={formatCurrency(summary.total_value_eur)} subtitle="EUR" />
            <Card title="P&L Global" value={formatCurrency(summary.pnl_eur)} subtitle={`${summary.pnl_pct.toFixed(2)} %`} />
            <Card title="Investi" value={formatCurrency(summary.total_invested_eur)} subtitle="Investi" />
            <Card
              title="Allocation Crypto"
              value={
                summary.total_value_eur
                  ? `${Math.round(
                      (holdings.filter((h) => h.type_portefeuille === "CRYPTO").reduce((acc, h) => acc + h.market_value_eur, 0) /
                        summary.total_value_eur) *
                        100
                    )}%`
                  : "0%"
              }
              subtitle="Crypto / Total"
            />
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="rounded-xl bg-white p-6 shadow lg:col-span-2">
            <h2 className="mb-4 text-lg font-semibold text-slate-700">Évolution du portefeuille</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={snapshots}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="ts" tickFormatter={(v) => new Date(v).toLocaleDateString()} />
                  <YAxis tickFormatter={(v) => `${v / 1000}k`} />
                  <Tooltip formatter={(value: number) => formatCurrency(value)} labelFormatter={(label) => new Date(label).toLocaleString("fr-FR")} />
                  <Line type="monotone" dataKey="value_total_eur" stroke="#6366f1" strokeWidth={2} dot={false} name="Valeur" />
                  <Line type="monotone" dataKey="pnl_total_eur" stroke="#10b981" strokeWidth={2} dot={false} name="P&L" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="rounded-xl bg-white p-6 shadow">
            <h2 className="mb-4 text-lg font-semibold text-slate-700">Allocation</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={donutData} innerRadius={60} outerRadius={90} dataKey="value">
                    {donutData.map((entry, index) => (
                      <Cell key={`cell-${entry.name}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => formatCurrency(value)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="mt-4 space-y-2 text-sm text-slate-600">
              {donutData.map((item, idx) => (
                <li key={item.name} className="flex items-center justify-between">
                  <span>
                    <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }}></span>
                    {item.name}
                  </span>
                  <span>{formatCurrency(item.value)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <section className="rounded-xl bg-white p-6 shadow">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="text-lg font-semibold text-slate-700">Positions</h2>
            <div className="text-sm text-slate-400 sm:text-right">
              <div>{holdings.length} positions</div>
              <div className="text-xs">{lastUpdatedLabel}</div>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <Th>Type</Th>
                  <Th>Actif</Th>
                  <Th>Quantité</Th>
                  <Th>PRU</Th>
                  <Th>Prix</Th>
                  <Th>Valeur</Th>
                  <Th>P&L</Th>
                  <Th>P&L %</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {holdings.map((holding) => (
                  <tr key={holding.identifier} className="hover:bg-slate-50">
                    <Td>{holding.type_portefeuille}</Td>
                    <Td>
                      <Link
                        href={`/positions/${encodeURIComponent(holding.identifier)}`}
                        className="font-medium text-indigo-600 hover:underline"
                      >
                        {holding.symbol_or_isin ?? holding.asset}
                      </Link>
                    </Td>
                    <Td>{holding.quantity.toFixed(4)}</Td>
                    <Td>{formatCurrency(holding.pru_eur)}</Td>
                    <Td>{formatCurrency(holding.market_price_eur)}</Td>
                    <Td>{formatCurrency(holding.market_value_eur)}</Td>
                    <Td className={holding.pl_eur >= 0 ? "text-emerald-600" : "text-red-600"}>
                      <TrendValue value={holding.pl_eur} formatter={(val) => formatCurrency(val)} />
                    </Td>
                    <Td className={holding.pl_pct >= 0 ? "text-emerald-600" : "text-red-600"}>
                      <TrendValue value={holding.pl_pct} formatter={(val) => `${formatNumber(val)}%`} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function Card({ title, value, subtitle }: { title: string; value: string; subtitle: string }) {
  return (
    <div className="rounded-xl bg-white p-6 shadow">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-400">{subtitle}</p>
    </div>
  );
}

function TrendValue({ value, formatter }: { value: number; formatter: (value: number) => string }) {
  const isPositive = value >= 0;
  const icon = isPositive ? "▲" : "▼";
  const sign = isPositive ? "+" : "-";
  const formatted = formatter(Math.abs(value));

  return (
    <span className="inline-flex items-center gap-1 font-medium">
      <span aria-hidden="true">{icon}</span>
      <span className="sr-only">{isPositive ? "Hausse" : "Baisse"} : </span>
      <span>
        ({sign} {formatted})
      </span>
    </span>
  );
}

function Th({ children }: { children: ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</th>;
}

function Td({ children }: { children: ReactNode }) {
  return <td className="px-4 py-3 text-sm text-slate-700">{children}</td>;
}

