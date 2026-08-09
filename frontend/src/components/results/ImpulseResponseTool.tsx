"use client";

import { useState } from "react";
import { fetchImpulseResponse } from "@/lib/api";
import type { CalculateRequest, IRResponse, ISO3382Parameters } from "@/lib/types";
import { useLicense } from "@/context/LicenseProvider";
import { roomPayload } from "@/lib/room";
import { Card, CardTitle } from "@/components/ui/Card";
import { FeatureGate } from "@/components/ui/FeatureGate";
import { ToolError } from "@/components/ui/ToolResult";
import { ImpulseResponseChart } from "@/components/charts/ImpulseResponseChart";
import { ISMParams } from "./ISMParams";

export function ImpulseResponseTool({ room, onResult }: { room: CalculateRequest; onResult?: (result: IRResponse) => void }) {
  const { apiKey } = useLicense();
  const [source, setSource] = useState({ x: room.largo * 0.22, y: room.ancho * 0.35, z: room.alto * 0.55 });
  const [receiver, setReceiver] = useState({ x: room.largo * 0.72, y: room.ancho * 0.62, z: room.alto * 0.4 });
  const [result, setResult] = useState<IRResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!apiKey) return;
    setLoading(true); setError(null);
    try {
      const response = await fetchImpulseResponse({
        ...roomPayload(room),
        source: [source.x, source.y, source.z],
        receiver: [receiver.x, receiver.y, receiver.z],
        max_order: 8,
        duration_s: 1,
        sample_rate: 44100,
        band: "500",
      }, apiKey);
      setResult(response);
      onResult?.(response);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo calcular la respuesta al impulso.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardTitle>Respuesta al impulso por fuentes imagen <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">PAID</span></CardTitle>
      <FeatureGate feature="ism">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <PointFields prefix="ism-fuente" label="Fuente" point={source} setPoint={setSource} room={room} />
          <PointFields prefix="ism-receptor" label="Receptor" point={receiver} setPoint={setReceiver} room={room} />
        </div>
        <button type="button" onClick={() => void run()} disabled={loading} className="mt-4 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Calculando…" : "Calcular respuesta al impulso"}</button>
        <ToolError message={error} onRetry={() => void run()} />
        {result && (
          <div className="mt-5 space-y-4">
            <p className="text-xs text-gray-500">{result.image_source_count} fuentes imagen · representación {result.impulse_representation} · retraso directo {result.direct_delay_ms.toFixed(2)} ms.</p>
            <ImpulseResponseChart ir={result.impulse_response} sampleRate={result.sample_rate} />
            {"error" in result.parameters ? <p className="text-sm text-amber-800">{String(result.parameters.error)}</p> : <ISMParams params={result.parameters as ISO3382Parameters} />}
          </div>
        )}
      </FeatureGate>
    </Card>
  );
}

function PointFields({ prefix, label, point, setPoint, room }: { prefix: string; label: string; point: { x: number; y: number; z: number }; setPoint: React.Dispatch<React.SetStateAction<{ x: number; y: number; z: number }>>; room: CalculateRequest }) {
  const bounds = { x: room.largo, y: room.ancho, z: room.alto };
  return <fieldset className="rounded-lg border border-gray-200 p-3"><legend className="px-1 text-xs font-semibold text-gray-700">{label}</legend><div className="grid grid-cols-3 gap-2">{(["x", "y", "z"] as const).map((axis) => <div key={axis}><label htmlFor={`${prefix}-${axis}`} className="block text-xs uppercase text-gray-500">{axis} (m)</label><input id={`${prefix}-${axis}`} type="number" min={0.001} max={bounds[axis] - 0.001} step={0.05} value={point[axis]} onChange={(event) => setPoint((current) => ({ ...current, [axis]: Number(event.target.value) }))} className="mt-1 w-full rounded border px-2 py-1.5 text-sm" /></div>)}</div></fieldset>;
}
