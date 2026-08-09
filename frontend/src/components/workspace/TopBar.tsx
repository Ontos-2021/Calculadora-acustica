"use client";

import { AudioLines } from "lucide-react";
import { OfflineBadge } from "@/components/ui/OfflineBadge";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { LicenseDialog } from "@/components/license/LicenseDialog";

export function TopBar() {
  return <header className="sticky top-0 z-40 border-b bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/85">
    <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-3 sm:px-5">
      <div className="grid size-8 place-items-center rounded-lg bg-teal-700 text-white dark:bg-teal-500 dark:text-zinc-950"><AudioLines className="size-5" /></div>
      <div className="min-w-0 flex-1"><h1 className="truncate text-sm font-bold tracking-tight sm:text-base">Calculadora Acústica</h1><p className="hidden text-[11px] text-muted sm:block">Workspace de análisis y diseño arquitectónico</p></div>
      <OfflineBadge />
      <ThemeToggle />
      <LicenseDialog />
    </div>
  </header>;
}
