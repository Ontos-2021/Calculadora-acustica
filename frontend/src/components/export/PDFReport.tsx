import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";
import type { CalculateResponse } from "@/lib/types";

const styles = StyleSheet.create({
  page: {
    padding: 30,
    fontFamily: "Helvetica",
    fontSize: 10,
    color: "#333",
  },
  header: {
    marginBottom: 20,
    paddingBottom: 10,
    borderBottom: "2 solid #6366f1",
  },
  title: {
    fontSize: 20,
    fontWeight: "bold",
    color: "#6366f1",
  },
  subtitle: {
    fontSize: 10,
    color: "#666",
    marginTop: 4,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: "bold",
    color: "#444",
    marginBottom: 6,
    paddingBottom: 4,
    borderBottom: "1 solid #ddd",
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 3,
  },
  label: {
    color: "#666",
  },
  value: {
    fontWeight: "bold",
  },
  table: {
    marginTop: 6,
  },
  tableRow: {
    flexDirection: "row",
    borderBottom: "1 solid #eee",
    paddingVertical: 3,
  },
  tableHeader: {
    backgroundColor: "#6366f1",
    color: "white",
    fontWeight: "bold",
    paddingVertical: 4,
  },
  cell: {
    flex: 1,
    paddingHorizontal: 4,
  },
  cellCenter: {
    flex: 1,
    paddingHorizontal: 4,
    textAlign: "center",
  },
  badge: {
    fontSize: 8,
    color: "#666",
  },
  footer: {
    position: "absolute",
    bottom: 20,
    left: 30,
    right: 30,
    textAlign: "center",
    color: "#999",
    fontSize: 8,
    borderTop: "1 solid #eee",
    paddingTop: 8,
  },
});

export function PDFReport({
  data,
  room,
}: {
  data: CalculateResponse;
  room: { largo: number; ancho: number; alto: number };
}) {
  const now = new Date().toLocaleDateString("es-AR");
  return (
    <Document>
      <Page size="A4" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.title}>Informe Acústico</Text>
          <Text style={styles.subtitle}>
            Calculadora Acústica Profesional v1.0 — {now}
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Parámetros de la Sala</Text>
          <View style={styles.row}>
            <Text style={styles.label}>Dimensiones:</Text>
            <Text style={styles.value}>
              {room.largo} × {room.ancho} × {room.alto} m
            </Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Volumen:</Text>
            <Text style={styles.value}>
              {(room.largo * room.ancho * room.alto).toFixed(1)} m³
            </Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>RT60 promedio (Sabine):</Text>
            <Text style={styles.value}>{data.rt60_promedio} s</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>f<sub>Schroeder</sub>:</Text>
            <Text style={styles.value}>{data.f_schroeder} Hz</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Modos de Resonancia</Text>
          <Text style={styles.badge}>
            Total: {data.cantidad_modos} | Axiales: {data.distribucion.axiales} | Tangenciales:{" "}
            {data.distribucion.tangenciales} | Oblicuos: {data.distribucion.oblicuos} |{" "}
            Degenerados: {data.distribucion.degenerados} | Solapados: {data.distribucion.solapados}
          </Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Criterio de Bonello</Text>
          <Text>Veredicto: {data.bonello.cumple ? "✓ CUMPLE" : "✗ NO CUMPLE"}</Text>
          <Text style={styles.badge}>Total modos en bandas: {data.bonello.total_modos}</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>RT60 por Banda de Octava</Text>
          {["125", "250", "500", "1000", "2000", "4000"].map((banda) => (
            <View key={banda} style={styles.tableRow}>
              <Text style={[styles.cell, { fontWeight: "bold" }]}>{banda} Hz</Text>
              <Text style={styles.cellCenter}>
                S: {data.rt60_bandas[banda]?.Sabine?.toFixed(2)}s
              </Text>
              <Text style={styles.cellCenter}>
                E: {data.rt60_bandas[banda]?.Eyring?.toFixed(2)}s
              </Text>
              <Text style={styles.cellCenter}>
                M: {data.rt60_bandas[banda]?.Millington?.toFixed(2)}s
              </Text>
              <Text style={styles.cellCenter}>
                F: {data.rt60_bandas[banda]?.FitzRoy?.toFixed(2)}s
              </Text>
              {data.objetivo && (
                <Text style={styles.cellCenter}>
                  Obj: {data.objetivo.valores[banda]?.toFixed(2)}s
                </Text>
              )}
            </View>
          ))}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Proporciones de Sala</Text>
          <Text>
            Actual: 1 : {data.proporciones.proporcion_actual[1]} :{" "}
            {data.proporciones.proporcion_actual[2]}
          </Text>
          <Text>
            Más cercana: {data.proporciones.mas_cercana} (1 :{" "}
            {data.proporciones.proporcion_cercana[1]} : {data.proporciones.proporcion_cercana[2]})
          </Text>
        </View>

        {data.degeneracion_dimensiones.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Advertencias</Text>
            {data.degeneracion_dimensiones.map((w, i) => (
              <Text key={i}>• {w}</Text>
            ))}
          </View>
        )}

        <Text style={styles.footer}>
          Generado por Calculadora Acústica Profesional — Los valores son estimaciones y deben
          validarse con mediciones in situ.
        </Text>
      </Page>
    </Document>
  );
}
