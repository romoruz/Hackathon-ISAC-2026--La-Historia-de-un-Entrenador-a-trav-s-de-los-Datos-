# ADR-59 · Adenda 6 — que los controles funcionen y que las etiquetas no mientan

> **Escrita el 2026-09-22**, después del **tercer ensayo** con un lector del
> hackathon sobre la página de h2_38 (registro en `docs/ensayos/2026-09-22c.md`)
> y **antes** del código de h2_39. Se commitea sola, antes del código.
>
> **Declaración de contaminación.** Todos los resultados de ADR-53 a ADR-61 ya se
> vieron. Como las adendas 3, 4 y 5, esta **solo cambia la presentación**: un bug
> de CSS, el rótulo de un control, cuatro pies de figura y el tope de palabras.
> No cambia ninguna cifra, familia, q, veredicto, predicción ni el marcador, y no
> añade contrastes ni datos nuevos.
>
> **Motivo.** El tercer ensayo encontró que los menús de la barra no responden;
> que el botón «todos sus clubes» promete un agregado que no existe (y que no
> debe existir); que no se dice si la media de la liga es histórica o por torneo;
> que «la última franja del campo» no se reconoce como una columna de la malla
> de 1.1; y que los medidores de 2.7 no se saben leer.

## 1. Los menús de la barra (bug de h2_38)

`.navin` llevaba `overflow:hidden` para garantizar que la barra no se desbordara.
Los `.drop-menu` son `position:absolute` y cuelgan **por debajo** de la barra, así
que quedaban recortados: se abrían invisibles. La regla se quita; nunca hizo
falta, porque un elemento absoluto no empuja el ancho de su contenedor. La barra
sigue sin poder desbordarse por `flex-wrap:nowrap` y porque el nombre del técnico
se encoge (`min-width:0` + `text-overflow:ellipsis`).

**El humo cambia de prueba.** Comprobar la hoja de estilo fue lo que dio falsa
seguridad: la regla que se verificaba era la que causaba el fallo. A partir de
aquí, el humo **abre** cada menú y comprueba que su primera opción es visible y
que ningún ancestro la recorta (ningún `overflow` distinto de `visible` en la
cadena hasta `body`). La misma prueba se hace sobre el selector de club.

## 2. El selector de club deja de decir «todos sus clubes»

No hay agregado de varias eras y **no puede haberlo**: cada era se compara contra
la liga de sus mismos torneos (ADR-53), así que sumar dos eras de torneos
distintos no tiene sentido. El botón por defecto muestra el club donde más
dirigió, no todos.

- Las pestañas pasan a ser **un botón por club**, en orden cronológico.
- El club donde más dirigió va marcado («donde más dirigió»).
- Ninguna etiqueta promete un agregado. Sustituye a la adenda 5 §4 en este punto;
  todo lo demás de aquel §4 sigue igual (el selector vive dentro de la sección,
  2.0 y 2.2 no lo llevan).
- Un test comprueba que la página **no contiene** la cadena «todos sus clubes».

## 3. Cuatro pies que faltan

- **1.3 (la deriva):** el pie dice que la línea es la media **cruda** de la liga
  en cada torneo y que sube para todos a la vez.
- **2.1 (su carrera):** el pie dice que cada punto es la diferencia contra la
  media de la liga **de ese mismo torneo**, y que la línea del cero es esa media,
  que se recalcula torneo a torneo. Es la respuesta a "¿es un histórico?": no.
- **2.2:** después de «la última franja del campo» va, una vez, «(la última de
  las cinco columnas en que partimos la cancha en 1.1)».
- **2.7 (los medidores):** el pie pasa a decirse en palabras — «cerca de 1 rota
  más que casi todos los equipos de ese torneo; cerca de 0, menos que casi
  todos» — y la palabra *percentil* sale del cuerpo. Se queda en el anexo.

## 4. Tope de palabras

Con datos reales el cuerpo quedó en 2 760 palabras (el tope de la adenda 5 §9 es
2 700). **El tope no sube.** Se recorta el cuerpo hasta caber, sin quitar ninguna
frase con cifra, ningún nivel, ningún condicional de los que protegen la
precisión y ningún hueco declarado. Lo que se recorta es redacción: repeticiones
entre el pie de una figura y la frase que la precede.

## 5. Lo que sigue prohibido

- Agregar métricas de eras de torneos distintos en una sola cifra.
- Cifras que no salgan de nuestros datos; declaraciones de los técnicos; consejos
  a clubes. Todo lo de ADR-59 §3 y las adendas 2 §8, 3 §5, 4 y 5 §7.

## 6. Lo que no cambia

Ninguna cifra, familia, q, veredicto, predicción ni el marcador. El anexo sigue
trayendo cada sección completa. Las lecturas preinscritas de Jardine y sus
guardas siguen igual. Ninguna cifra se teclea. El orden de la adenda 5 §1, la
portada de §2, el simulador paso a paso de §5 y las figuras de §6 se quedan como
están.

## 7. Fuera de esta adenda

- **Desglose del simulador por fase** (el siguiente paquete): enseñar, para una
  transición de zona a zona, cuánto pesa cada uno de los cuatro tableros. Hoy
  `simulador_v2.json` solo exporta el bloque de juego abierto (`conteos_abierto`
  filtra la fase 0 y aborta si encuentra un paso a otra fase), así que **no basta
  con exponerlo**: hay que volver a correr `46_simulador.py` exportando los
  cuatro bloques. Va con su propia adenda.
- **Color de club como acento** (después del desglose): ADR-59 preinscribió un
  solo tono, con la distinción foco/comparación por luminosidad y relleno, no por
  matiz. Relajarlo exige una adenda que diga dónde se admite el matiz (título y
  barra) y dónde sigue prohibido (cualquier figura que ya use la intensidad para
  comunicar, empezando por los mapas de calor).
- **F4 (ADR-62):** red de pases con nombres de quien da y quien recibe.
- **F5:** varias jugadas de ejemplo o un generador de «probabilidad de llegar a
  la última franja empezando en esta zona» (sale de la misma `N` y `h` de ADR-61,
  pero es un dato nuevo por zona y necesita su preinscripción), mapas de calor de
  remates y Voronoi en balón parado.
