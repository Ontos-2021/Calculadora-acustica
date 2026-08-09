"use client";

import ReactECharts from "echarts-for-react";
import type { RT60Bandas } from "@/lib/types";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];
const METODOS = ["Sabine", "Eyring", "Millington", "FitzRoy"] as const;
type Metodo = (typeof METODOS)[number];
const COLORES: Record<Metodo, string> = {
  Sabine: "#e74c3c",
  Eyring: "#3498db",
  Millington: "#2ecc71",
  FitzRoy: "#f39c12",
};

export function RT60Chart({ data }: { data: RT60Bandas }) {
  if (!data) return null;

  const option = {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
    },
    legend: {
      data: METODOS,
      bottom: 0,
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "15%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: BANDAS.map((b) => `${b} Hz`),
      name: "Frecuencia",
    },
    yAxis: {
      type: "value",
      name: "RT60 (s)",
    },
    dataZoom: [
      { type: "inside", start: 0, end: 100 },
    ],
    series: METODOS.map((metodo) => ({
      id: `rt60-${metodo}`,
      name: metodo,
      type: "bar",
      data: BANDAS.map((b) => data[b]?.[metodo] ?? 0),
      itemStyle: { color: COLORES[metodo] },
      emphasis: { focus: "series" },
    })),
  };

  return (
    <ReactECharts
      option={option}
      style={{ height: 380 }}
      notMerge
      lazyUpdate
      key="rt60-chart"
    />
  );
}
