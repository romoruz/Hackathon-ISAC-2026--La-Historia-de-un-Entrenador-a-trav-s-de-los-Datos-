## 7. Limitaciones y contrastes: estado actualizado

> **Instrucción**: reemplazar la sección 7 completa de `03_METHODS.md` (desde
> `## 7. Limitaciones y contrastes pendientes` hasta antes de
> `## 8. Referencias`) por este texto. La versión anterior decía que el supuesto
> de Markov no había sido testeado, lo cual dejó de ser cierto el 2026-08-20.

Se enuncian explícitamente. Un modelo cuyas limitaciones no se declaran no es
evaluable.

### 7.1 El supuesto de Markov FUE testeado y se RECHAZA

En vez del contraste orden 1 contra orden 2 que se planeaba —inviable por número
de parámetros con la muestra disponible— se usó un contraste **global**.

La cadena implica analíticamente la distribución del número de pasos hasta
absorción, que es **phase-type discreta**:

$$P(T > k) = \alpha^\top Q^k \mathbf{1}$$

Comparada contra la empírica por Kolmogorov–Smirnov, con nula calibrada por
bootstrap paramétrico tipo Lilliefors (los parámetros se estiman de los mismos
datos, así que la nula estándar de KS no aplica) y condicionando a
$T \geq$ `min_actions`:

| unidad | $n$ posesiones | KS | p95 nulo | $p$ | sesgo $E[T]$ |
|---|---|---|---|---|---|
| Jardine | 8,694 | 0.087 | 0.012 | 0.005 | +1.82% |
| Solari | 3,680 | 0.104 | 0.019 | 0.005 | +1.93% |
| América | 16,505 | 0.098 | 0.010 | 0.005 | +1.68% |

**Rechaza.** El patrón es idéntico en las tres unidades: menos masa en el centro
($k=2$–$10$), más en la cola ($k\geq12$), cruce en $k\approx11$, media casi
perfecta.

No es memoria simple sino **sobredispersión**: la firma de una mezcla. Hay al
menos dos poblaciones de posesión que el estado $(z,\phi)$ no distingue.

**Por qué el modelo se mantiene (ADR-21):**

1. El contraste de la Fase 3 compara dos cadenas ajustadas de la misma manera;
   una mala especificación **compartida** se cancela en buena medida. Como el
   patrón es idéntico en las tres unidades, esa premisa es **verificable**.
2. La nula del LRT se calibra por bootstrap (§4.3), no por $\chi^2$, así que no
   depende de la especificación.
3. Se midió el impacto: bajo un generador de mezcla la cobertura de los IC cae
   de 0.944 a 0.938. Prácticamente nada.

**Dónde sí bloquea**: la Fase 7 (simulación). Las longitudes simuladas estarán
mal distribuidas aunque la media coincida. La validación por KS del simulador
fallaría, y ya se sabe por qué.

**Cuidado metodológico que costó una iteración.** `min_actions` hace
$P(T<2)=0$ por construcción mientras la cadena le asigna 13% de masa. En la
primera versión del contraste **el estadístico KS completo venía del punto
$k=1$**: el test medía el truncamiento, no el ajuste. Hubo que comparar contra
la phase-type **condicionada**.

### 7.2 El modelo describe solo la fase con balón

La firma defensiva de un entrenador es igual de identificatoria y hoy está
ausente. Es la Fase 5 del roadmap.

### 7.3 Las duraciones se ignoran

El modelo es de tiempo discreto en número de acciones, no en segundos. Dos
equipos con la misma matriz pero ritmos distintos son indistinguibles. La
columna `duration` se conserva para la extensión semi-Markov (Fase 6).

El rechazo de §7.1 refuerza el caso: la distribución de longitud está mal
ajustada, y modelar los tiempos de permanencia es una vía para arreglarlo.

### 7.4 Decisiones de preprocesamiento: dos de tres cuantificadas

1. **Resolución de la malla** — ✅ **RESUELTO**. Barrido sobre
   $\{4\times3, 5\times4, 6\times4, 6\times5\}$. Los efectos grandes entre
   entrenadores son invariantes (±0.8 pp entre 12 y 30 zonas). La malla queda en
   $5\times4$: $6\times4$ da `params_per_obs` = 0.502 sobre la era más chica
   (Ortiz), por encima del umbral de 0.5.
2. **Encogimiento $\lambda$** — ✅ **RESUELTO**. La curva de CV es una meseta
   (0.006 nats entre $\lambda=100$ y $\lambda=2000$): **$\lambda$ no está
   identificado**. Y por álgebra sobre el estimador de la diferencia,
   $\hat p^* - \hat p_{base} = \frac{n_i}{n_i+\lambda}(\hat p^{MLE} - \hat p_{base})$,
   la magnitud reportada está atenuada por un factor que varía por renglón
   (0.585 con $\lambda=500$). **Regla: significancia con $\lambda^*$, magnitudes
   con $\lambda=0$** (ADR-22).
3. **Umbral de acarreos** (`min_carry_length = 5.0 m`) — ❌ **PENDIENTE**. Es la
   única sensibilidad del plan original que sigue sin reportarse.

   Nota: ya se sabe que **no puede** explicar las auto-transiciones. El 60% de
   ellas vienen de **pases**, que ningún umbral de acarreo toca. Y el 49–50% de
   los acarreos que sobreviven al filtro siguen sin salir de zona, así que el
   umbral de 5 m es cosmético a resolución $5\times4$.
4. **Agrupamiento de fases** — ❌ pendiente, baja prioridad. Las proporciones son
   estables entre dos clubes (`set_piece` 14.8% vs 14.6%), lo que sugiere que la
   agrupación captura algo del formato y no un artefacto de un equipo.

### 7.5 Validación externa: parcial

**Disponible y no usada**: contrastar $B_{\cdot,\text{GOAL}}$ contra
`shot_statsbomb_xg` agregado por zona, y contra `obv_*` (métrica propietaria de
StatsBomb). Es barato y sigue pendiente.

**Contraste grueso ya hecho**: $\bar{xT} = 0.0130$ contra una tasa de gol
empírica de ~1.6% por posesión. Mismo orden de magnitud sin ajuste. Es
sugerente, no concluyente.

### 7.6 Las fronteras de era son sintéticas, no documentales

Las fechas no provienen del API sino de una **derivación** de la estructura de
bloques de `match_id` (ADR-26): los bloques de ~17 partidos son torneos
regulares, y se asignan fechas repartidas dentro del calendario real de cada
torneo.

La cobertura resultante coincide con Wikipedia en ocho entrenadores de dos
clubes, con error máximo de 2–3 partidos concentrado en las fronteras a media
temporada. Una era de diez días con dos partidos queda exactamente ubicada.

**El supuesto frágil** es que dentro de un bloque el orden de `match_id`
aproxima el orden de jornada. No verificado. Afecta a los cambios de DT a media
temporada: **uno** en el América, **cuatro** en Cruz Azul.

**`detect_regime_changes` NO sirve para verificarlas.** Se construyó una prueba
placebo por permutación (`02_placebo_regimes.py`) y mostró que los quiebres que
detecta caen en fronteras de **torneo** —pretemporada, fichajes, rotación— no de
entrenador. Ninguna frontera documental aparece en el top 15. La afirmación se
retiró.

### 7.7 La amenaza viva: rotación de plantilla

Comparar eras dentro del mismo club controla institución, presupuesto, cantera,
estadio y calendario. **No controla rotación de plantilla.** Un DT que llega con
seis fichajes no es comparable con su predecesor.

Es la limitación más seria que queda. Es cuantificable —el dataset trae
`player_id`, así que se puede medir el solapamiento de minutos entre eras— y no
se ha hecho.

### 7.8 Lo que el modelo no puede afirmar

- Que un DT sea **mejor** que otro: se mide estilo, no rendimiento. Y ninguna
  diferencia en $P(\text{gol})$ resultó significativa.
- Causalidad: se detecta que una era difiere de otra, no que el DT sea la causa.
- Resultados de partido: se predicen transiciones, y la distancia entre eso y
  ganar es grande.
