# ADR-61 · Adenda 1 — llegar a la última franja, en todos sus clubes

> **Escrita el 2026-09-22**, después del tercer ensayo (`docs/ensayos/2026-09-22c.md`)
> y **antes** del código. Se commitea sola.
>
> **Declaración de contaminación.** Los resultados de ADR-53 a ADR-61 ya se vieron,
> incluidos los diez contrastes de F61. Por eso lo que esta adenda añade **no es
> una prueba**: son estimaciones descriptivas con su intervalo, **fuera** de la
> familia, sin p, sin q y **fuera del marcador**. F61 no cambia: siguen siendo los
> mismos 10 contrastes sobre las 5 eras principales, con los mismos q y los mismos
> veredictos. Si alguno cambiara, el script aborta (§4).
>
> **Motivo.** En la página de Larcamón, la figura de 2.2 comparaba a los cinco
> técnicos del proyecto (América·Jardine, Puebla·Larcamón, Toluca·Ambriz,
> Tigres·Herrera, América·Ortiz) porque eso era lo único medido. El lector está
> viendo a Larcamón y espera sus tres clubes. La figura no mentía, pero
> respondía a otra pregunta.

## 1. Qué se añade

Para **cada era** de las cinco historias (no solo la principal), con la misma
función `mide_era` y la misma base de comparación (la liga de los mismos torneos,
λ = 0):

- `L` = α′h, probabilidad de llegar a la última franja del campo;
- `τ` = (α′N_oo h)/(α′h), acciones hasta llegar, condicionado a llegar;
- `D_L = log(L_era / L_base)` y `D_τ = log(τ_era / τ_base)`;
- intervalo bootstrap por partido, estratificado por torneo, **con el mismo
  B = 4000 y la misma semilla** que las principales; intervalo básico en log.

## 2. Qué NO se añade

- **Ni p ni q.** No se calcula el p por inversión para las eras nuevas, y no
  entran a la corrección BH. F61 sigue siendo 5 eras × {D_L, D_τ} = 10.
- **Nada al marcador.** Ninguna predicción se evalúa con estas eras.
- **Ninguna lectura preinscrita.** Las guardas de Jardine siguen sobre su era
  principal y solo sobre ella.
- **Ninguna jugada de ejemplo** para las eras nuevas (D61-7 sigue solo para la
  principal, y en la página se va al anexo — ADR-59 adenda 7 §3).

## 3. Cómo se dice en la página

Cada era no principal va marcada **descriptiva** y lleva, pegada, la frase fija:

> "Esta no estaba en la lista de pruebas escrita antes de mirar: se mide igual,
> pero se lee como una descripción, no como un hallazgo."

La figura de 2.2 pasa a mostrar **los clubes del técnico que se está viendo**, en
orden cronológico, con la era principal marcada. La comparación entre los cinco
técnicos se conserva completa en el anexo, que es donde tiene sentido.

## 4. Guardas (el script aborta si fallan)

- **D61A-1.** Las cinco eras principales reproducen, con este código, exactamente
  los mismos `L`, `τ`, `D_L`, `D_τ`, `p`, `q` y `rechaza` que `progresion_v1.json`
  (tolerancia 1e-9 en los estimandos y **igualdad exacta** en los veredictos). Si
  no, aborta: la adenda no puede mover un resultado publicado.
- **D61A-2.** `|F61| = 10` después del cambio. Si el conteo cambia, aborta.
- **D61A-3.** Una era con menos de **200 posesiones** no se mide; se declara el
  hueco con su cifra. El umbral se fija aquí, antes de mirar.
- **D61A-4.** Si para una era el bloque no es irreducible o `L = 0` en la era o en
  la base, se declara no evaluable con su motivo, como ya hace §5 de ADR-61.

## 5. Coste

El bootstrap se multiplica por el número de eras (de 5 a ~12). El script imprime
el tiempo por era y admite `--solo-principales` para volver al comportamiento de
h2_35 sin tocar nada.

## 6. Salida

`progresion_v1.json` gana, por historia, una lista `eras_todas[]` con la misma
forma que `eras[]` más `principal: bool` y `exploratoria: bool`. La clave `eras[]`
**no cambia**: sigue trayendo las cinco principales con sus q y sus veredictos,
para que nada que ya lea ese archivo se entere del cambio.
