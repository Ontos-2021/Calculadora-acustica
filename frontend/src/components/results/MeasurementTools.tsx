"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

type Tab = "ess" | "waterfall" | "calibrate";

export function MeasurementTools() {
  const [tab, setTab] = useState<Tab>("ess");
  const [ess, setEss] = useState({ f1: 20, f2: 20000, dur: 1 });
  const [waterfallIr, setWaterfallIr] = useState("");
  const [calFreq, setCalFreq] = useState("500");
  const [calMeasured, setCalMeasured] = useState("0.8");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const calculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      let body: Record<string, unknown>;
      let url: string;
      if (tab === "ess") {
        url = `${base}/api/v1/measurement/ess`;
        body = { f1_hz: ess.f1, f2_hz: ess.f2, duration_s: ess.dur, sample_rate: 44100 };
      } else if (tab === "waterfall") {
        url = `${base}/api/v1/measurement/waterfall`;
        const ir = waterfallIr ? waterfallIr.split(",").map(Number) : [0];
        body = { ir, sample_rate: 44100, duration_s: 0.1 };
      } else {
        url = `${base}/api/v1/measurement/calibrate`;
        body = {
          largo: 5, ancho: 4, alto: 3,
          superficies: Array(6).fill({ material: "Concreto" }),
          measured_rt60: { [calFreq]: parseFloat(calMeasured) },
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
        Medición y validación
        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">PAID</span>
      </CardTitle>

      <div className="mb-4 flex gap-2">
        {([
          { key: "ess" as const, label: "ESS" },
          { key: "waterfall" as const, label: "Waterfall" },
          { key: "calibrate" as const, label: "Calibración" },
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

      {tab === "ess" && (
        <div className="mb-4 grid grid-cols-3 gap-3">
          <div>
            <label htmlFor="med-ess-f1" className="block text-xs text-gray-500">f₁ (Hz)</label>
            <input id="med-ess-f1" type="number" min="1" max="1000" value={ess.f1}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setEss(s => ({ ...s, f1: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="med-ess-f2" className="block text-xs text-gray-500">f₂ (Hz)</label>
            <input id="med-ess-f2" type="number" min="100" max="48000" value={ess.f2}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setEss(s => ({ ...s, f2: Number(e.target.value) }))} />
          </div>
          <div>
            <label htmlFor="med-ess-duracion" className="block text-xs text-gray-500">Duración (s)</label>
            <input id="med-ess-duracion" type="number" step="0.1" min="0.1" max="30" value={ess.dur}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setEss(s => ({ ...s, dur: Number(e.target.value) }))} />
          </div>
        </div>
      )}

      {tab === "waterfall" && (
        <div className="mb-4">
          <label htmlFor="med-waterfall-ir" className="block text-xs text-gray-500">IR (valores separados por coma)</label>
          <textarea
            id="med-waterfall-ir"
            rows={3}
            placeholder="0,0.5,0.2,-0.1,..."
            className="mt-1 w-full rounded border px-2 py-1 text-sm font-mono"
            value={waterfallIr}
            onChange={(e) => setWaterfallIr(e.target.value)}
          />
        </div>
      )}

      {tab === "calibrate" && (
        <div className="mb-4 grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="med-cal-banda" className="block text-xs text-gray-500">Banda (Hz)</label>
            <select id="med-cal-banda" className="mt-1 w-full rounded border px-2 py-1 text-sm"
              value={calFreq} onChange={(e) => setCalFreq(e.target.value)}>
              {BANDAS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="med-cal-rt60" className="block text-xs text-gray-500">RT60 medido (s)</label>
            <input id="med-cal-rt60" type="number" step="0.01" min="0.01" max="10" value={calMeasured}
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              onChange={(e) => setCalMeasured(e.target.value)} />
          </div>
        </div>
      )}

      <button
        onClick={calculate}
        disabled={loading}
        className="w-full rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
      >
        {loading ? "Calculando..." : "Ejecutar"}
      </button>

      {result && r && !("error" in result) && (
        <div className="mt-4 space-y-3">
          {tab === "ess" && (
            <div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="info">{(r.sample_rate as number) / 1000} kHz</Badge>
                <Badge variant="default">{r.duration_s as number}s</Badge>
                <Badge variant="success">{r.total_samples as number} samples</Badge>
              </div>
              <div className="mt-2 h-20 rounded bg-gray-50 p-2">
                <svg viewBox="0 0 500 60" className="h-full w-full">
                  {(r.signal as number[])?.slice(0, 500).map((v, i) => (
                    <line key={i} x1={i} y1={30 - v * 25} x2={i + 1} y2={30 - v * 25} stroke="#6366f1" strokeWidth={1} />
                  ))}
                </svg>
              </div>
            </div>
          )}

          {tab === "waterfall" && (() => {
            const bands = r.bands as Record<string, number[]>;
            const time = r.time_ms as number[];
            if (!bands || !time) return null;
            const maxDecay = Math.min(...Object.values(bands).flat(), -60);
            const minDecay = Math.max(...Object.values(bands).flat(), 0);
            const range = maxDecay - minDecay || 1;
            return (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-gray-600">Decaimiento espectral</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-[10px]">
                    <thead>
                      <tr>
                        <th className="p-1 text-left text-gray-500">t\f</th>
                        {BANDAS.map((b) => <th key={b} className="p-1 text-right text-gray-500">{b}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {time.filter((_, i) => i % Math.max(1, Math.floor(time.length / 20)) === 0).map((t, ti) => (
                        <tr key={ti}>
                          <td className="p-1 text-gray-400">{t.toFixed(0)}ms</td>
                          {BANDAS.map((b) => {
                            const val = bands[b]?.[ti * Math.max(1, Math.floor(time.length / 20))] ?? -60;
                            const intensity = ((val - minDecay) / range);
                            return (
                              <td key={b} className="p-1 text-right font-mono"
                                style={{ backgroundColor: `rgba(99, 102, 241, ${intensity})` }}>
                                {val.toFixed(1)}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}

          {tab === "calibrate" && (() => {
            const alphas = r.calibrated_alphas as Record<string, Record<string, number>>;
            if (!alphas) return null;
            return (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-gray-600">α calibrados</h4>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="px-2 py-1 text-left text-xs text-gray-500">Superficie</th>
                      {BANDAS.map((b) => (
                        <th key={b} className="px-2 py-1 text-right text-xs text-gray-500">{b}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(alphas).map(([banda, surfs]) => (
                      Object.entries(surfs).slice(0, 6).map(([nombre, alpha]) => (
                        <tr key={`${banda}-${nombre}`} className="border-b">
                          <td className="px-2 py-1 text-xs text-gray-700">{nombre}</td>
                          {BANDAS.map((b) => (
                            <td key={b} className="px-2 py-1 text-right text-xs font-mono">
                              {b === banda ? alpha.toFixed(3) : "—"}
                            </td>
                          ))}
                        </tr>
                      ))
                    )).slice(0, 6)}
                  </tbody>
                </table>
              </div>
            );
          })()}
        </div>
      )}
    </Card>
  );
}
