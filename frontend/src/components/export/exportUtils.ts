import type { CalculateResponse } from "@/lib/types";

export function exportCSV(data: CalculateResponse): void {
  const headers = [
    "nx", "ny", "nz", "frecuencia",
    "tipo", "peso_db", "degenerado", "solapado",
  ];
  const rows = data.modos.map((m) => [
    m.indices[0], m.indices[1], m.indices[2], m.frecuencia,
    m.tipo, m.peso_db, m.degenerado ? "Sí" : "No", m.solapado ? "Sí" : "No",
  ]);
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "modos_resonancia.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function exportJSON(data: CalculateResponse): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "resultados_acusticos.json";
  a.click();
  URL.revokeObjectURL(url);
}
