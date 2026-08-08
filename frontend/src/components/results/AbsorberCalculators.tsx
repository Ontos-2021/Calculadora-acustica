"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

type AbsorberType = "porous" | "helmholtz" | "membrane";

interface AlphaChartProps {
  alpha: Record<string, number>;
  f0?: number;
}

function AlphaChart({ alpha, f0 }: AlphaChartProps) {
  const maxVal = Math.max(...Object.values(alpha), 0.1);
  return (
    <div className="mt-3">
      <div className="flex items-end gap-1" style={{ height: 80 }}>
        {BANDAS.map((b) => (
          <div key={b} className="flex flex-1 flex-col items-center">
            <div
              className="w-full rounded-t bg-indigo-500 transition-all"
              style={{ height: `${(alpha[b] / maxVal) * 100}%`, minHeight: alpha[b] > 0 ? 4 : 0 }}
            />
            <span className="mt-1 text-[10px] text-gray-500">{b}</span>
          </div>
        ))}
      </div>
      {f0 && f0 > 0 && (
        <p className="mt-2 text-center text-xs font-medium text-indigo-600">
          Sintonizado a {f0.toFixed(0)} Hz
        </p>
      )}
    </div>
  );
}

export function AbsorberCalculators() {
  const [activeType, setActiveType] = useState<AbsorberType>("porous");
  const [porous, setPorous] = useState({ thickness: 0.05, flow: 10000, density: 100 });
  const [helmholtz, setHelmholtz] = useState({ neckArea: 0.01, cavityVol: 0.1, neckLen: 0.05, neckRadius: 0.02 });
  const [membrane, setMembrane] = useState({ massArea: 10, airGap: 0.1 });
  const [result, setResult] = useState<{ f0: number; Q: number; alpha: Record<string, number> } | null>(null);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const base = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}`;
      let body: Record<string, number>;
      let url: string;
      if (activeType === "porous") {
        url = `${base}/api/v1/design/absorbers/porous`;
        body = { thickness_m: porous.thickness, flow_resistivity: porous.flow, density_kgm3: porous.density };
      } else if (activeType === "helmholtz") {
        url = `${base}/api/v1/design/absorbers/helmholtz`;
        body = { neck_area_m2: helmholtz.neckArea, cavity_volume_m3: helmholtz.cavityVol, neck_length_m: helmholtz.neckLen, neck_radius_m: helmholtz.neckRadius };
      } else {
        url = `${base}/api/v1/design/absorbers/membrane`;
        body = { mass_per_area_kgm2: membrane.massArea, air_gap_m: membrane.airGap };
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

  return (
    <Card>
      <CardTitle>
        Calculadora de absorbentes
        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">PAID</span>
      </CardTitle>

      <div className="mb-4 flex gap-2">
        {([
          { key: "porous", label: "Poroso" },
          { key: "helmholtz", label: "Helmholtz" },
          { key: "membrane", label: "Membrana" },
        ] as const).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => { setActiveType(key); setResult(null); }}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              activeType === key ? "bg-indigo-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeType === "porous" && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div>
            <label htmlFor="abs-poroso-espesor" className="block text-xs text-gray-500">Espesor (m)</label>
            <input id="abs-poroso-espesor" type="number" step="0.005" min="0.01" max="1" value={porous.thickness}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setPorous(p => ({ ...p, thickness: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="abs-poroso-flow" className="block text-xs text-gray-500">Resistividad flujo σ</label>
            <input id="abs-poroso-flow" type="number" min="1000" max="1000000" value={porous.flow}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setPorous(p => ({ ...p, flow: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="abs-poroso-densidad" className="block text-xs text-gray-500">Densidad (kg/m³)</label>
            <input id="abs-poroso-densidad" type="number" min="10" max="500" value={porous.density}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setPorous(p => ({ ...p, density: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      {activeType === "helmholtz" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="abs-helmholtz-cuello-area" className="block text-xs text-gray-500">Área cuello (m²)</label>
            <input id="abs-helmholtz-cuello-area" type="number" step="0.001" min="0.001" max="1" value={helmholtz.neckArea}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setHelmholtz(h => ({ ...h, neckArea: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="abs-helmholtz-cavidad-vol" className="block text-xs text-gray-500">Volumen cavidad (m³)</label>
            <input id="abs-helmholtz-cavidad-vol" type="number" step="0.01" min="0.01" max="10" value={helmholtz.cavityVol}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setHelmholtz(h => ({ ...h, cavityVol: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="abs-helmholtz-cuello-len" className="block text-xs text-gray-500">Longitud cuello (m)</label>
            <input id="abs-helmholtz-cuello-len" type="number" step="0.005" min="0" max="1" value={helmholtz.neckLen}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setHelmholtz(h => ({ ...h, neckLen: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="abs-helmholtz-cuello-radio" className="block text-xs text-gray-500">Radio cuello (m)</label>
            <input id="abs-helmholtz-cuello-radio" type="number" step="0.005" min="0.001" max="0.5" value={helmholtz.neckRadius}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setHelmholtz(h => ({ ...h, neckRadius: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      {activeType === "membrane" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="abs-membrana-masa" className="block text-xs text-gray-500">Masa superficial (kg/m²)</label>
            <input id="abs-membrana-masa" type="number" step="0.5" min="0.5" max="200" value={membrane.massArea}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setMembrane(m => ({ ...m, massArea: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="abs-membrana-camara" className="block text-xs text-gray-500">Cámara de aire (m)</label>
            <input id="abs-membrana-camara" type="number" step="0.01" min="0.01" max="2" value={membrane.airGap}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setMembrane(m => ({ ...m, airGap: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      <button
        onClick={calculate}
        disabled={loading}
        className="w-full rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
      >
        {loading ? "Calculando..." : "Predecir α(f)"}
      </button>

      {result && (
        <div className="mt-4">
          {result.f0 > 0 && (
            <div className="mb-2 flex items-center gap-2">
              <Badge variant="info">f₀ = {result.f0.toFixed(0)} Hz</Badge>
              <Badge variant="default">Q = {result.Q.toFixed(1)}</Badge>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="px-2 py-1 text-left text-xs text-gray-500">Banda</th>
                  {BANDAS.map((b) => (
                    <th key={b} className="px-2 py-1 text-right text-xs text-gray-500">{b}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="px-2 py-1 text-xs font-medium text-gray-700">α</td>
                  {BANDAS.map((b) => (
                    <td key={b} className="px-2 py-1 text-right text-sm font-semibold">
                      {result.alpha[b]?.toFixed(3)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <AlphaChart alpha={result.alpha} f0={result.f0} />
        </div>
      )}
    </Card>
  );
}
