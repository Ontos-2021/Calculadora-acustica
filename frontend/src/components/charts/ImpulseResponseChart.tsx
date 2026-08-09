"use client";

import { EChart } from "./EChart";

export function ImpulseResponseChart({
  ir,
  sampleRate,
}: {
  ir: number[];
  sampleRate: number;
}) {
  if (!ir || ir.length === 0) return null;

  const timeMs = ir.map((_, i) => ((i * 1000) / sampleRate).toFixed(2));
  const displayLen = Math.min(ir.length, Math.ceil(sampleRate * 0.2));

  const option = {
    tooltip: {
      trigger: "axis",
      formatter: (params: { dataIndex: number; value: number }[]) => {
        const p = params[0];
        const t = (p.dataIndex * 1000) / sampleRate;
        return `t: ${t.toFixed(2)} ms<br/>Amplitud: ${p.value?.toFixed(4) ?? 0}`;
      },
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "10%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: timeMs.slice(0, displayLen),
      name: "Tiempo (ms)",
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: "value",
      name: "Amplitud",
      scale: true,
    },
    dataZoom: [
      { type: "inside", start: 0, end: 20 },
      { type: "slider", start: 0, end: 20, bottom: -5 },
    ],
    series: [
      {
        id: "impulso",
        type: "line",
        data: ir.slice(0, displayLen),
        symbol: "none",
        lineStyle: { color: "#6366f1", width: 1 },
        areaStyle: {
          color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(99,102,241,0.3)" }, { offset: 1, color: "rgba(99,102,241,0.05)" }] },
        },
      },
    ],
  };

  return (
    <EChart
      option={option}
      className="h-[clamp(18rem,50vw,22rem)]"
    />
  );
}
