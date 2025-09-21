"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatErrorDetail } from "@/lib/errors";
import { isTokenValid, useAuthStore } from "@/lib/store";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const router = useRouter();
  const { token, expiresAt, logout } = useAuthStore();
  const [binanceKey, setBinanceKey] = useState("");
  const [binanceSecret, setBinanceSecret] = useState("");
  const [snapshotTime, setSnapshotTime] = useState("18:00");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    if (!isTokenValid(token, expiresAt)) {
      logout();
      router.push("/login");
      return;
    }
  }, [token, expiresAt, logout, router]);

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
      await api.post("/config/api/binance", { key: binanceKey, secret: binanceSecret });
      setStatus("Clés Binance sauvegardées");
    } catch (err: any) {
      setStatus(formatErrorDetail(err.response?.data?.detail, "Impossible d'enregistrer"));
    }
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="mx-auto max-w-3xl space-y-10 px-6 py-12">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Configuration</h1>
          <p className="text-sm text-slate-500">Réglages généraux, API et sécurité</p>
        </div>
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
      </div>
    </div>
  );
}
