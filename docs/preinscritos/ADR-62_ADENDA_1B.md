# ADR-62 · Adenda 1b — un solo tamaño de bloque

> **Escrita el 2026-09-22**, después de escribir el código del placebo y **antes
> de correrlo ni una vez**. Corrige un sesgo de la adenda 1 §4 que se encontró
> probando el dimensionado de los bloques, no mirando resultados: el placebo no
> se ha ejecutado todavía.
>
> Se commitea sola, antes del código.

## 1. El sesgo

La adenda 1 §4 fijaba `m = min(k_a, k_b)` para el relevo, y para el placebo de
cada era "primeros m contra últimos m **si la era tiene ≥ 2m partidos; si no, la
mitad por lado**".

Esa última cláusula rompe la comparación. Ejemplo real del universo:
`América · Jardine (100 partidos) ↔ Ortiz (43)`. El relevo compararía bloques de
**43 contra 43**, pero el placebo de Ortiz, que no llega a 86 partidos, usaría
**21 contra 21**. Bloques más pequeños tienen menos pases, y con menos pases la
distancia `T` sube **por ruido muestral**, no porque el juego cambie.

Consecuencia: la distribución de placebos queda inflada, su percentil 90 sube, y
al relevo le cuesta más superarlo. El sesgo empuja hacia **retirar H62-1**.

Que empuje hacia el lado conservador no lo hace aceptable: es un sesgo conocido
y evitable, y si se deja, el resultado no se puede defender en ninguna de las dos
direcciones.

## 2. La corrección

**Un solo tamaño de bloque para todo**, relevo y placebos:

```
m = min(k_a // 2, k_b // 2)        y m ≥ 5
```

Así las dos eras caben siempre en dos bloques de tamaño `m` sin solaparse, y las
tres comparaciones —el relevo y los dos placebos— usan exactamente el mismo
número de partidos por lado.

- **T_relevo(m)**: últimos `m` partidos de la era *a* contra primeros `m` de la
  era *b*.
- **T_placebo(m)**: en cada era, primeros `m` contra últimos `m`.

Todo lo demás de la adenda 1 sigue igual: `m ≥ 5`, ≥ 30 pases por jugador en cada
bloque, ≥ 8 jugadores comunes, nivel B, fuera de F62, y el criterio de decisión
del §5 **sin tocar** (H62-1 aguanta si `T_relevo` supera el p90 de los placebos
en más de la mitad de los relevos comparables).

## 3. Lo que cuesta

Con `m = min(k_a//2, k_b//2)`, un relevo entre una era larga y una muy corta
puede dejar de ser comparable: `k_a = 12, k_b = 6` daba `m = 6` y ahora da
`m = 3`, por debajo del mínimo. **Se pierden relevos de cobertura a cambio de que
los que quedan sean comparables de verdad.** Cuántos se pierden se reporta en el
JSON y se dice en la página.

## 4. Por qué se puede cambiar ahora y no después

Porque el placebo **no se ha corrido**. El cambio no puede estar informado por su
resultado. Este es el único momento en que esta corrección es legítima; una vez
haya números, cualquier ajuste del dimensionado sería elegir el que guste.

Queda anotado que la adenda 1 se escribió con el sesgo dentro y que se detectó al
implementarla. El orden correcto habría sido dimensionar antes de firmar.
