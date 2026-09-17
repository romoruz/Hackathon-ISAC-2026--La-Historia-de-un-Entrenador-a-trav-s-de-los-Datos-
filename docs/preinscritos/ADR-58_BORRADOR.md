# ADR-58 — Uso de jugadores: núcleo, roles y lo que pasa tras el primer cambio

> **BORRADOR PREINSCRITO, 2026-09-17.** Escrito después de la sonda de
> alineaciones y antes de programar `scripts/38_jugadores.py` y de calcular
> cualquier métrica alrededor de las sustituciones. Se commitea solo.

## Contexto

El enunciado (5.3) pide roles dentro del sistema, cambios en alineaciones e
impacto de sustituciones. La sonda confirmó:
- alineación en los 1,530 partidos, con `positions` por jugador (`from`, `to`,
  periodos, motivos de entrada y salida, `counterpart_id`);
- `player_id` en el 100% de las acciones;
- 13,653 sustituciones (4.5 por equipo y partido; 93% tácticas; mediana del
  minuto 70; 1,808 antes del 46) y 5,493 cambios tácticos sin sustitución.

Unidades: las 53 eras. Familias: ADR-52 (21 eras) y casos (ADR-57, 24 eras).
Universo de partidos: D54-12.

## A · Núcleo y rotación (descriptivo)

**Minutos jugados** por jugador y partido, desde `positions`: la suma de
(`to` − `from`) por periodo. Un `to` nulo es el final del periodo, tomado como
el último `timestamp` de los eventos de ese periodo.

Por era y torneo:
- **N80**: el menor número de jugadores que suman el 80% de los minutos del
  equipo;
- **continuidad**: la fracción media del once titular que se repite respecto al
  partido anterior del mismo equipo en el mismo torneo;
- **jugadores distintos** usados;
- **cambios tácticos por partido** (eventos `Tactical Shift`).

Cada era se ubica en la distribución de la liga en los mismos torneos
(percentil), sin contraste.

## B · Roles (descriptivo)

Para cada jugador con al menos **450 minutos** en la era:
- su posición modal según la alineación;
- la distribución por zona 5×4 de sus acciones reales (transiciones con su
  `player_id`, marco del equipo que ataca).

Sin contraste.

## C · Tras el primer cambio táctico (inferencial, nunca causal)

**Evento.** La primera sustitución **táctica** (`substitution_outcome =
Tactical`) del equipo en el partido, si ocurre en el **segundo tiempo** con
`timestamp` entre **10:00 y 35:00** (minutos 55 a 80). Si el primer cambio
táctico fue antes (incluido el medio tiempo) o después, el equipo-partido no
entra.

**Ventanas** (mismo periodo, por `timestamp`), con **exclusión de ±60 s** en
torno al cambio:
- **antes**: posesiones que empiezan en [t − 11 min, t − 1 min);
- **después**: posesiones que empiezan en (t + 1 min, t + 11 min].

La ventana previa se recorta al inicio del periodo si hace falta.

**Métricas por ventana** (razón de sumas dentro de la ventana):
- **M1**: acciones por posesión del equipo;
- **M2**: P(remate) por posesión del equipo;
- **M4**: P(remate) concedido por posesión del rival;
- **FT (field tilt)**: acciones reales del equipo en el último tercio (x ≥ 80
  en su marco) ÷ acciones en el último tercio de los dos equipos.

**Δ** del evento = métrica después − métrica antes. Si una ventana tiene
denominador 0, el evento no cuenta para esa métrica.

**Estrato**:
- bloque de tiempo del cambio (10:00–17:59, 18:00–25:59, 26:00–35:00 del
  segundo tiempo);
- marcador del equipo al momento del cambio (perdiendo, empatando, ganando);
- torneo.

**Estimando.** θ = media de Δ de la era − media de Δ de la liga sin el club,
ponderada a la mezcla de estratos de la era.

**Incertidumbre.** Bootstrap por partido, B = 6000, con la base remuestreada
por partido estratificado por torneo y compartida en el club. IC basic y p por
inversión. Con 84 contrastes (ADR-52) y 96 (casos), el piso del p queda por
debajo de α/m.

**Familias.** {M1, M2, M4, FT} × eras: 84 contrastes (ADR-52) y 96 (casos), BH
al 5% por separado.

**Redacción obligatoria.** *"Tras sus primeros cambios, el equipo…"*. Nunca
*"sus cambios provocan…"*: los técnicos cambian cuando el partido lo pide
(confusión por indicación). La estratificación por minuto y marcador la
atenúa, pero no la elimina.

**Sensibilidades, fuera de las familias:**
1. sin exclusión de ±60 s;
2. el primer cambio **por lesión** en la misma franja, como referencia de un
   cambio no elegido.

**Por qué la exclusión no es necesaria para θ, pero se adopta.** El tiempo
muerto alrededor de un cambio lo comparten todos los cambios de la liga, y θ lo
resta. La exclusión limpia Δ: la primera posesión tras el cambio suele nacer de
un reinicio.

## Predicciones, escritas antes de calcular nada alrededor de los cambios

**Declaración de contaminación.** Vi los conteos de la sonda (sustituciones por
partido, cuartiles del minuto, motivos) y los resultados de ADR-53 a ADR-57.
**No** he visto ninguna métrica antes ni después de un cambio.

1. **Liga, perdiendo**: Δ M2 > 0 tras el primer cambio táctico.
2. **Liga, perdiendo**: Δ FT > 0 tras el primer cambio táctico.
3. **Poca separación**: a lo sumo **5 de 84** (ADR-52) y **5 de 96** (casos)
   rechazan.
4. **Liga, perdiendo**: |Δ M2| tras un cambio por lesión < |Δ M2| tras uno
   táctico.

Cada predicción se reporta tal como salga.
