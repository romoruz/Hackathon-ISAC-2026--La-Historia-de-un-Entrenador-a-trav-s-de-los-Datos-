# Actualizaciones de documentación — corte 2026-08-24

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

Tres archivos. Cada bloque indica dónde va y qué sustituye.

---

## 1. `README.md` — sustituir la línea de gol

**Antes:**

> **Ninguna diferencia en probabilidad de gol es significativa.** Duración de
> posesión y generación de peligro son dimensiones independientes del estilo.

**Después:**

> **Ninguna diferencia en la probabilidad de gol *estimada por la cadena*
> ($B_{\cdot,\text{GOAL}}$) es significativa.** Sobre la *tasa empírica* de gol
> por posesión sí aparece una, entre Jardine y Herrera (+0.73 pp, q=0.029),
> en una era de 17 partidos marcada por sobreajuste. Son cantidades distintas:
> la primera es una probabilidad de absorción del modelo, la segunda una
> proporción observada. Duración de posesión y generación de peligro siguen
> siendo dimensiones separables del estilo.

La distinción importa porque las dos frases parecen la misma y no lo son. Un
jurado que encuentre la tabla de tasas empíricas después de leer "ninguna
diferencia es significativa" concluirá que el reporte se contradice.

---

## 2. `10_RESULTADOS.md` — sección nueva

Insertar como sección propia, antes de las limitaciones.

### N. Estandarización por rival: el calendario no explica los efectos

**La amenaza.** Comparar eras dentro del mismo club controla plantel,
presupuesto, cantera, estadio y arbitraje, pero **no la composición del
calendario**. Jardine enfrentó a Cruz Azul diez veces —liguilla— y a los demás
rivales entre cuatro y seis. Herrera tuvo exactamente una vuelta completa: un
partido contra cada uno de los 17. Sus calendarios no son comparables.

**El método.** Estandarización directa sobre el soporte común de rivales
(§ADR-44). Con soporte discreto y positividad verificada, es la fórmula de
ajuste de Pearl con estratos saturados: *g-computation* no paramétrica, sin
modelo de asignación que especificar.

$$\hat\theta^{\,\text{std}}_e = \sum_{o \in \mathcal{O}_{12}} w_o \, \hat\theta_{e,o}$$

Positividad: **17/17 rivales en los seis pares del América**, cobertura 100%.
Bootstrap estratificado por `poss_uid` dentro de cada celda (era, rival), 2000
réplicas, intervalo básico. p-valor por inversión del mismo intervalo, de modo
que p e IC no pueden contradecirse.

**Control de multiplicidad (ADR-47).** 216 contrastes en total. Familia
confirmatoria = los 72 con cobertura ≥ 85%; los 144 restantes estiman el efecto
sobre el solapamiento, no el efecto global, y se reportan como exploratorios sin
q-valor. Benjamini–Hochberg al 5% sobre la familia confirmatoria: **34 pasaban
sin corregir, 29 sobreviven**. Los cinco que caen son los marginales.

#### N.1 Los titulares publicados sobreviven al ajuste

| titular | crudo | estandarizado | movimiento |
|---|---|---|---|
| Jardine sostiene más que Solari | +1.2650 | **+1.2496** | **−1.2%** |
| Anselmi sostiene más que Reynoso | −1.2950 | **−1.4164** | −9.4% |
| Anselmi genera más remates que Reynoso | −0.0405 | **−0.0444** | −9.7% |
| Ortiz sostiene más que Solari | +0.9174 | +0.8484 | −7.5% |
| Jardine sostiene más que Ortiz | +0.3475 | +0.4011 | +15.4% |

Ninguno se mueve más del 16%, ninguno cambia de signo, todos siguen
significativos tras FDR. **El diseño intra-club sí controlaba el calendario**, y
ahora eso se puede afirmar en vez de suponerlo. Que Jardine vs Solari se mueva
un 1.2% con diez partidos de liguilla de por medio es un resultado por sí solo.

#### N.2 Hallazgos defensivos (cadena conjugada)

🟢 Con soporte completo y q tras FDR:

| contraste | métrica | efecto | q |
|---|---|---|---|
| Anselmi vs Reynoso | concede posesiones más cortas | −0.61 acciones | 0.0042 |
| Anselmi vs Reynoso | concede menos remates | −3.61 pp | 0.0042 |
| Jardine vs Ortiz | concede posesiones más largas | +0.65 acciones | 0.0042 |
| Jardine vs Solari | concede posesiones más largas | +0.73 acciones | 0.0042 |
| Jardine vs Solari | presiona más al rival | +1.62 pp | 0.0180 |

🟡 Con etiqueta `[era corta]` (`params_per_obs` > 0.5, ADR-25):

| contraste | métrica | efecto | q |
|---|---|---|---|
| Jardine vs Herrera | concede posesiones más largas | +0.52 acciones | 0.0042 |
| Jardine vs Herrera | concede más remates | +2.77 pp | 0.0042 |
| Jardine vs Herrera | presiona más al rival | +2.14 pp | 0.0125 |
| Sánchez vs Anselmi | presiona más al rival | +2.48 pp | 0.0103 |
| Sánchez vs Reynoso | presiona más al rival | +3.88 pp | 0.0042 |

#### N.3 🔴 RETIRADO: "Anselmi presiona más que Reynoso"

Con IC crudo la diferencia parecía significativa (−1.22 pp). **Tras FDR no
sobrevive: p = 0.030, q = 0.0654.** No se reporta.

Y el dato va en contra de la intuición: **Sánchez presiona más que Anselmi**
(+2.48 pp, q=0.0103). Si la narrativa de Cruz Azul iba a ser "Anselmi es el
entrenador de la presión", los datos no la sostienen. Lo que sí sostienen es que
concede posesiones más cortas y menos remates: **eficacia defensiva sin
intensidad de presión superior.**

Es el hallazgo que más se benefició del control de multiplicidad, y conviene
contarlo así: la corrección no eliminó un resultado, corrigió una lectura.

#### N.4 ⚪ La paradoja de Jardine: presiona más y concede posesiones más largas

| contraste | presión | duración concedida |
|---|---|---|
| vs Solari | **+1.62 pp** (q=0.018) | **+0.73 acciones** (q=0.0042) |
| vs Herrera | **+2.14 pp** (q=0.013) | **+0.52 acciones** (q=0.0042) |

Presionar más debería **acortar** las posesiones rivales. Que ocurran las dos
cosas a la vez significa que presión y duración están desacopladas, y la
explicación natural es geográfica: presión en zonas donde no roba, y circulación
rival larga en el resto.

**No se interpreta hasta tener el mapa $\pi_e(z)$ (D1).** La tasa agregada de
presión es idéntica entre clubes (0.2104 América vs 0.2125 Cruz Azul), lo que
sugiere que la intensidad total es una constante del formato y que la señal
táctica es espacial. Declarar la tensión sin resolverla es preferible a
explicarla con una historia plausible.

#### N.5 Limitaciones de este análisis

1. **Cantidades empíricas, no del modelo.** Se estandarizan proporciones por
   posesión, no $E[T]$ ni $B_{\cdot,\text{GOAL}}$. Ajustar una matriz 80×84 por
   estrato con rivales de un solo partido es inviable. Sirven como control de
   confusión de las cantidades del modelo, no como sustituto.
2. **`min_actions` es asimétrico** (2 ofensiva, 1 defensiva; ADR-41). $E[T^{att}]$
   y $E[T^{def}]$ quedan truncados a distinto nivel y **no son comparables entre
   sí**. Solo era contra era dentro de la misma perspectiva.
3. **No se ajusta por localía ni por momento del partido.** El reto los pide
   explícitamente y se añaden como estratos adicionales al mismo estimador.
4. **La asignación de entrenadores es endógena.** Un DT llega después de una mala
   racha, así que su era empieza condicionada al rendimiento previo del club. Ni
   la estandarización ni ningún ajuste por observables lo corrige. Es la
   limitación causal que queda viva.
5. **El p-valor está acotado por la resolución del bootstrap.** Con 2000
   réplicas el mínimo alcanzable es 0.001, y 17 contrastes quedan empatados en
   q = 0.0042. No se puede ordenar entre ellos sin subir a 20000 réplicas.
6. **Cobertura desigual entre clubes.** 48 de los 72 contrastes confirmatorios
   son del América; de Cruz Azul solo entran Reynoso–Anselmi, Reynoso–Sánchez y
   Anselmi–Sánchez. Ver N.6.

#### N.6 Un hallazgo sobre la Liga MX, no sobre el método

144 de 216 contrastes quedan fuera de la familia confirmatoria por cobertura
insuficiente, y casi todos son de Cruz Azul. Con **once entrenadores en cuatro
años**, muchas eras no comparten calendario: Moreno I dirigió dos partidos y
solo coincide con otras eras en dos rivales.

No es un defecto del diseño. **El mallado y la comparabilidad los limita la era
más corta que quieras analizar, no el volumen total de datos.** Con 18 clubes en
vez de 2 el problema sería idéntico. Es una propiedad de la rotación de
entrenadores en el fútbol mexicano y conviene reportarla como resultado.

---

## 3. `06_DECISIONS.md` — ADRs nuevas

### ADR-39 — La defensa se modela como cadena conjugada

La fase sin balón no es un proceso propio: es el proceso del rival, modificado.
`transitions.parquet` ya contiene las posesiones de los 18 equipos, así que la
cadena conjugada sale del mismo artefacto con un filtro.

**Alternativa descartada**: construir un modelo defensivo independiente sobre
eventos `Pressure`, `Duel` e `Interception`. Contar acciones defensivas por zona
sin denominador de exposición mide dónde juega el rival, no dónde presionas tú
— el mismo error de longitud del bug #11.

### ADR-40 — El espejo es una permutación de índices, no una reflexión de coordenadas

StatsBomb normaliza al marco de ataque del ejecutante. Verificado empíricamente
sobre las filas de los rivales (2026-08-24): remates x̄ 103.97 (club) y 102.57
(rivales); saques de meta p10 = 7.0 en ambos lados.

La cadena conjugada **se estima en marco nativo**. El espejo se aplica al
presentar, con `StateSpace.mirror_zone`, que sobre malla uniforme es exactamente
$(i_x,i_y) \mapsto (n_x-1-i_x,\, n_y-1-i_y)$.

**Por qué sobre índices**: reflejar coordenadas antes de `zone_of` rompería
`coordinate_sanity` (daría corr ≈ −0.72, o sea `ok=False` en cada corrida sin
que nada estuviera mal), metería la transformación en la ruta numérica y
interactuaría con el `clip`. Sobre índices es exacto, sin punto flotante, y
aislado en una función pura testeable — la lección del bug #12.

Verificado: involución y consistencia con `zone_of` sobre 20,000 puntos y cinco
mallas; tres jugadores rivales de banda conocida (Mozo, Sanabria, González) caen
en la banda contraria tras el espejo, con 86.6%, 72.3% y 82.9%.

### ADR-41 — `min_actions = 1` en perspectiva defensiva

Una posesión de una acción que termina en absorción no recibe absorción terminal
y `min_actions = 2` la descarta. En la ofensiva eso ya estaba contabilizado
(§7.1: $P(T<2)=0$ por construcción). En la conjugada es peor: **una posesión
rival de una acción es el producto de una presión exitosa.**

Medido sobre 18,214 posesiones rivales del América: descarte global 9.06%, con
8.63% frente a Jardine y 10.49% frente a Solari. Rango de 1.86 pp, o 22%
relativo, y todo concentrado en $T=1$. Sesgo diferencial estimado sobre
$E[T^{def}]$: ~0.09 acciones, mismo orden que los efectos a detectar.

Al regenerar, se recuperaron 2,037 posesiones en el América (12.91%) y 1,981 en
Cruz Azul (13.20%) — más de lo predicho, porque el diagnóstico no aplicaba
`min_carry_length`.

**Consecuencia a declarar**: $E[T^{att}]$ y $E[T^{def}]$ no son comparables
entre sí.

### ADR-42 — `under_pressure` es una bandera, no un booleano

StatsBomb escribe `true` u omite la llave. Medido: **114,552 true / 0 false /
468,963 null** sobre 583,515 eventos. Un filtro por `is_not_null()` daría
π ≈ 1 en todas partes sin lanzar un solo error.

`fill_null(False)` obligatorio; `null` en las filas TERMINAL, que son
artificiales y no corresponden a ningún evento (ponerlas en `False` diluiría π
más en las eras con más absorciones terminales: sesgo diferencial otra vez).

Validación cruzada disponible y no usada aún: hay 53,006 eventos `Pressure`,
contra ~57k marcas `under_pressure` por lado. Dos lecturas independientes de la
misma cantidad.

### ADR-43 — `coach` y `coach_faced` son columnas distintas

`coach` = quién dirigía al ejecutante, null en rivales por diseño.
`coach_faced` = contra qué DT se jugó el partido, aplica a todas las filas.

Colapsarlas hacía que `select_units(unit='coach')` devolviera vacío sobre
transiciones defensivas, con un error que apuntaba al lugar equivocado.
`test_coach_faced.py` verifica que coinciden sobre las filas del club.

### ADR-44 — Estandarización directa por rival

Con soporte discreto y positividad, es la fórmula de ajuste de Pearl con
estratos saturados. **Alternativa descartada**: *propensity score matching*.
Existe para cuando no puedes estratificar (covariables continuas, celdas
vacías); aquí las celdas están llenas y PSM introduciría un modelo de asignación
que especificar y defender para aproximar un estimador que ya es exacto.

### ADR-45 — `perspective` entra al contrato de identidad del `.npz`

Sin ella, `phase1 --perspective defense` seguido de `phase2` (default attack)
pasa el guardarraíl: `unit` y `value` coinciden. Es el bug #7 con un campo más.

Verificación **estricta**: un `.npz` sin el campo se rechaza. Invalida todos los
artefactos anteriores y obliga a un `generar_todo.sh` completo. Es el precio
correcto: el parquet cambió con ADR-41, así que estaban obsoletos igualmente, y
04_DATA_CONTRACT §5.4 ya exige rerun al cambiar una definición.

### ADR-46 — Asimetría de credibilidad bajo sobreajuste

`params_per_obs` supera 0.5 en **seis de diez unidades ofensivas** a malla 5×4.
El criterio de ADR-25 se calibró sobre Ortiz (26 partidos) creyéndola la era más
corta; Herrera (17), Ferretti (16) y Moreno II (11) son menores.

No se reduce la malla: el barrido ya mostró que los efectos grandes sobreviven
entre 12 y 30 zonas. Se adopta etiqueta explícita (persistida en
`reports/manifiesto_unidades.json`) más tabla de sensibilidad a 4×3.

**El sesgo del sobreajuste va hacia encontrar diferencias**, así que un
resultado nulo desde una unidad sobreajustada es *más* robusto. El hallazgo
"Sánchez vs Ferretti sin efecto" viene precisamente de dos de esas unidades.

> **El argumento es DIRECCIONAL, no simétrico.** Refuerza los nulos y *debilita*
> los positivos que salgan de esas mismas unidades. Un titular significativo
> desde Herrera, Gutiérrez, Ferretti o Moreno II no puede apoyarse en este
> razonamiento: va con la etiqueta y nada más.

**Moreno II defensivo (`params_per_obs` = 1.016) queda excluido.** Más
parámetros que observaciones no es sobreajuste, es un modelo indeterminado.

### ADR-47 — Separación de familias para FDR

Los contrastes de estandarización por rival y los de $\pi_e(z)$ son **familias
separadas**. Responden preguntas distintas sobre objetos distintos —proporciones
empíricas agregadas por posesión frente a probabilidades binomiales por zona— y
se estiman con procedimientos independientes.

Los q-valores de la familia de estandarización quedan **fijados en la corrida
del 2026-08-24** y no se recalculan al añadir D1.

**Declarado antes de observar los resultados de D1.** La alternativa —familia
única recalculada al final— es igualmente válida, pero implicaría que ningún q
es citable hasta cerrar el análisis. Decidirlo después de ver los números sería
p-hacking sobre la estructura de la familia, aunque el razonamiento fuese
correcto.

Dentro de la familia de estandarización se separan además el conjunto
**confirmatorio** (cobertura ≥ 85%) del **exploratorio**, también declarado antes
de mirar los resultados. Motivo doble: interpretativo (distinto estimando) y de
potencia (BH reparte α entre el tamaño de la familia; incluir 144 contrastes de
baja cobertura habría subido el umbral de todos).

---

## 4. `02_STATE_OF_PLAY.md` — actualizar el conteo de bugs

El bug #13 **se evitó**, no se cometió: `under_pressure` es una bandera y un
filtro por `is_not_null()` habría dado π ≈ 1 en todas partes en silencio. Lo
detectó `14_diagnostico_defensa.py` **antes** de escribir una línea de D1.

Merece una fila propia en la tabla de bugs, marcada como *evitado*, porque el
patrón que lo detectó —diagnosticar el esquema antes de estimar— es replicable y
el resto de la tabla es de bugs encontrados después.
