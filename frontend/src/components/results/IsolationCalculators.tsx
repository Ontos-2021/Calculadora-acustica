"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

type Tab = "single" | "double" | "nc";

export function IsolationCalculators() {
  const [tab, setTab] = useState<Tab>("single");
  const [single, setSingle] = useState({ mass: 50, thick: 0.1 });
  const [dbl, setDbl] = useState({ m1: 50, m2: 20, gap: 0.1, stud: true });
  const [ncSpl, setNcSpl] = useState<Record<string, string>>({
    "125": "50", "250": "45", "500": "40", "1000": "35", "2000": "30", "4000": "25",
  });
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      let body: Record<string, unknown>;
      let url: string;
      if (tab === "single") {
        url = `${base}/api/v1/design/isolation/single-panel`;
        body = { mass_per_area_kgm2: single.mass, thickness_m: single.thick };
      } else if (tab === "double") {
        url = `${base}/api/v1/design/isolation/double-panel`;
        body = { m1_kgm2: dbl.m1, m2_kgm2: dbl.m2, gap_m: dbl.gap, stud_connection: dbl.stud };
      } else {
        url = `${base}/api/v1/design/isolation/nc`;
        const spl: Record<string, number> = {};
        for (const [k, v] of Object.entries(ncSpl)) {
          spl[k] = parseFloat(v) || 0;
        }
        body = { spl };
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
  const tl = r?.tl as Record<string, number> | undefined;

  const maxTl = tl ? Math.max(...Object.values(tl), 1) : 1;

  return (
    <Card>
      <CardTitle>
        Aislamiento acústico
        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">PAID</span>
      </CardTitle>

      <div className="mb-4 flex gap-2">
        {([
          { key: "single" as const, label: "Panel simple" },
          { key: "double" as const, label: "Doble hoja" },
          { key: "nc" as const, label: "Ruido NC" },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => { setTab(key); setResult(null); }}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === key ? "bg-indigo-500 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "single" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="aisl-simple-masa" className="block text-xs text-gray-500">Masa (kg/m²)</label>
            <input id="aisl-simple-masa" type="number" min="1" max="10000" value={single.mass}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setSingle(s => ({ ...s, mass: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="aisl-simple-espesor" className="block text-xs text-gray-500">Espesor (m)</label>
            <input id="aisl-simple-espesor" type="number" step="0.001" min="0.001" max="1" value={single.thick}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setSingle(s => ({ ...s, thick: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      {tab === "double" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="aisl-doble-m1" className="block text-xs text-gray-500">Masa hoja 1 (kg/m²)</label>
            <input id="aisl-doble-m1" type="number" min="1" max="10000" value={dbl.m1}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setDbl(d => ({ ...d, m1: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="aisl-doble-m2" className="block text-xs text-gray-500">Masa hoja 2 (kg/m²)</label>
            <input id="aisl-doble-m2" type="number" min="1" max="10000" value={dbl.m2}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setDbl(d => ({ ...d, m2: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="aisl-doble-camara" className="block text-xs text-gray-500">Cámara (m)</label>
            <input id="aisl-doble-camara" type="number" step="0.01" min="0.01" max="2" value={dbl.gap}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setDbl(d => ({ ...d, gap: Number(e.target.value) }))} />
          </div>
          <div className="flex items-end pb-1">
            <label className="flex items-center gap-2 text-xs text-gray-500">
              <input id="aisl-doble-stud" type="checkbox" checked={dbl.stud}
                onChange={(e) => setDbl(d => ({ ...d, stud: e.target.checked }))} />
              Con montantes (penalización)
            </label>
          </div>
        </div>
      )}

      {tab === "nc" && (
        <div className="mb-4 grid grid-cols-3 gap-2">
          {BANDAS.map((b) => {
            const ncId = `aisl-nc-${b}`;
            return (
            <div key={b}>
              <label htmlFor={ncId} className="block text-xs text-gray-500">{b} Hz (SPL)</label>
              <input id={ncId} type="number" min="0" max="120" value={ncSpl[b]}
                className="mt-1 w-full rounded border px-2 py-1 text-sm"
                onChange={(e) => setNcSpl(s => ({ ...s, [b]: e.target.value }))} />
            </div>
            );
          })}
        </div>
      )}

      <button
        onClick={calculate}
        disabled={loading}
        className="w-full rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
      >
        {loading ? "Calculando..." : "Calcular"}
      </button>

      {result && r && !("error" in result) && (
        <div className="mt-4 space-y-4">
          {tab !== "nc" && (
            <>
              <div className="flex flex-wrap gap-2">
                {r.fc_hz !== undefined && (
                  <Badge variant="info">f<sub>c</sub> = {(r.fc_hz as number).toFixed(0)} Hz</Badge>
                )}
                {r.f0_hz !== undefined && (
                  <Badge variant="info">f₀ = {(r.f0_hz as number).toFixed(0)} Hz</Badge>
                )}
                {r.stc !== undefined && (
                  <Badge variant="success">STC = {r.stc as number}</Badge>
                )}
                {r.rw !== undefined && (
                  <Badge variant="default">R<sub>w</sub> = {r.rw as number}</Badge>
                )}
              </div>

              {tl && (
                <div>
                  <h4 className="mb-1 text-xs font-semibold text-gray-600">TL por banda (dB)</h4>
                  <div className="flex items-end gap-1" style={{ height: 100 }}>
                    {BANDAS.map((b) => (
                      <div key={b} className="flex flex-1 flex-col items-center">
                        <span className="mb-0.5 text-[10px] font-medium text-indigo-600">
                          {tl[b]?.toFixed(0)}
                        </span>
                        <div
                          className="w-full rounded-t bg-indigo-500"
                          style={{ height: `${((tl[b] || 0) / maxTl) * 80}px`, minHeight: (tl[b] || 0) > 0 ? 2 : 0 }}
                        />
                        <span className="mt-0.5 text-[10px] text-gray-500">{b}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {tab === "nc" && (
            <div>
              <div className="mb-2">
                <Badge variant={((r.nc as number) || 0) <= 25 ? "success" : "danger"}>
                  NC = {r.nc as number}
                </Badge>
              </div>
              {tl && (
                <div className="flex gap-2">
                  {BANDAS.map((b) => (
                    <div key={b} className="flex-1 rounded bg-gray-50 p-1.5 text-center">
                      <div className="text-[10px] text-gray-500">{b}</div>
                      <div className="text-sm font-bold text-indigo-600">{tl[b]?.toFixed(0)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
