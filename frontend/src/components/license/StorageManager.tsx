"use client";

import { useEffect, useState } from "react";
import { Download, HardDrive, Trash2, Upload } from "lucide-react";
import { useLicense } from "@/context/LicenseProvider";
import {
  ApiError,
  deleteStoredObject,
  downloadStoredObject,
  fetchStorageUsage,
  fetchStoredObjects,
  uploadStoredObject,
} from "@/lib/api";
import type { StoredAsset, StorageUsage } from "@/lib/types";

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  return `${(value / 1024 ** 3).toFixed(1)} GiB`;
}

export function StorageManager() {
  const { apiKey, hasEntitlement } = useLicense();
  const [assets, setAssets] = useState<StoredAsset[]>([]);
  const [usage, setUsage] = useState<StorageUsage | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!apiKey || !hasEntitlement("storage")) return;
    try {
      const [objects, currentUsage] = await Promise.all([
        fetchStoredObjects(apiKey),
        fetchStorageUsage(apiKey),
      ]);
      setAssets(objects.items);
      setUsage(currentUsage);
      setError(null);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "No se pudo consultar el almacenamiento.");
    }
  }

  useEffect(() => { void refresh(); }, [apiKey]);

  async function upload(file: File) {
    if (!apiKey) return;
    setBusy(true);
    setProgress(0);
    try {
      await uploadStoredObject(file, apiKey, setProgress);
      await refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "No se pudo subir el archivo.");
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  async function remove(asset: StoredAsset) {
    if (!apiKey || !window.confirm(`¿Borrar ${asset.filename}?`)) return;
    setBusy(true);
    try {
      await deleteStoredObject(asset.id, apiKey);
      await refresh();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "No se pudo borrar el archivo.");
    } finally {
      setBusy(false);
    }
  }

  async function download(asset: StoredAsset) {
    if (!apiKey) return;
    try {
      const blob = await downloadStoredObject(asset.id, apiKey);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = asset.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "No se pudo descargar el archivo.");
    }
  }

  if (!apiKey || !hasEntitlement("storage")) return null;

  return <div className="mt-3 border-t border-zinc-200 pt-3 dark:border-zinc-800">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2"><HardDrive className="size-4 text-teal-600" /><h2 className="text-xs font-semibold">Almacenamiento privado</h2></div>
      <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-teal-700 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-teal-800 aria-disabled:opacity-50">
        <Upload className="size-3.5" /> Subir archivo
        <input className="sr-only" type="file" disabled={busy} onChange={(event) => event.target.files?.[0] && void upload(event.target.files[0])} />
      </label>
    </div>
    {usage && <div className="mt-2">
      <div className="mb-1 flex justify-between text-[11px] text-muted"><span>{formatBytes(usage.used_bytes)} usados</span><span>{formatBytes(usage.limit_bytes)}</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"><div className="h-full rounded-full bg-teal-600 transition-[width]" style={{ width: `${usage.usage_percent}%` }} /></div>
    </div>}
    {progress !== null && <div className="mt-2 text-[11px] text-teal-700" role="status">Subiendo… {progress}%</div>}
    {error && <p className="mt-2 text-xs text-red-700" role="alert">{error}</p>}
    <div className="mt-2 max-h-44 divide-y divide-zinc-200 overflow-y-auto dark:divide-zinc-800">
      {assets.map((asset) => <div key={asset.id} className="flex items-center gap-2 py-2 text-xs">
        <div className="min-w-0 flex-1"><p className="truncate font-medium">{asset.filename}</p><p className="text-[10px] text-muted">{asset.category} · {formatBytes(asset.size_bytes)}</p></div>
        <button type="button" onClick={() => void download(asset)} className="rounded p-1.5 hover:bg-surface-muted" aria-label={`Descargar ${asset.filename}`}><Download className="size-3.5" /></button>
        <button type="button" disabled={busy} onClick={() => void remove(asset)} className="rounded p-1.5 text-red-600 hover:bg-red-50 disabled:opacity-50" aria-label={`Borrar ${asset.filename}`}><Trash2 className="size-3.5" /></button>
      </div>)}
      {!assets.length && <p className="py-3 text-center text-[11px] text-muted">Todavía no hay archivos.</p>}
    </div>
  </div>;
}
