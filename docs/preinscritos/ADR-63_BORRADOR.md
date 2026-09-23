# ADR-63 — los mismos jugadores, con otro técnico

> **Escrito el 2026-09-22**, antes de mirar un solo toque por jugador y zona.
> Se commitea solo, antes del código.
>
> **Declaración de contaminación.** Los resultados de ADR-53 a ADR-61 ya se
> vieron, y la idea de esta sección nace de un ensayo con lectores, así que la
> *pregunta* está informada por lo que ya sabemos. El *dato* no: la distribución
> de toques por jugador y zona no se ha mirado nunca. Aun así, y para no
> aprovecharnos de esa asimetría, todo lo de ADR-63 se publica en **nivel C,
> descriptivo**: sin familia, sin q, sin veredicto y **fuera del marcador**. Se
> reporta un nulo de referencia (§4) para que el lector sepa qué es "mucho", pero
> no se usa para rechazar nada.
>
> **Motivo.** Todo el proyecto compara equipos. Esta sección compara **al mismo
> jugador consigo mismo** bajo dos técnicos en el mismo club. Cambia la frase de
> "el equipo juega distinto" a "los mismos jugadores tocan el balón en otras
> zonas", que es más difícil de explicar por el contexto del club.

## 1. Qué se mide

Para cada **pareja de técnicos consecutivos en el mismo club** (las mismas
parejas que ya usa `did_h4_v1 › pares`, sin añadir ninguna):

- Para cada jugador presente en las dos eras, su **distribución de toques por
  zona**: de todas sus acciones en esa era, qué fracción cae en cada una de las
  20 zonas. Suma 1 por jugador y era.
- La **diferencia por zona**, en puntos porcentuales: `p_a(z) − p_b(z)`.
- Un único número por jugador, **cuánto se movió**: `T = ½·Σ_z |p_a(z) − p_b(z)|`,
  la misma distancia de variación total que ADR-60 usa para los equipos. Va de 0
  (idéntico) a 1 (sin una sola zona en común).

La zona sale de `from_state // 4`, igual que en todo el proyecto. Se cuentan
todas las fases, no solo el juego abierto, y se dice.

## 2. Quién entra

Preinscrito, antes de mirar:

- **D63-1.** Un jugador entra si tiene **≥ 200 toques en cada una de las dos
  eras**. El umbral es el mismo que ADR-60 usa para las unidades y se fija aquí.
- **D63-2.** Una pareja entra si tiene **≥ 5 jugadores** que cumplan D63-1. Con
  menos, se declara el hueco con su cifra y no se pinta.
- **D63-3.** El identificador es `player_id`; el nombre que se muestra es el más
  frecuente para ese `player_id` (igual que ADR-59 adenda 4 §6). Un `player_id`
  nulo no entra.
- **D63-4.** No se recorta ni se pondera por minutos. Los toques ya son la
  exposición; añadir minutos mezclaría dos fuentes.

## 3. Qué NO se hace

- **No se atribuye intención ni causa.** Nunca "el técnico lo movió", ni "lo
  reconvirtió", ni "lo puso de X". Un jugador puede cambiar de zona por una
  lesión, por el rival, por su edad o por un fichaje. La página lo dice con la
  frase fija de §5.
- **No hay p, ni q, ni familia, ni entrada al marcador.**
- **No se nombra la posición táctica** más allá de la `posicion_modal` que ya
  publica `jugadores_v1`.
- **No se compara a un jugador con otro.** Cada jugador solo consigo mismo.

## 4. El nulo de referencia (descriptivo)

Para saber si una `T` es grande, se compara contra lo que se mueve un jugador
**sin cambiar de técnico**: dentro de cada era, se parten sus toques en dos
mitades por fecha y se calcula la misma `T`. Se publican el percentil 50 y el 90
de esas `T` de media era. Es el mismo truco del placebo de ADR-60 adenda 1, y se
lee igual: "un jugador se mueve esto de un semestre a otro aunque nadie cambie".

Se reporta como referencia visual, no como prueba: ninguna `T` se declara
significativa.

## 5. Cómo se dice en la página

Sección nueva, dentro de 3.1 (el club antes y después de él), en nivel C:

1. Dos cuadrículas 5 × 4 del mismo jugador, una por técnico, **con la misma
   escala**, y una tercera con la resta.
2. Una leyenda encima que diga qué es cada color, con los nombres de los dos
   técnicos, no "positivo/negativo".
3. Una nota fija que explique la unidad, porque el tercer ensayo tropezó ahí:

   > "Un punto porcentual es la resta de dos porcentajes. Si tocaba el 20% de sus
   > balones en esa zona con uno y el 10% con el otro, la diferencia es 10 puntos
   > porcentuales, no «el doble»."

4. El ranking de quién se movió más, con la línea del nulo de §4.
5. La frase fija de no-causalidad:

   > "Esto describe dónde tocó el balón cada jugador, no por qué. Un cambio puede
   > venir del técnico, del rival, de una lesión o de los fichajes; con estos
   > datos no se puede separar."

## 6. Salida

`scripts/47_jugadores_zona.py` → `reports/jugadores_zona_v1.json`:

```
parametros  {umbral_toques, min_jugadores, fases: "todas", nulo: "mitades por fecha"}
pares[]     {club, a, b, n_jugadores, hueco?}
  jugadores[] {player_id, nombre, posicion_modal, toques_a, toques_b,
               p_a[20], p_b[20], dif[20], T}
  nulo        {p50, p90, n}
```

## 7. Guardas (el script aborta si fallan)

- **D63-5.** Cada `p_a` y `p_b` suma 1 a 1e-9.
- **D63-6.** `T = ½‖p_a − p_b‖₁` cae en [0, 1].
- **D63-7.** Ningún jugador aparece dos veces en la misma pareja.
- **D63-8.** Si `transitions.parquet` no trae `player_id`, el script aborta con el
  nombre del directorio; no se inventa un sustituto.

## 8. Fuera de ADR-63

La red de pases con `pass_recipient_id`, la centralidad y el Gini estructural
siguen siendo **F4 (ADR-62)**. Esto no los adelanta ni los sustituye: aquí no hay
grafo, solo conteos por zona.
