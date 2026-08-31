# 11 — La matemática, explicada

> `03_METHODS.md` dice **qué** matemática se usa. Este documento dice **por qué
> funciona**, **dónde entra en el código** y **qué número produjo**.
>
> Escrito para dos lectores: alguien que tenga que defenderlo ante un jurado, y
> una IA que retome el proyecto sin contexto previo.

---

## 0. El mapa

| Objeto | Curso | Archivo | Qué produjo |
|---|---|---|---|
| Factorización de la verosimilitud | Inferencia | `estimate.mle` | legitima usar multinomial sobre datos secuenciales |
| Serie de Neumann | Análisis | `absorbing.fundamental` | $N$ existe porque $\rho(Q)=0.833<1$ |
| Encogimiento (James–Stein) | Inferencia | `estimate.shrink` | λ\*=500; +5% de perplejidad OOS |
| CV por bloques | Simulación | `estimate.cv_lambda` | la meseta que desidentifica λ |
| LRT simple vs compuesta | Inferencia | `inference.g2_rows` | 80/80 rechazos → ADR-25 |
| Bootstrap por bloques | Simulación | `inference.bootstrap_diff` | IC: +22.4% [18.6, 26.4] |
| KS + Lilliefors | Simulación | `03_bondad_ajuste_longitud.py` | Markov rechazado |
| Phase-type discreta | Procesos | mismo script | $P(T>k)=\alpha^\top Q^k\mathbf{1}$ |
| Permutación | Simulación | `10_nula_contextos.py` | la adaptación al marcador es real pero chica |
| Benjamini–Hochberg | Inferencia | `inference.benjamini_hochberg` | FDR por etapas |
| Variación total | Probabilidad | `09_huella_efecto.py` | la huella ordenada por magnitud |
| Transporte óptimo ($W_1$) | Prog. lineal | Fase 8, **no implementado** | — |

---

## 1. La cadena absorbente: qué son los estados y por qué

### El espacio de estados

Se parte el campo en una malla de $n_x \times n_y = 5\times 4 = 20$ zonas, y
cada zona se cruza con **cuatro fases de juego** (`open`, `transition`,
`restart`, `set_piece`). Eso da

$$\mathcal{S}_{\text{trans}} = \{(z, \phi)\} \quad\text{con}\quad |\mathcal{S}_{\text{trans}}| = 20 \times 4 = 80$$

Estos 80 son los **estados transitorios**: la posesión puede entrar y salir de
ellos cuantas veces quiera.

### Los cuatro estados absorbentes

$$\mathcal{S}_{\text{abs}} = \{\text{GOAL},\ \text{SHOT\_NOGOAL},\ \text{LOSS},\ \text{OUT}\}$$

**Absorbente significa que una vez que entras, no sales:** $p_{aa}=1$ para todo
$a\in\mathcal{S}_{\text{abs}}$. Modelan los cuatro finales posibles de una
posesión. Son cuatro y no dos porque un tiro fallado y una pérdida en el medio
campo son sucesos tácticamente distintos, y colapsarlos perdería información
(ADR-03).

El espacio total tiene $84$ estados, y la matriz tiene la estructura canónica

$$P = \begin{pmatrix} Q & R \\ \mathbf{0} & I \end{pmatrix}$$

- $Q$ es $80\times 80$: transitorio → transitorio.
- $R$ es $80\times 4$: transitorio → absorbente.
- La fila inferior dice que de un absorbente no se sale.

En el código solo se guardan las 80 primeras filas ($Q$ y $R$ juntas, $80\times
84$), porque la parte $(\mathbf{0}\ I)$ es constante.

### Qué es una "transición"

Cada **acción con balón** (pase, acarreo, tiro) genera **una** transición de su
zona de inicio a su zona de fin (ADR-15). Una posesión de 7 acciones aporta 7
transiciones, la última hacia un absorbente.

**Consecuencia no anticipada**: un pase de 6 metros dentro de una zona de
24×20 m es una transición $i\to i$. De ahí que el **28% de las transiciones sean
auto-transiciones**, y que el 40% de $E[T]$ sea permanencia en zona. Medido en
`05_auto_transiciones.py`.

### Por qué toda posesión termina

Si $\rho(Q) < 1$ (radio espectral), la probabilidad de seguir en estados
transitorios tras $k$ pasos, que es $\|Q^k\|$, tiende a cero. **Toda posesión
absorbe casi seguramente.**

En los datos: $\rho(Q) = 0.8333$ para Jardine. `absorbing.check` lo verifica en
cada corrida y **aborta si falla**, porque el encogimiento puede crear renglones
patológicos.

Para forzarlo, ADR-14 añade una transición artificial hacia `LOSS` cuando la
última acción deja el balón en estado transitorio. Son el **5.1%** de las
transiciones, y hay que declararlo al interpretar la cola de la distribución de
longitud.

---

## 2. El EMV: bajo qué distribución, exactamente

### El modelo probabilístico

Se supone que, **dado el estado actual**, el siguiente estado se elige de una
**distribución multinomial** cuyo vector de probabilidades depende solo del
estado actual:

$$(n_{i1}, \dots, n_{i,84}) \mid n_i \ \sim\ \text{Multinomial}(n_i,\ p_{i\cdot})$$

donde $n_{ij}$ = veces observadas $i\to j$ y $n_i = \sum_j n_{ij}$.

Esa es **la propiedad de Markov de primer orden**: el pasado no importa más allá
del estado actual.

### Por qué se puede usar multinomial sobre datos dependientes

**El problema.** Los eventos de una posesión están correlacionados. Un curso
básico diría que no aplica la teoría multinomial.

**El teorema (Billingsley, 1961).** La verosimilitud de una cadena de Markov
observada **se factoriza por renglones**:

$$L(P \mid \text{datos}) = \prod_{i}\underbrace{\prod_{j} p_{ij}^{n_{ij}}}_{\text{multinomial del renglón } i}$$

Cada renglón es un problema multinomial **independiente**, pese a que la cadena
es dependiente. Maximizando cada uno por separado con la restricción
$\sum_j p_{ij}=1$ (multiplicador de Lagrange) sale el EMV:

$$\boxed{\ \hat p_{ij}^{\text{MLE}} = \frac{n_{ij}}{n_i}\ }$$

La frecuencia relativa. Nada más.

### Dónde importó de verdad este teorema

En `07_cobertura_ic.py` se predijo que el bootstrap por posesión daría
intervalos más anchos que el ingenuo por transición. Salió **0.1091 contra
0.1091**: idénticos.

La razón es exactamente esta factorización: dado `from_state = i`, el destino es
condicionalmente independiente de todo lo demás, así que las transiciones de un
renglón son extracciones iid **aunque vengan de la misma posesión**.

**Consecuencia**: ADR-07 (bootstrap por bloques) es teóricamente correcto pero
**prácticamente irrelevante para las celdas de $P$**. Sí importa para $E[T]$,
donde el intervalo por posesión salió 19% más ancho, porque $E[T]$ agrega a
través de renglones.

---

## 3. El encogimiento: qué es λ, exactamente

### El problema que resuelve

El EMV es inutilizable en renglones ralos. Con $n_i = 20$ observaciones,
$\hat p_{ij}$ tiene varianza $p_{ij}(1-p_{ij})/20$ — enorme. Y con
$n_{ij}=0$ el EMV dice "esta transición es **imposible**", lo cual es falso:
solo no se observó.

### La fórmula

$$\boxed{\ \hat p^*_{ij}(\lambda) = \frac{n_{ij} + \lambda\, q_{ij}}{n_i + \lambda}\ }$$

donde $q$ es la **distribución de referencia** (el prior).

### Qué significa λ, en una frase

**λ es el número de observaciones ficticias que se le regalan a cada renglón,
repartidas según $q$.**

- $\lambda = 0$: sin regalo. Es el EMV puro.
- $\lambda = 500$ en un renglón con $n_i = 500$: mitad datos, mitad referencia.
- $\lambda \to \infty$: todos los renglones colapsan a $q$. Se pierde toda
  individualidad.

Reescrito como promedio ponderado se ve mejor:

$$\hat p^*_{ij} = \underbrace{\frac{n_i}{n_i+\lambda}}_{\text{peso de los datos}}\hat p^{\text{MLE}}_{ij} \;+\; \underbrace{\frac{\lambda}{n_i+\lambda}}_{\text{peso del prior}} q_{ij}$$

**El peso es automático por renglón**: los renglones densos casi ignoran el
prior, los ralos se apoyan casi por completo en él. Eso es lo que hace útil al
estimador.

### Doble lectura, ambas correctas

- **Frecuentista** (la que se defiende): estimador de encogimiento tipo
  **James–Stein**. Introduce sesgo hacia $q$ a cambio de reducir varianza. El
  error cuadrático medio total baja aunque cada estimador individual esté
  sesgado. Con $n_i$ grande el sesgo se desvanece.
- **Bayesiana** (segunda lectura): es exactamente la **media posterior** con
  prior $\text{Dirichlet}(\lambda q)$, que es conjugado de la multinomial. Y ahí
  λ tiene nombre propio: el **tamaño de muestra efectivo del prior**.

Se presenta primero la lectura frecuentista porque no requiere estadística
bayesiana formal.

### De dónde sale $q$

```python
_not_focus = trans.filter((pl.col(unit) != value) | pl.col(unit).is_null())
```

**Importante y contraintuitivo**: `transitions.parquet` contiene los **18
equipos** de los partidos analizados, y la columna `coach` es nula para los 17
rivales. El `is_null()` los incluye. Así que **$q$ es un pool de rivales, no
solo los otros entrenadores del club**.

El foco se excluye siempre (ADR-06). En v0.3 no se hacía y era un bug real: el
prior contenía al foco, así que "predecía bien" los datos retenidos por ser
suyos, y λ\* se disparaba al techo de la rejilla.

### El álgebra que resultó decisiva

Restando la línea base al estimador encogido:

$$\hat p^*_{\text{foco}} - \hat p_{\text{base}} = \frac{n_i}{n_i+\lambda}\left(\hat p^{\text{MLE}}_{\text{foco}} - \hat p_{\text{base}}\right)$$

Tres líneas de álgebra que descubrieron que **las magnitudes reportadas estaban
atenuadas por un factor que varía por renglón**: 0.585 con λ=500, 0.261 con
λ=2000.

Sin esta manipulación se habrían reportado efectos con el 58% de su tamaño real
sin que nada avisara. De ahí **ADR-22: significancia con λ\*, magnitudes con
λ=0**.

---

## 4. Cómo se elige λ, y por qué no se puede

### El método

Validación cruzada en 5 pliegues, donde **la unidad de partición es la posesión,
no el evento**. Partir por evento filtraría información entre train y test —dos
acciones de la misma posesión están fuertemente correlacionadas— y λ\* saldría
artificialmente bajo.

Se maximiza la log-verosimilitud fuera de muestra:

$$\lambda^* = \arg\max_\lambda \sum_{\text{pliegues}} \sum_{(i,j)\in\text{test}} \log \hat p^*_{ij}(\lambda;\ \text{train})$$

### El resultado incómodo

| λ | loglik OOS |
|---|---|
| 0 | −2.173 |
| 1 | −2.119 |
| 100 | −2.102 |
| **500** | **−2.0986** |
| 1000 | −2.0995 |
| 2000 | −2.105 |

**0.006 nats** entre λ=100 y λ=2000, contra **0.054** de λ=0 a λ=1. En
perplejidad, elegir 500 en vez de 200 cambia el poder predictivo un **0.6%**.

Dos afirmaciones distintas:

- ✅ *"El encogimiento mejora la predicción fuera de muestra"* — sólida, ~5% de
  perplejidad.
- ❌ *"El λ óptimo es 500"* — **no defendible**. La CV no lo identifica.

### La tensión que hay que declarar

**λ es casi irrelevante para predecir y decisivo para las magnitudes.** Dentro
del rango que los datos no distinguen, el efecto reportado varía por un factor
de tres.

### Nota de reproducibilidad (bug #8)

`possession_folds` barajaba `unique()` de polars, cuyo orden no está garantizado.
La semilla estaba fija pero el input no era determinista, y tres corridas
idénticas daban −2.1283, −2.1276 y −2.1287. **Una semilla fija sobre un input no
determinista no es determinismo.**

---

## 5. La matriz fundamental: análisis, no álgebra a secas

### El objeto

$$N = (I-Q)^{-1}, \qquad N_{ij} = \mathbb{E}[\text{visitas a } j \text{ antes de absorber} \mid \text{inicio en } i]$$

### Por qué existe

Porque la **serie de Neumann** converge:

$$N = \sum_{k=0}^{\infty} Q^k \quad\text{si}\quad \rho(Q)<1$$

Es el mismo argumento que la serie geométrica en un álgebra de Banach, y es
directamente el curso de análisis. La condición $\rho(Q)<1$ equivale a que toda
posesión termina casi seguramente.

### Detalle numérico

$N$ **no se calcula invirtiendo**. Se resuelve $(I-Q)N = I$ con
`scipy.linalg.solve`. Mismo resultado, mejor condicionamiento, menos costo. Hay
un test que verifica que `solve` coincide con la serie truncada a 400 términos.

### Lo que se construye encima

$$B = NR, \qquad t = N\mathbf{1}, \qquad \nu \propto (I-Q^\top)^{-1}\alpha$$

- $B_{ia}$ = probabilidad de absorber en $a$ partiendo de $i$. De ahí el xT del
  proyecto: $xT_i = B_{i,\text{GOAL}}$. **No se importa de la literatura, se
  deriva.**
- $t_i$ = número esperado de pasos hasta absorber.
- $\nu$ = distribución estacionaria de visitas: dónde vive el equipo.

**Validación externa gratuita**: $\bar{xT} = 0.0130$ contra una tasa de gol
empírica de ~1.6% por posesión. Mismo orden de magnitud sin que nadie lo
ajustara.

---

## 6. El contraste: LRT y por qué la significancia no bastó

### El estadístico

Para cada renglón, contraste de hipótesis **simple contra compuesta**:

$$G^2_i = 2\sum_j n_{ij}\log\frac{\hat p_{ij}}{q_{ij}} = 2n_i\, D_{KL}(\hat p_{i\cdot}\Vert q_{i\cdot})$$

Divergencia de Kullback–Leibler **escalada por el tamaño de muestra**.

### Por qué la nula NO es $\chi^2_{k-1}$

El resultado asintótico supone observaciones independientes. Aunque §2 dice que
dentro de un renglón sí lo son, el **número** de observaciones por renglón es
aleatorio y depende de la estructura de posesiones. Por eso la nula se calibra
**remuestreando posesiones** del pool base con el mismo número de posesiones que
el foco (ADR-08).

**Beneficio colateral no anticipado**: como la nula es empírica, el test es
robusto a la mala especificación que §7 detecta. Si se hubiera usado $\chi^2$,
el rechazo de Markov habría invalidado la Fase 3 entera.

### El problema que destapó

Con 67,492 transiciones se rechazan **80 de 80** renglones. $G^2 \propto n_i$:
mide **evidencia**, no **magnitud**. Un mapa uniformemente significativo no dice
dónde mirar.

### La corrección en tres pasos (ADR-25, 27, 28)

1. **Ordenar por distancia de variación total**, que no escala con $n$:

$$TV_i = \tfrac12\sum_j |p_{ij}-q_{ij}| \in [0,1]$$

2. **Restarle su nula.** $TV\geq 0$ siempre, y con pocos datos sale alta por
   ruido. Se remuestrea la base con el mismo tamaño y se resta la mediana. **El
   52% (Jardine) y el 63% (Anselmi) de la TV típica era tamaño de muestra.**

3. **Usar $z$ como filtro, nunca como orden.** Bajo la nula
   $\text{DE}(TV)\sim 1/\sqrt{n}$, así que
   $z \approx TV^{\text{exceso}}\sqrt{n}$: **escala con $\sqrt n$**, que es el
   defecto de $G^2$ entrando por la puerta de atrás. Filtro por fiabilidad
   ($z\geq3$), orden por magnitud.

---

## 7. Bondad de ajuste: la distribución phase-type

### La idea

Una cadena absorbente **implica** la distribución del número de pasos hasta la
absorción, en forma cerrada:

$$P(T > k) = \alpha^\top Q^k \mathbf{1}$$

Es una **phase-type discreta**. Compararla contra la empírica es un contraste
**global** del supuesto de Markov: no testea un renglón, testea la cadena
entera.

### El test y sus dos trampas

Kolmogorov–Smirnov, con dos cuidados que son puro curso de simulación:

1. **Los parámetros se estiman de los mismos datos**, así que la nula estándar
   de KS no aplica. Se calibra por **bootstrap paramétrico tipo Lilliefors**.
2. **Truncamiento.** `min_actions` hace $P(T<2)=0$ por construcción mientras la
   cadena le asigna 13% de masa. En la primera versión del script **el
   estadístico KS completo venía del punto $k=1$**: el test medía el
   truncamiento, no el ajuste. Hubo que comparar contra la phase-type
   **condicionada** a $T\geq2$.

### El resultado

| unidad | KS | p95 nulo | $p$ | sesgo $E[T]$ |
|---|---|---|---|---|
| Jardine | 0.087 | 0.012 | 0.005 | +1.82% |
| Solari | 0.104 | 0.019 | 0.005 | +1.93% |
| América | 0.098 | 0.010 | 0.005 | +1.68% |

**Rechaza**, con el mismo patrón: menos masa en el centro ($k$=2–10), más en la
cola ($k\geq12$), media casi perfecta. No es memoria simple sino
**sobredispersión**: la firma de una **mezcla**. Hay al menos dos poblaciones de
posesión que el estado $(z,\phi)$ no distingue.

### Por qué el modelo se mantiene (ADR-21)

1. El contraste compara dos cadenas ajustadas igual; una mala especificación
   **compartida** se cancela en buena medida. Y el patrón es idéntico en las
   tres unidades, así que la premisa es **verificable**.
2. La nula del LRT es por bootstrap, no $\chi^2$.
3. Se midió el impacto: bajo un generador de mezcla la cobertura de los IC cae
   de 0.944 a 0.938. Prácticamente nada.

**Dónde sí bloquea**: la Fase 7. Simular desde una cadena cuya distribución de
longitud está rechazada propaga el sesgo.

---

## 8. Cobertura: cómo se valida un intervalo

**El principio**: la única validación real de un IC es la **cobertura
empírica**. Simular desde un proceso con parámetro conocido, construir el
intervalo muchas veces, contar qué fracción contiene el valor verdadero.

**Un error conceptual que evitar**: la cobertura se mide contra el **parámetro
verdadero**, no contra el EMV. El EMV es el estimador; el parámetro es el
objetivo.

**Y una sutileza del encogimiento**: con λ>0 el estimador apunta a la diferencia
**atenuada** (§3), así que medir cobertura del parámetro verdadero con λ=500
daría mala cobertura, y **eso no sería un bug del bootstrap**. Por eso el
estudio corre con λ=0.

| n posesiones | cobertura (basic) |
|---|---|
| 300 | 0.935 |
| 1500 | 0.944 |
| 3000 | 0.944 |

`synth.py` **no sirve** para esto: inyecta el sesgo a nivel de generador de
eventos, así que la $P$ verdadera no se conoce en forma cerrada. Hubo que
generar a nivel de **cadena**.

---

## 9. Permutación: la lección que se repitió tres veces

**El principio**: una distancia sin distribución de referencia no significa
nada. $TV\geq0$ siempre, así que **cualquier** partición produce TV positiva por
ruido.

| caso | reportado | tras calibrar la nula |
|---|---|---|
| `detect_regime_changes` | TV = 0.22 como quiebre de era | ruido de calendario |
| Huella táctica | orden por TV cruda | 52–63% era tamaño de muestra |
| Contraste de contextos | TV = 0.04 como "no adapta" | 90% ruido; **conclusión contraria** |

**Tres de tres.** Es el principio metodológico central del proyecto (ADR-30).

**Y no se afirma la nula.** Si un contraste no rechaza, la frase es "no
detectamos un efecto mayor a $X$", con $X$ = p95 de la nula (**efecto mínimo
detectable**). Nunca "no hay efecto".

---

## 10. El diseño intra-jugador: efectos fijos sobre cadenas

La amenaza *"cambió el plantel"* se ataca comparando **a cada jugador consigo
mismo** bajo dos entrenadores. Si Fidalgo transiciona distinto con Jardine que
con Ortiz, **eso no lo explica el mercado de fichajes: es el mismo futbolista**.

Es la traducción de un **diseño de efectos fijos** al mundo de las cadenas de
Markov: el jugador es su propio control.

La nula se construye por permutación: si su comportamiento no cambió, las
etiquetas de era son intercambiables entre sus transiciones. Con control de FDR
sobre los jugadores testeados (ADR-09).

### Por qué el "núcleo estable" (nivel 2) NO funciona

Filtrar posesiones por "quién ejecutó las acciones" **selecciona por longitud**:
una posesión larga tiene más oportunidades de incluir a alguien fuera del
núcleo. Y la longitud es la variable de respuesta. **Es circularidad
estadística** — *length-biased sampling*.

El diagnóstico automático lo detecta con sesgo diferencial de 22–37 puntos
porcentuales. Con umbral 0.9 el signo **se invierte**. ADR-33.

---

## 11. Lo que aún no se ha usado

**Wasserstein $W_1$ (Fase 8).** Comparar las distribuciones de visitas $\nu_A$ y
$\nu_B$ con métrica base **en metros**:

$$W_1(\nu_A,\nu_B) = \min_{\pi\in\Pi(\nu_A,\nu_B)} \sum_{i,j}\pi_{ij}\,d(i,j)$$

Es un **problema de transporte**, o sea un programa lineal, con interpretación
directa: *"cuántos metros hay que mover la masa de probabilidad para convertir
el estilo de A en el de B"*. Y su **dual** da precios sombra por zona.

Es la conexión más directa con programación lineal y probablemente la extensión
de mayor retorno por esfuerzo.

**Reducción de varianza (Fase 7).** Números pseudoaleatorios comunes al comparar
escenarios simulados colapsa la varianza de la diferencia. *Importance sampling*
para eventos raros (gol).

**Semi-Markov (Fase 6).** $Q_{ij}(t) = p_{ij}F_{ij}(t)$. El rechazo de §7 lo
refuerza: la distribución de longitud está mal ajustada, y modelar los tiempos
de permanencia es una vía para arreglarlo.

---

## 12. Cómo defenderlo en cinco minutos

Si solo hay tiempo para una idea:

> El estilo de un entrenador es la matriz de transición de una cadena de Markov
> absorbente sobre (zona × fase). De ahí, por álgebra lineal, salen tres
> cantidades interpretables: dónde vive el equipo, cuánto dura su posesión, y
> con qué probabilidad termina en gol. Todo lo demás es medir la incertidumbre
> de esos números.

Si hay tiempo para una segunda:

> Tres veces reporté una distancia sin su distribución de referencia y las tres
> veces estaba equivocado. La nula empírica no es un adorno: es lo que separa un
> hallazgo de un artefacto de tamaño de muestra.

Y si preguntan por la limitación principal:

> El supuesto de Markov de primer orden se rechaza con p = 0.005, por
> sobredispersión, replicado en tres unidades. No lo escondo: lo medí, sé de qué
> tamaño es, y sé por qué no invalida el contraste entre entrenadores.
