"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { formatCurrency, formatDateTime, formatNumber } from "@/lib/format";
import { formatErrorDetail } from "@/lib/errors";

export default function TransactionsPage() {
  useRequireAuth();
  const [transactions, setTransactions] = useState<TransactionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
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
      setImportError("Choisissez un fichier ZIP à importer");
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

  return (
    <AppShell>
      <div className="space-y-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold text-slate-800">Transactions</h1>
          <p className="text-sm text-slate-500">
            Historique des opérations importées (limité aux 500 plus récentes). Pour ajouter de nouvelles lignes, téléversez un ZIP
            contenant au minimum un fichier transactions.csv conforme.
          </p>
        </div>
        <section className="space-y-4 rounded-xl bg-white p-6 shadow">
          <h2 className="text-lg font-semibold text-slate-700">Importer un relevé</h2>
          <form onSubmit={handleImport} className="flex flex-col gap-4 md:flex-row md:items-end">
            <div className="flex-1">
              <label className="block text-sm font-medium text-slate-600">Fichier ZIP</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                className="mt-1 w-full rounded border border-slate-200 px-3 py-2"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
              <p className="mt-1 text-xs text-slate-500">Le ZIP doit contenir un transactions.csv avec les colonnes attendues.</p>
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
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {transactions.map((transaction) => (
                    <tr key={transaction.id} className="hover:bg-slate-50">
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

function Th({ children }: { children: ReactNode }) {
  return <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</th>;
}

function Td({ children }: { children: ReactNode }) {
  return <td className="px-4 py-3 text-sm text-slate-700">{children}</td>;
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
};
