# ADR-59 · Adenda 7 — sus clubes lado a lado, y menos cosas que tocar

> **Escrita el 2026-09-22**, después del tercer ensayo
> (`docs/ensayos/2026-09-22c.md`) y **antes** del código. Se commitea sola.
>
> **Declaración de contaminación.** Todos los resultados de ADR-53 a ADR-61 ya se
> vieron. Esta adenda **solo cambia la presentación**: qué se enseña a la vez, qué
> baja al anexo y cómo se explican dos cosas. No cambia ninguna cifra, familia, q,
> veredicto, predicción ni el marcador. Las cifras nuevas que aparecen en la
> página vienen de ADR-61 adenda 1 y de ADR-63, que se preinscriben aparte.
>
> **Motivo.** El tercer ensayo: los botones de club siguen sin entenderse como
> botones; la figura de 2.2 compara a los cinco técnicos cuando el lector está
> viendo a uno; la jugada única no aporta; y "puntos porcentuales" no se explica.

## 1. Fuera las pestañas de club: los clubes, lado a lado

Sustituye a la adenda 5 §4 y a la adenda 6 §2. En las secciones con dato por club
(duración y zonas, ocasiones y territorio, sin el balón, contexto, balón parado,
jugadores), **no hay selector**: se muestran **todos los clubes del técnico a la
vez**, una columna por club, en orden cronológico, con la era principal marcada.
Es la misma forma que ya usa la sección de carrera (2.0), que nadie ha reportado
como confusa en tres ensayos.

- Con más de **tres** clubes, las columnas se apilan en filas de tres; no se
  encogen hasta ser ilegibles.
- Si un club no tiene esa medición, su columna lo dice en una línea, en lugar de
  desaparecer.
- **Ningún control nuevo.** El lector no tiene que descubrir nada para ver los
  datos: están puestos.
- Un test comprueba que en el cuerpo **no queda ningún `[data-selclub]`**.

Esto cierra, por construcción, la clase de fallo que se repitió en los ensayos
segundo y tercero: un control que no se ve, o que se ve y no parece control.

## 2. La figura de 2.2 pasa a ser sus clubes

Con ADR-61 adenda 1 ya hay `L` y `τ` para todas sus eras. La figura del cuerpo
muestra **los clubes del técnico que se está viendo**, no los cinco técnicos del
proyecto. La era principal va marcada y las demás llevan su etiqueta
**descriptiva** y la frase fija de ADR-61 adenda 1 §3.

La comparación entre los cinco técnicos **no se borra**: baja completa al anexo,
que es donde una tabla de cinco protagonistas tiene sentido.

## 3. La jugada única sale del cuerpo

La jugada de ejemplo de D61-7 baja al anexo. En el cuerpo queda, por escrito, lo
que decía la figura: cuántas acciones tarda en llegar una posesión típica que
llega. El ensayo fue claro: una sola jugada sorteada no ilustra un promedio y se
lee como si lo hiciera.

No se sustituye por varias jugadas superpuestas ni por un mapa de densidad de las
posesiones que llegan: las dos cosas son datos nuevos y van con su preinscripción,
en F5.

## 4. Dos explicaciones que faltaban

- **Puntos porcentuales**, allí donde aparezcan (3.1 y la sección nueva de
  ADR-63), con la nota fija de ADR-63 §5.3.
- **Leyenda encima de cualquier mapa de diferencia**, con los nombres de los dos
  técnicos en lugar de "positivo" y "negativo".

## 5. Topes

Suben a **≤ 3 000 palabras**, ≤ 18 secciones y ≤ 22 figuras por historia, porque
las columnas por club y la sección de ADR-63 añaden contenido real. El tope se
mide igual que hasta ahora y el humo sigue siendo quien lo hace fallar. Siguen
vigentes la prohibición de jerga (adenda 3 §5) y la regla de no apilar nada en
una columna de más de doce.

## 6. Lo que sigue prohibido

Agregar métricas de eras de torneos distintos en una sola cifra; cifras que no
salgan de nuestros datos; declaraciones de los técnicos; consejos a clubes;
atribuir intención a un jugador o a un técnico. Todo lo de ADR-59 §3 y las
adendas 2 §8, 3 §5, 4, 5 §7 y 6 §5.

## 7. Lo que no cambia

Ninguna cifra, familia, q, veredicto, predicción ni el marcador. El anexo sigue
trayendo cada sección completa, y ahora también la comparación de los cinco
técnicos (§2) y la jugada de ejemplo (§3). Las lecturas preinscritas de Jardine y
sus guardas siguen igual. Ninguna cifra se teclea. El orden de la adenda 5 §1, la
portada de §2, la barra de la adenda 6 §1 y el simulador paso a paso se quedan
como están.

## 8. Fuera de esta adenda

- **Desglose del simulador por fase**: sigue pendiente, con su propia adenda y
  volviendo a correr `46_simulador.py` para los cuatro bloques.
- **Color de club como acento**: sigue pendiente y sigue necesitando una adenda
  que diga dónde se admite el matiz y dónde no.
- **F4 (ADR-62)**: red de pases. **F5**: varias jugadas o densidad de las que
  llegan, mapas de remate y Voronoi.
