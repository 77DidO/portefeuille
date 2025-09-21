"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { formatCurrency, formatDate, formatDateTime, formatNumber, formatPercentage } from "@/lib/format";
import { formatErrorDetail } from "@/lib/errors";

interface HistoryPoint {
  ts: string;
  quantity: number;
  invested_eur: number;
  market_price_eur: number;
  market_value_eur: number;
  pl_eur: number;
  pl_pct: number;
}

interface HoldingDetail {
  asset: string;
  symbol_or_isin?: string | null;
  quantity: number;
  pru_eur: number;
  invested_eur: number;
  market_price_eur: number;
  market_value_eur: number;
  pl_eur: number;
  pl_pct: number;
  type_portefeuille: string;
  as_of: string;
  history: HistoryPoint[];
  realized_pnl_eur: number;
  dividends_eur: number;
  history_available: boolean;
}

export default function PositionDetailPage() {
  const params = useParams<{ id: string }>();
  const rawId = params?.id;
  const identifier = Array.isArray(rawId) ? rawId[0] : rawId ?? "";
  const decodedId = decodeURIComponent(identifier);

  const { token, expiresAt } = useRequireAuth();
  const [detail, setDetail] = useState<HoldingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      if (!decodedId) {
        setDetail(null);
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const { data } = await api.get<HoldingDetail>(
          `/portfolio/holdings/${encodeURIComponent(decodedId)}`
        );
        if (!active) return;
        setDetail(data);
        setError(null);
      } catch (err: any) {
        if (!active) return;
        setError(formatErrorDetail(err.response?.data?.detail, "Impossible de charger la position"));
        setDetail(null);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [decodedId, token, expiresAt]);

  const historyData = useMemo(() => {
    if (!detail?.history?.length) {
      return [];
    }
    return detail.history.map((point) => ({
      ...point,
      dateLabel: formatDate(point.ts),
    }));
  }, [detail]);

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex flex-col gap-2">
          <Link href="/" className="text-sm text-indigo-600 hover:underline">
            ← Retour au tableau de bord
          </Link>
          <div>
            <h1 className="text-2xl font-semibold text-slate-800">
              {detail?.symbol_or_isin ?? decodedId || "Position"}
            </h1>
            {detail ? (
              <p className="text-sm text-slate-500">
                {detail.asset} • {detail.type_portefeuille} • Mise à jour {formatDateTime(detail.as_of)}
              </p>
            ) : null}
          </div>
        </div>

        {loading ? <p>Chargement…</p> : null}
        {error ? <p className="text-red-600">{error}</p> : null}

        {detail ? (
          <div className="space-y-8">
            <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <StatCard title="Prix actuel" value={formatCurrency(detail.market_price_eur)} subtitle="EUR" />
              <StatCard title="Valeur de la position" value={formatCurrency(detail.market_value_eur)} subtitle="EUR" />
              <StatCard
                title="P&L latent"
                value={formatCurrency(detail.pl_eur)}
                subtitle={formatPercentage(detail.pl_pct)}
                trend={detail.pl_eur}
              />
              <StatCard
                title="P&L réalisé"
                value={formatCurrency(detail.realized_pnl_eur)}
                subtitle="Depuis l'origine"
                trend={detail.realized_pnl_eur}
              />
            </section>

            <section className="rounded-xl bg-white p-6 shadow">
              <h2 className="text-lg font-semibold text-slate-700">Détails</h2>
              <dl className="mt-4 grid gap-4 md:grid-cols-3">
                <DetailItem label="Quantité" value={formatNumber(detail.quantity, 4)} />
                <DetailItem label="Investi" value={formatCurrency(detail.invested_eur)} />
                <DetailItem label="PRU" value={formatCurrency(detail.pru_eur)} />
                <DetailItem label="Dividendes" value={formatCurrency(detail.dividends_eur)} />
                <DetailItem label="Type de portefeuille" value={detail.type_portefeuille} />
                <DetailItem label="Symbole" value={detail.symbol_or_isin ?? "-"} />
              </dl>
            </section>

            <section className="rounded-xl bg-white p-6 shadow">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-700">Historique</h2>
                {detail.history_available ? (
                  <span className="text-sm text-slate-400">{detail.history.length} points</span>
                ) : null}
              </div>
              {historyData.length ? (
                <div className="space-y-6">
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={historyData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="dateLabel" />
                        <YAxis tickFormatter={(value) => `${Math.round(value / 100) / 10}k`} />
                        <Tooltip
                          formatter={(value: number) => formatCurrency(value)}
                          labelFormatter={(label: string) => label}
                        />
                        <Line type="monotone" dataKey="market_value_eur" stroke="#6366f1" strokeWidth={2} dot={false} name="Valeur" />
                        <Line type="monotone" dataKey="pl_eur" stroke="#10b981" strokeWidth={2} dot={false} name="P&L" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200 text-sm">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Date</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Prix</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Valeur</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Investi</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">P&L</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">P&L %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {historyData.map((point) => (
                          <tr key={point.ts}>
                            <td className="px-4 py-2 text-slate-700">{formatDate(point.ts)}</td>
                            <td className="px-4 py-2 text-slate-700">{formatCurrency(point.market_price_eur)}</td>
                            <td className="px-4 py-2 text-slate-700">{formatCurrency(point.market_value_eur)}</td>
                            <td className="px-4 py-2 text-slate-700">{formatCurrency(point.invested_eur)}</td>
                            <td className="px-4 py-2 text-slate-700">{formatCurrency(point.pl_eur)}</td>
                            <td className="px-4 py-2 text-slate-700">{formatPercentage(point.pl_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-500">
                  Aucun historique disponible pour cet actif pour le moment. L&rsquo;historique apparaîtra après la prochaine prise d&rsquo;instantané.
                </p>
              )}
            </section>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}

function StatCard({
  title,
  value,
  subtitle,
  trend,
}: {
  title: string;
  value: string;
  subtitle?: string;
  trend?: number;
}) {
  const isPositive = trend === undefined ? undefined : trend >= 0;
  return (
    <div className="rounded-xl bg-white p-6 shadow">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-800">{value}</p>
      {subtitle ? <p className="text-xs text-slate-400">{subtitle}</p> : null}
      {trend !== undefined ? (
        <p className={`mt-1 text-xs font-medium ${isPositive ? "text-emerald-600" : "text-red-600"}`}>
          {isPositive ? "▲" : "▼"} {formatCurrency(trend)}
        </p>
      ) : null}
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-4">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-700">{value}</dd>
    </div>
  );
}
