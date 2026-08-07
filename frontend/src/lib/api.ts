import type { CalculateRequest, CalculateResponse } from "./types";

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

export async function fetchMaterials(): Promise<
  Record<string, { alphas: Record<string, number>; label: string }>
> {
  const res = await fetch(`${API_BASE}/api/v1/materials`);
  return res.json();
}
