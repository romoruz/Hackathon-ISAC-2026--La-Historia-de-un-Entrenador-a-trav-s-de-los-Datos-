# D59-P — Panel 5.5: métricas del proveedor por era (descriptivo)

> **BORRADOR PREINSCRITO, 2026-09-17.** Escrito después de la sonda h2_26 y
> antes de programar `scripts/40_panel_55.py`. Se commitea solo. Pasará a ser
> la nota del panel dentro de la ADR del informe (ADR-59).
>
> **Declaración de contaminación.** Vi el esquema del parquet de liga, la
> cobertura de `obv_*`, `shot_statsbomb_xg` y `pass_end_location`, y los
> resultados de ADR-53 a ADR-58. **No** he calculado ninguna de las métricas de
> este documento para ninguna era ni para la liga.

## Qué es y qué no es

El enunciado (5.5) pide métricas existentes (xG, OBV, pases progresivos,
presión, *field tilt*). Este panel las pone **por era y contra la liga del mismo
torneo**, con la misma unidad y el mismo universo que ADR-54 a ADR-58.

Es **descriptivo**: sin familia, sin p-valores, sin BH, sin predicciones. Lleva
intervalos para que ninguna cifra salga sin su incertidumbre, pero ningún
intervalo se redacta como hallazgo. La presión ya tiene su ADR (54) y no se
repite aquí.

## Unidad, universo y comparación

- **Unidad**: era = (club, entrenador), la misma lista que `38_jugadores.py`
  (cobertura suficiente y `check_verificada`). Clave compuesta, nunca solo el
  entrenador (bugs #17 y #18).
- **Universo**: partidos con sus dos lados (D54-12), fase regular, sin la
  temporada 351.
- **Observación**: equipo-partido, partido completo.
- **Liga**: los equipo-partido de los partidos **sin el club** (D54-4), en los
  mismos torneos, estandarizada a la mezcla de torneos de la era:
  base = Σ_t w_t · media_liga_t, con w_t = fracción de partidos de la era en t.
- **Diferencia** = media de la era − base. Relativa = diferencia ÷ base.
- **Incertidumbre**: bootstrap por partido, B = 2000, la base remuestreada por
  partido estratificado por torneo y compartida dentro del club (igual que 38).
  IC *basic* (función de 30). Semilla 20260919, estable por (club, entrenador).
- **Percentil por torneo**: la media de la era en el torneo dentro de la
  distribución de las medias de los demás equipos en ese torneo, con la
  función `percentil` de 38. Torneos con menos de 12 partidos de la era se
  marcan parciales y no llevan percentil (misma regla que 38).

## Coordenadas

Cada evento viene en el marco del equipo que lo ejecuta, que ataca hacia
x = 120 (verificado el 2026-09-17: pares presión–acción presionada a 3.60 m
rotando 180° contra 69.40 m sin rotar; `14_verificar_ejes_def.py` correcto en
América y Cruz Azul). Ninguna métrica de este panel mezcla eventos de dos
equipos en un mismo marco, así que **no se aplica espejo**.

`location` y `pass_end_location` son texto JSON `[x, y]`. Se leen con la misma
expresión que 38 (`strip_chars("[]")` y `split(",")`).

## Definiciones

**D59P-1 · xG.** Suma de `shot_statsbomb_xg` de los remates del equipo en el
partido.
- Principal: **sin penales** (`shot_type != "Penalty"`), a favor y en contra.
- Sensibilidad: con penales.
- Si la columna `shot_type` no existe o no trae la etiqueta `Penalty`, el
  script aborta (regla D54-9).

**D59P-2 · OBV.** Suma de `obv_total_net` de todos los eventos del equipo con
valor no nulo. A favor: los del equipo. En contra: los del rival en el mismo
partido.

**D59P-3 · Pase progresivo (principal).** Un pase cuenta si cumple todo:
1. completado: `pass_outcome` nulo;
2. de juego: `pass_type` no está en {Corner, Free Kick, Throw-in, Goal Kick,
   Kick Off};
3. empieza fuera del 40% propio del campo: x₀ ≥ 48;
4. se acerca al centro de la portería rival al menos un 25%:
   d(x₁, y₁) ≤ 0.75 · d(x₀, y₀), con d(x, y) = √((120 − x)² + (40 − y)²).

Por qué así: la condición relativa no depende de la escala de las coordenadas
de StatsBomb, que no son metros exactos. Excluir el 40% propio sigue la
definición pública más citada y evita contar como progresión la circulación de
la salida. No hay umbral de ángulo: la reducción de distancia a la portería ya
incluye la dirección, y un umbral de ángulo sería un parámetro libre sin
referencia.

Se reporta por partido (conteo) y como fracción de los pases que cumplen 1 y 2.

**D59P-4 · Pase progresivo (sensibilidad, umbrales fijos).** Mismos 1 y 2, sin
el 3, y ganancia g = d₀ − d₁ de al menos:
- 30 si empieza y acaba en campo propio (x < 60);
- 15 si empieza en campo propio y acaba en el rival;
- 10 si empieza y acaba en campo rival.

Un pase que empieza en campo rival y acaba en el propio nunca cuenta. Las
unidades son las de las coordenadas; se declara que no son metros exactos.

**D59P-5 · Field tilt.** **Se reutiliza la definición de ADR-58 (D58-C)**, no
se escribe otra: acciones reales del equipo (transiciones que no son
`TERMINAL`, unidas a su evento) con x ≥ 80 en su marco, divididas entre las
acciones reales de los dos equipos con x ≥ 80 en su propio marco. Aquí sobre el
partido completo, en lugar de ventanas de 10 minutos.

## Comprobaciones que el script ejecuta y reporta

1. Media de liga del *field tilt* sobre todos los equipo-partido = 0.5 (cada
   partido suma 1 entre sus dos lados).
2. Media de liga de xG a favor = media de xG en contra (y lo mismo para OBV).
3. Tasa de unión acciones–eventos = 1.0 (la misma que reporta 38).
4. Conteos de `pass_type` y de `shot_type`, y fracción de pases completados.
5. Fracción de pases progresivos en la liga con las dos definiciones.

Si falla 1 o 2, el script aborta sin escribir.

## Redacción

- "Bajo X, el equipo generó N xG sin penales por partido, M más que la liga en
  los mismos torneos [IC]."
- Nunca "mejor" ni "peor" sin decir en qué métrica, y nunca causal.
- Un intervalo que excluye el cero **no** es un hallazgo: el panel no tiene
  familia ni control de multiplicidad.

## Salida

`reports/metricas_v1.json` (nombre previsto en `PLAN_CIERRE.md`). Se escribe a
un archivo nuevo; si existe, el script se niega.
