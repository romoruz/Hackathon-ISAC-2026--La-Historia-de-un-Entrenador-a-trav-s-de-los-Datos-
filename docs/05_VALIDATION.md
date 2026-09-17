# 05 — Protocolo de validación y amenazas a la validez

> Qué está validado, qué NO lo está, y cómo alguien podría refutar este
> trabajo. Un modelo cuyas limitaciones no se declaran no es evaluable.
>
> Actualizado 2026-08-20 tras validar fases 0–2 en dos clubes.

---

## 1. Filosofía

En este proyecto **los errores no producen excepciones: producen números
plausibles pero equivocados**. Los **veinte** bugs encontrados hasta ahora
(`02_STATE_OF_PLAY.md` §8, `17_BITACORA_MIGRACION.md`, `10_RESULTADOS.md` §27.5 y §32) fueron todos silenciosos. Veinte de veinte (numerados hasta el #21; el #13 se evitó).

De ahí dos reglas:

1. **Todo cambio con un test.** No "el código corre", sino "el número es el que
   debe ser".
2. **Todo supuesto con un diagnóstico ejecutable.** Si un supuesto no se puede
   verificar en cada corrida, hay que enunciarlo como limitación.

Y dos reglas nuevas, aprendidas en la validación:

3. **Probar consumidor y productor por separado no prueba el contrato entre
   ellos.** `test_matrices_identity.py` pasó en verde mientras el guardarraíl
   abortaba siempre.
4. **Ninguna heurística calibrada sobre un solo club se presenta como general.**
   La detección de umbral de torneo funcionaba en el América y falló en Cruz
   Azul.
5. **Ninguna distancia se reporta sin su nula.** Tres veces se reportó una TV
   sin distribución de referencia y las tres veces la conclusión estaba mal:

   | caso | reportado | tras calibrar la nula |
   |---|---|---|
   | `detect_regime_changes` | 0.22 como quiebre de era | ruido de calendario |
   | Huella táctica | orden por TV cruda | 52–63% era tamaño de muestra |
   | Contraste de contextos | 0.04 como "no adapta" | 90% ruido; **conclusión contraria** |

   Tres de tres. Es el principio metodológico central del proyecto (ADR-30).
6. **No se afirma la nula.** Si un contraste no rechaza, la frase es "no
   detectamos un efecto mayor a X" con X = p95 de la nula. Nunca "no hay efecto".
7. **Un filtro más estricto no es más riguroso.** Puede introducir selección
   sobre la variable de respuesta. El barrido de umbrales es obligatorio cuando
   se filtra la muestra (ADR-33).
8. **Los bugs vienen de interacciones entre decisiones correctas**, no de código
   equivocado. El bug #10 nació de dos elecciones sensatas por separado que
   juntas eliminaban el mecanismo de absorción.

---

## 2. Niveles de validación

### Nivel 1 — Invariantes estructurales (automáticos, cada corrida)

| invariante | criterio | América | Cruz Azul |
|---|---|---|---|
| Filas de $P$ suman 1 | $<10^{-8}$ | 2.2e-16 ✅ | ✅ |
| $\rho(Q) < 1$ | espectral | 0.833 ✅ | ✅ |
| Filas de $B$ suman 1 | $<10^{-8}$ | ✅ | ✅ |
| Toda posesión absorbe | booleano | ✅ | ✅ |
| Orientación | corr > 0.5 | 0.720 ✅ | 0.726 ✅ |
| Identidad del `.npz` | igualdad | ✅ (ADR-24) | ✅ |
| Procedencia en el reporte | presencia | ✅ (ADR-23) | ✅ |

### Nivel 2 — Verificación numérica (135 tests)

- $N$ vía `solve` ≡ serie de Neumann truncada a 400 términos.
- $t = N\mathbf{1}$ ≡ suma de filas de $N$.
- $\hat p^*(\lambda \to 0)$ → EMV; $\hat p^*(\lambda \to \infty)$ → $q$.
- $G^2 = 0$ exactamente cuando $\hat p = q$.
- BH: monotonía; bajo 500 p-valores uniformes, ≤5 rechazos.
- El IC de la diferencia contiene su estimador puntual.
- **Los pliegues de CV no dependen del orden de las filas** (`test_cv_determinism.py`).
- **`phase1` escribe lo que `phase2` exige leer** (`test_npz_contract.py`).
- **El hash del config cambia cuando el config cambia** (`test_provenance.py`).

### Nivel 3 — Recuperación de parámetros

Sobre datos sintéticos con sesgo conocido inyectado: la Fase 3 produce rechazos
tras FDR, el placebo no los excede, y las celdas detectadas corresponden al
efecto inyectado.

### Nivel 4 — Validación sobre datos reales

| # | Validación | Estado | Resultado |
|---|---|---|---|
| 4.1 | Supuesto de Markov | ✅ **HECHA** | rechazado por sobredispersión |
| 4.2 | Contraste contra xG / OBV | ❌ pendiente | prioridad alta, esfuerzo bajo |
| 4.3 | Predictiva fuera de temporada | ❌ pendiente | — |
| 4.4 | Validación del simulador | ❌ requiere Fase 7 | fallará, ver 4.1 |
| 4.5 | Estabilidad dentro de era | ✅ **HECHA** | ver §2.5 abajo |
| 4.6 | **Replicación en club independiente** | ✅ **HECHA** | ver §2.6 |
| 4.7 | Análisis de potencia | ⚠️ **parcial** | efecto mínimo detectable sí; curva no |
| 4.8 | **Cobertura de los IC** | ✅ **HECHA** | 0.944 vs 0.95 nominal |
| 4.9 | **Nula del contraste de contextos** | ✅ **HECHA** | hay adaptación, es pequeña |
| 4.10 | **Confusión entrenador / plantel** | ✅ **HECHA** | 3 niveles, uno descartado |

#### 4.10 Confusión entrenador / plantel — HECHA (ADR-34)

Era **la amenaza más seria que quedaba viva**.

| nivel | resultado |
|---|---|
| 1 — solapamiento | Jardine heredó 67% de las acciones del plantel de Ortiz |
| 2 — núcleo estable | ❌ **descartado por circularidad** (ADR-33) |
| 3 — intra-jugador | ✅ 9 de 17 jugadores cambiaron (0.9 esperados por azar) |

**El nivel 2 se descartó porque el propio diagnóstico lo detectó**: filtrar
posesiones por quién ejecutó las acciones selecciona por longitud, que es la
variable medida. Con umbral 0.9 el signo del efecto se invierte.

**El nivel 3 es un diseño de efectos fijos**: cada jugador es su propio control.

#### 4.8 Cobertura de los IC — HECHA, pasa

`scripts/07_cobertura_ic.py`. Generador a nivel de cadena con $P$ conocida.

| n posesiones | basic | percentile |
|---|---|---|
| 300 | 0.935 | 0.923 |
| 1500 | 0.944 | 0.942 |
| 3000 | 0.944 | 0.943 |

Y tres subproductos: `basic` gana en muestras chicas (ADR-10 confirmada); la
mala especificación apenas degrada la cobertura (0.938, refuerza ADR-21); el
bootstrap por bloques no importa para celdas de $P$ pero sí 19% para $E[T]$
(ADR-07 matizada).

#### 4.9 Nula del contraste de contextos — HECHA, invierte el resultado

`scripts/10_nula_contextos.py`. Permutación de etiquetas de marcador **por
posesión** (a nivel de transición la nula saldría artificialmente estrecha).

Los seis contrastes rechazan en ambos clubes (p ≤ 0.034). **Pero el exceso sobre
el ruido es de 0.007 a 0.024**, contra `TV_exceso` de 0.09–0.21 en la firma
táctica. La adaptación es real y es 4–30× menor que la firma del entrenador.

#### 4.7 Análisis de potencia — parcial

Cada script de distancia reporta ahora su **efecto mínimo detectable** (p95 de
la nula), que es la cifra honesta de potencia por contraste. Falta la curva
completa: inyectar efectos de tamaño conocido, variar el número de partidos y
medir la tasa de detección.

#### 4.1 Contraste del supuesto de Markov — HECHA, rechaza

`scripts/03_bondad_ajuste_longitud.py`. En vez del contraste orden 1 vs orden 2
que se planeaba (inviable por número de parámetros), se usa un contraste
**global**: la cadena implica analíticamente la distribución de longitud de
posesión ($P(T>k) = \alpha^\top Q^k \mathbf{1}$, phase-type discreta) y se
compara contra la empírica.

| unidad | KS | p95 nulo | p | sesgo $E[T]$ |
|---|---|---|---|---|
| Jardine | 0.087 | 0.012 | 0.005 | +1.82% |
| Solari | 0.104 | 0.019 | 0.005 | +1.93% |
| América | 0.098 | 0.010 | 0.005 | +1.68% |

Patrón idéntico: **sobredispersión**. Ver ADR-21 para por qué no bloquea la
Fase 3 y sí bloquea la Fase 7.

**Dos cuidados que el script implementa y reporta:**
- **Truncamiento.** `min_actions` hace $P(T<2)=0$ por construcción mientras la
  cadena le asigna 13% de masa. Sin condicionar, el KS mide ese hueco y nada
  más: en la primera versión el estadístico completo venía del punto $k=1$.
- **Absorción terminal.** El 5.1% de las transiciones son artificiales
  (ADR-14). Parte de la cola es construcción propia.

#### 4.5 Estabilidad dentro de era — HECHA, y destapó un problema

`scripts/02_placebo_regimes.py`. Dentro de una era no debería haber quiebre.

| era | n | max obs | p95 nulo | p | veredicto |
|---|---|---|---|---|---|
| Jardine | 93 | 0.2216 | 0.2066 | 0.000 | **QUIEBRE** |
| Solari | 39 | 0.2099 | 0.2200 | 0.390 | homogénea |
| Ortiz | 26 | 0.1877 | 0.1957 | 0.520 | homogénea |
| Herrera | 17 | 0.1850 | 0.2019 | 0.850 | homogénea |

El quiebre de Jardine cae en fronteras de **torneo**, no de entrenador. Resultado:
`detect_regime_changes` queda descartado como validador de fronteras de era.

**Dos advertencias metodológicas del propio test:**
- Las tres eras que "aprobaron" tienen 17–39 partidos: poca potencia. No
  rechazar ahí es casi el resultado por defecto.
- El p95 nulo **no es comparable entre eras de distinto tamaño**: permutar 93
  partidos mezcla más y baja la TV. Para comparar habría que submuestrear.

#### 4.6 Replicación en club independiente — HECHA, pasa

Todo el pipeline se corrió sobre Cruz Azul: 158 partidos, 8 eras, fuente
documental distinta, cuatro cambios de DT a media temporada.

| métrica | América | Cruz Azul |
|---|---|---|
| `coordinate_sanity` | 0.7197 | 0.7256 |
| `frac_auto` | 0.2821 | 0.2712 |
| `frac_auto` en Carry | 0.4902 | 0.5003 |
| cuota de pases en auto | 60.4% | 59.5% |
| fase `open` | 55.8% | 54.3% |
| fase `set_piece` | 14.8% | 14.6% |

**Es la validación más fuerte del proyecto**: convierte "encontré una
diferencia" en "el método funciona".

#### 4.2 Validación externa contra xG — pendiente, alta prioridad

El dataset trae `shot_statsbomb_xg`. Comparar $B_{\cdot,\text{GOAL}}$ contra el
xG observado agregado por zona. **Es una tarde de trabajo y vale una
diapositiva.**

Contraste barato ya disponible: $\bar{xT}$ = 0.0130 contra una tasa de gol
empírica de ~1.6% por posesión. Mismo orden de magnitud sin ajuste.

⚠️ Ese contraste se hizo primero con números que el bug #7 había mezclado entre
entrenadores. Aguantó, pero por suerte. Los valores citados son post-parche.

---

## 3. Análisis de sensibilidad

| decisión | parámetro | estado | resultado |
|---|---|---|---|
| Encogimiento | $\lambda$ ∈ {0, 50, 500, 2000} | ✅ **HECHO** | ADR-22 |
| Resolución | `nx,ny` ∈ {4×3, 5×4, 6×4, 6×5} | ✅ **HECHO** | efecto invariante |
| Umbral de acarreos | `min_carry_length` ∈ {0, 5, 10} | ❌ **PENDIENTE** | **la única sin hacer** |
| Agrupamiento de fases | `phases`: 3 vs 4 | ❌ pendiente | baja prioridad |

### Sensibilidad a λ — hecha

`scripts/04_sensibilidad_lambda.py`.

| λ | rechazos/80 | atenuación mediana | Jaccard vs λ=0 |
|---|---|---|---|
| 0 | 80 | 1.000 | — |
| 50 | 76 | 0.934 | 0.950 |
| 500 | 71 | 0.585 | 0.887 |
| 2000 | 62 | 0.261 | 0.775 |

Estabilidad global 0.775, **pero toda la inestabilidad viene de λ=2000**, cuatro
veces por encima del óptimo. En el rango defendible (0–500) es 0.89–0.95.

### Sensibilidad a la resolución — hecha

`scripts/06_barrido_resolucion.py`. Δ% de $E[T]$ sin diagonal:

| malla | Jardine/Solari | Jardine/Ortiz | Anselmi/Reynoso |
|---|---|---|---|
| 4×3 | 18.98 | 4.98 | 21.88 |
| 5×4 | 19.90 | 5.64 | 23.16 |
| 6×4 | 21.29 | 6.26 | 22.60 |
| 6×5 | 20.91 | 6.10 | 23.53 |

Los efectos grandes son invariantes; el pequeño (Jardine/Ortiz) varía 13%
relativo y se reporta como tendencia.

**Criterio de éxito cumplido para los efectos grandes.** Una tabla de
sensibilidad es más convincente ante un jurado técnico que un resultado puntual,
porque demuestra que se buscó activamente romper el propio resultado.

---

## 4. Amenazas a la validez

### 4.1 Confusión entre entrenador y plantel

**Crítica**: "Lo que mides no es el DT, es que Jardine tuvo mejores jugadores."

**Mitigación parcial**: comparar eras dentro del mismo club controla
institución, presupuesto y cantera, pero **no** rotación de plantilla.

**Mitigación posible, no implementada**: cuantificar el solapamiento de
plantilla entre eras (minutos jugados por jugadores compartidos). El dataset
tiene `player_id`, así que es factible.

**Estado**: amenaza viva. Es la más seria que queda.

### 4.2 Confusión entre estilo y contexto

**Crítica**: "El equipo circula más porque va ganando, no porque el DT lo pida."

**Mitigación implementada**: `context_contrast` estratifica por marcador. TV
ponderada ≈ 0.040–0.044 entre los tres contextos: el marcador apenas mueve la
matriz de Jardine.

**RESUELTO (2026-08-20)**: la nula se calibró por permutación
(`10_nula_contextos.py`) y **el resultado se invirtió**. Los seis contrastes
rechazan en ambos clubes (p ≤ 0.034): **sí hay adaptación al marcador**.

Pero el exceso sobre el ruido es de 0.007 a 0.024, mientras que la firma
táctica del entrenador tiene `TV_exceso` de 0.09 a 0.21.

**La respuesta correcta al crítico** ya no es "no se adapta" —que era falso—
sino: *"se adapta, lo medimos, y es un orden de magnitud menor que el efecto que
atribuimos al DT"*. Un resultado cuantificado defiende mejor que uno absoluto.

### 4.3 Selección de la línea base

**Crítica**: "Comparas contra los rivales del América, que no son una muestra
aleatoria de la liga."

**Respuesta**: cierto, y por eso `other_coaches` es el diseño principal. Con dos
clubes en el archivo la crítica se debilita algo, pero no desaparece: 18 equipos
la eliminarían.

### 4.4 Múltiples comparaciones no declaradas

**Crítica**: "Probaste muchas mallas y umbrales hasta que salió significativo."

**Mitigación**: el registro de decisiones (`06_DECISIONS.md`) fecha cada
elección. Y en este proyecto el problema es el **contrario**: con 67k
transiciones se rechazan 80 de 80 estados. No hay que buscar significancia; hay
que filtrar por magnitud (ADR-25).

### 4.5 Circularidad del prior

**Crítica**: "Encoges hacia un promedio que contiene tus datos."

**Mitigación implementada**: `--prior exclude_focus` (ADR-06). Era **válida** en
v0.3 y se corrigió en v0.4.

**Matiz nuevo**: el prior sigue conteniendo a la línea base. Con λ=500 y una
mediana de renglón de 170 (Ortiz), el estimador es 75% prior. Esto **no** afecta
a $G^2$ —que se calcula sobre conteos crudos— pero sí a las magnitudes de
`bootstrap_diff` (ADR-22).

### 4.6 Fronteras de era imprecisas

**Crítica**: "Tus fechas son aproximadas; estás mezclando dos DT."

**Estado actualizado**: las fechas son **sintéticas derivadas** (ADR-26), no
documentales. La cobertura coincide con Wikipedia en ocho entrenadores con error
de 2–3 partidos.

`detect_regime_changes` **ya no sirve** para validarlas (§2.5).

**Acción**: fechas reales del API, especialmente para Cruz Azul, donde cuatro de
ocho torneos tienen cambio de DT a media temporada.

### 4.7 Poder estadístico en eras chicas

**Mitigación**: `coverage_report` marca eras con <25 partidos. En Cruz Azul,
**seis de ocho** eras no pasan el umbral.

**Pendiente**: análisis de potencia explícito con el generador sintético.
Inyectar un efecto de tamaño conocido, variar el número de partidos, medir la
tasa de detección. Daría una curva y permitiría decir "con 26 partidos
detectamos efectos de tamaño X con probabilidad Y". Convertiría la debilidad de
Ortiz en un número honesto.

### 4.8 Auto-transiciones — amenaza nueva, ya medida

**Crítica**: "Tu 'retención' es que tus zonas son grandes; un pase de 6 m no
sale de una zona de 24×20 m."

**Respuesta**: cierto, y está cuantificado. `frac_auto` = 0.28, el 40% de $E[T]$
es permanencia, y los pases aportan el 60%. **Pero el barrido de resolución
muestra que el efecto entre entrenadores sobrevive** entre 12 y 30 zonas, y la
brecha entre Δ con y sin diagonal se cierra al afinar — exactamente como debe si
las auto-transiciones son artefacto de zona gruesa.

**Estado**: amenaza respondida con evidencia.

---

## 5. Lo que este modelo NO puede hacer

- **No mide calidad de ejecución.**
- **No valora jugadores.**
- **No captura estructura sin balón.**
- **No modela ritmo.** Requiere Fase 6 (semi-Markov). Y ahora sabemos que la
  distribución de longitud está mal ajustada (§4.1), lo que refuerza el caso.
- **No establece causalidad.**
- **No predice resultados.**
- **No distingue tipos de posesión.** El rechazo de §4.1 dice que hay al menos
  dos poblaciones que el estado no separa.

---

## 6. Checklist antes de reportar cualquier número

- [ ] `pytest -q` en verde (135 tests)
- [ ] `coordinate_sanity.corr > 0.5`
- [ ] `rho_ok = true`
- [ ] `frac_below_min < 0.30` **en la unidad más pequeña** analizada
- [ ] `params_per_obs < 0.5` en esa misma unidad
- [ ] El artefacto trae `provenance`; el commit coincide con el código actual
- [ ] El `.npz` declara la unidad que se está reportando (ADR-24)
- [ ] Magnitudes con λ=0, significancia con λ\* (ADR-22)
- [ ] Sensibilidad a resolución ejecutada para todo efecto que se afirme
- [ ] Tabla de cobertura revisada; eras con <25 partidos marcadas
- [ ] Cada figura tiene enunciado el supuesto que la hace válida
- [ ] **Toda TV o distancia reportada tiene su nula** (ADR-30)
- [ ] Todo titular lleva IC, y el IC está validado por cobertura (ADR-31)
- [ ] Si un contraste no rechaza, se reporta el efecto mínimo detectable, no
      "no hay efecto"
- [ ] La multiplicidad por etapas se declara como tal (ADR-29)
- [x] **Orientación del eje Y verificada** (P-09, cerrada 2026-08-22 —
      bug #12). Reverificar con `13_verificar_ejes.py` tras tocar
      `grid.py`. Aplica antes de publicar mapas con
      etiquetas de banda

**Los cuatro últimos son de la Fase 3 y son los que más veces se han violado.**
Un 0.04 o un 0.22 sin distribución de referencia no significa nada, y se
comprobó tres veces.
