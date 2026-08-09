"use client";

import type { ReactNode } from "react";
import { useLicense } from "@/context/LicenseProvider";

export function FeatureGate({ feature, children }: { feature: string; children: ReactNode }) {
  const { apiKey, validating, hasEntitlement } = useLicense();
  if (validating) {
    return <p className="rounded-lg bg-gray-50 p-4 text-sm text-gray-500" aria-live="polite">Validando licencia…</p>;
  }
  if (!apiKey || !hasEntitlement(feature)) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">
        Activa una licencia con la función <strong>{feature}</strong> en el encabezado para usar esta herramienta.
      </div>
    );
  }
  return children;
}
