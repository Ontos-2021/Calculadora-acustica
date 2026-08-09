"use client";

import ReactECharts from "echarts-for-react";

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
      left: "3%",
      right: "4%",
      bottom: "10%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: frequencies.map((f) => `${f}`),
      name: "Frecuencia (Hz)",
      axisLabel: {
        rotate: 45,
        fontSize: 10,
      },
    },
    yAxis: {
      type: "value",
      name: "Cantidad de modos",
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
          color: "#4a90d9",
          borderRadius: [2, 2, 0, 0],
        },
        emphasis: {
          itemStyle: { color: "#2563eb" },
        },
      },
    ],
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 380 }}
      notMerge
      lazyUpdate
    />
  );
}
