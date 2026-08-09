import type { RT60Bandas, ObjetivoInfo } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";

const METODOS = ["Sabine", "Eyring", "Millington", "FitzRoy"] as const;
const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];

export function RT60Table({
  bandas,
  objetivo,
}: {
  bandas: RT60Bandas;
  objetivo: ObjetivoInfo | null;
}) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-gray-700">RT60 por Banda de Octava</h3>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white">
            <tr>
              <th className="px-3 py-2 font-medium">Banda</th>
              {METODOS.map((m) => (
                <th key={m} className="px-3 py-2 font-medium">{m} (s)</th>
              ))}
              {objetivo && <th className="px-3 py-2 font-medium">Objetivo (s)</th>}
            </tr>
          </thead>
          <tbody>
            {BANDAS.map((b) => {
              const diff = objetivo?.diferencias?.[b] ?? 0;
              return (
                <tr
                  key={b}
                  className="border-b border-gray-100 transition-colors hover:bg-indigo-50/50"
                >
                  <td className="px-3 py-1.5 font-medium text-gray-800">{b} Hz</td>
                  {METODOS.map((m) => (
                    <td key={m} className="px-3 py-1.5 text-gray-700">
                      {bandas[b]?.[m]?.toFixed(2) ?? "—"}
                    </td>
                  ))}
                  {objetivo && (
                    <td className={`px-3 py-1.5 font-medium ${diff > 0.2 ? "text-red-600" : "text-green-600"}`}>
                      {objetivo.valores[b]?.toFixed(2) ?? "—"}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {objetivo && (
        <p className="mt-2 text-xs text-gray-600">
          Objetivo para: <Badge variant="info">{objetivo.label}</Badge>
          {" — "}diferencias &gt; 0.2s marcadas en rojo
        </p>
      )}
    </div>
  );
}
