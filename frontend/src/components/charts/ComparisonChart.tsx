"use client";

import ReactECharts from "echarts-for-react";
import type { RT60Bandas, ObjetivoInfo } from "@/lib/types";

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
              ? "#e74c3c"
              : "#3498db",
          },
        })),
      },
      {
        id: "objetivo",
        name: "Objetivo",
        type: "bar",
        data: objetivos,
        itemStyle: {
          color: "#95a5a6",
          opacity: 0.6,
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
