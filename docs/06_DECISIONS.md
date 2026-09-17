# 06 — Registro de decisiones (ADR)

> Cada decisión con su contexto, alternativas consideradas y consecuencias.
> Sirve para dos cosas: que otra IA no reabra debates ya cerrados, y que ante
> un jurado se pueda justificar cualquier elección sin improvisar.
>
> Formato: **Decisión — Contexto — Alternativas — Consecuencias — Estado**
>
> ADR-01 a ADR-20 son de v0.2–v0.4. ADR-21 a ADR-26 son de la validación de
> fases 0–2 (2026-08-20).

---

## ADR-01 · El DT es un parámetro latente, no un agente

**Contexto.** "Cómo juega este entrenador" admite modelarlo como agente (RL
multiagente) o como parámetro de un proceso estocástico.

**Decisión.** Parámetro latente: $\theta$ = matriz de transición.

**Consecuencias.** Todo el aparato de inferencia clásica aplica y es
verificable. Se pierde la capacidad de modelar decisión individual.

**Estado.** Cerrada.

---

## ADR-02 · Cadena de Markov absorbente sobre zonas

**Decisión.** Cadena absorbente con estados (zona × fase) y cuatro absorbentes.

**Consecuencias.** $N$, $B$ y $\nu$ salen por álgebra lineal, todas
interpretables. Impone Markov de primer orden — limitación ahora **medida**, ver
ADR-21.

**Estado.** Cerrada. Es el núcleo del proyecto.

---

## ADR-03 · Cuatro estados absorbentes en vez de dos

**Decisión.** GOAL, SHOT_NOGOAL, LOSS, OUT.

**Estado.** Cerrada.

---

## ADR-04 · El contexto estratifica, no entra al estado

**Decisión.** Ajustar una cadena por nivel de contexto.

**Consecuencias.** Permite comparar $P(\cdot|c)$ entre contextos. Divide la
muestra en tres.

**Estado.** Cerrada.

---

## ADR-05 · Encogimiento con λ por validación cruzada

**Decisión.** $\hat p^*(\lambda)$ con λ por CV por bloques de posesión.

**Estado.** Cerrada, **matizada por ADR-22**: la CV no identifica λ.

---

## ADR-06 · El prior excluye a la unidad focal

**Decisión.** `--prior exclude_focus` por defecto.

**Estado.** Cerrada en v0.4. Era un **bug real** (#4), no una preferencia.

---

## ADR-07 · Bootstrap por posesión, no por evento

**Decisión.** La unidad de remuestreo es la posesión completa.

**Estado.** Cerrada.

---

## ADR-08 · La nula del LRT se calibra por bootstrap

**Decisión.** Distribución nula por remuestreo de posesiones del pool base.

**Consecuencias.** Test válido bajo dependencia. **Y ahora sabemos que también
lo hace robusto a la mala especificación medida en ADR-21**, porque no depende
de que $G^2 \sim \chi^2$.

**Estado.** Cerrada.

---

## ADR-09 · FDR (Benjamini–Hochberg), no FWER

**Decisión.** Control de FDR.

**Consecuencias.** **Insuficiente por sí solo**: con 67k transiciones se
rechazan 80 de 80 estados. El FDR controla falsos positivos, no trivialidad.
Ver ADR-25.

**Estado.** Cerrada, complementada por ADR-25.

---

## ADR-10 · IC bootstrap básico, no percentil

**Decisión.** Percentil invertido por defecto.

**Estado.** Cerrada.

---

## ADR-11 · Fase `restart` separada de `set_piece`

**Decisión.** Cuatro fases: open / transition / restart / set_piece.

**Consecuencias.** `set_piece` baja a ~15%. **Verificado en dos clubes**: 14.8%
(América) y 14.6% (Cruz Azul).

**Estado.** Cerrada.

---

## ADR-12 · `phase_order` explícito en el config

**Estado.** Cerrada. Era un **bug silencioso** (#3).

---

## ADR-13 · Filtro de acarreos cortos (5 m)

**Decisión.** `min_carry_length = 5.0 m`, configurable.

**Consecuencias.** Acciones por posesión: 9.0 → 6.9. **Y ahora sabemos que es
insuficiente**: el 49–50% de los acarreos que sobreviven al filtro siguen sin
salir de zona, y los pases aportan el 60% de las auto-transiciones. El umbral es
cosmético a resolución 5×4.

**Estado.** Cerrada provisionalmente; **sensibilidad todavía pendiente** (única
de la lista original que sigue sin hacerse).

---

## ADR-14 · Absorción terminal obligatoria

**Decisión.** Añadir transición hacia `LOSS` cuando la última acción deja el
balón en estado transitorio.

**Consecuencias.** En los datos reales son 11,268 transiciones artificiales de
222,251 (5.1%) en el América. Hay que declararlo al interpretar la cola de la
distribución de longitud (ADR-21).

**Estado.** Cerrada.

---

## ADR-15 · Una transición por acción (inicio → fin)

**Decisión.** Cada acción aporta una transición de su propio inicio a su propio
fin. Criterio de Rudd (2011) y Singh (2018).

**Consecuencia no anticipada.** Un pase de 6 m dentro de una zona de 24×20 m es
una transición $i \to i$. De ahí el 28% de auto-transiciones. Una formulación
alternativa —contar solo cambios de zona— eliminaría el problema pero cambiaría
la interpretación de $N$ y rompería la comparabilidad con la literatura.

**Estado.** Cerrada. La alternativa queda **registrada como no implementada**.

---

## ADR-16 · Comparación DT vs DT dentro del club como diseño principal

**Decisión.** `--baseline other_coaches` por defecto.

**Estado.** Cerrada. Es el diseño más fuerte disponible.

---

## ADR-17 · GNN descartado

**Razones.** (i) StatsBomb 360 son freeze frames sin velocidades. (ii) Censura
por área visible. (iii) La rúbrica premia comprensión y ROI, no AUC. (iv) Sin
GPU CUDA y sin tiempo.

**Estado.** Cerrada. **No reabrir.**

---

## ADR-18 · Secciones de Poincaré descartadas

**Razón.** Poincaré requiere sistemas autónomos con órbitas recurrentes. Un
partido es un proceso estocástico forzado, sin periodicidad.

**Estado.** Cerrada. **No reabrir.**

---

## ADR-19 · polars + numpy + scipy; sin Rust, sin frameworks pesados

**Estado.** Cerrada.

---

## ADR-20 · Todo parámetro en `config/default.yaml`

**Estado.** Cerrada, reforzada por ADR-23 (el hash del config va en cada
reporte).

---

## ADR-21 · Markov de primer orden se mantiene pese al rechazo

**Contexto.** El contraste de bondad de ajuste sobre la distribución phase-type
de longitud de posesión (`05_VALIDATION` §4.1, antes "no implementado") se
ejecutó y **rechaza**: KS ≈ 0.09 contra p95 nulo ≈ 0.012, p = 0.005, replicado
en Jardine, Solari y el club agregado.

El patrón no es cola pesada simple sino **sobredispersión**: menos masa en el
centro (k=2–10), más en la cola (k≥12), media casi perfecta (+1.8%). Es la firma
de una mezcla de al menos dos poblaciones de posesión.

**Decisión.** Mantener la cadena de primer orden y **declarar la limitación con
su magnitud medida**.

**Alternativas consideradas.**
- Ampliar el estado con la zona anterior → cuadra el número de parámetros; con
  Ortiz en 18,917 transiciones es inviable.
- Añadir un indicador de longitud acumulada al estado → rompe la
  interpretabilidad espacial de $N$ y $\nu$, que es el activo del proyecto.
- Modelo semi-Markov (Fase 6) → es la respuesta correcta a plazo, no ahora.

**Justificación.** El contraste de la Fase 3 compara dos cadenas ajustadas
igual; una mala especificación compartida se cancela en buena medida. La nula se
calibra por bootstrap (ADR-08), así que no depende de la especificación. Y el
patrón es **idéntico en las tres unidades**, lo que hace verificable la premisa
de que es compartido.

**Consecuencias.**
- La Fase 7 (simulación) requiere ampliar el estado antes de ser creíble. La
  validación por KS de `05_VALIDATION` §4.4 fallaría, y ya sabemos por qué.
- Va al reporte como limitación cuantificada, no como asterisco.

**Estado.** Cerrada.

---

## ADR-22 · λ no se identifica por CV: separar significancia de magnitud

**Contexto.** La curva de CV es una meseta: 0.006 nats entre λ=100 y λ=2000,
contra 0.054 de λ=0 a λ=1. Elegir 500 en vez de 200 cambia el poder predictivo
en 0.6%.

Simultáneamente, λ **sí** determina las magnitudes reportadas. Por álgebra sobre
`_diff_estimate`, la diferencia estimada es la real multiplicada por
$n_i/(n_i+\lambda)$: atenuación mediana 0.585 con λ=500 y 0.261 con λ=2000, y el
factor varía **por renglón**.

**Decisión.** **Significancia con λ\*, magnitudes con λ=0**, declarado
explícitamente en el reporte. No presentar λ\*=500 como un valor preciso, sino
como un punto dentro de un rango indistinguible.

**Alternativas.** λ fijo arbitrario (indefendible); reportar todo con λ\*
(atenúa las magnitudes sin avisar); reportar todo con λ=0 (pierde la
estabilización que la CV sí muestra que ayuda).

**Consecuencias.** El reporte lleva dos columnas donde antes llevaba una. Es más
honesto y más largo de explicar.

**Estado.** Cerrada. **Resuelve P-04.**

---

## ADR-23 · Todo artefacto declara su procedencia

**Contexto.** Una `cv_lambda.png` generada en v0.3 (rejilla hasta 500, λ\*=50)
sobrevivió al arreglo de la fuga de prior y siguió en `figures/` diciendo un
número que ningún resultado posterior respaldaba.

**Decisión.** Cada reporte JSON incluye `provenance` con hash del config,
commit de git y versión del paquete. Cada `.npz` de `phase1` incluye además
`unit`, `value`, `baseline`, `prior_mode` y `lam`.

**Consecuencias.** Cualquier artefacto sin `provenance` es anterior al parche y
debe regenerarse. Tests: `test_provenance.py`.

**Estado.** Cerrada. Implementa `08_REPRODUCIBILITY` §9.

---

## ADR-24 · Contrato de identidad entre fases

**Contexto.** Bug #7. `phase2` y `phase3` leían la matriz del `.npz` que dejó la
última corrida de `phase1`, pero usaban su propio `--value` para rotular. Se
modelaba a Ortiz y se rotulaba "Andre Jardine", sin aviso.

**Decisión.** `phase1` graba la identidad de lo que estimó; `phase2` y `phase3`
**abortan con `exit=1`** si no coincide, con mensaje que indica el comando
correcto.

**Alternativas.** Que `phase2` recalcule la matriz (duplicaría trabajo y crearía
una segunda ruta de código para lo mismo — el patrón del bug #2).

**Consecuencias.** El pipeline exige orden explícito. Es fricción deliberada.

**Regla general derivada.** Todo artefacto compartido en disco entre fases
declara qué lo produjo, y quien lo consume verifica. Probar consumidor y
productor por separado no prueba el contrato: de ahí `test_npz_contract.py`,
añadido después de que `test_matrices_identity.py` pasara en verde mientras el
guardarraíl abortaba siempre.

**Estado.** Cerrada.

---

## ADR-25 · La huella táctica se ordena por tamaño de efecto, no por significancia

**Contexto.** Con 67,492 transiciones, `phase3` rechaza 59 de 80 estados con
λ\*=500 y **80 de 80** con λ=0. Los p-valores tocan el piso del bootstrap
(1/501). Un mapa uniformemente significativo no indica dónde mirar, que es para
lo que existe la huella.

$G^2_i = 2n_i D_{KL}(\hat p_i \Vert q_i)$ escala con $n_i$: mide evidencia, no
magnitud.

**Decisión.** Rankear y graficar por **distancia de variación total por
renglón**, $\frac12\sum_j|p_{ij}-q_{ij}|$, que está en $[0,1]$ y no escala con
$n$. La significancia se conserva como filtro, no como criterio de orden. El
entregable es "los 10 estados donde más difiere".

**Alternativas.** Subir el umbral de FDR (arbitrario); usar solo los IC de la
diferencia (ya disponibles, pero por celda y no por renglón, y atenuados por λ).

**Consecuencias.** `plots.fingerprint_map` y `TacticalFingerprint.to_frame`
necesitan cambio. `n_boot` sube a 2000 o los p se declaran como `< 0.002`.

**Implementacion.** `scripts/09_huella_efecto.py`. Tres filtros y un orden:
significancia (FDR sobre los 80 renglones), fiabilidad ($z\geq3$), masa
($n\geq50$); orden por `TV_exceso`.

**Resultado.** La cascada de filtros:

| filtro | Jardine | Anselmi |
|---|---|---|
| significativos tras FDR | 80 de 80 | 71 de 80 |
| TV sobre p95 nulo | 61 | 39 |
| $z \geq 3$ | 44 | 23 |
| seleccionados | **44** | **22** |

**Estado.** **Cerrada.** Ver ADR-27 (la TV cruda tambien enganaba) y ADR-28
(por que $z$ filtra pero no ordena).

---

## ADR-26 · Fechas derivadas de la estructura de `match_id`

**Contexto.** El volcado no trae `match_date` y sin fecha no hay eras. El API es
la vía correcta pero requiere credenciales que no estaban disponibles.

**Decisión.** Derivar un **orden** de los bloques de `match_id` y asignar fechas
sintéticas dentro del calendario real de cada torneo, emitiendo un
`match_dates.csv` compatible con `eras.load_match_dates`.

**Justificación empírica.** La cobertura resultante coincide con Wikipedia en
ocho entrenadores de dos clubes, con error máximo de 2–3 partidos concentrado en
las fronteras a media temporada. Una era de diez días con dos partidos
(Joaquin Moreno I) queda **exactamente** ubicada.

**Supuesto frágil declarado.** Dentro de un bloque, orden de `match_id` ≈ orden
de jornada. No verificado. Afecta a los cambios de DT a media temporada: uno en
el América, **cuatro** en Cruz Azul.

**Consecuencias.** El apaño vive en un solo script y es reemplazable por las
fechas reales sin tocar nada aguas abajo. Para Cruz Azul, las fechas reales
**no son opcionales** si se quiere analizar a Gutiérrez, Ferretti o Moreno.

**Lección de proceso.** La primera versión de la detección automática de umbral
se calibró sobre el América y falló en Cruz Azul. La versión actual usa la
estructura conocida (8 torneos) en vez de una heurística de saltos. **Ninguna
heurística ajustada a un solo club debe presentarse como general.**

**Estado.** Cerrada, con las fechas del API como mejora pendiente.

---

## Decisiones pendientes

| # | Pregunta | Bloqueada por | Estado |
|---|---|---|---|
| P-01 | ¿La rúbrica evalúa análisis táctico o valuación de IP? | organizadores | abierta |
| ~~P-08~~ | ~~Solapamiento de plantilla~~ | — | **CERRADA: ADR-34** |
| P-09 | ¿Se verifica la orientación del eje Y de StatsBomb? | una tarde | ✅ **cerrada 2026-08-22** (bug #12). `13_verificar_ejes.py` |
| P-10 | ¿Se implementa Fase 8 (Wasserstein)? | tiempo | abierta |
| ~~P-02~~ | ~~Resolución final de la malla~~ | — | **CERRADA: 5×4**, `params_per_obs` = 0.502 en 6×4 sobre Ortiz |
| P-03 | ¿Definición propia de contraataque? | decidir narrativa | abierta |
| ~~P-04~~ | ~~¿λ fijo o por CV?~~ | — | **CERRADA: ADR-22** |
| P-05 | ¿Se implementa Fase 5 (defensa)? | tiempo | abierta |
| P-06 | ¿Se cambia ADR-15 a "solo cambios de zona"? | impacto en comparabilidad con Rudd/Singh | **nueva** |
| P-07 | ¿Se escala a 18 equipos antes o después de Fase 4? | terminar ADR-25 | **nueva** |


---

## ADR-27 · La TV se corrige por su nula antes de ordenar

**Contexto.** ADR-25 cambio el orden de $G^2$ a TV para no premiar renglones
densos. Pero la TV cruda tiene el sesgo **opuesto**: $TV \geq 0$ siempre, y con
pocos datos sale alta por puro ruido de muestreo. Ordenar por TV cruda premia a
los renglones ralos.

**Decision.** Restar la nula:

$$TV^{exceso}_i = TV_i - \text{mediana}(TV^{null}_i)$$

donde la nula se obtiene remuestreando posesiones de la linea base con el MISMO
tamano de muestra que el foco.

**Magnitud del problema, medida.** El **52%** (Jardine) y el **63%** (Anselmi)
de la TV mediana observada es tamano de muestra, no estilo.

**Consecuencias.** El entregable es el top por `TV_exceso`. La TV cruda y la
nula se reportan juntas para que el lector vea la correccion.

**Estado.** Cerrada.

---

## ADR-28 · $z$ filtra fiabilidad; `TV_exceso` ordena magnitud

**Contexto.** Restar la mediana corrige el sesgo pero no la varianza. En
renglones ralos `TV_exceso` sigue siendo una loteria: `z40|transition` de
Anselmi encabezaba el ranking con **n = 15**.

La correccion natural parece estandarizar:

$$z_i = \frac{TV_i - \text{med}(TV^{null}_i)}{\text{DE}(TV^{null}_i)}$$

**Pero eso reintroduce el problema.** Bajo la nula
$\text{DE}(TV^{null}_i)\sim 1/\sqrt{n_i}$, asi que
$z_i \approx TV^{exceso}_i\cdot\sqrt{n_i}$. **$z$ escala con $\sqrt{n}$**: es
el defecto de $G^2$ ($\propto n$) entrando por la puerta de atras, mas suave
pero el mismo.

| criterio | a quien premia |
|---|---|
| $G^2$ | renglones densos ($\propto n$) |
| $z$ | renglones densos ($\propto \sqrt{n}$) |
| $TV_{exceso}$ | renglones ralos (varianza alta) |

Ninguno de los tres sirve solo.

**Decision.** $z$ como **filtro** ($z\geq3$), `TV_exceso` como **orden**. Mas
un filtro de masa ($n\geq50$): un renglon con 15 observaciones no sostiene una
afirmacion tactica aunque pase todo lo demas.

Es la misma estructura que significancia + TV, un nivel mas adentro: filtro por
fiabilidad, orden por magnitud.

**Consecuencias.** El piso de la DE se acota para evitar division por cero. Los
filtros son parametros del script (`--z-min`, `--n-min-top`), no constantes.

**Estado.** Cerrada.

---

## ADR-29 · Multiplicidad por etapas, no FDR global sobre 6,720 celdas

**Contexto.** El FDR cubria los 80 renglones, pero los IC celda a celda son
$80\times84 = 6{,}720$ **sin corregir**: dos criterios distintos en la misma
salida.

**Alternativa rechazada.** BH global sobre las 6,720. Casi todas son
estructuralmente cero —transiciones imposibles entre zonas lejanas— y diluirian
el denominador hasta matar cualquier hallazgo real.

**Decision.** Procedimiento condicional de dos etapas:

1. Seleccionar renglones (ADR-25, ADR-27, ADR-28).
2. Aplicar BH **solo dentro de esos renglones** (~150–200 celdas).

**Consecuencias.** Se declara explicitamente como **test condicional de dos
etapas** en el reporte y en el JSON de salida (`"fdr_celdas"`). Presentarlo como
un unico test con FDR global seria incorrecto.

**Estado.** Cerrada.

---

## ADR-30 · Ninguna distancia se reporta sin su nula

**Contexto.** Tres veces se reporto una distancia sin distribucion de
referencia, y las tres veces la conclusion estaba mal:

| caso | reportado | tras calibrar la nula |
|---|---|---|
| `detect_regime_changes` | TV = 0.22 como quiebre de era | ruido de calendario |
| Huella tactica | orden por TV cruda | 52–63% era tamano de muestra |
| Contraste de contextos | TV = 0.04 como "no adapta" | 90% ruido; **conclusion contraria** |

El caso del contexto es el mas grave: se iba a reportar "filosofia, no
reactividad" y la realidad es que **si hay adaptacion al marcador** (p < 0.01 en
ambos clubes), solo que es un orden de magnitud menor que la firma tactica.

**Decision.** Regla dura: **toda distancia (TV, KL, Wasserstein, cualquier
divergencia) va acompanada de su distribucion nula empirica.** Sin nula no se
reporta.

**Corolario: no se afirma la nula.** Si un contraste no rechaza, la frase es "no
detectamos un efecto mayor a X", con X = p95 de la nula (**efecto minimo
detectable**). Nunca "no hay efecto". Ya paso con el placebo de `regimes`, donde
tres eras "aprobaron" por falta de potencia (17–39 partidos), no por
homogeneidad.

**Consecuencias.** Cada script de distancia reporta observado, nula, exceso y
efecto minimo detectable. Anade coste computacional (permutaciones o bootstrap)
y es innegociable.

**Estado.** Cerrada. Es el principio metodologico central del proyecto.

---

## ADR-31 · Los IC se validan por cobertura, no por argumento

**Contexto.** ADR-07 (bootstrap por bloques) y ADR-10 (IC basico) se eligieron
por argumento teorico. Nunca se comprobo que los intervalos cubrieran su nivel
nominal.

**Decision.** Estudio de cobertura empirica con generador **a nivel de cadena**:
se fija $P$, se muestrean posesiones, la verdad es exacta.

`synth.py` NO sirve para esto: inyecta el sesgo a nivel de generador de eventos,
asi que la $P$ verdadera no se conoce en forma cerrada. Sin parametro verdadero
no hay cobertura que medir.

**Precision conceptual.** La cobertura se mide contra el **parametro
verdadero**, no contra el EMV. Y con $\lambda>0$ el estimador apunta a la
diferencia ATENUADA (ADR-22), asi que el estudio corre con $\lambda=0$ para
aislar la mecanica del remuestreo.

**Resultados.**

| n posesiones | basic | percentile |
|---|---|---|
| 300 | 0.935 | 0.923 |
| 1500 | 0.944 | 0.942 |
| 3000 | 0.944 | 0.943 |

1. Cobertura converge a 0.944 contra 0.95 nominal. **Los IC son de fiar.**
2. `basic` supera a `percentile` en muestras chicas: **ADR-10 confirmada
   empiricamente**, justo donde importa (eras de ~2,500 posesiones).
3. Bajo mala especificacion (mezcla) la cobertura solo cae a 0.938: **refuerza
   ADR-21**.
4. **ADR-07 matizada**: el bootstrap por bloques NO cambia nada para las celdas
   de $P$ (0.1091 vs 0.1091), por la factorizacion de Billingsley. **Si importa
   para $E[T]$**: 19% mas ancho. La justificacion original era correcta pero se
   aplicaba al lugar equivocado.

**Estado.** Cerrada.

---

## ADR-32 · Las cantidades derivadas se reportan con IC propio

**Contexto.** El resultado principal del proyecto —"Jardine sostiene posesiones
un 20% mas largas"— era un **estimador puntual**. `bootstrap_diff` da IC para
celdas de $P$, no para $E[T]$, y las cantidades reportadas pasan por
$N=(I-Q)^{-1}$, funcion NO LINEAL de la matriz completa. No hay forma de
derivar su IC de los IC celda a celda.

**Decision.** `scripts/08_ic_derivados.py`: bootstrap por posesion de $E[T]$,
$P(\text{gol})$ y $P(\text{remate})$, remuestreando tambien $\alpha$ (si se
fijara, el IC ignoraria la incertidumbre sobre donde empiezan las posesiones).

**Resultados.**

| comparacion | $E[T]$ | IC 95% |
|---|---|---|
| Jardine vs Solari | +22.4% | [+18.6%, +26.4%] |
| Anselmi vs Reynoso | +25.6% | [+21.4%, +29.7%] |
| Jardine vs Ortiz | +7.9% | [+3.9%, +11.8%] |

**Hallazgo derivado.** Ninguna diferencia en $P(\text{gol})$ es significativa, y
$P(\text{remate})$ va en direcciones opuestas segun la pareja. **Duracion y
peligro son dimensiones independientes del estilo.**

**Consecuencias.** Jardine vs Ortiz pasa de 🟡 a 🟢 en `10_RESULTADOS.md`. Todo
titular del reporte lleva IC.

**Estado.** Cerrada.


---

## ADR-33 · El "nucleo estable" se descarta: sesgo por longitud

**Contexto.** El nivel 2 del control de plantel repetia el analisis usando solo
las posesiones donde los jugadores compartidos ejecutaron la mayoria de las
acciones. La idea era: si la diferencia persiste con el mismo personal, no puede
ser cambio de personal.

**El problema.** Cualquier filtro basado en "quien ejecuto las acciones"
**selecciona por longitud de posesion**: una posesion de 15 acciones tiene mucha
mas probabilidad de incluir a alguien fuera del nucleo que una de 3. Y la
longitud es exactamente la variable de respuesta.

Es circularidad: se condiciona la retencion de la muestra al valor de lo que se
mide. El nombre tecnico es **length-biased sampling** (NO "sesgo de
supervivencia", que es otro fenomeno).

**Evidencia.** El diagnostico automatico mide la longitud media de las
posesiones retenidas contra las descartadas, y el DIFERENCIAL entre eras:

| umbral | sesgo diferencial | delta Jardine vs Ortiz |
|---|---|---|
| 0.5 | 37 pp | +11.9% |
| 0.7 | 30 pp | +8.6% |
| 0.9 | 22 pp | **-24.3%** ← el signo se invierte |

**Un filtro mas estricto NO es mas riguroso.** Aqui es demostrablemente peor.

**Decision.** El nivel 2 se **descarta como resultado** y se reporta como
limitacion detectada algoritmicamente. Los niveles 1 (solapamiento) y 3
(intra-jugador) no estan afectados: el 1 es un conteo y el 3 no filtra
posesiones.

**Alternativa considerada y rechazada.** Reponderar las posesiones retenidas
para igualar la distribucion de longitud entre eras. Es maquinaria adicional
para rescatar el mas debil de los tres disenos, cuando el nivel 3 ya responde la
pregunta mejor.

**Estado.** Cerrada. Que el script detecte su propia invalidez es en si un
resultado presentable.

---

## ADR-34 · Diseno intra-jugador como respuesta a la confusion con el plantel

**Contexto.** La amenaza 4.1 de 05_VALIDATION —"lo que mides no es el DT, es que
tuvo mejores jugadores"— era la mas seria que quedaba viva. No se puede eliminar
con datos observacionales; se puede cuantificar y se puede disenar alrededor.

**Decision.** Tres niveles, de mas barato a mas fuerte:

1. **Solapamiento** (nivel 1): que fraccion de las acciones de la era B la
   ejecutaron jugadores que ya estaban en la era A. Es un conteo.
2. **Nucleo estable** (nivel 2): descartado, ver ADR-33.
3. **Intra-jugador** (nivel 3): para cada jugador con datos en ambas eras,
   contrastar si SU matriz de transicion cambio. Prueba de permutacion por
   jugador (las etiquetas de era son intercambiables bajo la nula) con control
   de FDR sobre los jugadores testeados.

El nivel 3 es la traduccion de un **diseno de efectos fijos** al mundo de las
cadenas: el jugador es su propio control.

**Resultados.**

| comparacion | cambian tras BH | esperados por azar |
|---|---|---|
| Jardine vs Ortiz | 9 de 17 | 0.9 |
| Anselmi vs Reynoso | 4 de 5 | 0.2 |
| Jardine vs Solari | 4 de 13 | 0.7 |

**Limitacion que NO desaparece y hay que declarar.** Aunque el jugador sea el
mismo, sus companeros, su posicion y sus rivales cambian. El nivel 3 acota mucho
la critica pero no la elimina.

**Consecuencias.** `possessions.py` graba `player_id` y `player` en las
transiciones. La amenaza 4.1 pasa de "no implementada" a "respondida con
evidencia".

**Estado.** Cerrada.

---

## ADR-35 · El prior son los rivales, no la liga (y hay que decirlo)

**Contexto.** `_not_focus` filtra `(coach != value) | coach.is_null()`. Como
`transitions.parquet` contiene los 18 equipos de los partidos analizados y la
columna `coach` es nula para los 17 rivales, **el `is_null()` los incluye a
todos**.

Esto se documento tarde y es contraintuitivo: es facil suponer que el prior son
"los otros entrenadores del club".

**Decision.** Mantener el comportamiento —un prior mas ancho es mejor prior— y
**declararlo explicitamente** en la documentacion y el reporte.

**Consecuencia declarada.** Los 17 rivales NO son una muestra aleatoria de la
liga: son los que ese club enfrento, con la composicion de su calendario. La
amenaza 4.3 de 05_VALIDATION sigue viva hasta tener los 18 equipos.

**Y una consecuencia sobre lambda.** La lectura "el America se parece bastante a
sus rivales" depende de quien compone el prior. **No sobrevive al cambio** y
habra que reescribirla (ver 12_API_STATSBOMB §5).

**Estado.** Superada (2026-09-14): con el API el prior es la liga completa sin el club focal (`16_MIGRACION_API.md` §5).

---

## ADR-36 · No agrupar entrenadores por clustering para ajustar lambda

**Contexto.** Surgio la idea de usar k-means o DBSCAN sobre las matrices de
transicion para encoger hacia "entrenadores de estilo parecido" en vez de hacia
"todos los demas". Formalmente seria un modelo jerarquico con grupos, que es
legitimo.

**Decision.** No implementarlo.

**Razones.**

1. **La premisa es falsa**: lambda YA es personalizado por entrenador.
   `cv_lambda` corre sobre las transiciones del foco, asi que cada era obtiene su
   propio lambda*.
2. **Fuga de prior en forma sutil**: se agruparia usando las mismas matrices que
   luego se van a encoger. El grupo de Jardine se define en parte POR Jardine,
   asi que su prior lo contendria. Es exactamente ADR-06 en una version mas
   dificil de detectar.
3. **Beneficio incierto**: la curva de CV es una meseta (0.006 nats entre 100 y
   2000), asi que un prior mejor apenas movera lambda*.

**Si algun dia se hace**, la unica version defendible excluye al foco al
construir el cluster, y requiere su propia validacion.

**Estado.** Cerrada. **No reabrir sin argumento nuevo.**

---

## ADR-37 · No comparar entrenadores entre clubes como resultado principal

**Contexto.** La distancia de variacion total compara cualquier par de
distribuciones sobre el mismo espacio de estados; matematicamente no hay
obstaculo para medir Jardine (America) contra un tecnico del Mazatlan.

**Decision.** No usarlo como titular. Comparar dentro del mismo club (ADR-16).

**Razones.**

1. **Confusion total**: la distancia entre clubes absorbe plantilla,
   presupuesto, cantera y calendario. Es el confusor que ADR-16 evita.
2. Si se quisiera hacer bien, la forma correcta seria diferencias en
   diferencias: cuanto se desvio cada tecnico de la linea base de SU club. Pero
   **la linea base de un club contiene a sus propios entrenadores** (Jardine es
   el 53% de las transiciones del America), asi que habria que excluir al foco
   de su propia base.
3. **Las TV no son comparables entre clubes sin su nula** (ADR-30). Un club con
   eras mas cortas tendra TV mayor por ruido de muestreo, no por tactica.

**Lo que si es defendible**: un jugador que paso por dos clubes bajo dos
tecnicos distintos es un diseno intra-jugador que cruza clubes (ADR-34). Pero
las muestras serian diminutas.

**Estado.** Cerrada.

---

## ADR-38 · El entregable es un HTML autocontenido, no Streamlit

**Contexto.** El prototipo se hizo en Streamlit. Funciona, pero apila bloques en
columnas: no permite rejillas asimetricas, tarjetas de tamanos distintos ni
barras laterales, y no hay CSS que cambie eso.

**Decision.** El entregable es `reporte.html`, generado por
`scripts/12_reporte_html.py`: un solo archivo con los datos embebidos como JSON,
selectores en JavaScript y graficas en SVG.

**Restriccion dura: CERO dependencias externas.** Ni CDN, ni fuentes remotas, ni
librerias. Se evaluo cargar Tailwind desde un CDN y **se rechazo**: el archivo
dejaria de funcionar sin internet, que es precisamente su mayor virtud.

**Ademas es el formato que pide la convocatoria** (reporte en HTML).

**Decision de diseno sobre las canchas.** Se evaluo suavizar la huella con
desenfoque gaussiano o hexbins, para que pareciera "nube de calor". **Se
rechazo**: el modelo estima una probabilidad CONSTANTE por zona. Difuminar los
bordes sugeriria una resolucion espacial continua que no existe, y ante un
jurado tecnico eso es una tergiversacion. Se usa un halo suave que no borra los
bordes.

**Streamlit se conserva** (`app.py`) para exploracion durante el desarrollo.

**Estado.** Cerrada.

---

# Bloque defensivo (D1) — ADR-39 a ADR-48

> Integradas el 2026-08-26 desde `ACTUALIZACIONES_DOCS.md` §3 y
> `ACTUALIZACIONES_DOCS_v2.md` §3, que quedan como histórico.

---

## ADR-39 · La defensa se modela como cadena conjugada

La fase sin balón no es un proceso propio: es **el proceso del rival,
modificado**. `transitions.parquet` ya contiene las posesiones de los 18 equipos
del volcado, así que la cadena conjugada sale del mismo artefacto con un filtro.

**Alternativa descartada**: un modelo defensivo independiente sobre eventos
`Pressure`, `Duel` e `Interception`. Contar acciones defensivas por zona **sin
denominador de exposición** mide dónde juega el rival, no dónde presionas tú —
el mismo error de longitud del bug #11.

**Estado.** Cerrada.

---

## ADR-40 · El espejo es una permutación de índices, no una reflexión de coordenadas

StatsBomb normaliza al marco de ataque del ejecutante. Verificado empíricamente
sobre las filas de los rivales (2026-08-24): remates x̄ 103.97 (club) y 102.57
(rivales); saques de meta p10 = 7.0 en ambos lados.

La cadena conjugada **se estima en marco nativo**. El espejo se aplica al
presentar, con `StateSpace.mirror_zone`, que sobre malla uniforme es exactamente
$(i_x,i_y) \mapsto (n_x-1-i_x,\, n_y-1-i_y)$.

**Por qué sobre índices y no sobre coordenadas**: reflejar antes de `zone_of`
rompería `coordinate_sanity` (daría corr ≈ −0.72, es decir `ok=False` en cada
corrida sin que nada estuviera mal), metería la transformación en la ruta
numérica e interactuaría con el `clip`. Sobre índices es exacto, sin punto
flotante, y aislado en una función pura testeable — la lección del bug #12.

Verificado: involución y consistencia con `zone_of` sobre 20,000 puntos y cinco
mallas; tres jugadores rivales de banda conocida (Mozo, Sanabria, González) caen
en la banda contraria tras el espejo, con 86.6%, 72.3% y 82.9%.

**Estado.** Cerrada.

---

## ADR-41 · `min_actions = 1` en perspectiva defensiva

Una posesión de una acción que termina en absorción no recibe absorción terminal,
y `min_actions = 2` la descarta. En la ofensiva eso ya estaba contabilizado
($P(T<2)=0$ por construcción). En la conjugada es peor: **una posesión rival de
una sola acción es el producto de una presión exitosa** — justo lo que se quiere
medir.

Medido sobre 18,214 posesiones rivales del América: descarte global 9.06%, con
8.63% frente a Jardine y 10.49% frente a Solari. Rango de 1.86 pp (22% relativo),
todo concentrado en $T=1$. Sesgo diferencial estimado sobre $E[T^{def}]$: ~0.09
acciones, **el mismo orden que los efectos a detectar**.

Al regenerar se recuperaron 2,037 posesiones en el América (12.91%) y 1,981 en
Cruz Azul (13.20%) — más de lo predicho, porque el diagnóstico no aplicaba
`min_carry_length`.

**Consecuencia a declarar siempre**: $E[T^{att}]$ y $E[T^{def}]$ **no son
comparables entre sí**. Usan `min_actions` distinto.

**Estado.** Cerrada.

---

## ADR-42 · `under_pressure` es una bandera, no un booleano

StatsBomb escribe `true` u **omite la llave**. Medido: **114,552 true / 0 false /
468,963 null** sobre 583,515 eventos.

Un filtro por `is_not_null()` daría **π ≈ 1 en todas partes sin lanzar un solo
error**. Es el bug #13, y se evitó porque `14_diagnostico_defensa.py` inspeccionó
el esquema antes de escribir una línea de estimación.

- `fill_null(False)` obligatorio.
- **`null` en las filas TERMINAL**, que son artificiales y no corresponden a
  ningún evento. Ponerlas en `False` diluiría π más en las eras con más
  absorciones terminales: sesgo diferencial otra vez.

Validación cruzada disponible y **no usada aún**: hay 53,006 eventos `Pressure`
contra ~57k marcas `under_pressure` por lado. Dos lecturas independientes de la
misma cantidad.

**Estado.** Cerrada.

---

## ADR-43 · `coach` y `coach_faced` son columnas distintas

- `coach` = quién dirigía al **ejecutante**. Null en los rivales, por diseño.
- `coach_faced` = contra qué DT se jugó el partido. Aplica a **todas** las filas.

Colapsarlas hacía que `select_units(unit='coach')` devolviera vacío sobre
transiciones defensivas, con un error que apuntaba al lugar equivocado.
`test_coach_faced.py` verifica que coinciden sobre las filas del club.

**Estado.** Cerrada.

---

## ADR-44 · Estandarización directa por rival

Con soporte discreto y positividad, es la fórmula de ajuste de Pearl con
estratos saturados.

**Alternativa descartada**: *propensity score matching*. Existe para cuando no
puedes estratificar (covariables continuas, celdas vacías); aquí las celdas están
llenas y PSM introduciría un modelo de asignación que especificar y defender para
aproximar un estimador que ya es exacto.

**Lo que NO ajusta, y hay que declarar** (corrección de v2):

1. **Localía** — se añade como estrato al mismo estimador. Pendiente.
2. **Momento del partido** — ídem. Pendiente. El reto los pide explícitamente.
3. **Endogeneidad de la asignación de entrenadores** — un DT llega tras una mala
   racha, así que su era empieza condicionada al rendimiento previo. **Esto no
   se corrige con ningún ajuste por observables** y va a limitaciones.

**Estado.** Cerrada, con tres limitaciones declaradas.

---

## ADR-45 · `perspective` entra al contrato de identidad del `.npz`

Sin ella, `phase1 --perspective defense` seguido de `phase2` (por defecto
`attack`) **pasa el guardarraíl**: `unit` y `value` coinciden. Es el bug #7 con
un campo más.

Verificación **estricta**: un `.npz` sin el campo se rechaza. Invalida todos los
artefactos anteriores y obliga a un `generar_todo.sh` completo.

Es el precio correcto: el parquet cambió con ADR-41, así que estaban obsoletos
igualmente, y `04_DATA_CONTRACT.md` §5 ya exige rerun completo al cambiar una
definición.

**Estado.** Cerrada.

---

## ADR-46 · Asimetría de credibilidad bajo sobreajuste

`params_per_obs` supera 0.5 en **seis de diez unidades ofensivas** a malla 5×4.
El criterio de ADR-25 se calibró sobre Ortiz (26 partidos) creyéndola la era más
corta; Herrera (17), Ferretti (16) y Moreno II (11) son menores.

**No se reduce la malla**: el barrido ya mostró que los efectos grandes
sobreviven entre 12 y 30 zonas. Se adopta una etiqueta explícita, persistida en
`reports/manifiesto_unidades.json`, más una tabla de sensibilidad a 4×3.

**El sesgo del sobreajuste va hacia encontrar diferencias**, así que un resultado
**nulo** desde una unidad sobreajustada es *más* robusto, no menos. El hallazgo
"Sánchez vs Ferretti sin efecto" viene precisamente de dos de esas unidades.

> **El argumento es DIRECCIONAL, no simétrico.** Refuerza los nulos y
> **debilita** los positivos que salgan de esas mismas unidades. Un titular
> significativo desde Herrera, Gutiérrez, Ferretti o Moreno II **no puede**
> apoyarse en este razonamiento: va con la etiqueta y nada más.

**Moreno II defensivo (`params_per_obs` = 1.016) queda excluido.** Más parámetros
que observaciones no es sobreajuste: es un modelo indeterminado.

**Estado.** Cerrada.

---

## ADR-47 · Separación de familias para FDR

Los contrastes de estandarización por rival y los de $\pi_e(z)$ son **familias
separadas**. Responden preguntas distintas sobre objetos distintos —proporciones
empíricas agregadas por posesión frente a probabilidades binomiales por zona— y
se estiman con procedimientos independientes.

Los q-valores de la familia de estandarización quedan **fijados en la corrida del
2026-08-24** y no se recalculan al añadir D1.

**Declarado antes de observar los resultados de D1.** La alternativa —familia
única recalculada al final— es igualmente válida, pero implicaría que ningún q es
citable hasta cerrar el análisis. Decidirlo *después* de ver los números sería
p-hacking sobre la estructura de la familia, aunque el razonamiento fuese
correcto.

Dentro de la familia de estandarización se separan además el conjunto
**confirmatorio** (cobertura ≥ 85%) del **exploratorio**, también declarado antes
de mirar resultados. Motivo doble: interpretativo (distinto estimando) y de
potencia (BH reparte α entre el tamaño de la familia; incluir 144 contrastes de
baja cobertura habría subido el umbral de todos).

**Estado.** Cerrada.

---

## ADR-48 · Dos subfamilias dentro del bloque de presión

**D1-CONTRASTES.** Toda afirmación de que dos eras difieren en presión: $\pi(z)$
por zona, nivel en $k\geq3$, pendiente de decaimiento, $L=1$ por fase. Nula:
permutación de la etiqueta de era **entre partidos**. Familia de descubrimiento,
BH al 5%. Tamaño: **46 contrastes**.

**D1-CALIBRACIÓN.** La asociación entre presión y desenlace, por era. Nula:
permutación de la **marca de presión** dentro de estrato (zona × tipo de acción).
No afirma que dos entrenadores difieran: **verifica que el instrumento mida
algo**. Se reporta con su p, fuera del BH conjunto con la anterior.

**Justificación de la separación.** Son asimétricas en riesgo. Un falso positivo
en la primera te hace defender que un entrenador difiere cuando no; la segunda es
una verificación del instrumento, con efectos de 11 pp en las cuatro eras y nada
marginal que corregir. Penalizar la potencia de los descubrimientos por comprobar
que la métrica no es ruido sería un castigo sin sentido.

**Exclusión declarada**: el estrato `balón parado` × $L=1$ tiene $\pi = 0$ en las
dos eras **por construcción** (una posesión de una acción nacida de saque o
córner es un despeje, con el balón parado y sin presión que anotar). Su $p = 1.0$
no es un resultado sino un estrato sin información; incluirlo inflaría la familia
y bajaría la potencia de los demás.

**Declarado antes de correr la corrección.**

### Consecuencia editorial de ADR-48

$\pi$ ponderada **por posesión** y **por acción** daban signos opuestos para
Jardine. No es un bug: son dos estimandos, y la brecha es **exactamente**

$$\pi_{\text{acción}} - \pi_{\text{posesión}} = \frac{\operatorname{Cov}(L, m)}{\mathbb{E}[L]}$$

verificada numéricamente con error de $2\times10^{-17}$. $\operatorname{Cov}(L,m) < 0$
en las cuatro eras: las posesiones rivales largas están menos presionadas. Bajo
Jardine la covarianza es más negativa (−0.0313 vs −0.0133), así que su $\pi$ por
acción cae más.

> **Toda cifra de presión debe decir explícitamente "por posesión" o "por
> acción".** Sin eso, dos frases correctas del mismo reporte se contradicen.

**Estado.** Cerrada.

---

## ADR-49 · La potencia de $\tau^2$ la manda $k$, y se cita el estimador conservador

**Contexto.** `12_API_STATSBOMB.md` §5.4 preguntaba si "estilo de entrenador" es
un concepto medible. Formalmente es $\tau^2$: la varianza entre unidades una vez
descontado el ruido de muestreo, estimada por Empirical Bayes normal-normal. Es
el hermano de $\lambda$ desde el otro lado — la confiabilidad
$\tau^2/(\tau^2+\sigma_j^2)$ es el peso de encogimiento de
`11_MATEMATICA_APLICADA.md` §3.

**Decisión 1 — medir el suelo antes de reportar el valor.**

El estimador está **truncado en cero**. Un $\tau^2 = 0$ puede significar dos
cosas incompatibles: que no hay variación, o que el diseño no puede verla.
Reportar el primero cuando pasa el segundo habría producido la conclusión *"el
estilo de entrenador no es medible"*, contradiciendo ADR-34 y los seis pilares,
**sin lanzar ninguna excepción**.

Por eso `scripts/23_potencia_tau2.py` calcula primero la curva de potencia por
simulación, con las $n$ reales y el $\sigma$ observado, y solo después el valor.

**Regla**: si el $\tau$ observado cae por debajo del suelo, la frase reportable
es *"este diseño no tiene potencia para detectarlo"*, **nunca** *"no hay
diferencia"*. Es la prohibición de afirmar la nula, aplicada aquí.

**Decisión 2 — no correr $\tau^2$ sobre un solo club.**

La simulación mostró algo contraintuitivo: **la potencia la determina el número
de unidades $k$, no el tamaño $n$ de cada una.** Con las 4 eras del América el
estimador devuelve cero el 32% de las veces habiendo variación real; con las 12
de los dos clubes, el 7%. El proyecto de córners previo, con 17 equipos de 30
observaciones, tenía mejor potencia que 4 eras de 8,694 posesiones.

Es evidente una vez visto: $\tau^2$ es una varianza **entre** unidades, y con
$k=4$ se estima a partir de cuatro números.

Esto da el argumento cuantitativo que faltaba para escalar a 18 equipos: el
beneficio no es más datos por unidad, es **más unidades**.

**Decisión 3 — se cita el estimador de ponderación mixta.**

Tres estimadores probados. El criterio de selección **no es el $\tau$ estimado
ni el suelo**, sino el comportamiento bajo la nula:

| estimador | suelo | dice $\tau>0$ con $\tau=0$ real |
|---|---|---|
| ponderación mixta | 0.247 | **15%** |
| DerSimonian–Laird | 0.124 | 45% |
| momentos sin ponderar | 0.124 | 42% |

DL y momentos tienen mejor suelo aparente **y son anticonservadores**. Elegirlos
sería elegir el número más favorable.

La ponderación mixta —promediar las desviaciones ponderando por $n$ y restar la
media **sin ponderar** de $\sigma_j^2$— es formalmente inconsistente y por eso
sesga a la baja. **Ese sesgo es la propiedad deseable aquí**: si aun así
encuentra señal, la señal está. Se conservan los tres en el script para poder
comprobar que coinciden; se reporta el conservador.

**Alternativa descartada.** Un modelo jerárquico bayesiano completo daría el
posterior de $\tau$ sin truncamiento ni elección de estimador, y es el objeto
más principiado. Requiere PyMC o Stan: ADR-19 lo excluye, y el perfil del
usuario no incluye estadística bayesiana formal (`AGENTS.md` §6). La curva de
potencia da la misma protección sin dependencias.

**Estado.** Cerrada.

---

## ADR-50 · Chequeo predictivo espacial y pseudo-residuos por celda

**Contexto.** La bondad de ajuste actual (§7.1 de `03_METHODS.md`) contrasta la
distribución de la **longitud** de posesión contra la phase-type implicada por la
cadena. Rechaza, por sobredispersión.

Ese contraste es **ómnibus sobre una sola dimensión**: dice que el modelo falla y
en qué medida, pero no **dónde** en el campo.

**Decisión.** Se añade un diagnóstico espacial: simular posesiones desde $P$ y
comparar la distribución de visitas por estado contra la observada, con el
residuo por celda proyectado sobre la cancha.

**Por qué no es circular.** $\nu$ es una cantidad **derivada** de la cadena
($N = (I-Q)^{-1}$), no algo a lo que se ajustó. Lo que se estimó son los
renglones de $P$. Comparar la distribución de visitas implicada contra la
observada es una prueba de ajuste legítima, del mismo género que el KS sobre
longitud.

**No confundir con la huella táctica.** La huella mapea $G^2$ **entre dos eras**:
dónde difieren dos entrenadores. Esto mapea **dónde la cadena falla contra sus
propios datos**. Preguntas distintas, mismo lienzo.

**Expectativa declarada antes de correrlo**: es probable que **rechace**, por la
misma sobredispersión de ADR-21. Eso no invalida el modelo — ADR-21 ya da los
tres argumentos, incluido que el impacto medido sobre la cobertura es de 0.944 a
0.938 — pero localizar el desajuste es información nueva y accionable, y un fallo
estructural medido y publicado es mejor que uno no buscado.

**Estado.** Abierta. Pendiente de implementación.

---

## ADR-51 · El módulo de geometría del remate: seis decisiones

**Contexto.** El proyecto de córners previo (xDefense) construyó una integral de
visibilidad, `goal_open`, sobre el `shot_freeze_frame`. Se porta aquí. La muestra
disponible es **cinco veces mayor** que la de aquel proyecto entero: 2,332
remates de juego abierto con 269 goles, frente a 720 remates con 51 goles.

**Decisión 1 — el filtro es `shot_type == "Open Play"`, no la disponibilidad de
foto.**

Los 32 remates sin freeze frame son **los 32 penales**. Ni uno de juego abierto.
Pero hay **4 penales que SÍ traen foto**: `goal_open ≈ 1` (los defensores están
fuera del área) y cero goles entre ellos. Filtrar por
`shot_freeze_frame.is_not_null()` los deja entrar y **atenúa el coeficiente de
`goal_open`**, que es justo el efecto a medir.

Es el bug #10 en forma nueva: el filtro correcto por la razón correcta produce el
conjunto equivocado. La exclusión de los penales es **por definición** —no hay
geometría defensiva que fotografiar en un penal—, no por disponibilidad de dato.

**Decisión 2 — tres correcciones al código heredado.**

1. **La frontera de `arctan2` en $x_s > 120$.** `04_DATA_CONTRACT.md` §3.2
   documenta que StatsBomb reporta $x = 120.1$ en remates. Con el tirador más
   allá de la línea, la portería queda detrás y los rumbos saltan cerca de
   $\pm\pi$: el original devolvía basura sin lanzar nada. Se recorta a 119.9 y
   se **cuenta** (`Contadores.recortados_x`). En los remates del América sale 0;
   se conserva porque los 1,926 remates rivales y Cruz Azul aún no se han
   procesado, y porque una corrección silenciosa es indistinguible de un bug.
   *Efecto secundario declarado*: recortar puede poner por delante a un defensor
   que estaba detrás. Tiene su propio test.
2. **Sin imputación.** Devuelve `nan` en los casos degenerados. El heredado hacía
   `fillna(median)` sobre las features de portero, metiendo remates promedio
   disfrazados de dato real. Aquí el remate se descarta entero (es **1** en el
   América) y se declara.
3. **El radio es explícito.** Estaba cableado a 0.5. Es una decisión, no un
   hecho, y debe poder barrerse. **Resultado del barrido: es irrelevante** —de
   0.3 a 0.5 el coeficiente pasa de +0.652 a +0.653.

**Decisión 3 — el bloque de remuestreo es el PARTIDO, no la posesión.**

ADR-07 fija `poss_uid` como unidad para las cantidades de la cadena. Aquí no
sirve: casi toda posesión tiene un solo remate, así que remuestrear por posesión
es prácticamente i.i.d.

La era se asigna **a nivel de partido** y los remates de un partido comparten
rival, marcador y contexto. Es además el bloque de la nula por permutación del
bloque defensivo (ADR-48).

**Medido, no supuesto**: con posesión los IC se estrechan entre un 17% y un 29%,
y la atribución geométrica de Jardine vs Ortiz pasa de [−0.0062, +0.0227] a
[−0.0009, +0.0196] — rozando la significancia. Habría sido un hallazgo fabricado
por la unidad de remuestreo. Es el género del bug #11.

**Decisión 4 — la atribución se descompone, y con su propio IC.**

$\overline{xG_{full}}$ mezcla features de ataque y de defensa. Una diferencia
significativa entre eras puede venir **entera** de que una era remata desde
mejores posiciones. Sin $\overline{xG_{base}}$ al lado, el hallazgo no es
atribuible:

$$\Delta \overline{xG_{full}} = \underbrace{\Delta \overline{xG_{base}}}_{\text{posición}} + \underbrace{\text{resto}}_{\text{geometría}}$$

El resto lleva IC propio por bootstrap, no la resta de dos estimadores puntuales.

**Decisión 5 — sin sklearn.**

La logística regularizada va por IRLS en numpy, ~20 líneas. ADR-19 restringe las
dependencias, y ver la verosimilitud escrita conecta con el curso de inferencia
mejor que un `.fit()`. Los pliegues de validación cruzada respetan el partido, y
los bloques se **ordenan antes de barajar** (bug #8).

**Decisión 6 — la lógica compartida vive en `src/`, no duplicada en dos scripts.**

`25_goal_open_eras.py` (un par) y `26_goal_open_barrido.py` (la familia) importan
de `src/dtdecoder/xg_remate.py`. Dos copias del cálculo de `xG_base` divergirían
en silencio y darían números que no cuadran entre dos secciones del mismo
reporte: es el bug #2 —*"estimador puntual e IC con recetas distintas"*— por
adelantado.

**Validación.** 26 tests numéricos en `tests/test_goal_open.py`. El fuerte es el
contraste contra una **implementación independiente por trazado de rayos**:
200,001 rayos a través de la boca de meta, sin compartir una línea de lógica con
el barrido de intervalos, coincidiendo a $10^{-3}$ en 31 escenas. Un test que
reimplementa la misma fórmula solo comprueba que sabes copiarla.

El barrido con FDR se validó en los dos sentidos: **control negativo** (dos
clubes sintéticos sin diferencia real → 0 de 15 sobreviven) y **control
positivo** (diferencia de posición inyectada → la detecta y no inventa efecto
geométrico donde no lo hay).

**Estado.** Cerrada.

## ADR-52 — La familia FDR del bloque defensivo tras la migración

**Fecha**: 2026-09-15. **Estado**: aceptada, escrita ANTES de correr
`generar_defensa_h7.sh`.

**Contexto.** El script 22 corre Benjamini-Hochberg sobre todos los contrastes
de presión. Con dos clubes y las eras viejas la familia tenía 46 contrastes y
el titular de Anselmi quedaba en q = 0.0414. Con la terna de H7 son 12 parejas
y la familia crece varias veces; los q suben mecánicamente.

**Decisión.** Opción (a): **se muestran todas las parejas y los q son los de
la familia grande.** Los titulares que no sobrevivan a ese umbral se reportan
como no significativos.

**Por qué no (b).** Declarar ahora un subconjunto confirmatorio sería fijar la
familia sabiendo ya qué contrastes existen y cuáles convenían. La familia
pequeña de agosto pertenece a un universo de eras que el bug #14 invalidó; no
se puede heredar su q.

**Consecuencia aceptada.** Si el titular de Anselmi cae, cae. No se vuelve a
la familia pequeña para recuperarlo. Además, Cruz Azul no está en la terna de
H7, así que ese contraste puede no llegar siquiera a calcularse.

<!-- h2_14 -->
**Adenda (2026-09-15).** El bloque D1 se corrió con **6 clubes**
(América, Atlas, Atlético San Luis, Cruz Azul, León, Monterrey), no con la terna: 27 parejas, 648
contrastes y **32** sobrevivientes a BH
(`reports/fdr_presion.json`). La opción (a) se mantiene sobre esa familia.
Pendiente: `generar_defensa_h7.sh` y `12_reporte_html.py` siguen con
`america,leon,atlas` por defecto; la corrida real usó `--clubes`.

---

<!-- h2_14 -->
## ADR-53 · El contraste entre eras se normaliza por la liga del mismo torneo

**Fecha.** 2026-09-15. Borrador y predicciones escritos ANTES de la corrida
(`docs/ADR-53_BORRADOR.md`); resultados de `reports/did_h4_v1.json`.

**Contexto.** En `25_pares_h4.py` la línea base contemporánea solo construía
el prior, y magnitud y permutación corrían a λ=0: el prior no entraba en
ningún número. La v5 medía la diferencia entre eras con la deriva del
proveedor dentro (bug #19). Encoger con λ>0 no lo arregla: atenúa por igual
estilo y deriva, sin cambiar su proporción.

**Decisión.** Para cada unidad u = (club, entrenador),
$D_u = \log E_T(\hat P_u, \hat\alpha_u) - \log E_T(\hat P_{base(u)}, \hat\alpha_u)$,
con la base igual a la liga sin el club, en los torneos de u y ponderada a su
mezcla (B1, B2). El estimando es el de `08_ic_derivados.py`, con la misma
función `derivadas`. Para un par del mismo club, $\theta = D_a - D_b$.
Bootstrap por posesión del foco y de la base (estratificada por torneo),
intervalo basic en escala log, p por inversión del intervalo y BH al 5% sobre
una **familia nueva**.

No es el DiD clásico: cada era se observa solo en su periodo y no hay
pre-tratamiento. El supuesto es que, sin cambio de entrenador, el club se
habría movido como la liga (B3/B4, contraste débil).

**Reglas preinscritas.** D53-1 a D53-8, en el borrador y en el JSON.

**Resultado.** 60 pares sobre 53 unidades · B = 4000 · rechazan tras BH: DiD **44**, crudo 47 · cambian de signo al corregir: **15** · no rechazados: 16 · eras bloqueadas: 0 · aviso de piso del p: ninguno · contra la v5: 12 dejan de rechazar, 11 empiezan a rechazar

| # | predicción | resultado | |
|---|---|---|---|
| 1 | la firma temporal baja respecto al crudo | crudo 37/47 (79%) → DiD 23/44 (52%) — cerca del 50% que se esperaría sin tendencia | ✅ |
| 2 | Cocca I vs Cocca II deja de ser negativo y significativo | crudo -7.01% → DiD +4.89% [+0.45, +9.62], q = 0.0389 — sigue siendo significativo con el signo INVERTIDO: el sentido del crudo era la deriva | ✅ |
| 3 | Jardine vs Solari conserva el signo y se reduce | crudo +31.42% → DiD +17.59% [+12.70, +22.43], q = 0.0010 | ✅ |
| 4 | ningún par demuestra equivalencia al 3% | ninguno; menor margen demostrable 4.02% | ✅ |

**Consecuencias.**
- La v5 queda como **diferencia bruta entre eras, deriva incluida**. No se
  borra ni se vuelve a correr.
- El control negativo **desaparece**: ningún par demuestra equivalencia al 3%.
  El argumento de discriminación pasa a apoyarse en los pares no rechazados,
  redactados con su margen ("no detectamos una diferencia mayor a X%"), y en
  la propia corrección: la firma temporal y los cambios de signo.
- El intervalo de n igualado de H4-3 se renombra `rango_submuestreo`: no es
  un IC (corr(b/n, ancho) = −0.88 sobre la v5).
- La sincronía del escalón A2022→C2023 es de **18 de 18** clubes (`frac_mismo_sentido` = 1.00); `17_SECCION_H2H4.md` §6 decía 17 de 18 y 0.94.

**Estado.** Aceptada.

---

<!-- h2_23 -->
## ADR-54 · El bloque defensivo D1 se normaliza por la liga del mismo torneo

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-54_BORRADOR.md`
(commit 2af2ab2) con las adendas 1 (vista defensora, bug #20) y 2 (universo de
partidos completos). Resultado: `reports/did_presion_v1.json`.

**Decisión.** Cada era defendiendo (acciones reales del rival, marco del club)
se compara con la liga sin **ningún** partido del club, en los mismos torneos y
estandarizada por torneo × zona. Unidad y base salen de la vista defensora
(`min_actions_defense = 1`). Cinco contrastes por par (E1 geografía ómnibus,
E2 nivel en k ≥ 3, E3 pendiente, E4/E5 posesiones de una acción), bootstrap por
partido con la base compartida en el club, B = 6000, familia en dos etapas con
BH al 5%.

**Resultado.** 27 pares · etapa 1: 135 contrastes · rechazan
**6** con la corrección y 24 sin ella ·
cambian de veredicto 20 · partidos excluidos por la
adenda 2: 6.

Sobreviven:
- América · Fernando Ortiz vs Santiago Solari · E1
- América · Fernando Ortiz vs Santiago Solari · E2
- Cruz Azul · Juan Reynoso vs Martin Anselmi · E1
- Cruz Azul · Juan Reynoso vs Martin Anselmi · E2
- Cruz Azul · Juan Reynoso vs Nicolas Larcamon · E1
- Cruz Azul · Juan Reynoso vs Nicolas Larcamon · E2

| # | predicción | valor | |
|---|---|---|---|
| 1 | firma temporal de E2 entre 35% y 65% (crudo y DiD) | `{"crudo": [8, 8], "did": [3, 3]}` | ❌ |
| 2 | Jardine-Ortiz E2: DiD mas negativo que el crudo | `{"did": -0.019565160510644025, "crudo": -0.004593706240646367}` | ✅ |
| 3 | Cocca I-II E2: \|DiD - crudo\| < 0.5 pp | `{"diferencia": 0.01826493269431484}` | ❌ |
| 4 | menos del 25% de la etapa 1 cambia de veredicto | `{"cambian": 20, "de": 135}` | ✅ |

La predicción 2 quedó contaminada por el humo con la base vieja (adenda 1).
La corrección pesó más de lo que suponía el diseño: sin ella rechazaban 24 contrastes y con ella 6.

**Estado.** Aceptada. Antes de redactar frases de geografía, la orientación de
las zonas se comprueba con `13_verificar_ejes.py`. Comprobada el 2026-09-17 con 13 y 14 sobre los datos
del API (`10_RESULTADOS.md` §33.4).

---

<!-- h2_23 -->
## ADR-55 · Balón parado: la cadena para la prevención, la geometría para la supresión

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-55_BORRADOR.md`
(commit 9aa5524) con la adenda 1 (sensibilidades exploratorias, bug #21).
Integra el proyecto previo de córners. Resultado: `reports/balon_parado_v2.json`.

**Decisión.** Secuencias de córner, tiro libre indirecto y saque de banda
construidas desde los eventos. C1 = P(remate | secuencia), C2 = E[xG | remate],
con un modelo de balón parado ajustado una vez para la liga (distancia, ángulo,
cabeza y geometría del freeze frame, fuera de pliegue por partido). Cada era se
compara con la liga del mismo torneo; bootstrap por partido, B = 6000. Familias:
ADR-52 (84 contrastes) y casos de ADR-57 (96).

**Liga.** P(remate | secuencia): {"corner": 0.3960562621979945, "tiro_libre": 0.20872295882763434, "banda": 0.13963562237227672}. P(gol | secuencia):
{"corner": 0.033380442829261725, "tiro_libre": 0.019678995115143056, "banda": 0.010744468509788933}. Exploratorio, remate en 10 s: {"corner": 0.33467931893128744, "tiro_libre": 0.1451500348918353, "banda": 0.0733426763494288};
dentro de la fase del proveedor: {"corner": 0.3813177199003971, "tiro_libre": 0.1492672714584787, "banda": 0.03414447700343993}. Cadena en córners:
P(remate) 0.1987, P(gol) 0.0170, E[T] 2.17.

**Modelo.** 9850 remates y 775 goles · AUC base 0.744,
con geometría 0.770, StatsBomb 0.775 · ΔAUC
+0.026 [+0.015, +0.038] · cabeza
-0.444 [-0.525, -0.367] ·
interacción cabeza × distancia -0.612.

**Familias.** ADR-52: 0 de 84 rechazan.
Casos: 2 de 96.
- Querétaro · Benjamin Mora · C2_of: unidad 0.0574, liga 0.0858, diferencia -0.0284 [-0.0416, -0.0166] (q ADR-52 —, q casos 0.0160)
- Santos Laguna · Ignacio Ambriz · C1_def: unidad 0.5340, liga 0.3850, diferencia +0.1490 [+0.0651, +0.2283] (q ADR-52 —, q casos 0.0160)

| # | predicción | valor | |
|---|---|---|---|
| 1 | min_actions=2 descartaba >15% de las posesiones que inician con corner | `{"valor": 0.2436233932296924, "nota": "la sonda (adenda 2) ya mostro 19.8% sobre TODAS las posesiones From Corner"}` | ✅ |
| 2 | P(S\|secuencia de corner) de la liga en [0.18, 0.30] | `{"valor": 0.3960562621979945}` | ❌ |
| 3 | beta_cabeza < 0 con IC95 que excluye 0 | `{"valor": [-0.444396318177287, -0.5249958967635829, -0.3666297705077236]}` | ✅ |
| 4 | delta AUC > 0 con IC95 que excluye 0 | `{"valor": [0.026024277970319032, 0.015043075453450318, 0.03771389993089076]}` | ✅ |
| 5 | \|cadena - producto\| / cadena < 0.25 (posesion) | `{"valor": 0.7843854513677296}` | ❌ |
| 6 | a lo sumo 10 de 84 rechazan | `{"valor": [0, 84]}` | ✅ |
| 7 | goal_open medio de corner < juego abierto | `{"valor": [0.6617221245303774, 0.7763747660210579]}` | ✅ |

De la P(remate | secuencia de córner) de 0.396, 0.335 ocurre en los primeros 10 s (85%). P(gol) por secuencia 0.0334; producto de las dos capas 0.0302; cadena 0.0170. P(remate) por posesión: empírica 0.385, cadena 0.199. La cadena de primer orden subestima el peligro del balón parado (rechazo de Markov, `03_METHODS.md` §7.1); su versión quedó descriptiva desde la preinscripción.

**Estado.** Aceptada.

---

<!-- h2_23 -->
## ADR-56 · Contexto: cuánto ajusta el entrenador más allá de lo que ajusta la liga

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-56_BORRADOR.md`
con la adenda 1 (B = 16,000). Resultado: `reports/contexto_v1.json`.

**Decisión.** θ = [M_era(A) − M_era(B)] − [M_liga(A) − M_liga(B)] desde la
perspectiva del club (el marcador del rival se invierte), para localía,
marcador, momento (minuto 60) y rival (tercio por diferencia de xG sin el
partido propio). Métricas M1–M4. Bootstrap por partido, que conserva la
dependencia dentro del partido; B = 16,000.

**Lo que ajusta la liga** (A y B de cada contexto):

| contexto | métrica | A | B |
|---|---|---|---|
| localia | acciones/posesión (ataque) | local: 5.703 | visitante: 5.361 |
| localia | P(remate) (ataque) | local: 12.5% | visitante: 10.5% |
| localia | π de presión (defensa) | local: 22.0% | visitante: 21.0% |
| localia | P(remate) concedido | local: 10.5% | visitante: 12.5% |
| marcador | acciones/posesión (ataque) | perdiendo: 5.864 | ganando: 5.053 |
| marcador | P(remate) (ataque) | perdiendo: 12.6% | ganando: 10.7% |
| marcador | π de presión (defensa) | perdiendo: 23.1% | ganando: 20.0% |
| marcador | P(remate) concedido | perdiendo: 10.7% | ganando: 12.6% |
| momento | acciones/posesión (ataque) | min>=60: 5.223 | min<60: 5.699 |
| momento | P(remate) (ataque) | min>=60: 12.6% | min<60: 10.9% |
| momento | π de presión (defensa) | min>=60: 21.4% | min<60: 21.5% |
| momento | P(remate) concedido | min>=60: 12.6% | min<60: 10.9% |
| rival | acciones/posesión (ataque) | fuerte: 5.302 | debil: 5.767 |
| rival | P(remate) (ataque) | fuerte: 10.5% | debil: 12.4% |
| rival | π de presión (defensa) | fuerte: 20.7% | debil: 21.9% |
| rival | P(remate) concedido | fuerte: 12.5% | debil: 10.7% |
| marcador_60 | acciones/posesión (ataque) | perdiendo: 5.753 | ganando: 4.771 |
| marcador_60 | P(remate) (ataque) | perdiendo: 13.6% | ganando: 11.0% |
| marcador_60 | π de presión (defensa) | perdiendo: 23.4% | ganando: 19.8% |
| marcador_60 | P(remate) concedido | perdiendo: 11.0% | ganando: 13.6% |

**Eras que se separan de ese ajuste.** ADR-52:
1 de 336. Casos: 0 de
384.
- Atlético San Luis · Guillermo Abascal · localia|M2: θ -0.0474 [-0.0697, -0.0232] (q ADR-52 0.0420, q casos —)

| # | predicción | valor | |
|---|---|---|---|
| 1 | liga: M1 perdiendo > ganando | `{"valor": [5.863596962657328, 5.053058637083994]}` | ✅ |
| 2 | liga: presion (M3) del que defiende perdiendo > ganando | `{"valor": [0.23097400642312324, 0.19990499392907266]}` | ✅ |
| 3 | liga: M2 local > visitante | `{"valor": [0.12537128487344426, 0.10477313484167342]}` | ✅ |
| 4 | liga: M2 min>=60 > min<60 | `{"valor": [0.12605541473647408, 0.10926124975944501]}` | ✅ |
| 5 | a lo sumo 20 de 336 rechazan (ADR-52) | `{"valor": [1, 336]}` | ✅ |
| 6 | entre los rechazos, el contexto mas frecuente es el marcador | `{"valor": {"localia": 1, "marcador": 0, "momento": 0, "rival": 0}}` | ❌ |

**Estado.** Aceptada. Un contraste sin rechazo se redacta con su intervalo:
"no detectamos un ajuste distinto al de la liga mayor a…".

---

<!-- h2_23 -->
## ADR-57 · Casos del informe: el América y los entrenadores con varios clubes

**Fecha.** 2026-09-16. Preinscrita en `docs/preinscritos/ADR-57_BORRADOR.md`.

**Decisión.** Casos = las eras del América más los entrenadores con al menos
dos eras analizables en clubes distintos. Es un criterio estructural,
recalculado por los scripts; coincidió con la tabla preinscrita
(diferencias: {}).

| entrenador | clubes |
|---|---|
| Andre Jardine | América, Atlético San Luis |
| Fernando Ortiz | América, Monterrey |
| Santiago Solari | América |
| Benat San Jose | Atlas, Mazatlán |
| Benjamin Mora | Atlas, Querétaro |
| Domenec Torrent | Atlético San Luis, Monterrey |
| Nicolas Larcamon | Cruz Azul, León, Puebla |
| Veljko Paunovic | Guadalajara, Tigres UANL |
| Victor Manuel Vucetich | Mazatlán, Monterrey |
| Eduardo Fentanes | Necaxa, Santos Laguna |
| Ignacio Ambriz | Santos Laguna, Toluca |
| Miguel Herrera | Tigres UANL, Tijuana |

La familia de casos se reporta aparte de la de ADR-52, en balón parado y en
contexto. Lo que viaja en E[T] y en balón parado es **descriptivo**, porque
esos puntos se vieron antes de preinscribir.

**Predicción 1** (al menos 6 de los 9 técnicos de varios clubes mantienen el
signo del ajuste al marcador en M1): **3 de 9** →
❌.

| entrenador | signo por club | mismo signo |
|---|---|---|
| Benat San Jose | + / − | no |
| Benjamin Mora | + / + | sí |
| Domenec Torrent | + / − | no |
| Eduardo Fentanes | + / − | no |
| Ignacio Ambriz | + / − | no |
| Miguel Herrera | − / + | no |
| Nicolas Larcamon | − / − / + | no |
| Veljko Paunovic | + / + | sí |
| Victor Manuel Vucetich | − / − | sí |

*Corrección:* `36_contexto.py` imprimió este conteo sobre 11 técnicos
(incluía a Jardine y a Ortiz), cuando el texto preinscrito dice nueve. El
veredicto no cambia. El ajuste al marcador **no viaja** con el entrenador en la mayoría de los casos.

**Estado.** Aceptada.

---

<!-- h2_27 -->
## ADR-58 · Uso de jugadores: núcleo, roles y lo que pasa tras el primer cambio

**Fecha.** 2026-09-17. Preinscrita en `docs/preinscritos/ADR-58_BORRADOR.md`
(commit db715ef). Resultado: `reports/jugadores_v1.json`.

**Decisión.** Tres bloques sobre las mismas eras y el mismo universo de
partidos que ADR-54 a ADR-57:

- **A · núcleo y rotación (descriptivo).** Minutos desde `positions`; por era y
  torneo: N80, continuidad del once, jugadores distintos y cambios tácticos por
  partido, cada uno como percentil en la liga del mismo torneo. Torneos con
  menos de 12 partidos de la era: parciales, sin percentil.
- **B · roles (descriptivo).** Posición modal y reparto 5×4 de las acciones de
  cada jugador con al menos 450 minutos.
- **C · tras el primer cambio táctico (inferencial, nunca causal).** Primera
  sustitución táctica entre 10:00 y 35:00 del segundo tiempo; ventanas de
  10 minutos con exclusión de ±60 s; θ = Δ de la era − Δ de la liga sin el club,
  estandarizada por bloque × marcador × torneo. Bootstrap por partido,
  B = 6000.

**Diagnóstico.** Reloj de `positions`: acumulado (13212
muestras) · unión acciones–eventos 1.0000 · partidos con
alineación 1524 · primeros cambios en la franja:
1859 tácticos y 325 por lesión.

**Lo que hace la liga tras el primer cambio** (Δ = después − antes; M1 en
acciones, el resto en puntos porcentuales):

| cambio | métrica | perdiendo | empatando | ganando |
|---|---|---|---|---|
| táctico | acciones/posesión | +0.301 (n 448) | -0.001 (n 685) | -0.127 (n 725) |
| táctico | P(remate) | +2.15 pp (n 448) | +1.01 pp (n 685) | -0.95 pp (n 725) |
| táctico | P(remate) concedido | -5.29 pp (n 448) | -1.58 pp (n 685) | +0.36 pp (n 725) |
| táctico | field tilt | +8.68 pp (n 449) | +3.89 pp (n 685) | +0.29 pp (n 725) |
| por lesión | acciones/posesión | +0.363 (n 66) | -0.622 (n 110) | -0.176 (n 149) |
| por lesión | P(remate) | +0.72 pp (n 66) | -0.72 pp (n 110) | -2.03 pp (n 149) |
| por lesión | P(remate) concedido | -2.74 pp (n 66) | +0.95 pp (n 110) | +0.09 pp (n 149) |
| por lesión | field tilt | +0.17 pp (n 66) | -3.92 pp (n 110) | -1.19 pp (n 149) |

**Familias.** ADR-52: 0 de 84 rechazan. Casos:
0 de 96.
- ninguno

| # | predicción | valor | |
|---|---|---|---|
| 1 | liga, perdiendo: Delta M2 > 0 tras el primer cambio tactico | `{"valor": [0.021513791718917354, 448]}` | ✅ |
| 2 | liga, perdiendo: Delta FT > 0 tras el primer cambio tactico | `{"valor": [0.08681587401001872, 449]}` | ✅ |
| 3 | a lo sumo 5 rechazos en ADR-52 y 5 en casos | `{"valor": [0, 84, 0, 96]}` | ✅ |
| 4 | liga, perdiendo: \|Delta M2\| por lesion < \|Delta M2\| tactico | `{"valor": [[0.007190642500591833, 66], [0.021513791718917354, 448]]}` | ✅ |

**Redacción obligatoria.** "Tras sus primeros cambios, el equipo…". Nunca "sus
cambios provocan…": los técnicos cambian cuando el partido lo pide (confusión
por indicación), y la estratificación por minuto y marcador la atenúa sin
eliminarla. En A, el calendario cargado por competiciones que no están en los
datos (Concachampions, Leagues Cup) empuja a rotar y se declara como confusor.

**Estado.** Aceptada.
