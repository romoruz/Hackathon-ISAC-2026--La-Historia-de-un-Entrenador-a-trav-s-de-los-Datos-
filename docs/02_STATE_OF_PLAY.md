# 02 — Estado actual

> `dtdecoder 0.6.0` · corte 2026-08-22 · **Empezar aquí.**
>
> Este documento es el ancla del proyecto. Si solo vas a leer uno, lee este.

---

## 1. Qué es esto, en cinco líneas

Modelamos el estilo de un entrenador como la **matriz de transición de una
cadena de Markov absorbente** sobre estados (zona × fase de juego), estimada de
eventos Hudl StatsBomb de Liga MX. De la cadena salen tres cantidades con
significado futbolístico: cuánto dura una posesión, dónde vive el equipo, y con
qué probabilidad termina en gol.

**Todo el pipeline está validado sobre dos clubes independientes.** El
entregable es un reporte HTML autocontenido.

### El reto que responde

ISAC 2026, *"La historia de un entrenador a través de los datos"*:

> *"Su análisis debe permitir que alguien que **no vio los partidos** pueda
> entender con claridad cómo juega el equipo y cuáles son las ideas del
> entrenador."*

Ese principio manda sobre todo lo demás. Por eso el reporte HTML no muestra ni
un p-valor: la incertidumbre se dice en palabras.

---

## 2. Dónde estamos

| Fase | Código | Datos reales | Validada |
|---|---|---|---|
| 0 — Ingesta y transiciones | ✅ | ✅ 2 clubes | ✅ |
| 1 — Estimación con encogimiento | ✅ | ✅ | ✅ |
| 2 — Cadena absorbente | ✅ | ✅ | ✅ |
| 3 — Inferencia | ✅ | ✅ | ✅ |
| Control de plantel | ✅ | ✅ | ✅ (con un nivel descartado) |
| Bloque defensivo D1 (presión) | ✅ | ✅ 2 clubes | ✅ |
| Calidad del remate (`goal_open`) | ✅ | ✅ | ✅ |
| Reporte HTML | ✅ | ✅ | ✅ 2 comprobaciones e2e |
| 4–9 (roadmap) | ❌ | — | — |

### Datos

| | Club América | Cruz Azul |
|---|---|---|
| archivo | `eventos_completos_america.csv` | `eventos_completos_cruz_azul.csv` |
| partidos | 175 | 158 |
| transiciones | 222,251 | 196,653 |
| posesiones | 32,282 | 30,371 |
| eras mapeadas | 4 | 8 |
| ventana | Apertura 2021 – Clausura 2025 | igual |

**Nota importante sobre el prior**: `transitions.parquet` contiene los **18
equipos** de esos partidos. La columna `coach` es nula para los 17 rivales, y
`_not_focus` los incluye vía `is_null()`. Es decir, **el prior ya es un pool de
rivales, no solo los otros entrenadores del club**. Ver §7.

---

## 3. Las fechas: resueltas por derivación (ADR-26)

El volcado no trae `match_date`. En vez de esperar al API, **se derivan del
patrón de `match_id`**: los identificadores de StatsBomb se asignan por lote, y
en estos datos forman bloques separados por saltos grandes. Los bloques de ~17
partidos son torneos regulares; los de 3–6, liguillas. La ventana contiene
exactamente **8 torneos**, y a cada partido se le asigna una fecha sintética
repartida en el calendario real de su torneo.

`scripts/01_derivar_fechas.py` emite un `match_dates.csv` compatible con
`eras.load_match_dates`, así que **es reemplazable por las fechas reales sin
tocar nada aguas abajo**.

### Validación contra Wikipedia

| club | DT | Wikipedia | derivado |
|---|---|---|---|
| América | Jardine | 160 (todas comp.) | 93 |
| América | Solari | 52 | 39 |
| América | Ortiz | 55 | 26 |
| Cruz Azul | Anselmi | 50 | 43 |
| Cruz Azul | Reynoso | 74 (desde ene-2021) | 37 |
| Cruz Azul | Ferretti | 17 | 16 |
| Cruz Azul | **Moreno I** | **2** | **2** ✅ exacto |

Error máximo 2–3 partidos, concentrado en las fronteras a media temporada.

**Supuesto frágil declarado**: dentro de un bloque, el orden de `match_id`
aproxima el orden de jornada. No verificado. El América tiene **un** cambio de
DT a media temporada; Cruz Azul tiene **cuatro**.

**Cuando llegue el API, esto se sustituye.** Ver `12_API_STATSBOMB.md`.

---

## 4. Resultados validados

Todos con intervalo de confianza y todos replicados. Detalle en
`10_RESULTADOS.md`.

| hallazgo | magnitud | IC 95% |
|---|---|---|
| Jardine sostiene más que Solari | +22.4% | [+18.6, +26.4] |
| Anselmi sostiene más que Reynoso | +25.6% | [+21.4, +29.7] |
| Jardine sostiene más que Ortiz | +7.9% | [+3.9, +11.8] |
| Anselmi genera más remates que Reynoso | +44.6% | [+30.1, +59.2] |
| Jardine genera menos remates que Ortiz | −12.5% | [−23.9, −1.5] |
| **Sánchez vs Ferretti** | **+1.6%** | **[−3.3, +6.8]** ← sin efecto |

**Esa última fila importa tanto como las otras.** Que el método encuentre
efectos grandes en unos cambios de entrenador y ninguno en otros demuestra que
**discrimina**, en lugar de hallar diferencias en todas partes.

Ninguna diferencia en **probabilidad de gol** resultó significativa.

---

## 5. Los seis pilares de validación

1. **Bondad de ajuste.** Markov de primer orden **rechazado** por
   sobredispersión (KS≈0.09, p=0.005), mismo patrón en tres unidades. ADR-21
   explica por qué el modelo se mantiene.
2. **Auto-transiciones.** El 40% de $E[T]$ es permanencia en zona. Medido, no
   oculto: 0.2821 (América) y 0.2712 (Cruz Azul).
3. **Invariancia a la resolución.** Los efectos grandes no cambian entre 12 y
   30 zonas.
4. **Replicación.** Todo lo anterior se reproduce en un club independiente con
   ocho entrenadores y otro calendario.
5. **Cobertura de los IC.** 0.944 contra 0.95 nominal, validada con un
   generador a nivel de cadena con parámetro conocido.
6. **Nulas empíricas.** Ninguna distancia se reporta sin su distribución de
   referencia (ADR-30). Se violó tres veces y las tres la conclusión estaba mal.

---

## 6. El control de plantel: tres niveles, uno descartado

La amenaza más seria del proyecto era *"lo que mides no es el DT, es que tuvo
mejores jugadores"*. `scripts/11_confusion_plantel.py` la ataca en tres niveles.

| nivel | qué hace | estado |
|---|---|---|
| 1 — solapamiento | % de acciones ejecutadas por jugadores compartidos | ✅ |
| 2 — núcleo estable | repetir el análisis solo con esas posesiones | ❌ **circular** |
| 3 — intra-jugador | comparar a cada jugador consigo mismo | ✅ **decisivo** |

### Nivel 1

Jardine heredó el **67%** de las acciones del plantel de Ortiz y el **55%** del
de Solari. Anselmi solo el **41%** del de Reynoso.

### Nivel 2 — DESCARTADO por sesgo de longitud

Cualquier filtro basado en "quién ejecutó las acciones" **selecciona por
longitud de posesión**: una posesión larga tiene más oportunidades de incluir a
alguien fuera del núcleo. Y la longitud es justo la variable que se mide.

El diagnóstico automático lo detecta en los tres umbrales probados (0.5, 0.7,
0.9), con sesgo diferencial de 22 a 37 puntos porcentuales. Con umbral 0.9 el
signo del efecto **se invierte**.

**Se reporta como limitación demostrada, no como resultado.** Que el script
detecte su propia invalidez es en sí una diapositiva.

### Nivel 3 — el argumento decisivo

Para cada jugador con datos en ambas eras, ¿cambió *su* patrón de transiciones?
Prueba de permutación por jugador, con control de FDR:

| comparación | cambian tras BH | esperados por azar |
|---|---|---|
| Jardine vs Ortiz | **9 de 17** | 0.9 |
| Anselmi vs Reynoso | **4 de 5** | 0.2 |
| Jardine vs Solari | **4 de 13** | 0.7 |

**La frase defendible**: *"Jardine heredó el 67% de las acciones del plantel de
Ortiz. Y de los 17 jugadores con datos en ambas eras, 9 cambiaron su patrón de
juego de forma detectable, cuando por azar se esperaría uno. Eso no lo explica
el fichaje."*

**Limitación que no desaparece**: aunque el jugador sea el mismo, sus
compañeros, su posición y sus rivales cambian.

---

## 7. Limitaciones vivas

### 7.1 El prior son rivales, no la liga

`_not_focus` incluye los 17 rivales del América, pero esos rivales **no son una
muestra aleatoria de la liga**: son los que enfrentó, con la composición de su
calendario. Con los 18 equipos completos esta amenaza desaparecería. Ver §9.

### 7.2 λ está débilmente identificado

La curva de CV es una meseta: 0.006 nats entre λ=100 y λ=2000. **"El encogimiento
mejora la predicción" es sólido; "el λ óptimo es 500" no lo es.**

Y λ es casi irrelevante para predecir pero decisivo para las magnitudes: la
atenuación va de 0.87 (λ=100) a 0.26 (λ=2000). Regla: **significancia con λ\*,
magnitudes con λ=0** (ADR-22).

### 7.3 Markov de primer orden rechazado

Sobredispersión. Se mantiene el modelo (ADR-21) pero bloquea la Fase 7.

### 7.4 Rotación de plantilla

Acotada por el nivel 3, no eliminada.

### 7.5 Fechas sintéticas

Especialmente frágiles en Cruz Azul (cuatro cambios a media temporada).

### 7.6 El eje Y — RESUELTO (bug #12)

**Estaba espejeado.** StatsBomb usa origen arriba-izquierda con `y` creciendo
hacia abajo, así que para un equipo que ataca hacia `x=120` el borde `y=0` queda
a su **izquierda**. El vector `FRANJA` estaba al revés.

Verificado con Alejandro Zendejas (extremo derecho): el **43.6%** de sus
acciones caen en `iy=3`, que por tanto es la banda derecha.

`scripts/13_verificar_ejes.py` lo comprueba contra tres jugadores de banda
conocida y debe correrse tras cualquier cambio en `grid.py`.

### 7.7 `min_carry_length` sin sensibilidad

La única del plan original sin hacer. Ya se sabe que **no puede** explicar las
auto-transiciones: el 60% vienen de pases, que ningún umbral de acarreo toca.

---

## 8. Los bugs #1–#12 (hasta 2026-08-22): todos silenciosos

Ninguno lanzó una excepción. Todos produjeron números plausibles pero
incorrectos. **Es el patrón de riesgo dominante del proyecto y el argumento que
justifica toda la infraestructura de tests.**

| # | Bug | Síntoma | Corrección |
|---|---|---|---|
| 1 | `scan_csv` con esquema de 100 filas | columnas raras tipadas `Null`; cero goles | escaneo completo |
| 2 | IC no contenía su estimador puntual | `diff=0.1827`, IC `[0.1915, 0.2714]` | `_diff_estimate()` única |
| 3 | Orden de fases del dict | `.npz` desalineados entre corridas | `phase_order` explícito |
| 4 | Fuga de prior | λ\* en el techo; diferencias diluidas | `--prior exclude_focus` |
| 5 | `set_piece` = 33% | saques de banda como balón parado | fase `restart` |
| 6 | 9 acciones por posesión | acarreos de reajuste | `min_carry_length` |
| 7 | `phase2` leía el `.npz` de otra unidad | figuras con nombre equivocado | contrato de identidad |
| 8 | Semilla fija sobre input no determinista | 3 corridas → 3 resultados | ordenar antes de barajar |
| 9 | `player_id` con `else None` | parquet sin la columna, sin aviso | `KeyError` explícito |
| 10 | Filtro tiraba las absorciones terminales | $E[T]$ inflado 30% | conservarlas siempre |
| 11 | Filtro por transición sesgaba por longitud | signo invertido con umbral alto | filtro por posesión + diagnóstico |
| 12 | **Eje Y espejeado** | los mapas mostraban la banda contraria | `FRANJA` invertida + `13_verificar_ejes.py` |

### Los dos más instructivos

**#10** nació de dos decisiones **correctas por separado**: poner `player_id =
null` en las absorciones terminales (no tienen ejecutante) y filtrar por
`player_id.is_not_null()` (razonable para atribución). Juntas eliminaban el
mecanismo de absorción que ADR-14 declara obligatorio. *Los bugs de este dominio
no vienen de código equivocado sino de interacciones entre decisiones correctas.*

**#11** se detectó porque la caída de $E[T]$ era una función monótona de la
cobertura del núcleo. Un patrón demasiado limpio para ser un efecto real.

### Cinco errores de proceso

1. **Un test verde que probaba medio contrato.** `test_matrices_identity.py`
   pasaba mientras el guardarraíl abortaba siempre, porque probaba el
   verificador contra diccionarios inventados y nunca contra un `.npz` real.
   De ahí `test_npz_contract.py`.
2. **`synth.py` no reproducía el esquema real.** Su docstring prometía "el
   ESQUEMA REAL de StatsBomb" y llevaba desde v0.2 sin generar `player_id`.
   *Un generador sintético incompleto es un test que valida menos de lo que
   aparenta.*
3. **Heurísticas calibradas sobre un club.** La detección de umbral de torneo
   funcionaba en el América y falló en Cruz Azul. Lo mismo con
   `FRONTERAS_RIESGOSAS`, que reportaba "Solari → Ortiz" al procesar Cruz Azul.
4. **Nombre de display ≠ valor de datos.** `"Club América"` en el selector
   contra `"América"` en la columna `team`: el filtro devolvía vacío y la app
   decía "se necesitan dos etapas" con un dataset perfectamente válido.
5. **Trabajar semanas sin comitear.** El historial se quedó en v0.4.0 (34 tests)
   mientras el proyecto llegaba a 109. Los backups y las copias de versión que
   parecían redundantes con git eran, de hecho, las únicas copias de los estados
   intermedios. Se descubrió al preparar la publicación, comparando
   `git ls-files` (53) con lo que había en disco (90). No produjo pérdida porque
   nada se había borrado, pero la premisa "está en git" era falsa y se usó para
   justificar decisiones de limpieza.

---

## 9. Qué hacer cuando llegue el API

Detalle completo en **`12_API_STATSBOMB.md`**. Resumen:

1. **Fechas reales** → sustituyen las derivadas sin tocar nada aguas abajo.
2. **Preguntar por un dataset de entrenadores.** StatsBomb tiene `manager` en el
   endpoint de partidos. Si está disponible, `coach_eras.csv` deja de ser
   investigación manual.
3. **Los 18 equipos.** Beneficio principal: el prior pasa de "rivales del
   América" a "la liga", lo que elimina la amenaza 7.1. Beneficio secundario:
   con un $q$ mejor estimado se podría sostener una malla más fina.
4. **Recalcular λ\* y su lectura.** La frase "el América se parece a sus
   rivales" no sobrevive al cambio de prior.

---

## 10. Siguiente acción concreta

1. ~~Verificar el eje Y~~ — ✅ **hecho** (§7.6, bug #12). Reverificar con
   `13_verificar_ejes.py` tras cualquier cambio en `grid.py`.
2. Sensibilidad a `min_carry_length` (§7.7). **La única del plan original
   que sigue sin hacer.**
3. ~~Validación externa contra `shot_statsbomb_xg`~~ — ✅ **hecha**
   (`10_RESULTADOS.md` §26.3: correlación 0.861, AUC 0.795 contra 0.820).
   Queda `obv_*`.
3b. Chequeo predictivo espacial (ADR-50): simular desde $P$ y comparar la
   distribución de visitas. Probablemente rechace, y eso también se reporta.
4. Fechas reales del API.
5. Los 18 equipos.
6. Fase 8 (Wasserstein): la extensión con mejor retorno y la que más conecta
   con programación lineal.

---

## 11. Nomenclatura y trampas

- El club en la columna `team` es `"América"` **sin "Club"**. El nombre de
  display es otro campo (bug #4 de proceso).
- Los entrenadores en `coach_eras*.csv` van **sin acento**.
- Joaquín Moreno dirigió Cruz Azul en dos periodos no contiguos: se registran
  como `Joaquin Moreno I` y `II`, porque una era es un periodo **continuo**.
- `MIN_POSESIONES` debe ser el mismo en `generar_todo.sh` y
  `12_reporte_html.py`, o el reporte lista entrenadores sin artefactos.

---

## 12. Tres errores de proceso más, de la sesión del entregable

Van con los cinco de §8. Los tres son del mismo género: **nada falló, y el
resultado era plausible y equivocado.**

6. **Adivinar el formato en vez de leerlo.** El simulador decidía si un estado
   era absorbente con una expresión regular sobre su nombre. Los estados son
   **enteros**. Con eso, todos daban «absorbente», la posesión moría en el paso 0
   y el marcador salía en `0.00` con la cancha vacía. La respuesta llevaba
   versiones dentro del propio archivo: `mapa_zonas()` ya los decodificaba.

7. **Etiquetar por estadística cuando había un criterio físico.** Los estados
   absorbentes son enteros sin nombre. Se intentó ordenarlos por frecuencia
   (intercambió REMATE y BALÓN FUERA) y luego por gradiente en puntos
   porcentuales (llamó REMATE a la PÉRDIDA, porque la pérdida también crece
   hacia la portería rival partiendo de una base alta). Lo que funciona es una
   restricción del fútbol: **gol y remate son ~0 en campo propio**, la pérdida no.

8. **Un redondeo que parecía un error de la matriz.** Las 20 casillas sumaban
   101% porque cada una se redondeaba por separado. El reparto real sumaba
   1.000000. No era un bug de cálculo pero se leía como uno, y eso basta para
   minar la confianza en la figura. Se arregló con el método de los restos
   mayores.

**Y uno de proceso puro**: cada tarball de instalación se extraía en la raíz y
dejaba su carpeta. Un `git add -A` metió **diez copias** de
`12_reporte_html.py` al commit — 266 archivos, 86,178 inserciones. Es la misma
basura que ya se había limpiado una vez, recreada. Están en `.gitignore`.
