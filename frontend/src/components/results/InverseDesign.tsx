"use client";

import type { InverseDesignResponse } from "@/lib/types";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

const ISO_COLORS: Record<string, string> = {
  A: "bg-green-100 text-green-800",
  B: "bg-blue-100 text-blue-800",
  C: "bg-yellow-100 text-yellow-800",
  D: "bg-orange-100 text-orange-800",
  E: "bg-red-100 text-red-800",
};

interface Props {
  data: InverseDesignResponse;
}

export function InverseDesign({ data }: Props) {
  const totalMissing = Object.values(data.missing_absorption).reduce((a, b) => a + b, 0);
  if (totalMissing <= 0) {
    return (
      <div className="rounded-lg bg-green-50 p-4 text-sm text-green-700">
        La sala ya cumple con el RT60 objetivo. No se requiere tratamiento adicional.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h3 className="text-base font-semibold text-gray-800">Diseño inverso</h3>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="px-3 py-2 text-left font-medium text-gray-600">Banda</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Actual (m²)</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Requerido (m²)</th>
              <th className="px-3 py-2 text-right font-medium text-gray-600">Faltante (m²)</th>
            </tr>
          </thead>
          <tbody>
            {BANDAS.map((b) => (
              <tr key={b} className="border-b">
                <td className="px-3 py-2 font-medium">{b} Hz</td>
                <td className="px-3 py-2 text-right">{data.current_absorption[b]?.toFixed(2)}</td>
                <td className="px-3 py-2 text-right">{data.required_absorption[b]?.toFixed(2)}</td>
                <td className="px-3 py-2 text-right font-semibold">
                  <span className={data.missing_absorption[b] > 0 ? "text-red-600" : "text-green-600"}>
                    {data.missing_absorption[b]?.toFixed(2)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.material_suggestions.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">Materiales sugeridos</h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.material_suggestions.map((s, i) => (
              <div key={i} className="rounded-lg border p-3 text-sm">
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-medium text-gray-800">{s.material}</span>
                  {s.iso_class && s.iso_class !== "No clasificado" && (
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${ISO_COLORS[s.iso_class] || "bg-gray-100"}`}>
                      {s.iso_class}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500">{s.categoria}</p>
                <p className="mt-2 text-lg font-bold text-indigo-600">
                  {s.area_needed_m2} m²
                </p>
                <p className="text-xs text-gray-500">
                  α<sub>w</sub> = {s.alpha_w?.toFixed(2) ?? "—"}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.placement_suggestions.length > 0 && (
        <div>
          <h4 className="mb-2 text-sm font-semibold text-gray-700">Colocación sugerida</h4>
          <div className="space-y-2">
            {data.placement_suggestions.map((p, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                <div>
                  <span className="font-medium text-gray-800">{p.surface}</span>
                  <span className="ml-2 text-xs text-gray-500">({p.surface_area_m2} m²)</span>
                </div>
                <div className="text-right">
                  <span className="font-semibold text-indigo-600">{p.coverage_percent}%</span>
                  <span className="ml-2 text-xs text-gray-500">cubrimiento</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
