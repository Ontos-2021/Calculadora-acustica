"use client";

import { LockKeyhole } from "lucide-react";
import { PDFDownloadLink } from "@react-pdf/renderer";
import type { ReportBundle } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card, CardTitle } from "@/components/ui/Card";
import { PDFReport } from "./PDFReport";
import { exportCSV, exportJSON, exportLatex, exportTypst } from "./exportUtils";

export function ProfessionalExport({ report, enabled }: { report: ReportBundle; enabled: boolean }) {
  return <Card><CardTitle>Exportación profesional</CardTitle>{!enabled ? <div className="relative overflow-hidden rounded-lg border border-amber-200 bg-surface-muted p-5"><div className="pointer-events-none select-none opacity-25 blur-[1px]"><div className="grid grid-cols-3 gap-2">{["PDF", "CSV", "JSON"].map((value) => <div key={value} className="rounded bg-zinc-300 p-3 text-center font-semibold">{value}</div>)}</div></div><div className="absolute inset-0 grid place-items-center"><span className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900"><LockKeyhole className="mr-1 inline size-3.5" />Requiere exports</span></div></div> : <div className="grid grid-cols-2 gap-2 sm:grid-cols-5"><PDFDownloadLink document={<PDFReport report={report} />} fileName="informe-acustico-profesional.pdf" className="rounded-md bg-zinc-900 px-3 py-2 text-center text-sm font-semibold text-white">{({ loading }) => loading ? "Generando…" : "PDF"}</PDFDownloadLink><Button onClick={() => exportCSV(report)}>CSV</Button><Button onClick={() => exportJSON(report)}>JSON</Button><Button onClick={() => exportLatex(report)}>LaTeX</Button><Button onClick={() => exportTypst(report)}>Typst</Button></div>}</Card>;
}
