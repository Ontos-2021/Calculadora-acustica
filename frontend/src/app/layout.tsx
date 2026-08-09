import type { Metadata } from "next";
import "./globals.css";
import { OfflineBadge } from "@/components/ui/OfflineBadge";
import { LicenseManager } from "@/components/license/LicenseManager";
import { Providers } from "./Providers";

export const metadata: Metadata = {
  title: "Calculadora Acústica Profesional",
  description:
    "Herramienta profesional de diseño acústico arquitectónico: modos de resonancia, RT60, criterio de Bonello y más.",
  manifest: "/manifest.json",
  icons: {
    icon: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/icon-192.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500">
        <Providers>
          <div className="mx-auto max-w-6xl px-3 py-5 sm:px-4 sm:py-8">
            <header className="mb-6 text-center sm:mb-8">
              <div className="mb-2 flex flex-wrap items-center justify-center gap-3 sm:gap-4">
                <h1 className="text-3xl font-bold text-white drop-shadow-lg sm:text-4xl">
                  Calculadora Acústica
                </h1>
                <OfflineBadge />
              </div>
              <p className="mt-1 text-sm text-white/75 sm:text-lg">
                Superficie, RT60, modos de resonancia y parámetros avanzados
              </p>
              <LicenseManager />
            </header>
            <main>{children}</main>
            <footer className="mt-12 text-center text-xs text-white/60">
              <p>Calculadora Acústica Profesional v2.0 · Estimación de ingeniería, no certificación</p>
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
