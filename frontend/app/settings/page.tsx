"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { formatErrorDetail } from "@/lib/errors";

export default function SettingsPage() {
  const [binanceKey, setBinanceKey] = useState("");
  const [binanceSecret, setBinanceSecret] = useState("");
  const [snapshotTime, setSnapshotTime] = useState("18:00");
  const [status, setStatus] = useState<string | null>(null);
  const [binanceConfigured, setBinanceConfigured] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [wiping, setWiping] = useState(false);

  useEffect(() => {
    async function loadSettings() {
      try {
        const { data } = await api.get("/config/settings");
        const snapshot = data.find((item: SettingResponse) => item.key === "snapshot_time");
        if (snapshot?.value) {
          setSnapshotTime(snapshot.value);
        }
        const binanceKeys = data.filter((item: SettingResponse) => item.key.startsWith("binance_api_"));
        setBinanceConfigured(binanceKeys.some((item) => Boolean(item.value)));
        setLoadError(null);
      } catch (err: any) {
        setLoadError(formatErrorDetail(err.response?.data?.detail, "Impossible de charger les paramètres"));
      }
    }
    loadSettings();
  }, []);

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.post("/config/settings", {
        data: {
          snapshot_time: snapshotTime
        }
      });
      setStatus("Préférences enregistrées");
    } catch (err: any) {
      setStatus(formatErrorDetail(err.response?.data?.detail, "Erreur lors de la sauvegarde"));
    }
  }

  async function handleSaveBinance(e: React.FormEvent) {
    e.preventDefault();
    try {
      const hasCredentials = Boolean(binanceKey || binanceSecret);
      await api.post("/config/api/binance", { key: binanceKey, secret: binanceSecret });
      setStatus("Clés Binance sauvegardées");
      setBinanceConfigured(hasCredentials);
    } catch (err: any) {
      setStatus(formatErrorDetail(err.response?.data?.detail, "Impossible d'enregistrer"));
    }
  }

  async function handleWipeData() {
    if (!window.confirm("Voulez-vous vraiment supprimer toutes les données importées ?")) {
      return;
    }
    try {
      setWiping(true);
      setStatus(null);
      await api.post("/config/wipe");
      setStatus("Toutes les données ont été supprimées");
    } catch (err: any) {
      setStatus(formatErrorDetail(err.response?.data?.detail, "Suppression impossible"));
    } finally {
      setWiping(false);
    }
  }

  return (
    <AppShell mainClassName="max-w-3xl space-y-10">
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Configuration</h1>
        <p className="text-sm text-slate-500">Réglages généraux, API et sécurité</p>
      </div>
      {loadError ? <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{loadError}</div> : null}
      {status ? <div className="rounded border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-700">{status}</div> : null}
      <section className="space-y-6 rounded-xl bg-white p-6 shadow">
        <h2 className="text-lg font-semibold text-slate-700">Préférences</h2>
        <form onSubmit={handleSaveSettings} className="space-y-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-600">Heure du snapshot (Europe/Paris)</label>
            <input
              type="time"
              className="w-40 rounded border border-slate-200 px-3 py-2"
              value={snapshotTime}
              onChange={(e) => setSnapshotTime(e.target.value)}
            />
          </div>
          <button type="submit" className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white">
            Enregistrer
          </button>
        </form>
      </section>

      <section className="space-y-6 rounded-xl bg-white p-6 shadow">
        <h2 className="text-lg font-semibold text-slate-700">API Binance (lecture seule)</h2>
        {binanceConfigured ? (
          <p className="text-sm text-slate-500">
            Une paire de clés est déjà enregistrée. Renseignez de nouvelles valeurs pour les remplacer.
          </p>
        ) : null}
        <form onSubmit={handleSaveBinance} className="space-y-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-600">API Key</label>
            <input
              className="w-full rounded border border-slate-200 px-3 py-2"
              value={binanceKey}
              onChange={(e) => setBinanceKey(e.target.value)}
              placeholder="clé publique"
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium text-slate-600">Secret</label>
            <input
              className="w-full rounded border border-slate-200 px-3 py-2"
              value={binanceSecret}
              onChange={(e) => setBinanceSecret(e.target.value)}
              placeholder="clé secrète"
            />
          </div>
          <button type="submit" className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white">
            Sauvegarder
          </button>
        </form>
      </section>

      <section className="space-y-4 rounded-xl bg-white p-6 shadow">
        <h2 className="text-lg font-semibold text-slate-700">Zone sensible</h2>
        <p className="text-sm text-slate-500">
          Supprime toutes les transactions, snapshots et journaux importés. Cette action est irréversible.
        </p>
        <button
          type="button"
          onClick={handleWipeData}
          disabled={wiping}
          className="w-full rounded bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-slate-300 md:w-auto"
        >
          {wiping ? "Suppression…" : "Vider toutes les données"}
        </button>
      </section>
    </AppShell>
  );
}

type SettingResponse = {
  key: string;
  value: string | null;
};
