import type { Mode } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";

export function ModeTable({ modos }: { modos: Mode[] }) {
  if (!modos || modos.length === 0) {
    return (
      <div className="rounded-lg bg-gray-50 p-6 text-center text-sm text-gray-400">
        No se encontraron modos de resonancia.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <Badge variant="success">Axiales (0 dB)</Badge>
        <Badge variant="warning">Tangenciales (−3 dB)</Badge>
        <Badge variant="default">Oblicuos (−6 dB)</Badge>
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
            {modos.map((m, i) => (
              <tr
                key={i}
                className="border-b border-gray-100 transition-colors hover:bg-indigo-50/50"
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
