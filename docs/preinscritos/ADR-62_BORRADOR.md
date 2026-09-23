# ADR-62 — la red de pases: ¿cambia quién pasa a quién, o solo cambian los jugadores?

> **Escrito el 2026-09-22**, con el receptor de pase ya extraído
> (`data/pases_api/pases.parquet`, h2_44) y **antes de mirar una sola relación
> entre variables**. Se commitea solo, antes del código de medición.
>
> ## Por qué esta preinscripción es distinta a todas las anteriores
>
> ADR-53 a ADR-63 se escribieron sobre datos ya vistos, y por eso lo añadido
> últimamente salió **descriptivo**: la pregunta venía informada por el
> resultado. Aquí no. De la red de pases se sabe, a día de hoy, exactamente
> esto y nada más (h2_43 y h2_44, ambos sin estimandos):
>
> - existe `pass.recipient.id` en los eventos crudos, con ~94% de cobertura;
> - hay 1 256 139 pases con receptor en los 1 530 partidos del universo;
> - el 88.0% son pases completados;
> - cada era tiene entre 154 y 50 408 pases, y entre 14 y 75 jugadores.
>
> Tamaños y cobertura. **Ni una sola relación.** Por eso F62 es una familia con
> hipótesis direccionales, corrección por FDR y entrada al marcador: es la única
> parte del proyecto que se puede preinscribir de verdad, y se aprovecha.
>
> **Compromiso de una sola corrida.** El script de medición se corre **una vez**.
> Si el resultado no gusta, se publica igual. Cualquier segunda corrida con
> parámetros distintos se declara como tal y no entra a F62.

## 1. El objeto

Para cada **era** (club, técnico), la red de pases **completados** entre sus
jugadores: `w_ij` = pases de i a j. Normalizada, `p_ij = w_ij / Σw`, suma 1.

Se usan solo pases completados (el 88%): en un pase fallido, `recipient` es el
destinatario **previsto**, no quien recibió el balón. Meterlos sería contar
intenciones como conexiones.

## 2. Los estimandos

Para cada **pareja de técnicos consecutivos en el mismo club** (las mismas de
`did_h4_v1 › pares`; no se añade ninguna):

- **T_red = ½‖p_a − p_b‖₁**, sobre los jugadores presentes en las dos eras,
  renormalizando a esos jugadores. Va de 0 (idéntica) a 1 (sin una conexión en
  común). Es la misma distancia de variación total que ADR-60 usa para las zonas
  y ADR-63 para los jugadores: la tercera aplicación de la misma vara.
- **ΔG**: diferencia del **Gini** del reparto de pases por jugador entre las dos
  eras. Mide si el juego se concentra en menos pies.
- **φ_U**: parte de T_red atribuible al **uso** (los mismos jugadores
  conectándose distinto) frente a la **composición** (qué jugadores hay), por la
  misma descomposición de ADR-60. **Descriptivo**, sin prueba: se reporta con su
  intervalo y no entra a F62.

## 3. Las hipótesis, con su dirección

Escritas antes de mirar. La tesis del proyecto es que los técnicos **estabilizan
un sistema** en vez de refundarlo; estas tres son su consecuencia comprobable, y
las tres pueden fallar.

- **H62-1.** Al cambiar de técnico, **T_red no supera** lo que se mueve la red
  **sin** cambiar de técnico (el nulo de §4) en la mayoría de los relevos.
  *Dirección: T_red ≤ percentil 90 del nulo.*
- **H62-2.** **ΔG no se separa del cero** en la mayoría de los relevos: la
  concentración del juego no es una firma del técnico.
  *Dirección: el intervalo de ΔG incluye el cero.*
- **H62-3.** **φ_U < 0.5** en la mayoría de los relevos: más de la mitad del
  cambio de red viene de que cambian los jugadores, no de que los mismos se
  conecten distinto. *Descriptiva, no entra a F62, pero se predice igual y se
  evalúa en el marcador como predicción de nivel C.*

Si H62-1 falla —si la red se mueve más de lo normal cuando cambia el técnico—
**es un hallazgo contra nuestra propia tesis y se publica en el cuerpo de la
página, no en el anexo**.

## 4. El nulo: qué se mueve una red sin cambiar de técnico

Por permutación, **a nivel de partido** (no de pase, porque los pases del mismo
partido no son independientes): dentro de cada club, se mezclan las etiquetas de
era entre los partidos de las dos eras del relevo, respetando el número de
partidos de cada una, y se recalcula T_red. **B = 2 000** permutaciones, semilla
fija declarada en el JSON.

Esto da, para cada relevo, su propia distribución nula. El p es la proporción de
permutaciones con T_red mayor o igual que el observado.

## 5. Familia y corrección

- **F62 = (relevos evaluables de las cinco historias) × {T_red, ΔG}.**
- Benjamini–Hochberg al **5%**, sobre F62 y solo sobre F62.
- φ_U queda fuera de la familia.
- Los relevos de clubes que no son de las cinco historias se miden y se publican
  en el anexo **como contexto descriptivo**, fuera de F62.

## 6. Quién entra (umbrales fijados con los tamaños de h2_44, antes de medir)

- **D62-1.** Una era entra si tiene **≥ 3 000 pases completados** y **≥ 20
  jugadores**. Con los tamaños observados, esto deja fuera las eras de paso
  (interinatos de uno o dos partidos: 154, 195, 264, 315, 332, 442, 456, 509,
  523, 552, 580, 777, 792, 855, 894, 908 pases) y conserva todas las eras de las
  cinco historias, que van de 9 793 a 50 408 pases.
- **D62-2.** Un jugador entra en la red de una era si da o recibe **≥ 100 pases**
  en ella.
- **D62-3.** Un relevo entra en F62 si las dos eras pasan D62-1 y comparten
  **≥ 8 jugadores** que pasen D62-2 en las dos.
- Un relevo que no pase D62-3 **se declara con su cifra**, no se omite.

## 7. Sesgos que se declaran en la página

1. **El 12% de los pases no se cuenta** (los fallidos), y ~6% de los pases no
   trae receptor. La red es de pases completados, y eso se dice.
2. **El portero infla las conexiones largas**: un saque de meta es un pase como
   cualquier otro en esta red. No se excluye —excluirlo sería una decisión no
   preinscrita— pero se reporta qué parte de cada red pasa por el portero.
3. **Los jugadores cambian entre eras.** Es precisamente lo que φ_U separa, pero
   φ_U es descriptivo: no se afirma causa.
4. **Un relevo a mitad de torneo** mezcla contextos (rival, calendario). Igual
   que en ADR-53, cada era se compara solo con la otra del mismo club.

## 8. Lo que NO se hace

- **No se atribuye intención.** Nunca "el técnico decidió jugar por fuera". La
  red describe conexiones, no órdenes.
- **No se nombra un sistema táctico** (4-3-3, etc.) a partir de la red.
- **No se juzga a un jugador.** Un jugador con pocas conexiones no es peor.
- **No se compara con otras ligas** ni con nada que no midamos.
- **No se usa centralidad de vector propio ni PageRank**: son fáciles de pintar y
  difíciles de interpretar sin un modelo de qué es "importante". Si se quisieran,
  irían en otra ADR con su justificación.

## 9. Salida

`scripts/50_red_pases.py` → `reports/red_pases_v1.json`:

```
parametros  {B, seed, umbral_pases_era, umbral_jugadores_era, umbral_pases_jugador,
             min_jugadores_comunes, solo_completados: true}
relevos[]   {club, a, b, en_f62, hueco?,
             n_jugadores_comunes, n_pases_a, n_pases_b,
             T_red {v, p, q, rechaza, nulo_p50, nulo_p90},
             gini {a, b, delta, ic95, p, q, rechaza},
             phi_U {v, ic95},            # descriptivo, fuera de F62
             portero {parte_a, parte_b}} # sesgo 2
familia     {m, n_rechazados}
predicciones[] {n, texto, cumple}        # H62-1, H62-2, H62-3
```

## 10. Guardas (el script aborta si fallan)

- **D62-4.** Cada `p` de la red suma 1 a 1e-9.
- **D62-5.** `T_red ∈ [0, 1]` y `φ_U ∈ [0, 1]`.
- **D62-6.** El número de contrastes de F62 es exactamente 2 × (relevos que pasan
  D62-3 en las cinco historias). Si no, aborta.
- **D62-7.** Ningún partido cae en las dos eras de un relevo.
- **D62-8.** La semilla y B quedan escritos en el JSON. Una segunda corrida con
  otros valores se marca `corrida: 2` y **no** entra a F62.
- **D62-9.** El script aborta si `data/pases_api/pases.parquet` no existe o si su
  cotejo (`reports/pases_cotejo.json`) no está.

## 11. Fuera de ADR-62

Voronoi y mapas de remate (F5); el desglose del simulador por fase; el color de
club como acento. Y cualquier medida de la red que no esté en §2: si después de
ver esto se nos ocurre otra, va en otra ADR y nace descriptiva, como debe ser.
