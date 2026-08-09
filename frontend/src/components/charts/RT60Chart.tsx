"use client";

import { EChart } from "./EChart";
import type { RT60Bandas } from "@/lib/types";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];
const METODOS = ["Sabine", "Eyring", "Millington", "FitzRoy"] as const;
type Metodo = (typeof METODOS)[number];
const COLORES: Record<Metodo, string> = {
  Sabine: "#0f766e",
  Eyring: "#0284c7",
  Millington: "#7c3aed",
  FitzRoy: "#d97706",
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
    <EChart
      option={option}
      className="h-[clamp(20rem,55vw,24rem)]"
      key="rt60-chart"
    />
  );
}
