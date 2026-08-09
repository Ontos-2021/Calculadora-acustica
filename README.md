# Calculadora Acústica Profesional

Herramienta profesional de diseño acústico arquitectónico con API FastAPI, frontend Next.js, cálculo FREE offline y modelos basados en referencias públicas ISO, ASTM y ANSI.

Los resultados son estimaciones de ingeniería. No sustituyen mediciones, ensayos, certificación ni verificación de cumplimiento.

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12+, FastAPI, Pydantic, SQLAlchemy |
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4 |
| Visualización | Apache ECharts 6 |
| PDF | @react-pdf/renderer |
| Offline | Service Worker + motor TypeScript determinista |
| Numérico | NumPy/SciPy en paquete server-only |
| Infra | Docker, nginx, PostgreSQL, Redis, worker, almacenamiento S3-compatible |

## Inicio rápido

```bash
# Backend
pip install -r requirements.txt -r requirements-dev.txt
uvicorn api.main:app --reload --port 8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
```

Abrir http://localhost:3000. API en http://localhost:8000/docs.

En desarrollo, Next.js reenvía `/api/*` al backend de `127.0.0.1:8000`. Puede
sobrescribirse con `API_PROXY_URL`. El Service Worker usa red primero para los
assets estáticos y reserva la caché como fallback, evitando mezclar chunks
obsoletos de Turbopack después de reiniciar `next dev`.

## Docker

```bash
docker compose up --build
```

Abrir http://localhost (frontend) o http://localhost:8000/docs (API).

## Tests

```bash
python3 -m pytest tests/ -q   # 500 tests

cd frontend
npm run build                 # build estático + TypeScript
npm run test:e2e              # 47 tests Playwright, incluye build de producción
```

La suite E2E levanta una API aislada con SQLite y cuotas deterministas, genera
el export estático y lo sirve con proxy `/api`. No reutiliza los servidores de
desarrollo de los puertos 3000/8000.

## Documentación de cambios

La evolución funcional y las correcciones de cada entrega se registran en
[`CHANGELOG.md`](CHANGELOG.md). El alcance histórico y el estado autoritativo
de las fases se mantienen en [`ROADMAP.md`](ROADMAP.md).

## Arquitectura

```
frontend/          Next.js 16 (static export)
  src/components/  UI + charts
  src/lib/         API client + motor FREE offline
  e2e/             Playwright + servidores aislados de producción

api/               FastAPI
  routes.py        Endpoints REST
  schemas.py       Modelos Pydantic
  dependencies.py  Feature gates
  licensing.py     API keys, tiers y entitlements
  database.py      SQLAlchemy, PostgreSQL/SQLite
  jobs.py           Cola Redis y trabajos

worker/            Procesamiento asíncrono

acoustic_core/     Biblioteca acústica (pure Python)
  models.py        Room, Material, Surface
  spectrum.py      Bandas y conversiones espectrales
  environment.py   Velocidad del sonido y ambiente
  uncertainty.py   Propagación e intervalos
  presets.py       Materiales + ISO 11654 + procedencia
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
  finite_impedance.py  Adaptador lazy server-only
  fem2d.py         Adaptador lazy server-only
  ray_tracing.py   Adaptador lazy server-only
  hybrid.py        Adaptador lazy server-only

acoustic_numerics/ NumPy/SciPy: impedancia, FEM, SAH-BVH e híbrido

tests/             500 tests pytest
```
