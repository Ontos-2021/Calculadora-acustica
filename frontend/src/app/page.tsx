import { Suspense } from "react";
import { Workspace } from "@/components/workspace/Workspace";

export default function Home() {
  return <Suspense fallback={<div className="p-8 text-sm text-muted">Preparando workspace…</div>}><Workspace /></Suspense>;
}
