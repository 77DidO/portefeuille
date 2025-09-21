import { create } from "zustand";
import { persist } from "zustand/middleware";
import jwtDecode from "jwt-decode";

type AuthState = {
  token: string | null;
  expiresAt: string | null;
  setToken: (token: string, expiresAt: string) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      expiresAt: null,
      setToken: (token, expiresAt) => set({ token, expiresAt }),
      logout: () => set({ token: null, expiresAt: null })
    }),
    {
      name: "portfolio-auth"
    }
  )
);

export function isTokenValid(token: string | null, expiresAt: string | null) {
  if (!token || !expiresAt) return false;
  const expiry = new Date(expiresAt).getTime();
  return Date.now() < expiry - 60_000;
}
