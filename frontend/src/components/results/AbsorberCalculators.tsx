"use client";

import { useState } from "react";
import { postAdvanced } from "@/lib/api";
import type { CalculateRequest } from "@/lib/types";
import { OCTAVE_BANDS } from "@/lib/types";
import { useLicense } from "@/context/LicenseProvider";
import { Card, CardTitle } from "@/components/ui/Card";
import { FeatureGate } from "@/components/ui/FeatureGate";
import { TabContainer } from "@/components/ui/TabContainer";
import { ToolError, ToolResult } from "@/components/ui/ToolResult";

type AbsorberType = "porous" | "helmholtz" | "membrane" | "area";

export function AbsorberCalculators({ room, onResult }: { room: CalculateRequest; onResult?: (name: string, result: unknown) => void }) {
  const { apiKey } = useLicense();
  const [activeType, setActiveType] = useState<AbsorberType>("porous");
  const [porous, setPorous] = useState({ thickness: 0.05, flow: 10000, density: 100, gap: 0, angle: 0 });
  const [helmholtz, setHelmholtz] = useState({ neckArea: 0.01, cavityVol: 0.1, neckLen: 0.05, neckRadius: 0.02 });
  const [membrane, setMembrane] = useState({ massArea: 10, airGap: 0.1 });
  const [missing, setMissing] = useState(5);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(type = activeType) {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let path: string;
      let body: Record<string, unknown>;
      if (type === "porous") {
        path = "design/absorbers/porous";
        body = { thickness_m: porous.thickness, flow_resistivity: porous.flow, density_kgm3: porous.density, air_gap_m: porous.gap, incidence_angle_deg: porous.angle, environment: room.environment };
      } else if (type === "helmholtz") {
        path = "design/absorbers/helmholtz";
        body = { neck_area_m2: helmholtz.neckArea, cavity_volume_m3: helmholtz.cavityVol, neck_length_m: helmholtz.neckLen, neck_radius_m: helmholtz.neckRadius, environment: room.environment };
      } else if (type === "membrane") {
        path = "design/absorbers/membrane";
        body = { mass_per_area_kgm2: membrane.massArea, air_gap_m: membrane.airGap };
      } else {
        path = "design/absorbers/recommended-area";
        body = {
          absorption_coefficients: { "125": 0.2, "250": 0.6, "500": 0.85, "1000": 0.9, "2000": 0.85, "4000": 0.8 },
          missing_absorption_m2_sabins: Object.fromEntries(OCTAVE_BANDS.map((band) => [band, missing])),
          installation_mode: "added",
          available_area_m2: room.largo * room.alto,
        };
      }
      const response = await postAdvanced<Record<string, unknown>>(path, body, apiKey);
      setResult(response);
      onResult?.(`absorber_${type}`, response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo calcular el absorbente.");
    } finally {
      setLoading(false);
    }
  }

  const alpha = result?.alpha as Record<string, number> | undefined;

  return (
    <Card>
      <CardTitle>Absorbentes y diagnóstico <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">PAID</span></CardTitle>
      <FeatureGate feature="absorbers">
        <TabContainer compact activeTab={activeType} onTabChange={(key) => { setActiveType(key as AbsorberType); setResult(null); setError(null); }} label="Tipos de absorbente" tabs={[{ key: "porous", label: "Poroso" }, { key: "helmholtz", label: "Helmholtz" }, { key: "membrane", label: "Membrana" }, { key: "area", label: "Área necesaria" }]}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <NumberField id="abs-poroso-espesor" label="Espesor (m)" value={porous.thickness} step={0.005} onChange={(value) => setPorous((current) => ({ ...current, thickness: value }))} />
            <NumberField id="abs-poroso-flow" label="Resistividad σ" value={porous.flow} onChange={(value) => setPorous((current) => ({ ...current, flow: value }))} />
            <NumberField id="abs-poroso-densidad" label="Densidad (kg/m³)" value={porous.density} onChange={(value) => setPorous((current) => ({ ...current, density: value }))} />
            <NumberField id="abs-poroso-gap" label="Cámara de aire (m)" value={porous.gap} step={0.01} onChange={(value) => setPorous((current) => ({ ...current, gap: value }))} />
            <NumberField id="abs-poroso-angle" label="Incidencia (°)" value={porous.angle} step={1} onChange={(value) => setPorous((current) => ({ ...current, angle: value }))} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <NumberField id="abs-helmholtz-cuello-area" label="Área cuello (m²)" value={helmholtz.neckArea} step={0.001} onChange={(value) => setHelmholtz((current) => ({ ...current, neckArea: value }))} />
            <NumberField id="abs-helmholtz-cavidad-vol" label="Volumen cavidad (m³)" value={helmholtz.cavityVol} step={0.01} onChange={(value) => setHelmholtz((current) => ({ ...current, cavityVol: value }))} />
            <NumberField id="abs-helmholtz-cuello-len" label="Longitud cuello (m)" value={helmholtz.neckLen} step={0.005} onChange={(value) => setHelmholtz((current) => ({ ...current, neckLen: value }))} />
            <NumberField id="abs-helmholtz-cuello-radio" label="Radio cuello (m)" value={helmholtz.neckRadius} step={0.001} onChange={(value) => setHelmholtz((current) => ({ ...current, neckRadius: value }))} />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <NumberField id="abs-membrana-masa" label="Masa superficial (kg/m²)" value={membrane.massArea} step={0.5} onChange={(value) => setMembrane((current) => ({ ...current, massArea: value }))} />
            <NumberField id="abs-membrana-camara" label="Cámara de aire (m)" value={membrane.airGap} step={0.01} onChange={(value) => setMembrane((current) => ({ ...current, airGap: value }))} />
          </div>
          <div>
            <NumberField id="abs-missing" label="Absorción faltante uniforme (m² sabins)" value={missing} step={0.5} onChange={setMissing} />
            <p className="mt-2 text-xs text-gray-500">Compara un panel genérico con el área disponible de una pared de la sala actual.</p>
          </div>
        </TabContainer>
        <button type="button" onClick={() => void run()} disabled={loading} className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
          {loading ? "Calculando…" : activeType === "area" ? "Calcular área" : "Predecir α(f)"}
        </button>
        <ToolError message={error} onRetry={() => void run()} />
        {alpha && (
          <div className="mt-4 overflow-x-auto" aria-label="Coeficientes de absorción calculados">
            <table className="w-full text-sm"><thead><tr><th className="text-left">Banda</th>{OCTAVE_BANDS.map((band) => <th key={band} className="px-2 text-right">{band} Hz</th>)}</tr></thead><tbody><tr><th className="text-left">α</th>{OCTAVE_BANDS.map((band) => <td key={band} className="px-2 text-right font-semibold">{alpha[band]?.toFixed(3)}</td>)}</tr></tbody></table>
          </div>
        )}
        {result && <ToolResult result={result} title="Modelo y límites de validez" />}
      </FeatureGate>
    </Card>
  );
}

function NumberField({ id, label, value, step = 1, onChange }: { id: string; label: string; value: number; step?: number; onChange: (value: number) => void }) {
  return <div><label htmlFor={id} className="block text-xs font-medium text-gray-600">{label}</label><input id={id} type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>;
}
