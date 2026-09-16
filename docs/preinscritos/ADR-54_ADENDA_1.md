# ADR-54 · Adenda 1 — la base de D1 usa la misma regla de posesión que la unidad

> **PREINSCRITA, 2026-09-16.** Escrita después del humo de `33` (200 réplicas,
> solo América) y **antes** de la corrida completa y de la sonda de la vista
> defensora. Se commitea sola.

## El hallazgo (bug #20)

La unidad focal de D1 son las acciones rivales del directorio del club, con
`min_actions_defense = 1`. La base salía de `data/prior_liga`, que usa
`min_actions = 2` para **todas** las posesiones (`cli.py`: "SOLO PRIOR … sin
`min_actions` asimétrico"). Por eso la base no tenía las posesiones de una
acción que terminan sin fila `TERMINAL`, que son justo las que una presión
exitosa produce.

Verificado fila por fila en el América:
- 1,895 acciones solo en el directorio del club y 0 solo en la liga;
- las 1,895 con L = 1 y sin `TERMINAL`: Jardine 1,085, Ortiz 483, Solari 327
  (2.0%, 2.2% y 2.5% de sus acciones).

El truncamiento difiere entre la unidad y la base, y difiere entre eras. Es el
bug #11 reapareciendo en la base. No lanzó ningún error.

**ADR-53 no está afectada.** Allí la unidad son las posesiones **del club**, que
en el directorio del club usan `min_actions = 2`, igual que la base.

## Decisión

**D54-10.** La base de D1 sale de la **vista defensora**: la unión, sobre los
18 directorios `data/processed_api_*`, de las filas con `team != club` del
directorio. Cada acción de la liga aparece ahí una sola vez, en el directorio
de quien defiende, con `min_actions_defense = 1`.
- La base de un club es la vista defensora sin los partidos de ese club (D54-4
  sin cambios).
- **La unidad focal sale de la misma vista**, así que las dos fuentes coinciden
  por construcción.
- **Condición de validez**, verificada por `34_sonda_vista_defensora.py` antes
  de programar:
  1. ninguna acción en más de un directorio;
  2. ninguna acción de la liga ausente de la unión;
  3. las filas extra son todas posesiones de L = 1 sin `TERMINAL`;
  4. los 1530 partidos presentes con sus dos equipos.

  Si falla alguna, **no se programa**: se escribe una adenda 2 con la
  alternativa, que es regenerar el artefacto de la liga con `min_actions = 1`
  tocando `src/`.

**D54-11.** Se descarta el humo de `33` corrido con la base vieja. Ninguna de
sus cifras se usa.

## Lo que no cambia

La familia, los estimandos E1–E5, B = 6000, la etapa 2 y **las cuatro
predicciones de ADR-54, tal como se escribieron**.

## Declaración de contaminación

El humo con la base vieja mostró, para el América:
- Jardine vs Ortiz: E2 DiD −1.96 pp contra un crudo de −0.46 pp (la predicción
  2 "cumplía");
- p de E1: 0.060, 0.020 y 0.005;
- ninguna rechazó tras BH, con m = 15.

**Las predicciones de ADR-54 no se modifican a la vista de eso.** La
predicción 2 queda contaminada para el América: se reporta con esta nota.
