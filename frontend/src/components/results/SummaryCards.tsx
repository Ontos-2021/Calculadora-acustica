import type { CalculateResponse } from "@/lib/types";
import { MetricCard } from "@/components/ui/MetricCard";

export function SummaryCards({ data }: { data: CalculateResponse }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <MetricCard
        label="RT60 Promedio"
        value={data.rt60_promedio.toFixed(2)}
        unit="s"
        sublabel="Sabine"
        color="text-indigo-600"
      />
      <MetricCard
        label="f<sub>Schroeder</sub>"
        value={data.f_schroeder.toFixed(0)}
        unit="Hz"
        sublabel="Campo difuso sobre esta frecuencia"
        color="text-cyan-600"
      />
      <MetricCard
        label="Δf (ancho modal)"
        value={data.delta_f.toFixed(2)}
        unit="Hz"
        sublabel="Modos separados < Δf se solapan"
        color="text-amber-600"
      />
      <MetricCard
        label="Modos totales"
        value={data.cantidad_modos}
        sublabel={`Ax ${data.distribucion.axiales} · Tg ${data.distribucion.tangenciales} · Ob ${data.distribucion.oblicuos}`}
        color="text-gray-700"
      />
    </div>
  );
}
