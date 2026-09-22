# ADR-59 · Adenda 3 — una página que se lee en quince minutos

> **Escrita el 2026-09-21**, después de cerrar F3 (h2_35, commit `df3bfa8`) y
> **antes** de tocar `12_reporte_html.py` para la reforma (paquete h2_36). Se
> commitea sola, antes del código.
>
> **Declaración de contaminación.** Todos los resultados de ADR-53 a ADR-61 ya
> se vieron. Esta adenda **solo cambia la presentación**: qué va en el cuerpo
> de la página, qué va al anexo y con qué palabras se dice. No cambia ninguna
> cifra, familia, q, veredicto, predicción ni el marcador. Nada se borra: lo que
> sale del cuerpo pasa al anexo con las mismas cifras y las mismas fuentes.
>
> **Motivo.** La revisión de la página por alguien que no la construyó
> encontró tres problemas. Primero, jerga que solo entiende quien la escribió
> (ADR-xx, N80, τ, q, "era", "base"). Segundo, que el acto 1 no nombra las
> cuatro fases de la cadena. Tercero, que es demasiado larga: medida sobre el
> demo sintético de h2_35, cada historia tiene unas 5 600 palabras, 22
> secciones y 37 figuras.

## 1. Un solo modo

Se retira el interruptor sencilla/técnica (revierte la adenda 2 §7). La página
tiene un solo lenguaje, llano, en todo el cuerpo. Lo técnico va al anexo (§4).

El nivel de cada frase **sigue visible**, como un punto de color con su
palabra: *probado* (A), *medido* (B), *descriptivo* (C). Una leyenda en la
cabecera explica los tres. El color sigue al nivel, no a la dirección del
resultado.

## 2. Estructura del cuerpo

El selector de cinco historias se queda: solo se ve una a la vez, así que no
es lo que alarga la página. Lo que se recorta son las secciones de cada
historia.

**Acto 1, común (de 7 secciones a 3):**

1. **La cancha, la posesión y cómo termina.** Fusiona 1.1 y 1.2 en un solo
   diagrama:
   - las 20 zonas;
   - las **cuatro formas de empezar** una posesión, cada una con su ejemplo:
     juego abierto; contragolpe o balón del portero; saque de banda o de meta;
     córner o tiro libre;
   - los **cuatro finales**: gol, remate sin gol, pérdida y balón fuera.

   Lleva también la frase de los bloques corregida en ADR-61 §0: una posesión
   conserva su forma de empezar, así que cada una es su propia cadena de 20
   zonas.
2. **Dónde vive el balón: simulador** (§6). Sustituye a la animación de 1.6.
3. **Por qué comparamos contra la liga del mismo torneo.** Una frase y la
   figura de la deriva.

**Acto 2, por historia (de 8 secciones a 7):**

| sección | qué lleva |
|---|---|
| 2.1 cuánto dura y dónde vive | su frase, el mapa de zonas y **una línea de consistencia**: "en k de n torneos quedó por encima (o por debajo) de la liga", con una minifigura de la serie (`did_h4_v1 › serie_por_torneo`) |
| 2.2 llegar al área | como en h2_35 |
| 2.3 ocasiones y territorio | igual |
| 2.4 sin el balón | igual; la falta de presión (fuera de los seis clubes) va en una nota de una línea, no en un bloque |
| 2.6 contexto | condensada a una frase y una figura; se queda porque sostiene la pregunta central |
| 2.7 balón parado | **muy comprimida**: una frase, la figura del embudo córner → remate → gol con las cifras que ya publica y un enlace "detalles en el anexo". Se queda en el cuerpo porque 5.4 es un componente del reto |
| 2.8 jugadores y minutos | igual |

2.5 (torneo tras torneo) completa va al anexo; su afirmación de consistencia
queda en 2.1. El mapa "dónde vive una posesión viva" de 2.1 va al anexo porque
repite el de zonas.

**Acto 3, por historia (de 4 secciones a 2):**

1. **El club antes y después de él.** T, el control y el placebo, como en
   h2_34. Suma φ_U en lenguaje llano, solo cuando es estimable y estable:
   "de ese cambio, X% viene de que los jugadores que siguieron se movieron
   distinto; el resto, de que jugaron otros". Si no es estable: "depende de
   cómo contemos a los que siguieron; no damos la cifra". El intervalo va al
   anexo.
2. **¿Se lleva su estilo a otro club?** Fusiona 3.3 y 3.4: el mapa de estilos
   y la distancia entre sus clubes contra la de la liga.

La antigua 3.2 (plantel contra uso) completa va al anexo.

**Cierre (de 3 secciones a 2, más el anexo):**

1. **¿Nos creen?** El marcador y el control, en corto.
2. **Límites.** Una lista de cinco líneas como máximo.

Después va el anexo.

## 3. Capas

Cada sección del cuerpo lleva **frase y figura**. "En un partido" solo aparece
donde ya existe. El plegable "cómo lo medimos" sale del cuerpo y va al anexo,
con un enlace desde su sección. Si falta la frase o la figura, se declara con
un hueco de una línea.

Una frase B sigue teniendo su intervalo (ADR-59 §2), pero el número del
intervalo se ve en la figura y en el anexo, no en la frase. La lectura de q en
palabras (`fuerza(q)`) sí va en la frase, sin el número.

## 4. El anexo: "Para quien quiera revisar las cuentas"

Va plegado al final y contiene, sin cambiar una cifra:

- el glosario técnico y el mapa de ADR a sección;
- por sección, su antiguo "cómo lo medimos" (estimando, comparación, familia,
  q, intervalos, archivo y campo);
- las secciones retiradas del cuerpo: estimación (1.3), el semáforo completo
  (1.4), por qué no simulamos (1.7), torneo tras torneo (2.5), plantel contra
  uso (3.2), el mapa de la posesión viva de 2.1 y la dispersión de P4;
- el marcador completo con cada predicción;
- el catálogo de errores, incluida la frase falsa de 1.2 (h2_31 a h2_34).

## 5. Lenguaje

**Glosario al inicio**, plegado, con los términos del oficio explicados en una
línea: field tilt, xG, npxG, OBV y pases progresivos.

**Fuera del cuerpo**: nada técnico del proyecto. `test_jerga.py` aborta si
alguno de estos patrones aparece en el cuerpo, contando el texto visible, los
títulos, los pies de figura, los `aria-label` y los `data-tip`:

`ADR-\d`, `\bq =`, `\bp = 0\.\d`, `IC \[`, `N80`, `τ`, `λ`, `π`,
`bootstrap`, `Benjamini`, `BH al`, `\bf = 0\.\d`, `\bF\d\d\b`, `D\d\d-\d`,
`h2_\d\d`, `\bera principal\b`, `\bla base\b`,
`cuasi-estacionaria`.

En el anexo están permitidos. El test tiene su prueba de que puede fallar.

**Traducciones fijas** (el generador las usa siempre, no se eligen caso por
caso):

- "duración esperada de la posesión" → "cuántas acciones dura una posesión";
- τ → "acciones hasta llegar";
- π → "a dónde tiende el balón cuando la posesión dura";
- N80 → "cuántos jugadores juntan el 80% de los minutos";
- A que rechaza → "es distinto de la liga, y lo comprobamos con una prueba
  escrita antes de mirar";
- A nula → "no encontramos diferencia; si la hay, es menor a X".

## 6. Simulador de "dónde vive el balón"

**Datos.** La matriz del bloque de juego abierto **no está** en
`progresion_v1.json`: ahí solo se guardaron π, λ₁ y la animación. La exporta
un script nuevo, `46_simulador.py`, que reusa las funciones de 45 (λ = 0, la
misma base). Exporta Q_open de la liga del torneo de 1.6 y de la era
principal de cada historia.

**Guarda.** El π que sale de cada Q_open exportada tiene que coincidir con el
publicado (`supervivencia_v1 › liga_16.pi` y `progresion_v1 › eras[].cuasi`) a
1e-9. Si no coincide, aborta. No es inferencia nueva: nivel C.

**Interacción.** La persona:

- elige la zona de inicio tocando la cancha;
- avanza con **"una acción más"** (μ → μQ/‖μQ‖), **"diez acciones"** o
  **"hasta el final"**, que pinta π;
- vuelve a empezar con **"reiniciar"**;
- cambia entre la liga y el técnico de la historia.

Junto a la cancha se ve "de cada 100 posesiones que empezaron aquí, siguen
vivas N", calculado como ‖μ₀Qⁿ‖. Frase fija: "Sigue tocando: si la posesión
dura, el balón termina repartido siempre igual, empiece donde empiece".

## 7. Topes que se prueban

Los mide el humo sobre el informe real, en cada una de las cinco historias:

- **palabras** en el cuerpo (sin anexo ni glosario): ≤ 2 500;
- **secciones** visibles: ≤ 14 (tres del acto 1, siete del acto 2, dos del
  acto 3 y dos del cierre);
- **figuras** en el cuerpo: ≤ 16.

Si alguna historia pasa de un tope, el humo falla.

## 8. Lo que no cambia

- Ninguna cifra, familia, q, veredicto ni predicción.
- Ninguna cifra tecleada: todas salen de los JSON y llevan su fuente, en el
  cuerpo y en el anexo.
- Las frases prohibidas (ADR-59 §3 y adenda 2 §8).
- Las lecturas preinscritas de Jardine con sus guardas (`LECTURA PREINSCRITA
  ROTA`).
- Las cinco ranuras de la portada (adenda 2 §6). Se añade arriba una sola línea
  fija, sin afirmación: "Qué cambia cuando cambia el técnico y qué se queda con
  el club, medido contra la liga del mismo torneo".
- Nada causal.
- Sin dependencias externas (ADR-38).
