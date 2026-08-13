"use client";

import { EChart } from "./EChart";

export function BonelloChart({
  bandas,
}: {
  bandas: Record<string, number>;
}) {
  if (!bandas || Object.keys(bandas).length === 0) return null;

  const frequencies = Object.keys(bandas).map(Number);
  const counts = Object.values(bandas);

  const option = {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: { name: string; value: number }[]) => {
        const p = params[0];
        return `${p.name} Hz<br/>Modos: <strong>${p.value}</strong>`;
      },
    },
    grid: {
      left: "8%",
      right: "4%",
      top: 12,
      bottom: "18%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: frequencies.map((f) => `${f}`),
      axisLabel: {
        rotate: 45,
        fontSize: 10,
      },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
    },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
    ],
    series: [
      {
        id: "bonello",
        type: "bar",
        data: counts,
        itemStyle: {
          color: "#0f766e",
          borderRadius: [2, 2, 0, 0],
        },
        emphasis: {
          itemStyle: { color: "#14b8a6" },
        },
      },
    ],
  };

  return (
    <div className="mt-5 border-t pt-4">
      <p className="mb-2 text-sm font-semibold text-foreground">Cantidad de modos por frecuencia</p>
      <EChart option={option} className="h-[clamp(18rem,45vw,22rem)]" />
    </div>
  );
}
