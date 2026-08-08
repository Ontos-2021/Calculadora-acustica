"use client";

import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import type { CalculateResponse, PressureMapResponse, IRResponse, InverseDesignResponse } from "@/lib/types";
import { calculate, fetchPressureMap, fetchImpulseResponse, fetchInverseDesign } from "@/lib/api";
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
import { PressureMapChart } from "@/components/charts/PressureMapChart";
import { ListeningPositionSelector } from "@/components/results/ListeningPositionSelector";
import { ImpulseResponseChart } from "@/components/charts/ImpulseResponseChart";
import { ISMParams } from "@/components/results/ISMParams";
import { InverseDesign } from "@/components/results/InverseDesign";
import { AbsorberCalculators } from "@/components/results/AbsorberCalculators";

export default function ResultsContent() {
  const searchParams = useSearchParams();
  const [data, setData] = useState<CalculateResponse | null>(null);
  const [requestData, setRequestData] = useState<{ largo: number; ancho: number; alto: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pressureData, setPressureData] = useState<PressureMapResponse | null>(null);
  const [pressureLoading, setPressureLoading] = useState(false);
  const [selectedMode, setSelectedMode] = useState("all");
  const [maxFreq, setMaxFreq] = useState(300);
  const [irData, setIrData] = useState<IRResponse | null>(null);
  const [irLoading, setIrLoading] = useState(false);
  const [irError, setIrError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [sourcePos, setSourcePos] = useState({ x: 1, y: 1, z: 1.5 });
  const [receiverPos, setReceiverPos] = useState({ x: 4, y: 3, z: 1.2 });
  const [inverseData, setInverseData] = useState<InverseDesignResponse | null>(null);
  const [inverseLoading, setInverseLoading] = useState(false);

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
      // Also fetch pressure map
      const pm = await fetchPressureMap({
        largo: request.largo,
        ancho: request.ancho,
        alto: request.alto,
        superficies: request.superficies,
        max_freq: 300,
        grid_size: 100,
      });
      setPressureData(pm);
      if (request.uso) {
        setInverseLoading(true);
        try {
          const inv = await fetchInverseDesign({
            largo: request.largo,
            ancho: request.ancho,
            alto: request.alto,
            superficies: request.superficies,
            target_uso: request.uso,
            include_placement: true,
          });
          setInverseData(inv);
        } catch {
          // inverse design is optional
        } finally {
          setInverseLoading(false);
        }
      }
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

      {pressureData && (
        <Card>
          <CardTitle>Mapa de Presión Modal</CardTitle>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <PressureMapChart
                data={pressureData}
                modes={data.modos}
                selectedMode={selectedMode}
                onSelectMode={setSelectedMode}
                onMaxFreqChange={setMaxFreq}
                maxFreq={maxFreq}
              />
            </div>
            <div>
              <ListeningPositionSelector
                modes={data.modos}
                largo={requestData?.largo ?? 5}
                ancho={requestData?.ancho ?? 4}
                alto={requestData?.alto ?? 3}
              />
            </div>
          </div>
        </Card>
      )}

      <Card>
        <CardTitle>
          Modos de Resonancia
          <span className="ml-2 text-sm font-normal text-gray-400">
            ({data.cantidad_modos} modos)
          </span>
        </CardTitle>
        <ModeTable
          modos={data.modos}
          onSelectMode={(freq) => {
            const m = data.modos.find((mm) => mm.frecuencia === freq);
            if (m && requestData) {
              setSelectedMode(String(freq));
              fetchPressureMap({
                largo: requestData.largo,
                ancho: requestData.ancho,
                alto: requestData.alto,
                superficies: JSON.parse(atob(searchParams.get("data") || "")).superficies,
                mode_indices: [m.indices[0], m.indices[1], m.indices[2]],
                grid_size: 80,
              }).then(setPressureData);
            }
          }}
          selectedFreq={selectedMode !== "all" ? Number(selectedMode) : null}
        />
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
      {inverseData && (
        <Card>
          <CardTitle>Diseño Inverso</CardTitle>
          <InverseDesign data={inverseData} />
        </Card>
      )}

      <AbsorberCalculators />

      <Card>
        <CardTitle>
          Análisis Avanzado — Fuentes Imagen
          <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">PAID</span>
        </CardTitle>
        {!apiKey ? (
          <div className="rounded-lg bg-amber-50 p-4">
            <p className="mb-3 text-sm text-amber-800">
              Esta funcionalidad requiere una licencia PAID.
            </p>
            <input
              type="text"
              placeholder="Ingrese su API Key..."
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
              <div>
                <label className="block text-xs font-medium text-gray-500">Fuente X</label>
                <input type="number" step="0.1" className="mt-1 w-full rounded border px-2 py-1 text-sm"
                  value={sourcePos.x} onChange={(e) => setSourcePos(s => ({ ...s, x: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500">Fuente Y</label>
                <input type="number" step="0.1" className="mt-1 w-full rounded border px-2 py-1 text-sm"
                  value={sourcePos.y} onChange={(e) => setSourcePos(s => ({ ...s, y: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500">Fuente Z</label>
                <input type="number" step="0.1" className="mt-1 w-full rounded border px-2 py-1 text-sm"
                  value={sourcePos.z} onChange={(e) => setSourcePos(s => ({ ...s, z: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500">Receptor X</label>
                <input type="number" step="0.1" className="mt-1 w-full rounded border px-2 py-1 text-sm"
                  value={receiverPos.x} onChange={(e) => setReceiverPos(s => ({ ...s, x: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500">Receptor Y</label>
                <input type="number" step="0.1" className="mt-1 w-full rounded border px-2 py-1 text-sm"
                  value={receiverPos.y} onChange={(e) => setReceiverPos(s => ({ ...s, y: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500">Receptor Z</label>
                <input type="number" step="0.1" className="mt-1 w-full rounded border px-2 py-1 text-sm"
                  value={receiverPos.z} onChange={(e) => setReceiverPos(s => ({ ...s, z: Number(e.target.value) }))} />
              </div>
            </div>
            <button
              onClick={async () => {
                setIrLoading(true);
                setIrError(null);
                try {
                  const r = requestData ? { largo: requestData.largo, ancho: requestData.ancho, alto: requestData.alto } : { largo: 5, ancho: 4, alto: 3 };
                  const encoded = searchParams.get("data");
                  let superficies: { material: string }[] = [];
                  try { const req = JSON.parse(atob(encoded || "")); superficies = req.superficies || []; } catch {}
                  const result = await fetchImpulseResponse({
                    ...r, superficies,
                    source: [sourcePos.x, sourcePos.y, sourcePos.z],
                    receiver: [receiverPos.x, receiverPos.y, receiverPos.z],
                  }, apiKey);
                  setIrData(result);
                } catch (err) {
                  setIrError(err instanceof Error ? err.message : "Error ISM");
                } finally {
                  setIrLoading(false);
                }
              }}
              disabled={irLoading}
              className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
            >
              {irLoading ? "Calculando..." : "Calcular respuesta al impulso"}
            </button>
            {irError && <p className="text-sm text-red-600">{irError}</p>}
            {irData && (
              <div className="space-y-4">
                <ImpulseResponseChart ir={irData.impulse_response} sampleRate={irData.sample_rate} />
                <ISMParams params={irData.parameters} />
              </div>
            )}
          </div>
        )}
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
            document={<PDFReport data={data} room={requestData} irParams={irData?.parameters} />}
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
