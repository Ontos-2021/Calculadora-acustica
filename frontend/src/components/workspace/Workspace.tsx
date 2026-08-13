"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { PanelLeftOpen } from "lucide-react";
import { RoomForm, ROOM_PRESETS } from "@/components/forms/RoomForm";
import ResultsContent from "@/app/results/ResultsContent";
import { Button } from "@/components/ui/Button";
import { Sheet } from "@/components/ui/Sheet";
import { ProjectControls } from "./ProjectControls";
import { decodeRequestData } from "@/lib/transport";
import { encodeRequestData } from "@/lib/transport";
import { useWorkspaceStore } from "@/lib/workspaceStore";
import type { CalculateRequest } from "@/lib/types";

export function Workspace() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const encoded = searchParams.get("data");
  const decoded = useMemo(() => { try { return encoded ? decodeRequestData(encoded) : null; } catch { return null; } }, [encoded]);
  const { request, setRequest, activeProjectId } = useWorkspaceStore();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [section, setSection] = useState(searchParams.get("s") || "summary");
  const current = decoded || request;

  useEffect(() => { if (decoded) setRequest(decoded); }, [decoded, setRequest]);

  const editor = <><ProjectControls /><RoomForm key={activeProjectId || encoded || "draft"} initialRequest={current} progressive={!current} onCalculate={(next) => { setSheetOpen(false); router.push(`/results?data=${encodeRequestData(next)}`); }} /></>;

  return <div className="mx-auto max-w-[1600px] lg:grid lg:grid-cols-[340px_minmax(0,1fr)] xl:grid-cols-[380px_minmax(0,1fr)]">
    <aside className="scrollbar-thin hidden h-[calc(100dvh-3.5rem)] overflow-y-auto border-r bg-surface p-4 lg:sticky lg:top-14 lg:block xl:p-5" aria-label="Parámetros de la sala">{editor}</aside>
    <main className="min-w-0 px-3 py-4 pb-24 sm:px-5 sm:py-6 lg:px-7 lg:pb-6 xl:px-9">
      {!current ? <Welcome onPreset={setRequest} /> : <ResultsContent requestOverride={current} activeSection={section} onSectionChange={setSection} />}
    </main>
    <Button type="button" className="fixed bottom-4 left-1/2 z-40 max-w-[calc(100vw-2rem)] -translate-x-1/2 truncate shadow-xl lg:hidden" onClick={() => setSheetOpen(true)}><PanelLeftOpen className="size-4 shrink-0" />{current ? `Sala · ${current.largo} × ${current.ancho} × ${current.alto} m` : "Configurar sala"}</Button>
    <Sheet open={sheetOpen} onOpenChange={setSheetOpen} title="Parámetros de la sala">{editor}</Sheet>
  </div>;
}

function Welcome({ onPreset }: { onPreset: (request: CalculateRequest) => void }) {
  return <div className="mx-auto max-w-5xl py-5 sm:py-12">
    <p className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700 dark:text-teal-400">Nuevo análisis</p>
    <h2 className="mt-3 max-w-3xl text-3xl font-bold tracking-[-0.035em] text-zinc-950 dark:text-white sm:text-5xl">Entiende la respuesta acústica de tu sala antes de construir.</h2>
    <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-700 dark:text-zinc-300 sm:text-lg">Empieza con una sala de referencia o introduce las dimensiones. Los resultados FREE aparecen inmediatamente en el navegador y se verifican con el servidor en segundo plano.</p>
    <section className="mt-8 grid gap-3 sm:grid-cols-3" aria-label="Salas de referencia">{ROOM_PRESETS.map((preset) => <button key={preset.name} type="button" onClick={() => onPreset(preset.request)} className="group rounded-xl border bg-surface p-5 text-left shadow-[var(--shadow-panel)] transition hover:-translate-y-0.5 hover:border-teal-500 hover:shadow-lg"><span className="text-xs font-semibold text-teal-700 dark:text-teal-400">Usar como punto de partida →</span><strong className="mt-5 block text-base">{preset.name}</strong><span className="mt-1 block text-sm text-muted">{preset.description}</span></button>)}</section>
    <div className="mt-8 rounded-xl border border-dashed border-teal-300 bg-teal-50/50 p-5 text-sm text-teal-950 dark:border-teal-900 dark:bg-teal-950/20 dark:text-teal-100"><strong>Flujo guiado:</strong> abre “Configurar sala” y completa primero largo, ancho y alto. El resto del panel se revelará automáticamente.</div>
  </div>;
}
