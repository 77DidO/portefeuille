"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Tableau de bord" },
  { href: "/transactions", label: "Transactions" },
  { href: "/journal", label: "Journal" },
  { href: "/gabarits", label: "Gabarits" },
  { href: "/snapshots", label: "Snapshots" },
  { href: "/export", label: "Export" }
];

export function AppShell({ children, mainClassName }: { children: ReactNode; mainClassName?: string }) {
  const pathname = usePathname();

  const mainClasses = ["mx-auto", "w-full", "px-6", "py-8", mainClassName ?? "max-w-6xl"].filter(Boolean).join(" ");

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Link href="/" className="text-xl font-semibold text-slate-800">
              Portefeuille — PEA & Crypto
            </Link>
            <p className="text-sm text-slate-500">Mono-utilisateur — données stockées en local</p>
          </div>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-end">
            <nav className="flex flex-wrap gap-3 text-sm font-medium">
              {NAV_ITEMS.map((item) => {
                const isActive = item.href === "/" ? pathname === item.href : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={
                      "rounded px-3 py-1 transition " +
                      (isActive ? "bg-indigo-50 text-indigo-600" : "text-slate-500 hover:bg-slate-100 hover:text-slate-700")
                    }
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
            <div className="flex items-center gap-3 text-sm">
              <Link className="text-indigo-600 hover:underline" href="/settings">
                Configuration
              </Link>
              <span className="text-slate-400">Mode local</span>
            </div>
          </div>
        </div>
      </header>
      <main className={mainClasses}>{children}</main>
    </div>
  );
}
