"use client";

import { useState } from "react";
import { getAdvanced, postAdvanced } from "@/lib/api";
import type { CalculateRequest } from "@/lib/types";
import { OCTAVE_BANDS } from "@/lib/types";
import { useLicense } from "@/context/LicenseProvider";
import { Card, CardTitle } from "@/components/ui/Card";
import { FeatureGate } from "@/components/ui/FeatureGate";
import { TabContainer } from "@/components/ui/TabContainer";
import { ToolError, ToolResult } from "@/components/ui/ToolResult";

type Tool = "single" | "double" | "noise" | "duct" | "flanking" | "targets";

export function IsolationCalculators({ room, onResult }: { room: CalculateRequest; onResult?: (name: string, result: unknown) => void }) {
  const { apiKey } = useLicense();
  const [tool, setTool] = useState<Tool>("single");
  const [single, setSingle] = useState({ mass: 50, thick: 0.1, material: "concreto" });
  const [doublePanel, setDoublePanel] = useState({ m1: 50, m2: 20, gap: 0.1, stud: true, absorption: 0.3 });
  const [noiseType, setNoiseType] = useState<"nc" | "nr">("nc");
  const [noise, setNoise] = useState<Record<string, string>>({ "125": "50", "250": "45", "500": "40", "1000": "35", "2000": "30", "4000": "25" });
  const [duct, setDuct] = useState({ width: 0.5, height: 0.3, length: 4, alpha: 0.5 });
  const [flanking, setFlanking] = useState({ direct: 55, first: 45, second: 50 });
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    try {
      let response: Record<string, unknown>;
      if (tool === "single") {
        response = await postAdvanced("design/isolation/single-panel", { mass_per_area_kgm2: single.mass, thickness_m: single.thick, material_type: single.material }, apiKey);
      } else if (tool === "double") {
        response = await postAdvanced("design/isolation/double-panel", { m1_kgm2: doublePanel.m1, m2_kgm2: doublePanel.m2, gap_m: doublePanel.gap, stud_connection: doublePanel.stud, cavity_absorption: doublePanel.absorption }, apiKey);
      } else if (tool === "noise") {
        response = await postAdvanced(`design/isolation/${noiseType}`, { spl: Object.fromEntries(Object.entries(noise).map(([band, value]) => [band, Number(value)])) }, apiKey);
      } else if (tool === "duct") {
        response = await postAdvanced("design/isolation/duct-attenuation", { width_m: duct.width, height_m: duct.height, length_m: duct.length, absorption_coefficients: duct.alpha, lined_perimeter_fraction: 1 }, apiKey);
      } else if (tool === "flanking") {
        response = await postAdvanced("design/isolation/flanking", { direct_tl_db: flanking.direct, flanking_paths_tl_db: [flanking.first, flanking.second] }, apiKey);
      } else {
        const [ncTargets, nrTargets] = await Promise.all([
          getAdvanced<Record<string, unknown>>("design/isolation/nc-targets", apiKey),
          getAdvanced<Record<string, unknown>>("design/isolation/nr-targets", apiKey),
        ]);
        response = { nc_targets: ncTargets, nr_targets: nrTargets };
      }

      if ((tool === "single" || tool === "double") && room.uso && typeof response.stc === "number" && typeof response.rw === "number") {
        try {
          const comparison = await postAdvanced<Record<string, unknown>>("design/isolation/target-comparison", { uso: room.uso, stc: response.stc, rw: response.rw }, apiKey);
          response = { ...response, room_use_target_comparison: comparison };
        } catch {
          response = { ...response, target_comparison_note: `No hay objetivo de aislamiento configurado para ${room.uso}.` };
        }
      }
      setResult(response);
      onResult?.(`isolation_${tool}`, response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo calcular el aislamiento.");
    } finally {
      setLoading(false);
    }
  }

  const thirdOctave = result?.third_octave_tl as Record<string, number> | undefined;

  return (
    <Card>
      <CardTitle>Aislamiento acústico <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">PAID</span></CardTitle>
      <FeatureGate feature="isolation">
        <TabContainer compact activeTab={tool} onTabChange={(key) => { setTool(key as Tool); setResult(null); setError(null); }} label="Herramientas de aislamiento" tabs={[{ key: "single", label: "Panel simple" }, { key: "double", label: "Doble hoja" }, { key: "noise", label: "NC / NR" }, { key: "duct", label: "Conducto" }, { key: "flanking", label: "Flancos" }, { key: "targets", label: "Objetivos" }]}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <NumberField id="aisl-simple-masa" label="Masa (kg/m²)" value={single.mass} onChange={(value) => setSingle((current) => ({ ...current, mass: value }))} />
            <NumberField id="aisl-simple-espesor" label="Espesor (m)" value={single.thick} step={0.001} onChange={(value) => setSingle((current) => ({ ...current, thick: value }))} />
            <div><label htmlFor="aisl-simple-material" className="block text-xs font-medium text-gray-600">Material estructural</label><select id="aisl-simple-material" value={single.material} onChange={(event) => setSingle((current) => ({ ...current, material: event.target.value }))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm"><option value="concreto">Concreto</option><option value="yeso">Yeso</option><option value="vidrio">Vidrio</option><option value="madera">Madera</option></select></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <NumberField id="aisl-doble-m1" label="Masa hoja 1" value={doublePanel.m1} onChange={(value) => setDoublePanel((current) => ({ ...current, m1: value }))} />
            <NumberField id="aisl-doble-m2" label="Masa hoja 2" value={doublePanel.m2} onChange={(value) => setDoublePanel((current) => ({ ...current, m2: value }))} />
            <NumberField id="aisl-doble-camara" label="Cámara (m)" value={doublePanel.gap} step={0.01} onChange={(value) => setDoublePanel((current) => ({ ...current, gap: value }))} />
            <NumberField id="aisl-doble-alpha" label="Absorción cámara" value={doublePanel.absorption} step={0.05} onChange={(value) => setDoublePanel((current) => ({ ...current, absorption: value }))} />
            <label className="flex items-center gap-2 text-xs text-gray-600"><input id="aisl-doble-stud" type="checkbox" checked={doublePanel.stud} onChange={(event) => setDoublePanel((current) => ({ ...current, stud: event.target.checked }))} /> Montantes rígidos</label>
          </div>
          <div>
            <div className="mb-3 flex gap-4"><label htmlFor="aisl-noise-nc" className="text-xs"><input id="aisl-noise-nc" type="radio" name="aisl-noise-curve" checked={noiseType === "nc"} onChange={() => setNoiseType("nc")} /> NC</label><label htmlFor="aisl-noise-nr" className="text-xs"><input id="aisl-noise-nr" type="radio" name="aisl-noise-curve" checked={noiseType === "nr"} onChange={() => setNoiseType("nr")} /> NR</label></div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">{OCTAVE_BANDS.map((band) => <div key={band}><label htmlFor={`aisl-nc-${band}`} className="block text-xs text-gray-600">{band} Hz SPL</label><input id={`aisl-nc-${band}`} type="number" value={noise[band]} onChange={(event) => setNoise((current) => ({ ...current, [band]: event.target.value }))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>)}</div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"><NumberField id="duct-width" label="Ancho (m)" value={duct.width} step={0.05} onChange={(value) => setDuct((current) => ({ ...current, width: value }))} /><NumberField id="duct-height" label="Alto (m)" value={duct.height} step={0.05} onChange={(value) => setDuct((current) => ({ ...current, height: value }))} /><NumberField id="duct-length" label="Longitud (m)" value={duct.length} step={0.1} onChange={(value) => setDuct((current) => ({ ...current, length: value }))} /><NumberField id="duct-alpha" label="Absorción revestimiento" value={duct.alpha} step={0.05} onChange={(value) => setDuct((current) => ({ ...current, alpha: value }))} /></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><NumberField id="flanking-direct" label="TL directo (dB)" value={flanking.direct} onChange={(value) => setFlanking((current) => ({ ...current, direct: value }))} /><NumberField id="flanking-first" label="Flanco 1 (dB)" value={flanking.first} onChange={(value) => setFlanking((current) => ({ ...current, first: value }))} /><NumberField id="flanking-second" label="Flanco 2 (dB)" value={flanking.second} onChange={(value) => setFlanking((current) => ({ ...current, second: value }))} /></div>
          <p className="text-sm text-gray-600">Consulta objetivos NC y NR por uso, con su base y advertencia de no certificación.</p>
        </TabContainer>
        <button type="button" onClick={() => void run()} disabled={loading} className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Calculando…" : tool === "targets" ? "Cargar objetivos" : "Calcular"}</button>
        <ToolError message={error} onRetry={() => void run()} />
        {thirdOctave && <ThirdOctaveTable values={thirdOctave} />}
        {result && <ToolResult result={result} title="Resultado de aislamiento y supuestos" />}
      </FeatureGate>
    </Card>
  );
}

function NumberField({ id, label, value, step = 1, onChange }: { id: string; label: string; value: number; step?: number; onChange: (value: number) => void }) {
  return <div><label htmlFor={id} className="block text-xs font-medium text-gray-600">{label}</label><input id={id} type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>;
}

function ThirdOctaveTable({ values }: { values: Record<string, number> }) {
  return <div className="mt-4 overflow-x-auto"><h3 className="mb-2 text-sm font-semibold">Pérdida por transmisión en tercio de octava</h3><table className="w-full text-xs"><thead><tr>{Object.keys(values).map((band) => <th key={band} className="px-1 text-right">{band}</th>)}</tr></thead><tbody><tr>{Object.values(values).map((value, index) => <td key={index} className="px-1 text-right">{value.toFixed(1)}</td>)}</tr></tbody></table></div>;
}
