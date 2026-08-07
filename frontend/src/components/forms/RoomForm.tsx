"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { CalculateRequest, SurfaceInput } from "@/lib/types";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];
const SUP_NOMBRES = ["Frente", "Contrafrente", "Lat. Izquierdo", "Lat. Derecho", "Piso", "Techo"];

const MATERIAL_PRESETS = [
  "Concreto", "Madera", "Yeso", "Vidrio",
  "Alfombra gruesa", "Cortina pesada", "Panel acústico", "Espuma acústica",
];

const USOS: Record<string, string> = {
  home_studio: "Home Studio / Grabación",
  sala_conferencias: "Sala de conferencias",
  aula: "Aula",
  teatro: "Teatro",
  sala_conciertos: "Sala de conciertos",
  iglesia: "Iglesia / Culto",
  home_theater: "Home Theater",
  restaurante: "Restaurante",
};

interface FormData {
  largo: string;
  ancho: string;
  alto: string;
  uso: string;
  materiales: string[];
  alphas: Record<string, Record<string, string>>;
}

export function RoomForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>({
    largo: "",
    ancho: "",
    alto: "",
    uso: "",
    materiales: Array(6).fill("Concreto"),
    alphas: {},
  });
  const [showAlpha, setShowAlpha] = useState<Record<number, boolean>>({});

  const updateMaterial = useCallback((i: number, val: string) => {
    setForm((f) => {
      const mats = [...f.materiales];
      mats[i] = val;
      return { ...f, materiales: mats };
    });
  }, []);

  const updateAlpha = useCallback((i: number, banda: string, val: string) => {
    setForm((f) => {
      const key = `sup_${i}`;
      const current = { ...(f.alphas[key] || {}) };
      current[banda] = val;
      return { ...f, alphas: { ...f.alphas, [key]: current } };
    });
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);

      const largo = parseFloat(form.largo);
      const ancho = parseFloat(form.ancho);
      const alto = parseFloat(form.alto);

      if (!largo || !ancho || !alto || largo <= 0 || ancho <= 0 || alto <= 0) {
        setError("Las dimensiones deben ser números positivos.");
        return;
      }

      const superficies: SurfaceInput[] = form.materiales.map((mat, i) => {
        const alphas: Record<string, number> = {};
        const key = `sup_${i}`;
        const custom = form.alphas[key];
        if (custom) {
          for (const banda of BANDAS) {
            const v = parseFloat(custom[banda]);
            if (!isNaN(v) && v >= 0 && v <= 1) alphas[banda] = v;
          }
        }
        return { material: mat, ...(Object.keys(alphas).length ? { alphas } : {}) };
      });

      const request: CalculateRequest = { largo, ancho, alto, superficies };
      if (form.uso) request.uso = form.uso;

      setLoading(true);
      const encoded = btoa(JSON.stringify(request));
      router.push(`/results?data=${encoded}`);
    },
    [form, router],
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Dimensiones de la sala
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {["largo", "ancho", "alto"].map((dim) => (
            <div key={dim}>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {dim.charAt(0).toUpperCase() + dim.slice(1)} (m)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                placeholder={`ej: ${dim === "largo" ? "8.5" : dim === "ancho" ? "6.0" : "3.0"}`}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                value={form[dim as keyof FormData] as string}
                onChange={(e) => setForm((f) => ({ ...f, [dim]: e.target.value }))}
              />
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Materiales por superficie
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SUP_NOMBRES.map((nombre, i) => (
            <div key={i}>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                {nombre}
              </label>
              <select
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                value={form.materiales[i]}
                onChange={(e) => updateMaterial(i, e.target.value)}
              >
                {MATERIAL_PRESETS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="mt-1 text-xs text-indigo-600 hover:text-indigo-800"
                onClick={() => setShowAlpha((s) => ({ ...s, [i]: !s[i] }))}
              >
                {showAlpha[i] ? "Ocultar α" : "α personalizado"}
              </button>
              {showAlpha[i] && (
                <div className="mt-2 grid grid-cols-3 gap-1 rounded-lg bg-gray-50 p-2">
                  {BANDAS.map((banda) => (
                    <div key={banda}>
                      <label className="text-[10px] text-gray-500">{banda} Hz</label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        placeholder="α"
                        className="w-full rounded border border-gray-300 px-1.5 py-1 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                        value={form.alphas[`sup_${i}`]?.[banda] ?? ""}
                        onChange={(e) => updateAlpha(i, banda, e.target.value)}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Uso de la sala
        </h3>
        <select
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          value={form.uso}
          onChange={(e) => setForm((f) => ({ ...f, uso: e.target.value }))}
        >
          <option value="">— Sin comparación objetivo —</option>
          {Object.entries(USOS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-400">
          Si selecciona un uso, el RT60 se comparará con el valor óptimo según normativa.
        </p>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-3 text-sm font-semibold text-white shadow-md transition-transform hover:scale-[1.01] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Calculando..." : "Calcular"}
      </button>
    </form>
  );
}
