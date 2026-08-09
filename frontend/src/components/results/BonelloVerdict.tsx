import type { BonelloResult } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";

export function BonelloVerdict({ bonello }: { bonello: BonelloResult }) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h3 className="text-sm font-semibold text-gray-700">Criterio de Bonello</h3>
        {bonello.cumple ? (
          <Badge variant="success">✓ Cumple</Badge>
        ) : (
          <Badge variant="danger">✗ No cumple</Badge>
        )}
      </div>
      {bonello.cumple ? (
        <p className="mb-3 text-sm text-green-600">
          La cantidad de modos por banda aumenta monótonamente con la frecuencia.
        </p>
      ) : (
        <div className="mb-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          La distribución modal no es monótona.
          Considere ajustar las proporciones de la sala.
        </div>
      )}
      <div className="max-h-64 overflow-y-auto rounded-lg border border-gray-200" tabIndex={0} aria-label="Bandas del criterio de Bonello">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-gradient-to-r from-indigo-500 to-purple-600 text-white">
            <tr>
              <th className="px-3 py-2 font-medium">Banda (Hz)</th>
              <th className="px-3 py-2 font-medium">Modos</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(bonello.bandas).map(([banda, cantidad]) => (
              <tr
                key={banda}
                className="border-b border-gray-100 transition-colors hover:bg-indigo-50/50"
              >
                <td className="px-3 py-1.5 text-gray-700">{banda}</td>
                <td className="px-3 py-1.5 font-medium text-gray-800">{cantidad}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
