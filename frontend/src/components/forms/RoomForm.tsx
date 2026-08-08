"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import type { CalculateRequest, SurfaceInput, MaterialInfo } from "@/lib/types";
import { fetchMaterials, fetchMaterialCategories } from "@/lib/api";

const BANDAS = ["125", "250", "500", "1000", "2000", "4000"];
const SUP_NOMBRES = ["Frente", "Contrafrente", "Lat. Izquierdo", "Lat. Derecho", "Piso", "Techo"];

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

const ISO_COLORS: Record<string, string> = {
  A: "bg-green-100 text-green-800",
  B: "bg-blue-100 text-blue-800",
  C: "bg-yellow-100 text-yellow-800",
  D: "bg-orange-100 text-orange-800",
  E: "bg-red-100 text-red-800",
};

interface FormData {
  largo: string;
  ancho: string;
  alto: string;
  uso: string;
  materiales: string[];
  alphas: Record<string, Record<string, string>>;
}

function MaterialBadge({ alpha_w, iso_class }: { alpha_w: number | null; iso_class: string }) {
  if (iso_class === "No clasificado" || !iso_class) return null;
  const color = ISO_COLORS[iso_class] || "bg-gray-100 text-gray-800";
  return (
    <span className={`ml-1 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${color}`}>
      {iso_class} (α_w={alpha_w?.toFixed(2)})
    </span>
  );
}

export function RoomForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [materials, setMaterials] = useState<MaterialInfo[]>([]);
  const [categories, setCategories] = useState<Record<string, string[]>>({});
  const [materialsLoading, setMaterialsLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [form, setForm] = useState<FormData>({
    largo: "",
    ancho: "",
    alto: "",
    uso: "",
    materiales: Array(6).fill("Concreto"),
    alphas: {},
  });
  const [showAlpha, setShowAlpha] = useState<Record<number, boolean>>({});

  useEffect(() => {
    async function load() {
      try {
        const [mats, cats] = await Promise.all([
          fetchMaterials(),
          fetchMaterialCategories(),
        ]);
        setMaterials(mats);
        setCategories(cats);
      } catch {
        setMaterials([]);
        setCategories({});
      } finally {
        setMaterialsLoading(false);
      }
    }
    load();
  }, []);

  const filteredMaterials = materials.filter((m) => {
    if (filter && !m.nombre.toLowerCase().includes(filter.toLowerCase())) return false;
    if (selectedCategory && m.categoria !== selectedCategory) return false;
    return true;
  });

  const grouped = filteredMaterials.reduce<Record<string, MaterialInfo[]>>((acc, m) => {
    (acc[m.categoria] ||= []).push(m);
    return acc;
  }, {});

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
              <label htmlFor={`dim-${dim}`} className="mb-1 block text-sm font-medium text-gray-700">
                {dim.charAt(0).toUpperCase() + dim.slice(1)} (m)
              </label>
              <input
                id={`dim-${dim}`}
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
        <div className="mb-3 flex flex-wrap gap-2">
          <input
            id="mat-filter"
            type="text"
            placeholder="Filtrar materiales..."
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <select
            id="mat-categoria"
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
          >
            <option value="">Todas las categorías</option>
            {Object.keys(categories).map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SUP_NOMBRES.map((nombre, i) => {
            const supId = `mat-${nombre.toLowerCase().replace(/[\s.]+/g, '-')}`;
            return (
            <div key={i}>
              <label htmlFor={supId} className="mb-1 block text-sm font-medium text-gray-700">
                {nombre}
              </label>
              <select
                id={supId}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                value={form.materiales[i]}
                onChange={(e) => updateMaterial(i, e.target.value)}
              >
                {materialsLoading ? (
                  <option>Cargando...</option>
                ) : (
                  Object.entries(grouped).map(([cat, mats]) => (
                    <optgroup key={cat} label={cat}>
                      {mats.map((m) => (
                        <option key={m.nombre} value={m.nombre}>
                          {m.nombre}{m.iso_class && m.iso_class !== "No clasificado" ? ` [${m.iso_class}]` : ""}
                        </option>
                      ))}
                    </optgroup>
                  ))
                )}
              </select>
              {form.materiales[i] && (
                <MaterialBadge
                  alpha_w={materials.find((m) => m.nombre === form.materiales[i])?.alpha_w ?? null}
                  iso_class={materials.find((m) => m.nombre === form.materiales[i])?.iso_class ?? ""}
                />
              )}
              <button
                type="button"
                className="mt-1 text-xs text-indigo-600 hover:text-indigo-800"
                onClick={() => setShowAlpha((s) => ({ ...s, [i]: !s[i] }))}
              >
                {showAlpha[i] ? "Ocultar α" : "α personalizado"}
              </button>
              {showAlpha[i] && (
                <div className="mt-2 grid grid-cols-3 gap-1 rounded-lg bg-gray-50 p-2">
                  {BANDAS.map((banda) => {
                    const alphaId = `alpha-${nombre.toLowerCase().replace(/[\s.]+/g, '-')}-${banda}`;
                    return (
                    <div key={banda}>
                      <label htmlFor={alphaId} className="text-[10px] text-gray-500">{banda} Hz</label>
                      <input
                        id={alphaId}
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
                    );
                  })}
                </div>
              )}
            </div>
            );
          })}
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Uso de la sala
        </h3>
        <select
          id="sala-uso"
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
        disabled={loading || materialsLoading}
        className="w-full rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-3 text-sm font-semibold text-white shadow-md transition-transform hover:scale-[1.01] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Calculando..." : "Calcular"}
      </button>
    </form>
  );
}
