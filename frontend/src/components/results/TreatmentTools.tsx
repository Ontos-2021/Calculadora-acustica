"use client";

import { useState } from "react";
import { fetchInverseDesign, postAdvanced } from "@/lib/api";
import type { CalculateRequest, CalculateResponse, InverseDesignResponse } from "@/lib/types";
import { useLicense } from "@/context/LicenseProvider";
import { roomPayload } from "@/lib/room";
import { Card, CardTitle } from "@/components/ui/Card";
import { FeatureGate } from "@/components/ui/FeatureGate";
import { TabContainer } from "@/components/ui/TabContainer";
import { ToolError, ToolResult } from "@/components/ui/ToolResult";
import { InverseDesign } from "./InverseDesign";

interface Props {
  room: CalculateRequest;
  analysis: CalculateResponse;
  onResult?: (name: string, result: unknown) => void;
}

export function TreatmentTools({ room, analysis, onResult }: Props) {
  const { apiKey } = useLicense();
  const [targetUse, setTargetUse] = useState(room.uso ?? "home_studio");
  const [material, setMaterial] = useState("Panel acústico");
  const [area, setArea] = useState(10);
  const [surfaceIndex, setSurfaceIndex] = useState(5);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [inverse, setInverse] = useState<InverseDesignResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(kind: "inverse" | "optimize" | "verify") {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    try {
      if (kind === "inverse") {
        const response = await fetchInverseDesign({ ...roomPayload(room), target_uso: targetUse, include_placement: true }, apiKey);
        setInverse(response);
        setResult(response as unknown as Record<string, unknown>);
        onResult?.("treatment_inverse", response);
      } else if (kind === "optimize") {
        const response = await postAdvanced<Record<string, unknown>>("design/inverse/optimize", {
          ...roomPayload(room),
          target_uso: targetUse,
          candidate_materials: [material],
          available_area_m2: area,
          installation_mode: "replacement",
          max_materials: 3,
          area_step_m2: 0.25,
          include_pressure_map: true,
        }, apiKey);
        setResult(response);
        onResult?.("treatment_optimization", response);
      } else {
        const target = analysis.objetivo?.valores ?? Object.fromEntries(["125", "250", "500", "1000", "2000", "4000"].map((band) => [band, 0.3]));
        const response = await postAdvanced<Record<string, unknown>>("design/inverse/verify", {
          ...roomPayload(room),
          target_rt60: target,
          treatments: [{ material, area_m2: area, surface_index: surfaceIndex, installation_mode: "replacement" }],
        }, apiKey);
        setResult(response);
        onResult?.("treatment_verification", response);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo calcular el tratamiento.");
    } finally {
      setLoading(false);
    }
  }

  const sharedInputs = (
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div>
        <label htmlFor="treatment-target" className="block text-xs font-medium text-gray-600">Uso objetivo</label>
        <select id="treatment-target" value={targetUse} onChange={(event) => setTargetUse(event.target.value)} className="mt-1 w-full rounded border px-2 py-1.5 text-sm">
          <option value="home_studio">Home studio</option><option value="home_theater">Home theater</option><option value="aula">Aula</option><option value="sala_conferencias">Conferencias</option><option value="teatro">Teatro</option><option value="sala_conciertos">Conciertos</option><option value="iglesia">Iglesia</option><option value="restaurante">Restaurante</option>
        </select>
      </div>
      <div>
        <label htmlFor="treatment-material" className="block text-xs font-medium text-gray-600">Material candidato</label>
        <input id="treatment-material" value={material} onChange={(event) => setMaterial(event.target.value)} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" />
      </div>
      <div>
        <label htmlFor="treatment-area" className="block text-xs font-medium text-gray-600">Área disponible (m²)</label>
        <input id="treatment-area" type="number" min="0" step="0.25" value={area} onChange={(event) => setArea(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" />
      </div>
    </div>
  );

  return (
    <Card>
      <CardTitle>Tratamiento y verificación <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">PAID</span></CardTitle>
      <FeatureGate feature="inverse_design">
        {sharedInputs}
        <TabContainer compact label="Herramientas de tratamiento" tabs={[{ key: "inverse", label: "Necesidad" }, { key: "optimize", label: "Optimizar" }, { key: "verify", label: "Verificar plan" }]}>
          <div>
            <p className="mb-3 text-xs text-gray-600">Calcula absorción actual, faltante y colocación usando esta sala y su mapa modal.</p>
            <button type="button" disabled={loading} onClick={() => void run("inverse")} className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Calculando…" : "Calcular necesidad"}</button>
            {inverse && <div className="mt-4"><InverseDesign data={inverse} /></div>}
          </div>
          <div>
            <p className="mb-3 text-xs text-gray-600">Asigna área limitada y comprueba el resultado con un cálculo directo.</p>
            <button type="button" disabled={loading} onClick={() => void run("optimize")} className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Optimizando…" : "Optimizar tratamiento"}</button>
          </div>
          <div>
            <div className="mb-3">
              <label htmlFor="treatment-surface" className="block text-xs font-medium text-gray-600">Superficie a reemplazar (0–5)</label>
              <input id="treatment-surface" type="number" min="0" max="5" value={surfaceIndex} onChange={(event) => setSurfaceIndex(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" />
            </div>
            <button type="button" disabled={loading} onClick={() => void run("verify")} className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Verificando…" : "Verificar plan"}</button>
          </div>
        </TabContainer>
        <ToolError message={error} />
        {result && !inverse && <ToolResult result={result} title="Diagnóstico de tratamiento" />}
      </FeatureGate>
    </Card>
  );
}
