# 03 — Informe metodológico

> **Audiencia**: matemáticos y estadísticos que deban evaluar la corrección y
> reproducibilidad del método. Se enuncian los supuestos, se derivan los
> estimadores y se justifica cada prueba estadística, incluyendo los casos en
> que la teoría asintótica estándar **no** aplica.

---

## 1. Formalización

### 1.1 El proceso observado

Un partido genera una secuencia de eventos. Se restringe la atención a las
**posesiones** del equipo de interés. Una posesión es una secuencia finita de
acciones con balón ejecutadas por el mismo equipo, terminada por remate,
pérdida, salida del balón o interrupción.

Sea $\mathcal{Z} = \{1,\dots,K\}$ una partición del campo en zonas y
$\Phi$ un conjunto finito de fases de juego. El **espacio de estados
transitorios** es el producto

$$\mathcal{S}_T = \mathcal{Z} \times \Phi, \qquad |\mathcal{S}_T| = K|\Phi|$$

y el conjunto de **estados absorbentes** es

$$\mathcal{S}_A = \{\text{GOAL},\ \text{SHOT\_NOGOAL},\ \text{LOSS},\ \text{OUT}\}.$$

El espacio completo es $\mathcal{S} = \mathcal{S}_T \sqcup \mathcal{S}_A$ con
$|\mathcal{S}| = K|\Phi| + 4$.

**Configuración actual**: $K = 20$ (malla $5\times4$), $|\Phi| = 4$
(open, transition, restart, set\_piece), de donde $|\mathcal{S}_T| = 80$ y
$|\mathcal{S}| = 84$.

### 1.2 Supuestos del modelo

**(A1) Markov de primer orden.** Dado el estado actual, la distribución del
siguiente estado es independiente de la historia previa:
$$\Pr(X_{t+1} = j \mid X_t = i, X_{t-1}, \dots, X_0) = \Pr(X_{t+1} = j \mid X_t = i) = p_{ij}.$$

**(A2) Homogeneidad temporal.** $p_{ij}$ no depende de $t$ dentro de la unidad
de análisis (una era de entrenador, opcionalmente estratificada por contexto).

**(A3) Absorción casi segura.** Desde todo estado transitorio hay probabilidad
positiva de alcanzar $\mathcal{S}_A$ en un número finito de pasos.

**(A4) Independencia entre posesiones.** Posesiones distintas son
intercambiables dentro de la unidad de análisis.

Notas sobre el estatus de cada supuesto:

- **(A1)** es el supuesto fuerte y **no ha sido testeado en este proyecto**.
  Ver §7.1 para el procedimiento de contraste pendiente. La literatura sugiere
  que la propiedad de Markov se sostiene razonablemente para las *transiciones
  de estado*, mientras que las *duraciones* violan claramente la exponencialidad
  (motivo de la Fase 6 semi-Markov del roadmap).
- **(A2)** se protege estratificando por marcador (Fase 4). Sin estratificar,
  agrega comportamiento heterogéneo.
- **(A3)** se **verifica numéricamente** en cada corrida vía $\rho(Q) < 1$.
- **(A4)** es lo que justifica el bootstrap por bloques de posesión. Es más
  débil que independencia entre eventos, que sería falsa.

### 1.3 Partición canónica

Ordenando primero los estados transitorios,

$$P = \begin{pmatrix} Q & R \\ \mathbf{0} & I \end{pmatrix},
\qquad Q \in [0,1]^{|\mathcal{S}_T|\times|\mathcal{S}_T|},
\qquad R \in [0,1]^{|\mathcal{S}_T|\times 4}.$$

$Q$ es sub-estocástica: $\|Q\|_\infty < 1$ siempre que todo estado transitorio
tenga probabilidad no nula de absorción, que es (A3).

---

## 2. Estimación

### 2.1 Verosimilitud y EMV

Sea $n_{ij}$ el número de transiciones observadas $i \to j$ y
$n_i = \sum_j n_{ij}$. Bajo (A1)–(A2), la verosimilitud de una trayectoria
observada se factoriza:

$$L(P \mid \text{datos}) = \prod_{i \in \mathcal{S}_T} \prod_{j \in \mathcal{S}} p_{ij}^{\,n_{ij}}.$$

Maximizando bajo las restricciones $\sum_j p_{ij} = 1$ mediante multiplicadores
de Lagrange se obtiene

$$\hat{p}_{ij}^{\text{EMV}} = \frac{n_{ij}}{n_i}.$$

**Resultado que hay que citar**: la verosimilitud se factoriza **por renglones**,
de modo que cada renglón constituye un problema multinomial independiente *pese
a que la cadena es dependiente*. Este es el resultado de Billingsley (1961), y
es lo que legitima aplicar inferencia multinomial estándar (EMV, cociente de
verosimilitudes, $\chi^2$) sobre datos secuenciales.

**Advertencia de alcance**: el resultado aplica a la cadena observada evento a
evento bajo (A1)–(A2). No cubre la heterogeneidad entre posesiones y partidos,
que es precisamente lo que el bootstrap por bloques (§4.1) sí protege.

### 2.2 Estimador de encogimiento

El EMV es inservible en renglones ralos: con $n_i = 2$ produce estimaciones de
0.5 y 0 con varianza enorme. Se usa

$$\boxed{\ \hat{p}^*_{ij}(\lambda) = \frac{n_{ij} + \lambda\, q_{ij}}{n_i + \lambda}\ }$$

donde $q_{i\cdot}$ es un renglón de referencia y $\lambda \ge 0$.

**Doble lectura, ambas correctas:**

*Frecuentista.* Es un estimador de encogimiento. Escribiendo
$w_i = n_i/(n_i+\lambda)$,
$$\hat p^*_{i\cdot} = w_i\,\hat p^{\text{EMV}}_{i\cdot} + (1-w_i)\, q_{i\cdot},$$
una combinación convexa entre evidencia propia y referencia. Introduce sesgo
hacia $q$ a cambio de reducir varianza; como $w_i \to 1$ cuando $n_i \to \infty$,
el sesgo se desvanece asintóticamente. Es el mismo argumento de dominancia en
error cuadrático medio que sostiene a los estimadores de James–Stein.

*Bayesiana.* Con prior conjugado $p_{i\cdot} \sim \text{Dirichlet}(\lambda q_{i\cdot})$
y verosimilitud multinomial, la posterior es
$\text{Dirichlet}(\lambda q_{i\cdot} + n_{i\cdot})$ y su media es exactamente
$\hat p^*_{i\cdot}(\lambda)$. Así, $\lambda$ es el **tamaño de muestra efectivo
del prior**.

Las dos lecturas coinciden numéricamente. La elección de cuál presentar es
retórica, no matemática.

### 2.3 Selección de $\lambda$

$\lambda$ **no se fija a ojo**. Se elige por validación cruzada de $k$ pliegues
**particionando por posesión**, maximizando log-verosimilitud fuera de muestra:

$$\lambda^* = \arg\max_{\lambda \in \Lambda} \sum_{f=1}^{k} \sum_{i,j} n^{(f)}_{ij}\,
\log \hat p^{*(-f)}_{ij}(\lambda)$$

donde $n^{(f)}$ son los conteos del pliegue retenido y $\hat p^{*(-f)}$ el
estimador ajustado sin él.

Particionar por evento en lugar de por posesión filtraría información entre
train y test —dos acciones de la misma posesión están fuertemente
correlacionadas— y sesgaría $\lambda^*$ a la baja.

**Interpretación directa de $\lambda^*$**: número de observaciones que hacen
falta en un renglón para que la evidencia propia pese lo mismo que la
referencia. Es una cantidad reportable por sí sola.

**Diagnóstico obligatorio**: si $\lambda^*$ cae en un extremo de $\Lambda$, la
rejilla es insuficiente o hay un problema de especificación. El software emite
aviso.

### 2.4 Elección de la referencia $q$: la fuga de prior

$q$ debe ser **externa a la unidad focal**. Si $q$ se calcula sobre un conjunto
que contiene al foco —caso frecuente cuando un club domina el archivo— entonces:

1. La log-verosimilitud fuera de muestra sobreestima la calidad de $q$, porque
   los datos retenidos contribuyeron a construirlo. $\lambda^*$ se infla y
   pierde su interpretación.
2. En una comparación entre dos unidades, ambas se encogen hacia un $q$ que las
   contiene: la diferencia estimada se atenúa **por construcción**, sin dejar
   rastro en los diagnósticos.

Formalmente, la fuga es una violación del principio de separación entre datos de
ajuste y datos de evaluación. La implementación ofrece tres modos, con
`exclude_focus` por defecto.

**Distinción conceptual que debe mantenerse explícita**: $q$ es el **prior** que
estabiliza renglones ralos; la **línea base** es contra quién se compara en la
Fase 3. Son objetos distintos y pueden coincidir o no.

---

## 3. Cantidades derivadas

### 3.1 Matriz fundamental

Bajo (A3), $\rho(Q) < 1$, y la serie de Neumann converge:

$$N = \sum_{k \ge 0} Q^k = (I - Q)^{-1}.$$

$N_{ij}$ = número esperado de visitas al estado $j$ antes de absorber, partiendo
de $i$.

**Implementación**: $N$ se obtiene resolviendo $(I-Q)N = I$ mediante
factorización LU, no invirtiendo explícitamente. Mismo resultado, mejor
condicionamiento numérico y menor costo. Verificado contra la suma truncada de
la serie en `test_neumann_series_matches_solve`.

### 3.2 Probabilidades de absorción

$$B = N R \in [0,1]^{|\mathcal{S}_T| \times 4}, \qquad \sum_{a} B_{ia} = 1 \ \forall i.$$

$B_{i,\text{GOAL}}$ es la probabilidad de que la posesión termine en gol dado que
se encuentra en el estado $i$. **Esta es la construcción de "Expected Threat"
desde primeros principios**, no una métrica importada: coincide conceptualmente
con la formulación de Rudd (2011) y Singh (2018), quienes introdujeron el uso de
cadenas de Markov para valorar situaciones de juego.

### 3.3 Longitud esperada de posesión

$$t = N\mathbf{1}, \qquad t_i = \sum_j N_{ij}.$$

### 3.4 Distribución de visitas

Dada una distribución inicial $\alpha$ sobre estados transitorios,

$$\nu \propto \alpha^\top N \quad\Longleftrightarrow\quad (I-Q)^\top \nu = \alpha,$$

normalizada a suma 1. $\nu$ resume "dónde vive" el equipo en una única medida de
probabilidad sobre $\mathcal{S}_T$, y es el objeto natural para comparar estilos
mediante distancias entre medidas (Fase 8 del roadmap).

$\alpha$ se estima empíricamente como la distribución de estados iniciales de
las posesiones observadas.

---

## 4. Inferencia

Esta sección contiene las decisiones estadísticamente delicadas. Cada una
corrige un error que sería invisible en la salida.

### 4.1 Bootstrap por bloques de posesión

**Problema.** Los eventos dentro de una posesión están fuertemente
correlacionados. Remuestrear acciones individuales asume independencia y produce
intervalos artificialmente angostos: se "detecta" estilo donde solo hay ruido.

**Solución.** La unidad de remuestreo es la **posesión completa**. Sea
$\mathcal{P} = \{\pi_1,\dots,\pi_M\}$ el conjunto de posesiones de la unidad de
análisis. Cada réplica bootstrap muestrea $M$ posesiones con reemplazo y
recalcula el estimador sobre la unión de sus transiciones.

Esto es un *block bootstrap* en el que los bloques son las posesiones. Su
validez descansa en (A4), un supuesto mucho más débil que independencia entre
eventos.

**Implementación.** Las transiciones se almacenan en formato tipo CSR
(`flat`, `starts`, `lens`), lo que permite remuestrear con `np.bincount` sin
reconstruir estructuras de datos. Miles de réplicas corren en segundos.

### 4.2 Intervalo de confianza de la diferencia

**Error frecuente que se evita.** Comparar dos intervalos por separado y
concluir de su traslape. Intervalos disjuntos $\Rightarrow$ diferencia
significativa (correcto), pero intervalos traslapados $\not\Rightarrow$ no
significancia. Es un error clásico.

**Procedimiento.** Se construye directamente la distribución bootstrap de

$$\hat\Delta = \hat p^*_{\text{foco}} - \hat p_{\text{base}}$$

remuestreando **ambos** lados. Definiendo la receta única

$$\hat P_{\text{base}} = \hat p^*(C_{\text{base}}, q, 0), \qquad
\hat P_{\text{foco}} = \hat p^*(C_{\text{foco}}, \hat P_{\text{base}}, \lambda),$$

el estimador puntual y cada réplica se computan con la **misma función**. Si no,
el intervalo deja de estar centrado en el estimador —síntoma observable: un IC
que no contiene su propio punto—. Hay test de regresión para esto.

**Método del intervalo.** Por defecto se usa el bootstrap *básico* (percentil
invertido):

$$\text{IC}_{1-\alpha} = \left[\,2\hat\Delta - q_{1-\alpha/2},\ \ 2\hat\Delta - q_{\alpha/2}\,\right]$$

donde $q_\gamma$ son cuantiles de las réplicas. Corrige el sesgo de primer orden,
que es justamente lo que introduce el encogimiento. El método percentil crudo
está disponible como alternativa.

### 4.3 Contraste de razón de verosimilitudes por renglón

Para cada estado transitorio $i$ se contrasta

$$H_0: p_{i\cdot} = q_{i\cdot} \qquad \text{vs} \qquad H_1: p_{i\cdot} \ne q_{i\cdot},$$

hipótesis simple contra compuesta sobre un modelo multinomial. El estadístico de
razón de verosimilitudes es

$$\boxed{\ G^2_i = 2\sum_{j} n_{ij} \log\!\frac{n_{ij}}{n_i\, q_{ij}}\ }$$

con la convención $0\log 0 = 0$. Equivalentemente, $G^2_i = 2 n_i D_{KL}(\hat p_{i\cdot} \Vert q_{i\cdot})$:
el estadístico es la divergencia de Kullback–Leibler escalada por el tamaño de
muestra, lo cual da una lectura de tamaño de efecto además de significancia.

**Por qué NO se usa la asintótica $\chi^2_{k-1}$.** El teorema de Wilks requiere
observaciones independientes. La dependencia intra-posesión inflaría el
estadístico y produciría rechazos espurios. En su lugar:

**Calibración por bootstrap de la distribución nula.** Se remuestrean $M$
posesiones (el mismo número que tiene la unidad focal) del *pool* de la línea
base, y se recalcula $G^2_i$ en cada réplica. Esto genera la distribución de
referencia bajo $H_0$ preservando (i) la dependencia intra-posesión y (ii) el
tamaño de muestra efectivo del foco.

El $p$-valor se estima como

$$\hat p_i = \frac{1 + \#\{b : G^{2,(b)}_i \ge G^{2,\text{obs}}_i\}}{1 + B}$$

con la corrección $+1$ estándar (Davison & Hinkley, 1997), que evita $p = 0$ y
garantiza validez conservadora del test.

**Filtro de potencia.** Renglones con $n_i <$ `min_row_count` (default 15) no se
testean: se les asigna $p = 1$ y se excluyen del control de multiplicidad, para
no gastar presupuesto de error en hipótesis sin potencia.

### 4.4 Control de multiplicidad

Con $|\mathcal{S}_T| = 80$ renglones testeados al 5%, se esperan ~4 rechazos
puramente por azar. Se controla la **tasa de falso descubrimiento** con el
procedimiento de Benjamini–Hochberg: ordenando $p_{(1)} \le \dots \le p_{(m)}$,
se rechazan las hipótesis hasta

$$k^* = \max\Big\{k : p_{(k)} \le \frac{k}{m}\alpha\Big\}.$$

Los $q$-valores se obtienen por el ajuste monótono acumulado usual. Se controla
FDR y no FWER porque el objetivo es exploratorio-descriptivo (identificar dónde
mirar), no confirmatorio.

BH es válido bajo independencia y bajo dependencia positiva por regresión
(PRDS). Las hipótesis por renglón no son independientes, pero la dependencia
esperada entre renglones vecinos es positiva. Una alternativa más conservadora
sería Benjamini–Yekutieli, válido bajo dependencia arbitraria al costo de un
factor $\sum_{k=1}^m 1/k$. **No implementado; queda registrado como opción.**

### 4.5 Contraste entre contextos

Para separar filosofía de reactividad se compara $P(\cdot \mid c)$ entre niveles
del contexto $c$ (marcador) mediante distancia de variación total por renglón,
ponderada por masa observada:

$$d_{TV}(a,b) = \sum_i w_i \cdot \tfrac12 \sum_j \big| \hat p^{(a)}_{ij} - \hat p^{(b)}_{ij} \big|,
\qquad w_i \propto n^{(a)}_i + n^{(b)}_i.$$

$d_{TV}$ pequeño entre "ganando" y "perdiendo" es evidencia de idea de juego
impuesta; $d_{TV}$ grande indica adaptación al resultado.

**Pendiente**: intervalos de confianza sobre $d_{TV}$ vía el mismo bootstrap por
posesión. Actualmente se reporta el punto sin incertidumbre.

---

## 5. Validación implementada

### 5.1 Verificaciones estructurales (en cada corrida)

| verificación | criterio | dónde |
|---|---|---|
| Estocasticidad | $\|\sum_j p_{ij} - 1\| < 10^{-8}$ | `AbsorbingChain.check` |
| Absorción | $\rho(Q) < 1$ | `AbsorbingChain.check` |
| Filas de $B$ | suman 1 | test |
| Orientación de coordenadas | corr(columna de zona, tasa de gol) > 0.5 | `coordinate_sanity` |
| Terminación de posesiones | toda posesión acaba absorbida | test |

### 5.2 Verificaciones numéricas (suite de tests)

- $N$ por `solve` coincide con la serie de Neumann truncada a 400 términos
  ($10^{-6}$).
- $t = N\mathbf{1}$ coincide con la suma de filas de $N$.
- $\hat p^*(\lambda\to0)$ recupera el EMV; $\hat p^*(\lambda\to\infty)$ recupera
  $q$; renglones vacíos caen en $q$.
- $G^2 = 0$ exactamente cuando $\hat p = q$.
- BH: monotonía de $q$-valores; bajo 500 $p$-valores uniformes, $\le 5$
  rechazos.
- El IC de la diferencia contiene su estimador puntual (ambos métodos).

### 5.3 Recuperación de parámetros

El generador sintético (`synth.py`) reproduce el esquema real de StatsBomb e
inyecta un sesgo conocido: un equipo progresa preferentemente hacia el carril
central con intensidad controlada por `dt_bias`.

El test `test_fingerprint_recovers_injected_bias` verifica:
- con sesgo inyectado, la Fase 3 produce rechazos tras FDR;
- con un equipo placebo (sin sesgo), los rechazos no exceden a los del sesgado.

En la ejecución end-to-end, las celdas con mayor diferencia significativa son
consistentemente transiciones de carril exterior a interior, que es exactamente
el efecto inyectado.

**Este experimento es la evidencia metodológica principal del proyecto** y debe
figurar en el reporte: demuestra que el método detecta señal real y distingue
señal de ruido.

---

## 6. Reproducibilidad

### 6.1 Determinismo

Todas las fuentes de aleatoriedad usan `numpy.random.default_rng(seed)` con
semillas provenientes del archivo de configuración:

| proceso | semilla | valor |
|---|---|---|
| pliegues de CV | `estimation.cv_seed` | 20260819 |
| bootstrap | `inference.boot_seed` | 11235 |

Ninguna semilla está hardcodeada en el código de análisis.

### 6.2 Parámetros

**Todo parámetro que afecte resultados vive en `config/default.yaml`.** El
archivo es parte del artefacto reproducible y debe versionarse junto con
cualquier resultado reportado.

### 6.3 Cadena de artefactos

Cada fase escribe su salida en disco con un reporte JSON de diagnósticos. La
cadena `transitions.parquet → P_matrices.npz → phase2.npz → fingerprint.parquet`
permite reejecutar cualquier fase sin repetir las anteriores.

### 6.4 Cómo reproducir

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest -q                      # verificación numérica: 34 tests
dtdecoder demo                 # pipeline completo sobre sintéticos
```

Para datos reales, ver `README.md` §"Flujo con datos de un solo club".

---

## 7. Limitaciones y contrastes: estado actualizado

> Reemplaza la sección 7 original, que decía que el supuesto de Markov no había
> sido testeado — dejó de ser cierto el 2026-08-20. Integra también
> `03_METHODS_SECCION7_REEMPLAZO.md` (aplicado 2026-08-26) y el bloque
> defensivo D1.

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

### 7.2 La fase sin balón: modelada como cadena conjugada (D1)

> **Actualizado 2026-08-26.** La versión anterior decía que el modelo describe
> solo la fase con balón. Dejó de ser cierto.

La firma defensiva se modela como **el proceso del rival, modificado** (ADR-39):
`transitions.parquet` ya contiene las posesiones de los 18 equipos, así que la
cadena conjugada sale del mismo artefacto con un filtro.

Sobre ella se define $\pi_e(z)$ = proporción de acciones del rival, en la zona
$z$ y bajo la era $e$, jugadas con `under_pressure`. Nulas por permutación de la
etiqueta de era **entre partidos**; multiplicidad en dos subfamilias separadas
(ADR-48). Resultados en `10_RESULTADOS.md` §17–§21.

**Tres limitaciones propias, todas declaradas:**

1. **Es asociación, no efecto causal.** StatsBomb anota presión cuando un
   defensor se acerca, y se acerca más cuando el rival ya está en problemas. El
   diseño no separa la dirección.
2. **`min_actions = 1` en perspectiva defensiva** (ADR-41): una posesión rival de
   una acción *es* el producto de una presión exitosa. Consecuencia:
   $E[T^{att}]$ y $E[T^{def}]$ **no son comparables entre sí**.
3. **Dos estimandos, no uno.** $\pi$ por posesión y $\pi$ por acción difieren
   exactamente en $\operatorname{Cov}(L,m)/\mathbb{E}[L]$, verificado con error
   $2\times10^{-17}$, y **con signos opuestos para Jardine**. Toda cifra declara
   cuál es.

**Lo que sigue ausente**: los datos 360 (*freeze frames*, `visible_area`) no
están en el volcado. Sin ellos no hay modelo de posición defensiva ni corrección
por adelgazamiento para la censura del área visible. Es la Fase 5 completa del
roadmap; D1 es su primer bloque, no su sustituto.

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
   $5\times4$.

   > **Matizado por ADR-46**: `params_per_obs` supera 0.5 en **seis de diez**
   > unidades ofensivas, no solo en Ortiz. No se reduce la malla; se etiqueta
   > cada unidad en `reports/manifiesto_unidades.json`. El sesgo del sobreajuste
   > va hacia **encontrar** diferencias, así que refuerza los nulos y debilita
   > los positivos. Moreno II defensivo (1.016) queda excluido.

2. **Encogimiento $\lambda$** — ✅ **RESUELTO**. La curva de CV es una meseta
   (0.006 nats entre $\lambda=100$ y $\lambda=2000$): **$\lambda$ no está
   identificado**. Y por álgebra sobre el estimador de la diferencia,
   $\hat p^* - \hat p_{base} = \frac{n_i}{n_i+\lambda}(\hat p^{MLE} - \hat p_{base})$,
   la magnitud reportada está atenuada por un factor que varía por renglón
   (0.585 con $\lambda=500$). **Regla: significancia con $\lambda^*$, magnitudes
   con $\lambda=0$** (ADR-22).

3. **Umbral de acarreos** (`min_carry_length = 5.0 m`) — ❌ **PENDIENTE**. Es la
   única sensibilidad del plan original que sigue sin reportarse.

   Ya se sabe que **no puede** explicar las auto-transiciones: el 60% de ellas
   vienen de **pases**, que ningún umbral de acarreo toca. Y el 49–50% de los
   acarreos que sobreviven al filtro siguen sin salir de zona, así que el umbral
   de 5 m es cosmético a resolución $5\times4$.

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

### 7.7 Rotación de plantilla: acotada, no eliminada

> **Actualizado 2026-08-26.** La versión anterior decía que era cuantificable y
> no se había hecho. Se hizo.

Comparar eras dentro del mismo club controla institución, presupuesto, cantera,
estadio y calendario. **No controla rotación de plantilla.**
`scripts/11_confusion_plantel.py` la ataca en tres niveles:

| nivel | qué hace | estado |
|---|---|---|
| 1 — solapamiento | % de acciones ejecutadas por jugadores compartidos | ✅ |
| 2 — núcleo estable | repetir el análisis solo con esas posesiones | ❌ **circular** (ADR-33) |
| 3 — intra-jugador | comparar a cada jugador consigo mismo | ✅ **decisivo** (ADR-34) |

El **nivel 2 se descarta por sesgo de longitud**: cualquier filtro basado en
"quién ejecutó las acciones" selecciona por longitud de posesión, que es justo la
variable que se mide. Con umbral 0.9 el signo del efecto **se invierte**. Se
reporta como limitación demostrada, no como resultado.

El **nivel 3 es el argumento válido**: prueba de permutación por jugador con
control de FDR. De los 17 jugadores con datos con Jardine y con Ortiz, **9
cambiaron** su patrón de forma detectable, cuando por azar se esperaría **0.9**.

**Lo que no desaparece**: aunque el jugador sea el mismo, sus compañeros, su
posición y sus rivales cambian. Y en el bloque defensivo se añade la
**endogeneidad de la asignación** — un DT llega tras una mala racha, así que su
era empieza condicionada al rendimiento previo (ADR-44). Eso no se corrige con
ningún ajuste por observables.

### 7.8 Lo que el modelo no puede afirmar

- Que un DT sea **mejor** que otro: se mide estilo, no rendimiento. Y ninguna
  diferencia en $P(\text{gol})$ estimada por la cadena resultó significativa.
- Causalidad: se detecta que una era difiere de otra, no que el DT sea la causa.
  En el bloque defensivo, además, la marca de presión es endógena al estado del
  rival.
- Resultados de partido: se predicen transiciones, y la distancia entre eso y
  ganar es grande.
- Nada sobre localía ni momento del partido: **el reto los pide explícitamente y
  no están** (ADR-44).


### 7.9 Endogeneidad de la asignación de entrenadores

> Sube a limitación **general** el 2026-08-26. Estaba declarada solo para el
> bloque defensivo (ADR-44) y aplica al proyecto entero.

Los entrenadores **no se asignan al azar**. Llegan tras una crisis deportiva, y
su era empieza condicionada al rendimiento previo. La literatura lo llama
*regresión a la media* o *new manager bounce*.

**Esto no se corrige con ningún ajuste por observables.** Estandarizar por rival,
por localía o por marcador no lo toca: el problema es la asignación, no la
composición de los partidos.

**Alcance real de la amenaza, con dos matices que la acotan:**

1. **El rebote es un fenómeno de rendimiento, no de estilo.** Un DT que llega
   tras una mala racha gana más partidos por inercia, motivación o suerte. Eso
   no hace que su equipo sostenga la posesión 7.76 acciones en vez de 6.50. El
   diseño mide estilo, no resultados — y ninguna diferencia en $P(\text{gol})$
   estimada por la cadena resultó significativa.
2. **Lo que sí amenaza es la afirmación causal**, que el proyecto ya declara no
   hacer en cuatro documentos. Un club puede *elegir* a un técnico por su estilo;
   entonces la era difiere por selección y no por efecto del DT. La afirmación
   sobreviviente es *"bajo este técnico el equipo jugó así"*, no *"este técnico
   hizo que el equipo jugara así"*.

**Lo que haría falta**: un diseño cuasi-experimental — control sintético o
diferencias en diferencias contra clubes que **no** cambiaron de entrenador en la
misma ventana. Es viable con los 18 equipos y hoy no lo es con dos.

### 7.10 Tiempo discreto en acciones: el reloj se descarta

Ampliación de §7.3, con el ejemplo que lo hace concreto:

> Una posesión de 5 acciones que dura **8 segundos** es un contragolpe. Una de
> 5 acciones que dura **30 segundos** es un bloque bajo saliendo con pausa. El
> modelo actual **no las distingue**: para la cadena son el mismo objeto.

Es la limitación de alcance más clara del proyecto, y es **deliberada**. La
columna `duration` se conserva sin usar precisamente para la Fase 6
(semi-Markov), donde $Q_{ij}(t) = p_{ij}F_{ij}(t)$ modela el tiempo de
permanencia explícitamente.

Las alternativas de la literatura —cadenas en tiempo continuo, procesos de
Hawkes con intensidad dependiente del tiempo transcurrido— son la generalización
correcta y quedan fuera del alcance actual. Declararlo como decisión, no como
descuido.

El rechazo de §7.1 refuerza el caso: la distribución de longitud está mal
ajustada, y modelar los tiempos de permanencia es una vía para arreglarlo.

### 7.11 Diagnóstico local del ajuste: pendiente

El contraste de §7.1 es **ómnibus sobre una sola dimensión**. Dice que la cadena
no describe bien la longitud de las posesiones y cuantifica cuánto. **No dice
dónde en el campo** falla.

Falta un chequeo predictivo espacial: simular desde $P$, comparar la
distribución de visitas por estado contra la observada, y proyectar el residuo
por celda sobre la cancha. Es ADR-50, y es barato.

**No confundirlo con la huella táctica**, que mapea $G^2$ entre dos eras — dónde
difieren dos entrenadores, no dónde falla el modelo.

### 7.12 Una sola matriz por era: estacionariedad, medida y acotada

Estimar una única $P$ por era asume **homogeneidad temporal** dentro de la era.
Un equipo ganando no transita igual que perdiendo.

**Está medido, no supuesto.** ADR-04 decidió que el contexto **estratifica** en
vez de entrar al espacio de estados, y `scripts/10_nula_contextos.py` contrasta
la adaptación al marcador contra su nula: es **real, pero de 4 a 30 veces menor
que la firma del entrenador** (`10_RESULTADOS.md` §4).

Nota sobre la dirección del sesgo: promediar sobre regímenes infla la varianza
**dentro** de la era, es decir $\sigma$. Un $\sigma$ mayor **sube** el suelo de
detección de $\tau^2$ (§25.4 de `10_RESULTADOS.md`). Mezclar contextos hace el
hallazgo de variación entre entrenadores **más difícil**, no más fácil — el lado
conservador.

## 8. Referencias

- Billingsley, P. (1961). *Statistical Methods in Markov Chains*.
  Annals of Mathematical Statistics 32(1), 12–40.
- Rudd, S. (2011). *A Framework for Tactical Analysis and Individual Offensive
  Production Assessment in Soccer Using Markov Chains*. NESSIS.
- Singh, K. (2018). *Introducing Expected Threat*.
  https://karun.in/blog/expected-threat.html
- Decroos, T., Bransen, L., Van Haaren, J., Davis, J. (2019). *Actions Speak
  Louder Than Goals: Valuing Player Actions in Soccer*. KDD. arXiv:1802.07127
- Davison, A. C., Hinkley, D. V. (1997). *Bootstrap Methods and Their
  Application*. Cambridge University Press.
- Benjamini, Y., Hochberg, Y. (1995). *Controlling the False Discovery Rate*.
  JRSS-B 57(1), 289–300.
- Benjamini, Y., Yekutieli, D. (2001). *The Control of the False Discovery Rate
  in Multiple Testing under Dependency*. Annals of Statistics 29(4), 1165–1188.
- Kemeny, J. G., Snell, J. L. (1976). *Finite Markov Chains*. Springer.
  (Matriz fundamental y absorción.)
- arXiv:2604.21087 — *Model quality in football: Quantifying the quality of an
  Expected Threat model*. Relevante para la relación entre número de estados,
  tamaño de muestra y error de estimación.
