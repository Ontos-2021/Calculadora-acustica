"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { AlertCircle, CheckCircle2, CircleDot, LockKeyhole, RefreshCw, TriangleAlert } from "lucide-react";
import type { AdvancedArtifacts, CalculateRequest, CalculateResponse, EngineProvenance, IRResponse, PressureMapResponse, ReportBundle } from "@/lib/types";
import { calculateOffline, OFFLINE_ENGINE, pressureMapWithOffline, SERVER_ENGINE } from "@/lib/offline";
import { ApiError, calculate } from "@/lib/api";
import { decodeRequestData } from "@/lib/transport";
import { roomPayload } from "@/lib/room";
import { useLicense } from "@/context/LicenseProvider";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { TabContainer } from "@/components/ui/TabContainer";
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

const TreatmentTools = dynamic(() => import("@/components/results/TreatmentTools").then((module) => module.TreatmentTools));
const AbsorberCalculators = dynamic(() => import("@/components/results/AbsorberCalculators").then((module) => module.AbsorberCalculators));
const DiffuserCalculators = dynamic(() => import("@/components/results/DiffuserCalculators").then((module) => module.DiffuserCalculators));
const IsolationCalculators = dynamic(() => import("@/components/results/IsolationCalculators").then((module) => module.IsolationCalculators));
const MeasurementTools = dynamic(() => import("@/components/results/MeasurementTools").then((module) => module.MeasurementTools));
const NumericalMethods = dynamic(() => import("@/components/results/NumericalMethods").then((module) => module.NumericalMethods));
const ImpulseResponseTool = dynamic(() => import("@/components/results/ImpulseResponseTool").then((module) => module.ImpulseResponseTool));
const ProfessionalExport = dynamic(() => import("@/components/export/ProfessionalExport").then((module) => module.ProfessionalExport));

const calculationCache = new Map<string, CalculateResponse>();

export default function ResultsContent({ requestOverride, activeSection, onSectionChange }: {
  requestOverride?: CalculateRequest | null;
  activeSection?: string;
  onSectionChange?: (section: string) => void;
} = {}) {
  const searchParams = useSearchParams();
  const encodedRequest = searchParams.get("data");
  const { status, hasEntitlement, apiKey } = useLicense();
  const [data, setData] = useState<CalculateResponse | null>(null);
  const [request, setRequest] = useState<CalculateRequest | null>(requestOverride || null);
  const [provenance, setProvenance] = useState<EngineProvenance>(OFFLINE_ENGINE);
  const [fallbackReason, setFallbackReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [internalSection, setInternalSection] = useState("summary");
  const section = activeSection ?? internalSection;
  const setSection = (value: string) => { if (activeSection === undefined) setInternalSection(value); onSectionChange?.(value); };
  const [pressureData, setPressureData] = useState<PressureMapResponse | null>(null);
  const [pressureLoading, setPressureLoading] = useState(false);
  const [pressureError, setPressureError] = useState<string | null>(null);
  const [pressureRefresh, setPressureRefresh] = useState(0);
  const [selectedMode, setSelectedMode] = useState("all");
  const [maxFreq, setMaxFreq] = useState(300);
  const [irData, setIrData] = useState<IRResponse | null>(null);
  const [advanced, setAdvanced] = useState<AdvancedArtifacts>({});

  useEffect(() => {
    let next = requestOverride || null;
    if (!next && encodedRequest) { try { next = decodeRequestData(encodedRequest); } catch (cause) { setError(cause instanceof Error ? cause.message : "Datos de cálculo no válidos."); } }
    setRequest(next);
  }, [encodedRequest, requestOverride]);

  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const key = JSON.stringify(request);
    async function load() {
      setLoading(!calculationCache.has(key)); setError(null); setFallbackReason(null);
      const cached = calculationCache.get(key);
      let localAvailable = Boolean(cached);
      if (cached) setData(cached);
      try {
        const local = await calculateOffline(request!);
        localAvailable = true;
        if (!controller.signal.aborted) { setData(local); setProvenance(OFFLINE_ENGINE); setLoading(false); }
      } catch { /* Full licensed materials may only exist on the server. */ }
      const timer = window.setTimeout(async () => {
        setSyncing(true);
        try {
          const server = await calculate(request!, apiKey, controller.signal);
          if (!controller.signal.aborted) { calculationCache.set(key, server); setData(server); setProvenance(SERVER_ENGINE); }
        } catch (cause) {
          if (controller.signal.aborted) return;
          if (cause instanceof ApiError && !cause.isNetworkFailure) {
            setData(null);
            setError(cause.message);
          } else if (!localAvailable) setError(cause instanceof Error ? cause.message : "No se pudo completar el análisis.");
          else setFallbackReason(cause instanceof Error ? cause.message : "Servidor no disponible");
        } finally { if (!controller.signal.aborted) { setLoading(false); setSyncing(false); } }
      }, 350);
      return timer;
    }
    let timer = 0;
    void load().then((value) => { timer = value || 0; });
    return () => { controller.abort(); if (timer) window.clearTimeout(timer); };
  // data is intentionally excluded: only the request controls this pipeline.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request, refresh, apiKey]);

  useEffect(() => {
    if (!request || section !== "pressure") return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setPressureLoading(true); setPressureError(null);
      try {
        const indices = selectedMode === "all" ? undefined : selectedMode.split(",").map(Number) as [number, number, number];
        const outcome = await pressureMapWithOffline({ ...roomPayload(request), ear_height: Math.min(1.2, request.alto), max_freq: maxFreq, grid_size: window.innerWidth < 768 ? 48 : 64, ...(indices ? { mode_indices: indices } : {}) }, apiKey, controller.signal);
        if (!controller.signal.aborted) setPressureData(outcome.data);
      } catch (cause) { if (!controller.signal.aborted) setPressureError(cause instanceof Error ? cause.message : "No se pudo actualizar el mapa de presión."); }
      finally { if (!controller.signal.aborted) setPressureLoading(false); }
    }, 220);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [request, section, selectedMode, maxFreq, pressureRefresh, apiKey]);

  if (loading && !data) return <Card aria-busy="true"><CardTitle>Preparando análisis</CardTitle><LoadingSkeleton rows={8} /></Card>;
  if (error || !data || !request) return <Card><Alert variant="danger" role="alert">{error || "No hay resultados disponibles."}</Alert><Button className="mt-4" variant="secondary" onClick={() => setRefresh((value) => value + 1)}><RefreshCw className="size-4" />Reintentar</Button></Card>;

  const selectedFrequency = selectedMode === "all" ? null : data.modos.find((mode) => mode.indices.join(",") === selectedMode)?.frecuencia ?? null;
  const recordArtifact = (name: string, result: unknown) => setAdvanced((current) => ({ ...current, [name]: result }));
  const report: ReportBundle = {
    schema_version: "acoustic-report/2.0", generated_at: new Date().toISOString(), input: request, results: data, pressure: pressureData,
    impulse_response: irData, advanced,
    treatment: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("treatment_") || key.startsWith("absorber_") || key.startsWith("diffuser_"))),
    isolation: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("isolation_"))),
    measurement: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("measurement_"))),
    numerical: Object.fromEntries(Object.entries(advanced).filter(([key]) => key.startsWith("numerical_"))),
    provenance, assumptions: [...provenance.assumptions, "Materiales y montaje se representan mediante condiciones nominales."], certification: "engineering_estimate_not_measurement_or_certification",
  };
  const professionalExports = status?.tier !== "FREE" && hasEntitlement("exports");

  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700 dark:text-teal-400">Análisis activo</p><h2 className="mt-1 text-2xl font-bold tracking-tight">{request.largo} × {request.ancho} × {request.alto} m</h2></div>
      <div className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${syncing ? "border-sky-200 bg-sky-50 text-sky-800" : provenance.offline ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-900"}`} role="status" aria-live="polite" data-testid="engine-source">{syncing ? "Estimación local · sincronizando" : provenance.offline ? "Estimación local" : "Verificado por servidor"}</div>
    </div>
    {fallbackReason && <Alert variant="warning">Se conserva el resultado local. {fallbackReason}</Alert>}

    <TabContainer activeTab={section} onTabChange={setSection} tabs={[
      { key: "summary", label: "Resumen" }, { key: "modes", label: "Modos", badge: String(data.cantidad_modos) },
      { key: "rt60", label: "RT60" }, { key: "pressure", label: "Presión" }, { key: "treatment", label: "Tratamiento" },
      { key: "isolation", label: "Aislamiento" }, { key: "measurement", label: "Medición" }, { key: "advanced", label: "Avanzado" },
    ]}>
      <section className="space-y-5" aria-label="Resumen del diagnóstico"><SummaryCards data={data} /><DiagnosticSummary data={data} onNavigate={setSection} /><ModelContext data={data} request={request} provenance={provenance} /></section>
      <section className="space-y-5"><Card><CardTitle>Modos de resonancia <span className="text-sm font-normal text-muted">· {data.cantidad_modos} modos</span></CardTitle><ModeTable modos={data.modos} selectedFreq={selectedFrequency} onSelectMode={(mode) => { setSelectedMode(mode.indices.join(",")); setSection("pressure"); }} /></Card><div className="grid gap-5 xl:grid-cols-2"><Card><BonelloVerdict bonello={data.bonello} /><BonelloChart bandas={data.bonello.bandas} /></Card><Card><ProportionsCard proporciones={data.proporciones} /></Card></div></section>
      <section className="space-y-5">{data.degeneracion_dimensiones.length > 0 && <DimensionWarnings warnings={data.degeneracion_dimensiones} />}<Card><CardTitle>Tiempo de reverberación por banda</CardTitle><div className="grid gap-6 xl:grid-cols-2"><div><h3 className="mb-2 text-sm font-semibold">Comparación de métodos</h3><RT60Chart data={data.rt60_bandas} /></div>{data.objetivo ? <div><h3 className="mb-2 text-sm font-semibold">Actual frente a objetivo</h3><ComparisonChart data={data.rt60_bandas} objetivo={data.objetivo} /></div> : <Alert>Selecciona un uso en el panel de sala para añadir un objetivo.</Alert>}</div><div className="mt-5"><RT60Table bandas={data.rt60_bandas} objetivo={data.objetivo} /></div></Card></section>
      <section>{pressureData ? <Card aria-busy={pressureLoading}><CardTitle>Mapa de presión modal</CardTitle>{pressureLoading && <Alert className="mb-3">Actualizando datos; se conserva el mapa anterior.</Alert>}{pressureError && <Alert variant="danger" className="mb-3">{pressureError}</Alert>}<PressureMapChart data={pressureData} modes={data.modos} selectedMode={selectedMode} onSelectMode={setSelectedMode} onMaxFreqChange={setMaxFreq} maxFreq={maxFreq} loading={pressureLoading} /><ListeningRecommendation data={pressureData} /></Card> : <Card><p className="text-sm text-muted">{pressureLoading ? "Calculando mapa de presión…" : pressureError || "Preparando mapa…"}</p>{pressureError && <Button className="mt-3" onClick={() => setPressureRefresh((value) => value + 1)}>Reintentar</Button>}</Card>}</section>
      <section className="space-y-5"><SectionIntro title="Diseño de tratamiento" description="Convierte los déficits por banda en decisiones de material, superficie y geometría." locked={!hasEntitlement("inverse_design")} /><TreatmentTools room={request} analysis={data} onResult={recordArtifact} /><AbsorberCalculators room={request} onResult={recordArtifact} /><DiffuserCalculators room={request} onResult={recordArtifact} /></section>
      <section className="space-y-5"><SectionIntro title="Aislamiento y ruido" description="Evalúa cerramientos, clasificaciones STC/Rw, curvas NC/NR y vías de transmisión." locked={!hasEntitlement("isolation")} /><IsolationCalculators room={request} onResult={recordArtifact} /></section>
      <section className="space-y-5"><SectionIntro title="Medición y respuesta" description="Genera señales ESS, importa WAV y contrasta el modelo con una respuesta medida." locked={!hasEntitlement("measurement")} /><MeasurementTools room={request} onResult={recordArtifact} /><ImpulseResponseTool room={request} onResult={(result) => { setIrData(result); recordArtifact("measurement_impulse_response", result); }} /></section>
      <section className="space-y-5"><SectionIntro title="Métodos numéricos" description="Modelos de impedancia, FEM, trazado de rayos e hibridación para investigación." locked={!hasEntitlement("numerical")} /><NumericalMethods room={request} onResult={recordArtifact} /><ProfessionalExport report={report} enabled={Boolean(professionalExports)} /></section>
    </TabContainer>
  </div>;
}

function DiagnosticSummary({ data, onNavigate }: { data: CalculateResponse; onNavigate: (section: string) => void }) {
  const ratio = data.objetivo ? data.rt60_promedio / (Object.values(data.objetivo.valores).reduce((a, b) => a + b, 0) / Object.values(data.objetivo.valores).length) : null;
  const items = [
    { ok: ratio === null ? null : ratio <= 1.25, title: "Reverberación", value: ratio ? `${ratio.toFixed(1)}× respecto al objetivo` : "Sin objetivo seleccionado", section: "rt60" },
    { ok: data.bonello.cumple, title: "Distribución modal", value: data.bonello.cumple ? "Cumple el criterio de Bonello" : `${data.bonello.violaciones.length} bandas en violación`, section: "modes" },
    { ok: data.bolt_area.is_inside, title: "Proporciones", value: data.bolt_area.is_inside ? "Dentro del área de Bolt" : `Fuera · distancia ${data.bolt_area.distance.toFixed(3)}`, section: "modes" },
    { ok: data.diffuse_field.is_diffuse, title: "Campo difuso", value: data.diffuse_field.is_diffuse ? `Indicador favorable desde ${data.f_schroeder.toFixed(0)} Hz` : "Solapamiento modal insuficiente", section: "modes" },
  ];
  return <Card><CardTitle>Diagnóstico accionable</CardTitle><div className="grid gap-3 md:grid-cols-2">{items.map((item) => <button key={item.title} type="button" onClick={() => onNavigate(item.section)} className="flex items-start gap-3 rounded-lg border bg-surface-muted p-4 text-left transition hover:border-teal-400 hover:bg-accent-soft">{item.ok === true ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" /> : item.ok === false ? <AlertCircle className="mt-0.5 size-5 shrink-0 text-rose-600" /> : <CircleDot className="mt-0.5 size-5 shrink-0 text-sky-600" />}<span><strong className="block text-sm">{item.title}</strong><span className="mt-1 block text-xs leading-5 text-muted">{item.value}</span><span className="mt-2 block text-xs font-semibold text-teal-700 dark:text-teal-400">Ver detalle →</span></span></button>)}</div></Card>;
}

function SectionIntro({ title, description, locked }: { title: string; description: string; locked: boolean }) {
  return <div className="rounded-xl border bg-surface p-5"><div className="flex items-start gap-3">{locked ? <LockKeyhole className="mt-0.5 size-5 text-amber-600" /> : <CheckCircle2 className="mt-0.5 size-5 text-teal-600" />}<div><h3 className="font-semibold">{title}</h3><p className="mt-1 text-sm text-muted">{description}</p>{locked && <p className="mt-2 text-xs font-semibold text-amber-700 dark:text-amber-400">Vista previa disponible · activa una licencia para calcular con tu sala.</p>}</div></div></div>;
}

function ModelContext({ data, request, provenance }: { data: CalculateResponse; request: CalculateRequest; provenance: EngineProvenance }) {
  return <Card><details><summary className="cursor-pointer text-sm font-semibold">Supuestos, incertidumbre y procedencia</summary><dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><div><dt className="text-xs text-muted">Ambiente</dt><dd className="font-semibold">{data.environment.temperature_c.toFixed(1)} °C · {data.environment.relative_humidity.toFixed(0)} % HR</dd></div><div><dt className="text-xs text-muted">Velocidad</dt><dd className="font-semibold">{data.sound_speed_m_s.toFixed(2)} m/s</dd></div><div><dt className="text-xs text-muted">Área de Bolt</dt><dd className="font-semibold">{data.bolt_area.is_inside ? "Dentro" : "Fuera"}</dd></div><div><dt className="text-xs text-muted">Aire</dt><dd className="font-semibold">{request.include_air_attenuation ? "Incluido" : "No incluido"}</dd></div></dl><p className="mt-4 text-xs leading-5 text-muted">{provenance.label} v{provenance.version}. Estimación de ingeniería para sala rectangular; valida las decisiones finales mediante medición.</p>{data.method_warnings.length > 0 && <Alert variant="warning" className="mt-3"><TriangleAlert className="mr-2 inline size-4" />{data.method_warnings.length} avisos de aplicabilidad del método.</Alert>}</details></Card>;
}

function ListeningRecommendation({ data }: { data: PressureMapResponse }) {
  const position = data.optimal_listening;
  return <section className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100" aria-label="Recomendación de posición de escucha"><h3 className="text-sm font-semibold">Posición de escucha más uniforme</h3><div className="mt-2 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><div><span className="block text-xs opacity-75">Posición</span><strong>X {position.x.toFixed(2)} · Y {position.y.toFixed(2)} m</strong></div><div><span className="block text-xs opacity-75">Movimiento</span><strong>{position.movement_m.toFixed(2)} m</strong></div><div><span className="block text-xs opacity-75">Vector</span><strong>ΔX {position.movement.dx_m.toFixed(2)} · ΔY {position.movement.dy_m.toFixed(2)}</strong></div><div><span className="block text-xs opacity-75">Mejora modelada</span><strong>{position.db_improvement.toFixed(2)} dB</strong></div></div></section>;
}
