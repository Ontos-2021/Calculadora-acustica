"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { KeyRound, X } from "lucide-react";
import { useLicense } from "@/context/LicenseProvider";
import { Button } from "@/components/ui/Button";
import { LicenseManager } from "./LicenseManager";

export function LicenseDialog() {
  const { status } = useLicense();
  return <Dialog.Root>
    <Dialog.Trigger asChild><Button type="button" variant="secondary" size="sm" data-testid="license-trigger" aria-label={status ? `Licencia ${status.tier}` : "Activar licencia"}><KeyRound className="size-4" /><span className="hidden sm:inline">{status?.tier || "Licencia"}</span></Button></Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-50 bg-zinc-950/45 backdrop-blur-[2px]" />
      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(94vw,42rem)] -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-surface p-5 shadow-2xl focus:outline-none">
        <div className="mb-3 flex items-start justify-between gap-4"><div><Dialog.Title className="text-lg font-semibold">Licencia profesional</Dialog.Title><Dialog.Description className="mt-1 text-sm text-muted">Activa herramientas de diseño, medición, aislamiento y métodos numéricos.</Dialog.Description></div><Dialog.Close className="grid size-9 place-items-center rounded-md text-muted hover:bg-surface-muted" aria-label="Cerrar"><X className="size-5" /></Dialog.Close></div>
        <LicenseManager />
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>;
}
