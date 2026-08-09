"use client";

import { useState } from "react";
import { postAdvanced } from "@/lib/api";
import type { CalculateRequest } from "@/lib/types";
import { useLicense } from "@/context/LicenseProvider";
import { Card, CardTitle } from "@/components/ui/Card";
import { FeatureGate } from "@/components/ui/FeatureGate";
import { TabContainer } from "@/components/ui/TabContainer";
import { ToolError, ToolResult } from "@/components/ui/ToolResult";

type DiffuserType = "qrd" | "skyline" | "diagnostics";

export function DiffuserCalculators({ room, onResult }: { room: CalculateRequest; onResult?: (name: string, result: unknown) => void }) {
  const { apiKey } = useLicense();
  const [activeType, setActiveType] = useState<DiffuserType>("qrd");
  const [qrd, setQrd] = useState({ freq: 1000, prime: 17, width: 0.05 });
  const [skyline, setSkyline] = useState({ freq: 1000, grid: 7, size: 0.05 });
  const [polarValues, setPolarValues] = useState("1, 0.8, 0.45, 0.8, 1");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    try {
      const path = activeType === "qrd" ? "design/diffusers/qrd" : activeType === "skyline" ? "design/diffusers/skyline" : "design/diffusers/diffusion";
      const body = activeType === "qrd"
        ? { design_freq_hz: qrd.freq, prime_n: qrd.prime, well_width_m: qrd.width }
        : activeType === "skyline"
          ? { design_freq_hz: skyline.freq, grid_n: skyline.grid, well_size_m: skyline.size }
          : { polar_response: polarValues.split(/[\s,;]+/).filter(Boolean).map(Number), response_unit: "pressure" };
      const response = await postAdvanced<Record<string, unknown>>(path, body, apiKey);
      setResult(response);
      onResult?.(`diffuser_${activeType}`, response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo calcular el difusor.");
    } finally {
      setLoading(false);
    }
  }

  async function runPolar() {
    if (!apiKey || !result) return;
    setLoading(true);
    setError(null);
    try {
      const response = await postAdvanced<Record<string, unknown>>("design/diffusers/qrd/polar-response", {
        well_depths_m: result.well_depths_m,
        frequency_hz: qrd.freq,
        well_width_m: qrd.width,
        environment: room.environment,
      }, apiKey);
      setResult({ ...result, polar_response: response });
      onResult?.("diffuser_polar", response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo simular la respuesta polar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardTitle>Difusores y respuesta polar <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">PAID</span></CardTitle>
      <FeatureGate feature="diffusers">
        <TabContainer compact activeTab={activeType} onTabChange={(key) => { setActiveType(key as DiffuserType); setResult(null); setError(null); }} label="Tipos de difusor" tabs={[{ key: "qrd", label: "QRD (1D)" }, { key: "skyline", label: "Skyline (2D)" }, { key: "diagnostics", label: "Difusión medida" }]}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <NumberField id="dif-qrd-freq" label="Frec. diseño (Hz)" value={qrd.freq} onChange={(value) => setQrd((current) => ({ ...current, freq: value }))} />
            <NumberField id="dif-qrd-n" label="N solicitado" value={qrd.prime} onChange={(value) => setQrd((current) => ({ ...current, prime: value }))} />
            <NumberField id="dif-qrd-ancho" label="Ancho pozo (m)" value={qrd.width} step={0.01} onChange={(value) => setQrd((current) => ({ ...current, width: value }))} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <NumberField id="dif-skyline-freq" label="Frec. diseño (Hz)" value={skyline.freq} onChange={(value) => setSkyline((current) => ({ ...current, freq: value }))} />
            <NumberField id="dif-skyline-grid" label="Grid N×N" value={skyline.grid} onChange={(value) => setSkyline((current) => ({ ...current, grid: value }))} />
            <NumberField id="dif-skyline-celda" label="Tamaño celda (m)" value={skyline.size} step={0.01} onChange={(value) => setSkyline((current) => ({ ...current, size: value }))} />
          </div>
          <div>
            <label htmlFor="dif-polar-values" className="block text-xs font-medium text-gray-600">Respuesta polar (presión, separada por comas)</label>
            <textarea id="dif-polar-values" rows={3} value={polarValues} onChange={(event) => setPolarValues(event.target.value)} className="mt-1 w-full rounded border px-2 py-1.5 font-mono text-sm" />
            <p className="mt-1 text-xs text-gray-500">Calcula el coeficiente y explicita la normalización; no equivale a un ensayo ISO.</p>
          </div>
        </TabContainer>
        <button type="button" onClick={() => void run()} disabled={loading} className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Calculando…" : "Calcular difusor"}</button>
        {activeType === "qrd" && Array.isArray(result?.well_depths_m) && (
          <button type="button" onClick={() => void runPolar()} disabled={loading} className="mt-2 w-full rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">Simular respuesta polar con el ambiente actual</button>
        )}
        <ToolError message={error} onRetry={() => void run()} />
        {result && <ToolResult result={result} title="Construcción, rango útil y manufacturabilidad" />}
      </FeatureGate>
    </Card>
  );
}

function NumberField({ id, label, value, step = 1, onChange }: { id: string; label: string; value: number; step?: number; onChange: (value: number) => void }) {
  return <div><label htmlFor={id} className="block text-xs font-medium text-gray-600">{label}</label><input id={id} type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>;
}
