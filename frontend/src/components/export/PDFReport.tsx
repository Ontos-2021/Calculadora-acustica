import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";
import type { ReportBundle } from "@/lib/types";

const styles = StyleSheet.create({
  page: { paddingTop: 34, paddingBottom: 46, paddingHorizontal: 34, fontFamily: "Helvetica", fontSize: 9, color: "#1f2937", lineHeight: 1.35 },
  header: { marginBottom: 14, paddingBottom: 8, borderBottom: "2 solid #4f46e5" },
  title: { fontSize: 20, fontWeight: "bold", color: "#4338ca" },
  subtitle: { marginTop: 3, color: "#4b5563" },
  section: { marginBottom: 13 },
  sectionTitle: { fontSize: 12, fontWeight: "bold", color: "#312e81", marginBottom: 5, borderBottom: "1 solid #c7d2fe", paddingBottom: 3 },
  row: { flexDirection: "row", borderBottom: "0.5 solid #e5e7eb", paddingVertical: 2 },
  label: { width: "38%", color: "#6b7280" },
  value: { width: "62%", fontWeight: "bold" },
  tableHeader: { flexDirection: "row", backgroundColor: "#4f46e5", color: "white", paddingVertical: 3 },
  tableRow: { flexDirection: "row", borderBottom: "0.5 solid #e5e7eb", paddingVertical: 2 },
  cell: { flex: 1, paddingHorizontal: 2, textAlign: "right" },
  firstCell: { flex: 1, paddingHorizontal: 2, textAlign: "left" },
  warning: { backgroundColor: "#fffbeb", border: "1 solid #fde68a", padding: 6, marginBottom: 3 },
  note: { color: "#4b5563", fontSize: 8 },
  code: { fontFamily: "Courier", fontSize: 6.5, backgroundColor: "#f3f4f6", padding: 5 },
  footer: { position: "absolute", bottom: 18, left: 34, right: 34, borderTop: "1 solid #d1d5db", paddingTop: 5, color: "#6b7280", fontSize: 7, flexDirection: "row", justifyContent: "space-between" },
});

const BANDS = ["125", "250", "500", "1000", "2000", "4000"];

export function PDFReport({ report }: { report: ReportBundle }) {
  return (
    <Document title="Informe acústico profesional" author="Calculadora Acústica Profesional" subject={report.schema_version}>
      <Page size="A4" style={styles.page} wrap>
        <View style={styles.header}>
          <Text style={styles.title}>Informe Acústico Profesional</Text>
          <Text style={styles.subtitle}>{report.schema_version} | {new Date(report.generated_at).toLocaleString("es")}</Text>
        </View>

        <View style={styles.warning}>
          <Text>ESTIMACIÓN DE INGENIERÍA. Este documento no es una medición, ensayo de producto, certificado ni verificación de cumplimiento. Valide resultados, montaje y normativa aplicable con profesionales y mediciones in situ.</Text>
        </View>

        <Section title="Procedencia y alcance">
          <ReportRow label="Motor" value={`${report.provenance.label} v${report.provenance.version}`} />
          <ReportRow label="Ejecución offline" value={report.provenance.offline ? "Sí" : "No"} />
          <ReportRow label="Clasificación" value={report.certification} />
          {report.assumptions.map((assumption, index) => <Text key={index} style={styles.note}>- {assumption}</Text>)}
        </Section>

        <Section title="Entrada de sala y ambiente">
          <ReportRow label="Dimensiones" value={`${report.input.largo} x ${report.input.ancho} x ${report.input.alto} m`} />
          <ReportRow label="Volumen" value={`${(report.input.largo * report.input.ancho * report.input.alto).toFixed(2)} m3`} />
          <ReportRow label="Uso" value={report.input.uso || "Sin objetivo seleccionado"} />
          <ReportRow label="Ambiente" value={`${report.input.environment.temperature_c.toFixed(1)} deg C | ${report.input.environment.relative_humidity.toFixed(1)} % HR | ${report.input.environment.pressure_pa.toFixed(0)} Pa`} />
          <ReportRow label="Velocidad del sonido" value={`${report.results.sound_speed_m_s.toFixed(2)} m/s`} />
          <ReportRow label="Atenuación de aire" value={report.input.include_air_attenuation ? "Incluida" : "No incluida"} />
          {report.input.superficies.map((surface, index) => <ReportRow key={index} label={`Superficie ${index + 1}`} value={`${surface.material}${surface.alphas ? ` | alpha personalizado: ${JSON.stringify(surface.alphas)}` : ""}`} />)}
        </Section>

        <Section title="Resumen acústico">
          <ReportRow label="RT60 Sabine medio" value={`${report.results.rt60_promedio.toFixed(1)} s`} />
          <ReportRow label="Frecuencia de Schroeder" value={`${report.results.f_schroeder.toFixed(1)} Hz`} />
          <ReportRow label="Ancho modal" value={`${report.results.delta_f.toFixed(2)} Hz`} />
          <ReportRow label="Modos" value={`${report.results.cantidad_modos} | axial ${report.results.distribucion.axiales} | tangencial ${report.results.distribucion.tangenciales} | oblicuo ${report.results.distribucion.oblicuos}`} />
          <ReportRow label="Bonello" value={report.results.bonello.cumple ? "Cumple el criterio implementado" : "No cumple el criterio implementado"} />
          <ReportRow label="Campo difuso modal" value={report.results.diffuse_field.is_diffuse ? "Indicador favorable" : "No establecido"} />
          <ReportRow label="Área de Bolt" value={report.results.bolt_area.is_inside ? "Dentro" : `Fuera; distancia ${report.results.bolt_area.distance.toFixed(3)}`} />
        </Section>

        <Section title="RT60 por banda (s)">
          <View style={styles.tableHeader}><Text style={styles.firstCell}>Hz</Text><Text style={styles.cell}>Sabine</Text><Text style={styles.cell}>Eyring</Text><Text style={styles.cell}>Millington</Text><Text style={styles.cell}>FitzRoy</Text><Text style={styles.cell}>Objetivo</Text></View>
          {BANDS.map((band) => { const values = report.results.rt60_bandas[band]; return <View key={band} style={styles.tableRow}><Text style={styles.firstCell}>{band}</Text><Text style={styles.cell}>{values.Sabine.toFixed(2)}</Text><Text style={styles.cell}>{values.Eyring.toFixed(2)}</Text><Text style={styles.cell}>{values.Millington.toFixed(2)}</Text><Text style={styles.cell}>{values.FitzRoy.toFixed(2)}</Text><Text style={styles.cell}>{report.results.objetivo?.valores[band]?.toFixed(2) ?? "-"}</Text></View>; })}
        </Section>

        <Section title="Advertencias">
          {[...report.results.degeneracion_dimensiones, ...report.results.method_warnings.map((warning) => warning.message)].length === 0
            ? <Text style={styles.note}>No se emitieron advertencias automáticas. Esto no elimina incertidumbres no modeladas.</Text>
            : [...report.results.degeneracion_dimensiones, ...report.results.method_warnings.map((warning) => warning.message)].map((warning, index) => <Text key={index} style={styles.warning}>- {warning}</Text>)}
        </Section>

        <Section title="Modos de resonancia (primeros 36)">
          <View style={styles.tableHeader}><Text style={styles.firstCell}>Índices</Text><Text style={styles.cell}>Hz</Text><Text style={styles.cell}>Tipo</Text><Text style={styles.cell}>Peso dB</Text><Text style={styles.cell}>Flags</Text></View>
          {report.results.modos.slice(0, 36).map((mode, index) => <View key={index} style={styles.tableRow}><Text style={styles.firstCell}>{mode.indices.join(",")}</Text><Text style={styles.cell}>{mode.frecuencia.toFixed(2)}</Text><Text style={styles.cell}>{mode.tipo}</Text><Text style={styles.cell}>{mode.peso_db.toFixed(0)}</Text><Text style={styles.cell}>{`${mode.degenerado ? "D" : "-"}/${mode.solapado ? "S" : "-"}`}</Text></View>)}
        </Section>

        {report.pressure && <Section title="Presión modal y posición de escucha"><ReportRow label="Cantidad" value={report.pressure.quantity} /><ReportRow label="Contexto" value={`${report.pressure.num_modos} modos | ${report.pressure.max_freq.toFixed(1)} Hz | oído ${report.pressure.ear_height.toFixed(2)} m`} /><ReportRow label="Posición recomendada" value={`X ${report.pressure.optimal_listening.x.toFixed(2)} m | Y ${report.pressure.optimal_listening.y.toFixed(2)} m`} /><ReportRow label="Movimiento" value={`${report.pressure.optimal_listening.movement_m.toFixed(2)} m | mejora modelada ${report.pressure.optimal_listening.db_improvement.toFixed(2)} dB`} /><Text style={styles.note}>Mapa acumulado: suma energética sin fase relativa. Confirmar con mediciones espaciales.</Text></Section>}

        {report.impulse_response && <Section title="Respuesta al impulso modelada"><ReportRow label="Muestreo" value={`${report.impulse_response.sample_rate} Hz`} /><ReportRow label="Fuentes imagen" value={String(report.impulse_response.image_source_count)} /><ReportRow label="Retraso directo" value={`${report.impulse_response.direct_delay_ms.toFixed(2)} ms`} /><Text style={styles.code}>{boundedJson(report.impulse_response.parameters)}</Text></Section>}

        {Object.keys(report.advanced).length > 0 && <Section title="Tratamiento, aislamiento, medición y métodos numéricos"><Text style={styles.note}>Se incluyen resúmenes serializados. JSON y CSV conservan todos los valores y matrices disponibles.</Text>{Object.entries(report.advanced).map(([name, value]) => <View key={name} wrap={false}><Text style={{ fontWeight: "bold", marginTop: 5 }}>{name.replaceAll("_", " ")}</Text><Text style={styles.code}>{boundedJson(value)}</Text></View>)}</Section>}

        <View style={styles.footer} fixed><Text>Calculadora Acústica Profesional | No certificación</Text><Text render={({ pageNumber, totalPages }) => `Página ${pageNumber} / ${totalPages}`} /></View>
      </Page>
    </Document>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{children}</View>;
}

function ReportRow({ label, value }: { label: string; value: string }) {
  return <View style={styles.row}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value}</Text></View>;
}

function boundedJson(value: unknown): string {
  const serialized = JSON.stringify(value, null, 1) ?? "Sin datos";
  return serialized.length > 3500 ? `${serialized.slice(0, 3500)}\n… resumen truncado en PDF; datos completos en JSON/CSV` : serialized;
}
