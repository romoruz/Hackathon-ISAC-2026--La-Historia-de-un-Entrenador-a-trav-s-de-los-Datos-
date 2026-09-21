# ADR-60 · Adenda 1 — qué dice el fallo del control y un placebo para T

> **Escrita el 2026-09-21, después de ver `reports/relevos_v1.json`** (h2_33,
> corrida del 2026-09-21 17:08). Se commitea sola, antes del código de
> h2_34.
>
> **Declaración de contaminación.** Todo lo de ADR-60 ya se vio: 19 de 21
> parejas rechazan, P2 y P6 fallan y el marcador de ADR-60 queda en 4 de 6.
> Nada de eso cambia: ni la familia, ni las q, ni los veredictos, ni el
> marcador. Esta adenda hace dos cosas. Primero, fija la lectura del fallo
> del control (§1 a §3). Segundo, añade un diagnóstico **exploratorio**, el
> placebo de §4, que se define aquí **antes de calcularlo**, con sus dos
> lecturas posibles escritas de antemano. El placebo es nivel C y no toca
> ningún veredicto de F60.

## 1. Qué pasó

- **F60:** rechazan 19 de 21 parejas tras BH, con T entre 0.030 y 0.138.
- **P6 (control):** falló. Cocca I → Cocca II, el mismo técnico en el mismo
  club, da T = 0.111 con p = 0.0002. Es una de las T más grandes de la tabla.
- **P2:** falló. Holan → Larcamón rechaza, con q = 0.003.

## 2. Lectura del control, fijada aquí

La nula de ADR-60 §4 contesta una sola pregunta: **¿son intercambiables los
partidos de las dos eras?** El control muestra que no lo son ni siquiera cuando
el técnico es el mismo. Entre dos etapas separadas en el tiempo cambian el
plantel (Cocca tiene 4 compartidos), los rivales y el club mismo.

Por lo tanto:

1. Un rechazo de T se lee **solo** como "el uso del campo cambió entre las dos
   eras". Nunca como "el técnico cambió el uso". Es lo que ya pedía ADR-60 §7;
   el control lo confirma con datos.
2. Que 19 de 21 rechacen **no** es evidencia de que los técnicos importen. Con
   un control que también rechaza, el rechazo casi universal es lo esperable
   si T mide cambio entre periodos, venga de donde venga.
3. La página lo dice junto a T, en 3.1, con las cifras del control sacadas del
   JSON.
4. P2 y P6 cuentan como fallos en el marcador, tal cual.

## 3. P5 es circular en parte

Con menos compartidos, más acciones caen en composición por construcción: los
jugadores no compartidos van enteros a C. Por eso la correlación positiva entre
compartidos y φ_U (ρ = 0.49, n = 21) es en parte mecánica. P5 se cumplió y así
se cuenta; el plegable de 3.2 dice que no es evidencia externa.

## 4. Placebo exploratorio: el tiempo dentro de una misma era

**Pregunta:** ¿cuánto cambia el uso del campo **sin** cambio de técnico?

**Unidades:** cada era que aparece en F60 o en el control, siempre que tenga
al menos 20 partidos. Por eso se excluyen las eras cortas.

**Placebo:** los partidos de la era, ordenados por fecha, se parten en dos
mitades con el mismo número de partidos (si el total es impar, el partido del
medio va a la primera mitad). Sobre esas dos mitades se calcula T con el mismo
código de 42: ocupación en exceso de la liga del mismo torneo y la misma nula
por permutación, con B = 999.

**Se publica, nivel C:**

- la mediana y el percentil 90 de las T placebo;
- para cada pareja de F60, el percentil de su T entre las T placebo;
- cuántas de las 21 T de relevo superan el percentil 90 del placebo.

**Sesgos declarados:**

- Cada mitad tiene menos partidos que una era completa, así que la T placebo
  tiende a salir **más grande** por ruido. Eso juega en contra de que los
  relevos se separen del placebo: la comparación es conservadora para la
  lectura A.
- Las dos mitades están pegadas en el tiempo; dos eras de un relevo también,
  pero cubren más tiempo en total.

**Lecturas, fijadas antes de calcular.** Sea *k* el número de T de relevo por
encima del percentil 90 del placebo:

- **A · k ≥ 11 de 21:** "los relevos mueven el uso del campo más que el paso
  del tiempo dentro de una misma era".
- **B · k ≤ 10:** "no distinguimos el cambio que acompaña a un relevo del que
  ya ocurre dentro de una misma era".

Ninguna de las dos es causal. No se agregan predicciones al marcador: esto es
exploratorio.

## 5. Qué entra al informe

- **3.1:** una nota con el control (T y p de Cocca I → Cocca II, desde
  `relevos_v1`) y la lectura de §2.
- **3.1:** la lectura del placebo (A o B, la que salga), nivel C, con su
  mediana y su percentil 90.
- **3.2:** en el plegable, la línea de §3.
- **La figura de T:** una banda con el percentil 90 del placebo como
  referencia de contexto, nunca como criterio.
