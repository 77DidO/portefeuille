"use client";

import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { formatErrorDetail } from "@/lib/errors";

export default function ExportPage() {
  const [downloading, setDownloading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    setDownloading(true);
    setStatus(null);
    setError(null);
    try {
      const response = await api.get<ArrayBuffer>("/export/zip", { responseType: "arraybuffer" });
      const blob = new Blob([response.data], { type: "application/zip" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "portefeuille_export.zip";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setStatus("Export téléchargé");
    } catch (err: any) {
      setError(formatErrorDetail(err.response?.data?.detail, "Impossible de télécharger l’archive"));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-8">
        <header className="space-y-2">
          <h1 className="text-2xl font-semibold text-slate-800">Export & sauvegarde</h1>
          <p className="text-sm text-slate-500">
            Récupérez une archive ZIP contenant l’intégralité des transactions, snapshots et paramètres pour sauvegarde ou
            migration.
          </p>
        </header>

        <section className="space-y-4 rounded-xl bg-white p-6 shadow">
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleDownload}
              className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
              disabled={downloading}
            >
              {downloading ? "Préparation…" : "Télécharger l’export"}
            </button>
            {status ? <span className="text-sm text-emerald-600">{status}</span> : null}
            {error ? <span className="text-sm text-red-600">{error}</span> : null}
          </div>
          <ul className="list-disc space-y-2 pl-6 text-sm text-slate-600">
            <li>transactions.csv — toutes les opérations importées avec leurs métadonnées.</li>
            <li>snapshots.csv — l’historique des valorisations quotidiennes.</li>
            <li>settings.json — les préférences applicatives (heure de snapshot, clés API chiffrées, etc.).</li>
          </ul>
        </section>

        <section className="space-y-3 rounded-xl bg-white p-6 shadow">
          <h2 className="text-lg font-semibold text-slate-700">Bonnes pratiques</h2>
          <ul className="list-disc space-y-2 pl-6 text-sm text-slate-600">
            <li>Pensez à stocker l’archive sur un support chiffré si elle contient des données sensibles.</li>
            <li>
              Après une restauration, ré-importez l’archive via l’API <code>/transactions/import</code> puis relancez un snapshot pour
              recalculer les positions.
            </li>
            <li>Automatisez les exports réguliers grâce à une tâche cron qui appelle directement cet endpoint.</li>
          </ul>
        </section>
      </div>
    </AppShell>
  );
}
