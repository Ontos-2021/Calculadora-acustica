import { Suspense } from "react";
import { Workspace } from "@/components/workspace/Workspace";

export default function ResultsPage() {
  return <Suspense fallback={<div className="p-8 text-sm text-muted">Cargando análisis…</div>}><Workspace /></Suspense>;
}
