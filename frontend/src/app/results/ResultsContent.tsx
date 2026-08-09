"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { PDFDownloadLink } from "@react-pdf/renderer";

import type {
  AdvancedArtifacts,
  CalculateRequest,
  CalculateResponse,
  EngineProvenance,
  IRResponse,
  PressureMapResponse,
  ReportBundle,
} from "@/lib/types";
import { calculateWithOffline, pressureMapWithOffline } from "@/lib/offline";
import { decodeRequestData } from "@/lib/transport";
import { roomPayload } from "@/lib/room";
import { useLicense } from "@/context/LicenseProvider";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { TabContainer } from "@/components/ui/TabContainer";
import { PDFReport } from "@/components/export/PDFReport";
import { exportCSV, exportJSON, exportLatex, exportTypst } from "@/components/export/exportUtils";
import { SummaryCards } from "@/components/results/SummaryCards";
import { ModeTable } from "@/components/results/ModeTable";
import { BonelloVerdict } from "@/components/results/BonelloVerdict";
import { ProportionsCard } from "@/components/results/ProportionsCard";
import { RT60Table } from "@/components/results/RT60Table";
import { DimensionWarnings } from "@/components/results/DimensionWarnings";
import { RT60Chart } from "@/components/charts/RT60Chart";
import { BonelloChart } from "@/components/charts/BonelloChart";
import { ComparisonChart } from "@/components/charts/ComparisonChart";
import { PressureMapChart } from "@/components/charts/PressureMapChart";
import { TreatmentTools } from "@/components/results/TreatmentTools";
import { AbsorberCalculators } from "@/components/results/AbsorberCalculators";
import { DiffuserCalculators } from "@/components/results/DiffuserCalculators";
import { IsolationCalculators } from "@/components/results/IsolationCalculators";
import { MeasurementTools } from "@/components/results/MeasurementTools";
import { NumericalMethods } from "@/components/results/NumericalMethods";
import { ImpulseResponseTool } from "@/components/results/ImpulseResponseTool";

export default function ResultsContent() {
  const searchParams = useSearchParams();
  const encodedRequest = searchParams.get("data");
  const { status, hasEntitlement, apiKey } = useLicense();
  const [data, setData] = useState<CalculateResponse | null>(null);
  const [request, setRequest] = useState<CalculateRequest | null>(null);
  const [provenance, setProvenance] = useState<EngineProvenance | null>(null);
  const [fallbackReason, setFallbackReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [activeTab, setActiveTab] = useState("analysis");

  const [pressureData, setPressureData] = useState<PressureMapResponse | null>(null);
  const [pressureLoading, setPressureLoading] = useState(false);
  const [pressureError, setPressureError] = useState<string | null>(null);
  const [pressureRefresh, setPressureRefresh] = useState(0);
  const [selectedMode, setSelectedMode] = useState("all");
  const [maxFreq, setMaxFreq] = useState(300);
  const [irData, setIrData] = useState<IRResponse | null>(null);
  const [advanced, setAdvanced] = useState<AdvancedArtifacts>({});

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      setData(null);
      if (!encodedRequest) {
        setError("No se encontraron datos de cálculo.");
        setLoading(false);
        return;
      }
      try {
        const decoded = decodeRequestData(encodedRequest);
        setRequest(decoded);
        const outcome = await calculateWithOffline(decoded, apiKey, controller.signal);
        if (controller.signal.aborted) return;
        setData(outcome.data);
        setProvenance(outcome.provenance);
        setFallbackReason(outcome.fallbackReason ?? null);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "No se pudo completar el análisis.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [encodedRequest, refresh, apiKey]);

  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setPressureLoading(true);
      setPressureError(null);
      try {
        const indices = selectedMode === "all"
          ? undefined
          : selectedMode.split(",").map(Number) as [number, number, number];
        const outcome = await pressureMapWithOffline({
          ...roomPayload(request),
          ear_height: Math.min(1.2, request.alto),
          max_freq: maxFreq,
          grid_size: 64,
          ...(indices ? { mode_indices: indices } : {}),
        }, apiKey, controller.signal);
        if (controller.signal.aborted) return;
        setPressureData(outcome.data);
        setAdvanced((current) => ({ ...current, pressure_provenance: outcome.provenance }));
      } catch (cause) {
        if (controller.signal.aborted) return;
        setPressureError(cause instanceof Error ? cause.message : "No se pudo actualizar el mapa de presión.");
      } finally {
        if (!controller.signal.aborted) setPressureLoading(false);
      }
    }, 220);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [request, selectedMode, maxFreq, pressureRefresh, apiKey]);

  function recordArtifact(name: string, result: unknown) {
    setAdvanced((current) => ({ ...current, [name]: result }));
  }

  if (loading) {
    return <div className="mx-auto max-w-5xl"><Card aria-busy="true"><CardTitle>Calculando…</CardTitle><LoadingSkeleton rows={8} /></Card></div>;
  }

  if (error || !data || !request || !provenance) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert" aria-live="assertive">{error || "No hay resultados disponibles."}</div>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {encodedRequest && <button type="button" onClick={() => setRefresh((value) => value + 1)} className="rounded-lg border border-indigo-300 px-4 py-2 text-sm font-medium text-indigo-700">Reintentar</button>}
            <Link href="/" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white">Volver</Link>
          </div>
        </Card>
      </div>
    );
  }

  const selectedFrequency = selectedMode === "all"
    ? null
    : data.modos.find((mode) => mode.indices.join(",") === selectedMode)?.frecuencia ?? null;
  const report: ReportBundle = {
    schema_version: "acoustic-report/2.0",
    generated_at: new Date().toISOString(),
    input: request,
    results: data,
    pressure: pressureData,
    impulse_response: irData,
    advanced,
    treatment: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("treatment_") || key.startsWith("absorber_") || key.startsWith("diffuser_"))),
    isolation: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("isolation_"))),
    measurement: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("measurement_"))),
    numerical: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("numerical_"))),
    provenance,
    assumptions: [...provenance.assumptions, "La selección de materiales representa condiciones nominales; juntas, montaje, mobiliario y ocupación real no se reconstruyen automáticamente."],
    certification: "engineering_estimate_not_measurement_or_certification",
  };
  const professionalExports = status?.tier !== "FREE" && hasEntitlement("exports");

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className={`rounded-xl border p-3 text-sm ${provenance.offline ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`} role="status" aria-live="polite" data-testid="engine-source">
        <strong>Motor:</strong> {provenance.label} v{provenance.version}.{fallbackReason ? ` Fallback offline: ${fallbackReason}.` : ""}
      </div>
      <SummaryCards data={data} />

      <TabContainer activeTab={activeTab} onTabChange={setActiveTab} tabs={[
        { key: "analysis", label: "Análisis", badge: String(data.cantidad_modos) },
        { key: "pressure", label: "Presión" },
        { key: "design", label: "Diseño" },
        { key: "isolation", label: "Aislamiento" },
        { key: "measurement", label: "Medición" },
        { key: "numerical", label: "Numérico" },
      ]}>
        <div className="space-y-6">
          <ModelContext data={data} request={request} provenance={provenance} />
          {data.degeneracion_dimensiones.length > 0 && <DimensionWarnings warnings={data.degeneracion_dimensiones} />}
          <Card>
            <CardTitle>Modos de Resonancia <span className="ml-2 text-sm font-normal text-gray-500">({data.cantidad_modos} modos)</span></CardTitle>
            <ModeTable modos={data.modos} selectedFreq={selectedFrequency} onSelectMode={(mode) => { setSelectedMode(mode.indices.join(",")); setActiveTab("pressure"); }} />
          </Card>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card><div className="space-y-4"><BonelloVerdict bonello={data.bonello} /><BonelloChart bandas={data.bonello.bandas} /></div></Card>
            <Card><ProportionsCard proporciones={data.proporciones} /></Card>
          </div>
          <Card>
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div><h3 className="mb-3 text-sm font-semibold text-gray-700">RT60 por método</h3><RT60Chart data={data.rt60_bandas} /></div>
              {data.objetivo ? <div><h3 className="mb-3 text-sm font-semibold text-gray-700">Actual vs. objetivo</h3><ComparisonChart data={data.rt60_bandas} objetivo={data.objetivo} /></div> : <div className="flex items-center justify-center rounded-lg bg-gray-50 p-8 text-sm text-gray-500">Selecciona un uso para comparar objetivos.</div>}
            </div>
            <div className="mt-6"><RT60Table bandas={data.rt60_bandas} objetivo={data.objetivo} /></div>
          </Card>
        </div>

        <div className="space-y-4">
          {pressureData ? (
            <Card aria-busy={pressureLoading}>
              <CardTitle>Mapa de presión modal</CardTitle>
              {pressureLoading && <p className="mb-3 rounded-lg bg-indigo-50 p-2 text-xs text-indigo-800" role="status" aria-live="polite">Actualizando datos; el mapa anterior se muestra atenuado.</p>}
              {pressureError && <div className="mb-3 flex flex-wrap justify-between gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert"><span>{pressureError}</span><button type="button" className="font-semibold underline" onClick={() => setPressureRefresh((value) => value + 1)}>Reintentar</button></div>}
              <PressureMapChart data={pressureData} modes={data.modos} selectedMode={selectedMode} onSelectMode={setSelectedMode} onMaxFreqChange={setMaxFreq} maxFreq={maxFreq} loading={pressureLoading} />
              <ListeningRecommendation data={pressureData} />
            </Card>
          ) : (
            <Card><p className="text-sm text-gray-600" role="status">{pressureLoading ? "Calculando mapa de presión…" : pressureError || "Mapa pendiente."}</p>{pressureError && <button type="button" onClick={() => setPressureRefresh((value) => value + 1)} className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white">Reintentar</button>}</Card>
          )}
        </div>

        <TabContainer compact label="Diseño acústico" tabs={[{ key: "treatment", label: "Tratamiento" }, { key: "absorbers", label: "Absorbentes" }, { key: "diffusers", label: "Difusores" }]}>
          <TreatmentTools room={request} analysis={data} onResult={recordArtifact} />
          <AbsorberCalculators room={request} onResult={recordArtifact} />
          <DiffuserCalculators room={request} onResult={recordArtifact} />
        </TabContainer>

        <IsolationCalculators room={request} onResult={recordArtifact} />

        <TabContainer compact label="Medición y simulación" tabs={[{ key: "measurement-tools", label: "Medición" }, { key: "ism", label: "Fuentes imagen" }]}>
          <MeasurementTools room={request} onResult={recordArtifact} />
          <ImpulseResponseTool room={request} onResult={(result) => { setIrData(result); recordArtifact("measurement_impulse_response", result); }} />
        </TabContainer>

        <NumericalMethods room={request} onResult={recordArtifact} />
      </TabContainer>

      <Card>
        <CardTitle>Exportación profesional <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">PAID</span></CardTitle>
        {!professionalExports ? (
          <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Activa una licencia PAID o RESEARCH con el entitlement <strong>exports</strong>. Los informes incluyen entradas, supuestos, advertencias, procedencia y todos los resultados calculados en esta sesión.</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            <PDFDownloadLink document={<PDFReport report={report} />} fileName="informe-acustico-profesional.pdf" className="rounded-lg bg-gray-800 px-3 py-2 text-center text-sm font-semibold text-white hover:bg-gray-900">{({ loading: pdfLoading }) => pdfLoading ? "Generando PDF…" : "Descargar PDF"}</PDFDownloadLink>
            <button type="button" onClick={() => exportCSV(report)} className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white">CSV completo</button>
            <button type="button" onClick={() => exportJSON(report)} className="rounded-lg bg-amber-700 px-3 py-2 text-sm font-semibold text-white">JSON completo</button>
            <button type="button" onClick={() => exportLatex(report)} className="rounded-lg bg-cyan-800 px-3 py-2 text-sm font-semibold text-white">LaTeX</button>
            <button type="button" onClick={() => exportTypst(report)} className="rounded-lg bg-purple-800 px-3 py-2 text-sm font-semibold text-white">Typst</button>
          </div>
        )}
      </Card>

      <div className="text-center"><Link href="/" className="inline-flex rounded-lg bg-indigo-700 px-5 py-2.5 text-sm font-semibold text-white shadow-md hover:bg-indigo-800">Nuevo análisis</Link></div>
    </div>
  );
}

function ModelContext({ data, request, provenance }: { data: CalculateResponse; request: CalculateRequest; provenance: EngineProvenance }) {
  return (
    <Card>
      <CardTitle>Contexto, supuestos e incertidumbre</CardTitle>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div><dt className="text-xs text-gray-500">Ambiente</dt><dd className="font-semibold">{data.environment.temperature_c.toFixed(1)} °C · {data.environment.relative_humidity.toFixed(0)} % HR</dd></div>
        <div><dt className="text-xs text-gray-500">Presión</dt><dd className="font-semibold">{(data.environment.pressure_pa / 1000).toFixed(1)} kPa</dd></div>
        <div><dt className="text-xs text-gray-500">Velocidad del sonido</dt><dd className="font-semibold">{data.sound_speed_m_s.toFixed(2)} m/s</dd></div>
        <div><dt className="text-xs text-gray-500">Campo difuso modal</dt><dd className="font-semibold">{data.diffuse_field.is_diffuse ? "Indicador favorable" : "No establecido"}</dd></div>
        <div><dt className="text-xs text-gray-500">Área de Bolt</dt><dd className="font-semibold">{data.bolt_area.is_inside ? "Dentro" : `Fuera · distancia ${data.bolt_area.distance.toFixed(3)}`}</dd></div>
        <div><dt className="text-xs text-gray-500">Atenuación de aire</dt><dd className="font-semibold">{request.include_air_attenuation ? "Incluida" : "No incluida"}</dd></div>
        <div className="col-span-2"><dt className="text-xs text-gray-500">Procedencia</dt><dd className="font-semibold">{provenance.label} v{provenance.version}</dd></div>
      </dl>
      <p className="mt-4 text-xs leading-5 text-gray-600">Modelo de sala rectangular con materiales nominales. Las tolerancias geométricas, montaje, mobiliario, ocupación y variación espacial no se resuelven automáticamente; RT60 se presenta a 0,1 s para no sugerir precisión de medición.</p>
      {data.method_warnings.length > 0 && <ul className="mt-3 space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">{data.method_warnings.map((warning, index) => <li key={`${warning.code}-${index}`}><strong>{warning.method || "Modelo"}{warning.band_hz ? ` ${warning.band_hz} Hz` : ""}:</strong> {warning.message}</li>)}</ul>}
    </Card>
  );
}

function ListeningRecommendation({ data }: { data: PressureMapResponse }) {
  const position = data.optimal_listening;
  return (
    <section className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4" aria-label="Recomendación de posición de escucha">
      <h3 className="text-sm font-semibold text-emerald-950">Recomendación de escucha basada en uniformidad espectral</h3>
      <div className="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div><span className="block text-xs text-emerald-800">Posición</span><strong>X {position.x.toFixed(2)} · Y {position.y.toFixed(2)} m</strong></div>
        <div><span className="block text-xs text-emerald-800">Movimiento</span><strong>{position.movement_m.toFixed(2)} m</strong></div>
        <div><span className="block text-xs text-emerald-800">Vector</span><strong>ΔX {position.movement.dx_m.toFixed(2)} · ΔY {position.movement.dy_m.toFixed(2)} m</strong></div>
        <div><span className="block text-xs text-emerald-800">Mejora modelada</span><strong>{position.db_improvement.toFixed(2)} dB</strong></div>
      </div>
      <p className="mt-2 text-xs text-emerald-900">El score es desviación estándar de niveles modales en dB; menor es más uniforme. Confirma la recomendación mediante medición en varias posiciones.</p>
      {position.warnings.map((warning) => <p key={warning} className="mt-1 text-xs font-medium text-amber-900">{warning}</p>)}
    </section>
  );
}
