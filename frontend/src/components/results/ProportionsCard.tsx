import type { ProporcionesResult } from "@/lib/types";

export function ProportionsCard({ proporciones }: { proporciones: ProporcionesResult }) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-gray-700">Proporciones de Sala</h3>
      <div className="mb-2 text-sm">
        <span className="text-gray-500">Proporción actual: </span>
        <span className="font-medium text-gray-800">
          1 : {proporciones.proporcion_actual[1]} : {proporciones.proporcion_actual[2]}
        </span>
      </div>
      <div className="mb-3 text-sm">
        <span className="text-gray-500">Más cercana: </span>
        <span className="font-medium text-indigo-600">{proporciones.mas_cercana}</span>
        <span className="text-gray-600">
          {" "}(1 : {proporciones.proporcion_cercana[1]} : {proporciones.proporcion_cercana[2]})
        </span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white">
            <tr>
              <th className="px-3 py-2 font-medium">Referencia</th>
              <th className="px-3 py-2 font-medium">Proporción</th>
              <th className="px-3 py-2 font-medium">Error</th>
            </tr>
          </thead>
          <tbody>
            {proporciones.todas.map(([nombre, r2, r3], i) => (
              <tr
                key={nombre}
                className={`border-b border-gray-100 transition-colors hover:bg-indigo-50/50 ${
                  i === 0 ? "bg-indigo-50" : ""
                }`}
              >
                <td className="px-3 py-1.5 text-gray-700">{nombre}</td>
                <td className="px-3 py-1.5 text-gray-700">1 : {r2} : {r3}</td>
                <td className="px-3 py-1.5 text-gray-700">
                  {i === 0 ? proporciones.error.toFixed(3) : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
