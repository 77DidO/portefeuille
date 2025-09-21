"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import {
  formatDateTime,
  formatNumber,
  fromDateTimeLocalInput,
  toDateTimeLocalInput
} from "@/lib/format";
import { formatErrorDetail } from "@/lib/errors";

const EMPTY_FORM: TradeFormState = {
  asset: "",
  pair: "",
  setup: "",
  entry: "",
  sl: "",
  tp: "",
  risk_r: "",
  status: "open",
  result_r: "",
  opened_at: "",
  closed_at: "",
  notes: ""
};

const STATUS_OPTIONS = [
  { value: "open", label: "Ouverte" },
  { value: "closed", label: "Clôturée" },
  { value: "cancelled", label: "Annulée" }
];

export default function JournalPage() {
  const [trades, setTrades] = useState<JournalTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newTrade, setNewTrade] = useState<TradeFormState>({ ...EMPTY_FORM });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createStatus, setCreateStatus] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<TradeFormState>({ ...EMPTY_FORM });
  const [updating, setUpdating] = useState(false);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  const hasTrades = useMemo(() => trades.length > 0, [trades]);

  async function refresh() {
    try {
      setLoading(true);
      const { data } = await api.get<JournalTrade[]>("/journal/");
      setTrades(data);
      setError(null);
    } catch (err: any) {
      setError(formatErrorDetail(err.response?.data?.detail, "Impossible de charger le journal"));
    } finally {
      setLoading(false);
    }
  }

  function handleNewFieldChange<K extends keyof TradeFormState>(field: K, value: TradeFormState[K]) {
    setNewTrade((prev) => ({ ...prev, [field]: value }));
  }

  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCreateError(null);
    setCreateStatus(null);
    if (!newTrade.asset.trim() || !newTrade.pair.trim()) {
      setCreateError("Renseignez au minimum l'actif et la paire");
      return;
    }
    let payload: Record<string, unknown>;
    try {
      payload = buildPayload(newTrade);
    } catch (err: any) {
      setCreateError(err instanceof Error ? err.message : "Valeurs numériques invalides");
      return;
    }
    payload.asset = newTrade.asset.trim();
    payload.pair = newTrade.pair.trim();
    payload.status = newTrade.status;
    setCreating(true);
    try {
      await api.post("/journal/", payload);
      setCreateStatus("Trade ajouté");
      setNewTrade({ ...EMPTY_FORM });
      await refresh();
    } catch (err: any) {
      setCreateError(formatErrorDetail(err.response?.data?.detail, "Impossible d'ajouter le trade"));
    } finally {
      setCreating(false);
    }
  }

  function startEditing(trade: JournalTrade) {
    setEditingId(trade.id);
    setEditForm({
      asset: trade.asset,
      pair: trade.pair,
      setup: trade.setup ?? "",
      entry: trade.entry !== null && trade.entry !== undefined ? String(trade.entry) : "",
      sl: trade.sl !== null && trade.sl !== undefined ? String(trade.sl) : "",
      tp: trade.tp !== null && trade.tp !== undefined ? String(trade.tp) : "",
      risk_r: trade.risk_r !== null && trade.risk_r !== undefined ? String(trade.risk_r) : "",
      status: trade.status,
      result_r: trade.result_r !== null && trade.result_r !== undefined ? String(trade.result_r) : "",
      opened_at: toDateTimeLocalInput(trade.opened_at),
      closed_at: toDateTimeLocalInput(trade.closed_at),
      notes: trade.notes ?? ""
    });
    setUpdateStatus(null);
    setUpdateError(null);
  }

  async function handleUpdate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (editingId === null) return;
    const original = trades.find((trade) => trade.id === editingId);
    if (!original) return;

    let payload: Record<string, unknown>;
    try {
      payload = buildUpdatePayload(editForm, original);
    } catch (err: any) {
      setUpdateError(err instanceof Error ? err.message : "Valeurs numériques invalides");
      return;
    }
    if (Object.keys(payload).length === 0) {
      setUpdateStatus("Aucune modification détectée");
      return;
    }

    setUpdating(true);
    setUpdateError(null);
    setUpdateStatus(null);
    try {
      await api.patch(`/journal/${editingId}`, payload);
      setUpdateStatus("Trade mis à jour");
      setEditingId(null);
      setEditForm({ ...EMPTY_FORM });
      await refresh();
    } catch (err: any) {
      setUpdateError(formatErrorDetail(err.response?.data?.detail, "Impossible de mettre à jour"));
    } finally {
      setUpdating(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold text-slate-800">Journal de trading</h1>
          <p className="text-sm text-slate-500">
            Suivez vos setups manuels, consignez le risque et mesurez vos résultats en multiple de risque (R).
          </p>
        </header>

        <section className="space-y-4 rounded-xl bg-white p-6 shadow">
          <div>
            <h2 className="text-lg font-semibold text-slate-700">Nouvelle entrée</h2>
            <p className="text-xs text-slate-500">Les champs numériques sont optionnels et peuvent être remplis plus tard.</p>
          </div>
          <form onSubmit={handleCreate} className="grid gap-4 lg:grid-cols-2">
            <Input label="Actif" value={newTrade.asset} onChange={(value) => handleNewFieldChange("asset", value)} required />
            <Input label="Paire / Marché" value={newTrade.pair} onChange={(value) => handleNewFieldChange("pair", value)} required />
            <Input label="Setup" value={newTrade.setup} onChange={(value) => handleNewFieldChange("setup", value)} />
            <Input label="Entrée" type="number" value={newTrade.entry} onChange={(value) => handleNewFieldChange("entry", value)} />
            <Input label="Stop" type="number" value={newTrade.sl} onChange={(value) => handleNewFieldChange("sl", value)} />
            <Input label="Take Profit" type="number" value={newTrade.tp} onChange={(value) => handleNewFieldChange("tp", value)} />
            <Input
              label="Risque (R)"
              type="number"
              value={newTrade.risk_r}
              onChange={(value) => handleNewFieldChange("risk_r", value)}
            />
            <div className="grid gap-2 text-sm">
              <label className="font-medium text-slate-600">Statut</label>
              <select
                className="rounded border border-slate-200 px-3 py-2"
                value={newTrade.status}
                onChange={(e) => handleNewFieldChange("status", e.target.value)}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="Ouvert le"
              type="datetime-local"
              value={newTrade.opened_at}
              onChange={(value) => handleNewFieldChange("opened_at", value)}
            />
            <Input
              label="Clôturé le"
              type="datetime-local"
              value={newTrade.closed_at}
              onChange={(value) => handleNewFieldChange("closed_at", value)}
            />
            <div className="lg:col-span-2">
              <Input
                label="Notes"
                value={newTrade.notes}
                onChange={(value) => handleNewFieldChange("notes", value)}
                multiline
              />
            </div>
            <div className="lg:col-span-2 flex flex-wrap items-center gap-3">
              <button
                type="submit"
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={creating}
              >
                {creating ? "Enregistrement…" : "Ajouter au journal"}
              </button>
              {createStatus ? <span className="text-sm text-emerald-600">{createStatus}</span> : null}
              {createError ? <span className="text-sm text-red-600">{createError}</span> : null}
            </div>
          </form>
        </section>

        <section className="space-y-4 rounded-xl bg-white p-6 shadow">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-700">Historique</h2>
            <span className="text-sm text-slate-400">{trades.length} lignes</span>
          </div>
          {loading ? <p>Chargement…</p> : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {!loading && !hasTrades ? <p className="text-sm text-slate-500">Aucun trade enregistré.</p> : null}
          {hasTrades ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <Th>ID</Th>
                    <Th>Actif</Th>
                    <Th>Paire</Th>
                    <Th>Setup</Th>
                    <Th>Entrée</Th>
                    <Th>Stop</Th>
                    <Th>TP</Th>
                    <Th>Risque</Th>
                    <Th>Statut</Th>
                    <Th>Résultat</Th>
                    <Th>Ouverture</Th>
                    <Th>Clôture</Th>
                    <Th>Notes</Th>
                    <Th></Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trades.map((trade) => (
                    <tr key={trade.id} className="hover:bg-slate-50">
                      <Td>#{trade.id}</Td>
                      <Td>{trade.asset}</Td>
                      <Td>{trade.pair}</Td>
                      <Td>{trade.setup ?? "—"}</Td>
                      <Td>{trade.entry !== null && trade.entry !== undefined ? formatNumber(trade.entry, 4) : "—"}</Td>
                      <Td>{trade.sl !== null && trade.sl !== undefined ? formatNumber(trade.sl, 4) : "—"}</Td>
                      <Td>{trade.tp !== null && trade.tp !== undefined ? formatNumber(trade.tp, 4) : "—"}</Td>
                      <Td>{trade.risk_r !== null && trade.risk_r !== undefined ? formatNumber(trade.risk_r, 2) : "—"}</Td>
                      <Td className="capitalize">{trade.status}</Td>
                      <Td>{trade.result_r !== null && trade.result_r !== undefined ? `${formatNumber(trade.result_r, 2)} R` : "—"}</Td>
                      <Td>{trade.opened_at ? formatDateTime(trade.opened_at) : "—"}</Td>
                      <Td>{trade.closed_at ? formatDateTime(trade.closed_at) : "—"}</Td>
                      <Td className="max-w-xs truncate" title={trade.notes ?? undefined}>
                        {trade.notes ?? "—"}
                      </Td>
                      <Td>
                        <button className="text-sm text-indigo-600 hover:underline" onClick={() => startEditing(trade)}>
                          Modifier
                        </button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {editingId !== null ? (
            <form onSubmit={handleUpdate} className="mt-6 space-y-4 rounded-lg border border-slate-200 p-4">
              <h3 className="text-base font-semibold text-slate-700">Modifier le trade #{editingId}</h3>
              <div className="grid gap-4 lg:grid-cols-2">
                <Input label="Setup" value={editForm.setup} onChange={(value) => setEditForm((prev) => ({ ...prev, setup: value }))} />
                <Input
                  label="Entrée"
                  type="number"
                  value={editForm.entry}
                  onChange={(value) => setEditForm((prev) => ({ ...prev, entry: value }))}
                />
                <Input label="Stop" type="number" value={editForm.sl} onChange={(value) => setEditForm((prev) => ({ ...prev, sl: value }))} />
                <Input label="Take Profit" type="number" value={editForm.tp} onChange={(value) => setEditForm((prev) => ({ ...prev, tp: value }))} />
                <Input
                  label="Risque (R)"
                  type="number"
                  value={editForm.risk_r}
                  onChange={(value) => setEditForm((prev) => ({ ...prev, risk_r: value }))}
                />
                <Input
                  label="Résultat (R)"
                  type="number"
                  value={editForm.result_r}
                  onChange={(value) => setEditForm((prev) => ({ ...prev, result_r: value }))}
                />
                <div className="grid gap-2 text-sm">
                  <label className="font-medium text-slate-600">Statut</label>
                  <select
                    className="rounded border border-slate-200 px-3 py-2"
                    value={editForm.status}
                    onChange={(e) => setEditForm((prev) => ({ ...prev, status: e.target.value }))}
                  >
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <Input
                  label="Ouvert le"
                  type="datetime-local"
                  value={editForm.opened_at}
                  onChange={(value) => setEditForm((prev) => ({ ...prev, opened_at: value }))}
                />
                <Input
                  label="Clôturé le"
                  type="datetime-local"
                  value={editForm.closed_at}
                  onChange={(value) => setEditForm((prev) => ({ ...prev, closed_at: value }))}
                />
                <div className="lg:col-span-2">
                  <Input
                    label="Notes"
                    value={editForm.notes}
                    onChange={(value) => setEditForm((prev) => ({ ...prev, notes: value }))}
                    multiline
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="submit"
                  className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={updating}
                >
                  {updating ? "Mise à jour…" : "Enregistrer"}
                </button>
                <button
                  type="button"
                  className="text-sm text-slate-500 hover:text-slate-700"
                  onClick={() => {
                    setEditingId(null);
                    setEditForm({ ...EMPTY_FORM });
                  }}
                >
                  Annuler
                </button>
                {updateStatus ? <span className="text-sm text-emerald-600">{updateStatus}</span> : null}
                {updateError ? <span className="text-sm text-red-600">{updateError}</span> : null}
              </div>
            </form>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}

function Input({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  multiline = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  multiline?: boolean;
}) {
  return (
    <div className="grid gap-2 text-sm">
      <label className="font-medium text-slate-600">
        {label}
        {required ? <span className="text-red-500"> *</span> : null}
      </label>
      {multiline ? (
        <textarea
          className="min-h-[120px] rounded border border-slate-200 px-3 py-2"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          type={type}
          className="rounded border border-slate-200 px-3 py-2"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
        />
      )}
    </div>
  );
}

function Th({ children }: { children: ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</th>;
}

function Td({ children }: { children: ReactNode }) {
  return <td className="px-4 py-3 text-sm text-slate-700">{children}</td>;
}

function buildPayload(form: TradeFormState) {
  const payload: Record<string, unknown> = {};
  if (form.setup.trim()) payload.setup = form.setup.trim();
  if (form.entry.trim()) payload.entry = parseNumber(form.entry);
  if (form.sl.trim()) payload.sl = parseNumber(form.sl);
  if (form.tp.trim()) payload.tp = parseNumber(form.tp);
  if (form.risk_r.trim()) payload.risk_r = parseNumber(form.risk_r);
  if (form.result_r.trim()) payload.result_r = parseNumber(form.result_r);
  if (form.opened_at) payload.opened_at = fromDateTimeLocalInput(form.opened_at);
  if (form.closed_at) payload.closed_at = fromDateTimeLocalInput(form.closed_at);
  if (form.notes.trim()) payload.notes = form.notes.trim();
  return payload;
}

function buildUpdatePayload(form: TradeFormState, original: JournalTrade) {
  const payload: Record<string, unknown> = {};
  if (form.setup.trim() !== (original.setup ?? "")) payload.setup = form.setup.trim() || null;
  if (form.entry !== formatNullableNumber(original.entry)) payload.entry = form.entry.trim() ? parseNumber(form.entry) : null;
  if (form.sl !== formatNullableNumber(original.sl)) payload.sl = form.sl.trim() ? parseNumber(form.sl) : null;
  if (form.tp !== formatNullableNumber(original.tp)) payload.tp = form.tp.trim() ? parseNumber(form.tp) : null;
  if (form.risk_r !== formatNullableNumber(original.risk_r))
    payload.risk_r = form.risk_r.trim() ? parseNumber(form.risk_r) : null;
  if (form.status !== original.status) payload.status = form.status;
  if (form.result_r !== formatNullableNumber(original.result_r))
    payload.result_r = form.result_r.trim() ? parseNumber(form.result_r) : null;
  if (form.opened_at !== toDateTimeLocalInput(original.opened_at))
    payload.opened_at = form.opened_at ? fromDateTimeLocalInput(form.opened_at) : null;
  if (form.closed_at !== toDateTimeLocalInput(original.closed_at))
    payload.closed_at = form.closed_at ? fromDateTimeLocalInput(form.closed_at) : null;
  if (form.notes.trim() !== (original.notes ?? "")) payload.notes = form.notes.trim() || null;
  return payload;
}

function parseNumber(value: string) {
  const parsed = parseFloat(value);
  if (Number.isNaN(parsed)) {
    throw new Error("Valeur numérique invalide");
  }
  return parsed;
}

function formatNullableNumber(value: number | null | undefined) {
  return value !== null && value !== undefined ? String(value) : "";
}

type TradeFormState = {
  asset: string;
  pair: string;
  setup: string;
  entry: string;
  sl: string;
  tp: string;
  risk_r: string;
  status: string;
  result_r: string;
  opened_at: string;
  closed_at: string;
  notes: string;
};

type JournalTrade = {
  id: number;
  asset: string;
  pair: string;
  setup?: string | null;
  entry?: number | null;
  sl?: number | null;
  tp?: number | null;
  risk_r?: number | null;
  status: string;
  result_r?: number | null;
  opened_at?: string | null;
  closed_at?: string | null;
  notes?: string | null;
};
