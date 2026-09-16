# ADR-54 · Adenda 2 — el universo de D1 son los partidos con sus dos lados

> **PREINSCRITA, 2026-09-16.** Escrita después de la sonda de la vista
> defensora (`reports/sonda_vista_defensora.txt`) y antes de ejecutar `33` con
> la vista. Se commitea sola, después de una comprobación automática y antes
> del código.

## Lo que mostró la sonda

De las cuatro condiciones de la adenda 1:
- **(1) Cumple**: 0 filas repetidas entre directorios.
- **(3) Cumple**: las 36,219 filas extra son todas de L = 1 sin `TERMINAL`.
- **(2) Falla**: 3,609 filas de la liga no están en la unión, todas en seis
  partidos: 3919090, 3972016, 3972023, 3972072, 3972119 y 4038911.
- **(4) Falla**: 1,524 de 1,530 partidos tienen sus dos lados.

América, Guadalajara y Tigres tienen 168 partidos en su directorio; los otros
15 clubes, 170.

**Explicación.** Son los partidos de interinos que `eras_api/absorbidos.csv`
quita del artefacto de su club (`load_exclusions`). En esos partidos falta el
lado que ese club defiende. El instalador del paquete h2_18 **comprueba que los
seis partidos coincidan con `absorbidos.csv` antes de hacer commit de esta
adenda**, y aborta si no.

La adenda 1 obligaba a escribir esto antes de programar. Esta adenda cumple esa
regla.

## Decisión

**D54-12.** El universo de D1 son los partidos con sus dos lados en la vista
defensora. Los incompletos salen **de todo**: de la base y de las unidades de
cualquier club. Un partido con un solo lado desbalancearía los pesos
(torneo × zona) de la base, y su otro lado pertenece a un interino que no
forma parte de ninguna unidad analizable.

- **Coste**: 6 de 1,530 partidos (0.4%) y 3,609 de 1,883,137 filas (0.19%).
- `33` calcula los incompletos en cada corrida y los imprime; no los toma de
  esta lista.

## Lo que no cambia

Todo lo demás de ADR-54 y de su adenda 1, incluidas las predicciones.

## Nota para ADR-55

Balón parado hereda D54-10 (la vista defensora) y D54-12 (el universo).

La sección 4 de la sonda ya mostró que `min_actions = 2` descartaba el 19.8%
de las posesiones `From Corner`. Eso **ya es visible** para la predicción 1 de
ADR-55, preinscrita antes (commit 9aa5524): se reporta con esta nota.
