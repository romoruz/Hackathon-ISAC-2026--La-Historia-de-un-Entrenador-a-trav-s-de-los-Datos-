# ADR-59 · Adenda 5 — primero el técnico, después el método

> **Escrita el 2026-09-22**, después del **segundo ensayo** con dos lectores
> ajenos (registro en `docs/ensayos/2026-09-22b.md`) y **antes** del código de
> h2_38. Se commitea sola, antes del código.
>
> **Declaración de contaminación.** Todos los resultados de ADR-53 a ADR-61 ya
> se vieron. Como las adendas 3 y 4, esta **solo cambia la presentación**: el
> orden de la página, la navegación, cómo se explica el método y cómo se
> dibujan cuatro figuras. No cambia ninguna cifra, familia, q, veredicto,
> predicción ni el marcador, y no añade contrastes.
>
> **Motivo.** El segundo ensayo encontró que: la página abre con el método y
> no con el técnico; el selector de club no responde en algunos clubes; la
> barra de navegación se pierde; no se explica el espacio de estados (solo los
> finales); el simulador enseña todo de golpe y no se entiende qué es el mapa
> de calor; no se dice de quién es la línea de 1.3; "franja del área" no se
> reconoce como una de las zonas de la malla; y la figura de 2.2 parece
> interactiva sin serlo.

## 1. Orden de la página

```
portada        quién, qué hicimos en cinco líneas, y las tres conclusiones
la historia    su carrera club por club y las evidencias (lo que era el acto 2 y 3)
el método      cómo se lee una posesión, el simulador y contra qué comparamos
¿nos creen?    marcador y límites
anexo          todo lo técnico, como hasta ahora
```

El método (lo que la adenda 3 llamaba "primero") pasa **después** de la
historia, con el rótulo "Cómo lo hicimos, si te interesa". Ninguna sección
cambia de contenido por moverse: son las mismas funciones.

## 2. Portada

Tres bloques fijos, iguales para las cinco historias:

1. **Nombre del técnico y sus clubes**, cada uno con sus torneos y partidos
   ("Puebla · 51 partidos · A2021–A2022"). El título ocupa a lo sumo un tercio
   de la primera pantalla.
2. **Qué hicimos, en cinco líneas**, con cifras que salen de los JSON: cuántos
   clubes, torneos y posesiones se analizaron; que cada posesión se modela como
   una cadena que va de zona a zona hasta gol, remate, pérdida o balón fuera;
   que cada época se compara contra la liga del mismo torneo; que las hipótesis
   se escribieron antes de mirar; y el marcador (cuántas predicciones se
   cumplieron de cuántas).
3. **Las tres conclusiones** de la adenda 4 §2, que suben aquí desde la sección
   de carrera, con su enlace a la evidencia que las sostiene.

## 3. Navegación

Una sola barra, **siempre visible** (fija arriba), compacta:

- el técnico, como menú desplegable (no cinco botones sueltos);
- "ir a", como menú desplegable con las secciones de la página;
- nada más. **El selector de club sale de la barra** (§4).

La barra no puede desbordarse: si no cabe, los menús se cierran en un botón.
El humo comprueba, al ancho de 1280 y de 1024, que todos los controles de la
barra están dentro de ella y que ningún otro elemento los tapa.

**Todo control se ve que es un control.** Cualquier botón o pestaña lleva
`cursor: pointer` y un realce al pasar el mouse y al enfocarlo con el teclado.
El segundo ensayo dio el selector por roto cuando en realidad respondía: no
había ninguna señal de que se pudiera tocar. Un test comprueba que ningún
control de la página se queda sin `cursor: pointer`.

## 4. Selector de club, local

Se quita el selector global de club. La otra mitad del problema del ensayo era
que, al cambiar de club desde la barra, lo que cambiaba quedaba fuera de la
pantalla: arriba todo seguía igual. Con el selector dentro de la sección, el
cambio ocurre donde el lector está mirando. La página habla del técnico **en
todos sus clubes**. En las secciones donde comparar por club aporta y el dato existe
(duración y zonas, ocasiones y territorio, sin el balón, contexto, balón
parado, jugadores), va un selector **dentro de la sección**, con sus clubes y
la opción "todos". Las secciones sin dato por club no lo llevan; llegar al
área (2.2) sigue siendo solo del club donde más dirigió y lo dice.

## 5. El método, explicado de verdad

- **El espacio de estados.** La sección dice, con sus cifras: el campo se parte
  en **20 zonas** (5 franjas de ancho × 4 de largo) y cada posesión arrastra
  **la forma en que empezó** (4), así que la cadena tiene **80 estados vivos**
  y 4 finales. Se dice por qué la malla es 5×4: con una malla más fina, el
  número de parámetros por observación pasa de 0.5 en la era más chica
  (decisión P-02 del proyecto). La cita va con su fuente.
- **Qué es una probabilidad de paso.** Un ejemplo con datos de la liga: desde
  una zona concreta, a dónde va el balón en la siguiente acción y con qué
  frecuencia, y cuántas veces la posesión termina ahí. Es el mismo conteo que
  usa el simulador.
- **Simulador paso a paso (1.2).** Una acción por clic:
  - se elige la zona de inicio tocando la cancha;
  - cada clic en "una acción más" mueve el balón a **una** zona, dibuja esa
    flecha con su probabilidad y deja el rastro de las anteriores;
  - cuando la posesión termina, lo dice (gol, remate, pérdida o fuera) y
    ofrece "otra jugada";
  - "de dónde viene y a dónde va" y "a la larga" quedan como dos vistas
    aparte, cada una con una línea que explica qué son sus porcentajes:
    en la primera, de cada 100 balones que pasan por esa zona; en la segunda,
    dónde está el balón en las posesiones que ya duraron mucho.
  - La leyenda de jugada inventada por el modelo (adenda 4 §5) se mantiene.

## 6. Figuras

- **2.1:** una sola línea de tiempo con **todos** los torneos del técnico, en
  orden, con una línea vertical donde cambia de club y el nombre del club
  encima de cada tramo. Sustituye a la serie de un solo club.
- **2.2:** barras horizontales en lugar de deslizadores. Cada era: una barra
  del intervalo, una marca gruesa en el valor y una línea vertical en el cero.
  Nada que parezca arrastrable.
- **1.3:** el título de la figura dice de quién es la línea ("todos los clubes
  de la liga, torneo a torneo") y la banda lleva su rótulo pegado ("diferencia
  normal entre clubes").
- **Nombres:** "franja del área" se llama, en toda la página, **"la última de
  las cinco franjas del campo"**, y la figura la marca sobre la cancha.

## 7. Lo que sigue prohibido

- Cifras que no salgan de nuestros datos. Nada de comparaciones con otras
  ligas o mundiales que no midamos.
- Declaraciones de los técnicos sobre su idea: contrastar lo que dicen con lo
  que hacen es atribuir intención.
- Consejos a clubes ("si lo contratas, espera…"): es recomendación, no
  descripción.
- Todo lo de ADR-59 §3 y las adendas 2 §8, 3 §5 y 4.

## 8. Lo que no cambia

Ninguna cifra, familia, q, veredicto, predicción ni el marcador. El anexo
sigue trayendo cada sección completa. Las lecturas preinscritas de Jardine y
sus guardas siguen igual. Ninguna cifra se teclea.

## 9. Topes

Por historia, en el cuerpo: ≤ 2 700 palabras (suben 200 por la portada y el
método explicado), ≤ 16 secciones y ≤ 18 figuras. Sigue prohibida la jerga de
la adenda 3 §5 y sigue vigente la regla de que nada se apila en una columna de
más de doce.

## 10. Fuera de esta adenda

- **F4 (ADR-62):** red de pases con **nombres de quien da y quien recibe** y
  el tipo de acción. El segundo ensayo lo pidió; los datos lo permiten
  (`pass_recipient_id` en los eventos). Va con su ADR y sus predicciones.
- **F5:** mapas de calor de dónde rematan y reciben remates, y Voronoi en
  balón parado.
- Cambiar el elenco de cinco historias por una sola protagonista: **no**. Las
  cinco se miden con la misma vara; elegir papeles narrativos sería escoger la
  conclusión antes del dato.
