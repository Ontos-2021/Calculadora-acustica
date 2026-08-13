"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { CalculateRequest, MaterialInfo, SurfaceInput } from "@/lib/types";
import { fetchMaterialCategories, fetchMaterials } from "@/lib/api";
import { offlineDefaultMaterials, offlineMaterialCategories } from "@/lib/offline";
import { encodeRequestData } from "@/lib/transport";
import { useLicense } from "@/context/LicenseProvider";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";

const BANDS = ["125", "250", "500", "1000", "2000", "4000"];
const SURFACES = ["Frente", "Contrafrente", "Lat. Izquierdo", "Lat. Derecho", "Piso", "Techo"];
const USES: Record<string, string> = {
  home_studio: "Home Studio / Grabación", sala_conferencias: "Sala de conferencias", aula: "Aula",
  teatro: "Teatro", sala_conciertos: "Sala de conciertos", iglesia: "Iglesia / Culto",
  home_theater: "Home Theater", restaurante: "Restaurante",
};

export const ROOM_PRESETS: Array<{ name: string; description: string; request: CalculateRequest }> = [
  { name: "Home studio", description: "4,2 × 3,4 × 2,6 m", request: roomPreset(4.2, 3.4, 2.6, "home_studio", ["Panel acústico", "Madera", "Yeso", "Yeso", "Alfombra gruesa", "Panel acústico"]) },
  { name: "Aula", description: "9 × 7 × 3,2 m", request: roomPreset(9, 7, 3.2, "aula", ["Yeso", "Yeso", "Yeso", "Vidrio", "Alfombra gruesa", "Panel acústico"]) },
  { name: "Sala de conferencias", description: "12 × 8 × 3,5 m", request: roomPreset(12, 8, 3.5, "sala_conferencias", ["Madera", "Panel acústico", "Yeso", "Yeso", "Alfombra gruesa", "Panel acústico"]) },
];

function roomPreset(largo: number, ancho: number, alto: number, uso: string, materials: string[]): CalculateRequest {
  return { largo, ancho, alto, uso, superficies: materials.map((material) => ({ material })), environment: { temperature_c: 20, relative_humidity: 50, pressure_pa: 101325 }, include_air_attenuation: false };
}

interface FormState {
  largo: string; ancho: string; alto: string; uso: string; materials: string[];
  alphas: Record<string, Record<string, string>>; temperature: string; humidity: string; pressure: string; includeAir: boolean;
}

function toForm(request?: CalculateRequest | null): FormState {
  return {
    largo: request ? String(request.largo) : "", ancho: request ? String(request.ancho) : "", alto: request ? String(request.alto) : "",
    uso: request?.uso || "", materials: request?.superficies.map((surface) => surface.material) || Array(6).fill("Concreto"),
    alphas: Object.fromEntries((request?.superficies || []).map((surface, index) => [`sup_${index}`, Object.fromEntries(Object.entries(surface.alphas || {}).map(([band, value]) => [band, String(value)]))])),
    temperature: String(request?.environment.temperature_c ?? 20), humidity: String(request?.environment.relative_humidity ?? 50),
    pressure: String(request?.environment.pressure_pa ?? 101325), includeAir: request?.include_air_attenuation ?? false,
  };
}

function requestFromForm(form: FormState): CalculateRequest | null {
  const largo = Number(form.largo), ancho = Number(form.ancho), alto = Number(form.alto);
  const temperature = Number(form.temperature), humidity = Number(form.humidity), pressure = Number(form.pressure);
  if (![largo, ancho, alto].every((value) => Number.isFinite(value) && value > 0)) return null;
  if (!Number.isFinite(temperature) || temperature <= -273.15 || temperature > 100 || !Number.isFinite(humidity) || humidity < 0 || humidity > 100 || !Number.isFinite(pressure) || pressure <= 0) return null;
  const superficies: SurfaceInput[] = form.materials.map((material, index) => {
    const alpha = form.alphas[`sup_${index}`] || {};
    const parsed = Object.fromEntries(BANDS.flatMap((band) => {
      const value = Number(alpha[band]);
      return alpha[band] !== undefined && Number.isFinite(value) && value >= 0 && value <= 1 ? [[band, value]] : [];
    }));
    return { material, ...(Object.keys(parsed).length ? { alphas: parsed } : {}) };
  });
  return { largo, ancho, alto, superficies, environment: { temperature_c: temperature, relative_humidity: humidity, pressure_pa: pressure }, include_air_attenuation: form.includeAir, ...(form.uso ? { uso: form.uso } : {}) };
}

export function RoomForm({ initialRequest, onCalculate, progressive = false }: {
  initialRequest?: CalculateRequest | null;
  onCalculate?: (request: CalculateRequest) => void;
  progressive?: boolean;
} = {}) {
  const router = useRouter();
  const { apiKey, status } = useLicense();
  const hasFullCatalog = Boolean(apiKey && status?.entitlements.includes("materials"));
  const [form, setForm] = useState(() => toForm(initialRequest));
  const [error, setError] = useState<string | null>(null);
  const [materials, setMaterials] = useState<MaterialInfo[]>([]);
  const [categories, setCategories] = useState<Record<string, string[]>>({});
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [materialsError, setMaterialsError] = useState<string | null>(null);
  const [retryCatalog, setRetryCatalog] = useState(0);
  const [filter, setFilter] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [showAlpha, setShowAlpha] = useState<Record<number, boolean>>({});

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setMaterialsLoading(true); setMaterialsError(null);
      try {
        const catalogKey = hasFullCatalog ? apiKey : null;
        const [items, groups] = await Promise.all([fetchMaterials(catalogKey), fetchMaterialCategories(catalogKey)]);
        if (!controller.signal.aborted) { setMaterials(items); setCategories(groups); }
      } catch (cause) {
        if (!controller.signal.aborted) {
          setMaterials(offlineDefaultMaterials()); setCategories(offlineMaterialCategories());
          setMaterialsError(`${cause instanceof Error ? cause.message : "No se pudo cargar el catálogo."} Se usan los materiales FREE incluidos en la aplicación.`);
        }
      } finally { if (!controller.signal.aborted) setMaterialsLoading(false); }
    }
    void load(); return () => controller.abort();
  }, [apiKey, hasFullCatalog, retryCatalog]);

  const updateMaterial = useCallback((index: number, material: string) => setForm((current) => {
    const next = [...current.materials]; next[index] = material; return { ...current, materials: next };
  }), []);
  const grouped = materials.filter((material) => (!filter || material.nombre.toLowerCase().includes(filter.toLowerCase())) && (!selectedCategory || material.categoria === selectedCategory))
    .reduce<Record<string, MaterialInfo[]>>((groups, material) => { (groups[material.categoria] ||= []).push(material); return groups; }, {});
  const dimensionsValid = Boolean(requestFromForm({ ...form, temperature: "20", humidity: "50", pressure: "101325" }));
  const hasPendingChanges = Boolean(initialRequest && JSON.stringify(form) !== JSON.stringify(toForm(initialRequest)));

  function submit(event: FormEvent) {
    event.preventDefault(); setError(null);
    const request = requestFromForm(form);
    if (!request) { setError("Las dimensiones deben ser números positivos. Revisa también temperatura, humedad y presión."); return; }
    if (onCalculate) onCalculate(request);
    else router.push(`/results?data=${encodeRequestData(request)}`);
  }

  return (
    <form onSubmit={submit} className="space-y-6" data-testid="room-editor">
      {error && <Alert variant="danger" role="alert" aria-live="assertive">{error}</Alert>}
      <fieldset>
        <legend className="mb-3 text-xs font-bold uppercase tracking-[0.12em] text-zinc-500">1 · Dimensiones</legend>
        <div className="grid grid-cols-3 gap-2">
          {(["largo", "ancho", "alto"] as const).map((dimension) => (
            <Field key={dimension} htmlFor={`dim-${dimension}`} label={`${dimension[0].toUpperCase()}${dimension.slice(1)} (m)`}>
              <Input id={`dim-${dimension}`} type="number" inputMode="decimal" step="0.01" min="0.01" required placeholder={dimension === "largo" ? "8,5" : dimension === "ancho" ? "6,0" : "3,0"} value={form[dimension]} onChange={(event) => setForm((current) => ({ ...current, [dimension]: event.target.value }))} />
            </Field>
          ))}
        </div>
      </fieldset>

      {(!progressive || dimensionsValid) && <>
        <details className="group" open={!progressive || dimensionsValid}>
          <summary className="cursor-pointer list-none text-xs font-bold uppercase tracking-[0.12em] text-zinc-500">2 · Ambiente <span className="float-right text-teal-700 group-open:rotate-180">⌄</span></summary>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <Field htmlFor="env-temperature" label="Temperatura °C"><Input id="env-temperature" type="number" min="-50" max="100" step="0.1" value={form.temperature} onChange={(event) => setForm((current) => ({ ...current, temperature: event.target.value }))} /></Field>
            <Field htmlFor="env-humidity" label="Humedad %"><Input id="env-humidity" type="number" min="0" max="100" value={form.humidity} onChange={(event) => setForm((current) => ({ ...current, humidity: event.target.value }))} /></Field>
            <Field htmlFor="env-pressure" label="Presión Pa"><Input id="env-pressure" type="number" min="10000" max="2000000" value={form.pressure} onChange={(event) => setForm((current) => ({ ...current, pressure: event.target.value }))} /></Field>
          </div>
          <label className="mt-3 flex gap-2 text-xs text-zinc-600 dark:text-zinc-400"><input type="checkbox" checked={form.includeAir} onChange={(event) => setForm((current) => ({ ...current, includeAir: event.target.checked }))} /> Incluir atenuación del aire en RT60</label>
        </details>

        <section>
          <h3 className="text-xs font-bold uppercase tracking-[0.12em] text-zinc-500">3 · Materiales</h3>
          <div className="mt-2 flex items-center justify-between gap-2 text-xs text-zinc-500"><span>{hasFullCatalog ? "Catálogo completo de la licencia" : "Catálogo FREE anónimo"}</span>{materialsError && <button type="button" className="font-semibold text-teal-700" onClick={() => setRetryCatalog((value) => value + 1)}>Reintentar catálogo</button>}</div>
          {materialsError && <Alert variant="warning" className="mt-2 text-xs" role="status">{materialsError}</Alert>}
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Input id="mat-filter" type="search" placeholder="Filtrar materiales…" value={filter} onChange={(event) => setFilter(event.target.value)} className="text-xs" />
            <Select id="mat-categoria" aria-label="Filtrar materiales por categoría" value={selectedCategory} onChange={(event) => setSelectedCategory(event.target.value)} className="text-xs"><option value="">Todas las categorías</option>{Object.keys(categories).map((category) => <option key={category}>{category}</option>)}</Select>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {SURFACES.map((surface, index) => {
              const slug = surface.toLowerCase().replace(/[\s.]+/g, "-");
              return <div key={surface} className="rounded-lg border bg-surface-muted p-2.5">
                <label htmlFor={`mat-${slug}`} className="mb-1 block text-xs font-semibold">{surface}</label>
                <Select id={`mat-${slug}`} value={form.materials[index]} onChange={(event) => updateMaterial(index, event.target.value)} className="min-h-9 text-xs">
                  {materialsLoading && !materials.length ? <option>Cargando...</option> : Object.entries(grouped).map(([category, items]) => <optgroup key={category} label={category}>{items.map((material) => <option key={material.nombre} value={material.nombre}>{material.nombre}{material.iso_class && material.iso_class !== "No clasificado" ? ` [${material.iso_class}]` : ""}</option>)}</optgroup>)}
                </Select>
                <button type="button" className="mt-1.5 text-xs font-semibold text-teal-700 dark:text-teal-400" onClick={() => setShowAlpha((current) => ({ ...current, [index]: !current[index] }))}>{showAlpha[index] ? "Ocultar α" : "α personalizado"}</button>
                {showAlpha[index] && <div className="mt-2 grid grid-cols-3 gap-1">{BANDS.map((band) => <Field key={band} htmlFor={`alpha-${slug}-${band}`} label={`${band} Hz`}><Input id={`alpha-${slug}-${band}`} type="number" step="0.01" min="0" max="1" placeholder="α" className="min-h-8 px-2 text-xs" value={form.alphas[`sup_${index}`]?.[band] ?? ""} onChange={(event) => setForm((current) => ({ ...current, alphas: { ...current.alphas, [`sup_${index}`]: { ...current.alphas[`sup_${index}`], [band]: event.target.value } } }))} /></Field>)}</div>}
              </div>;
            })}
          </div>
        </section>

        <Field htmlFor="sala-uso" label="4 · Uso de la sala" hint="Añade un objetivo normativo al diagnóstico de RT60.">
          <Select id="sala-uso" aria-label="Uso de la sala" value={form.uso} onChange={(event) => setForm((current) => ({ ...current, uso: event.target.value }))}><option value="">Sin comparación objetivo</option>{Object.entries(USES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>
        </Field>
      </>}
      {hasPendingChanges && <p className="text-center text-xs font-medium text-amber-700 dark:text-amber-400" role="status">Cambios sin aplicar</p>}
      <Button type="submit" className="w-full" disabled={materialsLoading}>{initialRequest ? "Actualizar análisis" : "Calcular"}</Button>
    </form>
  );
}
