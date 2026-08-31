# 04 — Contrato de datos

> Qué se espera del archivo de entrada, qué significa cada columna que se usa,
> y qué trampas tiene el formato StatsBomb. Leer esto ANTES de tocar
> `ingest.py` o `possessions.py`.

---

## 1. Archivo de trabajo actual

| | |
|---|---|
| Nombre | `eventos_completos_america.csv` |
| Formato | CSV plano (volcado del API de Hudl StatsBomb) |
| Cobertura | 175 partidos del Club América, Apertura 2021 – Clausura 2025 |
| Equipos presentes | 18 (América + 17 rivales) |
| Eventos totales | ~583,500 |
| Contiene | eventos de **ambos** equipos en cada partido |

**Consecuencia de diseño**: no hay una "liga" completa como referencia, pero sí
un pool de rivales. Y, más importante, hay varias eras de entrenador dentro del
mismo club — el diseño de comparación fuerte.

---

## 2. Columnas usadas

### Requeridas (el pipeline falla explícitamente si faltan)

| columna | tipo | uso |
|---|---|---|
| `id` | str | identificador de evento |
| `index` | int | **orden canónico dentro del partido** |
| `match_id` | int | agrupación por partido |
| `period` | int | 1, 2, (3, 4 en tiempos extra) |
| `minute`, `second` | int | tiempo de juego |
| `type` | str | tipo de evento (Pass, Carry, Shot, Pressure, ...) |
| `team` | str | equipo que **ejecuta** la acción |
| `possession` | int | id de la secuencia de posesión |
| `possession_team` | str | equipo **dueño** de la posesión |
| `play_pattern` | str | cómo empezó la posesión |
| `location` | list o str | coordenadas de inicio |

### Opcionales (se conservan si existen)

`duration`, `pass_end_location`, `carry_end_location`, `shot_end_location`,
`pass_outcome`, `shot_outcome`, `shot_statsbomb_xg`, `under_pressure`,
`counterpress`, `player`, `player_id`, `team_id`, `possession_team_id`,
`obv_total_net`, `obv_for_net`, `obv_against_net`.

`duration` se conserva explícitamente **para la Fase 6 semi-Markov**, aunque
hoy no se use.

### Columnas presentes pero NO usadas

El volcado tiene ~130 columnas. Las de portero, faltas, tarjetas, sustituciones,
50/50, bloqueos y el detalle de `tactics` no entran al modelo actual. Varias son
insumo directo de fases futuras:

- **Fase 5 (defensa)**: `type == "Pressure"`, `counterpress`,
  `interception_outcome`, `duel_type`, `duel_outcome`, `clearance_*`.
- **Fase 5 (360)**: el polígono `visible_area` y los *freeze frames del
  producto 360* **no están en este archivo**; hay que traerlos del API.

  > **CORRECCIÓN 2026-08-26.** La versión anterior de esta línea decía que
  > "los freeze frames" no estaban, sin más. Es cierto para StatsBomb 360 y
  > **falso para `shot_freeze_frame`**, que es una columna del evento de
  > remate y **sí está en el volcado**: la traen 2,454 de 2,486 remates del
  > América (98.7%). Los 32 que faltan son los 32 penales.
  >
  > Redactada así, la línea llevó a descartar toda una vía de análisis
  > durante semanas. Es un error de proceso del mismo género que los otros:
  > nada falla, la afirmación es plausible, y cuesta una capacidad que ya
  > se tenía. Ver `10_RESULTADOS.md` §26 y ADR-51.
- **Validación externa**: `shot_statsbomb_xg` permite contrastar el
  $B_{\cdot,\text{GOAL}}$ estimado contra un xG independiente.
- **Comparación de referencia**: `obv_*` (On-Ball Value) es la métrica
  propietaria de StatsBomb. Comparar el xT propio contra OBV es una validación
  de convergencia barata.

---

## 3. Trampas del formato

### 3.1 `location` viene en dos formatos

- Lista nativa `[60.0, 40.0]` en parquet/JSON.
- String serializado `"[60.0, 40.0]"` en CSV.

`ingest.parse_location` maneja ambos. Los remates traen un tercer componente
(altura) que se ignora.

### 3.2 Coordenadas fuera del campo

StatsBomb reporta `x = 120.1` en remates y `y = -0.2` en centros desde la línea
de fondo. `StateSpace.zone_of` recorta al rango válido. **No es un error de los
datos**: es cómo se registra el balón cruzando la línea.

### 3.3 Orientación

StatsBomb normaliza al marco de ataque del equipo que ejecuta: el equipo con
balón siempre ataca hacia $x = 120$. Como el pipeline solo toma acciones del
`possession_team`, no hace falta voltear nada.

**Verificado en cada corrida** por `coordinate_sanity`: la tasa de gol debe
crecer con el índice de columna de zona. En los datos reales: corr = 0.72.

Si una extracción distinta no estuviera normalizada, todos los mapas saldrían
espejeados y el diagnóstico lo detectaría.

### 3.4 `play_pattern` etiqueta la POSESIÓN, no el evento

**La trampa más costosa.** Una posesión que empezó con saque de banda queda
marcada `From Throw In` en sus 20 acciones siguientes, aunque termine en gol
cinco minutos después.

Distribución real en el archivo:

| play_pattern | eventos | % |
|---|---|---|
| Regular Play | 315,373 | 54.0 |
| From Throw In | 107,196 | 18.4 |
| From Free Kick | 68,064 | 11.7 |
| From Goal Kick | 40,727 | 7.0 |
| From Corner | 17,233 | 3.0 |
| From Kick Off | 15,723 | 2.7 |
| From Keeper | 14,955 | 2.6 |
| From Counter | 3,544 | 0.6 |
| Other | 700 | 0.1 |

Agrupar los saques de banda como "balón parado" habría etiquetado mal el 18% de
los datos. De ahí la fase `restart`, separada de `set_piece`.

**`phase` describe el ORIGEN de la posesión, no el estado del balón ahora.**
Debe decirse así en el reporte.

Nota adicional: `From Counter` es muy restrictivo (0.6%), lo que deja la fase
`transition` con poca masa. Si el contraataque va a ser parte de la narrativa,
hace falta una definición operativa propia (roadmap §5.1).

### 3.5 `Carry` es abundante

131,237 acarreos contra 162,490 pases: el 44% de las acciones con balón. La
secuencia típica es pase–acarreo–pase–acarreo. La mayoría son reajustes de
control de 1–3 metros, no decisiones tácticas, y generan auto-transiciones
$i \to i$ que inflan $N$.

`min_carry_length = 5.0` los filtra. Efecto observado: las acciones por posesión
bajaron de ~9.0 a ~6.9, y las transiciones totales de 304,541 a 222,251.

**El umbral es una decisión, no un hecho.** Debe reportarse sensibilidad.

### 3.6 Inferencia de esquema en CSV

Decenas de columnas solo tienen valor en eventos raros. Con el
`infer_schema_length = 100` por defecto de polars quedan tipadas como `Null` y
**los filtros sobre ellas devuelven vacío en silencio** — el pipeline reportaría
cero goles sin ningún error.

`ingest._scan_csv` fuerza `infer_schema_length=None`. Cuesta una pasada extra
una sola vez; después se trabaja sobre parquet.

### 3.7 No hay columna de entrenador ni de fecha

El volcado no trae ni `coach` ni `match_date`. Sin fecha no hay mapeo de eras, y
`match_id` no garantiza orden temporal entre competencias. Ver
`02_STATE_OF_PLAY.md` §4.

### 3.8 — `under_pressure` es una BANDERA, no un booleano

StatsBomb escribe `true` u **omite la llave**. No existe `false`. Medido sobre el
volcado del América:

| valor | eventos |
|---|---|
| `true` | 114,552 |
| `false` | **0** |
| `null` | 468,963 |

Un filtro por `is_not_null()` daría **π ≈ 1 en todas partes, sin lanzar un solo
error**. Es el bug #13 y se evitó porque `14_diagnostico_defensa.py` inspeccionó
el esquema antes de escribir una línea de estimación (ADR-42).

- `fill_null(False)` **obligatorio** al leerla.
- **`null` en las filas TERMINAL**: son artificiales y no corresponden a ningún
  evento. Ponerlas en `False` diluiría π más en las eras con más absorciones
  terminales — sesgo diferencial otra vez.

Validación cruzada disponible y no usada: hay 53,006 eventos `Pressure` contra
~57k marcas `under_pressure` por lado. Dos lecturas independientes de lo mismo.

---

### 3.9 Las pérdidas por acoso NO generan transición

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

1. **No pueden entrar al lado de la exposición** de π. Comparar acciones
   presionadas contra no presionadas incluyéndolas sería circular por
   construcción.
2. **El desenlace de la posesión sí las recoge**, vía la absorción terminal hacia
   `LOSS`. La masa está contabilizada; lo que se pierde es la CAUSA.

> Cualquier análisis que pregunte *"¿este evento terminó la posesión?"* debe usar
> **"es la última acción real de la posesión"**, no *"su `to_state` es
> absorbente"*. La segunda definición excluye justo las muertes por acoso.

**Y π difiere mucho por tipo de acción**: Pass 0.148, Carry 0.321. Un análisis de
presión que no estratifique por `action_type` mide en parte la mezcla de acciones
del rival, no la presión.

---


---

## 4. Definiciones operativas

Estas son las definiciones del proyecto. Van al reporte palabra por palabra.

> **Posesión**: grupo `(match_id, possession)` de StatsBomb, restringido a las
> acciones ejecutadas por `possession_team`. Se descartan las posesiones con
> menos de `min_actions` acciones.
>
> **Acción**: evento cuyo `type` está en `moving_types` (Pass, Carry, Shot).
> Ball Receipt, Pressure, Duel y Ball Recovery **no** generan transición.
>
> **Transición**: cada acción aporta UNA transición
> (zona\_inicio, fase) → destino, donde el destino es (zona\_fin, fase) si la
> acción mantiene la posesión, o un estado absorbente si la termina.
>
> **Absorción terminal**: si la última acción de la posesión deja el balón en un
> estado transitorio, se añade una transición extra hacia `LOSS`.

### Justificación del diseño "una transición por acción"

Se usa (inicio → fin) de cada acción en lugar de encadenar
(fin$_{k-1}$ → inicio$_k$). Es el criterio de Rudd (2011) y Singh (2018), y
evita que el arrastre del control —recepción, toque previo, ajuste del cuerpo—
contamine las transiciones con movimiento que el modelo no explica.

### Por qué la absorción terminal es obligatoria

Sin ella, las posesiones que simplemente terminan (falta, cambio, fin de
periodo, robo sin evento registrado del equipo) nunca absorberían. Las filas de
$P$ no reflejarían las tasas reales de pérdida y $N = (I-Q)^{-1}$ se inflaría
hacia arriba de forma sistemática.

---

## 5. Reglas para modificar el contrato

1. **Toda columna nueva usada va a `REQUIRED` u `OPTIONAL` en `ingest.py`**, para
   que la validación falle temprano y con mensaje claro.
2. **Todo cambio en las definiciones operativas se documenta aquí**, no solo en
   el código.
3. **Ningún parámetro de preprocesamiento se hardcodea**: va a
   `config/default.yaml` con comentario que explique la decisión.
4. Al cambiar una definición, **rerun completo desde `phase0`**. Los artefactos
   intermedios no se invalidan solos.
