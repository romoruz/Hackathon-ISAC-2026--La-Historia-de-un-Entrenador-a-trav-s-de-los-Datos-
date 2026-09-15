# 16 — Migración al API de StatsBomb y decisiones de alcance

> **BORRADOR — pendiente de confirmación humana.** Fecha: 2026-09-14.
> Cada sección marcada `DECISIÓN PENDIENTE` requiere que Rodrigo confirme o
> corrija antes de correr nada. Una vez confirmadas, este documento se
> convierte en ADRs en `06_DECISIONS.md` y esta versión pasa a histórico.

---

## 1. Qué cambió el 2026-09-14

Se obtuvo acceso al API de Hudl StatsBomb (credenciales ISAC). Lo disponible:

| | |
|---|---|
| Competencia | Liga MX (`competition_id = 73`), 6 temporadas |
| Temporadas | 108, 235, 281, 317, 318 (completas) + 351 (en curso) |
| Partidos | 1,854 · **1,767 con eventos disponibles** |
| Equipos | 19 (18 por temporada; Atlante entra en 351 por Mazatlán) |
| Entrenadores | 103 distintos, **147 eras**, 58 analizables con ≥25 partidos |
| 360 | `match_status_360 = available` en ~1,755 partidos |
| Columnas de evento | 178 tras aplanar (el volcado viejo tenía 134) |

Lo que **no** hay: Copa, Leagues Cup ni Concachampions. Eso resuelve la
pregunta 2 de `12_API_STATSBOMB.md` §2: no hay `match_id` de otras
competencias contaminando los bloques.

Campos confirmados presentes: `index`, `possession`, `possession_team`,
`play_pattern`, `location`, `duration`, `shot_statsbomb_xg`,
`shot_freeze_frame`, `under_pressure`, `counterpress`, `player_id`,
`obv_total_net`, `obv_for_net`. **El contrato de datos se cumple entero.**

---

## 2. El hallazgo que obliga a recalcular

`data/coach_eras.csv` (investigación manual sobre Wikipedia) tiene **dos
errores** en el Club América, confirmados contra prensa del momento y contra
el propio API:

| frontera | el CSV decía | lo correcto | error |
|---|---|---|---|
| Herrera → Solari | 2021-12-05 | **≈ dic 2020** | ~1 año |
| Solari → Ortiz | 2022-10-09 | **2022-03-03** | ~7 meses |

Evidencia: Solari fue cesado el 2 de marzo de 2022 tras la jornada 8 del
Clausura 2022; Ortiz entró de interino el día 3. Wikipedia registra a Herrera
en 2017–2020, a Gilberto Adame con 1 partido en 2021, y a Solari en 2021–2022
con 52 partidos. La aritmética cierra: los 52 de Solari son Guard1anes 2021
(anterior a la ventana) + Concachampions + los 27 de Liga MX que el API ve.
Ortiz da **55 partidos en Wikipedia y 55 en el API**.

### Consecuencias

1. **Miguel Herrera no existe** en la ventana del API. Todo resultado con su
   nombre describe en realidad a Solari.
2. La "era Solari" del análisis previo era Herrera(mal etiquetado) + Solari +
   7 meses de Ortiz.
3. Cambian las eras: Solari 39 → **27**, Ortiz 26 → **55**, Jardine → **129**.

### Resultados que quedan retirados hasta recálculo

| titular | estado |
|---|---|
| Jardine sostiene más que Solari, +22.4% [+18.6, +26.4] | 🔴 RETIRADO |
| Jardine genera menos remates que Ortiz, −12.5% [−23.9, −1.5] | 🔴 RETIRADO |
| Control de plantel: 9 de 17 jugadores Jardine↔Ortiz | 🔴 RETIRADO |
| Anselmi vs Reynoso (Cruz Azul) | 🟡 revisar eras primero |
| Sánchez vs Ferretti (Cruz Azul) | 🟡 revisar eras primero |

**No se publica el repositorio hasta que estos estén recalculados o marcados
como retirados en el README.**

### Por qué el contraste planeado no lo habría detectado

`12_API_STATSBOMB.md` §3 predecía "diferencias de 2–3 partidos". Falló porque
comparaba **fechas derivadas contra fechas reales**, dando el CSV de eras por
bueno. El error vivía en la pieza que no se estaba contrastando. Es el bug #14
y es de una clase nueva: los otros trece eran de código, este es de un dato de
entrada investigado a mano, y ningún test podía atraparlo porque el pipeline
hacía exactamente lo que se le pidió.

---

## 3. Protocolo de eras: triangulación

Ni el API solo ni la investigación manual sola. El procedimiento:

1. `scripts/01_construir_eras.py` construye las eras desde `manager` del API.
2. El script marca banderas: `PRIMERA_DE_VENTANA`, `CORTA`, `NO_CONTIGUA`,
   `MULTI_MANAGER`, `FUSIONADA`.
3. El humano verifica **por conteo de partidos**, no por fecha. La aritmética
   es más difícil de falsear por accidente que una fecha, y fue lo que cerró
   los casos Ortiz y Solari.
4. Las correcciones van a `data/eras_correcciones.csv`, que se aplica **a
   nivel de partido** antes de agrupar en rachas. Así nunca hay solapamientos.

**Estado de la evidencia**: sobre las 4 fronteras del América verificadas
contra fuentes externas, el API acertó **4 de 4**. No se ha encontrado ningún
error del API. La bandera `PRIMERA_DE_VENTANA` es precautoria, no un indicio.

> `DECISIÓN PENDIENTE 1` — **Verificación: censo o muestreo.**
> Hay 10 eras analizables marcadas `PRIMERA_DE_VENTANA` (una ya verificada:
> América). Recomendación: verificar **3 de las 9 restantes** elegidas por
> tamaño (Atlas/Cocca, Cruz Azul/Reynoso, Monterrey/Aguirre). Si las tres
> cuadran, aceptar las seis restantes y declarar en el reporte que fue
> muestreo. Si alguna falla, censo completo.
> **Coste**: 15 min (muestreo) contra 1 h (censo).

---

## 4. Decisiones de alcance pendientes

> `DECISIÓN PENDIENTE 2` — **Temporada 351 (2026/2027).**
> Está en curso: 153 partidos programados, 66 con eventos. Además Atlante
> solo aparece ahí, sustituyendo a Mazatlán.
> **Recomendación: EXCLUIR.** Una era que sigue abierta no tiene `end_date`
> real, y la cobertura crece entre corridas, lo que rompe la reproducibilidad
> exacta. Se puede mencionar como "datos disponibles hasta la fecha X".

> `DECISIÓN PENDIENTE 3` — **Liguilla, repechaje y play-in.**
> Son ~25 partidos por temporada con contexto distinto: eliminación directa,
> ida y vuelta, se juega al resultado. Y solo los buenos llegan, así que
> sobrerrepresentan a los técnicos exitosos: es **selección sobre el
> desenlace**, el mismo defecto que hace inválido un muestreo top4/bottom4.
> **Recomendación: EXCLUIR del ajuste, reportar como sensibilidad.**
> Nota: la etiqueta `competition_stage` es inconsistente (la temporada 235
> dice `Regular Season` donde las otras dicen `Apertura`), así que el torneo
> se deriva de la **fecha**: julio–diciembre = Apertura, enero–junio =
> Clausura. Robusto y en una línea.

> `DECISIÓN PENDIENTE 4` — **Umbral de era analizable.**
> Hoy se usa 25 partidos, elegido a ojo porque Ortiz con 26 daba
> `params_per_obs` = 0.502 en 6×4 (ADR-25). **Hay que calcularlo con el
> criterio, no heredarlo.** Depende de la malla elegida en la decisión 5 y
> del `frac_below_min` sobre la era más chica que entre al análisis.
> **Acción**: barrido de `params_per_obs` y `frac_below_min` contra número
> de partidos, y fijar el umbral donde cruce el criterio.

> `DECISIÓN PENDIENTE 5` — **Resolución de la malla.**
> El barrido previo fijó 5×4 porque 6×4 daba `params_per_obs` = 0.502 sobre
> la era más chica. Pero `12_API_STATSBOMB.md` §5.3 anota que ese criterio
> mide el sobreajuste del **EMV crudo**, mientras el proyecto usa el
> estimador **encogido**. Con un prior de liga mucho mejor estimado se podría
> encoger más y sostener 6×4.
> **Recomendación: repetir el barrido midiendo el error del estimador
> encogido**, no contando parámetros. Es la mejora que el propio documento
> anticipaba y ahora es ejecutable.

---

## 5. El cambio estructural: la unidad de análisis

### Antes
- Espacio de estados derivado del **club**.
- Unidad = `(club, era)`.
- Prior `q` = los 17 rivales que el América enfrentó.
- Diseño fuerte = comparar eras **dentro** del mismo club (ADR-16).

### Después
- Espacio de estados derivado de la **liga**. Sin esto no se pueden comparar
  matrices entre clubes: no viven en el mismo espacio.
- Unidad = `(coach_id, club, era)`. `coach_id` es **global en el API**, así
  que el mismo técnico es rastreable entre clubes sin emparejar nombres.
- Prior `q` = la liga. Con 18 equipos sí es una muestra de la liga, así que
  **muere la amenaza 4.3 de `05_VALIDATION.md`**.
- λ\* cambia de significado. La frase "el América se parece a sus rivales"
  **no sobrevive** y hay que reescribirla.

### El beneficio colateral que importa

Hoy Jardine es el 53% de las transiciones del América: "el América histórico"
*es* Jardine, y la línea base contiene al foco. Con prior de liga, cualquier
entrenador es ~3% de su propio prior. **La fuga de prior (ADR-06) casi
desaparece.**

---

## 6. El enfoque nuevo: ¿la firma del entrenador viaja?

El diseño actual controla institución, presupuesto y calendario, pero **no
controla plantel** (§7.7, la amenaza viva). El diseño nuevo invierte el
control: varios planteles, varios presupuestos, un solo entrenador.

Candidatos con carrera múltiple en la ventana:

| entrenador | clubes |
|---|---|
| Larcamón | Puebla 60 · León 39 · Cruz Azul 37 · Necaxa 19 |
| Jardine | América 129 · Atlético San Luis 54 |
| Cristante | Juárez 32 · Toluca 18 · Querétaro 13 · Puebla 12 |
| Ambriz | Toluca 73 · Santos 28 · León 15 |
| Ortiz | América 55 · Monterrey 44 |
| Vucetich | Monterrey 54 · Mazatlán 34 |
| Fentanes | Necaxa 43 · Santos 43 |
| Siboldi | Tigres 48 · Mazatlán 19 · Tijuana 12 |

### Contraste 1 — la firma que viaja
¿Es $TV$(Larcamón en Puebla, Larcamón en León) menor que la $TV$ entre dos
eras cualesquiera? **Nula**: la distribución empírica de TV sobre los ~1,700
pares de eras posibles. Es ADR-30 aplicado, no matemática nueva.

### Contraste 2 — diferencias en diferencias
Cuánto se desvía cada técnico de la línea base de **su** club, comparado entre
clubes. `12_API_STATSBOMB.md` §6 lo describe y lista dos problemas; ahora los
dos son resolubles: se excluye al foco de su propia base, y la nula existe.

### Lo que este diseño NO resuelve
Los entrenadores **eligen** club y pueden adaptarse al plantel que reciben.
No es identificación causal. Pero con Larcamón en cuatro clubes y Cristante en
cuatro, la explicación por selección se vuelve forzada. Hay que decirlo así:
*"la firma persiste a través de cuatro planteles distintos"*, nunca
*"el entrenador causa la firma"*.

---

## 7. Lo que NO cambia

- Toda la maquinaria: cadena absorbente, $N=(I-Q)^{-1}$, encogimiento,
  LRT/$G^2$, bootstrap por `poss_uid`, FDR, nulas empíricas.
- El rechazo de Markov de orden 1 por sobredispersión (§7.1) y ADR-21.
- λ débilmente identificado: significancia con λ\*, magnitudes con λ=0
  (ADR-22).
- Ninguna distancia sin su nula (ADR-30).
- `detect_regime_changes` sigue descartado como validador de fronteras.
- Los 135 tests. **El repositorio NO se rehace desde cero**: el registro
  acumulado de 51 ADRs y 14 bugs es lo que hace defendible el proyecto.

---

## 8. Qué se versiona a partir de ahora

| ruta | por qué |
|---|---|
| `data/eras_api/` | eras derivadas del API, reproducibles pero baratas |
| `data/eras_correcciones.csv` | **investigación humana irrepetible** |
| `data/alias_entrenadores.csv` | **investigación humana irrepetible** |
| `data/raw_api/indice_partidos.csv` | metadatos, no eventos |

| ruta | NUNCA |
|---|---|
| `data/raw_api/events/`, `lineups/`, `frames/` | datos licenciados |
| `data/api/*.csv`, `*.parquet` | derivados de datos licenciados |
| `.venv-sb/`, `.env` | entorno y credenciales |

---

## 9. Reglas de trabajo nuevas

1. **`src/dtdecoder/` jamás importa `statsbombpy`.** El API vive en
   `scripts/00_fetch_statsbomb.py` y nada más. El puente son archivos en
   disco.
2. **Dos entornos**: `.venv` para el pipeline y los tests, `.venv-sb` para el
   API. `statsbombpy` arrastra pandas y numpy; meterlos en el entorno del
   pipeline es invitar a deriva numérica (§8 de `08_REPRODUCIBILITY.md`).
3. **Una respuesta vacía del API no es un dato: es un fallo.** `statsbombpy`
   no lanza excepción con un 401, imprime y devuelve vacío. El descargador
   aborta ante respuestas vacías en vez de cachearlas. Fue bug #15, cometido
   durante esta misma migración.
4. **Las credenciales no van en un `.py`.** `read -rs` y variables de entorno.
