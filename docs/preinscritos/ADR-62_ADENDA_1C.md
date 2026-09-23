# ADR-62 · Adenda 1c — H62-1 queda sin resolver

> **Escrita el 2026-09-23**, después de la única corrida del placebo
> (`reports/placebo_red_v1.json`) y después de encontrar en él un fallo de código.
> **No preinscribe ninguna corrida nueva.** Declara que el placebo no se vuelve a
> correr y qué puede y qué no puede decir la página sobre la red de pases.
>
> Se commitea sola, antes de tocar código o página.

## 1. Lo que pasó, en orden

1. **F62 se corrió una vez** con el nulo de ADR-62 §4 (permutación de partidos).
   Los 18 relevos superaron el nulo con p = 0; H62-1 se cumplió en 0 de 18.
2. **El nulo estaba mal diseñado.** Permutar partidos destruye el orden temporal:
   las eras reales son bloques contiguos en el tiempo y las permutadas no, así
   que `T_obs` recoge toda la deriva temporal y el nulo la promedia. El resultado
   no separa "cambió el técnico" de "pasó el tiempo". (Un primer diagnóstico,
   que atribuía el efecto a la composición del plantel, era falso y se corrigió:
   `T_red` ya se restringe a jugadores comunes en ambos lados.)
3. **Se preinscribió un placebo** por bloques contiguos (adenda 1) y se corrigió
   su dimensionado **antes de correrlo** (adenda 1b).
4. **El placebo se corrió una vez.** Leído tal cual: 11 de 30 relevos comparables
   superaron el p90 de los placebos.
5. **Después de correrlo se encontró un fallo.** `51_placebo_red.py` corta
   `bl_a, bl_b = ia[-m:], ib[:m]`, lo que supone que la era *a* precede a la *b*.
   El orden de `did_h4_v1 › pares` no lo garantiza: **24 pares** estaban
   invertidos, y en **13** de ellos `T_relevo` salió `None`. En los invertidos el
   "relevo" comparaba los bloques más alejados del cambio, no los pegados a él.
   Se detectó al revisar por qué los T más altos del estudio caían en esos pares.

## 2. Por qué no se vuelve a correr

- El criterio del §5 de la adenda 1 es **relativo**: "más de la mitad de los
  relevos evaluables (> 50 %)". El `> 15.0` que imprimió el script era `n / 2`
  calculado en ejecución, no un umbral preinscrito. Arreglar el orden cambia qué
  relevos son evaluables, y con eso cambia el denominador. Volver a correr no es
  neutral respecto al criterio.
- D62A-5 prevé "una segunda corrida con otros parámetros". Un fallo de código no
  es otro parámetro; la guarda no cubre este caso.
- La adenda 1b §4 dice que una vez hay números no se toca el diseño. Ya hay
  números.

Por eso **no habrá `placebo_red_v2.json`**.

## 3. Qué queda

- **H62-1 queda sin resolver.** No se cumple ni se retira. En particular, la
  página **no** usa ninguna de las dos frases del §5 de la adenda 1: ni "la red
  se mueve más cuando cambia el técnico" ni "la red se mueve lo mismo cambie o no
  el técnico". Las dos serían afirmar algo que este trabajo no midió bien.
- **H62-2** (ΔG) se reporta como salió en la corrida única, con la advertencia de
  que su nulo comparte el defecto del §1.2.
- **H62-3 falló**: predecía φ_U < 0.5 en la mayoría de los relevos y se cumplió
  en 8 de 18. En los otros 10, más de la mitad del cambio de red viene de cómo se
  conectan los mismos jugadores, no de quién llega o se va. Se publica como
  predicción fallida, con ese nombre.
- **Límite de φ_U, dicho en la página.** φ_U reparte el cambio entre dos eras en
  "uso" y "composición", pero no dice **por qué** cambió. Ese cambio incluye la
  deriva temporal del §1.2. φ_U no depende del placebo, pero tampoco separa al
  técnico del paso del tiempo. La página puede decir de qué está hecho el cambio;
  **no** puede decir que el técnico lo causó.

## 4. Actas

- `reports/red_pases_v1.json`: acta de la corrida única de F62. Intocable.
- `reports/placebo_red_v1.json`: acta de la corrida única del placebo, **con el
  fallo dentro**. Se commitea tal cual y queda marcada como defectuosa en la
  página y en el catálogo de fallos. Intocable.
- `51_placebo_red.py`: en el paquete siguiente se deja **inerte** (aborta citando
  esta adenda). No se corrige el orden, porque corregirlo solo sirve para correrlo.

## 5. Catálogo de fallos de F62

| # | Fallo | Cuándo se vio | Qué se hizo |
|---|---|---|---|
| 1 | Nulo por permutación que ignora el orden temporal | Después de F62 (p = 0 en los 18) | Placebo preinscrito (adenda 1) |
| 1b | Diagnóstico propio equivocado del punto 1 (composición) | Al releer el código | Corregido en voz alta antes de actuar |
| 2 | Bloques de tamaño desigual en el placebo | Antes de correrlo | Adenda 1b |
| 3 | Pares en orden temporal invertido | Después de correrlo | Esta adenda: no se vuelve a correr; H62-1 sin resolver |

## 6. Lo que se aprende

El fallo 3 pasó porque el script confió en un orden que ningún documento
garantizaba, y ninguna guarda lo comprobaba. D62A-2 comprobaba que los bloques no
se solaparan, no que estuvieran en el orden correcto. **Toda guarda que comprueba
una forma debe comprobar también el supuesto del que depende esa forma.**
