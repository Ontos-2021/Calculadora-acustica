export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  pageSize = 20,
  className = "",
}: {
  columns: { key: string; label: string; render?: (value: unknown, row: T) => React.ReactNode }[];
  data: T[];
  pageSize?: number;
  className?: string;
}) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gradient-to-r from-indigo-500 to-purple-600 text-white">
            {columns.map((col) => (
              <th key={col.key} className="px-4 py-3 font-medium">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.slice(0, pageSize).map((row, i) => (
            <tr
              key={i}
              className="border-b border-gray-100 transition-colors hover:bg-indigo-50/50"
            >
              {columns.map((col) => (
                <td key={col.key} className="px-4 py-2 text-gray-700">
                  {col.render
                    ? col.render(row[col.key], row)
                    : String(row[col.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > pageSize && (
        <p className="mt-2 text-center text-xs text-gray-600">
          Mostrando {pageSize} de {data.length} resultados
        </p>
      )}
    </div>
  );
}
