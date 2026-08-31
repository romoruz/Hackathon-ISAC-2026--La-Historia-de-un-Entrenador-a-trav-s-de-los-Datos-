# Actualizaciones de documentación v2 — corte 2026-08-25

> **HISTÓRICO — ya aplicado.** El contenido de este documento se integró en los
> documentos canónicos el 2026-08-26: las ADR-39 a ADR-48 en `06_DECISIONS.md`,
> los resultados del bloque defensivo y las tres retractaciones en
> `10_RESULTADOS.md` §16–§24, y §3.7bis/§3.8 en `04_DATA_CONTRACT.md`.
>
> **No cites de aquí.** Se conserva por una sola razón: contiene el
> *razonamiento* de por qué se retiró cada afirmación, y eso es material de
> defensa ante un jurado. Los documentos canónicos dicen *qué* se retiró; este
> dice *cómo se descubrió que estaba mal*.
>
> Recuperado el 2026-08-26 tras comprobar que no existía en el repositorio ni en
> el historial de git. Ver `docs/14_LIMPIEZA_REPO.md` §5.

---

> **Supersede `ACTUALIZACIONES_DOCS.md`.** Aquel documento contenía dos cifras
> que después se retiraron. Ver §0.

Orden de aplicación: **§0 primero** (retirar lo falso), luego §1–§3.

---

## 0. RETRACTACIONES — aplicar antes que nada

Tres afirmaciones que llegaron a `10_RESULTADOS.md` o a la versión anterior de
este documento y que **hoy no tienen soporte**. Se retiran, no se matizan.

### 0.1 🔴 RETIRADO — "Jardine presiona más al rival que Solari"

Publicado como +1.62 pp, q=0.0180, desde la estandarización por posesión.

**Por qué se retira.** Tres contrastes independientes lo desmienten:

| contraste | resultado |
|---|---|
| pendiente de decaimiento (kmin=2) | −0.0084 vs −0.0084, p = 0.984 |
| nivel en k≥3 | −0.0089, p = 0.480 |
| ponderación por acción | −0.57 pp (signo contrario) |

En cada índice de acción, Jardine y Solari presionan igual: las curvas se
cruzan seis veces y los IC se solapan en los doce puntos. La diferencia por
posesión venía de que el rival conserva más el balón bajo Jardine
(E[L] = 5.90 vs 5.00), no de que se presione distinto.

**La cifra de estandarización no era errónea**: medía un estimando distinto
(π ponderada por posesión) y sigue siendo correcta como tal. Lo que era
erróneo es la lectura futbolística: "presiona más" no se sostiene.

### 0.2 🔴 RETIRADO — "Anselmi sostiene la presión, p = 0.001"

Escrito a partir de la pendiente de π contra k ajustada **desde k=1**.

**Por qué se retira.** π(1) ≈ 0.15 y π(2) ≈ 0.26: la primera acción es la menos
presionada de todas, porque muchas posesiones rivales nacen de balón parado y
no hay presión que anotar. Ajustar una recta a una curva que sube y luego baja
convierte k=1 en un punto de palanca. Con kmin=2 la pendiente de Anselmi pasa
de +0.00475 a −0.00595 y la diferencia de p = 0.001 a **p = 0.077**.

**El hallazgo no desaparece, cambia de estimando.** Ver §1.2: lo que difiere no
es la tasa de decaimiento sino el NIVEL mantenido.

### 0.3 🔴 RETIRADO — "Jardine gana más balones al primer toque"

Exploratorio, +8.0 pp en posesiones de una acción en juego abierto, p = 0.0206.

**Por qué se retira.** No sobrevive al FDR de la familia D1-contrastes:
q = 0.0935 sobre 46 contrastes (ADR-48). Es exactamente el falso positivo
marginal que la corrección existe para atrapar.

---

## 1. `10_RESULTADOS.md` — sección nueva: el bloque de presión (D1)

### N.1 El instrumento: ¿la presión sirve?

Antes de comparar entrenadores hay que comprobar que la etiqueta de presión
mida algo con consecuencia. Si π no cambia el desenlace, todo el bloque
describe un comportamiento sin efecto.

Desenlace: *"¿es esta la última acción real de la posesión?"*. Captura todas
las formas de morir, incluidas las que el espacio de estados no ve —
`Dispossessed` (3,407 eventos) y `Clearance` (6,355) llevan `under_pressure`
= 1.000 **exacto**, es definicional, y ninguno está en `moving_types`.
Estandarizado por (zona × tipo de acción).

| era | efecto | p |
|---|---|---|
| Jardine | **+0.1225** | 0.0020 |
| Solari | **+0.1076** | 0.0020 |
| Reynoso | **+0.1159** | 0.0020 |
| Anselmi | **+0.1091** | 0.0020 |

Una acción rival presionada tiene **11 puntos porcentuales más** de
probabilidad de ser la última de su posesión, a igualdad de zona y de tipo de
acción. Consistente en cuatro eras de dos clubes.

Restringido a k≥3 el efecto es +0.115 y +0.122: **igual o mayor**. Eso
significa que la presión no mata desproporcionadamente pronto, y por tanto que
el contraste de nivel de §N.2 no está viciado por censura de supervivencia —
una limitación que se temía y que resultó despreciable.

**Caveat obligatorio**: es asociación, no efecto causal. StatsBomb anota
presión cuando un defensor se acerca, y se acerca más cuando el rival ya está
en problemas. El diseño no separa esa dirección.

### N.2 🟢 Anselmi sostiene el nivel de presión desde el tercer toque

| | π en k≥3 | acciones |
|---|---|---|
| Anselmi | **0.2509** | 14,402 |
| Reynoso | **0.2038** | 13,809 |

Diferencia **+4.71 pp**, p = 0.0016 (5,000 permutaciones de la etiqueta de era
entre partidos), **q = 0.0414** tras BH sobre 46 contrastes.

En k=1 y k=2 las dos eras son indistinguibles. La diferencia aparece desde el
tercer toque del rival y se mantiene hasta k=12.

**Cuatro fuentes de confusión descartadas por separado:**

| fuente | evidencia |
|---|---|
| rival enfrentado | soporte común 17/17, cobertura 100% |
| tipo de acción | cuotas casi idénticas (Pass .755/.753, Carry .228/.224); Anselmi presiona más en las TRES |
| origen de la posesión | Anselmi presiona más en las CUATRO fases |
| longitud de la posesión | Kitagawa: composición aporta 18% del total |

Y el efecto es mayor donde más pesa: cuando el rival **conduce**, sube a
**+6.4 pp** (0.463 vs 0.400); en pases es +1.8 pp.

**Caveats**: (a) el contraste condiciona a que la posesión llegara a k=3 —
atenuación medida como despreciable en §N.1, pero declarada; (b) q = 0.0414
contra α = 0.05 es supervivencia **sin holgura**: con dos o tres contrastes más
en la familia, caería.

### N.3 🟢 Dónde presiona Anselmi: dos zonas sobreviven

| zona | centro (m) | π Anselmi | π Reynoso | Δ | q |
|---|---|---|---|---|---|
| z23 | (60, 70) | 0.2509 | 0.2083 | **+0.0425** | 0.0414 |
| z13 | (36, 70) | 0.2578 | 0.2190 | **+0.0388** | 0.0414 |

**PENDIENTE DE VERIFICAR ANTES DE PUBLICAR**: las dos están en `iy=3`, que tras
el espejo corresponde a la banda por la que **ataca el rival**. Con `cx` = 60 y
36 en marco del club, son mediocampo y tercio propio. La frase tentativa es
*"presiona más en su carril izquierdo defensivo, en campo propio y medio"* —
pero debe confirmarse con `13_verificar_ejes.py` y contra la tabla de tercios
antes de escribirse. Es el tipo exacto de afirmación que el bug #12 produjo mal.

Por tercio (marco del club): propio +2.56 pp, medio +2.92 pp, rival +0.80 pp.
La presión extra está abajo y en el medio, **casi nada arriba**. Anselmi no es
un entrenador de presión alta.

Dato adicional de exposición: Anselmi concede el 28.6% de las acciones rivales
en su propio tercio contra el 33.7% de Reynoso. Cinco puntos menos de tiempo
del rival cerca de su área, **además** de presionar más cuando llega.

### N.4 🟡 Jardine y Solari: misma intensidad, distinta geografía

El contraste global no rechaza (nivel p = 0.480; pendiente p = 0.984), pero una
zona sí sobrevive al FDR:

| zona | centro (m) | π Jardine | π Solari | Δ | q |
|---|---|---|---|---|---|
| z32 | (84, 50) | 0.1405 | 0.1766 | **−0.0361** | 0.0414 |

**Signo negativo**: Jardine presiona **menos** ahí — centro del último tercio.
Por tercio: propio +0.44, medio **−1.73**, rival +1.29 pp.

La lectura: mismo volumen total de presión, repartido distinto. Jardine cede el
mediocampo central y aprieta algo más arriba. Es un hallazgo más fino que
"presiona más" y no admite esa frase.

### N.5 ⚪ La tasa agregada de presión no discrimina

América 0.2104, Cruz Azul 0.2125. Dos clubes independientes, 175 y 158
partidos, calendarios distintos, y coinciden en el tercer decimal.

Lecturas: (a) el proveedor anota la presión de forma consistente entre volcados,
lo que refuerza que la lectura de la bandera es correcta; (b) **la intensidad
total de presión es prácticamente una constante del formato**, y lo que separa
a los entrenadores es la geografía y la persistencia, no el volumen.

Es reportable como tal: *"la intensidad total de presión es indistinguible entre
clubes; lo que distingue a los entrenadores es dónde y hasta cuándo."*

### N.6 La paradoja de los dos estimandos, resuelta con una identidad

π ponderada por posesión y por acción daban signos opuestos para Jardine. No es
un bug: son dos estimandos, y la brecha es **exactamente**

$$\pi_{\text{acción}} - \pi_{\text{posesión}} = \frac{\operatorname{Cov}(L, m)}{\mathbb{E}[L]}$$

verificada numéricamente con error de 2×10⁻¹⁷. Cov(L,m) < 0 en las cuatro eras:
las posesiones rivales largas están menos presionadas. Bajo Jardine la
covarianza es más negativa (−0.0313 vs −0.0133), así que su π por acción cae más.

**Consecuencia editorial**: toda cifra de presión debe decir explícitamente
"por posesión" o "por acción". Sin eso, dos frases correctas del mismo reporte
se contradicen.

---

## 2. `README.md` — dos cambios

### 2.1 La línea de gol

> **Ninguna diferencia en la probabilidad de gol *estimada por la cadena*
> ($B_{\cdot,\text{GOAL}}$) es significativa.** Sobre la *tasa empírica* de gol
> por posesión sí aparece una, entre Jardine y Herrera (+0.73 pp, q=0.029), en
> una era de 17 partidos marcada por sobreajuste. Son cantidades distintas: la
> primera es una probabilidad de absorción del modelo, la segunda una
> proporción observada.

### 2.2 Añadir el bloque defensivo a los titulares

| hallazgo | magnitud | q |
|---|---|---|
| La presión acorta posesiones (4 eras, 2 clubes) | +11 pp | 0.0020 |
| Anselmi sostiene la presión desde el 3er toque | +4.71 pp | 0.0414 |
| Anselmi concede posesiones más cortas que Reynoso | −0.61 acciones | 0.0042 |
| Anselmi concede menos remates que Reynoso | −3.61 pp | 0.0042 |

---

## 3. `06_DECISIONS.md` — ADR 39 a 48

Las ADR 39–47 están redactadas en `ACTUALIZACIONES_DOCS.md` §3 y siguen
vigentes **salvo dos correcciones**:

- **ADR-44** (estandarización directa): añadir que **no** ajusta por localía,
  momento del partido ni por la endogeneidad de la asignación de entrenadores
  (un DT llega tras una mala racha, así que su era empieza condicionada al
  rendimiento previo). Los dos primeros se añaden como estratos al mismo
  estimador; el tercero no se corrige con ningún ajuste por observables y va a
  limitaciones.
- **ADR-46** (asimetría de credibilidad): sin cambios, pero recordar que el
  argumento es **direccional** — refuerza los nulos y NO los positivos.

### ADR-48 — Dos subfamilias dentro del bloque de presión

**D1-CONTRASTES.** Toda afirmación de que dos eras difieren en presión: π(z) por
zona, nivel en k≥3, pendiente de decaimiento, L=1 por fase. Nula: permutación de
la etiqueta de era **entre partidos**. Familia de descubrimiento, BH al 5%.
Tamaño: 46 contrastes.

**D1-CALIBRACIÓN.** La asociación entre presión y desenlace, por era. Nula:
permutación de la **marca de presión** dentro de estrato (zona × tipo). No
afirma que dos entrenadores difieran: verifica que el instrumento mida algo.
Se reporta con su p, fuera de BH conjunto con la anterior.

**Justificación de la separación.** Son asimétricas en riesgo. Un falso positivo
en la primera te hace defender que un entrenador difiere cuando no; la segunda
es una verificación del instrumento, con efectos de 11 pp en las cuatro eras y
nada marginal que corregir. Penalizar la potencia de los descubrimientos por
comprobar que la métrica no es ruido sería un castigo sin sentido.

**Exclusión declarada**: el estrato `balón parado` × L=1 tiene π = 0 en las dos
eras por construcción (una posesión de una acción nacida de saque o córner es un
despeje, con el balón parado y sin presión que anotar). Su p = 1.0 no es un
resultado sino un estrato sin información; incluirlo inflaría la familia y
bajaría la potencia de los demás.

**Declarado antes de correr la corrección.**

---

## 4. Registro de errores de proceso — tres entradas nuevas

Van con los cuatro que ya están en `02_STATE_OF_PLAY.md` §8. Los tres son
errores de **análisis**, no de código, y ninguno produjo una excepción.

### 4.1 Ajustar una recta a una curva no monótona

π(k) sube de k=1 a k=2 y luego baja. La pendiente ajustada desde k=1 no estima
el decaimiento: estima una mezcla de la subida inicial y la bajada posterior.
Produjo un p = 0.001 que con kmin=2 pasó a 0.077, y con él un titular que
estuvo tres días en la documentación.

**Se detectó mirando la figura**, no por ningún test. Ningún diagnóstico
automático avisa de que el estimando no corresponde a la pregunta.

### 4.2 Leer `phase` como estado actual del balón

Al ver π = 0 en el estrato `balón parado` × L=1 se concluyó que
`under_pressure` no se anota en balón parado, que π mediría en parte la
proporción de balón parado, y que había que recalcular todos los mapas
restringiendo a juego abierto.

**Falso.** `set_piece` tiene π = 0.19 y `restart` 0.17–0.19. Los ceros venían de
la **intersección** con L=1: una posesión de una sola acción nacida de saque o
córner es un despeje, sin presión que registrar.

`04_DATA_CONTRACT.md` §3.4 ya decía que `phase` etiqueta el ORIGEN de la
posesión, no el estado del balón ahora. Se citó dos veces en la misma sesión y
se leyó mal la tercera. **Es la trampa más costosa del formato, y sigue
atrapando después de estar documentada.**

### 4.3 Corregir dos cosas a la vez y atribuir el resultado a la equivocada

La calibración daba signo negativo. Se corrigieron simultáneamente el desenlace
(incluir muertes por acoso) y la estratificación (añadir `action_type`), y se
atribuyó la inversión de signo a lo primero.

**Era lo segundo.** Con el desenlace viejo pero estratificando por tipo de
acción, el signo ya sale positivo (+0.05 a +0.07). La exclusión de
`Dispossessed` atenuaba el efecto a la mitad, pero no lo invertía.

**Regla**: al corregir dos cosas a la vez, medir cada una por separado antes de
atribuir. El script conserva la columna del desenlace viejo justo para eso.

---

## 5. `04_DATA_CONTRACT.md` — fila nueva en §3

### 3.8 Las pérdidas por acoso no generan transición

`moving_types = ["Pass", "Carry", "Shot"]` deja fuera tres tipos que **sí
terminan posesiones**:

| tipo | n (Cruz Azul) | tasa de `under_pressure` |
|---|---|---|
| `Dispossessed` | 3,407 | **1.000** |
| `Clearance` | 6,355 | **1.000** |
| `Miscontrol` | 4,299 | 0.265 |
| `Foul Won` | 3,840 | 0.754 |

Las tasas de 1.000 son **definicionales**: perder el balón en el forcejeo *es*
estar presionado. Dos consecuencias:

1. **No pueden entrar al lado de la exposición** de π. Comparar presionadas
   contra no presionadas incluyéndolas sería circular por construcción.
2. **El desenlace de la posesión sí las recoge**, vía la absorción terminal
   hacia `LOSS`. La masa está contabilizada; lo que se pierde es la CAUSA.

Cualquier análisis que pregunte "¿este evento terminó la posesión?" debe usar
*"es la última acción real de la posesión"*, no *"su to_state es absorbente"*.
La segunda definición excluye justo las muertes por acoso.

Añadir también: **π difiere mucho por tipo de acción** — Pass 0.148, Carry
0.321. Un análisis de presión que no estratifique por `action_type` mide en
parte la mezcla de acciones del rival.

---

## 6. Pendientes que este documento NO cierra

1. **Verificar la orientación de z23/z13** antes de escribir §N.3.
2. **Localía y momento del partido** — el reto los pide explícitamente y no
   están. Se añaden como estratos al estimador de estandarización.
3. **Calibración predictiva de $B_{\cdot,\text{GOAL}}$** contra
   `shot_statsbomb_xg` (Brier / correlación por zona). `05_VALIDATION` §4.2 lo
   estima en una tarde.
4. **D2 (riesgos competitivos)** — Kaplan-Meier sobre la supervivencia de la
   posesión rival, Cox para el efecto del DT. Es el marco que trata la censura
   correctamente; hoy solo está declarada.
5. **El bloque defensivo no está en `12_reporte_html.py`.** Un análisis que no
   llega al entregable no existe para el jurado.
