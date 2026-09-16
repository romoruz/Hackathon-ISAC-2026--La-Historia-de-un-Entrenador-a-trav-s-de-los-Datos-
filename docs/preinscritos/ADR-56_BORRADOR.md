# ADR-56 — Contexto: cuánto ajusta el entrenador más allá de lo que ajusta la liga

> **BORRADOR PREINSCRITO, 2026-09-16.** Escrito antes de ver cualquier dato de
> contexto del API y antes de programar `scripts/36_contexto.py`. Se commitea
> solo, y la sonda de contexto corre **después** del commit.

## Contexto

La tercera parte de la pregunta del reto: *¿de qué manera el entrenador ajusta
su comportamiento según el contexto (rival, marcador, localía o momento del
juego)?* (5.2).

La observación de partida: **toda la liga ajusta**. Un equipo que va perdiendo
ataca distinto, sin importar quién lo dirija. Por eso "el entrenador ajusta"
significa "ajusta **más o menos que la liga** en el mismo contexto".

## Definiciones

| contexto | niveles (A vs B) | nivel del dato | fuente |
|---|---|---|---|
| **localía** | local vs visitante | partido | `indice_partidos.csv` |
| **marcador** | ganando vs perdiendo (empate descriptivo) | posesión | `score_state` / `score_state_club` de las transiciones |
| **momento** | minuto ≥ 60 vs < 60 (bloques de 15' descriptivos) | posesión | `minute` del primer evento de la posesión |
| **rival** | tercio superior vs tercio inferior | partido | ver abajo |

**Fuerza del rival**: la diferencia de xG por partido del rival en **ese
torneo**, calculada **sin el partido que se clasifica** (leave-one-out), y
cortada en tercios de la liga de ese torneo. Se usa xG y no puntos porque los
eventos no traen el marcador final de forma directa y el xG es menos ruidoso.

**Métricas por unidad y contexto** (M1–M4). Todas salen de la vista defensora
(D54-10, `min_actions = 1`) y del universo de D54-12:
- **M1**: acciones por posesión del club atacando.
- **M2**: P(remate) por posesión del club atacando.
- **M3**: π de presión por acción del rival (club defendiendo).
- **M4**: P(remate) por posesión del rival (remate concedido).

## Estimando

$$\theta = \big[M_u(A) - M_u(B)\big] - \big[M_L(A) - M_L(B)\big]$$

- $M_u$: la unidad.
- $M_L$: la liga sin el club, en los mismos torneos, ponderada a la mezcla por
  torneo de la unidad **dentro de cada nivel de contexto**, igual que en
  ADR-53/54/55.
- M1 se reporta en acciones, M2–M4 en pp.

## Incertidumbre

- **Bootstrap por partido**, B = 6000, con la base remuestreada por partido
  estratificado por torneo y compartida dentro del club.
- **Conserva toda la dependencia dentro del partido**: el marcador y el momento
  cambian dentro del partido, y remuestrear partidos enteros no rompe su
  autocorrelación. Es la respuesta a la crítica de permutar posesiones sueltas.
- **IC basic y p por inversión** (funciones de `30`).
- **Aviso explícito si el piso del p impide rechazar** (lo que le faltó a `35`).

## Familia

**M1–M4 × {localía, marcador, momento, rival}** para las 21 unidades de los
seis clubes de ADR-52: **336 contrastes**, BH al 5%. Todo lo demás es
descriptivo y se calcula para las 53 unidades:
- las cuatro métricas por nivel;
- la tabla cruzada marcador × momento;
- el empate;
- los bloques de 15'.

**Marcador y momento están confundidos**: perder es más frecuente al final. Se
reportan por separado y, **como sensibilidad**, el marcador **dentro** de
"minuto ≥ 60". No hay un modelo conjunto: con B = 6000 y 21 unidades, el
cruce completo deja celdas ralas.

## Condiciones de validez, verificadas por la sonda antes de programar

1. `score_state_club` (o `score_state`) permite saber el marcador **desde el
   punto de vista del equipo que ataca** en toda la vista defensora. Hay que
   decidir cuál y cómo según la sonda, y documentarlo en el script.
2. `minute` llega a las posesiones por `(match_id, possession)` en al menos el
   99% de las filas.
3. `indice_partidos.csv` da local y visitante para los 1,524 partidos.
4. La diferencia de xG por partido es calculable para los 18 equipos en los 10
   torneos.

Si alguna falla, se escribe una adenda antes del código.

## Predicciones, escritas antes de ver los datos de contexto

**Declaración de contaminación.**
- Vi los resultados **anteriores a la migración** de `10_nula_contextos.py`
  (volcado viejo, eras previas al bug #14): el marcador movía poco la matriz.
- No he visto ningún dato de contexto del API.

A nivel de **liga** (sin contraste de entrenador):

1. **Perdiendo se ataca más largo**: M1(perdiendo) > M1(ganando).
2. **Perdiendo se presiona más**: el π de presión del equipo que defiende es
   mayor cuando va perdiendo que cuando va ganando.
3. **Ventaja de local**: M2(local) > M2(visitante).
4. **El final es más abierto**: M2(minuto ≥ 60) > M2(minuto < 60).

A nivel de **entrenador**:

5. **Poca separación**: de los 336 contrastes, **como máximo 20** rechazan tras
   BH.
6. **Si algo separa, es el marcador**: entre los rechazos (si los hay), el
   contexto más frecuente es el marcador.

Cada predicción se reporta tal como salga.

## Lo que no se hace

- Ningún modelo de regresión con interacciones entrenador × contexto: la
  familia de contrastes ya es el estimando.
- Ninguna afirmación causal: el contexto no se asigna al azar, y el marcador es
  consecuencia del juego.
