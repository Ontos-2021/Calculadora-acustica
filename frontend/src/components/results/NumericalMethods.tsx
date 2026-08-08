"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

type Tab = "impedance" | "fem2d" | "raytrace" | "hybrid";

export function NumericalMethods() {
  const [tab, setTab] = useState<Tab>("impedance");
  const [imp, setImp] = useState({ L: 5, W: 4, H: 3, Z: 10000 });
  const [fem, setFem] = useState({ W: 5, H: 4, nx: 15, ny: 15, modes: 3, exclude: "" });
  const [ray, setRay] = useState({ rays: 200, reflections: 20 });
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      let body: Record<string, unknown>;
      let url: string;
      if (tab === "impedance") {
        url = `${base}/api/v1/numerical/finite-impedance`;
        body = { L_m: imp.L, W_m: imp.W, H_m: imp.H, Z_wall: imp.Z, max_order: 3 };
      } else if (tab === "fem2d") {
        url = `${base}/api/v1/numerical/fem2d`;
        body = { width: fem.W, height: fem.H, grid_nx: fem.nx, grid_ny: fem.ny, num_modes: fem.modes, exclude_region: fem.exclude };
      } else if (tab === "raytrace") {
        url = `${base}/api/v1/numerical/ray-tracing`;
        body = {
          largo: imp.L, ancho: imp.W, alto: imp.H,
          superficies: Array(6).fill({ material: "Concreto" }),
          num_rays: ray.rays, max_reflections: ray.reflections,
        };
      } else {
        url = `${base}/api/v1/numerical/hybrid`;
        body = {
          largo: imp.L, ancho: imp.W, alto: imp.H,
          superficies: Array(6).fill({ material: "Concreto" }),
          num_rays: ray.rays,
        };
      }
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) setResult(await res.json());
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const r = result as Record<string, unknown> | null;

  return (
    <Card>
      <CardTitle>
        Métodos numéricos
        <span className="ml-2 rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">INVESTIGACIÓN</span>
      </CardTitle>

      <div className="mb-4 flex flex-wrap gap-2">
        {([
          { key: "impedance" as const, label: "Impedancia finita" },
          { key: "fem2d" as const, label: "FEM 2D" },
          { key: "raytrace" as const, label: "Ray tracing" },
          { key: "hybrid" as const, label: "Híbrido" },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => { setTab(key); setResult(null); }}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === key ? "bg-purple-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3">
        <div>
          <label className="block text-xs text-gray-500">Largo (m)</label>
          <input type="number" step="0.1" min="0.1" max="50" value={imp.L}
            className="mt-1 w-full rounded border px-2 py-1 text-sm"
            onChange={(e) => setImp(s => ({ ...s, L: Number(e.target.value) }))} />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Ancho (m)</label>
          <input type="number" step="0.1" min="0.1" max="50" value={imp.W}
            className="mt-1 w-full rounded border px-2 py-1 text-sm"
            onChange={(e) => setImp(s => ({ ...s, W: Number(e.target.value) }))} />
        </div>
        <div>
          <label className="block text-xs text-gray-500">Alto (m)</label>
          <input type="number" step="0.1" min="0.1" max="50" value={imp.H}
            className="mt-1 w-full rounded border px-2 py-1 text-sm"
            onChange={(e) => setImp(s => ({ ...s, H: Number(e.target.value) }))} />
        </div>
      </div>

      {tab === "impedance" && (
        <div className="mb-4">
          <div>
            <label className="block text-xs text-gray-500">Impedancia de pared (rayl)</label>
            <input type="number" min="1" max="1e8" value={imp.Z}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setImp(s => ({ ...s, Z: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      {tab === "fem2d" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500">Grid NX</label>
            <input type="number" min="5" max="50" value={fem.nx}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setFem(s => ({ ...s, nx: Number(e.target.value) }))} />
          </div>
          <div>
            <label className="block text-xs text-gray-500">Grid NY</label>
            <input type="number" min="5" max="50" value={fem.ny}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setFem(s => ({ ...s, ny: Number(e.target.value) }))} />
          </div>
          <div>
            <label className="block text-xs text-gray-500">Modos</label>
            <input type="number" min="1" max="20" value={fem.modes}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setFem(s => ({ ...s, modes: Number(e.target.value) }))} />
          </div>
          <div>
            <label className="block text-xs text-gray-500">Exclusión (x0,y0,x1,y1)</label>
            <input type="text" placeholder="ej: 2,0,4,2" value={fem.exclude}
              className="mt-1 w-full rounded border px-2 py-1 text-sm font-mono"
              onChange={(e) => setFem(s => ({ ...s, exclude: e.target.value }))} />
          </div>
        </div>
      )}

      {tab !== "fem2d" && tab !== "impedance" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500">Rayos</label>
            <input type="number" min="50" max="5000" value={ray.rays}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setRay(s => ({ ...s, rays: Number(e.target.value) }))} />
          </div>
          <div>
            <label className="block text-xs text-gray-500">Máx. reflexiones</label>
            <input type="number" min="5" max="100" value={ray.reflections}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setRay(s => ({ ...s, reflections: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      <button
        onClick={calculate}
        disabled={loading}
        className="w-full rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
      >
        {loading ? "Calculando..." : "Ejecutar"}
      </button>

      {result && r && !("error" in result) && (
        <div className="mt-4 space-y-3">
          {tab === "impedance" && (() => {
            const axial = r.axial_modes as Record<string, unknown>[];
            if (!axial) return null;
            return (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-gray-600">Modos axiales con pared finita</h4>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="px-2 py-1 text-left text-xs text-gray-500">n</th>
                      <th className="px-2 py-1 text-right text-xs text-gray-500">f (Hz)</th>
                      <th className="px-2 py-1 text-right text-xs text-gray-500">f rígida (Hz)</th>
                      <th className="px-2 py-1 text-right text-xs text-gray-500">Desplazamiento</th>
                      <th className="px-2 py-1 text-right text-xs text-gray-500">RT60 (s)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {axial.map((m, i) => (
                      <tr key={i} className="border-b">
                        <td className="px-2 py-1 text-xs">{m.n as number}</td>
                        <td className="px-2 py-1 text-right text-xs font-medium">{(m.frequency_hz as number).toFixed(1)}</td>
                        <td className="px-2 py-1 text-right text-xs text-gray-500">{(m.rigid_frequency_hz as number).toFixed(1)}</td>
                        <td className="px-2 py-1 text-right text-xs">{(m.shift_hz as number).toFixed(2)}</td>
                        <td className="px-2 py-1 text-right text-xs">{(m.rt60_estimate_s as number).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })()}

          {tab === "fem2d" && (() => {
            const modes = r.modes as Record<string, unknown>[];
            if (!modes || modes.length === 0) return <p className="text-xs text-gray-400">No se encontraron modos (malla muy pequeña)</p>;
            return (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-gray-600">Modos FEM 2D</h4>
                {modes.map((m, i) => (
                  <div key={i} className="mb-2 rounded bg-gray-50 p-2">
                    <Badge variant="info">Modo {m.mode as number}: {(m.frequency_hz as number).toFixed(1)} Hz</Badge>
                    <div className="mt-1 grid" style={{ gridTemplateColumns: `repeat(${(m.grid_x as number[]).length}, 1fr)` }}>
                      {(m.shape_2d as number[][]).map((row, j) => (
                        <div key={j} className="flex flex-col-reverse">
                          {row.map((val, k) => (
                            <div key={k}
                              className="h-2"
                              style={{ backgroundColor: `rgba(124, 58, 237, ${Math.abs(val)})` }}
                              title={`(${k},${row.length - 1 - j}): ${val.toFixed(2)}`}
                            />
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            );
          })()}

          {tab === "raytrace" && (() => {
            const energy = r.energy_db as number[];
            const times = r.energy_time_s as number[];
            if (!energy || energy.length === 0) return <p className="text-xs text-gray-400">Sin datos de energía</p>;
            return (
              <div>
                <Badge variant="warning">RT60 ≈ {(r.rt60_estimate_s as number).toFixed(2)}s</Badge>
                <div className="mt-2 h-24">
                  <svg viewBox={`0 0 ${energy.length} 60`} className="h-full w-full">
                    {energy.slice(0, Math.min(energy.length, 200)).map((v, i) => (
                      <line key={i} x1={i} y1={30 - (v + 60) * 0.5} x2={i + 1} y2={30 - (v + 60) * 0.5} stroke="#7c3aed" strokeWidth={1} />
                    ))}
                  </svg>
                </div>
              </div>
            );
          })()}

          {tab === "hybrid" && (() => {
            const h = r.hybrid as Record<string, unknown>;
            const ism = r.ism as Record<string, unknown>;
            const ray2 = r.ray_tracing as Record<string, unknown>;
            if (!h) return null;
            return (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="info">f<sub>Sch</sub> = {(r.schroeder_frequency_hz as number).toFixed(0)} Hz</Badge>
                  <Badge variant="warning">RT60 híbrido = {(h.rt60_estimate_s as number).toFixed(2)}s</Badge>
                </div>
                <p className="text-xs text-gray-500">
                  ISM: peso {(h.weight_ism as number * 100).toFixed(0)}% | 
                  Ray tracing: peso {(h.weight_ray_tracing as number * 100).toFixed(0)}%
                </p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded bg-indigo-50 p-2 text-xs">
                    <span className="font-medium">ISM</span>
                    <p>Fuentes: {(ism?.image_sources as number) || 0}</p>
                    <p>T20: {((ism?.iso_3382 as Record<string, unknown>)?.T20 as number || 0).toFixed(2)}s</p>
                  </div>
                  <div className="rounded bg-purple-50 p-2 text-xs">
                    <span className="font-medium">Ray tracing</span>
                    <p>Rayos: {ray2?.num_rays as number || 0}</p>
                    <p>RT60: {(ray2?.rt60_estimate_s as number || 0).toFixed(2)}s</p>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </Card>
  );
}
