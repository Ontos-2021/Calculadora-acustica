"use client";

import { useRef, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import type { PressureMapResponse, Mode } from "@/lib/types";

export function PressureMapChart({
  data,
  modes,
  selectedMode,
  onSelectMode,
  onMaxFreqChange,
  maxFreq,
}: {
  data: PressureMapResponse;
  modes: Mode[];
  selectedMode: string;
  onSelectMode: (val: string) => void;
  onMaxFreqChange: (val: number) => void;
  maxFreq: number;
}) {
  const chartRef = useRef<ReactECharts>(null);

  const heatmapData = useMemo(() => {
    const points: [number, number, number][] = [];
    for (let yi = 0; yi < data.grid_y.length; yi++) {
      for (let xi = 0; xi < data.grid_x.length; xi++) {
        points.push([data.grid_x[xi], data.grid_y[yi], data.pressure[yi][xi]]);
      }
    }
    return points;
  }, [data]);

  const option = {
    tooltip: {
      position: "top",
      formatter: (params: { value: [number, number, number] }) => {
        const [x, y, v] = params.value;
        return `<strong>Posición:</strong> (${x.toFixed(2)}, ${y.toFixed(2)}) m<br/>
                <strong>Presión:</strong> ${(v * 100).toFixed(1)}%`;
      },
    },
    grid: {
      left: "5%",
      right: "5%",
      bottom: "12%",
      top: "5%",
      containLabel: true,
    },
    xAxis: {
      type: "value",
      name: "Largo (m)",
      min: 0,
      max: data.grid_x[data.grid_x.length - 1],
    },
    yAxis: {
      type: "value",
      name: "Ancho (m)",
      min: 0,
      max: data.grid_y[data.grid_y.length - 1],
    },
    visualMap: {
      min: 0,
      max: 1,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: {
        color: ["#1a237e", "#42a5f5", "#ffffff", "#ef5350", "#b71c1c"],
      },
      text: ["Antinodo", "Nodo"],
      textStyle: { fontSize: 10 },
    },
    series: [
      {
        name: "Presión modal",
        type: "heatmap",
        data: heatmapData,
        label: { show: false },
        emphasis: {
          itemStyle: { borderColor: "#333", borderWidth: 1 },
        },
      },
      {
        name: "Posición óptima",
        type: "scatter",
        data: [[data.optimal_listening.x, data.optimal_listening.y]],
        symbol: "cross",
        symbolSize: 20,
        itemStyle: {
          color: "#00e676",
          borderColor: "#004d40",
          borderWidth: 2,
        },
        z: 10,
      },
    ],
  };

  const modeOptions = useMemo(() => {
    const unique = new Map<number, Mode>();
    modes.forEach((m) => {
      if (!unique.has(m.frecuencia)) unique.set(m.frecuencia, m);
    });
    return Array.from(unique.values()).sort((a, b) => a.frecuencia - b.frecuencia);
  }, [modes]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <div>
          <label htmlFor="presion-modo" className="block text-xs font-medium text-gray-500">
            Modo
          </label>
          <select
            id="presion-modo"
            className="mt-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
            value={selectedMode}
            onChange={(e) => onSelectMode(e.target.value)}
          >
            <option value="all">Acumulado (todos los modos)</option>
            {modeOptions.map((m) => (
              <option key={m.frecuencia} value={m.frecuencia}>
                {m.frecuencia} Hz — ({m.indices.join(",")})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="presion-fmax" className="block text-xs font-medium text-gray-500">
            Frecuencia máxima: {maxFreq} Hz
          </label>
          <input
            id="presion-fmax"
            type="range"
            min={50}
            max={500}
            step={5}
            value={maxFreq}
            onChange={(e) => onMaxFreqChange(Number(e.target.value))}
            className="mt-1 w-40"
          />
        </div>
        <div className="rounded-lg bg-green-50 px-3 py-1.5 text-xs">
          <span className="text-green-700">
            Posición óptima: ({data.optimal_listening.x.toFixed(2)}, {data.optimal_listening.y.toFixed(2)}) m
          </span>
        </div>
      </div>
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: 480 }}
        notMerge
        lazyUpdate
      />
      <p className="text-xs text-gray-400">
        Mapa de presión a {data.ear_height} m de altura
        {selectedMode === "all"
          ? ` — ${data.num_modos} modos hasta ${maxFreq} Hz`
          : ` — modo específico ${selectedMode} Hz`}
        . Los puntos verdes indican la posición de escucha óptima.
      </p>
    </div>
  );
}
