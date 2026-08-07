"use client";

import { useState, useMemo, useCallback } from "react";
import type { Mode } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";

export function ModeTable({
  modos,
  onSelectMode,
  selectedFreq,
}: {
  modos: Mode[];
  onSelectMode?: (frecuencia: number) => void;
  selectedFreq?: number | null;
}) {
  const [filterType, setFilterType] = useState<string>("all");
  const [freqMin, setFreqMin] = useState("");
  const [freqMax, setFreqMax] = useState("");

  const filtered = useMemo(() => {
    let result = modos;
    if (filterType !== "all") {
      result = result.filter((m) => m.tipo === filterType);
    }
    const min = parseFloat(freqMin);
    const max = parseFloat(freqMax);
    if (!isNaN(min)) result = result.filter((m) => m.frecuencia >= min);
    if (!isNaN(max)) result = result.filter((m) => m.frecuencia <= max);
    return result;
  }, [modos, filterType, freqMin, freqMax]);

  if (!modos || modos.length === 0) {
    return (
      <div className="rounded-lg bg-gray-50 p-6 text-center text-sm text-gray-400">
        No se encontraron modos de resonancia.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge variant="success">Axiales (0 dB)</Badge>
        <Badge variant="warning">Tangenciales (−3 dB)</Badge>
        <Badge variant="default">Oblicuos (−6 dB)</Badge>
        <span className="ml-auto text-xs text-gray-400">
          {filtered.length} de {modos.length} modos
        </span>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          className="rounded-lg border border-gray-300 px-2 py-1 text-xs"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="all">Todos</option>
          <option value="axial">Axiales</option>
          <option value="tangencial">Tangenciales</option>
          <option value="oblicuo">Oblicuos</option>
        </select>
        <input
          type="number"
          placeholder="Frec. min"
          className="w-20 rounded-lg border border-gray-300 px-2 py-1 text-xs"
          value={freqMin}
          onChange={(e) => setFreqMin(e.target.value)}
        />
        <input
          type="number"
          placeholder="Frec. max"
          className="w-20 rounded-lg border border-gray-300 px-2 py-1 text-xs"
          value={freqMax}
          onChange={(e) => setFreqMax(e.target.value)}
        />
        {onSelectMode && (
          <span className="text-[10px] text-gray-400">
            Click en una fila para ver el mapa de presión del modo
          </span>
        )}
      </div>

      <div className="max-h-96 overflow-y-auto rounded-lg border border-gray-200">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-gradient-to-r from-indigo-500 to-purple-600 text-white">
            <tr>
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">nx</th>
              <th className="px-3 py-2 font-medium">ny</th>
              <th className="px-3 py-2 font-medium">nz</th>
              <th className="px-3 py-2 font-medium">Frec (Hz)</th>
              <th className="px-3 py-2 font-medium">Tipo</th>
              <th className="px-3 py-2 font-medium">Flags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((m, i) => (
              <tr
                key={i}
                onClick={() => onSelectMode?.(m.frecuencia)}
                className={`cursor-pointer border-b border-gray-100 transition-colors hover:bg-indigo-50/50 ${
                  selectedFreq === m.frecuencia ? "bg-indigo-100" : ""
                }`}
              >
                <td className="px-3 py-1.5 text-gray-500">{i + 1}</td>
                <td className="px-3 py-1.5 text-gray-700">{m.indices[0]}</td>
                <td className="px-3 py-1.5 text-gray-700">{m.indices[1]}</td>
                <td className="px-3 py-1.5 text-gray-700">{m.indices[2]}</td>
                <td className="px-3 py-1.5 font-medium text-gray-800">{m.frecuencia}</td>
                <td className="px-3 py-1.5">
                  {m.tipo === "axial" && <Badge variant="success">Ax</Badge>}
                  {m.tipo === "tangencial" && <Badge variant="warning">Tg</Badge>}
                  {m.tipo === "oblicuo" && <Badge variant="default">Ob</Badge>}
                </td>
                <td className="px-3 py-1.5">
                  {m.degenerado && <Badge variant="danger">Deg</Badge>}
                  {m.solapado && <Badge variant="info">Sol</Badge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
