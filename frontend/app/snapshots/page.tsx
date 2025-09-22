"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from "recharts";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatSignedCurrency,
  fromDateTimeLocalInput
} from "@/lib/format";
import { formatErrorDetail } from "@/lib/errors";

export default function SnapshotsPage() {
  const [snapshots, setSnapshots] = useState<SnapshotResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rangeFrom, setRangeFrom] = useState("");
  const [rangeTo, setRangeTo] = useState("");
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  const chartData = useMemo(
    () =>
      snapshots.map((snapshot) => ({
        ...snapshot,
        value_other_eur: computeOtherValue(snapshot),
        date: formatDate(snapshot.ts)
      })),
    [snapshots]
  );

  const lastSnapshot = snapshots.at(-1) ?? null;
  const lastSnapshotOther =
    lastSnapshot !== null ? Math.max(0, computeOtherValue(lastSnapshot)) : null;

  async function refresh(filters?: { from?: string; to?: string }) {
    try {
      setLoading(true);
      const { data } = await api.get<SnapshotRangeResponse>("/snapshots/", {
        params: filters
      });
      setSnapshots(data.snapshots);
      setError(null);
    } catch (err: any) {
      setError(formatErrorDetail(err.response?.data?.detail, "Impossible de récupérer les snapshots"));
    } finally {
      setLoading(false);
    }
  }

  async function handleFilter(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const filters = {
      from: fromDateTimeLocalInput(rangeFrom),
      to: fromDateTimeLocalInput(rangeTo)
    };
    await refresh(filters);
  }

  async function handleReset() {
    setRangeFrom("");
    setRangeTo("");
    await refresh();
  }

  async function handleRunSnapshot() {
    setRunning(true);
    setRunStatus(null);
    setRunError(null);
    try {
      await api.post("/snapshots/run");
      setRunStatus("Snapshot lancé");
      const filters = {
        from: fromDateTimeLocalInput(rangeFrom),
        to: fromDateTimeLocalInput(rangeTo)
      };
      await refresh(filters);
    } catch (err: any) {
      setRunError(formatErrorDetail(err.response?.data?.detail, "Impossible de lancer un snapshot"));
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-slate-800">Snapshots</h1>
            <p className="text-sm text-slate-500">
              Historique des valorisations quotidiennes. Utilisez les filtres pour restreindre la plage de dates ou déclenchez un
              snapshot manuel.
            </p>
          </div>
          <div className="flex flex-col gap-2 text-sm lg:items-end">
            <button
              className="rounded bg-indigo-600 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              onClick={handleRunSnapshot}
              disabled={running}
            >
              {running ? "Exécution…" : "Lancer un snapshot"}
            </button>
            {runStatus ? <span className="text-emerald-600">{runStatus}</span> : null}
            {runError ? <span className="text-red-600">{runError}</span> : null}
          </div>
        </div>

        <section className="space-y-4 rounded-xl bg-white p-6 shadow">
          <h2 className="text-lg font-semibold text-slate-700">Filtrer</h2>
          <form onSubmit={handleFilter} className="grid gap-4 md:grid-cols-3">
            <div className="grid gap-2 text-sm">
              <label className="font-medium text-slate-600">De</label>
              <input
                type="datetime-local"
                className="rounded border border-slate-200 px-3 py-2"
                value={rangeFrom}
                onChange={(e) => setRangeFrom(e.target.value)}
              />
            </div>
            <div className="grid gap-2 text-sm">
              <label className="font-medium text-slate-600">À</label>
              <input
                type="datetime-local"
                className="rounded border border-slate-200 px-3 py-2"
                value={rangeTo}
                onChange={(e) => setRangeTo(e.target.value)}
              />
            </div>
            <div className="flex items-end gap-3">
              <button
                type="submit"
                className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white"
              >
                Appliquer
              </button>
              <button
                type="button"
                className="rounded border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:border-slate-300"
                onClick={handleReset}
              >
                Réinitialiser
              </button>
            </div>
          </form>
        </section>

        <section className="space-y-6 rounded-xl bg-white p-6 shadow">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
            <SummaryCard title="Dernier snapshot" value={lastSnapshot ? formatDateTime(lastSnapshot.ts) : "—"} />
            <SummaryCard
              title="Valeur totale"
              value={lastSnapshot ? formatCurrency(lastSnapshot.value_total_eur) : "—"}
            />
            <SummaryCard
              title="Valeur PEA"
              value={lastSnapshot ? formatCurrency(lastSnapshot.value_pea_eur) : "—"}
            />
            <SummaryCard
              title="Valeur Crypto"
              value={lastSnapshot ? formatCurrency(lastSnapshot.value_crypto_eur) : "—"}
            />
            <SummaryCard
              title="Valeur autres"
              value={
                lastSnapshotOther !== null ? formatCurrency(lastSnapshotOther) : "—"
              }
            />
            <SummaryCard
              title="P&L cumulée"
              value={lastSnapshot ? formatSignedCurrency(lastSnapshot.pnl_total_eur) : "—"}
            />
          </div>

          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ left: 12, right: 24 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis tickFormatter={(value) => `${Math.round(value / 1000)}k`} width={80} />
                <Tooltip
                  formatter={(value: number, name: string) => [formatCurrency(value), name]}
                  labelFormatter={(label) => label}
                />
                <Legend />
                <Line type="monotone" dataKey="value_total_eur" name="Valeur totale" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="pnl_total_eur" name="P&L" stroke="#10b981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {loading ? <p>Chargement…</p> : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {!loading && snapshots.length === 0 ? <p className="text-sm text-slate-500">Aucun snapshot sur la période.</p> : null}

          {snapshots.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <Th>Date</Th>
                    <Th>Valeur totale</Th>
                    <Th>Valeur PEA</Th>
                    <Th>Valeur Crypto</Th>
                    <Th>Valeur autres</Th>
                    <Th>P&L total</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {snapshots.map((snapshot) => (
                    <tr key={snapshot.ts} className="hover:bg-slate-50">
                      <Td>{formatDateTime(snapshot.ts)}</Td>
                      <Td>{formatCurrency(snapshot.value_total_eur)}</Td>
                      <Td>{formatCurrency(snapshot.value_pea_eur)}</Td>
                      <Td>{formatCurrency(snapshot.value_crypto_eur)}</Td>
                      <Td>{formatCurrency(Math.max(0, computeOtherValue(snapshot)))}</Td>
                      <Td>{formatSignedCurrency(snapshot.pnl_total_eur)}</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}

function SummaryCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-2 text-lg font-semibold text-slate-800">{value}</p>
    </div>
  );
}

function Th({ children }: { children: ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</th>;
}

function Td({ children }: { children: ReactNode }) {
  return <td className="px-4 py-3 text-sm text-slate-700">{children}</td>;
}

function computeOtherValue(snapshot: SnapshotResponse): number {
  return (
    snapshot.value_total_eur - snapshot.value_pea_eur - snapshot.value_crypto_eur
  );
}

type SnapshotResponse = {
  ts: string;
  value_pea_eur: number;
  value_crypto_eur: number;
  value_total_eur: number;
  pnl_total_eur: number;
};

type SnapshotRangeResponse = {
  snapshots: SnapshotResponse[];
};
