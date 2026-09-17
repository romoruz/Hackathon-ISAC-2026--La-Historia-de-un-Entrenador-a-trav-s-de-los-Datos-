# 10 — Resultados

> Todo hallazgo con su procedencia, su magnitud y su caveat. Nada aquí es
> presentable sin leer su columna de limitaciones.
>
> Corte: 2026-08-20 · `dtdecoder 0.5.0` · **Fases 0–3 completas**

<!-- h2_14 -->
> ⚠️ **AVISO (2026-09-15).** Las secciones 1 a 26 se calcularon con el volcado
> anterior y con `coach_eras.csv` **previo al bug #14**: la etiqueta "Solari"
> cubría a Herrera mal rotulado, a Solari y a siete meses de Ortiz, y el par
> Sánchez–Ferretti no existe con el umbral de 25 partidos. Sus cifras por era
> **no son citables**. Los contrastes entre eras vigentes están en **§27**.
> Siguen en pie las conclusiones de método que no dependen de las eras: la
> cobertura de los IC (§9) y el principio de §13.

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

Es el patrón de todos los bugs del proyecto aplicado a la estadística: un número plausible y
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

<!-- h2_14 -->
---

# 27. 🟢 H4 con la deriva fuera (ADR-53)

**Fuente**: `scripts/30_did_contemporaneo.py` → `reports/did_h4_v1.json`
**Método**: desviación de cada era contra la liga sin su club en los mismos
torneos, estimando α′N1 a λ=0, bootstrap por posesión (foco y base), IC basic,
BH sobre los pares intra-club. Detalle en ADR-53.

60 pares sobre 53 unidades · B = 4000 · rechazan tras BH: DiD **44**, crudo 47 · cambian de signo al corregir: **15** · no rechazados: 16 · eras bloqueadas: 0 · aviso de piso del p: ninguno · contra la v5: 12 dejan de rechazar, 11 empiezan a rechazar

## 27.1 Predicciones preinscritas contra lo que salió

| # | predicción | resultado | |
|---|---|---|---|
| 1 | la firma temporal baja respecto al crudo | crudo 37/47 (79%) → DiD 23/44 (52%) — cerca del 50% que se esperaría sin tendencia | ✅ |
| 2 | Cocca I vs Cocca II deja de ser negativo y significativo | crudo -7.01% → DiD +4.89% [+0.45, +9.62], q = 0.0389 — sigue siendo significativo con el signo INVERTIDO: el sentido del crudo era la deriva | ✅ |
| 3 | Jardine vs Solari conserva el signo y se reduce | crudo +31.42% → DiD +17.59% [+12.70, +22.43], q = 0.0010 | ✅ |
| 4 | ningún par demuestra equivalencia al 3% | ninguno; menor margen demostrable 4.02% | ✅ |

## 27.2 Los 60 pares

Signo positivo: el primer entrenador del par sostiene la posesión más que el
segundo. 🟢 rechaza tras BH · ⚪ no rechaza · ↺ el signo cambia al corregir la
deriva.
"crudo" es el mismo estimando sin normalizar, con las mismas réplicas.

| club | par | crudo | DiD | IC 95% | q | |
|---|---|---|---|---|---|---|
| América | Andre Jardine vs Fernando Ortiz | +12.8% | **+3.5%** | [+0.1, +7.0] | 0.0562 | ⚪ |
| América | Andre Jardine vs Santiago Solari | +31.4% | **+17.6%** | [+12.7, +22.4] | 0.0010 | 🟢 |
| América | Fernando Ortiz vs Santiago Solari | +16.5% | **+13.6%** | [+8.2, +18.7] | 0.0010 | 🟢 |
| Atlas | Benat San Jose vs Benjamin Mora | -4.2% | **-7.9%** | [-12.0, -3.5] | 0.0010 | 🟢 |
| Atlas | Benat San Jose vs Diego Cocca I | +7.0% | **-3.2%** | [-6.9, +0.6] | 0.1301 | ⚪ ↺ |
| Atlas | Benat San Jose vs Diego Cocca II | -0.5% | **+1.6%** | [-3.0, +6.4] | 0.5503 | ⚪ ↺ |
| Atlas | Benjamin Mora vs Diego Cocca I | +11.7% | **+5.1%** | [+1.0, +9.4] | 0.0207 | 🟢 |
| Atlas | Benjamin Mora vs Diego Cocca II | +3.9% | **+10.2%** | [+4.9, +15.5] | 0.0010 | 🟢 |
| Atlas | Diego Cocca I vs Diego Cocca II | -7.0% | **+4.9%** | [+0.5, +9.6] | 0.0389 | 🟢 ↺ |
| Atlético San Luis | Andre Jardine vs Domenec Torrent | -22.8% | **-18.0%** | [-21.0, -15.0] | 0.0010 | 🟢 |
| Atlético San Luis | Andre Jardine vs Guillermo Abascal | -11.5% | **-2.3%** | [-6.1, +1.7] | 0.2931 | ⚪ |
| Atlético San Luis | Andre Jardine vs Gustavo Leal | -29.5% | **-25.0%** | [-27.8, -21.9] | 0.0010 | 🟢 |
| Atlético San Luis | Domenec Torrent vs Guillermo Abascal | +14.7% | **+19.2%** | [+14.2, +24.5] | 0.0010 | 🟢 |
| Atlético San Luis | Domenec Torrent vs Gustavo Leal | -8.7% | **-8.5%** | [-12.2, -4.6] | 0.0010 | 🟢 |
| Atlético San Luis | Guillermo Abascal vs Gustavo Leal | -20.4% | **-23.2%** | [-26.4, -19.8] | 0.0010 | 🟢 |
| Cruz Azul | Juan Reynoso vs Martin Anselmi | -22.7% | **-15.6%** | [-19.0, -12.4] | 0.0010 | 🟢 |
| Cruz Azul | Juan Reynoso vs Nicolas Larcamon | -8.9% | **+2.8%** | [-1.5, +7.0] | 0.2639 | ⚪ ↺ |
| Cruz Azul | Martin Anselmi vs Nicolas Larcamon | +17.8% | **+21.8%** | [+17.3, +26.4] | 0.0010 | 🟢 |
| Guadalajara | Fernando Gago vs Gabriel Milito | -12.2% | **-12.3%** | [-16.1, -8.5] | 0.0010 | 🟢 |
| Guadalajara | Fernando Gago vs Veljko Paunovic | +12.3% | **+8.2%** | [+3.8, +12.7] | 0.0010 | 🟢 |
| Guadalajara | Gabriel Milito vs Veljko Paunovic | +27.9% | **+23.3%** | [+18.4, +28.3] | 0.0010 | 🟢 |
| Juárez | Hernan Cristante vs Martin Varini | -4.8% | **+4.3%** | [+0.2, +8.8] | 0.0522 | ⚪ ↺ |
| Juárez | Hernan Cristante vs Mauricio Barbieri | +0.1% | **+8.2%** | [+3.3, +13.1] | 0.0017 | 🟢 |
| Juárez | Hernan Cristante vs Ricardo Ferretti | +1.2% | **-1.4%** | [-5.2, +3.0] | 0.5503 | ⚪ ↺ |
| Juárez | Martin Varini vs Mauricio Barbieri | +5.1% | **+3.7%** | [-0.9, +8.3] | 0.1514 | ⚪ |
| Juárez | Martin Varini vs Ricardo Ferretti | +6.3% | **-5.5%** | [-9.4, -1.5] | 0.0150 | 🟢 ↺ |
| Juárez | Mauricio Barbieri vs Ricardo Ferretti | +1.1% | **-8.8%** | [-12.8, -4.5] | 0.0017 | 🟢 ↺ |
| León | Ariel Holan vs Eduardo Berizzo | +4.0% | **+19.2%** | [+14.5, +24.5] | 0.0010 | 🟢 |
| León | Ariel Holan vs Nicolas Larcamon | +4.1% | **+10.9%** | [+6.3, +15.5] | 0.0010 | 🟢 |
| León | Eduardo Berizzo vs Nicolas Larcamon | +0.1% | **-7.0%** | [-10.8, -3.2] | 0.0010 | 🟢 ↺ |
| Mazatlán | Benat San Jose vs Gabriel Caballero | -7.5% | **-5.9%** | [-10.2, -1.2] | 0.0209 | 🟢 |
| Mazatlán | Benat San Jose vs Ismael Rescalvo | -20.4% | **-12.7%** | [-16.7, -8.7] | 0.0010 | 🟢 |
| Mazatlán | Benat San Jose vs Victor Manuel Vucetich | -15.5% | **-7.3%** | [-11.4, -3.0] | 0.0024 | 🟢 |
| Mazatlán | Gabriel Caballero vs Ismael Rescalvo | -13.9% | **-7.2%** | [-11.5, -3.0] | 0.0017 | 🟢 |
| Mazatlán | Gabriel Caballero vs Victor Manuel Vucetich | -8.7% | **-1.5%** | [-5.7, +2.8] | 0.5503 | ⚪ |
| Mazatlán | Ismael Rescalvo vs Victor Manuel Vucetich | +6.0% | **+6.2%** | [+1.7, +11.1] | 0.0115 | 🟢 |
| Monterrey | Domenec Torrent vs Fernando Ortiz | +6.8% | **+4.9%** | [+0.3, +9.9] | 0.0522 | ⚪ |
| Monterrey | Domenec Torrent vs Martin Demichelis | +12.9% | **+10.9%** | [+5.7, +16.0] | 0.0010 | 🟢 |
| Monterrey | Domenec Torrent vs Victor Manuel Vucetich | +32.6% | **+22.1%** | [+16.8, +27.4] | 0.0010 | 🟢 |
| Monterrey | Fernando Ortiz vs Martin Demichelis | +5.8% | **+5.6%** | [+1.0, +10.0] | 0.0207 | 🟢 |
| Monterrey | Fernando Ortiz vs Victor Manuel Vucetich | +24.2% | **+16.3%** | [+11.9, +20.9] | 0.0010 | 🟢 |
| Monterrey | Martin Demichelis vs Victor Manuel Vucetich | +17.5% | **+10.1%** | [+5.8, +14.7] | 0.0010 | 🟢 |
| Necaxa | Eduardo Fentanes vs Jaime Lozano | -15.4% | **-23.7%** | [-26.7, -20.7] | 0.0010 | 🟢 |
| Pumas UNAM | Andres Lillini vs Efrain Valdez | -15.4% | **-5.5%** | [-8.8, -2.1] | 0.0039 | 🟢 |
| Pumas UNAM | Andres Lillini vs Gustavo Lema | -7.4% | **+1.9%** | [-1.4, +5.4] | 0.2931 | ⚪ ↺ |
| Pumas UNAM | Efrain Valdez vs Gustavo Lema | +9.5% | **+7.9%** | [+3.9, +12.0] | 0.0010 | 🟢 |
| Querétaro | Benjamin Mora vs Mauro Gerk | +4.4% | **-1.9%** | [-5.5, +1.6] | 0.2960 | ⚪ ↺ |
| Santos Laguna | Eduardo Fentanes vs Ignacio Ambriz | -19.8% | **-10.6%** | [-14.1, -6.8] | 0.0010 | 🟢 |
| Tigres UANL | Guido Pizarro vs Miguel Herrera | +9.5% | **-1.2%** | [-4.8, +2.6] | 0.5503 | ⚪ ↺ |
| Tigres UANL | Guido Pizarro vs Robert Siboldi | +2.4% | **+0.8%** | [-3.0, +4.8] | 0.7015 | ⚪ |
| Tigres UANL | Guido Pizarro vs Veljko Paunovic | +15.5% | **+15.7%** | [+10.8, +20.8] | 0.0010 | 🟢 |
| Tigres UANL | Miguel Herrera vs Robert Siboldi | -6.5% | **+2.1%** | [-1.4, +5.8] | 0.2931 | ⚪ ↺ |
| Tigres UANL | Miguel Herrera vs Veljko Paunovic | +5.5% | **+17.1%** | [+12.6, +21.7] | 0.0010 | 🟢 |
| Tigres UANL | Robert Siboldi vs Veljko Paunovic | +12.8% | **+14.7%** | [+9.9, +19.4] | 0.0010 | 🟢 |
| Tijuana | Juan Carlos Osorio vs Miguel Herrera | +40.0% | **+36.9%** | [+31.6, +42.2] | 0.0010 | 🟢 |
| Tijuana | Juan Carlos Osorio vs Sebastian Abreu | +21.9% | **+26.1%** | [+20.4, +32.1] | 0.0010 | 🟢 |
| Tijuana | Miguel Herrera vs Sebastian Abreu | -12.9% | **-7.9%** | [-11.6, -4.1] | 0.0010 | 🟢 |
| Toluca | Antonio Mohamed vs Ignacio Ambriz | +0.6% | **-6.0%** | [-9.3, -2.7] | 0.0024 | 🟢 ↺ |
| Toluca | Antonio Mohamed vs Renato Paiva | +0.1% | **+0.2%** | [-3.7, +4.0] | 0.9583 | ⚪ |
| Toluca | Ignacio Ambriz vs Renato Paiva | -0.5% | **+6.6%** | [+2.8, +10.4] | 0.0010 | 🟢 ↺ |

**Afirmaciones defendibles.**
- Magnitudes: la columna DiD, nunca la de crudo.
- Cocca I vs Cocca II: el técnico difiere de sí mismo, pero **en sentido
  contrario al del crudo**. Sin la corrección se habría contado al revés.
- Un par no rechazado se redacta con su margen (§27.3), nunca como "sin
  diferencia".

## 27.3 Lo que se puede decir de los no rechazados

| club | par | no detectamos una diferencia mayor a |
|---|---|---|
| Toluca | Antonio Mohamed vs Renato Paiva | 4.02% |
| Tigres UANL | Guido Pizarro vs Robert Siboldi | 4.75% |
| Tigres UANL | Guido Pizarro vs Miguel Herrera | 4.80% |
| Juárez | Hernan Cristante vs Ricardo Ferretti | 5.25% |
| Pumas UNAM | Andres Lillini vs Gustavo Lema | 5.41% |
| Querétaro | Benjamin Mora vs Mauro Gerk | 5.47% |
| Mazatlán | Gabriel Caballero vs Victor Manuel Vucetich | 5.72% |
| Tigres UANL | Miguel Herrera vs Robert Siboldi | 5.83% |
| Atlético San Luis | Andre Jardine vs Guillermo Abascal | 6.14% |
| Atlas | Benat San Jose vs Diego Cocca II | 6.44% |
| Atlas | Benat San Jose vs Diego Cocca I | 6.95% |
| Cruz Azul | Juan Reynoso vs Nicolas Larcamon | 6.99% |
| América | Andre Jardine vs Fernando Ortiz | 7.05% |
| Juárez | Martin Varini vs Mauricio Barbieri | 8.28% |
| Juárez | Hernan Cristante vs Martin Varini | 8.77% |
| Monterrey | Domenec Torrent vs Fernando Ortiz | 9.90% |

Ningún par cumple el criterio de equivalencia al 3% (D53-4). Con unas 3,000
posesiones por era, el margen mínimo demostrable ronda el 4%.

## 27.4 ⚪ Material para H5, no citable

Entrenadores con más de una unidad analizable. No controla el efecto del
club: es insumo para H5, no un resultado.

| entrenador | club: desviación contra la liga del mismo torneo [IC 95%] |
|---|---|
| Andre Jardine | América +24.6% [+22.3, +26.9] · Atlético San Luis -10.0% [-12.2, -7.7] |
| Benat San Jose | Atlas -7.5% [-10.4, -4.7] · Mazatlán -12.6% [-15.5, -9.5] |
| Benjamin Mora | Atlas +0.4% [-2.8, +3.6] · Querétaro -21.1% [-23.5, -18.7] |
| Domenec Torrent | Atlético San Luis +9.8% [+6.8, +12.9] · Monterrey +21.9% [+17.8, +26.1] |
| Eduardo Fentanes | Necaxa -29.1% [-30.9, -27.3] · Santos Laguna -9.2% [-11.4, -7.1] |
| Fernando Ortiz | América +20.3% [+16.9, +23.7] · Monterrey +16.2% [+12.7, +19.6] |
| Ignacio Ambriz | Santos Laguna +1.5% [-2.0, +5.0] · Toluca +23.7% [+21.0, +26.6] |
| Miguel Herrera | Tigres UANL +18.3% [+15.6, +21.1] · Tijuana -12.8% [-14.7, -10.9] |
| Nicolas Larcamon | Cruz Azul +0.8% [-2.0, +3.6] · León +6.9% [+3.9, +10.0] · Puebla -5.7% [-7.9, -3.5] |
| Veljko Paunovic | Guadalajara -5.6% [-8.2, -3.1] · Tigres UANL +1.1% [-2.0, +4.3] |
| Victor Manuel Vucetich | Mazatlán -5.7% [-8.5, -2.9] · Monterrey -0.1% [-2.7, +2.5] |

## 27.5 Bug #19 — la línea base que no entraba

`25_pares_h4.py` declaraba (H4-5) que el prior contemporáneo cancelaba la
deriva, y su regla H4-1 decía "significancia a λ\*". El código corría
magnitud y permutación a λ=0, donde el prior no entra. Ninguna excepción,
números plausibles: el síntoma fue estadístico (el entrenador posterior más
largo en la mayoría de los pares significativos). Corregido por ADR-53;
textos de `25` corregidos en el paquete h2_11.

## 27.6 Caveats

1. **La base no es el club.** El supuesto es que el club se habría movido como
   la liga; B3 lo contrasta de forma débil (14 unidades divergen en Carry/Pass).
2. **P(gol) y P(remate) son descriptivos** (D53-2): no hay contraste con FDR
   sobre ellos en esta versión.
3. **La serie por torneo** de cada unidad está en el JSON y es descriptiva.
4. **Todo lo anterior a §27 de este documento** usa las eras previas al
   bug #14 (ver el aviso de cabecera).

<!-- h2_23 -->
---

# 28. 🟢 D1 con la deriva fuera (ADR-54)

**Fuente**: `scripts/33_did_presion.py` → `reports/did_presion_v1.json`.
135 contrastes en la etapa 1; rechazan 6 con la
corrección (24 sin ella). 🟢 = rechaza tras BH.

| club | par | E1 q | E2 (pp) | E3 (‰/toque) | E4 (pp) | E5 (pp) |
|---|---|---|---|---|---|---|
| América | Andre Jardine vs Fernando Ortiz | 0.3017 | -1.96 (q 0.3852) | -1.38 (q 0.7040) | +6.51 (q 0.3351) | -0.85 (q 0.7002) |
| América | Andre Jardine vs Santiago Solari | 0.2175 | +3.25 (q 0.2989) | -1.10 (q 0.8509) | +10.47 (q 0.0643) | -0.48 (q 0.8509) |
| América | Fernando Ortiz vs Santiago Solari | 🟢 0.0412 | 🟢 +5.21 (q 0.0412) | +0.28 (q 0.9575) | +3.96 (q 0.6635) | +0.37 (q 0.9162) |
| Atlas | Benat San Jose vs Benjamin Mora | 0.4472 | -2.16 (q 0.4816) | -1.18 (q 0.8509) | -3.69 (q 0.7002) | +2.87 (q 0.2561) |
| Atlas | Benat San Jose vs Diego Cocca I | 0.9575 | +0.70 (q 0.8070) | +1.15 (q 0.8070) | -4.54 (q 0.5820) | +2.38 (q 0.3351) |
| Atlas | Benat San Jose vs Diego Cocca II | 0.8509 | +0.20 (q 0.9575) | -2.39 (q 0.6067) | +2.39 (q 0.8509) | +1.00 (q 0.7917) |
| Atlas | Benjamin Mora vs Diego Cocca I | 0.2561 | +2.86 (q 0.3017) | +2.34 (q 0.6385) | -0.84 (q 0.9162) | -0.49 (q 0.8509) |
| Atlas | Benjamin Mora vs Diego Cocca II | 0.3351 | +2.36 (q 0.4829) | -1.20 (q 0.8509) | +6.08 (q 0.4829) | -1.87 (q 0.4829) |
| Atlas | Diego Cocca I vs Diego Cocca II | 0.4604 | -0.50 (q 0.8509) | -3.54 (q 0.3404) | +6.93 (q 0.3917) | -1.38 (q 0.6359) |
| Atlético San Luis | Andre Jardine vs Domenec Torrent | 0.3351 | -2.46 (q 0.4122) | +3.66 (q 0.4012) | +3.81 (q 0.6385) | +0.15 (q 1.0000) |
| Atlético San Luis | Andre Jardine vs Guillermo Abascal | 0.6385 | -2.53 (q 0.3556) | -1.22 (q 0.7917) | +2.14 (q 0.8509) | -2.84 (q 0.4829) |
| Atlético San Luis | Andre Jardine vs Gustavo Leal | 1.0000 | +0.49 (q 0.8509) | +3.52 (q 0.3351) | -1.82 (q 0.8509) | -0.09 (q 0.9598) |
| Atlético San Luis | Domenec Torrent vs Guillermo Abascal | 0.4995 | -0.07 (q 1.0000) | -4.88 (q 0.3351) | -1.68 (q 0.8509) | -3.00 (q 0.4829) |
| Atlético San Luis | Domenec Torrent vs Gustavo Leal | 0.3249 | +2.96 (q 0.3351) | -0.14 (q 0.9744) | -5.64 (q 0.4829) | -0.25 (q 0.9575) |
| Atlético San Luis | Guillermo Abascal vs Gustavo Leal | 0.4829 | +3.03 (q 0.3017) | +4.74 (q 0.2561) | -3.96 (q 0.7040) | +2.75 (q 0.4995) |
| Cruz Azul | Juan Reynoso vs Martin Anselmi | 🟢 0.0112 | 🟢 -9.60 (q 0.0112) | -6.25 (q 0.1125) | +4.06 (q 0.6385) | +1.13 (q 0.6320) |
| Cruz Azul | Juan Reynoso vs Nicolas Larcamon | 🟢 0.0112 | 🟢 -7.71 (q 0.0112) | -2.24 (q 0.6359) | +1.98 (q 0.8509) | +1.78 (q 0.4170) |
| Cruz Azul | Martin Anselmi vs Nicolas Larcamon | 0.8070 | +1.90 (q 0.5820) | +4.01 (q 0.4170) | -2.08 (q 0.8509) | +0.64 (q 0.8019) |
| León | Ariel Holan vs Eduardo Berizzo | 0.7262 | +1.29 (q 0.7581) | -0.76 (q 0.8509) | +4.62 (q 0.6414) | -1.32 (q 0.7262) |
| León | Ariel Holan vs Nicolas Larcamon | 0.8964 | -1.47 (q 0.7262) | -0.60 (q 0.8964) | +3.34 (q 0.7917) | -0.05 (q 1.0000) |
| León | Eduardo Berizzo vs Nicolas Larcamon | 0.3351 | -2.76 (q 0.4170) | +0.16 (q 0.9732) | -1.28 (q 0.8964) | +1.27 (q 0.6385) |
| Monterrey | Domenec Torrent vs Fernando Ortiz | 0.7002 | -2.13 (q 0.5812) | -0.87 (q 0.8509) | +8.65 (q 0.3351) | +2.84 (q 0.4012) |
| Monterrey | Domenec Torrent vs Martin Demichelis | 0.4829 | -2.63 (q 0.4995) | +1.30 (q 0.8070) | +9.29 (q 0.3351) | +1.96 (q 0.6385) |
| Monterrey | Domenec Torrent vs Victor Manuel Vucetich | 0.4829 | -2.41 (q 0.4829) | -3.24 (q 0.4156) | +7.64 (q 0.3917) | +0.70 (q 0.8509) |
| Monterrey | Fernando Ortiz vs Martin Demichelis | 0.6912 | -0.50 (q 0.8850) | +2.17 (q 0.5594) | +0.64 (q 0.9575) | -0.88 (q 0.8070) |
| Monterrey | Fernando Ortiz vs Victor Manuel Vucetich | 0.8509 | -0.28 (q 0.9190) | -2.38 (q 0.4829) | -1.01 (q 0.9162) | -2.14 (q 0.3351) |
| Monterrey | Martin Demichelis vs Victor Manuel Vucetich | 0.4829 | +0.22 (q 0.9575) | -4.55 (q 0.2561) | -1.65 (q 0.8762) | -1.26 (q 0.6912) |

## 28.1 Etapa 2: zonas dentro de los pares cuyo E1 rechaza


**América · Fernando Ortiz vs Santiago Solari** — 2 zonas tras BH dentro del par:

| zona (ix, iy) | Δ | IC 95% | q | crudo | logit mismo signo |
|---|---|---|---|---|---|
| 3 (0, 3) | +13.48 pp | [+7.67, +19.44] | 0.0033 | +10.81 pp | sí |
| 6 (1, 2) | +10.55 pp | [+4.67, +16.86] | 0.0033 | +8.05 pp | sí |

**Cruz Azul · Juan Reynoso vs Martin Anselmi** — 13 zonas tras BH dentro del par:

| zona (ix, iy) | Δ | IC 95% | q | crudo | logit mismo signo |
|---|---|---|---|---|---|
| 1 (0, 1) | -9.71 pp | [-18.11, -1.75] | 0.0261 | -12.26 pp | sí |
| 3 (0, 3) | -8.21 pp | [-13.74, -2.77] | 0.0055 | -6.94 pp | sí |
| 4 (1, 0) | -9.19 pp | [-13.91, -4.28] | 0.0010 | -6.34 pp | sí |
| 5 (1, 1) | -10.12 pp | [-15.75, -4.43] | 0.0010 | -8.11 pp | sí |
| 7 (1, 3) | -11.15 pp | [-15.10, -6.84] | 0.0010 | -8.94 pp | sí |
| 8 (2, 0) | -8.34 pp | [-12.34, -4.31] | 0.0010 | -6.67 pp | sí |
| 9 (2, 1) | -4.88 pp | [-9.34, -0.68] | 0.0395 | -2.70 pp | sí |
| 10 (2, 2) | -10.26 pp | [-14.90, -5.62] | 0.0010 | -7.94 pp | sí |
| 11 (2, 3) | -10.17 pp | [-13.94, -6.31] | 0.0010 | -8.33 pp | sí |
| 13 (3, 1) | -7.72 pp | [-12.55, -2.98] | 0.0040 | -5.97 pp | sí |
| 14 (3, 2) | -8.05 pp | [-12.27, -3.84] | 0.0010 | -7.26 pp | sí |
| 15 (3, 3) | -7.24 pp | [-11.50, -3.04] | 0.0017 | -7.17 pp | sí |
| 16 (4, 0) | -11.40 pp | [-18.38, -4.43] | 0.0030 | -12.25 pp | sí |

**Cruz Azul · Juan Reynoso vs Nicolas Larcamon** — 10 zonas tras BH dentro del par:

| zona (ix, iy) | Δ | IC 95% | q | crudo | logit mismo signo |
|---|---|---|---|---|---|
| 3 (0, 3) | -9.83 pp | [-15.43, -3.97] | 0.0050 | -10.05 pp | sí |
| 4 (1, 0) | -9.45 pp | [-13.91, -5.17] | 0.0033 | -6.76 pp | sí |
| 7 (1, 3) | -12.39 pp | [-16.88, -7.64] | 0.0033 | -10.25 pp | sí |
| 8 (2, 0) | -6.75 pp | [-11.05, -2.61] | 0.0089 | -5.00 pp | sí |
| 9 (2, 1) | -7.92 pp | [-12.88, -3.01] | 0.0089 | -5.09 pp | sí |
| 10 (2, 2) | -8.19 pp | [-13.74, -2.22] | 0.0200 | -5.75 pp | sí |
| 11 (2, 3) | -9.21 pp | [-13.41, -4.82] | 0.0044 | -7.40 pp | sí |
| 13 (3, 1) | -6.04 pp | [-10.80, -0.98] | 0.0367 | -5.06 pp | sí |
| 14 (3, 2) | -6.92 pp | [-11.80, -2.09] | 0.0200 | -6.19 pp | sí |
| 15 (3, 3) | -5.47 pp | [-9.99, -1.08] | 0.0363 | -5.99 pp | sí |

**Caveats.** (1) Antes de redactar dónde presiona cada técnico, hay que
comprobar la orientación de las zonas con `13_verificar_ejes.py`. (2) E2
condiciona a sobrevivir hasta k = 3. (3) La presión es asociación: StatsBomb
la anota cuando un defensor se acerca.

---

# 29. 🟢 Balón parado (ADR-55)

**Fuente**: `scripts/35_balon_parado.py` → `reports/balon_parado_v2.json`.
La síntesis está en ADR-55. Eras de casos (diferencia contra la liga del mismo
torneo; C2 en unidades de xG por remate):

| era | partidos | C1 of (dif.) | C1 def (dif.) | C2 of (dif.) | C2 def (dif.) |
|---|---|---|---|---|---|
| Andre Jardine (América) | 100 | +0.3 pp [-4.1, +4.6] | -2.6 pp [-6.8, +1.8] | +0.0037 | -0.0050 |
| Fernando Ortiz (América) | 43 | -1.8 pp [-8.3, +4.8] | -9.2 pp [-15.3, -2.6] | -0.0054 | -0.0123 |
| Santiago Solari (América) | 25 | +5.1 pp [-3.9, +14.3] | +2.6 pp [-8.6, +14.2] | -0.0026 | -0.0184 |
| Benat San Jose (Atlas) | 34 | +2.0 pp [-5.8, +9.8] | +3.3 pp [-4.8, +12.1] | +0.0009 | -0.0104 |
| Benjamin Mora (Atlas) | 31 | -7.0 pp [-13.7, -0.5] | +2.9 pp [-4.9, +10.3] | +0.0131 | +0.0058 |
| Andre Jardine (Atlético San Luis) | 48 | -3.4 pp [-10.2, +4.0] | -4.2 pp [-10.5, +2.3] | +0.0005 | -0.0146 |
| Domenec Torrent (Atlético San Luis) | 34 | +0.6 pp [-7.6, +8.4] | +11.7 pp [+2.7, +21.0] | -0.0004 | +0.0047 |
| Nicolas Larcamon (Cruz Azul) | 33 | +4.0 pp [-2.4, +11.4] | -4.3 pp [-15.0, +7.0] | -0.0068 | +0.0343 |
| Veljko Paunovic (Guadalajara) | 34 | -9.3 pp [-18.0, -0.6] | +12.7 pp [+4.6, +22.1] | -0.0030 | -0.0123 |
| Nicolas Larcamon (León) | 34 | +3.3 pp [-4.5, +11.9] | -7.7 pp [-13.6, -1.4] | +0.0029 | -0.0007 |
| Victor Manuel Vucetich (Mazatlán) | 34 | +2.3 pp [-4.1, +8.6] | -3.0 pp [-11.4, +5.9] | -0.0025 | +0.0059 |
| Benat San Jose (Mazatlán) | 26 | +0.9 pp [-13.5, +14.6] | -3.8 pp [-13.3, +4.4] | -0.0183 | +0.0036 |
| Victor Manuel Vucetich (Monterrey) | 45 | +2.4 pp [-4.3, +9.0] | -8.8 pp [-17.3, -0.6] | -0.0125 | +0.0073 |
| Fernando Ortiz (Monterrey) | 38 | -5.3 pp [-12.4, +1.7] | -2.5 pp [-8.4, +3.1] | -0.0131 | -0.0110 |
| Domenec Torrent (Monterrey) | 25 | +6.9 pp [-3.9, +17.8] | +1.7 pp [-6.9, +9.5] | -0.0112 | -0.0001 |
| Eduardo Fentanes (Necaxa) | 40 | -2.8 pp [-10.7, +4.5] | -0.1 pp [-6.3, +6.4] | -0.0102 | -0.0035 |
| Nicolas Larcamon (Puebla) | 51 | +5.4 pp [-1.2, +12.2] | +0.2 pp [-5.5, +5.7] | -0.0001 | +0.0020 |
| Benjamin Mora (Querétaro) | 33 | +8.3 pp [-0.7, +18.3] | +5.0 pp [-2.3, +12.0] | -0.0284 | -0.0124 |
| Eduardo Fentanes (Santos Laguna) | 41 | +1.8 pp [-6.4, +9.3] | +8.0 pp [-0.4, +16.2] | +0.0055 | -0.0090 |
| Ignacio Ambriz (Santos Laguna) | 28 | -0.3 pp [-10.4, +10.3] | +14.9 pp [+6.5, +22.8] | +0.0170 | +0.0090 |
| Miguel Herrera (Tigres UANL) | 51 | -4.2 pp [-9.9, +1.6] | -7.2 pp [-14.6, +0.4] | +0.0080 | +0.0031 |
| Veljko Paunovic (Tigres UANL) | 27 | +5.3 pp [-1.6, +11.7] | -0.9 pp [-11.1, +8.8] | +0.0222 | -0.0200 |
| Miguel Herrera (Tijuana) | 45 | -2.3 pp [-9.0, +4.6] | -7.5 pp [-14.6, -0.5] | -0.0067 | +0.0140 |
| Ignacio Ambriz (Toluca) | 64 | +5.4 pp [-0.5, +11.8] | +0.0 pp [-5.1, +5.0] | -0.0122 | +0.0025 |

---

# 30. 🟢 Contexto (ADR-56)

**Fuente**: `scripts/36_contexto.py` → `reports/contexto_v1.json`. La tabla de
la liga está en ADR-56. Las eras del América:


**Andre Jardine** (100 partidos)

| contraste | θ | IC 95% | q (ADR-52) |
|---|---|---|---|
| localia · M1 | -0.003 | [-0.569, +0.568] | 1.0000 |
| localia · M2 | -0.08 pp | [-1.83, +1.63] | 1.0000 |
| localia · M3 | -0.15 pp | [-2.35, +1.99] | 1.0000 |
| localia · M4 | +0.16 pp | [-1.54, +1.85] | 1.0000 |
| marcador · M1 | +0.090 | [-0.573, +0.747] | 1.0000 |
| marcador · M2 | +0.47 pp | [-1.88, +2.68] | 1.0000 |
| marcador · M3 | +0.27 pp | [-2.32, +2.78] | 1.0000 |
| marcador · M4 | -2.70 pp | [-4.92, -0.47] | 0.4226 |
| momento · M1 | -0.070 | [-0.465, +0.323] | 1.0000 |
| momento · M2 | +2.05 pp | [+0.25, +3.86] | 0.4640 |
| momento · M3 | -0.68 pp | [-1.93, +0.58] | 0.9659 |
| momento · M4 | +0.08 pp | [-1.48, +1.57] | 1.0000 |
| rival · M1 | -0.353 | [-1.016, +0.289] | 0.9659 |
| rival · M2 | -1.92 pp | [-4.01, +0.16] | 0.6757 |
| rival · M3 | -3.62 pp | [-6.26, -1.06] | 0.2007 |
| rival · M4 | -0.15 pp | [-1.83, +1.58] | 1.0000 |

**Fernando Ortiz** (43 partidos)

| contraste | θ | IC 95% | q (ADR-52) |
|---|---|---|---|
| localia · M1 | +0.839 | [+0.202, +1.514] | 0.3207 |
| localia · M2 | +0.75 pp | [-1.88, +3.29] | 1.0000 |
| localia · M3 | -2.79 pp | [-6.20, +0.62] | 0.8134 |
| localia · M4 | +0.91 pp | [-1.33, +3.18] | 0.9790 |
| marcador · M1 | -0.160 | [-0.921, +0.613] | 1.0000 |
| marcador · M2 | -0.92 pp | [-5.93, +3.90] | 1.0000 |
| marcador · M3 | -4.76 pp | [-8.48, -1.35] | 0.2007 |
| marcador · M4 | -0.00 pp | [-2.99, +3.06] | 1.0000 |
| momento · M1 | -0.410 | [-0.916, +0.090] | 0.8134 |
| momento · M2 | -0.73 pp | [-3.70, +2.21] | 1.0000 |
| momento · M3 | -0.46 pp | [-2.11, +1.12] | 1.0000 |
| momento · M4 | +0.31 pp | [-1.98, +2.52] | 1.0000 |
| rival · M1 | -0.138 | [-0.901, +0.654] | 1.0000 |
| rival · M2 | +1.25 pp | [-2.13, +4.24] | 0.9890 |
| rival · M3 | -0.06 pp | [-4.52, +4.10] | 1.0000 |
| rival · M4 | -0.10 pp | [-2.90, +2.64] | 1.0000 |

**Santiago Solari** (25 partidos)

| contraste | θ | IC 95% | q (ADR-52) |
|---|---|---|---|
| localia · M1 | +0.580 | [-0.413, +1.571] | 0.9526 |
| localia · M2 | +0.31 pp | [-2.67, +3.42] | 1.0000 |
| localia · M3 | -0.08 pp | [-4.69, +4.48] | 1.0000 |
| localia · M4 | +2.15 pp | [-1.00, +5.61] | 0.8756 |
| marcador · M1 | -0.313 | [-1.448, +0.973] | 1.0000 |
| marcador · M2 | -0.24 pp | [-5.21, +4.37] | 1.0000 |
| marcador · M3 | +1.99 pp | [-3.31, +7.87] | 0.9890 |
| marcador · M4 | +2.12 pp | [-2.49, +7.29] | 0.9713 |
| momento · M1 | -0.058 | [-0.666, +0.543] | 1.0000 |
| momento · M2 | -0.25 pp | [-3.03, +2.55] | 1.0000 |
| momento · M3 | -0.23 pp | [-2.39, +1.90] | 1.0000 |
| momento · M4 | +0.05 pp | [-2.16, +2.47] | 1.0000 |
| rival · M1 | -1.478 | [-2.804, -0.285] | 0.3687 |
| rival · M2 | -1.51 pp | [-5.70, +3.02] | 1.0000 |
| rival · M3 | +3.77 pp | [-2.35, +9.43] | 0.8798 |
| rival · M4 | +0.35 pp | [-3.78, +4.65] | 1.0000 |

En las eras del América, 6 de 48 intervalos excluyen el cero **antes**
de corregir y **ninguno** sobrevive a BH. La frase correcta: ningún técnico del
América ajusta al contexto de forma detectablemente distinta a la liga.

---

# 31. ⚪ Casos: lo que viaja con el entrenador (descriptivo)

Tabla de ADR-57. E[T] y balón parado se vieron antes de preinscribir: son
descriptivos.

| entrenador | club | E[T] vs liga (H4) | ajuste al marcador, M1 | C1 of | C1 def |
|---|---|---|---|---|---|
| Andre Jardine | América | +24.6% | +0.090 | +0.3 pp | -2.6 pp |
| Andre Jardine | Atlético San Luis | -10.0% | +0.888 | -3.4 pp | -4.2 pp |
| Fernando Ortiz | América | +20.3% | -0.160 | -1.8 pp | -9.2 pp |
| Fernando Ortiz | Monterrey | +16.2% | -0.464 | -5.3 pp | -2.5 pp |
| Santiago Solari | América | +5.9% | -0.313 | +5.1 pp | +2.6 pp |
| Benat San Jose | Atlas | -7.5% | +0.272 | +2.0 pp | +3.3 pp |
| Benat San Jose | Mazatlán | -12.6% | -0.766 | +0.9 pp | -3.8 pp |
| Benjamin Mora | Atlas | +0.4% | +0.608 | -7.0 pp | +2.9 pp |
| Benjamin Mora | Querétaro | -21.1% | +0.680 | +8.3 pp | +5.0 pp |
| Domenec Torrent | Atlético San Luis | +9.8% | +0.879 | +0.6 pp | +11.7 pp |
| Domenec Torrent | Monterrey | +21.9% | -0.886 | +6.9 pp | +1.7 pp |
| Nicolas Larcamon | Cruz Azul | +0.8% | -0.143 | +4.0 pp | -4.3 pp |
| Nicolas Larcamon | León | +6.9% | -0.479 | +3.3 pp | -7.7 pp |
| Nicolas Larcamon | Puebla | -5.7% | +0.596 | +5.4 pp | +0.2 pp |
| Veljko Paunovic | Guadalajara | -5.6% | +0.147 | -9.3 pp | +12.7 pp |
| Veljko Paunovic | Tigres UANL | +1.1% | +0.741 | +5.3 pp | -0.9 pp |
| Victor Manuel Vucetich | Mazatlán | -5.7% | -0.228 | +2.3 pp | -3.0 pp |
| Victor Manuel Vucetich | Monterrey | -0.1% | -0.866 | +2.4 pp | -8.8 pp |
| Eduardo Fentanes | Necaxa | -29.1% | +0.798 | -2.8 pp | -0.1 pp |
| Eduardo Fentanes | Santos Laguna | -9.2% | -0.068 | +1.8 pp | +8.0 pp |
| Ignacio Ambriz | Santos Laguna | +1.5% | +1.009 | -0.3 pp | +14.9 pp |
| Ignacio Ambriz | Toluca | +23.7% | -0.331 | +5.4 pp | +0.0 pp |
| Miguel Herrera | Tigres UANL | +18.3% | -0.693 | -4.2 pp | -7.2 pp |
| Miguel Herrera | Tijuana | -12.8% | +0.378 | -2.3 pp | -7.5 pp |

---

# 32. Bugs #20 y #21

**#20 · la base de D1 truncaba distinto que la unidad.** `data/prior_liga`
usa `min_actions = 2`; las eras defendiendo, `min_actions_defense = 1`. La
base no tenía las posesiones de una acción que terminan sin fila `TERMINAL`,
justo el producto de una presión exitosa (y de un córner despejado al primer
toque). Corregido con la vista defensora (ADR-54, adenda 1).

**#21 · el freeze frame del API es JSON.** `xg_remate.features` se escribió
para el texto de Python del volcado viejo (`True`/`False`) y devolvía `None`
en silencio con el JSON del API (`true`/`false`). `35` detecta el formato
sobre una muestra y aborta si ninguno funciona (ADR-55, adenda 1).

Los dos produjeron números o vacíos sin excepción. Con estos, el registro
suma **veinte bugs encontrados**, numerados hasta el #21 (el #13 se evitó).
