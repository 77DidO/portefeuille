"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { isTokenValid, useAuthStore } from "@/lib/store";

export function useRequireAuth() {
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const expiresAt = useAuthStore((state) => state.expiresAt);
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    if (!isTokenValid(token, expiresAt)) {
      logout();
      router.push("/login");
    }
  }, [token, expiresAt, logout, router]);

  return { token, expiresAt, logout };
}
