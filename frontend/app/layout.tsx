import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Portefeuille PEA + Crypto",
  description: "Dashboard mono-utilisateur pour suivre PEA & Crypto"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-slate-50 text-slate-900">
        {children}
      </body>
    </html>
  );
}
