"use client";

import { useState, type FormEvent } from "react";
import { useLicense } from "@/context/LicenseProvider";

function quotaLabel(name: string): string {
  return name
    .replace("requests_per_minute", "solicitudes/min")
    .replace("daily_request_units", "unidades/día")
    .replace("max_concurrent_jobs", "trabajos simultáneos")
    .replace("max_storage_bytes", "almacenamiento (bytes)");
}

export function LicenseManager() {
  const { status, validating, error, activate, revokeLocal } = useLicense();
  const [candidate, setCandidate] = useState("");
  const [expanded, setExpanded] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await activate(candidate)) {
      setCandidate("");
      setExpanded(true);
    }
  }

  return (
    <section className="mx-auto mt-4 max-w-3xl rounded-xl border border-white/25 bg-white/95 p-3 text-left shadow-sm" aria-label="Licencia y clave API">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Licencia</span>
        {status ? (
          <>
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${status.tier === "FREE" ? "bg-gray-100 text-gray-700" : status.tier === "PAID" ? "bg-amber-100 text-amber-800" : "bg-purple-100 text-purple-800"}`}>
              {status.tier}
            </span>
            <span className="min-w-0 flex-1 truncate text-xs text-gray-600">
              {status.email} · clave {status.key_prefix}…
            </span>
            <button type="button" className="text-xs font-medium text-indigo-600 hover:text-indigo-800" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
              {expanded ? "Ocultar detalle" : "Ver detalle"}
            </button>
            <button type="button" className="text-xs font-medium text-red-600 hover:text-red-800" onClick={revokeLocal}>
              Revocar sesión local
            </button>
          </>
        ) : (
          <form onSubmit={submit} className="flex min-w-0 flex-1 flex-wrap gap-2">
            <label htmlFor="license-key" className="sr-only">Clave API</label>
            <input
              id="license-key"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={candidate}
              onChange={(event) => setCandidate(event.target.value)}
              placeholder="Clave API PAID / RESEARCH"
              className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            />
            <button type="submit" disabled={validating} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
              {validating ? "Validando…" : "Activar"}
            </button>
          </form>
        )}
      </div>

      {!status && (
        <p className="mt-1 text-[11px] text-gray-500">
          El análisis FREE es anónimo. La clave se conserva únicamente en esta sesión del navegador.
        </p>
      )}
      {error && <p className="mt-1 text-xs text-red-700" role="alert" aria-live="polite">{error}</p>}

      {status && expanded && (
        <div className="mt-3 grid gap-3 border-t border-gray-100 pt-3 sm:grid-cols-2">
          <div>
            <h2 className="text-xs font-semibold text-gray-700">Funciones habilitadas</h2>
            <p className="mt-1 text-[11px] leading-5 text-gray-600">{status.entitlements.join(" · ")}</p>
          </div>
          <div>
            <h2 className="text-xs font-semibold text-gray-700">Cuotas</h2>
            <dl className="mt-1 grid grid-cols-[1fr_auto] gap-x-3 text-[11px] text-gray-600">
              {Object.entries(status.quotas).map(([name, value]) => (
                <div className="contents" key={name}>
                  <dt>{quotaLabel(name)}</dt>
                  <dd className="font-medium tabular-nums">{value.toLocaleString("es")}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}
    </section>
  );
}
