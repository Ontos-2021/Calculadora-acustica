import { useMemo, useCallback } from "react";
import type { Mode } from "@/lib/types";

/** Evalúa la presión de un modo en un punto (x,y,z) — JS puro, rápido */
export function evaluatePointPressure(
  mode: Mode,
  x: number,
  y: number,
  z: number,
  largo: number,
  ancho: number,
  alto: number,
): number {
  const [nx, ny, nz] = mode.indices;
  const p =
    Math.cos((nx * Math.PI * x) / largo) *
    Math.cos((ny * Math.PI * y) / ancho) *
    Math.cos((nz * Math.PI * z) / alto);
  return Math.abs(p);
}

/** Evalúa la presión acumulada en un punto para todos los modos */
export function evaluateAccumulatedPressure(
  modes: Mode[],
  x: number,
  y: number,
  z: number,
  largo: number,
  ancho: number,
  alto: number,
): { pressure: number; flatness: number } {
  let totalEnergy = 0;
  const pressures: number[] = [];
  for (const mode of modes) {
    const p = evaluatePointPressure(mode, x, y, z, largo, ancho, alto);
    pressures.push(p);
    totalEnergy += p * p;
  }
  const mean = pressures.reduce((a, b) => a + b, 0) / pressures.length;
  const variance =
    pressures.reduce((sum, v) => sum + (v - mean) ** 2, 0) / pressures.length;
  return {
    pressure: Math.sqrt(totalEnergy / modes.length),
    flatness: 1 / (1 + variance),
  };
}
