"use client";

import { useState } from "react";
import axios from "axios";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { formatErrorDetail } from "@/lib/errors";

export default function LoginPage() {
  const router = useRouter();
  const setToken = useAuthStore((s) => s.setToken);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
      const { data } = await axios.post(`${base}/auth/login`, { username, password });
      setToken(data.access_token, data.expires_at);
      router.push("/");
    } catch (err: any) {
      setError(formatErrorDetail(err.response?.data?.detail, "Impossible de se connecter"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <form onSubmit={handleSubmit} className="w-full max-w-md space-y-6 rounded-xl bg-white p-8 shadow">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Connexion</h1>
          <p className="text-sm text-slate-500">Mono-utilisateur — admin</p>
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-600" htmlFor="username">
            Identifiant
          </label>
          <input
            id="username"
            className="w-full rounded border border-slate-200 px-3 py-2 focus:border-indigo-500 focus:outline-none"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <label className="block text-sm font-medium text-slate-600" htmlFor="password">
            Mot de passe
          </label>
          <input
            id="password"
            type="password"
            className="w-full rounded border border-slate-200 px-3 py-2 focus:border-indigo-500 focus:outline-none"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <button
          type="submit"
          className="w-full rounded bg-indigo-600 px-3 py-2 text-white transition hover:bg-indigo-700"
          disabled={loading}
        >
          {loading ? "Connexion…" : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
