# ADR-62 · Adenda 1 — el nulo no separa al técnico del paso del tiempo

> **Escrita el 2026-09-22**, DESPUÉS de ver el resultado de la corrida única
> (`reports/red_pases_v1.json`, commit 8845475) y **antes** del código del
> placebo. Se commitea sola.
>
> **Esta adenda NO es una preinscripción limpia y no se va a presentar como
> tal.** Nace de mirar un resultado. Lo que añade se publica en **nivel B**
> (medido, con su margen), nunca en nivel A, y **no entra a F62**. La distinción
> importa: F62 fue la única familia del proyecto escrita a ciegas, y eso no se
> puede reclamar dos veces.

## 1. Qué salió, para que quede escrito

De la corrida única, sobre 18 relevos evaluables:

- **H62-1 falló: 0 de 18.** En los dieciocho, `T_red` superó el percentil 90 de
  su nulo. Sin una excepción.
- **H62-2 se cumplió: 11 de 18.**
- **H62-3 falló: 8 de 18** (necesitaba más de 9).

## 2. Por qué 18 de 18 es una señal de alarma, no de celebración

En `América · Jardine ↔ Ortiz`: `T_red` = 0.454, nulo p50 = 0.246, p90 = 0.265,
`p` = 0.0 sobre 2 000 permutaciones. Ni una sola réplica se acercó. Un p
exactamente 0 con una separación de 0.19 no dice "efecto enorme": dice que el
estadístico está midiendo **algo distinto** en el observado y en el nulo.

Ninguna variable social real es tan universal como para dar 18 de 18 exactos.

## 3. El diagnóstico, corregido

Un primer diagnóstico —que el nulo mezclaba jugadores de las dos etapas— era
**incorrecto**, y queda anotado como tal: `T_red` se calcula solo sobre los
jugadores comunes, en el observado y en cada permutación, así que la composición
del plantel en el estadístico es la misma por construcción.

Lo que de verdad pasa: **la permutación destruye el orden temporal**. Los dos
grupos reales son bloques de tiempo **contiguos**; los grupos permutados mezclan
partidos del principio y del final del periodo. Así que `T_red` observado recoge
toda la deriva temporal —forma, lesiones, minutos acumulados, roles que
evolucionan, calendario— y el nulo la promedia y se estrecha.

**Consecuencia:** cualquier par de bloques temporales contiguos habría superado
ese nulo, cambiara o no el técnico. H62-1 no separa "cambió el técnico" de "pasó
el tiempo".

**ADR-62 §4 preinscribió el mecanismo** (permutación a nivel de partido, B =
2 000, semilla fija) y se corrió exactamente ese. Lo que no se dimensionó fue su
alcance. El método no cambia; cambia lo que se puede afirmar con él.

**Error de proceso, anotado para el catálogo:** el proyecto ya usaba el placebo
por mitades dos veces (ADR-60 adenda 1 y ADR-63 §4) y aun así ADR-62 no lo
incluyó. La herramienta estaba en casa.

## 4. El placebo: mismo tamaño, mismos bloques contiguos

Para cada relevo (club, técnico a → técnico b) con `k_a` y `k_b` partidos:

1. **m = min(k_a, k_b)**, acotado a `m ≥ 5`. Si no llega, el relevo se declara
   no comparable y se dice con su cifra.
2. **T_relevo(m)**: los **últimos m** partidos de la era *a* contra los
   **primeros m** de la era *b*. Mismo tamaño por lado y bloques adyacentes al
   relevo, para que la distancia temporal sea la mínima posible.
3. **T_placebo(m)**: dentro de **cada una de las dos eras por separado**, sus
   **primeros m** partidos contra sus **últimos m** (si la era tiene ≥ 2m
   partidos; si no, la mitad por lado). Mismo tamaño, bloques contiguos, **sin
   cambio de técnico**.
4. Se agregan todos los `T_placebo(m)` de todas las eras evaluables en una
   distribución de referencia.
5. Jugadores: entra quien tenga **≥ 30 pases en cada bloque** (proporcional a
   que los bloques son más chicos que las eras enteras), y se exigen **≥ 8
   jugadores comunes**, igual que D62-3.

Todos estos números se fijan **aquí, antes de correr**.

## 5. El criterio de decisión, fijado antes

- **H62-1 aguanta** si `T_relevo(m)` supera el **percentil 90** de la
  distribución de `T_placebo(m)` en **más de la mitad** de los relevos
  evaluables (> 50 %).
- **H62-1 se retira** en caso contrario. La página dirá, con todas sus letras,
  que la red se mueve lo mismo cambie o no el técnico, y la afirmación sobre la
  red se apoyará únicamente en **φ_U**.
- Se reportan además, sin umbral y como descripción: la mediana de
  `T_relevo(m)`, la mediana de `T_placebo(m)` y su diferencia.

**Se retire o no, el resultado se publica en el cuerpo de la página, no en el
anexo**, junto con este diagnóstico.

## 6. Lo que NO cambia

- **H62-2 y H62-3 no se tocan.** Sus resultados (11 de 18 y 8 de 18) quedan como
  salieron en la corrida única.
- **F62 no cambia**: sigue siendo 36 contrastes con sus q y sus veredictos. El
  placebo no entra a la familia ni la recorrige.
- **`red_pases_v1.json` no se toca ni se regenera.** Es el acta de la corrida
  única. El placebo escribe su propio archivo.
- φ_U sigue siendo descriptivo, con el aviso de ADR-62 §2 sobre qué descompone.

## 7. Guardas

- **D62A-1.** El script del placebo **no puede escribir** en
  `reports/red_pases_v1.json`. Aborta si el archivo destino es ese.
- **D62A-2.** Ningún partido cae en los dos bloques de una comparación.
- **D62A-3.** `T ∈ [0, 1]` en todos los casos.
- **D62A-4.** El número de relevos comparables y el de placebos quedan escritos
  en el JSON, junto con `m` de cada uno.
- **D62A-5.** Una segunda corrida con otros parámetros se marca y se declara.

## 8. Lo que se aprende, para F5

Cuando un contraste da `p = 0.0` exacto en **todos** sus casos, la primera
hipótesis a comprobar es que el nulo no esté midiendo otra cosa. Los efectos
reales son ruidosos; los artefactos de diseño son limpios.
