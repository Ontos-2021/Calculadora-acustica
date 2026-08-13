# Frontend de Calculadora Acústica

Aplicación Next.js 16 con App Router, React 19, Tailwind CSS 4, ECharts 6 y
export estático. Consume la API FastAPI, conserva la clave de licencia solo en
`sessionStorage` y ofrece un motor TypeScript determinista para cálculos FREE
sin conexión.

## Desarrollo

El backend debe estar disponible en `http://127.0.0.1:8000`:

```bash
npm install
npm run dev
```

Abrir http://localhost:3000. En desarrollo, `next.config.ts` reenvía `/api/*`
al backend. Para usar otro destino:

```bash
API_PROXY_URL=http://127.0.0.1:9000 npm run dev
```

## Build y pruebas

```bash
npm run build
npm run test:e2e
```

`npm run test:e2e` genera el export en `.next-e2e`, prepara licencias PAID y
RESEARCH deterministas, levanta una API aislada en `127.0.0.1:8010` y sirve el
frontend con proxy en `127.0.0.1:3100`. La suite contiene 47 pruebas de cálculo,
tratamiento, aislamiento, medición, métodos numéricos, exportación, PWA,
accesibilidad y respuesta móvil. La prueba de catálogo con red caída se ejecuta
con `serviceWorkers: "block"`: `page.route` no intercepta solicitudes atendidas
por un service worker, así que es necesario desactivarlo para simular el fallo
de red y ejercitar el fallback FREE y el reintento.

## Offline/PWA

El Service Worker precachea el shell, los datos FREE y los chunks necesarios.
Con red disponible, los assets usan network-first para no reutilizar chunks
obsoletos de Turbopack. Sin red, la navegación y los assets recurren a la caché
y los cálculos FREE usan `src/lib/offline.ts`.

## Estructura

```text
src/app/          Rutas y providers
src/components/   Formularios, resultados, gráficos y licencia
src/context/      Estado de licencia de sesión
src/lib/          Cliente API, transporte y motor offline
e2e/              Playwright, fixtures y servidores aislados
public/           Manifest, Service Worker y datos offline
```
