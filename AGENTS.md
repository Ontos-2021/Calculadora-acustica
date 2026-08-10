# Project: Calculadora Acústica Profesional

## Structure
- `acoustic_core/` - Pure Python lib (no numpy)
- `acoustic_numerics/` - Server-only NumPy/SciPy solvers
- `api/` - FastAPI backend
- `worker/` - Redis job worker
- `frontend/` - Next.js 16 App Router
- `tests/` - pytest (526 tests)

## Commands
- `python3 -m pytest tests/ -q` - Run backend tests
- `npm run build` (from frontend/) - Build frontend
- `npm run test:e2e` (from frontend/) - Build production export and run 47 Playwright tests
- `npm run dev` (from frontend/) - Dev frontend
- `uvicorn api.main:app --reload` - Dev backend
- `docker compose up --build` - Full stack

## Conventions
- New modules: `acoustic_core/<name>.py`, add to `__init__.py`
- New endpoints: schema in `api/schemas.py`, route in `api/routes.py`, feature in `api/dependencies.py`
- Frontend components in `frontend/src/components/`, types in `types.ts`, API in `api.ts`
- Tests: `tests/test_<module>.py`
- Offline: update the deterministic TypeScript implementation in `frontend/src/lib/offline.ts` when changing FREE calculations
- Numerical methods: implement in `acoustic_numerics/`; keep `acoustic_core/` adapters lazy and dependency-free
- Materials: add in `acoustic_core/presets.py` with `categoria`, backward compat names in `_OLD_NAMES`
