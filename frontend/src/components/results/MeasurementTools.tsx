"use client";

import { useState, type ChangeEvent } from "react";
import { downloadAdvanced, postAdvanced, uploadWav } from "@/lib/api";
import type { CalculateRequest } from "@/lib/types";
import { useLicense } from "@/context/LicenseProvider";
import { roomPayload } from "@/lib/room";
import { Card, CardTitle } from "@/components/ui/Card";
import { FeatureGate } from "@/components/ui/FeatureGate";
import { TabContainer } from "@/components/ui/TabContainer";
import { ToolError, ToolResult } from "@/components/ui/ToolResult";

type Tool = "ess" | "wav" | "signal" | "calibrate";
type SignalTool = "filter" | "spectrogram" | "modal-q" | "waterfall";

export function MeasurementTools({ room, onResult }: { room: CalculateRequest; onResult?: (name: string, result: unknown) => void }) {
  const { apiKey } = useLicense();
  const [tool, setTool] = useState<Tool>("ess");
  const [ess, setEss] = useState({ f1: 20, f2: 20000, duration: 2, sampleRate: 44100, bitDepth: 24 });
  const [wavFile, setWavFile] = useState<File | null>(null);
  const [signalText, setSignalText] = useState("");
  const [signalTool, setSignalTool] = useState<SignalTool>("spectrogram");
  const [centerFrequency, setCenterFrequency] = useState(500);
  const [measuredRt, setMeasuredRt] = useState(0.8);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function syntheticSignal(): number[] {
    return Array.from({ length: 8192 }, (_, index) => Math.sin(2 * Math.PI * 500 * index / 44100) * Math.exp(-index / 2600));
  }

  function parsedSignal(): number[] {
    if (!signalText.trim()) return syntheticSignal();
    const values = signalText.split(/[\s,;]+/).filter(Boolean).map(Number);
    if (!values.length || values.some((value) => !Number.isFinite(value))) throw new Error("La señal contiene valores no numéricos.");
    return values;
  }

  function store(name: string, response: Record<string, unknown>) {
    setResult(response);
    onResult?.(name, response);
    const preview = response.samples_preview;
    if (Array.isArray(preview) && preview.every((value) => typeof value === "number")) {
      setSignalText((preview as number[]).join(","));
    }
  }

  async function runEss() {
    if (!apiKey) return;
    setLoading(true); setError(null);
    try {
      const response = await postAdvanced<Record<string, unknown>>("measurement/ess", { f1_hz: ess.f1, f2_hz: ess.f2, duration_s: ess.duration, sample_rate: ess.sampleRate, bit_depth: ess.bitDepth }, apiKey);
      store("measurement_ess", response);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo generar el ESS."); }
    finally { setLoading(false); }
  }

  async function downloadEss() {
    if (!apiKey) return;
    setLoading(true); setError(null);
    try {
      const download = await downloadAdvanced("measurement/ess/wav", { f1_hz: ess.f1, f2_hz: ess.f2, duration_s: ess.duration, sample_rate: ess.sampleRate, bit_depth: ess.bitDepth }, apiKey, `ess-${ess.f1}-${ess.f2}Hz.wav`);
      saveBlob(download.blob, download.filename);
      onResult?.("measurement_ess_wav", { filename: download.filename, size_bytes: download.blob.size, sample_rate: ess.sampleRate });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo descargar el WAV."); }
    finally { setLoading(false); }
  }

  async function runWav(analyze: boolean) {
    if (!apiKey || !wavFile) { setError("Selecciona un archivo WAV."); return; }
    setLoading(true); setError(null);
    try {
      const response = await uploadWav(wavFile, apiKey, { analyze, channel: "mix", directDelayMs: 0 });
      store(analyze ? "measurement_wav_analysis" : "measurement_wav_import", response);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo procesar el WAV."); }
    finally { setLoading(false); }
  }

  async function runSignal() {
    if (!apiKey) return;
    setLoading(true); setError(null);
    try {
      const signal = parsedSignal();
      let path: string;
      let body: Record<string, unknown>;
      if (signalTool === "filter") {
        path = "measurement/filter"; body = { signal, sample_rate: 44100, center_hz: centerFrequency, fraction: 3 };
      } else if (signalTool === "spectrogram") {
        path = "measurement/spectrogram"; body = { signal: signal.slice(0, 65536), sample_rate: 44100, window_size: 256, hop_size: 128, max_frames: 1024 };
      } else if (signalTool === "modal-q") {
        path = "measurement/modal-q"; body = { signal, sample_rate: 44100, target_frequency_hz: centerFrequency, cycles_per_window: 4, dynamic_range_db: 30 };
      } else {
        path = "measurement/waterfall"; body = { ir: signal, sample_rate: 44100, duration_s: Math.min(0.18, signal.length / 44100), fraction: 1, time_step_s: 0.01 };
      }
      const response = await postAdvanced<Record<string, unknown>>(path, body, apiKey);
      store(`measurement_${signalTool}`, response);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo analizar la señal."); }
    finally { setLoading(false); }
  }

  async function runCalibration() {
    if (!apiKey) return;
    setLoading(true); setError(null);
    try {
      const measured = Object.fromEntries(["125", "250", "500", "1000", "2000", "4000"].map((band) => [band, measuredRt]));
      const response = await postAdvanced<Record<string, unknown>>("measurement/calibrate", { ...roomPayload(room), measured_rt60: measured, iterations: 30 }, apiKey);
      store("measurement_calibration", response);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo calibrar el modelo."); }
    finally { setLoading(false); }
  }

  return (
    <Card>
      <CardTitle>Medición y validación <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">PAID</span></CardTitle>
      <FeatureGate feature="measurement">
        <TabContainer compact activeTab={tool} onTabChange={(key) => { setTool(key as Tool); setResult(null); setError(null); }} label="Herramientas de medición" tabs={[{ key: "ess", label: "ESS / WAV" }, { key: "wav", label: "Importar WAV" }, { key: "signal", label: "Señal" }, { key: "calibrate", label: "Calibración" }]}>
          <div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <NumberField id="med-ess-f1" label="f₁ (Hz)" value={ess.f1} onChange={(value) => setEss((current) => ({ ...current, f1: value }))} />
              <NumberField id="med-ess-f2" label="f₂ (Hz)" value={ess.f2} onChange={(value) => setEss((current) => ({ ...current, f2: value }))} />
              <NumberField id="med-ess-duracion" label="Duración (s)" value={ess.duration} step={0.1} onChange={(value) => setEss((current) => ({ ...current, duration: value }))} />
              <NumberField id="med-ess-rate" label="Muestreo (Hz)" value={ess.sampleRate} onChange={(value) => setEss((current) => ({ ...current, sampleRate: value }))} />
              <div><label htmlFor="med-ess-depth" className="block text-xs font-medium text-gray-600">Profundidad</label><select id="med-ess-depth" value={ess.bitDepth} onChange={(event) => setEss((current) => ({ ...current, bitDepth: Number(event.target.value) }))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm"><option value="16">16 bit</option><option value="24">24 bit</option><option value="32">32 bit</option></select></div>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-2"><button type="button" onClick={() => void runEss()} disabled={loading} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Generar vista previa ESS</button><button type="button" onClick={() => void downloadEss()} disabled={loading} className="rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-indigo-700 disabled:opacity-50">Descargar ESS WAV</button></div>
          </div>
          <div>
            <label htmlFor="med-wav-file" className="block text-xs font-medium text-gray-600">Archivo WAV PCM / float</label>
            <input id="med-wav-file" type="file" accept="audio/wav,.wav" onChange={(event: ChangeEvent<HTMLInputElement>) => setWavFile(event.target.files?.[0] ?? null)} className="mt-1 block w-full rounded border p-2 text-sm" />
            <div className="mt-3 grid gap-2 sm:grid-cols-2"><button type="button" onClick={() => void runWav(false)} disabled={loading || !wavFile} className="rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-indigo-700 disabled:opacity-50">Importar metadatos y muestras</button><button type="button" onClick={() => void runWav(true)} disabled={loading || !wavFile} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Analizar ISO 3382</button></div>
          </div>
          <div>
            <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
              <div><label htmlFor="med-signal" className="block text-xs font-medium text-gray-600">Muestras separadas por coma (vacío = señal de prueba determinista)</label><textarea id="med-signal" rows={3} value={signalText} onChange={(event) => setSignalText(event.target.value)} className="mt-1 w-full rounded border px-2 py-1.5 font-mono text-xs" /></div>
              <div><label htmlFor="med-signal-tool" className="block text-xs font-medium text-gray-600">Análisis</label><select id="med-signal-tool" value={signalTool} onChange={(event) => setSignalTool(event.target.value as SignalTool)} className="mt-1 w-full rounded border px-2 py-1.5 text-sm"><option value="filter">Filtro 1/3 octava</option><option value="spectrogram">Espectrograma</option><option value="modal-q">Q modal</option><option value="waterfall">Waterfall</option></select><label htmlFor="med-center" className="mt-3 block text-xs font-medium text-gray-600">Frecuencia central (Hz)</label><input id="med-center" type="number" value={centerFrequency} onChange={(event) => setCenterFrequency(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>
            </div>
            <button type="button" onClick={() => void runSignal()} disabled={loading} className="mt-3 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Analizar señal</button>
          </div>
          <div>
            <p className="mb-3 text-xs leading-5 text-gray-600">Ajusta coeficientes de las seis superficies de la sala actual. Los diagnósticos muestran convergencia, error e identificabilidad; no convierten el modelo en una medición certificada.</p>
            <NumberField id="med-cal-rt60" label="RT60 medido uniforme (s)" value={measuredRt} step={0.05} onChange={setMeasuredRt} />
            <button type="button" onClick={() => void runCalibration()} disabled={loading} className="mt-3 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Calibrar sala actual</button>
          </div>
        </TabContainer>
        {loading && <p className="mt-3 text-sm text-indigo-700" role="status" aria-live="polite">Procesando medición…</p>}
        <ToolError message={error} />
        {result && <ToolResult result={result} title="Resultado de medición y diagnósticos" />}
      </FeatureGate>
    </Card>
  );
}

function NumberField({ id, label, value, step = 1, onChange }: { id: string; label: string; value: number; step?: number; onChange: (value: number) => void }) {
  return <div><label htmlFor={id} className="block text-xs font-medium text-gray-600">{label}</label><input id={id} type="number" step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
