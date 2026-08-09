import type { CalculateRequest } from "./types";

export class TransportDataError extends Error {
  constructor(message = "Los datos del análisis están dañados o incompletos.") {
    super(message);
    this.name = "TransportDataError";
  }
}

export function encodeBase64Url(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  const chunkSize = 0x8000;
  for (let start = 0; start < bytes.length; start += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(start, start + chunkSize));
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function decodeBase64Url(value: string): string {
  if (!value || !/^[A-Za-z0-9_-]+$/.test(value) || value.length % 4 === 1) {
    throw new TransportDataError();
  }
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
  try {
    const binary = atob(padded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new TransportDataError();
  }
}

export function encodeRequestData(request: CalculateRequest): string {
  return encodeBase64Url(JSON.stringify(request));
}

export function decodeRequestData(value: string): CalculateRequest {
  try {
    const parsed = JSON.parse(decodeBase64Url(value)) as Partial<CalculateRequest>;
    if (
      !parsed ||
      typeof parsed !== "object" ||
      ![parsed.largo, parsed.ancho, parsed.alto].every(
        (dimension) => typeof dimension === "number" && Number.isFinite(dimension) && dimension > 0,
      ) ||
      !Array.isArray(parsed.superficies) ||
      parsed.superficies.length !== 6
    ) {
      throw new TransportDataError();
    }
    return {
      ...parsed,
      environment: parsed.environment ?? {
        temperature_c: 20,
        relative_humidity: 50,
        pressure_pa: 101325,
      },
    } as CalculateRequest;
  } catch (error) {
    if (error instanceof TransportDataError) throw error;
    throw new TransportDataError();
  }
}
