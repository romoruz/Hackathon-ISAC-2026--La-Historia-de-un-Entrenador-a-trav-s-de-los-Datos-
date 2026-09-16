# ADR-55 — Balón parado: la cadena para la prevención, la geometría para la supresión

> **BORRADOR PREINSCRITO, 2026-09-16.** Escrito antes de la sonda de la vista
> defensora, antes de programar `scripts/35_balon_parado.py` y antes de ver
> ningún número de balón parado del API. Se commitea solo.
> Integra el proyecto previo de córners (xDefense) en el framework.

## Contexto

El enunciado (5.4) pide los balones parados ofensivos (córners, tiros libres,
saques de banda en zona de peligro; patrones y zonas de remate) y los
defensivos (organización, marcaje, zonas de vulnerabilidad). El proyecto previo
descomponía

$$P(G\mid C) = P(S\mid C)\cdot P(G\mid S, C),$$

con una logística de intención del cobro para el primer factor y la geometría
del `shot_freeze_frame` (`goal_open`) para el segundo. Con 51 goles no tenía
potencia. El API da 6,591 remates de córner con 488 goles y 6,778 de tiro libre
con 549, todos con freeze frame.

## Definiciones (5.6)

- **Secuencia de córner**: empieza en el evento con `pass_type = Corner`.
  Incluye su posesión y las posesiones siguientes del mismo partido y periodo
  con `play_pattern = From Corner`, hasta la primera con otro patrón.
  - **Atacante**: el equipo del cobrador. **Defensor**: el otro.
  - **S = 1** si el atacante remata dentro de la secuencia, incluido el remate
    directo. **G = 1** si marca.
  - Reproduce el `corner_id` del proyecto previo con los eventos del API.
- **Secuencia de tiro libre indirecto**: igual, desde `pass_type = Free Kick`
  con origen en campo rival (x ≥ 60), con `play_pattern = From Free Kick`.
  - **Los tiros libres directos** (`shot_type = Free Kick`) van aparte,
    descriptivos.
  - **Los penales** quedan fuera por definición.
- **Saques de banda** en el último tercio: solo volumen y P(S), descriptivos.
- **Regla de posesión**: `min_actions = 1` en los dos lados, desde la vista
  defensora (ADR-54, adenda 1). Con `min_actions = 2` un córner despejado al
  primer toque desaparece de la muestra: es la mejor defensa posible, y es el
  mismo sesgo de selección que el proyecto previo identificó con el freeze
  frame.

## Decisión

### Capa 1 — prevención

- **C1** = P̂(S | secuencia de córner), empírica por secuencia, del atacante
  (ofensivo) o del rival (defensivo).
- **Contraparte estructural, descriptiva**:
  $P(S\mid C) = \alpha_C^\top(B_{\cdot,\text{GOAL}} + B_{\cdot,\text{SHOT}})$ y
  $E[T\mid C] = \alpha_C^\top N\mathbf 1$, con $\alpha_C$ los estados iniciales de
  las posesiones que empiezan con córner. Usa `derivadas` de `08` a λ=0. Con
  ~300 córners por era los renglones `set_piece` son ralos, así que esta
  versión **no entra en la familia**.
- **La logística de intención del cobro** del proyecto previo se conserva como
  **perfil descriptivo**: proporciones de técnica, altura, lado y zona de
  destino. No es predictor: el proyecto previo mostró que no separa equipos, y
  usar el desenlace del pase sería fuga del objetivo.

### Capa 2 — supresión

- **Modelo de xG de balón parado**, ajustado **una sola vez para toda la liga**
  (regla 3 de `26`), sobre los remates de secuencias de córner y de tiro libre
  indirecto. Sin penales ni directos.
  - Logística L2 con `xg_remate.ajusta_logistica` (λ=3), predicciones fuera de
    pliegue **por partido** (`fuera_de_pliegue`).
  - `xG_base`: distancia, ángulo y **cabeza (indicador binario)**.
  - `xG_full`: `xG_base` más `goal_open`, `d_def_cerca`, `n_def_3m`, `gk_prof` y
    `gk_desv`.
  - **Sensibilidad**: interacción cabeza × distancia. No habrá un modelo
    separado para balones aéreos: parte la muestra a la mitad y un jerárquico
    queda fuera por ADR-19.
- **C2** = E[xG_full | remate de la secuencia], ofensivo o defensivo.
- **Descriptivos**:
  - $xD_{shot} = xG_{base} - xG_{full}$ medio de los remates concedidos;
  - `goal_open` medio;
  - mapas de remate y de destino;
  - calibración contra `shot_statsbomb_xg` como validación externa.
- **Segunda jugada, descriptiva**: con $V(s) = B_{s,\text{GOAL}}$ de la cadena de
  la liga (vista defensora, λ=0), el **máximo de V** alcanzado por el atacante
  después de la primera posesión de la secuencia. Sensibilidad: ventana de
  10 s con `timestamp`. Es el valor marginal de la posición, que la
  probabilidad agregada de C1 no separa.

### Comparación, incertidumbre y familia

- **Cada cantidad de la unidad se compara con la liga sin el club, en los
  mismos torneos** (ADR-53/54). C1 se reporta en pp y C2 en unidades de xG.
- **Bootstrap por partido**, B = 6000, con la base remuestreada por partido
  estratificado por torneo y compartida dentro del club. **El modelo de xG no se
  reajusta en cada réplica**: es un estorbo a estimar (regla 3 de `26`), y se
  declara.
- **IC basic y p por inversión** (funciones de `30`).
- **Familia de descubrimiento**: {C1, C2} × {ofensivo, defensivo} para las
  21 unidades de los seis clubes de ADR-52, es decir 84 contrastes con BH al 5%.
  Todo lo demás es descriptivo, y se calcula para las 53 unidades.
- **Clave compuesta** (club, entrenador) y candado H4-8 vigentes.

## Predicciones, escritas antes de ver los datos de balón parado

**Declaración de contaminación.** Antes de escribir esto vi:
- los totales de la sonda: remates y goles por `play_pattern`, y córners por
  equipo (entre 698 y 968);
- los resultados del proyecto previo (P(S|C) ≈ 0.236; ΔAUC +0.044 con IC que
  cruzaba 0; τ² ≈ 0 entre equipos);
- el humo de D1.

**No** he visto ninguna tasa por secuencia, ningún coeficiente de cabeza ni
ningún número por equipo o era del API.

1. **La regla de posesión importa en córners.** Entre las posesiones
   `From Corner`, `min_actions = 2` descartaba **más del 15%** (sección 4 de la
   sonda).
2. **P(S | secuencia de córner) de la liga está entre 0.18 y 0.30.**
3. **La cabeza baja el xG**: β_cabeza < 0 en `xG_base`, con IC 95% (bootstrap
   por partido) que excluye el 0.
4. **La geometría aporta**: ΔAUC(`xG_full` − `xG_base`) > 0 con IC 95% que
   excluye el 0. Con 51 goles no lo lograba; con ~1,000 debería.
5. **El producto cierra**: en la liga,
   $|\alpha_C^\top B_{\cdot,\text{GOAL}} - \hat P(S)\,\hat E[xG\mid S]| \,/\, \alpha_C^\top B_{\cdot,\text{GOAL}} < 0.25$,
   a nivel de posesión.
6. **Poca separación entre unidades**: de los 84 contrastes, **como máximo 10**
   rechazan tras BH.
7. **La organización defensiva se ve en la foto**: el `goal_open` medio de los
   remates de córner es **menor** que el de los remates de juego abierto en la
   liga.

Cada predicción se contrasta y se reporta **tal como salga**.

## Lo que no se hereda del proyecto previo

sklearn y PyMC (ADR-19), el ranking de equipos, el bootstrap por tiro, y el
`fillna(median)` de las variables del portero (se descarta el remate, como en
`25`).
