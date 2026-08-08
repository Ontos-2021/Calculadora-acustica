import type { CalculateRequest, CalculateResponse, MaterialInfo } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function calculate(
  data: CalculateRequest,
): Promise<CalculateResponse> {
  const res = await fetch(`${API_BASE}/api/v1/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      err.detail || `Error ${res.status}`,
    );
  }
  return res.json();
}

export async function fetchImpulseResponse(
  data: {
    largo: number;
    ancho: number;
    alto: number;
    superficies: { material: string }[];
    source: [number, number, number];
    receiver: [number, number, number];
    max_order?: number;
  },
  apiKey?: string,
): Promise<import("./types").IRResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) headers["X-API-Key"] = apiKey;

  const res = await fetch(`${API_BASE}/api/v1/impulse-response`, {
    method: "POST",
    headers,
    body: JSON.stringify({ ...data, max_order: data.max_order ?? 8 }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err.detail || "Error al calcular ISM");
  }
  return res.json();
}

export async function fetchMaterials(): Promise<MaterialInfo[]> {
  const res = await fetch(`${API_BASE}/api/v1/materials`);
  if (!res.ok) throw new ApiError(res.status, "Error al cargar materiales");
  return res.json();
}

export async function fetchMaterialCategories(): Promise<Record<string, string[]>> {
  const res = await fetch(`${API_BASE}/api/v1/materials/categories`);
  if (!res.ok) throw new ApiError(res.status, "Error al cargar categorías");
  return res.json();
}

export async function fetchMaterialDetail(name: string): Promise<MaterialInfo> {
  const res = await fetch(`${API_BASE}/api/v1/materials/${encodeURIComponent(name)}`);
  if (!res.ok) throw new ApiError(res.status, `Material '${name}' no encontrado`);
  return res.json();
}

export interface PressureMapRequest {
  largo: number;
  ancho: number;
  alto: number;
  superficies: { material: string; alphas?: Record<string, number> }[];
  ear_height?: number;
  max_freq?: number;
  grid_size?: number;
  mode_indices?: [number, number, number];
}

export async function fetchPressureMap(
  data: PressureMapRequest,
): Promise<import("./types").PressureMapResponse> {
  const res = await fetch(`${API_BASE}/api/v1/pressure-map`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(res.status, err.detail || "Error al obtener mapa de presión");
  }
  return res.json();
}
