# ADR-55 · Adenda 1 — la secuencia de córner es más larga de lo previsto

> **PREINSCRITA, 2026-09-16.** Escrita después del primer humo de `35` sobre los
> datos reales, que se detuvo antes del modelo, y **antes** de calcular
> cualquiera de las cantidades que aquí se añaden. Se commitea sola.

## Lo que se vio

- **P(S | secuencia de córner) en la liga = 0.396.** La predicción 2 de ADR-55
  decía [0.18, 0.30]. **La predicción 2 falla**, y se reporta como tal. Esa cifra
  no depende del bootstrap.
- Otros valores de la liga: tiro libre indirecto 0.209, saque de banda en el
  último tercio 0.140.
- 14,859 secuencias de córner.

**Explicación probable, no verificada.** StatsBomb conserva
`play_pattern = From Corner` mientras el atacante recicla la posesión, así que
la secuencia puede incluir remates muy posteriores al cobro. El proyecto previo
daba 0.236 con otra ventana.

Además, el humo no llegó al modelo: `xg_remate.features` devolvió `None` para
todos los remates (bug #21, ver el paquete h2_20).

## Decisión

**D55-9.** La definición principal de C1 **no cambia**, y la familia tampoco.

**D55-10.** Se añaden dos sensibilidades **exploratorias**, fuera de la familia
y sin p, para la liga y para cada unidad:
- **S₁₀**: remate del atacante con `timestamp` en (0, 10] s tras el cobro, en el
  mismo periodo.
- **S_fase**: remate del atacante dentro de la secuencia con `set_piece_phase`
  no nulo, la fase de balón parado que delimita el proveedor.

Se reportan junto a C1 con la etiqueta "exploratorio, añadido tras ver
P(S) = 0.396".

**D55-11.** El script aborta si menos de 100 remates superan la extracción de
geometría. Un modelo sobre cero remates no debe fallar lejos de la causa.

## Lo que no cambia

Las demás predicciones, la familia, el modelo y la segunda jugada.
