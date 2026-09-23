# ADR-59 · Adenda 10 — la red de pases en la página, sin resolver

> **Escrita el 2026-09-23**, después de ADR-62 adenda 1c y antes de tocar el
> generador. Se commitea sola, antes del código.
>
> Fija cómo entra F62 a la página. Todo lo que se puede decir ya lo decidió la
> adenda 1c. Esta adenda solo dice dónde va, con qué palabras y con qué topes.

## 1. Dónde va

Una sección nueva **en el cuerpo**, común a las cinco historias, en el cierre:
**C.2 «¿Cambia quién le pasa el balón a quién?»**, entre «¿Nos creen?» y
«Límites», que pasa a ser C.3. La adenda 1 §5 de ADR-62 pide el resultado en el
cuerpo y no en el anexo, y se cumple.

Va en el cierre y no en cada historia porque la prueba es una sola familia sobre
los relevos de las cinco historias, y porque lo que hay que contar es el mismo
para todas: que no se resolvió.

## 2. Qué dice el cuerpo, en este orden

1. Qué se miró: quién le pasa el balón a quién, en los relevos de las cinco
   historias, y que es la única parte escrita antes de ver un solo dato.
2. Que la primera prueba marcó cambio en todos los relevos y por qué era
   injusta: comparaba dos épocas seguidas contra mezclas de partidos de
   cualquier fecha.
3. Que la segunda prueba tenía un error nuestro (cuántos relevos quedaron al
   revés), que no se repitió y por qué, y la frase literal: **«No sabemos si la
   red cambia más cuando cambia el técnico.»**
4. De qué está hecho el cambio (φ_U, sin nombrarlo): en cuántos relevos más de
   la mitad viene de que los mismos jugadores eligen a otros compañeros, y si
   eso era lo que esperábamos.
5. La frase de no-causalidad: dice de qué está hecho el cambio, **no quién lo
   causó**; puede ser el técnico o el paso del tiempo.
6. **Una figura**: un punto por relevo sobre una recta de 0 a 1, con la marca de
   la mitad. Sin flecha entre técnicos: φ_U no tiene dirección, y el orden de
   los pares del acta no es cronológico (fue el fallo 3).

Todo es **nivel C**. Ninguna cifra va tecleada.

## 3. Qué NO dice el cuerpo

- Ninguna de las dos frases del §5 de la adenda 1 de ADR-62 («la red se mueve
  más cuando cambia el técnico» / «se mueve lo mismo cambie o no»).
- Nada que atribuya el cambio de red al técnico.
- Las palabras «placebo» y «percentil», ni el 11 de 30 de la prueba con el error.

## 4. El anexo («C.2 · cómo lo medimos»)

La corrida única completa: la tabla de los relevos (T, lo que daba el nulo, ΔG y
su intervalo, φ_U); la familia y cuántos rechazan, marcados como resultado de
una prueba injusta; H62-2 con la advertencia de que su nulo comparte el defecto;
la prueba por tramos con su resultado **y la leyenda «tiene el error dentro y no
se lee»**; el aviso de `red_pases_v1 › aviso_phi_U`; y el catálogo de los cuatro
fallos de F62 de la adenda 1c §5.

## 5. El marcador

ADR-62 entra al marcador, como dice su preámbulo. **H62-1 entra como «no se pudo
evaluar»** (adenda 1c §3), H62-2 y H62-3 como salieron. Cambian por eso los
totales de C.1 y del anexo; el recuadro «ADR-53 a 58» no cambia.

## 6. El conteo de relevos al revés

Sale de `reports/placebo_red_fallo.json`, que escribe `52_fallo_orden.py`. Ese
script **no calcula ninguna distancia**: lee las fechas de los parquets y el
acta del placebo y cuenta qué pares estaban al revés. Se corre antes de
commitear, para comprobar que las cifras de la adenda 1c (24 al revés, 13 sin T)
son las del acta. Si no cuadran, no se commitea nada.

## 7. Topes

La sección C.2 lleva **su propio tope, contado aparte**: 220 palabras y una
figura. Los topes generales (2 900 + 200 por club, 18 secciones, 30 figuras) no
cambian y **no cuentan esta sección**.

Por qué aparte y no subiendo el general: la adenda 9 §4 dice que un tope no se
sube a mano cada vez que algo no cabe. Esta sección es contenido nuevo que ADR-62
obliga a poner en el cuerpo, y su tope propio impide que crezca a costa de las
historias o que las historias crezcan a su costa.

## 8. El humo comprueba

La sección existe y está en el cierre; dice «No sabemos si la red cambia más
cuando cambia el técnico», «error nuestro» y «no quién lo causó»; no contiene las
frases del §3; un punto por relevo; su tope aparte; y en el anexo, la marca «no
se lee» junto a la prueba con el error.
