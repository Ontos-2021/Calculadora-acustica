import type {
  CalculateRequest,
  CalculateResponse,
  InverseDesignResponse,
  IRResponse,
  LicenseStatus,
  MaterialInfo,
  PressureMapRequest,
  PressureMapResponse,
  RoomRequest,
  StoredAsset,
  StoredAssetList,
  StorageUsage,
} from "./types";

type ErrorKind = "network" | "unauthorized" | "forbidden" | "rate_limited" | "validation" | "http";
type ResponseType = "json" | "blob" | "text";

function normalizedApiRoot(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim() || "/api";
  const root = configured.replace(/\/+$/, "");
  if (/\/api\/v1$/i.test(root)) return root;
  if (/\/api$/i.test(root)) return `${root}/v1`;
  return `${root}/api/v1`;
}

export const API_ROOT = normalizedApiRoot();

function apiUrl(path: string): string {
  return `${API_ROOT}/${path.replace(/^\/+/, "")}`;
}

function errorDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") return null;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const issue = item as { loc?: unknown[]; msg?: string };
        const location = issue.loc?.slice(1).join(".");
        return `${location ? `${location}: ` : ""}${issue.msg || "dato no válido"}`;
      })
      .join("; ");
  }
  return null;
}

function statusKind(status: number): ErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 429) return "rate_limited";
  if (status === 400 || status === 422) return "validation";
  return "http";
}

function statusMessage(status: number, detail: string | null): string {
  const suffix = detail ? ` ${detail}` : "";
  if (status === 401) return `La clave API no es válida, está inactiva o falta.${suffix}`.trim();
  if (status === 403) return `La licencia no incluye esta función.${suffix}`.trim();
  if (status === 429) return `Se alcanzó la cuota o el límite temporal de solicitudes.${suffix}`.trim();
  if (status === 422) return `Revisa los datos ingresados.${suffix}`.trim();
  return detail || `La API respondió con estado ${status}.`;
}

export class ApiError extends Error {
  readonly kind: ErrorKind;
  readonly retryAfterSeconds: number | null;
  readonly detail: string | null;

  constructor(
    public readonly status: number,
    message: string,
    options: { kind?: ErrorKind; retryAfterSeconds?: number | null; detail?: string | null; cause?: unknown } = {},
  ) {
    super(message, options.cause === undefined ? undefined : { cause: options.cause });
    this.name = "ApiError";
    this.kind = options.kind ?? statusKind(status);
    this.retryAfterSeconds = options.retryAfterSeconds ?? null;
    this.detail = options.detail ?? null;
  }

  get isNetworkFailure(): boolean {
    return this.kind === "network";
  }
}

interface ApiRequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown | FormData;
  apiKey?: string | null;
  signal?: AbortSignal;
  responseType?: ResponseType;
  headers?: HeadersInit;
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (options.body !== undefined && !isForm) headers.set("Content-Type", "application/json");
  if (options.apiKey) headers.set("X-API-Key", options.apiKey);
  headers.set("Accept", options.responseType === "blob" ? "application/octet-stream, audio/wav" : "application/json");

  const requestBody: BodyInit | undefined = options.body === undefined
    ? undefined
    : isForm
      ? options.body as FormData
      : JSON.stringify(options.body);
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: options.method ?? (options.body === undefined ? "GET" : "POST"),
      headers,
      body: requestBody,
      signal: options.signal,
      cache: "no-store",
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "No se pudo conectar con el servidor.", {
      kind: "network",
      cause,
    });
  }

  if (!response.ok) {
    const payload = await response.clone().json().catch(() => null);
    const detail = errorDetail(payload) || (await response.text().catch(() => "")) || null;
    const retryHeader = response.headers.get("Retry-After");
    throw new ApiError(response.status, statusMessage(response.status, detail), {
      detail,
      retryAfterSeconds: retryHeader && Number.isFinite(Number(retryHeader)) ? Number(retryHeader) : null,
    });
  }

  if (response.status === 204) return undefined as T;
  if (options.responseType === "blob") return (await response.blob()) as T;
  if (options.responseType === "text") return (await response.text()) as T;
  return (await response.json()) as T;
}

export function calculate(data: CalculateRequest, apiKey?: string | null, signal?: AbortSignal): Promise<CalculateResponse> {
  return apiRequest<CalculateResponse>("calculate", { body: data, apiKey, signal });
}

export function fetchLicenseStatus(apiKey: string, signal?: AbortSignal): Promise<LicenseStatus> {
  return apiRequest<LicenseStatus>("license/status", { apiKey, signal });
}

export function fetchStoredObjects(apiKey: string): Promise<StoredAssetList> {
  return apiRequest<StoredAssetList>("objects", { apiKey });
}

export function fetchStorageUsage(apiKey: string): Promise<StorageUsage> {
  return apiRequest<StorageUsage>("objects/usage", { apiKey });
}

export function deleteStoredObject(assetId: string, apiKey: string): Promise<void> {
  return apiRequest<void>(`objects/${encodeURIComponent(assetId)}`, { method: "DELETE", apiKey });
}

export function downloadStoredObject(assetId: string, apiKey: string): Promise<Blob> {
  return apiRequest<Blob>(`objects/${encodeURIComponent(assetId)}/download`, {
    apiKey,
    responseType: "blob",
  });
}

export function uploadStoredObject(
  file: File,
  apiKey: string,
  onProgress: (percent: number) => void,
): Promise<StoredAsset> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", apiUrl("objects"));
    request.setRequestHeader("X-API-Key", apiKey);
    request.responseType = "json";
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100));
    };
    request.onerror = () => reject(new ApiError(0, "No se pudo subir el archivo.", { kind: "network" }));
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        onProgress(100);
        resolve(request.response as StoredAsset);
        return;
      }
      const detail = errorDetail(request.response);
      reject(new ApiError(request.status, statusMessage(request.status, detail), { detail }));
    };
    const form = new FormData();
    form.append("file", file);
    request.send(form);
  });
}

export function fetchMaterials(apiKey?: string | null): Promise<MaterialInfo[]> {
  return apiRequest<MaterialInfo[]>(apiKey ? "materials" : "materials/defaults", { apiKey });
}

export function fetchMaterialCategories(apiKey?: string | null): Promise<Record<string, string[]>> {
  return apiRequest<Record<string, string[]>>(
    apiKey ? "materials/categories" : "materials/defaults/categories",
    { apiKey },
  );
}

export function fetchMaterialDetail(name: string, apiKey: string): Promise<MaterialInfo> {
  return apiRequest<MaterialInfo>(`materials/${encodeURIComponent(name)}`, { apiKey });
}

export function fetchPressureMap(
  data: PressureMapRequest,
  options: { signal?: AbortSignal; apiKey?: string | null } = {},
): Promise<PressureMapResponse> {
  return apiRequest<PressureMapResponse>("pressure-map", { body: data, signal: options.signal, apiKey: options.apiKey });
}

export function fetchInverseDesign(
  data: RoomRequest & { target_uso: string; include_placement?: boolean },
  apiKey: string,
): Promise<InverseDesignResponse> {
  return apiRequest<InverseDesignResponse>("design/inverse", { body: data, apiKey });
}

export function fetchImpulseResponse(
  data: RoomRequest & {
    source: [number, number, number];
    receiver: [number, number, number];
    max_order?: number;
    sample_rate?: number;
    duration_s?: number;
    band?: string;
  },
  apiKey: string,
): Promise<IRResponse> {
  return apiRequest<IRResponse>("impulse-response", {
    body: { ...data, max_order: data.max_order ?? 8 },
    apiKey,
  });
}

export function postAdvanced<T>(path: string, body: unknown, apiKey: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { body, apiKey, signal });
}

export function getAdvanced<T>(path: string, apiKey: string, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { apiKey, signal });
}

export async function downloadAdvanced(
  path: string,
  body: unknown,
  apiKey: string,
  fallbackFilename: string,
): Promise<{ blob: Blob; filename: string }> {
  const blob = await apiRequest<Blob>(path, { body, apiKey, responseType: "blob" });
  return { blob, filename: fallbackFilename };
}

export function uploadWav(
  file: File,
  apiKey: string,
  options: { analyze?: boolean; channel?: string; directDelayMs?: number } = {},
): Promise<Record<string, unknown>> {
  const data = new FormData();
  data.append("file", file);
  const query = new URLSearchParams({ channel: options.channel ?? "0" });
  if (options.analyze) query.set("direct_delay_ms", String(options.directDelayMs ?? 0));
  const action = options.analyze ? "analyze" : "import";
  return apiRequest<Record<string, unknown>>(`measurement/wav/${action}?${query}`, {
    body: data,
    apiKey,
  });
}
