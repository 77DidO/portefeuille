"use client";

import {
  Fragment,
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { formatCurrency, formatDateTime, formatNumber } from "@/lib/format";
import { formatErrorDetail } from "@/lib/errors";

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<TransactionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<TransactionFormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    refresh();
  }, []);

  const hasTransactions = useMemo(() => transactions.length > 0, [transactions]);

  async function refresh() {
    try {
      setLoading(true);
      const { data } = await api.get<TransactionResponse[]>("/transactions/");
      setTransactions(data);
      setError(null);
    } catch (err: any) {
      setError(formatErrorDetail(err.response?.data?.detail, "Impossible de charger les transactions"));
    } finally {
      setLoading(false);
    }
  }

  async function handleImport(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedFile) {
      setImportError("Choisissez un fichier ZIP ou CSV à importer");
      return;
    }
    const formData = new FormData();
    formData.append("file", selectedFile);
    setImportError(null);
    setImportStatus(null);
    setImporting(true);
    try {
      await api.post("/transactions/import", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setImportStatus("Import terminé avec succès");
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await refresh();
    } catch (err: any) {
      setImportError(formatErrorDetail(err.response?.data?.detail, "Import impossible"));
    } finally {
      setImporting(false);
    }
  }

  function startEditing(transaction: TransactionResponse) {
    setEditingId(transaction.id);
    setEditForm(transactionToFormState(transaction));
    setActionError(null);
  }

  function handleCancelEdit() {
    setEditingId(null);
    setEditForm(null);
    setActionError(null);
  }

  function handleEditFieldChange(event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = event.target;
    setEditForm((previous) => {
      if (!previous) {
        return previous;
      }
      const fieldName = name as keyof TransactionFormState;
      return { ...previous, [fieldName]: value };
    });
  }

  async function handleEditSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editForm || editingId === null) {
      return;
    }

    setActionError(null);

    const quantity = Number(editForm.quantity.replace(",", "."));
    if (Number.isNaN(quantity)) {
      setActionError("Quantité invalide");
      return;
    }
    const unitPrice = Number(editForm.unit_price_eur.replace(",", "."));
    if (Number.isNaN(unitPrice)) {
      setActionError("Prix unitaire invalide");
      return;
    }
    const fee = Number(editForm.fee_eur.replace(",", "."));
    if (Number.isNaN(fee)) {
      setActionError("Frais invalides");
      return;
    }
    const total = Number(editForm.total_eur.replace(",", "."));
    if (Number.isNaN(total)) {
      setActionError("Total invalide");
      return;
    }
    if (!editForm.ts) {
      setActionError("Date invalide");
      return;
    }
    const tsDate = new Date(editForm.ts);
    if (Number.isNaN(tsDate.getTime())) {
      setActionError("Date invalide");
      return;
    }

    const payload: TransactionUpdatePayload = {
      source: editForm.source.trim(),
      type_portefeuille: editForm.type_portefeuille.trim(),
      operation: editForm.operation.trim(),
      asset: editForm.asset.trim(),
      symbol_or_isin: editForm.symbol_or_isin.trim() ? editForm.symbol_or_isin.trim() : null,
      quantity,
      unit_price_eur: unitPrice,
      fee_eur: fee,
      total_eur: total,
      ts: tsDate.toISOString(),
      notes: editForm.notes.trim() ? editForm.notes.trim() : null,
      external_ref: editForm.external_ref.trim() ? editForm.external_ref.trim() : null
    };

    setSaving(true);
    try {
      await api.patch<TransactionResponse>(`/transactions/${editingId}`, payload);
      setEditingId(null);
      setEditForm(null);
      await refresh();
    } catch (err: any) {
      setActionError(formatErrorDetail(err.response?.data?.detail, "Modification impossible"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(transaction: TransactionResponse) {
    const confirmed = window.confirm(
      `Supprimer la transaction du ${formatDateTime(transaction.ts)} ? Cette action est irréversible.`
    );
    if (!confirmed) {
      return;
    }

    setActionError(null);
    setDeletingId(transaction.id);
    try {
      await api.delete(`/transactions/${transaction.id}`);
      if (editingId === transaction.id) {
        setEditingId(null);
        setEditForm(null);
      }
      await refresh();
    } catch (err: any) {
      setActionError(formatErrorDetail(err.response?.data?.detail, "Suppression impossible"));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-slate-800">Transactions</h1>
          <p className="text-sm text-slate-500">
            Historique des opérations importées (limité aux 500 plus récentes). Pour ajouter de nouvelles lignes, téléversez un ZIP ou un fichier CSV
            contenant au minimum un fichier transactions.csv conforme.
          </p>
        </div>
        <section className="space-y-4 rounded-xl bg-white p-6 shadow">
          <h2 className="text-lg font-semibold text-slate-700">Importer un relevé</h2>
          <form onSubmit={handleImport} className="flex flex-col gap-4 md:flex-row md:items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-600">Fichier ZIP ou CSV</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip,.csv"
                className="mt-1 w-full rounded border border-slate-200 px-3 py-2"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
              <p className="mt-1 text-xs text-slate-500">Le ZIP ou le CSV doit contenir un transactions.csv avec les colonnes attendues.</p>
            </div>
            <button
              type="submit"
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={importing}
            >
              {importing ? "Import…" : "Lancer l'import"}
            </button>
          </form>
          {importStatus ? <p className="text-sm text-emerald-600">{importStatus}</p> : null}
          {importError ? <p className="text-sm text-red-600">{importError}</p> : null}
        </section>

        <section className="rounded-xl bg-white p-6 shadow">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-700">Historique</h2>
            <div className="text-sm text-slate-400">{transactions.length} lignes</div>
          </div>
          {loading ? <p>Chargement…</p> : null}
          {error ? <p className="text-red-600">{error}</p> : null}
          {!loading && !hasTransactions ? (
            <p className="text-sm text-slate-500">Aucune transaction importée pour le moment.</p>
          ) : null}
          {hasTransactions ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <Th>Date</Th>
                    <Th>Source</Th>
                    <Th>Type</Th>
                    <Th>Opération</Th>
                    <Th>Actif</Th>
                    <Th>Symbole</Th>
                    <Th>Quantité</Th>
                    <Th>Prix unitaire</Th>
                    <Th>Frais</Th>
                    <Th>Total</Th>
                    <Th>Notes</Th>
                    <Th>Actions</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {transactions.map((transaction) => (
                    <Fragment key={transaction.id}>
                      <tr className="hover:bg-slate-50">
                        <Td>{formatDateTime(transaction.ts)}</Td>
                        <Td>{transaction.source}</Td>
                        <Td className="uppercase">{transaction.type_portefeuille}</Td>
                        <Td>{transaction.operation}</Td>
                        <Td>{transaction.asset}</Td>
                        <Td>{transaction.symbol_or_isin ?? "-"}</Td>
                        <Td>{formatNumber(transaction.quantity, 4)}</Td>
                        <Td>{formatCurrency(transaction.unit_price_eur)}</Td>
                        <Td>{formatCurrency(transaction.fee_eur)}</Td>
                        <Td>{formatCurrency(transaction.total_eur)}</Td>
                        <Td className="max-w-xs truncate" title={transaction.notes ?? undefined}>
                          {transaction.notes ?? "—"}
                        </Td>
                        <Td>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
                              onClick={() => startEditing(transaction)}
                              disabled={saving && editingId === transaction.id}
                            >
                              Modifier
                            </button>
                            <button
                              type="button"
                              className="text-sm font-medium text-red-600 hover:text-red-800 disabled:text-slate-400"
                              onClick={() => handleDelete(transaction)}
                              disabled={deletingId === transaction.id}
                            >
                              {deletingId === transaction.id ? "Suppression…" : "Supprimer"}
                            </button>
                          </div>
                        </Td>
                      </tr>
                      {editingId === transaction.id && editForm ? (
                        <tr className="bg-slate-50">
                          <td colSpan={12} className="px-4 py-4">
                            <form onSubmit={handleEditSubmit} className="space-y-4">
                              <div className="grid gap-4 md:grid-cols-2">
                                <FormField label="Source">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="source"
                                    value={editForm.source}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Type de portefeuille">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="type_portefeuille"
                                    value={editForm.type_portefeuille}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Opération">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="operation"
                                    value={editForm.operation}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Actif">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="asset"
                                    value={editForm.asset}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Symbole ou ISIN">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="symbol_or_isin"
                                    value={editForm.symbol_or_isin}
                                    onChange={handleEditFieldChange}
                                  />
                                </FormField>
                                <FormField label="Quantité">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="quantity"
                                    value={editForm.quantity}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Prix unitaire (€)">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="unit_price_eur"
                                    value={editForm.unit_price_eur}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Frais (€)">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="fee_eur"
                                    value={editForm.fee_eur}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Total (€)">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="total_eur"
                                    value={editForm.total_eur}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Date">
                                  <input
                                    type="datetime-local"
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="ts"
                                    value={editForm.ts}
                                    onChange={handleEditFieldChange}
                                    required
                                  />
                                </FormField>
                                <FormField label="Référence externe" className="md:col-span-2">
                                  <input
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="external_ref"
                                    value={editForm.external_ref}
                                    onChange={handleEditFieldChange}
                                  />
                                </FormField>
                                <FormField label="Notes" className="md:col-span-2">
                                  <textarea
                                    className="w-full rounded border border-slate-200 px-3 py-2"
                                    name="notes"
                                    value={editForm.notes}
                                    onChange={handleEditFieldChange}
                                    rows={3}
                                  />
                                </FormField>
                              </div>
                              {actionError ? <p className="text-sm text-red-600">{actionError}</p> : null}
                              <div className="flex gap-2">
                                <button
                                  type="submit"
                                  className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                                  disabled={saving}
                                >
                                  {saving ? "Enregistrement…" : "Enregistrer"}
                                </button>
                                <button
                                  type="button"
                                  className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
                                  onClick={handleCancelEdit}
                                  disabled={saving}
                                >
                                  Annuler
                                </button>
                              </div>
                            </form>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {actionError && (!editForm || editingId === null) ? (
            <p className="mt-4 text-sm text-red-600">{actionError}</p>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}

function Th({ children }: { children: ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</th>;
}

function Td({ children }: { children: ReactNode }) {
  return <td className="px-4 py-3 text-sm text-slate-700">{children}</td>;
}

function FormField({
  label,
  children,
  className
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const classes = ["flex flex-col gap-1", className]
    .filter((value): value is string => Boolean(value))
    .join(" ");
  return (
    <div className={classes}>
      <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</label>
      {children}
    </div>
  );
}

type TransactionResponse = {
  id: number;
  source: string;
  type_portefeuille: string;
  operation: string;
  asset: string;
  symbol_or_isin?: string | null;
  quantity: number;
  unit_price_eur: number;
  fee_eur: number;
  total_eur: number;
  ts: string;
  notes?: string | null;
  external_ref?: string | null;
};

type TransactionUpdatePayload = {
  source: string;
  type_portefeuille: string;
  operation: string;
  asset: string;
  symbol_or_isin: string | null;
  quantity: number;
  unit_price_eur: number;
  fee_eur: number;
  total_eur: number;
  ts: string;
  notes: string | null;
  external_ref: string | null;
};

type TransactionFormState = {
  source: string;
  type_portefeuille: string;
  operation: string;
  asset: string;
  symbol_or_isin: string;
  quantity: string;
  unit_price_eur: string;
  fee_eur: string;
  total_eur: string;
  ts: string;
  notes: string;
  external_ref: string;
};

function transactionToFormState(transaction: TransactionResponse): TransactionFormState {
  return {
    source: transaction.source,
    type_portefeuille: transaction.type_portefeuille,
    operation: transaction.operation,
    asset: transaction.asset,
    symbol_or_isin: transaction.symbol_or_isin ?? "",
    quantity: transaction.quantity.toString(),
    unit_price_eur: transaction.unit_price_eur.toString(),
    fee_eur: transaction.fee_eur.toString(),
    total_eur: transaction.total_eur.toString(),
    ts: formatDateTimeLocalInput(transaction.ts),
    notes: transaction.notes ?? "",
    external_ref: transaction.external_ref ?? ""
  };
}

function formatDateTimeLocalInput(ts: string): string {
  const date = new Date(ts);
  const offsetMinutes = date.getTimezoneOffset();
  const localDate = new Date(date.getTime() - offsetMinutes * 60 * 1000);
  return localDate.toISOString().slice(0, 16);
}
