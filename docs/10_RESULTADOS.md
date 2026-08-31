# 10 — Resultados

> Todo hallazgo con su procedencia, su magnitud y su caveat. Nada aquí es
> presentable sin leer su columna de limitaciones.
>
> Corte: 2026-08-20 · `dtdecoder 0.5.0` · **Fases 0–3 completas**

---

## 0. Cómo leer este documento

| etiqueta | significado |
|---|---|
| 🟢 **RESULTADO** | replicado, invariante a decisiones de modelado, con IC |
| 🟡 **TENDENCIA** | signo consistente, magnitud inestable |
| 🔴 **RETIRADO** | se investigó y no se sostiene |
| ⚪ **PENDIENTE** | falta el contraste que lo haría interpretable |

Un hallazgo sin la fuente que lo produjo no es citable.

---

## 1. 🟢 Duración de posesión, con intervalo de confianza

**Fuente**: `scripts/08_ic_derivados.py` → `reports/ic_*.json`
**Método**: bootstrap por posesión, 1000 réplicas, IC básico, λ=0.

| comparación | $E[T]$ A | $E[T]$ B | Δ | IC 95% |
|---|---|---|---|---|
| Jardine vs Solari | 6.796 | 5.553 | **+22.4%** | [+18.6%, +26.4%] |
| Anselmi vs Reynoso | 6.632 | 5.282 | **+25.6%** | [+21.4%, +29.7%] |
| Jardine vs Ortiz | 6.796 | 6.298 | **+7.9%** | [+3.9%, +11.8%] |

Los tres excluyen el cero.

**Afirmación defendible**: *"Bajo Jardine, el América sostiene posesiones un 22%
más largas que bajo Solari (IC 95%: 19%–26%). Bajo Anselmi, Cruz Azul un 26% más
que bajo Reynoso."*

**Por qué es sólido:**
- Invariante entre 12 y 30 zonas (`06_barrido_resolucion.py`).
- Se mantiene al eliminar la diagonal de $Q$: no depende de auto-transiciones.
- La brecha entre Δ con y sin diagonal **se cierra** al afinar la malla,
  exactamente como debe si las auto-transiciones son artefacto de zona gruesa.
- Replicado en dos clubes con entrenadores y calendarios distintos.
- Los IC están **validados por cobertura** (§9).

**Cambio respecto a la versión anterior**: Jardine vs Ortiz pasa de 🟡 a 🟢. El
IC lo establece aunque la magnitud sea modesta.

**Caveats**: eras de fechas sintéticas (ADR-26); no controla rotación de
plantilla; "sostener más" no implica "jugar mejor" (§2).

---

## 2. 🟢 Duración y peligro son dimensiones independientes

**Fuente**: `reports/ic_*.json`

Este es el hallazgo que cambia la narrativa del proyecto.

| comparación | $E[T]$ | P(remate) | P(gol) |
|---|---|---|---|
| Jardine vs Solari | **+22.4%** ✅ | +1.1% ✗ | +22.4% ✗ |
| Anselmi vs Reynoso | **+25.6%** ✅ | **+44.6%** ✅ | +51.3% ✗ |
| Jardine vs Ortiz | **+7.9%** ✅ | **−12.5%** ✅ | −8.7% ✗ |

(✅ = el IC excluye el cero)

**Ninguna diferencia en probabilidad de gol es significativa.** Las posesiones
duran más, pero eso no se traduce en más gol de forma detectable.

Y `P(remate)` va en direcciones **opuestas**: Jardine retiene más que Ortiz y
remata **menos** (−12.5%, IC [−23.9%, −1.5%]); Anselmi retiene más que Reynoso y
remata **mucho más** (+44.6%, IC [+30.1%, +59.2%]).

**Afirmación defendible**: *"Duración de posesión y generación de peligro son
dimensiones independientes del estilo. Dos entrenadores pueden alargar la
posesión por razones tácticas opuestas: uno para penetrar, otro para controlar
el partido."*

Es la distinción que un director deportivo entiende de inmediato, y es lo que
justifica el aparato matemático: sin descomponer $N$ y $B$ por separado, ambos
casos se verían iguales.

**Caso limítrofe a reportar como tal**: Anselmi vs Reynoso en P(gol), `basic` da
[−0.00010, +0.00662] (incluye cero) y `percentile` da [+0.00003, +0.00675] (lo
excluye). **Un resultado que depende de qué IC elijas no es un resultado**: va
como no significativo.

---

## 3. 🟢 Huella táctica: Jardine retiene en el balón parado ofensivo

**Fuente**: `scripts/09_huella_efecto.py` → `reports/huella_jardine.json`
**Método**: TV por renglón, nula por remuestreo, filtro por $z\geq3$ y $n\geq50$,
orden por `TV_exceso`. 2000 réplicas.

### La cascada de filtros

| filtro | Jardine | Anselmi |
|---|---|---|
| significativos tras FDR | 80 de 80 | 71 de 80 |
| TV sobre p95 nulo | 61 | 39 |
| $z \geq 3$ | 44 | 23 |
| $n \geq 50$ | 76 | 71 |
| **seleccionados** | **44** | **22** |

**El 52% (Jardine) y el 63% (Anselmi) de la TV típica es tamaño de muestra, no
estilo.** La significancia sola sobredetectaba por un factor de 2 y 3.

Esta cascada es una diapositiva por sí misma.

### Top de Jardine (extracto)

| estado | n | TV | ruido | exceso | z |
|---|---|---|---|---|---|
| z03\|set_piece | 114 | 0.395 | 0.182 | 0.213 | 4.3 |
| **z40\|set_piece** | **674** | 0.214 | 0.038 | **0.176** | **13.9** |
| z02\|set_piece | 285 | 0.220 | 0.106 | 0.114 | 4.8 |
| z40\|open | 941 | 0.125 | 0.030 | 0.095 | 9.4 |
| z43\|set_piece | 600 | 0.133 | 0.042 | 0.091 | 6.8 |
| z40\|restart | 800 | 0.111 | 0.026 | 0.086 | 9.7 |

Seis de diez son `set_piece` o `restart`. Las celdas confirman el mecanismo:

| celda | delta |
|---|---|
| z40\|set_piece → z40\|set_piece | **+0.139** |
| z40\|set_piece → LOSS | **−0.136** |
| z43\|set_piece → LOSS | −0.124 |
| z43\|set_piece → z43\|set_piece | +0.091 |
| z40\|restart → LOSS | −0.076 |

**Afirmación defendible**: *"Jardine convierte los balones parados y reinicios en
zonas ofensivas en posesión sostenida en vez de perderlos. En z40|set_piece la
pérdida cae del 40.3% al 26.7%."*

### Top de Anselmi

Sus diez estados están en `open`, `restart` y `set_piece` de zonas **z01, z02,
z10, z11, z22** — tercio defensivo y medio. Ninguno en la banda ofensiva. Celda
clave: `z02|open → LOSS` con **−0.063** (de 14.4% a 8.0%).

### La distinción

**Jardine retiene en el tercio ofensivo; Anselmi retiene en la salida.** Ambos
sostienen posesiones ~25% más largas, por mecanismos y en zonas distintas.

Coherente con §2: retener en z40 es cerca del área pero por balón parado;
retener en z02 es construir desde atrás y convertir en remates.

**Dos rutas de análisis independientes** —$E[T]$ con bootstrap, y la huella por
TV— apuntando a lo mismo.

---

## 4. 🟢 La adaptación al marcador es real, pero pequeña

**Fuente**: `scripts/10_nula_contextos.py` → `reports/nula_contextos_*.json`
**Método**: permutación de etiquetas de contexto **por posesión**, 2000 réplicas.

| contraste | Jardine z / p | Anselmi z / p |
|---|---|---|
| losing vs winning | **6.19** / 0.0005 | **4.41** / 0.0005 |
| drawing vs winning | 2.76 / 0.005 | 6.27 / 0.0005 |
| drawing vs losing | 1.88 / 0.034 | 2.43 / 0.009 |

**Los seis contrastes rechazan.** El más fuerte es el mismo en ambos clubes:
ganando contra perdiendo.

Pero la magnitud:

| contraste (Jardine) | TV obs | ruido | **exceso** |
|---|---|---|---|
| drawing vs losing | 0.117 | 0.110 | **0.007** |
| drawing vs winning | 0.092 | 0.085 | **0.007** |
| losing vs winning | 0.141 | 0.117 | **0.024** |

**El 90% de la TV observada es ruido de estratificación.**

Compara con la firma táctica (§3): `TV_exceso` de 0.09 a 0.21. **La firma del
entrenador es entre 4 y 30 veces mayor que su reacción al marcador.**

**Afirmación defendible**: *"El estilo se adapta significativamente al marcador
(p < 0.01 en ambos clubes), pero la magnitud de esa adaptación es un orden de
magnitud menor que la firma táctica del entrenador. La identidad domina sobre la
reactividad."*

**Corrección importante respecto a la versión anterior.** Antes se reportaba
TV = 0.04 como evidencia de "filosofía, no reactividad". Estaba **doblemente
equivocado**: el número real es 0.007–0.024, y la conclusión cualitativa era la
contraria. Responde a la amenaza 4.2 de `05_VALIDATION` mucho mejor que antes:
al crítico que dice *"circula más porque va ganando"* ya no se le responde "no se
adapta" —que era falso— sino "se adapta, lo medimos, y es pequeño comparado con
el efecto que atribuimos al DT".

---

## 5. 🟢 El 40% de la duración esperada es permanencia en zona

**Fuente**: `scripts/05_auto_transiciones.py`

| métrica | América | Cruz Azul |
|---|---|---|
| `frac_auto` | 0.2821 | 0.2712 |
| entre no absorbentes | 0.3414 | 0.3327 |
| `frac_auto` en `Carry` | 0.4902 | 0.5003 |
| cuota de pases en auto | 60.4% | 59.5% |
| inflación de $E[T]$ | 38.9–42.5% | 35.6–40.2% |

Dos clubes independientes, mismo valor al segundo decimal: es una **propiedad de
la especificación**, no de un equipo.

Los pases aportan el 60%, así que `min_carry_length` no puede corregirlo. La
palanca es la resolución.

**Es un hallazgo metodológico, no un defecto oculto.** Cualquier xT sobre zonas
gruesas tiene este problema; la diferencia es que aquí está medido.

---

## 6. 🟢 Markov de primer orden: rechazado por sobredispersión

**Fuente**: `scripts/03_bondad_ajuste_longitud.py`

| unidad | KS | p95 nulo | p | sesgo $E[T]$ |
|---|---|---|---|---|
| Jardine | 0.087 | 0.012 | 0.005 | +1.82% |
| Solari | 0.104 | 0.019 | 0.005 | +1.93% |
| América | 0.098 | 0.010 | 0.005 | +1.68% |

Patrón idéntico: menos masa en el centro (k=2–10), más en la cola (k≥12), media
casi perfecta.

**Afirmación defendible**: *"La cadena acierta la duración media (±2%) y falla la
forma. El exceso es sobredispersión: hay al menos dos poblaciones de posesión que
(zona × fase) no distingue."*

**Por qué no invalida el contraste** (ADR-21): la mala especificación es
compartida por todas las unidades —verificable, no supuesto— y la nula del LRT es
por bootstrap, no $\chi^2$. Además §9 lo midió: la cobertura cae de 0.944 a
0.938 bajo mezcla.

**Dónde sí bloquea**: la Fase 7. Las longitudes simuladas estarán mal
distribuidas aunque la media coincida.

---

## 7. 🟢 Invariancia a la resolución

**Fuente**: `scripts/06_barrido_resolucion.py`

Δ% de $E[T]$ sin diagonal:

| malla | Jardine/Solari | Jardine/Ortiz | Anselmi/Reynoso |
|---|---|---|---|
| 4×3 | 18.98 | 4.98 | 21.88 |
| 5×4 | 19.90 | 5.64 | 23.16 |
| 6×4 | 21.29 | 6.26 | 22.60 |
| 6×5 | 20.91 | 6.10 | 23.53 |

`frac_auto` baja monótonamente (0.378 → 0.199) en ambos clubes: el chequeo de
sanidad pasa.

**La malla queda en 5×4**: 6×4 da `params_per_obs` = 0.502 sobre Ortiz, por
encima del umbral de 0.5. Predicho y confirmado (P-02).

---

## 8. 🟢 El método es portable entre clubes

| métrica | América | Cruz Azul |
|---|---|---|
| `coordinate_sanity` | 0.7197 | 0.7256 |
| transiciones/posesión | 6.89 | 6.47 |
| fase `open` | 55.8% | 54.3% |
| fase `restart` | 26.1% | 27.6% |
| fase `set_piece` | 14.8% | 14.6% |

Cruz Azul tiene ocho eras contra cuatro y cuatro cambios a media temporada
contra uno. Los diagnósticos convergen igual.

---

## 9. 🟢 Los intervalos de confianza están validados

**Fuente**: `scripts/07_cobertura_ic.py`

| n posesiones | cobertura (basic) | cobertura (percentile) |
|---|---|---|
| 300 | 0.935 | 0.923 |
| 1500 | 0.944 | 0.942 |
| 3000 | 0.944 | 0.943 |

Nominal 0.95. Converge a 0.944.

**Tres resultados adicionales:**

1. **`basic` supera a `percentile` en muestras chicas** (0.935 vs 0.923 con
   n=300). ADR-10 se eligió por argumento teórico; ahora tiene respaldo empírico
   justo donde importa.
2. **La mala especificación casi no degrada la cobertura**: 0.938 con mezcla
   contra 0.944 markoviano. Refuerza ADR-21.
3. **El bootstrap por bloques no cambia nada para las celdas de $P$** (0.1091 vs
   0.1091), por la factorización de Billingsley. **Sí importa para $E[T]$**: 19%
   más ancho. ADR-07 queda matizado con evidencia.

---

## 10. 🟢 Validación externa: xT medio ≈ tasa de gol empírica

$\bar{xT}$ = 0.0130 (Jardine), 0.0128 (Ortiz).

Contraste: ~92 posesiones por equipo por partido, ~1.5 goles por partido → tasa
de gol por posesión ≈ 1.6%. El modelo implica 1.30%. Mismo orden de magnitud sin
ajuste.

⚠️ Esta comparación se hizo primero con números que el bug #7 había mezclado
entre entrenadores. Aguantó, pero por suerte. Los valores citados son
post-parche.

**Pendiente**: validación formal contra `shot_statsbomb_xg` y `obv_*`.

---

## 10b. 🟢 El efecto no son los fichajes

**Fuente**: `scripts/11_confusion_plantel.py`

| comparación | jugadores comunes | acciones heredadas | cambian tras BH | esperados |
|---|---|---|---|---|
| Jardine vs Ortiz | 20 de 54 | **67%** | **9 de 17** | 0.9 |
| Jardine vs Solari | 21 de 54 | **55%** | **4 de 13** | 0.7 |
| Anselmi vs Reynoso | 7 de 28 | **41%** | **4 de 5** | 0.2 |

**Afirmación defendible**: *"Jardine heredó el 67% de las acciones del plantel
de Ortiz. Y de los 17 jugadores con datos en ambas eras, 9 cambiaron su patrón
de juego de forma detectable, cuando por azar se esperaría uno."*

**Caveat**: aunque el jugador sea el mismo, sus compañeros, su posición y sus
rivales cambian.

---

## 10c. 🔴 RETIRADO — el "núcleo estable"

| umbral | sesgo diferencial de longitud | Δ Jardine vs Ortiz |
|---|---|---|
| 0.5 | 37 pp | +11.9% |
| 0.7 | 30 pp | +8.6% |
| 0.9 | 22 pp | **−24.3%** ← signo invertido |

Filtrar posesiones por quién las ejecutó selecciona por longitud, que es la
variable medida. **Se reporta como limitación demostrada.**

---

## 10d. 🟢 El método discrimina

| comparación | Δ E[T] | IC 95% |
|---|---|---|
| Anselmi vs Reynoso | +25.6% | [+21.4, +29.7] |
| Jardine vs Solari | +22.4% | [+18.6, +26.4] |
| Jardine vs Ortiz | +7.9% | [+3.9, +11.8] |
| **Sánchez vs Ferretti** | **+1.6%** | **[−3.3, +6.8]** |

La última fila **no es un fallo: es evidencia**. Un método que encontrara
diferencias en todos los cambios de entrenador estaría detectando ruido.

---

## 11. 🟢 λ está débilmente identificado

Meseta de **0.006 nats** entre λ=100 y λ=2000, contra 0.054 de λ=0 a λ=1.

| afirmación | estado |
|---|---|
| "El encogimiento mejora la predicción OOS (~5% de perplejidad)" | 🟢 |
| "El λ óptimo es 500" | ❌ no defendible |

**λ es casi irrelevante para predecir y decisivo para las magnitudes**: la
atenuación va de 0.87 (λ=100) a 0.26 (λ=2000). Regla: significancia con λ\*,
magnitudes con λ=0 (ADR-22).

---

## 12. 🔴 RETIRADO — `detect_regime_changes` como validador de fronteras

| era | n | max obs | p95 nulo | p |
|---|---|---|---|---|
| Jardine | 93 | 0.2216 | 0.2066 | **0.000** |
| Solari | 39 | 0.2099 | 0.2200 | 0.390 |
| Ortiz | 26 | 0.1877 | 0.1957 | 0.520 |
| Herrera | 17 | 0.1850 | 0.2019 | 0.850 |

El quiebre de Jardine cae en cierre de Apertura 2024 y arranque de Clausura
2025: fronteras de **torneo**, no de entrenador. Ninguna frontera documental
aparece en el top 15.

Las tres eras que "aprobaron" tienen 17–39 partidos: **poca potencia**. No
rechazar ahí es casi el resultado por defecto.

**Qué decir en el reporte**: que se construyó la prueba, se buscó romper el
propio instrumento, y se retiró la afirmación.

---

## 13. La lección que se repitió tres veces

| caso | reportado sin nula | tras calibrarla |
|---|---|---|
| `regimes` | TV = 0.22 como quiebre de era | ruido de calendario |
| Huella táctica | orden por TV cruda | 52–63% era tamaño de muestra |
| Contexto | TV = 0.04 como "no adapta" | 90% ruido; **la conclusión era la contraria** |

**Tres de tres.** Ya no es anécdota: es un principio del proyecto. Una distancia
sin distribución de referencia no significa nada.

---

## 14. Tabla maestra

| # | Hallazgo | Estado |
|---|---|---|
| 1 | $E[T]$: +22.4% / +25.6% / +7.9%, todos con IC que excluye cero | 🟢 |
| 2 | Duración y peligro son dimensiones independientes | 🟢 |
| 3 | Jardine retiene en balón parado ofensivo; Anselmi en salida | 🟢 |
| 4 | Adaptación al marcador real pero 4–30× menor que la firma | 🟢 |
| 5 | 40% de $E[T]$ es permanencia en zona | 🟢 |
| 6 | Markov orden 1 rechazado por sobredispersión | 🟢 |
| 7 | Efecto invariante entre 12 y 30 zonas | 🟢 |
| 8 | Método portable entre clubes | 🟢 |
| 9 | IC validados por cobertura (0.944 vs 0.95) | 🟢 |
| 10 | xT medio ≈ tasa de gol empírica | 🟢 |
| 11 | λ débilmente identificado | 🟢 |
| 12 | `regimes` no valida fronteras de era | 🔴 |
| 13 | 9 de 17 jugadores cambian bajo otro DT | 🟢 |
| 14 | El "núcleo estable" es circular | 🔴 |
| 15 | Sánchez vs Ferretti: sin efecto detectable | 🟢 |

---

## 15. Lo que NO se puede afirmar

- Que un DT sea **mejor** que otro. Se mide estilo, no rendimiento. Y P(gol) no
  difiere significativamente en ninguna comparación.
- Que la diferencia se deba **al DT** y no al plantel. No hay control de
  rotación (`05_VALIDATION` §4.1). **Es la amenaza viva más seria.**
- Ninguna magnitud de la Fase 3 sin declarar la atenuación por λ.
- Nada sobre Gutiérrez, Ferretti o Moreno en Cruz Azul: sus eras caen en torneos
  con cambio a media temporada y las fechas son sintéticas.
- Nada sobre Herrera: 17 partidos, `suficiente = false`.
- Ningún contrafactual: la Fase 7 no existe y §6 anticipa que su validación
  fallaría.
- Que el efecto Jardine–Ortiz sea grande: +7.9% con IC [+3.9%, +11.8%] es real
  pero modesto.

---

# Bloque defensivo D1 — la presión

> Integrado el 2026-08-26 desde `ACTUALIZACIONES_DOCS_v2.md`, que queda como
> histórico. Corte del análisis: 2026-08-25.
>
> **Toda cifra de esta sección declara si es por posesión o por acción**
> (ADR-48). Sin eso, dos frases correctas se contradicen.

---

## 16. 🔴 RETIRADAS — tres afirmaciones sin soporte

**Léelo antes que el resto de esta sección.** Las tres llegaron a estar escritas
y hoy no se sostienen. Se retiran, no se matizan. **Si las ves citadas en algún
sitio, ese sitio está desactualizado.**

### 16.1 🔴 "Jardine presiona más al rival que Solari"

Publicado como +1.62 pp, q = 0.0180, desde la estandarización por posesión.

Tres contrastes independientes lo desmienten:

| contraste | resultado |
|---|---|
| pendiente de decaimiento (kmin=2) | −0.0084 vs −0.0084, p = 0.984 |
| nivel en k≥3 | −0.0089, p = 0.480 |
| ponderación por acción | −0.57 pp (**signo contrario**) |

En cada índice de acción, Jardine y Solari presionan igual: las curvas se cruzan
seis veces y los IC se solapan en los doce puntos. La diferencia por posesión
venía de que el rival **conserva más el balón** bajo Jardine
($E[L] = 5.90$ vs $5.00$), no de que se presione distinto.

**La cifra de estandarización no era errónea**: medía un estimando distinto
($\pi$ ponderada por posesión) y sigue siendo correcta como tal. Lo erróneo era
la lectura futbolística.

### 16.2 🔴 "Anselmi sostiene la presión, p = 0.001"

Escrito desde la pendiente de $\pi$ contra $k$ ajustada **desde k=1**.

$\pi(1) \approx 0.15$ y $\pi(2) \approx 0.26$: la primera acción es la menos
presionada de todas, porque muchas posesiones rivales nacen de balón parado y no
hay presión que anotar. Ajustar una recta a una curva que **sube y luego baja**
convierte k=1 en un punto de palanca. Con kmin=2 la pendiente de Anselmi pasa de
+0.00475 a −0.00595 y la diferencia de p = 0.001 a **p = 0.077**.

**El hallazgo no desaparece: cambia de estimando.** Lo que difiere no es la tasa
de decaimiento sino el NIVEL mantenido. Ver §18.

### 16.3 🔴 "Jardine gana más balones al primer toque"

Exploratorio: +8.0 pp en posesiones de una acción en juego abierto, p = 0.0206.

**No sobrevive al FDR** de la familia D1-contrastes: q = 0.0935 sobre 46
contrastes (ADR-48). Es exactamente el falso positivo marginal que la corrección
existe para atrapar.

---

## 17. 🟢 El instrumento: la presión sirve

Antes de comparar entrenadores hay que comprobar que la etiqueta de presión mida
algo con consecuencia. Si $\pi$ no cambia el desenlace, todo el bloque describe
un comportamiento sin efecto.

Desenlace: *"¿es esta la última acción **real** de la posesión?"*. Captura todas
las formas de morir, incluidas las que el espacio de estados no ve —
`Dispossessed` (3,407) y `Clearance` (6,355) llevan `under_pressure` = 1.000
**exacto**, es definicional, y ninguno está en `moving_types`.
Estandarizado por (zona × tipo de acción).

| era | efecto | p |
|---|---|---|
| Jardine | **+0.1225** | 0.0020 |
| Solari | **+0.1076** | 0.0020 |
| Reynoso | **+0.1159** | 0.0020 |
| Anselmi | **+0.1091** | 0.0020 |

Una acción rival presionada tiene **11 puntos porcentuales más** de probabilidad
de ser la última de su posesión, a igualdad de zona y tipo de acción. Consistente
en **cuatro eras de dos clubes**.

Restringido a k≥3 el efecto es +0.115 y +0.122: **igual o mayor**. Eso significa
que la presión no mata desproporcionadamente pronto, y por tanto que el contraste
de nivel de §18 **no está viciado por censura de supervivencia** — una limitación
que se temía y resultó despreciable.

> **Caveat obligatorio**: es **asociación, no efecto causal**. StatsBomb anota
> presión cuando un defensor se acerca, y se acerca más cuando el rival ya está
> en problemas. El diseño no separa esa dirección. Debe decirse cada vez.

---

## 18. 🟢 Anselmi sostiene el nivel de presión desde el tercer toque

| | $\pi$ en k≥3 | acciones |
|---|---|---|
| Anselmi | **0.2509** | 14,402 |
| Reynoso | **0.2038** | 13,809 |

Diferencia **+4.71 pp**, p = 0.0016 (5,000 permutaciones de la etiqueta de era
entre partidos), **q = 0.0414** tras BH sobre 46 contrastes.

En k=1 y k=2 las dos eras son **indistinguibles**. La diferencia aparece desde el
tercer toque del rival y se mantiene hasta k=12.

**Cuatro fuentes de confusión descartadas por separado:**

| fuente | evidencia |
|---|---|
| rival enfrentado | soporte común 17/17, cobertura 100% |
| tipo de acción | cuotas casi idénticas (Pass .755/.753, Carry .228/.224); Anselmi presiona más en las TRES |
| origen de la posesión | Anselmi presiona más en las CUATRO fases |
| longitud de la posesión | Kitagawa: la composición aporta el 18% del total |

Y el efecto es mayor donde más pesa: cuando el rival **conduce**, sube a
**+6.4 pp** (0.463 vs 0.400); en pases es +1.8 pp.

**Caveats:** (a) el contraste condiciona a que la posesión llegara a k=3 —
atenuación medida como despreciable en §17, pero declarada; (b) **q = 0.0414
contra α = 0.05 es supervivencia sin holgura**: con dos o tres contrastes más en
la familia, caería.

---

## 19. 🟢 Dónde presiona Anselmi: dos zonas sobreviven

| zona | centro (m) | $\pi$ Anselmi | $\pi$ Reynoso | Δ | q |
|---|---|---|---|---|---|
| z23 | (60, 70) | 0.2509 | 0.2083 | **+0.0425** | 0.0414 |
| z13 | (36, 70) | 0.2578 | 0.2190 | **+0.0388** | 0.0414 |

> ⚠️ **Verificar la orientación antes de escribir la frase futbolística.** Las
> dos zonas están en `iy=3`. Con `cx` = 60 y 36 en marco del club son mediocampo
> y tercio propio. La frase tentativa —*"presiona más en su carril izquierdo
> defensivo, en campo propio y medio"*— **debe confirmarse con
> `13_verificar_ejes.py` y contra la tabla de tercios** antes de publicarse. Es
> el tipo exacto de afirmación que el bug #12 produjo mal.

Por tercio (marco del club): propio **+2.56 pp**, medio **+2.92 pp**, rival
**+0.80 pp**. La presión extra está abajo y en el medio, **casi nada arriba**.

> **Anselmi no es un entrenador de presión alta.** Es la conclusión contraria a
> la que sugiere el titular de §18 leído sin la geografía.

Dato adicional de exposición: Anselmi concede el **28.6%** de las acciones
rivales en su propio tercio contra el **33.7%** de Reynoso. Cinco puntos menos de
tiempo del rival cerca de su área, **además** de presionar más cuando llega.

---

## 20. 🟡 Jardine y Solari: misma intensidad, distinta geografía

El contraste global **no rechaza** (nivel p = 0.480; pendiente p = 0.984), pero
una zona sobrevive al FDR:

| zona | centro (m) | $\pi$ Jardine | $\pi$ Solari | Δ | q |
|---|---|---|---|---|---|
| z32 | (84, 50) | 0.1405 | 0.1766 | **−0.0361** | 0.0414 |

**Signo negativo**: Jardine presiona **menos** ahí — centro del último tercio.
Por tercio: propio +0.44, medio **−1.73**, rival +1.29 pp.

La lectura: **mismo volumen total de presión, repartido distinto.** Jardine cede
el mediocampo central y aprieta algo más arriba. Es un hallazgo más fino que
"presiona más" y **no admite esa frase** (ver §16.1).

---

## 21. ⚪ La tasa agregada de presión no discrimina

América **0.2104**, Cruz Azul **0.2125**. Dos clubes independientes, 175 y 158
partidos, calendarios distintos, y coinciden en el tercer decimal.

Dos lecturas, ambas útiles:

1. El proveedor anota la presión de forma **consistente entre volcados**, lo que
   refuerza que la lectura de la bandera es correcta (ADR-42).
2. **La intensidad total de presión es prácticamente una constante del
   formato.** Lo que separa a los entrenadores es la **geografía** y la
   **persistencia**, no el volumen.

Frase reportable: *"la intensidad total de presión es indistinguible entre
clubes; lo que distingue a los entrenadores es dónde y hasta cuándo."*

---

## 22. Tres errores de proceso nuevos

Van con los cuatro de `02_STATE_OF_PLAY.md` §8. Los tres son errores de
**análisis**, no de código, y **ninguno produjo una excepción**.

### 22.1 Ajustar una recta a una curva no monótona

$\pi(k)$ sube de k=1 a k=2 y luego baja. La pendiente ajustada desde k=1 no
estima el decaimiento: estima una mezcla de la subida inicial y la bajada
posterior. Produjo un p = 0.001 que con kmin=2 pasó a 0.077, y con él un titular
que estuvo **tres días** en la documentación.

**Se detectó mirando la figura**, no por ningún test. Ningún diagnóstico
automático avisa de que el estimando no corresponde a la pregunta.

### 22.2 Leer `phase` como estado actual del balón

Al ver $\pi = 0$ en el estrato `balón parado` × L=1 se concluyó que
`under_pressure` no se anota en balón parado, que $\pi$ mediría en parte la
proporción de balón parado, y que había que recalcular todos los mapas
restringiendo a juego abierto.

**Falso.** `set_piece` tiene $\pi = 0.19$ y `restart` 0.17–0.19. Los ceros venían
de la **intersección** con L=1: una posesión de una sola acción nacida de saque o
córner es un despeje, sin presión que registrar.

`04_DATA_CONTRACT.md` §3.4 ya lo decía. **Se citó dos veces en la misma sesión y
se leyó mal la tercera.** Es la trampa más costosa del formato y sigue atrapando
después de estar documentada.

### 22.3 Corregir dos cosas a la vez y atribuir el resultado a la equivocada

La calibración daba signo negativo. Se corrigieron **simultáneamente** el
desenlace (incluir muertes por acoso) y la estratificación (añadir
`action_type`), y se atribuyó la inversión de signo a lo primero.

**Era lo segundo.** Con el desenlace viejo pero estratificando por tipo de acción
el signo ya sale positivo (+0.05 a +0.07). La exclusión de `Dispossessed`
atenuaba el efecto a la mitad, pero no lo invertía.

> **Regla**: al corregir dos cosas a la vez, medir cada una por separado antes de
> atribuir. El script conserva la columna del desenlace viejo justo para eso.

---

## 23. Tabla maestra — bloque defensivo

| # | Hallazgo | Estimando | Estado |
|---|---|---|---|
| 16 | La presión acorta posesiones: +11 pp en 4 eras de 2 clubes | por acción, estratificado | 🟢 |
| 17 | Anselmi sostiene el nivel desde k≥3: +4.71 pp, q=0.0414 | por acción | 🟢 |
| 18 | Dos zonas de Anselmi sobreviven al FDR | por acción, por zona | 🟢 |
| 19 | Anselmi **no** es de presión alta: la presión extra está abajo y en el medio | por tercio | 🟢 |
| 20 | Anselmi concede posesiones más cortas (−0.61 acciones, q=0.0042) | estandarizado por rival | 🟢 |
| 21 | Anselmi concede menos remates (−3.61 pp, q=0.0042) | estandarizado por rival | 🟢 |
| 22 | Jardine y Solari: misma intensidad, distinta geografía | por acción | 🟡 |
| 23 | La tasa agregada de presión no discrimina entre clubes | por acción | ⚪ |
| 24 | "Jardine presiona más que Solari" | — | 🔴 RETIRADO |
| 25 | "Anselmi sostiene la presión, p=0.001" | — | 🔴 RETIRADO |
| 26 | "Jardine gana más balones al primer toque" | — | 🔴 RETIRADO |

---

## 24. Pendientes del bloque defensivo

1. **Verificar la orientación de z23/z13** antes de escribir la frase de §19.
2. **Localía y momento del partido** — el reto los pide explícitamente y no
   están. Se añaden como estratos al estimador de estandarización (ADR-44).
3. **Calibración predictiva de $B_{\cdot,\text{GOAL}}$** contra
   `shot_statsbomb_xg` (Brier / correlación por zona). `05_VALIDATION` §4.2 lo
   estima en una tarde.
4. **D2 (riesgos competitivos)** — Kaplan–Meier sobre la supervivencia de la
   posesión rival, Cox para el efecto del DT. Es el marco que trata la censura
   correctamente; hoy solo está declarada.
5. ~~El bloque defensivo no está en `12_reporte_html.py`~~ — **CERRADO
   2026-08-26.** La sección `05 · sin balón` está implementada y es la quinta del
   entregable. Ver `15_REPORTE_HTML.md` §3.

---

# 25. 🟢 Cuánta variación hay entre eras, y cuánta se puede ver

> Corrida 2026-08-26 · `scripts/23_potencia_tau2.py` · ADR-49
>
> Cierra la pregunta que `12_API_STATSBOMB.md` §5.4 dejó abierta:
> *"¿cuánta variación de estilo hay entre DTs comparada con la variación dentro
> de un mismo DT? Esa razón dice si 'estilo de entrenador' es siquiera un
> concepto medible."*

## 25.1 El resultado

Sobre las **nueve eras** de los dos clubes con al menos 1,500 posesiones
(`MIN_POSS`, el mismo umbral del reporte), midiendo acciones por posesión:

| cantidad | valor |
|---|---|
| $\tau$ — desviación típica **entre** entrenadores | **0.596** acciones/posesión |
| suelo de detección del diseño | **0.247** |
| razón señal/suelo | **2.4×** |
| $\sigma$ — desviación típica **dentro** de una era | 6.25 acciones/posesión |
| ICC = $\tau^2/(\tau^2+\sigma^2)$ | **0.9%** |
| confiabilidad mediana $\tau^2/(\tau^2+\sigma_j^2)$ | 0.96 |
| rango de medias | 6.23 (Gutiérrez) – 7.76 (Jardine) = **1.54 acciones** |

**Existe variación real entre eras, y es pequeña.** Las dos mitades de esa
frase importan por igual.

> **Y la etiqueta importa tanto como el número.** Esto NO es «el estilo del
> entrenador»: es la varianza **entre eras**, y una era cambia por más cosas
> que la pizarra. Ver §25.5.

Robusto al umbral: con las **doce** eras (`--min-n 100`, incluyendo Aguirre con
717 posesiones y Moreno I con 207) da $\tau = 0.622$ contra un suelo de 0.281,
**2.2×**. La conclusión no depende de dónde se corte.

## 25.2 Por qué se cita el estimador *aparentemente peor*

Se probaron tres estimadores de $\tau^2$ por el método de los momentos. La tabla
que decide **no es la del $\tau$ estimado**, sino la del comportamiento **bajo la
nula**: qué fracción de veces cada uno inventa variación cuando no la hay.

| estimador | $\tau$ | suelo | señal/suelo | **dice $\tau>0$ con $\tau=0$ real** |
|---|---|---|---|---|
| **ponderación mixta** | **0.596** | **0.247** | **2.4×** | **15%** |
| DerSimonian–Laird | 0.642 | 0.124 | 5.2× | 45% ❌ |
| momentos sin ponderar | 0.560 | 0.124 | 4.5× | 42% ❌ |

DL y momentos parecen mejores —suelo más bajo, razón mayor— y son
**anticonservadores**: casi la mitad de las veces reportan variación entre
unidades donde no existe ninguna. Citarlos sería elegir el número más favorable.

**Se reporta el de ponderación mixta.** Su sesgo a la baja, que empezó siendo un
defecto detectado en el código heredado, es exactamente la propiedad que se
quiere en el estimador que va al reporte: si aun así encuentra señal, la señal
está.

## 25.3 El susurro persistente: cómo se dice esto sin exagerar

Un ICC del 0.9% **no es un hallazgo aplastante**. Es un efecto real, bien medido
y pequeño. La frase reportable:

> *"Quién dirige explica menos del 1% de lo que dura una posesión concreta —
> casi nada, porque una jugada individual es puro azar. Pero sobre miles de
> posesiones ese 1% son 1.54 acciones de diferencia entre el técnico que más
> sostiene el balón y el que menos. El estilo no se ve en una jugada; se ve en
> la acumulación."*

**Lo que NO se puede decir**: que el efecto sea grande, ni que "domine el
ruido". El $\tau$ está 2.4× por encima del *suelo de detección*, que mide con
cuánta precisión se estima la media de una era — **no** el tamaño del efecto.
Confundir las dos cosas es el error que esta sección existe para evitar.

## 25.4 El suelo de detección: por qué hubo que medirlo antes

El estimador está **truncado en cero** (`max(·, 0)`). Con pocas unidades devuelve
exactamente cero **aunque la variación real no sea cero**, y esa lectura —*"el
estilo de entrenador no es medible"*— habría contradicho los seis pilares de
validación y el resultado intra-jugador de ADR-34, sin que nada fallara.

Es el patrón de los doce bugs aplicado a la estadística: un número plausible y
equivocado, sin excepción de por medio.

**El hallazgo que reordena la intuición: la potencia la manda el NÚMERO de
unidades, no su tamaño.** Simulando con $\tau$ igual a una vez el ruido de
muestreo:

| diseño | unidades | n por unidad | falso negativo |
|---|---|---|---|
| solo América | 4 | 1,500–8,694 | **32%** |
| América + Cruz Azul | 12 | 207–8,694 | 7% |
| 18 equipos (`12_API` §5) | ~50 | 1,500–8,694 | 0% |
| proyecto de córners previo | 17 | 30–173 | 1% |

La última fila es la que lo demuestra: unidades **de 30 observaciones** daban
mejor potencia que las eras del América con 8,694 posesiones cada una. $\tau^2$
es una varianza entre unidades; con $k=4$ se estima a partir de cuatro números,
por precisos que sean.

**Consecuencia operativa: no se corre $\tau^2$ sobre un solo club.**

## 25.5 Qué contiene $\tau^2$, y qué NO se puede concluir

> Añadido el 2026-08-29, tras revisar la redacción original. El número no
> cambia; la etiqueta sí.

$\tau^2$ mide la varianza **entre eras**. Una era no cambia solo porque cambie
el entrenador: cambia el plantel, el calendario, el momento de forma, y también
**la razón por la que se cambió de técnico** — que suele ser una mala racha.

Por tanto:

$$\tau^2_{\text{observado}} = \underbrace{\tau^2_{\text{entrenador}} + \tau^2_{\text{plantel}} + \tau^2_{\text{contexto}}}_{\text{no separables con este diseño}}$$

**Lo que sí se puede afirmar**: que las eras de un mismo club difieren entre sí
más de lo que explica el ruido de muestreo, en 0.596 acciones por posesión, con
un suelo de detección de 0.247.

**Lo que NO se puede afirmar**: qué parte de esa diferencia pone el entrenador.

### Por qué ADR-34 no cierra este hueco

El control de plantel intra-jugador —9 de 17 futbolistas cambiaron su patrón
consigo mismos, contra 0.9 esperados por azar— es evidencia fuerte de que **la
huella táctica** no se explica solo por fichajes. Pero valida esa comparación
concreta, **no descompone $\tau^2$**: son dos cantidades distintas, calculadas
sobre objetos distintos, y juntarlas era el error de la redacción anterior.

### Qué haría falta

Un modelo de efectos mixtos con término de plantel, o un diseño
cuasi-experimental contra clubes que **no** cambiaron de técnico en la misma
ventana. Ambos necesitan los 18 equipos: con 12 eras no hay grados de libertad
para separar dos componentes de varianza. Es la misma restricción de ADR-49 —
manda $k$, no $n$.

### La frase que sí se sostiene ante un jurado

> *"Las etapas de un mismo club se distinguen entre sí más de lo que explica el
> azar, y hemos medido cuánto. Cuánto de eso pone el entrenador y cuánto los
> jugadores que tenía, este diseño no lo separa."*

---

## 25.6 Otros caveats


1. **Es la media empírica de acciones por posesión, no el $E[T]$ de la cadena.**
   Son estimandos distintos. Como contraste informal, Jardine vs Solari da
   +19.5% aquí contra el +22.4% publicado: consistente, no idéntico, y no tiene
   por qué serlo.
2. **Desbalance.** 5.5× con `MIN_POSS`; 42× sin él. El Empirical Bayes lo
   pondera por precisión, pero conviene declararlo.
3. **Una sola cantidad.** Se midió sobre duración de posesión. $P(\text{gol})$ y
   $P(\text{remate})$ están pendientes y podrían dar $\tau$ distinto — el reporte
   ya muestra que duración y peligro son dimensiones separables.
4. **No es causal, y tampoco es atribuible.** Mide que las eras difieren, no
   que el entrenador sea la causa **ni qué parte le corresponde**. La varianza
   entre eras contiene también plantel y contexto. Ver §25.5.

---

# 26. El eje de calidad del remate: qué mueve un entrenador y qué no

> Corrida 2026-08-26 · `scripts/25_goal_open_eras.py`, `26_goal_open_barrido.py`
> · familia `goal_open-eras` · ADR-51
>
> Módulo geométrico portado del proyecto de córners previo (xDefense) con tres
> correcciones. La muestra aquí es **cinco veces** la de aquel proyecto entero.

## 26.1 De dónde sale la muestra

`shot_freeze_frame` **sí está** en el volcado. `04_DATA_CONTRACT.md` §2 decía que
los freeze frames no estaban, y era cierto para **StatsBomb 360** (los del
producto de posiciones) y falso para el del evento de remate. Esa línea costó
descartar esta línea de trabajo durante semanas.

| | América | Cruz Azul |
|---|---|---|
| remates | 2,486 | — |
| con freeze frame | 2,454 (98.7%) | — |
| **juego abierto (conjunto de modelado)** | **2,332 · 269 goles** | **2,022 · 185 goles** |

**Los 32 remates sin foto son los 32 penales.** Ni uno de juego abierto ni de
tiro libre. El xG de StatsBomb para ellos es una constante (media y mediana
ambas 0.7835), y su tasa de gol —28 de 36— coincide con esa constante.

> **El filtro correcto es `shot_type == "Open Play"`, NO
> `shot_freeze_frame.is_not_null()`.** Parecen equivalentes y no lo son: hay
> **4 penales que SÍ traen foto**, y son 4 observaciones con `goal_open ≈ 1` y
> cero goles. Filtrar por disponibilidad de foto las deja entrar y **atenúa
> justo el efecto que se quiere medir**. Es el bug #10 con otra cara: el filtro
> correcto por la razón correcta produce el conjunto equivocado.

## 26.2 🟢 La geometría defensiva predice el gol

| modelo | AUC |
|---|---|
| `xG_base` (distancia + ángulo) | 0.7277 |
| `xG_full` (+ geometría defensiva) | **0.7949** |
| **Δ AUC** | **+0.0672** · IC95 **[+0.0451, +0.0882]** |

`goal_open` es el segundo coeficiente estandarizado más grande (**+0.652**),
solo por detrás de la distancia (−0.692).

El proyecto de córners obtuvo Δ AUC = +0.044 con IC que cruzaba cero. Con 2,332
remates en vez de 720, la respuesta es inequívoca.

**Invariante al radio del disco**: duplicarlo de 0.3 a 0.5 m mueve el
coeficiente de +0.652 a +0.653 y el Δ AUC de +0.0672 a +0.0693. La decisión que
se había marcado como arbitraria resulta irrelevante.

## 26.3 🟢 Validación externa: deuda de §24.3 saldada

| | AUC | BS | REL |
|---|---|---|---|
| `xG_full` propio | 0.7949 | 0.08356 | 0.00022 |
| `shot_statsbomb_xg` | 0.8203 | 0.07963 | 0.00047 |

**Correlación 0.861.** Siete features contra un modelo propietario, y la
diferencia de AUC es de 0.025.

Descomposición de Murphy ($BS = UNC - RES + REL$): **RES/UNC = 15.4%**. El
modelo resuelve el 15% de la incertidumbre; el 85% restante es **irreducible**
con estas features. Es la prueba numérica de que el gol desde juego abierto es
mayormente azar — y la razón de por qué nadie debería esperar separar
entrenadores por calidad de remate con esta muestra.

## 26.4 ⚪ La familia `goal_open-eras`: 0 de 21 sobreviven

**Familia declarada por escrito antes de correr el barrido** (ADR-47), copiada
al JSON con su fecha: una comparación por pareja de entrenadores **contiguos**
del mismo club con ≥150 remates, tres cantidades por pareja (diferencia en
`xG_base`, atribución geométrica, tasa empírica de gol), Benjamini–Hochberg
al 5%.

**Alcance: 7 de las 10 transiciones posibles.** Cruz Azul deja fuera a
**Moreno II (134 remates), Aguirre (86) y Moreno I (24)** por el umbral.

| pareja | cantidad | p | q |
|---|---|---|---|
| Jardine vs Ortiz | dif `xG_base` | 0.0180 | **0.3779** |
| Solari vs Herrera | dif `xG_base` | 0.0585 | 0.5319 |
| Ortiz vs Solari | dif `xG_base` | 0.0760 | 0.5319 |
| *(las otras 18)* | | ≥0.21 | ≥0.73 |

**Ninguna sobrevive.** El +0.0147 de Jardine vs Ortiz habría sido el titular
central: sin corregir daba p = 0.018.

**No hay partición legítima que lo salve**, y se comprobó antes de proponerlo:
aun si la familia hubiera sido solo `xG_base` con 7 pruebas —la partición más
favorable imaginable— q = 0.126.

> Anotado como **hipótesis post hoc, no como resultado**: los tres p más bajos
> de la familia son los tres de `xG_base` del América. La probabilidad de que
> eso ocurra por azar en alguna de las tres cantidades es 7.9%. Sugerente y sin
> valor probatorio. Perseguirlo exige una familia nueva declarada antes, sobre
> datos nuevos.

## 26.5 La forma correcta del nulo

**No** *"no hay diferencia en la calidad de los remates"*. Sí esto:

> **A través de siete cambios de entrenador en dos clubes, no detectamos
> diferencias en la calidad de los remates mayores de aproximadamente el 10% de
> la tasa base de gol.** Los IC descartan efectos por encima de ±0.012 en xG por
> remate; efectos menores quedan fuera del alcance de este diseño.

El ±10% sale directamente de los semianchos de los IC y es lo que convierte "no
encontramos" en una afirmación con contenido.

## 26.6 🟢 El hallazgo: dónde llega el entrenador y dónde no

| dimensión | efecto entre entrenadores | |
|---|---|---|
| duración de la posesión | +22.4%, +25.6% | 🟢 |
| volumen de remates | +44.6%, −12.5% | 🟢 |
| presión sostenida (k≥3) | +4.71 pp, q=0.041 | 🟢 |
| **calidad del remate** | **0 de 21 sobreviven** | ⚪ |
| probabilidad de gol | ninguna significativa, por **dos vías independientes** | ⚪ |

**Los entrenadores mueven dónde juega el equipo, cuánto aguanta el balón,
cuántas veces remata y dónde aprieta sin él. Lo que no mueven de forma
detectable es lo bueno que es cada remate.**

Es un hallazgo, no un fracaso, y es el mismo argumento de credibilidad que
sostiene "Sánchez vs Ferretti sin efecto": un método que encuentra efectos en
todas las dimensiones que mira es sospechoso. Este encuentra en cuatro y
descarta en dos, con la misma maquinaria.

Y las dos vías que descartan el gol son independientes: la probabilidad de
absorción de la cadena y la tasa empírica sobre el modelo de xG. Dos métodos
distintos, mismo resultado.

**Frase de cierre para el jurado:**

> *"El entrenador decide dónde y cuántas veces rematas. Quién remata mejor no lo
> decide él."*

## 26.7 Caveats

1. **`goal_open` tiene masa puntual en 1.0**: el 40% de los remates no tiene
   ningún defensor en la línea de visión. La media resume mal esa distribución;
   se reportan también la mediana y la fracción por debajo de 0.90.
2. **El bloque de remuestreo es el partido, no la posesión** (ADR-51). Con
   posesión los IC se estrechan entre un 17% y un 29%, y la atribución
   geométrica de Jardine vs Ortiz queda rozando la significancia
   ([−0.0009, +0.0196]). Habría sido un hallazgo fabricado por la unidad de
   remuestreo.
3. **Condicional a que hubo remate.** El freeze frame solo existe si se remató,
   así que esto mide calidad **del remate**, no capacidad de generarlo. Es el
   sesgo de selección estructural del proyecto de córners, heredado y declarado.
4. **7 de 10 transiciones.** Tres eras de Cruz Azul quedan fuera por muestra.
5. Los penales quedan fuera del análisis por definición: 36 remates.
