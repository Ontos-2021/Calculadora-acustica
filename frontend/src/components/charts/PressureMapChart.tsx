"use client";

import { useMemo } from "react";
import type { Mode, PressureMapResponse } from "@/lib/types";
import { EChart } from "./EChart";

export function PressureMapChart({
  data,
  modes,
  selectedMode,
  onSelectMode,
  onMaxFreqChange,
  maxFreq,
  loading,
}: {
  data: PressureMapResponse;
  modes: Mode[];
  selectedMode: string;
  onSelectMode: (value: string) => void;
  onMaxFreqChange: (value: number) => void;
  maxFreq: number;
  loading?: boolean;
}) {
  const signed = data.quantity === "signed_normalized_pressure";
  const quantityLabel = signed ? "Presión modal normalizada con signo" : "Magnitud RMS modal ponderada normalizada";
  const heatmapData = useMemo(() => {
    const points: [number, number, number][] = [];
    for (let yIndex = 0; yIndex < data.grid_y.length; yIndex += 1) {
      for (let xIndex = 0; xIndex < data.grid_x.length; xIndex += 1) {
        points.push([xIndex, yIndex, data.pressure[yIndex][xIndex]]);
      }
    }
    return points;
  }, [data]);

  const option = {
    aria: {
      enabled: true,
      description: `${quantityLabel} a ${data.ear_height.toFixed(2)} metros de altura. ${data.num_modos} modos representados.`,
    },
    animation: false,
    tooltip: {
      position: "top",
      formatter: (params: { value: [number, number, number] }) => {
        const [xIndex, yIndex, value] = params.value;
        const x = data.grid_x[xIndex];
        const y = data.grid_y[yIndex];
        if (value === undefined) return `<strong>Recomendación:</strong> (${x.toFixed(2)}, ${y.toFixed(2)}) m`;
        return `<strong>Posición:</strong> (${x.toFixed(2)}, ${y.toFixed(2)}) m<br/><strong>${signed ? "Presión p/pmax" : "Magnitud RMS relativa"}:</strong> ${value.toFixed(3)}`;
      },
    },
    grid: { left: "5%", right: "5%", bottom: "14%", top: "5%", containLabel: true },
    xAxis: {
      type: "category",
      name: "Largo (m)",
      data: data.grid_x.map((value) => value.toFixed(2)),
      axisLabel: { interval: Math.max(0, Math.floor(data.grid_x.length / 6) - 1) },
    },
    yAxis: {
      type: "category",
      name: "Ancho (m)",
      data: data.grid_y.map((value) => value.toFixed(2)),
      axisLabel: { interval: Math.max(0, Math.floor(data.grid_y.length / 6) - 1) },
    },
    visualMap: {
      min: signed ? -1 : 0,
      max: 1,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: signed ? ["#0369a1", "#bae6fd", "#ffffff", "#fecdd3", "#be123c"] : ["#fafafa", "#99f6e4", "#0f766e", "#18181b"] },
      text: signed ? ["Antinodo +", "Antinodo −"] : ["Mayor magnitud", "Nodo / menor"],
      textStyle: { fontSize: 10 },
    },
    series: [
      { id: "presion", name: quantityLabel, type: "heatmap", data: heatmapData, emphasis: { itemStyle: { borderColor: "#111827", borderWidth: 1 } } },
      {
        id: "escucha",
        name: "Recomendación de escucha",
        type: "scatter",
        data: [[nearestIndex(data.grid_x, data.optimal_listening.x), nearestIndex(data.grid_y, data.optimal_listening.y)]],
        symbol: "cross",
        symbolSize: 20,
        itemStyle: { color: "#10b981", borderColor: "#064e3b", borderWidth: 2 },
        z: 10,
      },
    ],
  };

  const modeOptions = useMemo(
    () => modes
      .filter((mode, index) => modes.findIndex((candidate) => candidate.indices.join(",") === mode.indices.join(",")) === index)
      .sort((left, right) => left.frecuencia - right.frecuencia),
    [modes],
  );

  const representativeRows = heatmapData
    .filter((_, index) => index % Math.max(1, Math.floor(heatmapData.length / 12)) === 0)
    .slice(0, 12)
    .map(([xIndex, yIndex, value]) => [data.grid_x[xIndex], data.grid_y[yIndex], value] as const);

  return (
    <figure className="space-y-4" aria-busy={loading}>
      <div className="flex flex-wrap items-end gap-4">
        <div className="min-w-0 flex-1 sm:flex-none">
          <label htmlFor="presion-modo" className="block text-xs font-medium text-gray-600">Contexto modal</label>
          <select id="presion-modo" className="mt-1 max-w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm" value={selectedMode} onChange={(event) => onSelectMode(event.target.value)}>
            <option value="all">Acumulado (todos los modos)</option>
            {modeOptions.map((mode) => (
              <option key={mode.indices.join(",")} value={mode.indices.join(",")}>
                {mode.frecuencia.toFixed(1)} Hz · ({mode.indices.join(",")})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="presion-fmax" className="block text-xs font-medium text-gray-600">Frecuencia máxima: {maxFreq} Hz</label>
          <input id="presion-fmax" type="range" min={50} max={500} step={5} value={maxFreq} disabled={selectedMode !== "all"} onChange={(event) => onMaxFreqChange(Number(event.target.value))} className="mt-1 w-40 disabled:opacity-40" />
        </div>
        <div className="rounded-lg bg-indigo-50 px-3 py-2 text-xs text-indigo-900">
          {quantityLabel}
        </div>
      </div>

      <div role="img" aria-label={`${quantityLabel}. Recomendación en X ${data.optimal_listening.x.toFixed(2)} m, Y ${data.optimal_listening.y.toFixed(2)} m.`} className={loading ? "opacity-55" : ""}>
        <EChart option={option} className="h-[clamp(22rem,70vw,30rem)]" />
      </div>
      <figcaption className="text-xs leading-5 text-gray-500">
        Plano a {data.ear_height.toFixed(2)} m. {selectedMode === "all" ? `${data.num_modos} modos hasta ${data.max_freq.toFixed(1)} Hz; la fase relativa no se modela.` : `Modo ${data.max_freq.toFixed(1)} Hz con presión normalizada con signo.`}
      </figcaption>
      <details className="rounded-lg border border-gray-200 p-2 text-xs">
        <summary className="cursor-pointer font-medium text-gray-700">Datos accesibles de muestra del mapa</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full">
            <thead><tr><th className="text-left">X (m)</th><th className="text-left">Y (m)</th><th className="text-left">Valor normalizado</th></tr></thead>
            <tbody>{representativeRows.map(([x, y, value], index) => <tr key={index}><td>{x.toFixed(2)}</td><td>{y.toFixed(2)}</td><td>{value.toFixed(3)}</td></tr>)}</tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

function nearestIndex(values: number[], target: number): number {
  return values.reduce(
    (best, value, index) => Math.abs(value - target) < Math.abs(values[best] - target) ? index : best,
    0,
  );
}
