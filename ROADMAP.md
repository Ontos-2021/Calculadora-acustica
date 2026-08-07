# Roadmap — Calculadora Acústica Profesional

> **Visión**: Herramienta profesional de diseño acústico arquitectónico, freemium, con arquitectura moderna (API + frontend React/Next.js), capacidad offline (PWA) y soporte normativo ISO + ASTM.

---

## Fase 0 — Consolidación del núcleo actual (ahora)

La base existente funciona, pero tiene ruido técnico que pagará deuda si no se limpia ahora.

### 0.1 Correcciones y edge cases

| Ítem | Problema |
|---|---|
| `combine_modes` recursiva | Reescribir con `itertools.product(0..n, repeat=3)` — más legible y eficiente |
| `log(1-α)` con α = 1 | Millington y Eyring explotan. Añadir `α ≥ 1 → ∞` o `α > 0.99 → modo de amortiguamiento máximo` |
| Sabine sin validación de ᾱ | Sabine miente si ᾱ > 0.2. Añadir advertencia automática |
| Bonello sin evaluación | El criterio exige monotonía estricta. Implementar chequeo booleano: `all(v[i] <= v[i+1] for i ...)` |

### 0.2 Clasificación de modos (FREE)

Clasificar cada modo por tipo y asignar peso energético:

```
Tipo        Índices no nulos    Peso relativo
Axial       1                   0 dB (referencia)
Tangencial  2                   −3 dB
Oblicuo     3                   −6 dB
```

Información adicional a reportar:
- **Modos degenerados**: dos ternas (nx,ny,nz) distintas con la misma frecuencia → duplicación de energía, peor caso de diseño
- **Solapamiento modal**: modo con separación < Δf respecto al anterior (ver 0.3)

### 0.3 Frecuencia de Schroeder y ancho de banda modal (FREE)

```
f_S = 2000 · √(RT60 / V)
Δf = 2.2 / RT60
```

- Reportar f_S al usuario: "por debajo de X Hz los modos individuales importan; por encima el campo es difuso"
- Δf define si dos modos adyacentes se perciben separados o fusionados
- Umbral de campo difuso: solapamiento ≥ 3 modos simultáneos (base del criterio de Schroeder)

### 0.4 RT60 con dependencia frecuencial

**Cambio estructural necesario**. Pasar de:

```
α único  →  RT60 único
```

a:

```
α(125 Hz)  →  RT60(125 Hz)
α(250 Hz)  →  RT60(250 Hz)
...        →  ...
α(4000 Hz) →  RT60(4000 Hz)
```

Esto implica rediseñar el formulario de entrada (6 superficies × 6 bandas = 36 campos). Alternativa más práctica para UI: bandas de octava (125, 250, 500, 1k, 2k, 4k) con posibilidad de expandir a tercios.

### 0.5 Proporciones de sala (FREE)

Comparar L:A:H contra el **área de Bolt** y las proporciones de referencia:

| Proporción (L:A:H) | Referencia |
|---|---|
| 1 : 1.25 : 1.60 | Golden Ratio acústico |
| 1 : 1.14 : 1.39 | Louden (1971) |
| 1 : 1.19 : 1.46 | Sepmeyer |
| 1 : 1.28 : 1.54 | Bonello |

Además: indicar si dos dimensiones son iguales o múltiplos enteros entre sí (→ modos degenerados, la peor situación acústica).

### 0.6 Refactor para API-first

Reestructurar el código para que el módulo de cálculo sea una biblioteca Python independiente:

```
acoustic_core/
├── models/
│   ├── room.py          # Sala, dimensiones, superficies
│   ├── materials.py     # Material con α(f) por banda
│   └── modes.py         # Modo: índices, tipo, frecuencia, peso
├── reverberation/
│   ├── sabine.py
│   ├── eyring.py
│   ├── millington.py
│   └── fitzroy.py
├── resonance/
│   ├── modes.py         # Cálculo de modos
│   └── pressure.py      # Distribución de presión (Fase 2)
├── evaluation/
│   ├── bonello.py
│   └── schroeder.py
└── design/
    ├── ratios.py         # Proporciones óptimas
    └── targets.py        # RT60 objetivo según uso
```

Esto permite: probar unitariamente, servir desde FastAPI, y portar partes a WASM para offline.

---

## Fase 1 — Arquitectura moderna (API + Frontend)

### 1.1 Backend: FastAPI

Migrar de Flask a FastAPI:

- OpenAPI/Swagger automático — documentación y testing gratuito
- Async donde tenga sentido (lectura de BD de materiales, ESS generation)
- Validación Pydantic (elimina el `try/except` manual de entrada)
- Middleware de licencias para el modelo freemium
- Pruebas con pytest + httpx

### 1.2 Frontend: React + Next.js

- Next.js App Router con SSR/SSG según ruta
- PWA via Service Worker + `next-pwa` o Workbox: cachear el core de cálculo en WASM para operación offline
- Componentes modales dinámicos (el formulario de α(f) se expande colapsablemente)
- Gráficos interactivos con D3 o Plotly (zoom en waterfall, selección de modos, click en frecuencia→mapa de presión)

### 1.3 Core WASM para offline

Compilar el módulo `acoustic_core` a WebAssembly (Pyodide o Emscripten) para que la PWA funcione sin servidor en las funcionalidades FREE. Las funcionalidades PAID requieren validación online.

### 1.4 Exportación profesional (PAID)

- **PDF**: informe completo con memoria de cálculo, gráficos, materiales sugeridos y normativa aplicable
- **CSV/JSON**: datos crudos para post-procesamiento
- **Latex/typst**: para usuarios que integran en documentación técnica

### 1.5 API pública

Endpoints versionados (`/api/v1/...`) con rate limiting y tier de acceso según licencia. Documentación interactiva en `/docs`.

---

## Fase 2 — Parámetros acústicos avanzados

El salto cualitativo: de estadística a geométrica. **Core del valor profesional del producto**.

### 2.1 Mapas de presión modal (FREE)

Para cada modo y para el espectro combinado:

```
p(x,y,z) ∝ cos(nx·πx/L) · cos(ny·πy/W) · cos(nz·πz/H)
```

Output:
- **Mapa de planta** (corte a altura de oído, 1.2 m): heatmap 2D de presión acumulada
- **Modos individuales**: seleccionable por frecuencia, muestra nodos (azul) y antinodos (rojo)
- **Posición óptima de escucha**: punto con presión más plana a través del espectro modal

Valor práctico: "tu modo de 47 Hz tiene un nodo justo donde está tu cabeza → mover el listening position 30 cm a la izquierda te da 6 dB más de respuesta en esa frecuencia".

### 2.2 Método de Fuentes Imagen (PAID)

Para sala rectangular, el ISM es exacto y computacionalmente barato:

```
Reflexión de orden k en pared i: fuente espejada con signo según α
```

De la respuesta al impulso reconstruida se extraen:

| Parámetro | Fórmula | Norma |
|---|---|---|
| **C80** | `10·log₁₀(E_0-80ms / E_80ms-∞)` | ISO 3382-1 |
| **C50** | `10·log₁₀(E_0-50ms / E_50ms-∞)` | ISO 3382-1 |
| **D50** | `E_0-50ms / E_total` | ISO 3382-1 |
| **Ts** | `∫t·p²dt / ∫p²dt` | ISO 3382-1 |
| **EDT** | pendiente primeros 10 dB × 6 | ISO 3382-1 |
| **ITDG** | gap entre directo y primera reflexión | (crítico en diseño LEDE) |
| **Flutter echo** | detección de periodicidad en reflexiones tardías | — |

### 2.3 RT60 por bandas con comparación objetivo (FREE)

Para cada banda de octava:

```
RT60_calculado(ƒ) vs. RT60_objetivo(ƒ, uso)
```

Uso seleccionable:

| Uso | RT60 obj @ 500 Hz | Norma |
|---|---|---|
| Sala de conferencias | 0.6 – 0.8 s | DIN 18041 |
| Aula | 0.6 – 0.9 s | DIN 18041 |
| Teatro | 0.8 – 1.2 s | ISO 3382 |
| Sala de conciertos | 1.5 – 2.2 s | ISO 3382 |
| Estudio grabación | 0.2 – 0.4 s | EBU Tech 3276 |
| Home theater | 0.3 – 0.5 s | THX |
| Iglesia | 1.8 – 3.0 s | — |

Visualización: barras lado a lado (actual vs. objetivo) con banda de tolerancia.

---

## Fase 3 — Diseño y tratamiento acústico

De la diagnosis a la prescripción. **El feature que convierte a un profesional en cliente**.

### 3.1 Base de materiales con α(f) (PAID)

- Materiales de fabricante con α por banda de octava (ISO 354 / ASTM C423)
- Clasificación **ISO 11654**: α_w y clase A–E
- Coeficiente de absorción de personas, butacas y audiencia (ISO 3382-1 Anexo A)
- Absorción del aire (relevante > 2 kHz, función de HR y T):
  ```
  m = f² · (1.6e-10 · HR) / (T + 273)
  ```
- α de incidencia normal (para usar en modelos de impedancia de pared)

### 3.2 Diseño inverso (PAID)

Flujo: *dimensiones + α_actual + RT60_objetivo → materiales necesarios*

```
A_requerida(ƒ) = 0.161 · V / RT60_objetivo(ƒ)
A_faltante(ƒ) = A_requerida(ƒ) − A_actual(ƒ)
→ m² de material X necesarios
→ ¿en qué superficie colocarlos? (según mapa de presión modal)
```

### 3.3 Calculadora de absorbentes (PAID)

| Tipo | Fórmula de diseño |
|---|---|
| **Poroso** | `f_min = c / (4·d)`; modelo de Delany-Bazley con resistividad al flujo σ |
| **Helmholtz** | `f₀ = (c/2π)·√(A/(V·L_eff))` — sintonizable |
| **Membrana** | `f₀ = 60 / √(m·d)` — m en kg/m², d en m |

Input: espesor, densidad, perforación, masa → Output: curva α(f) predicha y m² recomendados.

### 3.4 Calculadora de difusores (PAID)

- **QRD**: secuencia de residuos cuadráticos, profundidad según f_diseño
- **Skyline**: variante 2D
- Coeficiente de difusión (ISO 17497-1)

---

## Fase 4 — Aislamiento acústico

La otra mitad de la acústica arquitectónica. Crucial para el profesional: estudios, salas de ensayo, home theaters en edificios.

### 4.1 Pérdida por transmisión (PAID)

- **Ley de masa**: `TL ≈ 20·log₁₀(m·f) − 47` (campo difuso)
- **Frecuencia crítica / coincidencia**: `f_c = c² / (2π · 1.8 · h)` para paneles homogéneos
- **TL real**: por debajo de f_c sigue la ley de masa, en f_c hay un notch (pérdida abrupta de aislamiento)

### 4.2 Sistemas de doble hoja (PAID)

Resonancia masa-resorte-masa:

```
f₀ ≈ 60 · √((m₁+m₂)/(m₁·m₂·d))
```

- Por debajo de f₀ la doble hoja aísla **peor** que una hoja simple de igual masa total
- Tablas de diseño: distancia entre montantes, lana mineral en cavidad, desacople mecánico
- TL real con transmisión por flancos (ISO 12354-1)

### 4.3 Índices globales (PAID)

- **STC** (ASTM E413) / **Rw** (ISO 717-1)
- Conversión entre curvas TL(ƒ) → número único + términos de adaptación (C, C_tr)
- Comparación con requisitos de código (CTE DB-HR, IBC, etc.)

### 4.4 Ruido de fondo y HVAC (PAID)

- Curvas **NC** (ANSI S12.2) y **NR** (ISO 1996)
- Objetivos por uso:
  | Tipo | NC objetivo |
  |---|---|
  | Estudio grabación | NC-15 / NC-20 |
  | Sala de conciertos | NC-15 / NC-20 |
  | Teatro | NC-20 / NC-25 |
  | Oficina ejecutiva | NC-25 / NC-30 |
  | Aula | NC-25 / NC-30 |
  | Restaurante | NC-35 / NC-40 |
- Cálculo de atenuación en conductos rectangulares

---

## Fase 5 — Medición y validación

Cerrar el bucle: lo predicho vs. lo medido. **Rasgo diferenciador frente a otras calculadoras**.

### 5.1 Generación de señal ESS (PAID)

Barrido sinusoidal exponencial (Farina, 2000):

```
x(t) = sin(2π · f₁ · L · (e^(t/L) − 1)),  L = T / ln(f₂/f₁)
```

Ventajas:
- Permite separar respuesta lineal de distorsión armónica
- Alta relación señal/ruido
- Barrido reproducible para toda la plataforma

### 5.2 Importación de respuesta al impulso (PAID)

- Carga de archivos WAV (RIFF estándar + floating point)
- Deconvolución de ESS → respuesta al impulso
- Filtrado por bandas de octava/tercio (Butterworth 4to orden)

### 5.3 Integración inversa de Schroeder (PAID)

```
E(t) = ∫_t^∞ p²(τ) dτ  →  decay curve en dB
RT60 = pendiente · 6, con regresión lineal sobre intervalo −5 a −25 dB (T20)
```

- EDT (primeros 10 dB)
- T20, T30 (ISO 3382-1)
- Curva de decaimiento con indicador de no-linealidad

### 5.4 Waterfall / Espectrograma (PAID)

- **Waterfall** (decaimiento espectral 3D): identificación de modos que "cuelgan" más que el RT60 promedio
- **Espectrograma**: evolución temporal del contenido frecuencial
- Detección de modos con Q anómalo (absorbentes mal colocados o ausentes)

### 5.5 Calibración del modelo (PAID, avanzado)

```
α_calibrado(ƒ) = α_libro(ƒ) + Δ(ƒ)  ← de minimizar error: |RT60_medido − RT60_modelo|
```

- Actualización de la base de materiales con los coeficientes reales de la sala
- Refinamiento iterativo: medir → ajustar α → predecir → medir de nuevo

---

## Fase 6 — Métodos numéricos (investigación)

El techo técnico. Justificado solo si la demanda profesional lo sostiene.

### 6.1 Modos con impedancia de pared finita

Los modos reales se desplazan y amortiguan respecto al modelo de pared rígida:

```
tan(kz·L) = (j·Z_wall·kz) / (ρ·c)
```

Implementación 1D (axial) primero, validación contra fórmulas cerradas.

### 6.2 FEM 2D para secciones no rectangulares

- Techos inclinados, plantas en L o trapezoidales
- Elementos finitos 2D en plano de planta para modos horizontales
- Acoplamiento con modos verticales analíticos

### 6.3 Ray tracing / Cone tracing

Para salas de geometría arbitraria en campo difuso (f > f_S):

- Algoritmo de ray tracing con detección de intersección SAS/SAH
- Estadísticas de reflexiones, energía por superficie, listener
- Validación contra ISM para sala rectangular (debe coincidir)

### 6.4 Modelo híbrido

- Por debajo de f_S: FEM o ISM (según geometría)
- Por encima de f_S: ray tracing
- Transición suave con ventana de solapamiento

Estado del arte académico. Correspondería a una publicación científica.

---

## Modelo freemium — Mapa de licencias

| Fase | Funcionalidad | FREE | PAID |
|---|---|---|---|
| Fase 0 | RT60 (4 fórmulas, single-number) | ✓ | |
| Fase 0 | Modos de resonancia | ✓ | |
| Fase 0 | Clasificación axial/tangencial/oblicuo | ✓ | |
| Fase 0 | Modos degenerados + solapamiento | ✓ | |
| Fase 0 | Frecuencia de Schroeder | ✓ | |
| Fase 0 | Proporciones óptimas de sala | ✓ | |
| Fase 0 | Bonello automático | ✓ | |
| Fase 2 | RT60 por bandas + comparación objetivo | ✓ | |
| Fase 2 | Mapas de presión modal | ✓ | |
| — | **Todo lo anterior, offline (WASM)** | ✓ | |
| Fase 2 | ISM → Respuesta al impulso | | ✓ |
| Fase 2 | C80, C50, D50, Ts, EDT | | ✓ |
| Fase 2 | ITDG + flutter echo | | ✓ |
| Fase 3 | Base de materiales α(f) | | ✓ |
| Fase 3 | Diseño inverso (target RT60) | | ✓ |
| Fase 3 | Calculadora de absorbentes | | ✓ |
| Fase 3 | Calculadora de difusores | | ✓ |
| Fase 4 | Aislamiento (TL, STC, Rw) | | ✓ |
| Fase 4 | Ruido de fondo NC/NR | | ✓ |
| Fase 5 | ESS + medición + calibración | | ✓ |
| Fase 6 | FEM / ray tracing / híbrido | | ✓ |
| — | Exportación PDF profesional | | ✓ |
| — | API con rate limiting elevado | | ✓ |

---

## Arquitectura técnica resumida

```
┌─────────────────────────────────────────────────┐
│                   Frontend (Next.js)             │
│  ┌───────────────────────────────────────────┐   │
│  │  PWA Service Worker                       │   │
│  │  ├── Core WASM (cálculos FREE offline)    │   │
│  │  ├── Cache de BD de materiales            │   │
│  │  └── Queue de exportaciones               │   │
│  └───────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────┐   │
│  │  Componentes                              │   │
│  │  ├── Formulario sala (dimensiones + α(f)) │   │
│  │  ├── Mapa de presión (canvas/WebGL)       │   │
│  │  ├── Gráficos (Plotly/D3)                 │   │
│  │  └── Informe PDF (jsPDF / react-pdf)      │   │
│  └───────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────┐
│              Backend (FastAPI)                    │
│  ┌───────────────────────────────────────────┐   │
│  │  acoustic_core (biblioteca Python)        │   │
│  │  ├── room / materials / modes             │   │
│  │  ├── reverberation / resonance            │   │
│  │  ├── evaluation / design                  │   │
│  │  ├── isolation / measurement              │   │
│  │  └── fem / raytracing                     │   │
│  └───────────────────────────────────────────┘   │
│  ┌───────────────────────────────────────────┐   │
│  │  Capa de servicio                         │   │
│  │  ├── Auth + licencias                     │   │
│  │  ├── Rate limiting                        │   │
│  │  ├── Background tasks (ESS, PDF)          │   │
│  │  └── API versionada v1/v2                 │   │
│  └───────────────────────────────────────────┘   │
└──────────────────────────────────────────────────┘
```

---

## Notas técnicas importantes

### Precisión numérica (acústica)

- El JND (diferencia apenas perceptible) del RT60 es ~5%. **Reportar con 0.1 s de precisión, no 0.1 ms** como ahora.
- La incertidumbre de los α tabulados es ~±20% entre laboratorios (ISO 354 round robin). Las predicciones deben reportar intervalos de confianza, no puntos exactos.
- La velocidad del sonido c depende de T y HR: `c = 331.3 · √(1 + T/273.15)`. Permitir ajuste.

### Portabilidad WASM

- El módulo `acoustic_core` debe escribirse evitando dependencias nativas (numpy puede ser problemático en WASM). Considerar:
  - Core en Rust con bindings Python (via PyO3) + WASM (via wasm-pack)
  - O mantener Python puro con stdlib math y usar Pyodide en frontend

### Normativa — prioridad de implementación

| Norma | Contenido | Prioridad |
|---|---|---|
| ISO 3382-1 | Medición RT60, C80, EDT | Alta (Fase 2) |
| ISO 354 | Medición α en cámara reverberante | Alta (Fase 3) |
| ISO 11654 | Clasificación absorbentes (α_w) | Alta (Fase 3) |
| DIN 18041 | RT60 objetivo según uso | Alta (Fase 2) |
| ASTM E90 / C423 | TL y α (sistema americano) | Alta (Fase 3) |
| ISO 12354 | Transmisión por flancos | Media (Fase 4) |
| ISO 717-1 | Rw, C, C_tr | Media (Fase 4) |
| ANSI S12.2 | Curvas NC | Media (Fase 4) |
| ISO 17497-1 | Coeficiente de difusión | Baja (Fase 3) |
| EBU Tech 3276 | RT60 para broadcast | Media (Fase 2) |

---

*Este roadmap es vivo. Cada fase debe validarse con usuarios profesionales antes de pasar a la siguiente.*
