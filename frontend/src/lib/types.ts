export const OCTAVE_BANDS = ["125", "250", "500", "1000", "2000", "4000"] as const;

export type OctaveBand = (typeof OCTAVE_BANDS)[number];
export type BandValues = Record<string, number>;

export interface EnvironmentInput {
  temperature_c: number;
  relative_humidity: number;
  pressure_pa: number;
}

export interface StoredAsset {
  id: string;
  filename: string;
  content_type: string;
  category: "upload" | "wav" | "export" | "job" | string;
  size_bytes: number;
  sha256: string;
  status: "PENDING" | "READY" | "DELETING" | "FAILED";
  created_at: string;
}

export interface StoredAssetList {
  items: StoredAsset[];
  total: number;
  offset: number;
  limit: number;
}

export interface StorageUsage {
  used_bytes: number;
  limit_bytes: number;
  remaining_bytes: number;
  object_count: number;
  usage_percent: number;
}

export interface EnvironmentResult extends EnvironmentInput {
  sound_speed_m_s: number;
}

export interface SurfaceInput {
  material: string;
  alphas?: BandValues;
}

export interface RoomRequest {
  largo: number;
  ancho: number;
  alto: number;
  superficies: SurfaceInput[];
  environment: EnvironmentInput;
}

export interface CalculateRequest extends RoomRequest {
  uso?: string;
  include_air_attenuation?: boolean;
}

export interface Mode {
  indices: [number, number, number];
  frecuencia: number;
  tipo: "axial" | "tangencial" | "oblicuo";
  peso_db: number;
  degenerado: boolean;
  solapado: boolean;
  multiplicity?: number;
  degeneracy_cluster?: number | null;
  overlap_multiplicity?: number;
  overlap_cluster?: number | null;
}

export interface BonelloResult {
  cumple: boolean;
  bandas: Record<string, number>;
  violaciones: number[];
  total_modos: number;
}

export interface ProporcionesResult {
  proporcion_actual: [number, number, number];
  mas_cercana: string;
  proporcion_cercana: [number, number, number];
  error: number;
  todas: [string, number, number][];
  en_area_bolt?: boolean;
  distancia_area_bolt?: number;
  proporcion_bolt_mas_cercana?: [number, number, number];
  convencion_dimensiones?: string;
  multiplos_enteros?: [string, string, number][];
}

export interface RT60Bandas {
  [banda: string]: {
    Sabine: number;
    Eyring: number;
    Millington: number;
    FitzRoy: number;
  };
}

export interface ObjetivoInfo {
  label: string;
  valores: BandValues;
  diferencias?: BandValues;
}

export interface MethodWarning {
  code: string;
  message: string;
  method?: string | null;
  band_hz?: string | null;
  surface?: string | null;
  severity?: "info" | "warning";
}

export interface DiffuseFieldResult {
  campo_difuso: boolean;
  umbral_solapamiento: number;
  solapamiento_maximo: number;
  clusters_difusos: number[];
  is_diffuse: boolean;
  minimum_overlap: number;
  max_overlap: number;
}

export interface BoltAreaResult {
  normalized_ratio: [number, number, number];
  is_inside: boolean;
  distance: number;
  nearest_ratio: [number, number, number];
  dimension_convention: string;
}

export interface CalculateResponse {
  modos: Mode[];
  frecuencias: number[];
  cantidad_modos: number;
  distribucion: {
    axiales: number;
    tangenciales: number;
    oblicuos: number;
    degenerados: number;
    solapados: number;
    [key: string]: number | boolean;
  };
  rt60_bandas: RT60Bandas;
  rt60_promedio: number;
  f_schroeder: number;
  delta_f: number;
  bonello: BonelloResult;
  proporciones: ProporcionesResult;
  degeneracion_dimensiones: string[];
  objetivo: ObjetivoInfo | null;
  method_warnings: MethodWarning[];
  environment: EnvironmentResult;
  sound_speed_m_s: number;
  diffuse_field: DiffuseFieldResult;
  bolt_area: BoltAreaResult;
}

export interface ListeningPosition {
  x: number;
  y: number;
  score: number;
  score_unit: string;
  boundary_margin: number;
  reference_position: { x: number; y: number };
  reference_score_db: number;
  movement_m: number;
  movement: { dx_m: number; dy_m: number; distance_m: number };
  improvement_db: number;
  db_improvement: number;
  warnings: string[];
}

export interface PressureMapRequest extends RoomRequest {
  ear_height?: number;
  max_freq?: number;
  grid_size?: number;
  mode_indices?: [number, number, number];
}

export interface PressureMapResponse {
  grid_x: number[];
  grid_y: number[];
  pressure: number[][];
  magnitude: number[][];
  energy: number[][] | null;
  signed_pressure: number[][] | null;
  quantity: "signed_normalized_pressure" | "normalized_weighted_rms_magnitude" | string;
  max_freq: number;
  ear_height: number;
  num_modos: number;
  optimal_listening: ListeningPosition;
  warnings: string[];
  environment: EnvironmentResult;
}

export interface MaterialSuggestion {
  material: string;
  area_needed_m2: number;
  alpha_w: number | null;
  iso_class: string;
  categoria: string;
  per_band: BandValues;
  installation_mode?: string | null;
  available_area_m2?: number | null;
  feasible?: boolean | null;
  governing_bands?: string[];
  predicted_rt60_s?: Record<string, number | null> | null;
  estimate_label?: string | null;
}

export interface PlacementSuggestion {
  surface: string;
  surface_area_m2: number;
  missing_absorption_m2: number;
  priority_score: number;
  coverage_percent: number;
  governing_band?: string | null;
  pressure_evidence?: string | null;
}

export interface InverseDesignResponse {
  current_absorption: BandValues;
  required_absorption: BandValues;
  missing_absorption: BandValues;
  material_suggestions: MaterialSuggestion[];
  placement_suggestions: PlacementSuggestion[];
}

export interface MaterialInfo {
  nombre: string;
  categoria: string;
  alphas: BandValues;
  alpha_w: number | null;
  iso_class: string;
  provenance?: string | null;
  uncertainty?: {
    standard: number;
    expanded: number;
    unit: string;
    coverage_factor: number;
    confidence_level: number | null;
    source: string | null;
  } | null;
  catalog?: Record<string, unknown> | null;
  iso11654?: Record<string, unknown> | null;
}

export interface ISO3382Parameters {
  EDT: number | null;
  T20: number | null;
  T30: number | null;
  C80: number;
  C50: number;
  D50: number;
  Ts: number;
  ITDG: number | null;
  flutter_echo: { detected: boolean; frequency: number | null; [key: string]: unknown };
  regression_diagnostics?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface IRResponse {
  impulse_response: number[];
  sample_rate: number;
  direct_delay_ms: number;
  direct_delay_s: number;
  direct_sample: number;
  arrivals_rendered: number;
  image_source_count: number;
  impulse_representation: string;
  normalization_gain: number;
  band: string;
  parameters: ISO3382Parameters | { error: string };
  environment: EnvironmentResult;
}

export interface LicenseStatus {
  authenticated: true;
  user_id: string;
  license_id: string;
  api_key_id: string;
  email: string;
  tier: "FREE" | "PAID" | "RESEARCH";
  key_prefix: string;
  entitlements: string[];
  quotas: Record<string, number>;
}

export interface EngineProvenance {
  id: "server-acoustic-core" | "offline-typescript-free";
  label: string;
  version: string;
  offline: boolean;
  assumptions: string[];
}

export type AdvancedArtifacts = Record<string, unknown>;

export interface ReportBundle {
  schema_version: "acoustic-report/2.0";
  generated_at: string;
  input: CalculateRequest;
  results: CalculateResponse;
  pressure?: PressureMapResponse | null;
  treatment?: unknown;
  isolation?: unknown;
  measurement?: unknown;
  numerical?: unknown;
  impulse_response?: IRResponse | null;
  advanced: AdvancedArtifacts;
  provenance: EngineProvenance;
  assumptions: string[];
  certification: "engineering_estimate_not_measurement_or_certification";
}
