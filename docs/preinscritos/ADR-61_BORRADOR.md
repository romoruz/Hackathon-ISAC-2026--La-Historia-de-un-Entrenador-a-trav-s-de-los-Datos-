# ADR-61 · Progresión, dónde vive una posesión viva y por qué no simulamos

> **Borrador v2, 2026-09-21.** Se escribe y se commitea **sola, antes del
> código** de F3 (paquete h2_35). La v1 no se commiteó. Cambios frente a ella:
> §0 registra el diagnóstico de fase ya corrido; §1 y §3 pasan de la cadena
> de zonas sumada a los bloques por fase; P2 declara que está informada por
> ADR-53; P4 publica sus cinco puntos; la franja va al JSON como constante.
>
> **Declaración de contaminación.** Ya se vio todo lo de ADR-53 a ADR-60: E[T]
> contra la liga (`did_h4_v1`), field tilt, pases progresivos, npxG y OBV
> (`metricas_v1`), las zonas de la era principal (mapa de 2.1), T y el placebo
> (`relevos_v1`, `placebo_v1`) y el rechazo del ajuste de longitudes de
> ADR-21 (KS ≈ 0.09 en el América). **No se ha calculado ninguna probabilidad
> de llegada, ningún tiempo de primer paso, ninguna distribución
> cuasi-estacionaria y ninguna curva de supervivencia por torneo.** Las
> predicciones de §7 se escriben sin esos números.

## 0. Diagnóstico estructural, con su regla fijada aquí

La fase de un estado sale de `play_pattern`, que etiqueta la posesión
**completa** por cómo empezó (`config/default.yaml`, `phases`). Por eso una
posesión nunca cambia de fase y Q es diagonal por bloques (cuatro bloques de
20 zonas, uno por fase). Los transitorios **no** se comunican entre sí, y la
frase del acto 1 (1.2) que dice lo contrario es falsa desde h2_31.

**Visto antes de escribir esta versión** (2026-09-21, un solo club):
`data/processed_api_tijuana/transitions.parquet` tiene 168 456 transiciones
entre transitorios y **ninguna** cambia de fase (0.000%). Por fase:
abierto 90 711, reinicio 44 019, balón parado 27 406, transición 6 320. No se
calculó nada más.

**Qué no cambia:** N, E[T], B y todo lo de ADR-53 a ADR-60. El álgebra de
una cadena absorbente no necesita que los transitorios se comuniquen. Lo
único que el bloque rompe es la frase de 1.2 y la definición de la
cuasi-estacionaria (§3).

- **D61-0.** El script mide la fracción *f* de transiciones entre
  transitorios con `from_state % 4 ≠ to_state % 4`, sobre toda la liga.
- **Si f < 0.01** (lo esperado tras el diagnóstico de Tijuana)**:** la frase de 1.2 se reescribe así: "Una posesión conserva la
  fase con la que empezó. Por eso la cadena se parte en cuatro bloques que no
  se comunican; dentro de cada bloque, las zonas sí". La cita *f* va con su
  fuente. Es una corrección y se registra en el catálogo de errores del
  anexo, con la fecha en que entró la frase (h2_31) y la de la corrección.
- **Si f ≥ 0.01** en la liga completa (contradiría a Tijuana)**:** el script
  aborta. Eso significa que algún club construye la fase de otra forma, y hay
  que entenderlo antes de seguir.



## 1. Tres cadenas y para qué sirve cada una

| cadena | estados | se usa en |
|---|---|---|
| **completa** | 80 transitorios (zona × fase) + 4 absorbentes | progresión (§2) y supervivencia (§4) |
| **bloque por fase** | los 20 transitorios de una sola fase (Q_φ, submatriz de Q) | cuasi-estacionaria (§3) |
| **completa con franja absorbente** | las zonas de la franja del área se vuelven un quinto absorbente | progresión (§2) |

Todas las magnitudes se calculan con λ = 0 (ADR-22). Las acciones son las
propias del club, con `coach` no nulo, igual que en 42. El torneo sale de
`torneo_cols` de `25_pares_h4.py`.

## 2. Progresión (sección 2.2) · nivel A

**Franja del área:** las zonas con `ix = zona // 4 = 4`, es decir, la última de
las cinco columnas de la malla (de 96 a 120 en la escala del proveedor, que mide
120 × 80; el área grande empieza en 102, así que la franja la contiene
completa y un poco más). Va al JSON como constante `franja_ix = 4` con esta
justificación en texto, y la página la dibuja en la cancha del plegable. El último tercio no coincide con
ninguna frontera de la malla 5 × 4. Por eso el título de 2.2 cambia de
"último tercio" a "franja del área". La sensibilidad con `ix ≥ 3` se publica
como nivel C y no entra a la familia.

**Unidad:** la era principal de cada historia (adenda 2 de ADR-59 §2): las
cinco eras.

**Estimandos**, sobre las posesiones de la era que **empiezan fuera** de la
franja, con α′ su distribución inicial renormalizada:

- **L** = P(llegar a la franja antes de que la posesión termine) = α′ h, con
  h = (I − Q_oo)⁻¹ Q_of 1. Aquí *o* son los estados fuera de la franja y *f* los
  de la franja. Un remate o un gol desde fuera de la franja cuenta como "no
  llegó".
- **τ** = E[acciones hasta llegar | llega] = (α′ N_oo h) / (α′ h), con
  N_oo = (I − Q_oo)⁻¹.

**Comparación**, igual que ADR-53: D_L = log L(P̂_era, α′_era) − log
L(P̂_base, α′_era), y lo mismo para τ. La base es la liga sin el club, en los
torneos de la era y ponderada a su mezcla, con la misma construcción de base
(y el mismo mínimo por torneo) que `25_pares_h4.py`. **Se usa el α′ de la
era en los dos términos**, para que la diferencia no venga de dónde empiezan
las posesiones.

**Inferencia:**

- Bootstrap **por partido**, estratificado por torneo, con B = 4000. Se
  remuestrean la era y la base. Las posesiones de un mismo partido no son
  independientes, y ADR-60 ya remuestreó por partido. 2.1 (ADR-53) remuestrea
  por posesión; la diferencia se declara en el plegable.
- Intervalo basic en escala log; p por inversión del intervalo.
- **Familia F61:** cinco eras × {D_L, D_τ} = **10 contrastes**, BH al 5%.
- Réplicas no finitas (una réplica sin llegadas): se descartan y se cuentan.
  Si pasan de 1% de B en una era, esa era es **no evaluable** para ese
  estimando y sale de la familia. El tamaño de la familia se ajusta y se
  declara.

**Redacción** con las plantillas de la adenda 2 §3: "difiere", o "no
detectamos una diferencia mayor a X" con X el extremo del intervalo más lejano
al cero, en puntos porcentuales relativos.

**Capa 3 (en un partido): una jugada real, elegida por regla.** De las
posesiones de la era principal que empiezan fuera de la franja y llegan a
ella, se toma la que tarda en llegar un número de acciones igual a round(τ̂_era).
Si hay varias, la más antigua por (`match_date`, `poss_uid`). Si ninguna tarda
exactamente eso, la más cercana y, en empate, la más corta. Se dibuja su
recorrido de zonas y lleva el rótulo "una posesión real, elegida por regla, no
por ser vistosa". Sin nivel propio.

## 3. Dónde vive una posesión viva (1.6 y 2.1) · nivel C

Como Q es diagonal por bloques (§0), sumar las cuatro fases en una sola
cadena de zonas mezclaría cuatro dinámicas que nunca se tocan. Se trabaja por
bloque:

- **Bloque principal: juego abierto** (`open`, índice 0 de `phase_order`),
  el que tiene más transiciones. La pregunta "dónde vive una posesión viva"
  se contesta sobre él. Se dice así en la página: "en juego abierto".
- **λ₁ de cada uno de los cuatro bloques**, para la liga: el bloque con el
  λ₁ más grande es donde se concentra, a la larga, la cuasi-estacionaria de
  la cadena completa. Nivel C, una línea en 1.6.
- **Cuasi-estacionaria π** del bloque de juego abierto: vector propio izquierdo de Q_open con valor propio
  λ₁, el de mayor módulo (Perron–Frobenius), normalizado a suma 1. Se calcula
  con eigen y se verifica por iteración de potencias, μₙ₊₁ = μₙ Q_open / ‖μₙ Q_open‖₁,
  desde el α de las posesiones de juego abierto. Si las dos difieren en más de 1e-6 (norma 1), aborta.
- **Guarda:** Q_open tiene que ser irreducible (las 20 zonas alcanzables entre
  sí). Si no lo es, esa unidad queda como "no evaluable" y se declara; no se
  calcula π sobre una clase parcial.
- **1/(1 − λ₁)**: cuántas acciones le quedan, en promedio, a una posesión de
  juego abierto que ya duró mucho. Se publica junto a E[T] con una advertencia: miden cosas
  distintas.

**Acto 1 (1.6), pedagógico:** π del bloque de juego abierto de la liga del torneo con más posesiones
(regla mecánica), más la animación μ₀ = α, μ₁, … sobre la cancha hasta que la
distancia a π baje de 0.01. Es un solo mapa: no se comparan torneos.

**2.1, por historia:** π del bloque de juego abierto de la era principal y de la base, en dos canchas del
mismo tamaño con escala compartida (reglas 3 y 4 de 15_REPORTE_HTML), más
1/(1 − λ₁) de la era y de la base. Nivel C, sin contraste ni intervalo: la
frase es descriptiva ("dónde se concentra"). No se usa ni la palabra
"significativo" ni "diferencia".

## 4. Por qué no simulamos (1.7) · nivel C

La deriva del proveedor cambia la longitud de las posesiones entre torneos, y
mezclar torneos con longitudes distintas **infla la dispersión por sí solo**.
Por eso la comparación se hace **torneo por torneo**:

- **Observada:** S_t(k) = P(L > k) sobre las posesiones de la liga en el
  torneo t (todos los clubes, acciones propias).
- **Modelo:** la curva que implica la cadena **completa** del torneo t (con sus
  cuatro bloques: la mezcla de fases es legítima, porque es la de los datos),
  S_t(k) = α_t Q_tᵏ 1, **condicionada a L ≥ 2** porque `min_actions = 2`
  descarta las posesiones de una acción.
- **Se publica:** las dos curvas del torneo con más posesiones (la misma regla
  que en §3); en cuántos torneos la observada queda por encima de la del
  modelo en k = 12 y por debajo en k = 5; y el KS de cada torneo, sin p.
- La figura sustituye al hueco de 1.7. El texto de 1.7 no cambia de tesis:
  la cadena no reproduce las longitudes, así que no se simula.

## 5. Qué queda fuera de ADR-61

- Entropía por fila de Q y Jensen–Shannon entre torneos (2.5). No entran:
  2.5 ya tiene su serie y sumarlas es más superficie sin pregunta nueva. Si
  hay tiempo, van en una adenda.
- La calculadora de la cadena y la centralidad de zonas (PageRank sobre Q).
- Progresión por pareja o por relevo. ADR-61 describe la era principal;
  el acto 3 sigue con ADR-60.
- Cualquier tiempo en segundos (el proveedor no lo da de forma fiable, ver
  límites).

## 6. Reglas preinscritas (van al JSON como `reglas_preinscritas`)

- **D61-0:** diagnóstico de fase y su regla (§0); si f ≥ 0.01, aborta.
- **D61-1:** franja del área = `ix = 4`; α′ solo con posesiones que empiezan
  fuera; el α′ de la era en los dos términos.
- **D61-2:** λ = 0 en todas las magnitudes.
- **D61-3:** bootstrap por partido estratificado por torneo, B = 4000, basic en
  log, seed 20260923.
- **D61-4:** F61 = 5 eras × {D_L, D_τ}; BH al 5%; no evaluables fuera y
  declarados.
- **D61-5:** π y λ₁ sobre el bloque de juego abierto, más λ₁ de los cuatro bloques de la liga; irreducibilidad obligatoria; eigen
  y potencias tienen que coincidir.
- **D61-6:** supervivencia por torneo, con el modelo condicionado a L ≥ 2.
- **D61-7:** la jugada de ejemplo sale de la regla de §2, sin excepciones.
- **Salidas:** `reports/progresion_v1.json` (§2 y §3) y
  `reports/supervivencia_v1.json` (§0 y §4). Script `45_progresion.py`.

## 7. Predicciones (van al marcador, separadas de ADR-53 a ADR-60)

1. **P1 · coherencia con el territorio.** El signo del estimado puntual de D_L
   coincide con el signo del field tilt de la era contra la liga
   (`metricas_v1 › global`, estimado puntual) en **al menos 4 de las 5** eras
   principales.
2. **P2 · Jardine en el América.** D_L > 0 y sobrevive a BH en F61.
   *Informada por datos ya vistos:* ADR-53 rechaza para esta era
   (E[T] por encima de la liga) y su field tilt también está por encima.
   D_L no se ha calculado, pero la dirección no es ciega.
3. **P3 · réplica de ADR-21, por torneo.** La cola observada queda por encima
   de la del modelo en k = 12 en **al menos dos tercios** de los torneos.
   *Contaminada en parte:* ADR-21 ya lo vio en el América, con todos los
   torneos juntos. Aquí se prueba torneo por torneo y en toda la liga, que es
   donde el efecto de mezcla ya no puede producirlo.
4. **P4 · la llegada no es la duración.** Entre las cinco eras, la correlación
   de Spearman entre D_L y el ΔE[T] de ADR-53 (`did_h4_v1 ›
   unidades.rel_E_T_vs_liga`) es **menor a 0.9**. Si fuera casi 1, 2.2 no
   aportaría nada sobre 2.1, y se diría así. Con n = 5 es descriptiva; se
   evalúa igual. El JSON publica los cinco pares (D_L, ΔE[T]) y la página
   los dibuja como dispersión en el plegable de 2.2 (nivel C), para que se
   vea de dónde sale el valor de ρ.

Si una predicción no se puede evaluar (por ejemplo, una era no evaluable en
P1), cuenta como "no evaluable", ni cumplida ni fallida, igual que en ADR-60.

## 8. Qué cambia en el informe

- **1.2:** la frase de las clases, según D61-0.
- **1.6:** deja de estar pendiente: el mapa de π del bloque de juego abierto
  de la liga, la animación y el λ₁ de cada bloque.
- **1.7:** la figura de supervivencia en lugar del hueco.
- **2.1:** una capa más con π de la era contra la base y 1/(1 − λ₁); nivel C.
- **2.2:** deja de estar pendiente, con las cuatro capas y el título "¿llega
  a la franja del área sin perderlo?".
- **Cierre:** las predicciones de ADR-61 entran al marcador con su bloque
  propio.
- **Frases prohibidas:** ninguna nueva. "Progresa mejor" y "más eficiente" no
  se usan: la llegada no es calidad.
