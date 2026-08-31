# 00 — Roadmap del proyecto

> **Audiencia**: una IA (o persona) que retome este proyecto sin haber
> participado en las conversaciones previas. Este documento describe QUÉ se
> construye, EN QUÉ ORDEN y POR QUÉ ese orden. Para *cómo* está construido,
> ver `01_ARCHITECTURE.md`. Para el estado actual, ver `02_STATE_OF_PLAY.md`.

---

## 0. Contexto del problema

**Reto**: "La Historia de un Entrenador a través de los Datos". Dado un conjunto
de eventos de múltiples partidos bajo un mismo entrenador, construir —
únicamente a partir de los datos — una narrativa que permita entender cómo juega
ese equipo y qué ideas tácticas lo definen.

**Datos**: 8 temporadas de eventos Hudl StatsBomb + StatsBomb 360 de Liga MX
(Apertura 2021 – Clausura 2025). El archivo de trabajo actual
(`eventos_completos_america.csv`) contiene los eventos de 175 partidos del Club
América, incluyendo los eventos de sus 17 rivales.

**Tensión no resuelta en el enunciado**: el reto pide análisis táctico pero la
rúbrica de evaluación pesa 65% en criterios de negocio (valor de una IP, ROI,
activación de marca, escalabilidad). El proyecto está diseñado para servir a
ambas lecturas: el motor analítico *es* la IP, y el análisis táctico es su
sustento. **Confirmar con los organizadores antes de la entrega final.**

---

## 1. Principio rector

> **El DT no es un agente que se simula. Es un parámetro latente que se estima.**

Modelar al entrenador como agente exigiría dotarlo de objetivos, percepción y
política — eso es aprendizaje por refuerzo multiagente y no se puede validar con
datos de eventos. En cambio, si el estilo del DT se define como un **vector de
parámetros θ que gobierna un proceso estocástico observable**, todo el aparato
de inferencia estadística clásica aplica directamente y con rigor.

En concreto: θ = la matriz de transición de una cadena de Markov absorbente
sobre el campo, estimada por máxima verosimilitud con encogimiento.

---

## 2. Regla de secuenciación

Las fases están ordenadas por **dependencia** y por **razón riesgo/beneficio**,
no por atractivo técnico. La regla es:

> Nada avanza a la fase N+1 mientras la fase N no tenga sus diagnósticos en
> verde y sus supuestos escritos.

Motivo: cada fase hereda los sesgos de la anterior. Un error en la definición de
posesión (Fase 0) contamina el xT (Fase 2), la huella táctica (Fase 3) y el
simulador (Fase 7) sin dejar rastro visible.

---

## 3. NÚCLEO — Cadena de Markov absorbente (Fases 0–3)

**Este es el proyecto.** Todo lo demás es extensión. Si solo se completan las
fases 0–3 con rigor, ya existe un entregable competitivo y defendible.

### Fase 0 — Ingesta y construcción del espacio de estados
**Estado: implementada** (`possessions.py`, `ingest.py`, `grid.py`)

Objetivo: convertir un volcado plano de eventos en una tabla de transiciones
`(poss_uid, from_state, to_state, phase, score_state)`.

Decisiones que hay que documentar explícitamente:

| decisión | valor actual | dónde se configura |
|---|---|---|
| partición del campo | 5×4 zonas | `config.pitch.nx/ny` |
| fases | open / transition / restart / set_piece | `config.phase_order` + `config.phases` |
| acciones que mueven el balón | Pass, Carry, Shot | `config.possession.moving_types` |
| filtro de acarreos | ≥ 5 m | `config.possession.min_carry_length` |
| estados absorbentes | GOAL, SHOT_NOGOAL, LOSS, OUT | `grid.ABSORBING` |

Criterios de salida (todos deben cumplirse):
- `coordinate_sanity.corr > 0.5` — las coordenadas están en el marco de ataque
  correcto y P(gol) crece hacia la portería rival.
- Toda posesión termina en un estado absorbente (hay un test para esto).
- Las proporciones por fase son plausibles (`set_piece` no debe exceder ~20%).

### Fase 1 — Estimación con encogimiento
**Estado: implementada** (`estimate.py`)

Objetivo: obtener `P̂*` estable incluso en renglones ralos, con λ elegido por
validación cruzada por bloques de posesión.

Criterios de salida:
- `frac_below_min < 0.30` para **la unidad de análisis más pequeña** que se
  vaya a usar (una era de DT, no el agregado del club).
- λ\* es un óptimo **interior** de `estimation.lambda_grid`. Si toca cualquier
  extremo, el pipeline avisa y hay que investigar antes de seguir.
- La curva error-vs-N (`figures/error_vs_n.png`) muestra que el error se
  estabiliza con los datos disponibles.

### Fase 2 — Cadena absorbente
**Estado: implementada** (`absorbing.py`)

Objetivo: `N = (I−Q)⁻¹`, `B = NR`, xT propio, distribución de visitas ν.

Criterios de salida:
- `ρ(Q) < 1` verificado numéricamente (el pipeline aborta si falla).
- Las filas de `B` suman 1.
- El mapa de xT es monótono creciente hacia la portería rival (sanidad).

### Fase 3 — Inferencia con control de error
**Estado: implementada** (`inference.py`)

Objetivo: determinar en qué estados el DT se separa de la referencia, con
control de error tipo I.

Cuatro correcciones implementadas, todas necesarias:
1. Bootstrap por **posesión**, no por evento (dependencia intra-posesión).
2. Se bootstrapea la **diferencia**, no dos intervalos separados.
3. La nula del LRT `G²` se **calibra por bootstrap**, no se asume χ².
4. Multiplicidad controlada con Benjamini–Hochberg.

Criterios de salida:
- El IC de la diferencia contiene su propio estimador puntual (hay test).
- El experimento de recuperación de parámetros sobre datos sintéticos detecta
  un sesgo inyectado y no lo detecta en un placebo.

---

## 4. EXTENSIONES (Fases 4–9)

Ordenadas por relación valor/esfuerzo. **Ninguna debe empezarse antes de que
las fases 0–3 tengan sus criterios de salida en verde.**

### Fase 4 — Estratificación por contexto
**Prioridad: ALTA. Es el hallazgo más vendible.**
**Estado: parcialmente implementada** (`inference.context_contrast`)

Comparar `P(·|ganando)` vs `P(·|empatando)` vs `P(·|perdiendo)` en distancia de
variación total.

Interpretación:
- Distancias grandes ⇒ el "estilo" es **reactivo** al marcador.
- Distancias pequeñas ⇒ evidencia de **filosofía impuesta**.

Este contraste separa una idea de juego real de un artefacto del resultado, y
casi ningún competidor lo hará. Falta: intervalos de confianza sobre las
distancias TV (bootstrap por posesión, mismo mecanismo que la Fase 3).

**Advertencia de tamaño de muestra**: estratificar por marcador divide la
muestra en tres. Verificar `frac_below_min` en el estrato más pequeño
(típicamente "perdiendo").

### Fase 5 — Fase defensiva: proceso de Poisson espacial
**Prioridad: ALTA. Es la mitad del juego que hoy falta.**
**Estado: NO implementada.**

El modelo actual solo describe qué hace el equipo **con** el balón. La firma
defensiva de un entrenador es igual de identificatoria.

Modelo: acciones defensivas (presiones, duelos, intercepciones, faltas) como un
**proceso de Poisson no homogéneo** sobre el campo con intensidad λ(x,y):

```
N(A) ~ Poisson( ∫_A λ(x,y) dx dy )
```

Discretizando en celdas, la verosimilitud es exactamente la de una **regresión
Poisson** con offset igual al tiempo de exposición sin balón:

```
log λ_k = β₀ + β₁x_k + β₂y_k + ... + log T_k
```

La superficie `λ̂(x,y)` **es** el mapa de presión del DT. Compararla contra la
referencia es otro LRT.

**Ventaja de partida**: StatsBomb ya provee un evento `Pressure` (jugadores
dentro de ~4–5 yardas del portador), así que no hay que inventar la definición.

**El detalle que casi nadie hará — corrección por adelgazamiento**: los datos
360 solo capturan jugadores dentro del área visible del frame, y cada frame trae
su polígono `visible_area`. Lo observado es un **thinning** del proceso real:

```
λ_obs(x,y) = π(x,y) · λ_real(x,y)
```

donde π(x,y) = P(la zona es visible). Por la propiedad de adelgazamiento el
proceso observado sigue siendo Poisson; π se estima empíricamente (fracción de
frames cuyo polígono contiene el punto) y se corrige dividiendo — un estimador
tipo Horvitz–Thompson. Esto es teoría de procesos puntuales aplicada a un sesgo
real de medición.

Sub-tarea relacionada: **tiempo hasta recuperación** como problema de **riesgos
competitivos** (recuperación activa vs concesión). Un DT de contrapresión tiene
hazard alto en los primeros 5 segundos. Es PPDA con un modelo probabilístico
detrás en vez de un cociente ad hoc.

### Fase 6 — Semi-Markov: duraciones
**Prioridad: MEDIA. Es una corrección de supuesto, no una función nueva.**
**Estado: NO implementada.**

La literatura reciente muestra que **el supuesto de tiempos de permanencia
exponenciales es empíricamente inválido** para secuencias de eventos de fútbol:
la propiedad de Markov parece sostenerse para las *transiciones de estado*, pero
las *distribuciones de duración* se desvían sustancialmente de la exponencial
(colas pesadas a la derecha).

Consecuencia práctica — y es buena noticia: **la cadena embebida ya construida
es válida**. Lo que falta es separar el kernel:

```
Q_ij(t) = p_ij · F_ij(t)
          ↑        ↑
   cadena embebida  distribución de duración
```

`p_ij` ya está estimada (Fase 1). `F_ij` se ajusta por separado con una familia
flexible (log-normal, Weibull, gamma) eligiendo por bondad de ajuste con
**Kolmogorov–Smirnov y QQ-plots**.

Resultado interpretable directo: si la duración media por transición del DT es
sistemáticamente menor que la referencia, eso *es* "juego directo" medido, no
adjetivado.

La columna `duration` ya se conserva en la ingesta para esto.

### Fase 7 — Simulación y contrafactuales
**Prioridad: MEDIA-ALTA. Es el diferenciador competitivo.**
**Estado: NO implementada.**

Con `P̂*` ya se puede simular posesiones completas por Monte Carlo y generar
contrafactuales:

> "¿Qué pasa con el xG esperado de este DT si enfrenta un rival que presiona
> alto?" → se modifica el kernel del rival, se simulan 50,000 posesiones, se
> comparan.

**Dos técnicas de reducción de varianza que hay que implementar y reportar:**

1. **Números pseudoaleatorios comunes (CRN)**: al comparar dos entrenadores o
   dos escenarios, usar las mismas semillas. La varianza de la *diferencia* se
   colapsa y se detectan efectos pequeños con muchas menos réplicas.
2. **Importance sampling**: los goles son raros (~1 por cada 150 posesiones).
   Simular bajo un kernel inclinado hacia zonas de progresión y corregir con el
   cociente de verosimilitudes reduce la varianza dramáticamente.

**Antes de confiar en cualquier contrafactual: validar el simulador.** Comparar
la *distribución* simulada de longitud de posesión, duración y zona de
finalización contra la empírica, con **KS y QQ-plots**. Si la cadena reproduce
las distribuciones reales, todo lo construido encima es creíble. Si no, el
diagnóstico típico es que Markov de primer orden es demasiado pobre y hay que
ampliar el estado (zona anterior, o fase de juego).

### Fase 8 — Métrica de encaje: distancia de Wasserstein
**Prioridad: MEDIA. Es el puente al caso de negocio.**
**Estado: NO implementada.**

El estilo es una **medida de probabilidad** (la distribución de visitas ν, ya
calculada en la Fase 2). El encaje entre un DT y un club objetivo es una
**distancia entre medidas**:

```
d(DT, club) = W₁(ν_DT, ν_club)
```

`W₁` es exactamente el **problema de transporte / flujo a costo mínimo**, es
decir un programa lineal resoluble con `scipy.optimize.linprog`.

Especificación necesaria (sin esto la distancia no está bien definida):
- **Sobre qué**: la distribución de visitas ν sobre estados. Para comparar
  kernels completos, `W₁` renglón por renglón promediando con peso ν_i.
- **Métrica base**: distancia euclidiana en metros entre centroides de zona
  (`StateSpace.zone_centroids()` ya la provee). Esto da unidades físicamente
  interpretables: "hay que mover la masa de probabilidad, en promedio, 8.3
  metros de cancha para convertir un estilo en el otro".

**Bono**: el **dual de Kantorovich** devuelve un potencial φ_i por zona; las
zonas con |φ_i| grande son las que explican el desencaje. La solución dual no
es un tecnicismo: es la interpretación táctica del número.

Ventajas sobre un score ponderado ad hoc: es una métrica de verdad, es
descomponible, y como hay posterior de P̂ se obtiene una **distribución** de la
distancia, no un número puntual. De ahí sale una probabilidad de encaje honesta:
`P(d < τ)`.

### Fase 9 — Caso de negocio
**Prioridad: ALTA para la rúbrica (65%). Baja dependencia técnica.**
**Estado: NO implementada.**

- **El dolor**: la rotación de entrenadores en Liga MX. **No inventar cifras**:
  contar los cambios de DT reales en las 8 temporadas *desde los propios datos*
  (el CSV de eras ya construido es esa cuenta). Un número extraído del propio
  periodo de análisis es un argumento mucho más fuerte que citar un reporte.
- **ROI**: si el motor evita un mal fichaje de DT cada tres años, el ahorro es
  un múltiplo del costo de la licencia. Presentar con tres escenarios
  (conservador / base / optimista) y tabla de sensibilidad al parámetro clave —
  la rúbrica pide explícitamente "escenarios múltiples y sensibilidad
  financiera".
- **Comparativo contra alternativas** (lo pide la rúbrica): contra el status quo
  de scouting por video y reputación. El argumento es que ambos están sesgados
  hacia resultados recientes y no separan estilo de contexto; este método sí, y
  lo demuestra con el análisis de `P(·|c)` de la Fase 4.
- **Escalabilidad**: el pipeline es agnóstico a la liga. Cualquier competencia
  con cobertura StatsBomb entra sin cambiar código. Costo marginal ≈ licencia de
  datos.

---

## 5. IDEAS EXPLORATORIAS (sin compromiso)

Estas no están en la ruta crítica. Se listan porque surgieron en la discusión y
podrían aportar, pero cada una necesita justificación antes de invertir tiempo.

### 5.1 Definición propia de contraataque
`From Counter` de StatsBomb es muy restrictivo (0.6% de los eventos en los datos
actuales), lo que deja la fase `transition` con poca masa. Si el contraataque va
a ser parte de la narrativa del DT, conviene una definición operativa propia:

> posesión que arranca con recuperación en campo propio y alcanza el último
> tercio en menos de N segundos con menos de M pases.

Se construye sobre `transitions.parquet` sin tocar nada anterior. Requiere
calibrar N y M y **reportar sensibilidad a esa elección**.

### 5.2 Clustering de posesiones (tipologías de ataque)
En vez de imponer las fases del config, **descubrirlas**: representar cada
posesión por un vector de características (zona de inicio, zonas visitadas,
duración, número de acciones, progresión vertical/lateral, resultado) y
agrupar. El perfil de un DT sería entonces su distribución sobre tipologías.

Ventaja: quita el sesgo de que `play_pattern` describe el origen y no el
desarrollo.
Riesgo: los clusters no supervisados suelen ser difíciles de nombrar
tácticamente, y un cluster sin nombre no es una idea vendible. **Exigir que cada
cluster tenga una descripción en lenguaje de entrenador antes de usarlo.**

### 5.3 Balón parado como modelo aparte
Córners y tiros libres tienen una estructura tan distinta del juego abierto que
mezclarlos en la misma cadena es discutible aunque estén separados por fase. Un
modelo específico (distribución de zonas de remate, primer contacto, segunda
jugada) sería más informativo. **Bajo la fase actual ya están aislados**, así que
esto es refinamiento, no corrección.

### 5.4 Posesiones largas y control del ritmo
Analizar la distribución de longitud de posesión por DT (no solo su media).
Un equipo con muchas posesiones cortas *y* muchas muy largas es distinto de uno
con todas medianas, aunque coincidan en promedio. Se conecta con la Fase 6.

### 5.5 Malla adaptativa
La malla uniforme desperdicia resolución en zonas donde pasa poco y la escatima
donde pasa mucho. Una partición basada en densidad de eventos (o en un árbol
cuaternario) daría más renglones informativos con el mismo presupuesto de
parámetros. **No hacerlo antes de justificarlo con la curva error-vs-N.**

### 5.6 Métricas de red de pases
Centralidad, densidad, agrupamiento de la red de pases, como *features*
descriptivas. Baratas e interpretables. **Explícitamente NO se recomienda GNN**:
ver `02_STATE_OF_PLAY.md` §"Decisiones cerradas".

---

## 6. Orden de ejecución recomendado

```
[HECHO]   Fase 0 → Fase 1 → Fase 2 → Fase 3
          ↓
[AHORA]   Mapeo de eras de DT (requiere fechas de partido)
          ↓
[SIGUE]   Fase 4 (contexto) ─── es el hallazgo más vendible
          ↓
          Fase 9 (negocio) ──── 65% de la rúbrica, poca dependencia técnica
          ↓
          Fase 5 (defensa) ──── completa la mitad faltante del juego
          ↓
          Fase 7 (simulación) ─ diferenciador competitivo
          ↓
          Fase 8 (Wasserstein) ─ puente al caso de negocio
          ↓
          Fase 6 (semi-Markov) ─ refinamiento de supuesto
          ↓
[OPCIONAL] Ideas exploratorias §5
```

**Ruta mínima viable si el tiempo aprieta**: Fases 0–4 + 9. Con eso hay un
proyecto completo, honesto y competitivo.

---

## 7. Regla de oro

> Nada entra a la presentación si no se puede enunciar el supuesto que lo hace
> válido y el dato que lo respalda.

Un modelo simple bien justificado gana a un modelo sofisticado sin validar. Los
jueces técnicos preguntan por los supuestos; los jueces de negocio preguntan por
las consecuencias. Ambos castigan la caja negra.
