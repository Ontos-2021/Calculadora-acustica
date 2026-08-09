import { ApiError, calculate, fetchPressureMap } from "./api";
import type {
  CalculateRequest,
  CalculateResponse,
  EngineProvenance,
  EnvironmentInput,
  EnvironmentResult,
  MaterialInfo,
  Mode,
  ObjetivoInfo,
  PressureMapRequest,
  PressureMapResponse,
} from "./types";
import { OCTAVE_BANDS } from "./types";

export const OFFLINE_ENGINE: EngineProvenance = {
  id: "offline-typescript-free",
  label: "Motor FREE TypeScript determinista",
  version: "1.0.0",
  offline: true,
  assumptions: [
    "Sala rectangular con límites rígidos y campo modal analítico.",
    "RT60 estimado con Sabine, Eyring, Millington-Sette y FitzRoy; no sustituye una medición ISO 3382.",
    "Coeficientes de absorción genéricos con incertidumbre de cribado; no son datos certificados de producto.",
    "El mapa acumulado suma energía modal sin asumir fase relativa entre modos.",
  ],
};

export const SERVER_ENGINE: EngineProvenance = {
  id: "server-acoustic-core",
  label: "acoustic_core del servidor",
  version: "0.1",
  offline: false,
  assumptions: [
    "Modelo de ingeniería para sala rectangular.",
    "Los resultados deben validarse con mediciones y criterios del proyecto.",
  ],
};

const MATERIAL_DATA: Record<string, { categoria: string; alphas: Record<string, number> }> = {
  Concreto: {
    categoria: "Mampostería",
    alphas: { "125": 0.01, "250": 0.02, "500": 0.04, "1000": 0.06, "2000": 0.08, "4000": 0.1 },
  },
  Madera: {
    categoria: "Madera",
    alphas: { "125": 0.05, "250": 0.05, "500": 0.07, "1000": 0.06, "2000": 0.06, "4000": 0.07 },
  },
  Yeso: {
    categoria: "Techos",
    alphas: { "125": 0.04, "250": 0.04, "500": 0.05, "1000": 0.06, "2000": 0.08, "4000": 0.08 },
  },
  Vidrio: {
    categoria: "Vidrio",
    alphas: { "125": 0.03, "250": 0.03, "500": 0.05, "1000": 0.08, "2000": 0.1, "4000": 0.1 },
  },
  "Alfombra gruesa": {
    categoria: "Pisos",
    alphas: { "125": 0.08, "250": 0.24, "500": 0.57, "1000": 0.69, "2000": 0.71, "4000": 0.73 },
  },
  "Cortina pesada": {
    categoria: "Telas y cortinas",
    alphas: { "125": 0.1, "250": 0.3, "500": 0.5, "1000": 0.65, "2000": 0.7, "4000": 0.7 },
  },
  "Panel acústico": {
    categoria: "Paneles acústicos",
    alphas: { "125": 0.2, "250": 0.6, "500": 0.85, "1000": 0.9, "2000": 0.85, "4000": 0.8 },
  },
  "Espuma acústica": {
    categoria: "Espumas",
    alphas: { "125": 0.15, "250": 0.35, "500": 0.65, "1000": 0.8, "2000": 0.8, "4000": 0.75 },
  },
};

const TARGETS: Record<string, ObjetivoInfo> = {
  home_studio: { label: "Home Studio / Grabación", valores: flatTarget(0.3) },
  sala_conferencias: { label: "Sala de conferencias", valores: flatTarget(0.7) },
  aula: { label: "Aula", valores: { "125": 0.75, "250": 0.75, "500": 0.8, "1000": 0.8, "2000": 0.8, "4000": 0.75 } },
  teatro: { label: "Teatro", valores: { "125": 1, "250": 1, "500": 1, "1000": 1, "2000": 1, "4000": 0.9 } },
  sala_conciertos: { label: "Sala de conciertos", valores: { "125": 1.8, "250": 1.8, "500": 1.8, "1000": 1.8, "2000": 1.6, "4000": 1.4 } },
  iglesia: { label: "Iglesia / Culto", valores: { "125": 2.2, "250": 2.2, "500": 2.2, "1000": 2.2, "2000": 2, "4000": 1.8 } },
  home_theater: { label: "Home Theater", valores: flatTarget(0.4) },
  restaurante: { label: "Restaurante", valores: { "125": 0.5, "250": 0.5, "500": 0.6, "1000": 0.6, "2000": 0.6, "4000": 0.5 } },
};

const RATIOS: Record<string, [number, number, number]> = {
  "Golden Ratio": [1, 1.25, 1.6],
  "Louden (1971)": [1, 1.14, 1.39],
  Sepmeyer: [1, 1.19, 1.46],
  Bonello: [1, 1.28, 1.54],
  Volkmann: [1, 1.26, 1.59],
};

function flatTarget(value: number): Record<string, number> {
  return Object.fromEntries(OCTAVE_BANDS.map((band) => [band, value]));
}

function round(value: number, digits = 4): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function classifyMaterial(alphas: Record<string, number>): { alphaW: number; isoClass: string } {
  const alphaW = Math.min(1, Math.round(
    OCTAVE_BANDS.slice(1).reduce((sum, band) => sum + alphas[band], 0) / 5 / 0.05,
  ) * 0.05);
  const isoClass = alphaW >= 0.9 ? "A" : alphaW >= 0.8 ? "B" : alphaW >= 0.6 ? "C" : alphaW >= 0.3 ? "D" : alphaW >= 0.15 ? "E" : "No clasificado";
  return { alphaW, isoClass };
}

export function offlineDefaultMaterials(): MaterialInfo[] {
  return Object.entries(MATERIAL_DATA).map(([nombre, material]) => {
    const classification = classifyMaterial(material.alphas);
    return {
      nombre,
      categoria: material.categoria,
      alphas: { ...material.alphas },
      alpha_w: classification.alphaW,
      iso_class: classification.isoClass,
      provenance: "Bundled FREE generic material table; engineering estimate, not product certification.",
    };
  });
}

export function offlineMaterialCategories(): Record<string, string[]> {
  return offlineDefaultMaterials().reduce<Record<string, string[]>>((categories, material) => {
    (categories[material.categoria] ||= []).push(material.nombre);
    return categories;
  }, {});
}

export function offlineDesignTargets(): Record<string, ObjetivoInfo> {
  return structuredClone(TARGETS);
}

function environmentResult(input: EnvironmentInput): EnvironmentResult {
  const kelvinRatio = (input.temperature_c + 273.15) / 293.15;
  const humidityCorrection = 1 + 0.00016 * (input.relative_humidity - 50);
  const pressureCorrection = Math.sqrt(101325 / input.pressure_pa);
  return {
    ...input,
    sound_speed_m_s: round(343.2 * Math.sqrt(kelvinRatio) * humidityCorrection * pressureCorrection, 5),
  };
}

function materialAlphas(material: string, overrides?: Record<string, number>): Record<string, number> {
  const preset = MATERIAL_DATA[material]?.alphas;
  if (!preset && (!overrides || OCTAVE_BANDS.some((band) => overrides[band] === undefined))) {
    throw new Error(`El material '${material}' no está disponible offline; define sus seis coeficientes α.`);
  }
  return Object.fromEntries(OCTAVE_BANDS.map((band) => [band, overrides?.[band] ?? preset?.[band] ?? 0]));
}

function calculateModes(request: CalculateRequest | PressureMapRequest, c: number, maxFrequency = 300): Mode[] {
  const limits = [request.largo, request.ancho, request.alto].map((dimension) =>
    Math.min(80, Math.ceil((2 * maxFrequency * dimension) / c)),
  );
  const modes: Mode[] = [];
  for (let nx = 0; nx <= limits[0]; nx += 1) {
    for (let ny = 0; ny <= limits[1]; ny += 1) {
      for (let nz = 0; nz <= limits[2]; nz += 1) {
        if (nx === 0 && ny === 0 && nz === 0) continue;
        const frequency = (c / 2) * Math.sqrt(
          (nx / request.largo) ** 2 + (ny / request.ancho) ** 2 + (nz / request.alto) ** 2,
        );
        if (frequency > maxFrequency) continue;
        const nonZero = Number(nx > 0) + Number(ny > 0) + Number(nz > 0);
        modes.push({
          indices: [nx, ny, nz],
          frecuencia: frequency,
          tipo: nonZero === 1 ? "axial" : nonZero === 2 ? "tangencial" : "oblicuo",
          peso_db: nonZero === 1 ? 0 : nonZero === 2 ? -3 : -6,
          degenerado: false,
          solapado: false,
          multiplicity: 1,
          overlap_multiplicity: 1,
        });
      }
    }
  }
  modes.sort((left, right) => left.frecuencia - right.frecuencia);
  return modes;
}

function markModeClusters(modes: Mode[], bandwidth: number): void {
  let degeneracyCluster = 0;
  for (let start = 0; start < modes.length; start += 1) {
    let end = start + 1;
    while (end < modes.length && Math.abs(modes[end].frecuencia - modes[start].frecuencia) <= 0.01) end += 1;
    if (end - start > 1) {
      degeneracyCluster += 1;
      for (let index = start; index < end; index += 1) {
        modes[index].degenerado = true;
        modes[index].multiplicity = end - start;
        modes[index].degeneracy_cluster = degeneracyCluster;
      }
    }
    start = end - 1;
  }

  let overlapCluster = 0;
  for (let start = 0; start < modes.length; start += 1) {
    let end = start + 1;
    while (end < modes.length && modes[end].frecuencia - modes[end - 1].frecuencia <= bandwidth) end += 1;
    if (end - start > 1) {
      overlapCluster += 1;
      for (let index = start; index < end; index += 1) {
        modes[index].solapado = true;
        modes[index].overlap_multiplicity = end - start;
        modes[index].overlap_cluster = overlapCluster;
      }
    }
    start = end - 1;
  }
}

function bonello(frequencies: number[]): CalculateResponse["bonello"] {
  const centers: number[] = [];
  for (let index = -8; index <= 8; index += 1) centers.push(125 * 2 ** (index / 3));
  const counts = centers.map((center) => {
    const low = center / 2 ** (1 / 6);
    const high = center * 2 ** (1 / 6);
    return frequencies.filter((frequency) => frequency >= low && frequency < high).length;
  });
  const violations = counts.flatMap((count, index) => index > 0 && count < counts[index - 1] ? [index] : []);
  return {
    cumple: violations.length === 0,
    bandas: Object.fromEntries(centers.map((center, index) => [round(center, 1), counts[index]])),
    violaciones: violations,
    total_modos: counts.reduce((sum, count) => sum + count, 0),
  };
}

function roomRatios(request: CalculateRequest): CalculateResponse["proporciones"] {
  const dimensions = [request.largo, request.ancho, request.alto].sort((a, b) => a - b);
  const normalized: [number, number, number] = [1, dimensions[1] / dimensions[0], dimensions[2] / dimensions[0]];
  const ordered = Object.entries(RATIOS)
    .map(([name, ratio]) => [name, ratio[1], ratio[2], Math.abs(normalized[1] - ratio[1]) + Math.abs(normalized[2] - ratio[2])] as const)
    .sort((left, right) => left[3] - right[3]);
  const nearestMiddle = Math.min(1.9, Math.max(1.1, normalized[1]));
  const nearestLargest = Math.max(nearestMiddle, Math.min(2.8, Math.max(1.4, normalized[2])));
  const distance = Math.hypot(normalized[1] - nearestMiddle, normalized[2] - nearestLargest);
  const names = ["largo", "ancho", "alto"] as const;
  const multiples: [string, string, number][] = [];
  const values = [request.largo, request.ancho, request.alto];
  for (let first = 0; first < values.length; first += 1) {
    for (let second = first + 1; second < values.length; second += 1) {
      const ratio = Math.max(values[first], values[second]) / Math.min(values[first], values[second]);
      const integer = Math.round(ratio);
      if (integer >= 2 && Math.abs(ratio - integer) <= 0.01) {
        multiples.push(values[first] > values[second] ? [names[first], names[second], integer] : [names[second], names[first], integer]);
      }
    }
  }
  return {
    proporcion_actual: normalized.map((value) => round(value, 5)) as [number, number, number],
    mas_cercana: ordered[0][0],
    proporcion_cercana: [1, ordered[0][1], ordered[0][2]],
    error: ordered[0][3],
    todas: ordered.map(([name, middle, largest]) => [name, middle, largest]),
    en_area_bolt: distance === 0,
    distancia_area_bolt: distance,
    proporcion_bolt_mas_cercana: [1, nearestMiddle, nearestLargest],
    convencion_dimensiones: "shortest:middle:longest (orientation-independent)",
    multiplos_enteros: multiples,
  };
}

function dimensionWarnings(request: CalculateRequest): string[] {
  const named = [["Largo", request.largo], ["Ancho", request.ancho], ["Alto", request.alto]] as const;
  const warnings: string[] = [];
  for (let first = 0; first < named.length; first += 1) {
    for (let second = first + 1; second < named.length; second += 1) {
      const [leftName, left] = named[first];
      const [rightName, right] = named[second];
      if (Math.abs(left - right) < 0.01) warnings.push(`${leftName} = ${rightName}: dimensiones iguales elevan la degeneración modal.`);
      const ratio = Math.max(left, right) / Math.min(left, right);
      if (Math.round(ratio) >= 2 && Math.abs(ratio - Math.round(ratio)) < 0.01) {
        warnings.push(`${leftName} y ${rightName} tienen una relación entera ${Math.round(ratio)}:1.`);
      }
    }
  }
  return warnings;
}

export async function calculateOffline(request: CalculateRequest): Promise<CalculateResponse> {
  await Promise.resolve();
  if (request.superficies.length !== 6) throw new Error("El cálculo requiere exactamente seis superficies.");
  const environment = environmentResult(request.environment);
  const volume = request.largo * request.ancho * request.alto;
  const areas = [
    request.ancho * request.alto,
    request.ancho * request.alto,
    request.largo * request.alto,
    request.largo * request.alto,
    request.largo * request.ancho,
    request.largo * request.ancho,
  ];
  const alphas = request.superficies.map((surface) => materialAlphas(surface.material, surface.alphas));
  const totalArea = areas.reduce((sum, area) => sum + area, 0);
  const rt60Bands: CalculateResponse["rt60_bandas"] = {};
  const methodWarnings: CalculateResponse["method_warnings"] = [];

  for (const band of OCTAVE_BANDS) {
    const absorption = areas.reduce((sum, area, index) => sum + area * alphas[index][band], 0);
    const averageAlpha = absorption / totalArea;
    const millingtonAbsorption = areas.reduce(
      (sum, area, index) => sum - area * Math.log(Math.max(1e-9, 1 - alphas[index][band])),
      0,
    );
    const sx = areas[0] + areas[1];
    const sy = areas[2] + areas[3];
    const sz = areas[4] + areas[5];
    const ax = (alphas[0][band] + alphas[1][band]) / 2;
    const ay = (alphas[2][band] + alphas[3][band]) / 2;
    const az = (alphas[4][band] + alphas[5][band]) / 2;
    const fitzDenominator = totalArea ** 2;
    const fitz = 0.161 * volume * (
      sx / -Math.log(Math.max(1e-9, 1 - ax)) +
      sy / -Math.log(Math.max(1e-9, 1 - ay)) +
      sz / -Math.log(Math.max(1e-9, 1 - az))
    ) / fitzDenominator;
    rt60Bands[band] = {
      Sabine: 0.161 * volume / Math.max(absorption, 1e-9),
      Eyring: 0.161 * volume / Math.max(-totalArea * Math.log(Math.max(1e-9, 1 - averageAlpha)), 1e-9),
      Millington: 0.161 * volume / Math.max(millingtonAbsorption, 1e-9),
      FitzRoy: fitz,
    };
    if (averageAlpha > 0.2) {
      methodWarnings.push({
        code: "sabine_applicability",
        method: "Sabine",
        band_hz: band,
        message: `Sabine pierde precisión con absorción media alta (${averageAlpha.toFixed(2)}) a ${band} Hz; compara Eyring/Millington.`,
        severity: "warning",
      });
    }
  }

  const rt60Mean = OCTAVE_BANDS.reduce((sum, band) => sum + rt60Bands[band].Sabine, 0) / OCTAVE_BANDS.length;
  const bandwidth = 2.2 / Math.max(rt60Mean, 1e-6);
  const modes = calculateModes(request, environment.sound_speed_m_s);
  markModeClusters(modes, bandwidth);
  const frequencies = modes.map((mode) => mode.frecuencia);
  const proportions = roomRatios(request);
  const maxOverlap = Math.max(0, ...modes.map((mode) => mode.overlap_multiplicity ?? 1));
  const diffuseClusters = Array.from(new Set(
    modes.filter((mode) => (mode.overlap_multiplicity ?? 1) >= 3).map((mode) => mode.overlap_cluster ?? 0),
  )).filter(Boolean);
  const target = request.uso ? TARGETS[request.uso] : undefined;
  const objective = target ? {
    ...structuredClone(target),
    diferencias: Object.fromEntries(OCTAVE_BANDS.map((band) => [band, Math.abs(rt60Bands[band].Sabine - target.valores[band])])),
  } : null;

  return {
    modos: modes,
    frecuencias: frequencies,
    cantidad_modos: modes.length,
    distribucion: {
      axiales: modes.filter((mode) => mode.tipo === "axial").length,
      tangenciales: modes.filter((mode) => mode.tipo === "tangencial").length,
      oblicuos: modes.filter((mode) => mode.tipo === "oblicuo").length,
      degenerados: modes.filter((mode) => mode.degenerado).length,
      solapados: modes.filter((mode) => mode.solapado).length,
    },
    rt60_bandas: rt60Bands,
    rt60_promedio: rt60Mean,
    f_schroeder: 2000 * Math.sqrt(rt60Mean / volume),
    delta_f: bandwidth,
    bonello: bonello(frequencies),
    proporciones: proportions,
    degeneracion_dimensiones: dimensionWarnings(request),
    objetivo: objective,
    method_warnings: methodWarnings,
    environment,
    sound_speed_m_s: environment.sound_speed_m_s,
    diffuse_field: {
      campo_difuso: maxOverlap >= 3,
      umbral_solapamiento: 3,
      solapamiento_maximo: maxOverlap,
      clusters_difusos: diffuseClusters,
      is_diffuse: maxOverlap >= 3,
      minimum_overlap: 3,
      max_overlap: maxOverlap,
    },
    bolt_area: {
      normalized_ratio: proportions.proporcion_actual,
      is_inside: proportions.en_area_bolt ?? false,
      distance: proportions.distancia_area_bolt ?? 0,
      nearest_ratio: proportions.proporcion_bolt_mas_cercana ?? proportions.proporcion_actual,
      dimension_convention: proportions.convencion_dimensiones ?? "shortest:middle:longest",
    },
  };
}

function modalValue(mode: Mode, x: number, y: number, z: number, room: PressureMapRequest): number {
  return Math.cos(mode.indices[0] * Math.PI * x / room.largo)
    * Math.cos(mode.indices[1] * Math.PI * y / room.ancho)
    * Math.cos(mode.indices[2] * Math.PI * z / room.alto);
}

function spectralScore(modes: Mode[], x: number, y: number, z: number, room: PressureMapRequest): number {
  if (!modes.length) return 0;
  const levels = modes.map((mode) => {
    const amplitude = 10 ** (mode.peso_db / 20) * Math.abs(modalValue(mode, x, y, z, room));
    return 20 * Math.log10(Math.max(amplitude, 1e-4));
  });
  const mean = levels.reduce((sum, level) => sum + level, 0) / levels.length;
  return Math.sqrt(levels.reduce((sum, level) => sum + (level - mean) ** 2, 0) / levels.length);
}

export async function pressureMapOffline(request: PressureMapRequest): Promise<PressureMapResponse> {
  await Promise.resolve();
  const environment = environmentResult(request.environment);
  const maxFrequency = request.max_freq ?? 300;
  const earHeight = request.ear_height ?? Math.min(1.2, request.alto);
  const size = Math.min(100, Math.max(10, request.grid_size ?? 60));
  const allModes = calculateModes(request, environment.sound_speed_m_s, maxFrequency);
  const modes = request.mode_indices
    ? allModes.filter((mode) => mode.indices.every((index, axis) => index === request.mode_indices?.[axis]))
    : allModes;
  if (request.mode_indices && !modes.length) {
    const [nx, ny, nz] = request.mode_indices;
    const nonZero = Number(nx > 0) + Number(ny > 0) + Number(nz > 0);
    modes.push({
      indices: request.mode_indices,
      frecuencia: environment.sound_speed_m_s / 2 * Math.sqrt(
        (nx / request.largo) ** 2 + (ny / request.ancho) ** 2 + (nz / request.alto) ** 2,
      ),
      tipo: nonZero === 1 ? "axial" : nonZero === 2 ? "tangencial" : "oblicuo",
      peso_db: nonZero === 1 ? 0 : nonZero === 2 ? -3 : -6,
      degenerado: false,
      solapado: false,
    });
  }
  const gridX = Array.from({ length: size }, (_, index) => request.largo * index / (size - 1));
  const gridY = Array.from({ length: size }, (_, index) => request.ancho * index / (size - 1));
  const single = Boolean(request.mode_indices);
  const signed = single ? gridY.map((y) => gridX.map((x) => modalValue(modes[0], x, y, earHeight, request))) : null;
  const energyRaw = single ? null : gridY.map((y) => gridX.map((x) => modes.reduce((sum, mode) => {
    const value = modalValue(mode, x, y, earHeight, request);
    return sum + 10 ** (mode.peso_db / 10) * value ** 2;
  }, 0)));
  const maxEnergy = energyRaw ? Math.max(0, ...energyRaw.flat()) : 1;
  const energy = energyRaw?.map((row) => row.map((value) => maxEnergy ? value / maxEnergy : 0)) ?? null;
  const magnitude = signed
    ? signed.map((row) => row.map(Math.abs))
    : (energy ?? []).map((row) => row.map(Math.sqrt));
  const pressure = signed ?? magnitude;

  const margin = Math.min(0.5, 0.1 * Math.min(request.largo, request.ancho));
  const reference = { x: Math.max(margin, Math.min(request.largo - margin, request.largo * 0.38)), y: request.ancho / 2 };
  const referenceScore = spectralScore(allModes, reference.x, reference.y, earHeight, request);
  let best = { x: reference.x, y: reference.y, score: referenceScore };
  const searchSize = 24;
  for (let yi = 0; yi < searchSize; yi += 1) {
    const y = margin + (request.ancho - 2 * margin) * yi / (searchSize - 1);
    for (let xi = 0; xi < searchSize; xi += 1) {
      const x = margin + (request.largo - 2 * margin) * xi / (searchSize - 1);
      const score = spectralScore(allModes, x, y, earHeight, request);
      if (score < best.score) best = { x, y, score };
    }
  }
  const dx = best.x - reference.x;
  const dy = best.y - reference.y;
  const movement = Math.hypot(dx, dy);
  const improvement = Math.max(0, referenceScore - best.score);
  const warnings = modes.length ? [] : [`No hay modos hasta ${maxFrequency} Hz.`];

  return {
    grid_x: gridX,
    grid_y: gridY,
    pressure,
    magnitude,
    energy,
    signed_pressure: signed,
    quantity: single ? "signed_normalized_pressure" : "normalized_weighted_rms_magnitude",
    max_freq: single ? modes[0]?.frecuencia ?? maxFrequency : maxFrequency,
    ear_height: earHeight,
    num_modos: modes.length,
    optimal_listening: {
      x: best.x,
      y: best.y,
      score: best.score,
      score_unit: "dB standard deviation",
      boundary_margin: margin,
      reference_position: reference,
      reference_score_db: referenceScore,
      movement_m: movement,
      movement: { dx_m: dx, dy_m: dy, distance_m: movement },
      improvement_db: improvement,
      db_improvement: improvement,
      warnings,
    },
    warnings,
    environment,
  };
}

export interface CalculationOutcome<T> {
  data: T;
  provenance: EngineProvenance;
  fallbackReason?: string;
}

function browserIsOffline(): boolean {
  return typeof navigator !== "undefined" && !navigator.onLine;
}

async function serverRequestWithTimeout<T>(
  request: (signal: AbortSignal) => Promise<T>,
  externalSignal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort(externalSignal?.reason);
  if (externalSignal?.aborted) abortFromCaller();
  else externalSignal?.addEventListener("abort", abortFromCaller, { once: true });
  const timer = window.setTimeout(
    () => controller.abort(new DOMException("El servidor no respondió a tiempo.", "TimeoutError")),
    5_000,
  );
  try {
    return await request(controller.signal);
  } finally {
    window.clearTimeout(timer);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function calculateWithOffline(
  request: CalculateRequest,
  apiKey: string | null | undefined,
  signal?: AbortSignal,
): Promise<CalculationOutcome<CalculateResponse>> {
  if (browserIsOffline()) {
    return { data: await calculateOffline(request), provenance: OFFLINE_ENGINE, fallbackReason: "Sin conexión" };
  }
  try {
    return { data: await serverRequestWithTimeout((requestSignal) => calculate(request, apiKey, requestSignal), signal), provenance: SERVER_ENGINE };
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return { data: await calculateOffline(request), provenance: OFFLINE_ENGINE, fallbackReason: error.message };
    }
    if (!(error instanceof ApiError) || !error.isNetworkFailure) throw error;
    return { data: await calculateOffline(request), provenance: OFFLINE_ENGINE, fallbackReason: error.message };
  }
}

export async function pressureMapWithOffline(
  request: PressureMapRequest,
  apiKey: string | null | undefined,
  signal?: AbortSignal,
): Promise<CalculationOutcome<PressureMapResponse>> {
  if (browserIsOffline()) {
    return { data: await pressureMapOffline(request), provenance: OFFLINE_ENGINE, fallbackReason: "Sin conexión" };
  }
  try {
    return { data: await serverRequestWithTimeout((requestSignal) => fetchPressureMap(request, { signal: requestSignal, apiKey }), signal), provenance: SERVER_ENGINE };
  } catch (error) {
    if (signal?.aborted) throw error;
    if (error instanceof DOMException && error.name === "TimeoutError") {
      return { data: await pressureMapOffline(request), provenance: OFFLINE_ENGINE, fallbackReason: error.message };
    }
    if (!(error instanceof ApiError) || !error.isNetworkFailure) throw error;
    return { data: await pressureMapOffline(request), provenance: OFFLINE_ENGINE, fallbackReason: error.message };
  }
}
