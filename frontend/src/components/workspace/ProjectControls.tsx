"use client";

import { Copy, Save, Trash2 } from "lucide-react";
import { useWorkspaceStore } from "@/lib/workspaceStore";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";

export function ProjectControls() {
  const { projects, activeProjectId, request, openProject, saveProject, duplicateProject, removeProject } = useWorkspaceStore();
  return <section className="mb-5 rounded-lg border bg-surface-muted p-3" aria-label="Proyectos guardados">
    <div className="mb-2 flex items-center justify-between"><h2 className="text-xs font-bold uppercase tracking-[0.12em] text-zinc-500">Proyecto</h2><span className="text-[11px] text-muted">Autosave local</span></div>
    <Select aria-label="Proyecto activo" className="min-h-9 text-xs" value={activeProjectId || ""} onChange={(event) => event.target.value && openProject(event.target.value)}><option value="">Sala sin guardar</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</Select>
    <div className="mt-2 grid grid-cols-3 gap-1">
      <Button type="button" variant="secondary" size="sm" disabled={!request} onClick={() => saveProject()} title="Guardar proyecto"><Save className="size-3.5" /><span className="sr-only xl:not-sr-only">Guardar</span></Button>
      <Button type="button" variant="ghost" size="sm" disabled={!activeProjectId} onClick={() => activeProjectId && duplicateProject(activeProjectId)} title="Duplicar proyecto"><Copy className="size-3.5" /><span className="sr-only">Duplicar</span></Button>
      <Button type="button" variant="ghost" size="sm" disabled={!activeProjectId} onClick={() => activeProjectId && removeProject(activeProjectId)} title="Eliminar proyecto"><Trash2 className="size-3.5 text-rose-600" /><span className="sr-only">Eliminar</span></Button>
    </div>
  </section>;
}
