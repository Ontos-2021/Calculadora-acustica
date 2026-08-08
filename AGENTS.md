# Project: Calculadora Acústica Profesional

## Structure
- `acoustic_core/` - Pure Python lib (no numpy)
- `api/` - FastAPI backend
- `frontend/` - Next.js 16 App Router
- `tests/` - pytest (194 tests)

## Commands
- `python -m pytest tests/ -v` - Run backend tests
- `npm run build` (from frontend/) - Build frontend
- `npm run dev` (from frontend/) - Dev frontend
- `uvicorn api.main:app --reload` - Dev backend
- `docker compose up --build` - Full stack

## Conventions
- New modules: `acoustic_core/<name>.py`, add to `__init__.py`
- New endpoints: schema in `api/schemas.py`, route in `api/routes.py`, feature in `api/dependencies.py`
- Frontend components in `frontend/src/components/`, types in `types.ts`, API in `api.ts`
- Tests: `tests/test_<module>.py`
- Offline: update inline Python in `frontend/src/lib/offline.ts` when adding core modules
- Materials: add in `acoustic_core/presets.py` with `categoria`, backward compat names in `_OLD_NAMES`
