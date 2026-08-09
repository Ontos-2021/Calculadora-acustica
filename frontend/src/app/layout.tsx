import type { Metadata } from "next";
import "@fontsource-variable/inter/wght.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "./globals.css";
import { TopBar } from "@/components/workspace/TopBar";
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
      <body className="min-h-screen bg-canvas text-foreground antialiased">
        <Providers>
          <TopBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
