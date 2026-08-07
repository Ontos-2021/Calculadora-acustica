export interface Mode {
  indices: [number, number, number];
  frecuencia: number;
  tipo: "axial" | "tangencial" | "oblicuo";
  peso_db: number;
  degenerado: boolean;
  solapado: boolean;
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
  valores: Record<string, number>;
  diferencias?: Record<string, number>;
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
  };
  rt60_bandas: RT60Bandas;
  rt60_promedio: number;
  f_schroeder: number;
  delta_f: number;
  bonello: BonelloResult;
  proporciones: ProporcionesResult;
  degeneracion_dimensiones: string[];
  objetivo: ObjetivoInfo | null;
}

export interface CalculateRequest {
  largo: number;
  ancho: number;
  alto: number;
  uso?: string;
  superficies: { material: string; alphas?: Record<string, number> }[];
}

export interface SurfaceInput {
  material: string;
  alphas?: Record<string, number>;
}

export interface PressureMapResponse {
  grid_x: number[];
  grid_y: number[];
  pressure: number[][];
  max_freq: number;
  ear_height: number;
  num_modos: number;
  optimal_listening: { x: number; y: number; score: number };
}

export interface ListeningPosition {
  x: number;
  y: number;
  score: number;
}

export interface IRResponse {
  impulse_response: number[];
  sample_rate: number;
  direct_delay_ms: number;
  parameters: {
    EDT: number;
    T20: number;
    T30: number;
    C80: number;
    C50: number;
    D50: number;
    Ts: number;
    ITDG: number | null;
    flutter_echo: { detected: boolean; frequency: number | null };
  };
}
