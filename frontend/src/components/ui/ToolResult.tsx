import type { ReactNode } from "react";

function formatValue(value: unknown): ReactNode {
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString("es") : value.toFixed(3);
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return `${value.length} valores`;
  if (value && typeof value === "object") return `${Object.keys(value).length} campos`;
  return "—";
}

export function ToolResult({ result, title = "Resultado" }: { result: Record<string, unknown>; title?: string }) {
  const metrics = Object.entries(result)
    .filter(([, value]) => ["number", "string", "boolean"].includes(typeof value))
    .slice(0, 8);
  return (
    <section className="mt-4 rounded-lg border border-indigo-100 bg-indigo-50/40 p-3" aria-live="polite">
      <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
      {metrics.length > 0 && (
        <dl className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map(([key, value]) => (
            <div key={key} className="rounded-md bg-white p-2 shadow-sm">
              <dt className="text-[10px] uppercase tracking-wide text-gray-500">{key.replaceAll("_", " ")}</dt>
              <dd className="mt-0.5 text-sm font-semibold text-indigo-800">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer font-medium text-indigo-700">Ver datos y diagnósticos completos</summary>
        <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded bg-slate-950 p-3 text-[11px] text-slate-100">
          {JSON.stringify(result, null, 2)}
        </pre>
      </details>
    </section>
  );
}

export function ToolError({ message, onRetry }: { message: string | null; onRetry?: () => void }) {
  if (!message) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert" aria-live="assertive">
      <span>{message}</span>
      {onRetry && <button type="button" onClick={onRetry} className="font-semibold underline">Reintentar</button>}
    </div>
  );
}
