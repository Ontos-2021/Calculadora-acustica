# Changelog

Todos los cambios relevantes de este proyecto se documentan aquí. El formato
sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto
usa versionado semántico para las entregas públicas.

## [Unreleased]

### Añadido

- Contrato versionado del subsistema de almacenamiento privado, incluyendo
  ownership, cuota por licencia, ciclo de vida, API e integraciones previstas.
- Modelo persistente `StoredAsset` y baseline Alembic para evolucionar el
  esquema de almacenamiento en instalaciones existentes.
- Backend de almacenamiento app-scoped e inyectable en desarrollo, tests y
  producción, con LocalStorage local y S3 privado en producción.
- Servicio transaccional de objetos con reserva de cuota por licencia,
  ownership, integridad SHA-256, compensación y ciclo de vida persistente.
- API autenticada `/objects` para subir, listar, consultar uso, descargar y
  borrar objetos privados.
- Entitlement `storage` desde FREE y rate limiting sensible al método HTTP para
  cobrar uploads sin penalizar consultas.
- Auditoría de objetos, verificación SHA-256 en descarga y reconciliación de
  registros pendientes, contenido ausente y blobs huérfanos.

## [2.0.0] - 2026-08-09

### Añadido

- Núcleo científico por bandas con ambiente, propagación de incertidumbre,
  advertencias metodológicas, modos ponderados y evaluación de campo difuso.
- Paquete server-only `acoustic_numerics/` con NumPy/SciPy para impedancia
  finita, FEM 2D, trazado de rayos SAH-BVH y modelos híbridos.
- Herramientas profesionales de diseño inverso, absorbentes, difusores,
  aislamiento, medición ESS/ISO 3382, mapas de presión e ISM.
- Plataforma FREEMIUM con API keys, tiers FREE/PAID/RESEARCH, entitlements,
  cuotas, rate limiting, PostgreSQL/SQLite, Redis, jobs, worker y storage.
- Exportación profesional PDF, CSV, JSON, LaTeX y Typst con entradas,
  procedencia, supuestos, advertencias y resultados de sesión.
- PWA con motor FREE TypeScript determinista, catálogo offline y shell
  precacheado.
- Suite de 500 pruebas pytest y 47 pruebas Playwright contra el export estático
  de producción, incluyendo accesibilidad y layouts móviles.

### Cambiado

- La API pública queda versionada bajo `/api/v1` con contratos Pydantic
  explícitos y feature gates centralizados.
- Los métodos numéricos se cargan mediante adaptadores lazy para conservar
  `acoustic_core/` libre de dependencias NumPy/SciPy.
- Playwright construye y sirve el export de producción mediante servidores
  aislados, API con dos workers y licencias deterministas.
- `pdf-parse` se actualiza a 2.4.5 y las pruebas validan el contenido real de
  los informes PDF generados.

### Corregido

- Las solicitudes de cálculo y mapa de presión ahora transmiten la clave API;
  las licencias PAID/RESEARCH dejan de consumir la cuota anónima.
- Alias de usos de sala entre diseño y aislamiento, incluyendo
  `home_studio`, `home_theater`, `sala_conferencias` e `iglesia`.
- Identidades estables de series ECharts para evitar fallos internos
  `getRawIndex` al actualizar datos.
- Service Worker actualizado a `acoustic-pwa-v5`: assets estáticos
  network-first y caché solo como fallback, evitando mezclar chunks antiguos de
  Turbopack con código nuevo.
- Validación de licencia con timeout recuperable y persistencia restringida a
  la sesión del navegador.
- Carreras E2E en exportación: JSON y CSV esperan a que el mapa de presión esté
  disponible antes de comprobar resultados avanzados.
- Etiquetado accesible, contraste, navegación por teclado, tablas desplazables
  y viewport móvil Chromium.

### Validación

- `python3 -m pytest tests/ -q`: 500 pruebas aprobadas.
- `npm run build`: export estático y TypeScript aprobados.
- `npm run test:e2e`: 47 pruebas aprobadas; última ejecución en 5.8 minutos.
- `docker compose config --quiet` y `git diff --check`: aprobados.

### Límites

- Los resultados son estimaciones de ingeniería basadas en referencias
  públicas; no constituyen medición, ensayo, certificación ni declaración de
  cumplimiento.
