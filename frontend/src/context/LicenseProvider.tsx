"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, fetchLicenseStatus } from "@/lib/api";
import type { LicenseStatus } from "@/lib/types";

const SESSION_KEY = "acoustic-api-key";

interface LicenseContextValue {
  apiKey: string | null;
  status: LicenseStatus | null;
  validating: boolean;
  error: string | null;
  activate: (candidate: string) => Promise<boolean>;
  revokeLocal: () => void;
  hasEntitlement: (feature: string) => boolean;
}

const LicenseContext = createContext<LicenseContextValue | null>(null);

export function LicenseProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [validating, setValidating] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function validate(candidate: string, persist: boolean): Promise<boolean> {
    const normalized = candidate.trim();
    if (!normalized) {
      setError("Introduce una clave API.");
      return false;
    }
    setValidating(true);
    setError(null);
    const controller = new AbortController();
    const timer = window.setTimeout(
      () => controller.abort(new DOMException("El servidor no respondió a tiempo.", "TimeoutError")),
      12_000,
    );
    try {
      const license = await fetchLicenseStatus(normalized, controller.signal);
      setApiKey(normalized);
      setStatus(license);
      if (persist) sessionStorage.setItem(SESSION_KEY, normalized);
      return true;
    } catch (cause) {
      setApiKey(null);
      setStatus(null);
      sessionStorage.removeItem(SESSION_KEY);
      if (controller.signal.aborted) {
        setError("No se pudo validar la licencia: el servidor no respondió a tiempo.");
      } else {
        setError(cause instanceof ApiError ? cause.message : "No se pudo validar la licencia.");
      }
      return false;
    } finally {
      window.clearTimeout(timer);
      setValidating(false);
    }
  }

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (!stored) {
      setValidating(false);
      return;
    }
    void validate(stored, false);
  }, []);

  function revokeLocal() {
    sessionStorage.removeItem(SESSION_KEY);
    setApiKey(null);
    setStatus(null);
    setError(null);
    setValidating(false);
  }

  return (
    <LicenseContext.Provider
      value={{
        apiKey,
        status,
        validating,
        error,
        activate: (candidate) => validate(candidate, true),
        revokeLocal,
        hasEntitlement: (feature) => Boolean(status?.entitlements.includes(feature)),
      }}
    >
      {children}
    </LicenseContext.Provider>
  );
}

export function useLicense(): LicenseContextValue {
  const context = useContext(LicenseContext);
  if (!context) throw new Error("useLicense must be used inside LicenseProvider");
  return context;
}
