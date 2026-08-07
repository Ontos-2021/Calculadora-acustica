"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import type { CalculateResponse } from "@/lib/types";
import { calculate } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/Card";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { PDFDownloadLink } from "@react-pdf/renderer";
import { PDFReport } from "@/components/export/PDFReport";
import { exportCSV, exportJSON } from "@/components/export/exportUtils";
import { SummaryCards } from "@/components/results/SummaryCards";
import { ModeTable } from "@/components/results/ModeTable";
import { BonelloVerdict } from "@/components/results/BonelloVerdict";
import { ProportionsCard } from "@/components/results/ProportionsCard";
import { RT60Table } from "@/components/results/RT60Table";
import { DimensionWarnings } from "@/components/results/DimensionWarnings";
import { RT60Chart } from "@/components/charts/RT60Chart";
import { BonelloChart } from "@/components/charts/BonelloChart";
import { ComparisonChart } from "@/components/charts/ComparisonChart";

export default function ResultsContent() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<CalculateResponse | null>(null);
  const [requestData, setRequestData] = useState<{ largo: number; ancho: number; alto: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchResults = useCallback(async () => {
    const encoded = searchParams.get("data");
    if (!encoded) {
      setError("No se encontraron datos de cálculo.");
      setLoading(false);
      return;
    }
    try {
      const request = JSON.parse(atob(encoded));
      setRequestData({ largo: request.largo, ancho: request.ancho, alto: request.alto });
      const result = await calculate(request);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al calcular");
    } finally {
      setLoading(false);
    }
  }, [searchParams]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl">
        <Card>
          <CardTitle>Calculando...</CardTitle>
          <LoadingSkeleton rows={8} />
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
          <div className="mt-4 text-center">
            <Link
              href="/"
              className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600"
            >
              Volver
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <SummaryCards data={data} />
      {data.degeneracion_dimensiones.length > 0 && (
        <DimensionWarnings warnings={data.degeneracion_dimensiones} />
      )}
      <Card>
        <CardTitle>
          Modos de Resonancia
          <span className="ml-2 text-sm font-normal text-gray-400">
            ({data.cantidad_modos} modos)
          </span>
        </CardTitle>
        <ModeTable modos={data.modos} />
      </Card>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <div className="grid grid-cols-1 gap-4">
            <BonelloVerdict bonello={data.bonello} />
            <BonelloChart bandas={data.bonello.bandas} />
          </div>
        </Card>
        <Card>
          <ProportionsCard proporciones={data.proporciones} />
        </Card>
      </div>
      <Card>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-gray-700">RT60 por Método</h3>
            <RT60Chart data={data.rt60_bandas} />
          </div>
          {data.objetivo ? (
            <div>
              <h3 className="mb-3 text-sm font-semibold text-gray-700">Actual vs. Objetivo</h3>
              <ComparisonChart data={data.rt60_bandas} objetivo={data.objetivo} />
            </div>
          ) : (
            <div className="flex items-center justify-center rounded-lg bg-gray-50 p-8 text-sm text-gray-400">
              Seleccione un uso para ver la comparación con el RT60 objetivo
            </div>
          )}
        </div>
        <div className="mt-6">
          <RT60Table bandas={data.rt60_bandas} objetivo={data.objetivo} />
        </div>
      </Card>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="rounded-lg bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-transform hover:scale-[1.02] hover:bg-indigo-600"
        >
          Volver
        </Link>

        {requestData && (
          <PDFDownloadLink
            document={<PDFReport data={data} room={requestData} />}
            fileName="informe-acustico.pdf"
            className="rounded-lg bg-gray-700 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-transform hover:scale-[1.02] hover:bg-gray-800"
          >
            {({ loading: pdfLoading }) =>
              pdfLoading ? "Generando PDF..." : "Descargar PDF"
            }
          </PDFDownloadLink>
        )}

        <button
          onClick={() => exportCSV(data)}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-transform hover:scale-[1.02] hover:bg-emerald-700"
        >
          Exportar CSV
        </button>

        <button
          onClick={() => exportJSON(data)}
          className="rounded-lg bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md transition-transform hover:scale-[1.02] hover:bg-amber-700"
        >
          Exportar JSON
        </button>
      </div>
    </div>
  );
}
