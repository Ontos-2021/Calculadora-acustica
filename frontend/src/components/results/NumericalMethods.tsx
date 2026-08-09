"use client";

import { useState } from "react";
import { postAdvanced } from "@/lib/api";
import type { CalculateRequest } from "@/lib/types";
import { useLicense } from "@/context/LicenseProvider";
import { roomPayload } from "@/lib/room";
import { Card, CardTitle } from "@/components/ui/Card";
import { FeatureGate } from "@/components/ui/FeatureGate";
import { TabContainer } from "@/components/ui/TabContainer";
import { ToolError, ToolResult } from "@/components/ui/ToolResult";

type Tool = "impedance" | "fem2d" | "polygon" | "raytrace" | "hybrid";

export function NumericalMethods({ room, onResult }: { room: CalculateRequest; onResult?: (name: string, result: unknown) => void }) {
  const { apiKey, hasEntitlement } = useLicense();
  const [tool, setTool] = useState<Tool>("impedance");
  const [impedance, setImpedance] = useState(10000);
  const [grid, setGrid] = useState({ nx: 18, ny: 18, modes: 4 });
  const [polygon, setPolygon] = useState(() => `0,0; ${room.largo},0; ${room.largo},${room.ancho}; 0,${room.ancho}`);
  const [rays, setRays] = useState({ count: 300, reflections: 20, scattering: 0.1 });
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function sourceReceiver() {
    return {
      source: [room.largo * 0.22, room.ancho * 0.35, room.alto * 0.55] as [number, number, number],
      receiver: [room.largo * 0.72, room.ancho * 0.62, room.alto * 0.4] as [number, number, number],
    };
  }

  function polygonVertices(): [number, number][] {
    const vertices = polygon.split(";").map((point) => point.trim().split(",").map(Number));
    if (vertices.length < 3 || vertices.some((point) => point.length !== 2 || point.some((value) => !Number.isFinite(value)))) {
      throw new Error("Define al menos tres vértices como x,y; x,y; …");
    }
    return vertices as [number, number][];
  }

  async function run() {
    if (!apiKey) return;
    if (tool === "polygon" && !hasEntitlement("research")) {
      setError("El FEM poligonal requiere el entitlement research.");
      return;
    }
    setLoading(true); setError(null);
    try {
      let path: string;
      let body: Record<string, unknown>;
      if (tool === "impedance") {
        path = "numerical/finite-impedance";
        body = { L_m: room.largo, W_m: room.ancho, H_m: room.alto, Z_wall: impedance, max_order: 3, environment: room.environment };
      } else if (tool === "fem2d") {
        path = "numerical/fem2d";
        body = { width: room.largo, height: room.ancho, grid_nx: grid.nx, grid_ny: grid.ny, num_modes: grid.modes, environment: room.environment };
      } else if (tool === "polygon") {
        path = "numerical/fem2d/polygon";
        body = { vertices: polygonVertices(), target_edge_length_m: Math.max(0.15, Math.min(room.largo, room.ancho) / 15), num_modes: grid.modes, room_height_m: room.alto, max_vertical_order: 1, environment: room.environment };
      } else if (tool === "raytrace") {
        path = "numerical/ray-tracing";
        body = { ...roomPayload(room), ...sourceReceiver(), num_rays: rays.count, max_reflections: rays.reflections, scattering: rays.scattering, max_time_s: 1, seed: 42 };
      } else {
        path = "numerical/hybrid";
        body = { ...roomPayload(room), ...sourceReceiver(), num_rays: rays.count, max_reflections: rays.reflections, max_ism_order: 5, seed: 42 };
      }
      const response = await postAdvanced<Record<string, unknown>>(path, body, apiKey);
      setResult(response);
      onResult?.(`numerical_${tool}`, response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo ejecutar el método numérico.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardTitle>Métodos numéricos <span className="ml-2 rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-800">INVESTIGACIÓN</span></CardTitle>
      <FeatureGate feature="numerical">
        <div className="mb-4 rounded-lg bg-purple-50 p-3 text-xs leading-5 text-purple-900">
          Geometría actual: <strong>{room.largo} × {room.ancho} × {room.alto} m</strong>. Todos los métodos usan estas dimensiones, superficies y condiciones ambientales. Comprueba convergencia de malla/rayos antes de tomar decisiones.
        </div>
        <TabContainer compact activeTab={tool} onTabChange={(key) => { setTool(key as Tool); setResult(null); setError(null); }} label="Métodos numéricos" tabs={[{ key: "impedance", label: "Impedancia" }, { key: "fem2d", label: "FEM 2D" }, { key: "polygon", label: "FEM polígono" }, { key: "raytrace", label: "Ray tracing" }, { key: "hybrid", label: "Híbrido" }]}>
          <NumberField id="num-imp-z" label="Impedancia compleja, parte real (rayl)" value={impedance} onChange={setImpedance} />
          <MeshFields grid={grid} setGrid={setGrid} />
          <div><label htmlFor="num-polygon" className="block text-xs font-medium text-gray-600">Vértices x,y separados por punto y coma</label><textarea id="num-polygon" rows={3} value={polygon} onChange={(event) => setPolygon(event.target.value)} className="mt-1 w-full rounded border px-2 py-1.5 font-mono text-sm" />{!hasEntitlement("research") && <p className="mt-2 text-xs text-amber-800">Tu licencia incluye numérico pero no el endpoint research poligonal.</p>}<div className="mt-3"><MeshFields grid={grid} setGrid={setGrid} /></div></div>
          <RayFields rays={rays} setRays={setRays} />
          <RayFields rays={rays} setRays={setRays} />
        </TabContainer>
        <button type="button" onClick={() => void run()} disabled={loading || (tool === "polygon" && !hasEntitlement("research"))} className="mt-4 w-full rounded-lg bg-purple-700 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-800 disabled:opacity-50">{loading ? "Ejecutando…" : "Ejecutar con la sala actual"}</button>
        <ToolError message={error} onRetry={() => void run()} />
        {result && <ToolResult result={result} title="Resultado numérico y estado de investigación" />}
      </FeatureGate>
    </Card>
  );
}

function MeshFields({ grid, setGrid }: { grid: { nx: number; ny: number; modes: number }; setGrid: React.Dispatch<React.SetStateAction<{ nx: number; ny: number; modes: number }>> }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><NumberField id="num-fem-nx" label="Nodos X" value={grid.nx} onChange={(value) => setGrid((current) => ({ ...current, nx: value }))} /><NumberField id="num-fem-ny" label="Nodos Y" value={grid.ny} onChange={(value) => setGrid((current) => ({ ...current, ny: value }))} /><NumberField id="num-fem-modos" label="Modos" value={grid.modes} onChange={(value) => setGrid((current) => ({ ...current, modes: value }))} /></div>;
}

function RayFields({ rays, setRays }: { rays: { count: number; reflections: number; scattering: number }; setRays: React.Dispatch<React.SetStateAction<{ count: number; reflections: number; scattering: number }>> }) {
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-3"><NumberField id="num-ray-rayos" label="Rayos" value={rays.count} onChange={(value) => setRays((current) => ({ ...current, count: value }))} /><NumberField id="num-ray-reflexiones" label="Reflexiones" value={rays.reflections} onChange={(value) => setRays((current) => ({ ...current, reflections: value }))} /><NumberField id="num-ray-scattering" label="Scattering" value={rays.scattering} step={0.05} onChange={(value) => setRays((current) => ({ ...current, scattering: value }))} /></div>;
}

function NumberField({ id, label, value, step = 1, onChange }: { id: string; label: string; value: number; step?: number; onChange: (value: number) => void }) {
  return <div><label htmlFor={id} className="block text-xs font-medium text-gray-600">{label}</label><input id={id} type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>;
}
