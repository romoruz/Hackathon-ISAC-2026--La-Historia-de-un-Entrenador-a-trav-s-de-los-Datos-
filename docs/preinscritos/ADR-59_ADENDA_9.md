# ADR-59 · Adenda 9 — el tope de palabras escala con los clubes

> **Escrita el 2026-09-22**, mientras se construía h2_42 y **antes** de
> commitearlo. Se commitea sola.
>
> **Declaración de contaminación.** Ninguna. Esta adenda no toca datos, figuras
> ni texto: solo cambia **cómo se mide** el tope de palabras del cuerpo.

## 1. El problema

La adenda 8 pide enseñar los clubes del técnico lado a lado, y ADR-63 añade una
sección. Con eso, la historia de Larcamón —que tiene **tres** clubes— queda en
3 384 palabras contra un tope fijo de 3 200, mientras las de dos clubes caben.

Un tope fijo castiga exactamente lo que la adenda 8 acaba de pedir: cuantos más
clubes tiene un técnico, más contenido legítimo tiene su historia. Recortar hasta
caber significaría quitarle a Larcamón lo que sí le cabe a Jardine, y por la
única razón de que dirigió en más sitios.

## 2. La regla

El tope pasa a ser, por historia:

```
tope = 2 900 + 200 × (número de clubes del técnico)
```

Dos clubes → 3 300. Tres clubes → 3 500. Los topes de secciones (≤ 18) y figuras
(≤ 30) no cambian: no escalan porque las figuras nuevas ya traen los clubes
dentro en lugar de repetirse.

**Medido antes de fijarlo**, con los datos sintéticos: Jardine 3 203 (tope
3 300), Larcamón 3 384 (tope 3 500), Ambriz 3 181, Herrera 3 150, Ortiz 3 092.
El margen sobre datos reales es de unas 60 palabras por historia, que es la
diferencia observada entre sintético y real en las cinco entregas anteriores.

## 3. Lo que no cambia

El tope sigue existiendo y sigue siendo el humo quien lo hace fallar. No se
relaja la jerga (adenda 3 §5), ni la regla de no apilar en columnas de más de
doce, ni ninguna otra. Ninguna cifra, familia, q, veredicto, predicción ni el
marcador se tocan.

## 4. Por qué se escribe en vez de subir el número

Subir un número fijo cada vez que no cabe convierte el tope en un trámite. Una
regla que dice **por qué** crece la página se puede defender ante el jurado y
frena igual: si mañana una historia de dos clubes llega a 3 400, sigue fallando.
