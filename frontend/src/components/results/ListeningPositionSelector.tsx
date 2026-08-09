"use client";

import { useState, useCallback, useMemo } from "react";
import type { Mode } from "@/lib/types";
import { evaluateAccumulatedPressure } from "@/lib/pressure";

export function ListeningPositionSelector({
  modes,
  largo,
  ancho,
  alto,
  earHeight = 1.2,
}: {
  modes: Mode[];
  largo: number;
  ancho: number;
  alto: number;
  earHeight?: number;
}) {
  const [x, setX] = useState(largo * 0.38);
  const [y, setY] = useState(ancho * 0.38);

  const result = useMemo(
    () => evaluateAccumulatedPressure(modes, x, y, earHeight, largo, ancho, alto),
    [modes, x, y, earHeight, largo, ancho, alto],
  );

  const pressurePercent = Math.round(result.pressure * 100);
  const flatnessPercent = Math.round(result.flatness * 100);

  const pressureColor =
    pressurePercent > 70
      ? "text-red-600"
      : pressurePercent > 40
        ? "text-amber-600"
        : "text-green-600";

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <h4 className="mb-3 text-sm font-semibold text-gray-700">
        Posición de Escucha Interactiva
      </h4>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="escucha-x" className="block text-xs font-medium text-gray-500">
            X: {x.toFixed(2)} m
          </label>
          <input
            id="escucha-x"
            type="range"
            min={0.1}
            max={largo - 0.1}
            step={0.05}
            value={x}
            onChange={(e) => setX(Number(e.target.value))}
            className="mt-1 w-full"
          />
        </div>
        <div>
          <label htmlFor="escucha-y" className="block text-xs font-medium text-gray-500">
            Y: {y.toFixed(2)} m
          </label>
          <input
            id="escucha-y"
            type="range"
            min={0.1}
            max={ancho - 0.1}
            step={0.05}
            value={y}
            onChange={(e) => setY(Number(e.target.value))}
            className="mt-1 w-full"
          />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="rounded-lg bg-white p-2 text-center shadow-sm">
          <p className="text-xs text-gray-600">Presión acumulada</p>
          <p className={`text-lg font-bold ${pressureColor}`}>
            {pressurePercent}%
          </p>
        </div>
        <div className="rounded-lg bg-white p-2 text-center shadow-sm">
          <p className="text-xs text-gray-600">Uniformidad espectral</p>
          <p className="text-lg font-bold text-indigo-600">{flatnessPercent}%</p>
        </div>
      </div>

      <p className="mt-2 text-[10px] text-gray-600">
        Arrastre los sliders para encontrar la mejor posición de escucha.
        Menor presión acumulada en nodos; mayor uniformidad = respuesta más plana.
      </p>
    </div>
  );
}
