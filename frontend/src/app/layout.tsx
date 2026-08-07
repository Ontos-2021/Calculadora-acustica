import type { Metadata } from "next";
import "./globals.css";
import { OfflineBadge } from "@/components/ui/OfflineBadge";

export const metadata: Metadata = {
  title: "Calculadora Acústica Profesional",
  description:
    "Herramienta profesional de diseño acústico arquitectónico: modos de resonancia, RT60, criterio de Bonello y más.",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500">
        <div className="mx-auto max-w-6xl px-4 py-8">
          <header className="mb-8 text-center">
            <div className="mb-2 flex items-center justify-center gap-4">
              <h1 className="text-4xl font-bold text-white drop-shadow-lg">
                Calculadora Acústica
              </h1>
              <OfflineBadge />
            </div>
            <p className="mt-1 text-lg text-white/70">
              Superficie, RT60, modos de resonancia y parámetros avanzados
            </p>
          </header>
          <main>{children}</main>
          <footer className="mt-12 text-center text-xs text-white/40">
            <p>Calculadora Acústica Profesional v1.0</p>
          </footer>
        </div>
      </body>
    </html>
  );
}
