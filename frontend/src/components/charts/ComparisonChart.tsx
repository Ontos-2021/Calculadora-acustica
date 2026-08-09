"use client";

import type { RT60Bandas, ObjetivoInfo } from "@/lib/types";
import { EChart } from "./EChart";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

export function ComparisonChart({
  data,
  objetivo,
}: {
  data: RT60Bandas;
  objetivo: ObjetivoInfo;
}) {
  if (!data || !objetivo) return null;

  const actuales = BANDAS.map((b) => data[b]?.Sabine ?? 0);
  const objetivos = BANDAS.map((b) => objetivo.valores[b] ?? 0);

  const option = {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
    },
    legend: {
      data: ["Actual (Sabine)", "Objetivo"],
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
    series: [
      {
        id: "actual",
        name: "Actual (Sabine)",
        type: "bar",
        data: actuales.map((v, i) => ({
          value: v,
          itemStyle: {
            color: objetivos[i] > 0 && Math.abs(v - objetivos[i]) > 0.2
              ? "#e11d48"
              : "#0f766e",
          },
        })),
      },
      {
        id: "objetivo",
        name: "Objetivo",
        type: "bar",
        data: objetivos,
        itemStyle: {
          color: "#a1a1aa",
          opacity: 0.6,
        },
      },
    ],
  };

  return (
    <EChart
      option={option}
      className="h-[clamp(20rem,55vw,24rem)]"
    />
  );
}
