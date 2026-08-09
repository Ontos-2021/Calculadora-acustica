"use client";

import type { ReactNode } from "react";
import { LockKeyhole } from "lucide-react";
import { useLicense } from "@/context/LicenseProvider";

export function FeatureGate({ feature, children }: { feature: string; children: ReactNode }) {
  const { apiKey, validating, hasEntitlement } = useLicense();
  if (validating) {
    return <p className="rounded-lg bg-surface-muted p-4 text-sm text-muted" aria-live="polite">Validando licencia…</p>;
  }
  if (!apiKey || !hasEntitlement(feature)) {
    return (
      <div className="relative min-h-36 overflow-hidden rounded-lg border border-amber-200 bg-surface-muted" role="status">
        <div className="pointer-events-none grid grid-cols-3 gap-2 p-5 opacity-25 blur-[1.5px]" aria-hidden="true">
          <div className="col-span-2 h-24 rounded-md bg-teal-400" />
          <div className="space-y-2"><div className="h-7 rounded bg-zinc-300" /><div className="h-7 rounded bg-zinc-300" /><div className="h-7 rounded bg-zinc-300" /></div>
        </div>
        <div className="absolute inset-0 grid place-items-center bg-white/25 p-4 backdrop-blur-[1px] dark:bg-zinc-950/20">
          <div className="max-w-sm rounded-lg border border-amber-300 bg-amber-50/95 p-3 text-center text-sm text-amber-950 shadow-sm dark:border-amber-800 dark:bg-amber-950/95 dark:text-amber-100">
            <LockKeyhole className="mx-auto mb-1.5 size-5" />
            Activa una licencia con <strong>{feature}</strong> para calcular con tu sala.
          </div>
        </div>
      </div>
    );
  }
  return children;
}
