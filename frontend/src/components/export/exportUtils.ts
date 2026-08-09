import type { ReportBundle } from "@/lib/types";

function download(content: BlobPart, type: string, filename: string): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function csvCell(value: unknown): string {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return `"${(text ?? "").replaceAll('"', '""')}"`;
}

export function exportCSV(report: ReportBundle): void {
  const rows: unknown[][] = [["schema_version", "section", "item", "field", "value", "unit"]];
  const add = (section: string, item: string, field: string, value: unknown, unit = "") => {
    rows.push([report.schema_version, section, item, field, value, unit]);
  };
  add("metadata", "report", "generated_at", report.generated_at);
  add("metadata", "report", "certification", report.certification);
  add("provenance", report.provenance.id, "engine", report.provenance.label);
  add("provenance", report.provenance.id, "version", report.provenance.version);
  add("input", "room", "largo", report.input.largo, "m");
  add("input", "room", "ancho", report.input.ancho, "m");
  add("input", "room", "alto", report.input.alto, "m");
  add("input", "room", "uso", report.input.uso ?? "none");
  add("input", "environment", "temperature_c", report.input.environment.temperature_c, "degC");
  add("input", "environment", "relative_humidity", report.input.environment.relative_humidity, "%");
  add("input", "environment", "pressure_pa", report.input.environment.pressure_pa, "Pa");
  add("input", "environment", "include_air_attenuation", Boolean(report.input.include_air_attenuation));
  report.input.superficies.forEach((surface, index) => {
    add("input", `surface_${index}`, "material", surface.material);
    for (const [band, alpha] of Object.entries(surface.alphas ?? {})) add("input", `surface_${index}`, `alpha_${band}_hz`, alpha);
  });
  add("result", "summary", "rt60_promedio", report.results.rt60_promedio, "s");
  add("result", "summary", "schroeder", report.results.f_schroeder, "Hz");
  add("result", "summary", "sound_speed", report.results.sound_speed_m_s, "m/s");
  add("result", "summary", "bolt_inside", report.results.bolt_area.is_inside);
  add("result", "summary", "diffuse_field", report.results.diffuse_field.is_diffuse);
  for (const [band, methods] of Object.entries(report.results.rt60_bandas)) {
    for (const [method, value] of Object.entries(methods)) add("rt60", `${band}_hz`, method, value, "s");
    if (report.results.objetivo) add("target", `${band}_hz`, "rt60", report.results.objetivo.valores[band], "s");
  }
  report.results.modos.forEach((mode, index) => {
    add("mode", String(index + 1), "indices", mode.indices.join("/"));
    add("mode", String(index + 1), "frequency", mode.frecuencia, "Hz");
    add("mode", String(index + 1), "type", mode.tipo);
    add("mode", String(index + 1), "weight", mode.peso_db, "dB");
    add("mode", String(index + 1), "degenerate", mode.degenerado);
    add("mode", String(index + 1), "overlap", mode.solapado);
  });
  report.results.method_warnings.forEach((warning, index) => add("warning", String(index + 1), warning.code, warning.message));
  report.assumptions.forEach((assumption, index) => add("assumption", String(index + 1), "text", assumption));
  if (report.pressure) {
    add("pressure", "map", "quantity", report.pressure.quantity);
    add("pressure", "map", "max_frequency", report.pressure.max_freq, "Hz");
    add("pressure", "recommendation", "x", report.pressure.optimal_listening.x, "m");
    add("pressure", "recommendation", "y", report.pressure.optimal_listening.y, "m");
    add("pressure", "recommendation", "movement", report.pressure.optimal_listening.movement_m, "m");
    add("pressure", "recommendation", "improvement", report.pressure.optimal_listening.db_improvement, "dB");
    report.pressure.grid_y.forEach((y, yIndex) => report.pressure?.grid_x.forEach((x, xIndex) => {
      add("pressure_grid", `${xIndex}/${yIndex}`, `${x.toFixed(4)},${y.toFixed(4)}`, report.pressure?.pressure[yIndex][xIndex]);
    }));
  }
  for (const [name, artifact] of Object.entries(report.advanced)) add("advanced", name, "json", artifact);
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
  download(`\uFEFF${csv}`, "text/csv;charset=utf-8", "informe-acustico-completo.csv");
}

export function exportJSON(report: ReportBundle): void {
  download(JSON.stringify(report, null, 2), "application/json;charset=utf-8", "informe-acustico-completo.json");
}

function latexEscape(value: string): string {
  return value
    .replaceAll("\\", "\\textbackslash{}")
    .replaceAll("&", "\\&")
    .replaceAll("%", "\\%")
    .replaceAll("$", "\\$")
    .replaceAll("#", "\\#")
    .replaceAll("_", "\\_")
    .replaceAll("{", "\\{")
    .replaceAll("}", "\\}");
}

export function exportLatex(report: ReportBundle): void {
  const surfaces = report.input.superficies.map((surface, index) => `${index + 1} & ${latexEscape(surface.material)} \\\\`).join("\n");
  const rtRows = Object.entries(report.results.rt60_bandas).map(([band, values]) => `${band} & ${values.Sabine.toFixed(2)} & ${values.Eyring.toFixed(2)} & ${values.Millington.toFixed(2)} & ${values.FitzRoy.toFixed(2)} \\\\`).join("\n");
  const warnings = report.results.method_warnings.map((warning) => `\\item ${latexEscape(warning.message)}`).join("\n") || "\\item Ninguna advertencia metodológica emitida.";
  const source = `\\documentclass[11pt,a4paper]{article}
\\usepackage[utf8]{inputenc}
\\usepackage[spanish]{babel}
\\usepackage{booktabs}
\\usepackage[margin=2.2cm]{geometry}
\\title{Informe acústico profesional}
\\date{${latexEscape(report.generated_at)}}
\\begin{document}
\\maketitle
\\textbf{Esquema:} ${latexEscape(report.schema_version)}\\\\
\\textbf{Procedencia:} ${latexEscape(report.provenance.label)} v${latexEscape(report.provenance.version)}\\\\
\\textbf{No certificación:} estimación de ingeniería; validar con mediciones y normativa aplicable.
\\section{Entrada}
Sala de ${report.input.largo} $\\times$ ${report.input.ancho} $\\times$ ${report.input.alto} m. Ambiente: ${report.input.environment.temperature_c}~$^\\circ$C, ${report.input.environment.relative_humidity}\\% HR, ${report.input.environment.pressure_pa} Pa.
\\begin{tabular}{rl}\\toprule Superficie & Material \\\\ \\midrule
${surfaces}
\\bottomrule\\end{tabular}
\\section{Resumen}
RT60 Sabine medio: ${report.results.rt60_promedio.toFixed(1)} s. Velocidad del sonido: ${report.results.sound_speed_m_s.toFixed(2)} m/s. Frecuencia de Schroeder: ${report.results.f_schroeder.toFixed(1)} Hz.
\\begin{tabular}{rrrrr}\\toprule Hz & Sabine & Eyring & Millington & FitzRoy \\\\ \\midrule
${rtRows}
\\bottomrule\\end{tabular}
\\section{Advertencias}
\\begin{itemize}${warnings}\\end{itemize}
\\section{Resultados adicionales}
Se adjuntan ${Object.keys(report.advanced).length} conjuntos avanzados en la exportación JSON/CSV del mismo esquema. Modos: ${report.results.cantidad_modos}. ${report.pressure ? `Recomendación de escucha: (${report.pressure.optimal_listening.x.toFixed(2)}, ${report.pressure.optimal_listening.y.toFixed(2)}) m, mejora ${report.pressure.optimal_listening.db_improvement.toFixed(2)} dB.` : "Mapa de presión no calculado."}
\\end{document}
`;
  download(source, "application/x-tex;charset=utf-8", "informe-acustico.tex");
}

function typstEscape(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll('"', '\\"').replaceAll("#", "\\#");
}

export function exportTypst(report: ReportBundle): void {
  const rtRows = Object.entries(report.results.rt60_bandas).map(([band, values]) => `  [${band} Hz], [${values.Sabine.toFixed(2)}], [${values.Eyring.toFixed(2)}], [${values.Millington.toFixed(2)}], [${values.FitzRoy.toFixed(2)}],`).join("\n");
  const materials = report.input.superficies.map((surface, index) => `- Superficie ${index + 1}: ${typstEscape(surface.material)}`).join("\n");
  const source = `#set page(margin: 22mm)
#set text(lang: "es", size: 10pt)
= Informe acústico profesional
_Esquema ${report.schema_version}; generado ${typstEscape(report.generated_at)}_

*Procedencia:* ${typstEscape(report.provenance.label)} v${typstEscape(report.provenance.version)}

#block(fill: rgb("fff4d6"), inset: 8pt)[*No certificación:* estimación de ingeniería. Validar con mediciones in situ y normativa aplicable.]

== Entrada
Sala: ${report.input.largo} × ${report.input.ancho} × ${report.input.alto} m. Ambiente: ${report.input.environment.temperature_c} °C, ${report.input.environment.relative_humidity}% HR, ${report.input.environment.pressure_pa} Pa.

${materials}

== RT60 modelado
Promedio Sabine: ${report.results.rt60_promedio.toFixed(1)} s. Velocidad del sonido: ${report.results.sound_speed_m_s.toFixed(2)} m/s.

#table(columns: 5, [*Hz*], [*Sabine*], [*Eyring*], [*Millington*], [*FitzRoy*],
${rtRows}
)

== Resultados disponibles
Modos: ${report.results.cantidad_modos}. Artefactos avanzados: ${Object.keys(report.advanced).length}.
${report.pressure ? `Posición recomendada: (${report.pressure.optimal_listening.x.toFixed(2)}, ${report.pressure.optimal_listening.y.toFixed(2)}) m; movimiento ${report.pressure.optimal_listening.movement_m.toFixed(2)} m; mejora modelada ${report.pressure.optimal_listening.db_improvement.toFixed(2)} dB.` : "Mapa de presión no calculado."}
`;
  download(source, "text/plain;charset=utf-8", "informe-acustico.typ");
}
