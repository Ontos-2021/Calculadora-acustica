# Calculadora Acústica Profesional

Herramienta profesional de diseño acústico arquitectónico con API (FastAPI) y frontend (Next.js), capacidad offline (Pyodide WASM) y soporte normativo ISO + ASTM.

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12, FastAPI, Pydantic |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4 |
| Visualización | Apache ECharts 6 |
| PDF | @react-pdf/renderer |
| Offline | Pyodide (Python en WASM) |
| Infra | Docker, nginx |

## Inicio rápido

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

Abrir http://localhost:3000. API en http://localhost:8000/docs.

## Docker

```bash
docker compose up --build
```

Abrir http://localhost (frontend) o http://localhost:8000/docs (API).

## Tests

```bash
python -m pytest tests/ -v    # 194 tests
```

## Arquitectura

```
frontend/          Next.js 16 (static export)
  src/components/  UI + charts
  src/lib/         API client + offline Pyodide

api/               FastAPI
  routes.py        Endpoints REST
  schemas.py       Modelos Pydantic
  dependencies.py  Feature gates

acoustic_core/     Biblioteca acústica (pure Python)
  models.py        Room, Material, Surface
  presets.py       38 materiales + ISO 11654
  reverberation.py RT60 (4 métodos)
  resonance.py     Modos de resonancia
  evaluation.py    Bonello, Schroeder
  design.py        Proporciones, RT60 objetivo
  pressure.py      Mapas de presión modal
  impulse.py       ISM + ISO 3382
  inverse.py       Diseño inverso
  absorbers.py     Absorbentes
  diffusers.py     Difusores QRD/Skyline
  isolation.py     Aislamiento (TL, STC, Rw, NC)
  measurement.py   ESS, waterfall, calibración
  finite_impedance.py  Modos con pared finita
  fem2d.py         FEM 2D
  ray_tracing.py   Ray tracing Monte Carlo
  hybrid.py        Híbrido ISM + ray tracing

tests/             194 tests pytest
```
