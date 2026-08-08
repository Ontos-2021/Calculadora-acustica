"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

type DiffuserType = "qrd" | "skyline";

export function DiffuserCalculators() {
  const [activeType, setActiveType] = useState<DiffuserType>("qrd");
  const [qrd, setQrd] = useState({ freq: 1000, prime: 17, width: 0.05 });
  const [skyline, setSkyline] = useState({ freq: 1000, grid: 7, size: 0.05 });
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      let body: Record<string, unknown>;
      let url: string;
      if (activeType === "qrd") {
        url = `${base}/api/v1/design/diffusers/qrd`;
        body = { design_freq_hz: qrd.freq, prime_n: qrd.prime, well_width_m: qrd.width };
      } else {
        url = `${base}/api/v1/design/diffusers/skyline`;
        body = { design_freq_hz: skyline.freq, grid_n: skyline.grid, well_size_m: skyline.size };
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
  const depths = activeType === "qrd"
    ? (r?.well_depths_m as number[] | undefined)
    : (r?.well_depths_m as number[][] | undefined);
  const maxDepth = (r?.max_depth_m as number) || 0;
  const totalWidth = (r?.total_width_m as number) || 0;
  const minFreq = (r?.min_effective_freq_hz as number) || 0;
  const diffCoeff = r?.diffusion_coefficient as Record<string, number> | undefined;

  return (
    <Card>
      <CardTitle>
        Calculadora de difusores
        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">PAID</span>
      </CardTitle>

      <div className="mb-4 flex gap-2">
        {([
          { key: "qrd" as const, label: "QRD (1D)" },
          { key: "skyline" as const, label: "Skyline (2D)" },
        ]).map(({ key, label }) => (
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

      {activeType === "qrd" && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div>
            <label htmlFor="dif-qrd-freq" className="block text-xs text-gray-500">Frec. diseño (Hz)</label>
            <input id="dif-qrd-freq" type="number" min="100" max="10000" value={qrd.freq}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setQrd(p => ({ ...p, freq: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="dif-qrd-n" className="block text-xs text-gray-500">N (primo)</label>
            <input id="dif-qrd-n" type="number" min="5" max="199" value={qrd.prime}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setQrd(p => ({ ...p, prime: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="dif-qrd-ancho" className="block text-xs text-gray-500">Ancho pozo (m)</label>
            <input id="dif-qrd-ancho" type="number" step="0.01" min="0.01" max="1" value={qrd.width}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setQrd(p => ({ ...p, width: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      {activeType === "skyline" && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div>
            <label htmlFor="dif-skyline-freq" className="block text-xs text-gray-500">Frec. diseño (Hz)</label>
            <input id="dif-skyline-freq" type="number" min="100" max="10000" value={skyline.freq}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setSkyline(p => ({ ...p, freq: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="dif-skyline-grid" className="block text-xs text-gray-500">Grid N×N</label>
            <input id="dif-skyline-grid" type="number" min="2" max="20" value={skyline.grid}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setSkyline(p => ({ ...p, grid: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="dif-skyline-celda" className="block text-xs text-gray-500">Tamaño celda (m)</label>
            <input id="dif-skyline-celda" type="number" step="0.01" min="0.01" max="1" value={skyline.size}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setSkyline(p => ({ ...p, size: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      <button
        onClick={calculate}
        disabled={loading}
        className="w-full rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
      >
        {loading ? "Calculando..." : "Calcular difusor"}
      </button>

      {result && r && !("error" in result) && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="info">f₀ = {(r.design_freq_hz as number)?.toFixed(0)} Hz</Badge>
            <Badge variant="default">N = {(r.prime_n as number) || (r.grid_n as number)}</Badge>
            <Badge variant="success">{totalWidth} m ancho</Badge>
            <Badge variant="warning">f_min ≈ {minFreq} Hz</Badge>
          </div>

          <div>
            <h4 className="mb-1 text-xs font-semibold text-gray-600">Perfil de profundidades (m)</h4>
            {activeType === "qrd" && Array.isArray(depths) && (
              <div className="flex items-end gap-0.5" style={{ height: 80 }}>
                {(depths as number[]).map((d, i) => (
                  <div key={i} className="flex flex-1 flex-col items-center">
                    <div
                      className="w-full rounded-t bg-indigo-500"
                      style={{ height: `${(d / (maxDepth || 1)) * 100}%`, minHeight: d > 0 ? 2 : 0 }}
                    />
                    <span className="mt-0.5 text-[8px] text-gray-400">{i}</span>
                  </div>
                ))}
              </div>
            )}
            {activeType === "skyline" && Array.isArray(depths) && (
              <div className="grid" style={{ gridTemplateColumns: `repeat(${(depths as number[][]).length}, 1fr)` }}>
                {(depths as number[][]).map((row, i) => (
                  <div key={i} className="flex flex-col-reverse gap-0.5">
                    {row.map((d, j) => (
                      <div
                        key={j}
                        className="w-full rounded bg-indigo-500"
                        style={{ height: `${(d / (maxDepth || 1)) * 40}px`, minHeight: d > 0 ? 2 : 0 }}
                        title={`(${i},${j}): ${d}m`}
                      />
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          {diffCoeff && (
            <div>
              <h4 className="mb-1 text-xs font-semibold text-gray-600">Coeficiente de difusión estimado</h4>
              <div className="flex gap-2">
                {BANDAS.map((b) => (
                  <div key={b} className="flex-1 rounded bg-gray-50 p-1.5 text-center">
                    <div className="text-[10px] text-gray-500">{b}</div>
                    <div className="text-sm font-bold text-indigo-600">{(diffCoeff[b] * 100).toFixed(0)}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
