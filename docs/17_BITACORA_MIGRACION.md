# 17 — Bitácora de la migración al API (sesión 2026-09-14)

> Registro de una sola sesión de trabajo. Sirve para **retomar en un chat
> nuevo sin repetir nada**. Se lee junto con `16_MIGRACION_API.md`, que
> contiene las decisiones; esto contiene el estado, lo verificado y los
> errores cometidos.

---

## 0. Cómo retomar

Mensaje inicial sugerido para un asistente nuevo:

> Retomo `dt-decoder` tras migrar al API de StatsBomb. He leído
> `docs/16_MIGRACION_API.md` y `docs/17_BITACORA_MIGRACION.md`.
> Estado: descarga completa (1,767 partidos), adaptador validado (H1 pasó),
> eras construidas para 19 clubes (134 eras, 53 analizables), malla 5×4 y
> umbral 25 confirmados por aritmética. Voy por H2: adaptar los 19 clubes y
> correr `phase0` sobre la liga completa.

---

## 1. Estado al cierre de la sesión

### Infraestructura

| pieza | estado |
|---|---|
| Credenciales ISAC | ✅ funcionan (9 competencias) |
| `.venv-sb` (entorno del API) | ✅ statsbombpy 1.22, pandas<3 |
| `scripts/00_fetch_statsbomb.py` | ✅ descarga idempotente y reanudable |
| `scripts/01_construir_eras.py` | ✅ eras desde `manager`, con banderas |
| `scripts/02_adaptar_eventos.py` | ✅ JSON crudo → esquema del volcado |
| `data/raw_api/` | ✅ 1,767 eventos + 1,765 lineups, ~1.2 GB |
| 360 (`frames/`) | ⬜ NO descargado (varios GB, no hace falta aún) |

**Fallos de descarga**: 3 de 3,524 llamadas, todos "respuesta vacía",
resueltos al reintentar. Cero pendientes.

### Datos

- 6 temporadas de Liga MX (`competition_id = 73`): 108, 235, 281, 317, 318, 351.
- 1,854 partidos, **1,767 con eventos**.
- Sin Copa, Leagues Cup ni Concachampions.
- 19 equipos (Atlante solo en 351, sustituyendo a Mazatlán).
- 178 columnas tras aplanar, contra 134 del volcado viejo. Las requeridas
  están todas; `obv_*` y `shot_freeze_frame` también.
- ~690 transiciones por partido del club focal (medido, no estimado).

### Eras

Con alcance **liguilla fuera, temporada 351 fuera**, umbral 25 partidos:

**134 eras, 53 analizables** en 18 clubes.

América: Solari 27 · Ortiz 55 · Jardine 129.
Cruz Azul: Reynoso 34 · Anselmi 37 · Larcamón 33.

Artefactos: `data/eras_api/` (rico, con banderas),
`data/eras_compat/` (3 columnas para `eras.load_eras`),
`data/alias_entrenadores.csv` (31 etiquetas rellenadas a mano).

---

## 2. Hitos: hecho y pendiente

| # | hito | estado |
|---|---|---|
| — | Descarga completa | ✅ |
| — | Eras de 19 clubes | ✅ |
| — | Decisiones de alcance (2, 3, 4, 5) | ✅ |
| **H1** | **Regresión del adaptador sobre 175 partidos** | ✅ **PASA** |
| H2 | Adaptar 19 clubes a parquet, `phase0` sobre la liga | ⬜ |
| H3 | Prior de liga, λ\* recalculado y reinterpretado | ⬜ |
| H4 | Recalcular titulares; barrido de pares con FDR | ⬜ |
| H5 | La firma que viaja (intra-entrenador entre clubes) | ⬜ |
| H6 | τ² con 53 unidades; descomponer entrenador vs club | ⬜ |
| H7 | Reporte HTML con entrada por entrenador | ⬜ |
| H8 | Limpieza (agente + doc 14), CI, publicación | ⬜ |

---

## 3. H1 — el veredicto, con su evidencia

Mismos 175 `match_id`, dos fuentes independientes:

| | volcado | API | dif |
|---|---|---|---|
| eventos | 583,515 | 583,547 | +32 |
| `n_transitions` | 224,288 | 224,130 | −158 (0.07%) |
| `n_possessions` | 34,319 | 33,874 | −445 (1.3%) |
| `coordinate_sanity` | 0.7204 | 0.7204 | 0.0000 |

Sobre los **583,512 eventos compartidos**: `match_id`, `type`, `team` e
`index` coinciden en **el 100%**.

La diferencia está sola en `possession`. En el partido 3919008, con los
3,463 eventos idénticos e `index` de 1 a 3,463 sin huecos, los cortes de
posesión son **210 idénticos de 244**, y los que no coinciden están
**desplazados uno o dos eventos** (405→402, 476→478, 610→611, 830→831).

**Conclusión**: StatsBomb reprocesó, añadió 32 acarreos y movió los límites
de posesión. El adaptador es correcto.

> **Consecuencia metodológica que va al reporte.** La unidad de remuestreo de
> todo el bootstrap es `poss_uid`, y esa unidad **la define el proveedor y la
> revisa con el tiempo**. El efecto medido es del 1% y no es diferencial
> entre eras, así que no invalida nada; pero declararlo refuerza por qué los
> IC se validan por cobertura empírica en vez de darse por buenos.

---

## 4. El hallazgo principal: `coach_eras.csv` estaba mal

Dos errores en el América, confirmados contra prensa y Wikipedia:

| frontera | el CSV decía | correcto | error |
|---|---|---|---|
| Herrera → Solari | 2021-12-05 | ≈ dic **2020** | ~1 año |
| Solari → Ortiz | 2022-10-09 | **2022-03-03** | ~7 meses |

Miguel Herrera **no existe** en la ventana del API: su segunda etapa terminó
en 2020. Todo resultado con su nombre describe en realidad a Solari.

**Aritmética que lo cierra**: Wikipedia da Ortiz 55 partidos y el API da 55.
Solari tiene 52 en Wikipedia = Guard1anes 2021 (fuera de ventana) +
Concachampions + los 27 de Liga MX que el API ve.

### Titulares retirados hasta recálculo

- Jardine sostiene más que Solari, +22.4% → 🔴
- Jardine genera menos remates que Ortiz, −12.5% → 🔴
- Control de plantel, 9 de 17 jugadores Jardine↔Ortiz → 🔴
- Sánchez vs Ferretti (el par **sin efecto**) → 🔴 **imposible de recalcular**:
  con umbral 25, esas eras tienen 14 y 13 partidos.

> **Pendiente con prioridad**: el par Sánchez–Ferretti era el ejemplo de que
> el método distingue un cambio **sin** efecto, y el README lo declara como
> lo que hace creíble al método. Hay que **sustituirlo por otro par nulo
> salido del barrido sistemático con FDR** sobre las 53 eras (H4). Un par
> nulo elegido de un barrido es más defendible que uno ya conocido.

---

## 5. Verificación de eras: protocolo y resultado

**Regla**: verificar por **conteo de partidos**, no por fecha. La aritmética
es más difícil de falsear por accidente.

**Muestreo, no censo** (decisión tomada y documentada): de las 10 eras
analizables marcadas `PRIMERA_DE_VENTANA`, se verificaron 4 contra fuentes
externas.

| club / entrenador | inicio | fin |
|---|---|---|
| América / Solari | ✅ | ✅ |
| Atlas / Cocca | ✅ | ~1–2 partidos |
| Cruz Azul / Reynoso | ✅ | ✅ exacto |
| Monterrey / Aguirre | ✅ | **1 partido de más** |

**El API acertó 4 de 4 en asignación de inicio.** No se ha encontrado ningún
error de inicio del API. La bandera `PRIMERA_DE_VENTANA` es precautoria.

**Error residual conocido**: hasta ±1 partido en el cierre de una era, cuando
el cese ocurre entre jornadas y el interino toma el siguiente partido
(Aguirre cesado el 26-feb-2022, el API le da el partido del 2-mar).
**Mitigación pendiente**: sensibilidad excluyendo el primer partido de cada era.

---

## 6. Decisiones de alcance, cerradas

| # | decisión | resuelto |
|---|---|---|
| 1 | Verificación por **muestreo**, documentado como tal | ✅ |
| 2 | **Excluir** temporada 351 (en curso, Atlante, cobertura cambiante) | ✅ |
| 3 | **Excluir** liguilla/repechaje/play-in del ajuste; reportar como sensibilidad | ✅ |
| 4 | Umbral de era: **25 partidos** | ✅ |
| 5 | Malla: **5×4** para el titular; **6×4 como sensibilidad viable** | ✅ |

### La aritmética de 4 y 5

Con ~690 transiciones por partido del club focal y el criterio
`params_per_obs` ≤ 0.5:

| malla | estados | params | partidos necesarios | eras que pasan (de 134) |
|---|---|---|---|---|
| 4×3 | 48 | 2,448 | 7 | 105 |
| **5×4** | **80** | **6,640** | **19** | **68** |
| 6×4 | 96 | 9,504 | 28 | 48 |
| 6×5 | 120 | 14,760 | 43 | 14 |

El umbral de 25 está **por encima** del criterio (19): es conservador.
6×4 pasa de descartado a sensibilidad con 48 eras. Se elige 5×4 porque 6×4
cuesta 20 unidades, y **la potencia de τ² la manda el número de unidades**.

**Pendiente (H3, no bloqueante)**: repetir el barrido midiendo el error del
estimador **encogido** en vez de contar parámetros. `params_per_obs` mide el
sobreajuste del EMV crudo y es conservador por construcción
(`12_API_STATSBOMB.md` §5.3). Con prior de liga el encogimiento es mucho más
fuerte y mejor informado.

### Notas de derivación

- **El torneo se deriva de la FECHA**, no de `competition_stage`: la etiqueta
  es inconsistente (la temporada 235 dice `Regular Season` donde las otras
  dicen `Apertura`). Julio–diciembre = Apertura, enero–junio = Clausura.
- `grid.py` **ya es global**: `StateSpace` depende solo del config, y
  `estimate.py` construye `C = np.zeros((n_transient, n_states))`. Las
  matrices de clubes distintos ya son comparables. **No hace falta el cambio
  estructural que se había previsto para la semana 2.**

---

## 7. Errores cometidos en esta sesión

Cuatro, y ninguno lanzó una excepción. Van aquí porque el *porqué* es lo que
impide repetirlos.

| # | error | causa | lección |
|---|---|---|---|
| 1 | El descargador cacheó respuestas vacías como si fueran datos | `statsbombpy` **no lanza excepción con un 401**: imprime y devuelve vacío | una respuesta vacía es un fallo, no un dato; abortar, no cachear |
| 2 | Se afirmó que el API se equivocaba con Herrera | reconocer un nombre en un club no es verificarlo; se usó memoria en vez de fuente | **la aritmética antes que la fecha**; el conteo cuadra o no cuadra |
| 3 | Se comparó el esquema leyendo **un solo partido** | las banderas de eventos raros salieron como "ausentes" | es el mismo error que `infer_schema_length=100` (§3.6 del contrato) |
| 4 | Se estimó "140 transiciones por partido" a ojo, y eran 690 | promedio sobre 18 equipos de un archivo dominado por uno | poner siempre el contraste en el script, no fiarse de la estimación |

Además, dos bugs menores del instrumental: `01_construir_eras.py`
sobrescribía el CSV global en corridas de un solo club (arreglado), y una
resta de columnas `u32` en un diagnóstico dio $2^{32}-528$ en vez de −528.

> El patrón es el mismo que el proyecto documenta desde el bug #1 (#14 a esta fecha):
> **nada falla, todo es plausible, y el número está mal.** Esta vez sobre
> datos de entrada y sobre el instrumental de diagnóstico, no sobre `src/`.

---

## 8. Decisión pendiente de confirmar

> **¿La fuente canónica pasa a ser el API?**
> Recomendación: **sí**. Cobertura de 19 clubes, fechas reales, entrenadores,
> 360 disponible. El volcado viejo queda como histórico.
>
> **Consecuencia incómoda que hay que escribir en
> `08_REPRODUCIBILITY.md` §4.3**: contra un API vivo, el hash de
> `DATA_PROVENANCE.txt` prueba **qué descargaste**, no qué descargará otro.
> El proveedor revisa datos históricos: quedó medido, un 1% en la definición
> de posesión sobre 175 partidos en unos meses. La reproducibilidad exacta
> exige conservar el crudo descargado, o publicar los agregados (§4.2).

---

## 9. Reglas nuevas que rigen de aquí en adelante

1. **`src/dtdecoder/` jamás importa `statsbombpy`.** El API vive en
   `scripts/00_fetch_statsbomb.py`. El puente son archivos en disco.
2. **Dos entornos**: `.venv` para pipeline y tests, `.venv-sb` para el API.
   Un diagnóstico que solo lea `.json.gz` corre en `.venv` sin problema.
3. **Credenciales por `read -rs` y variable de entorno**, nunca en un `.py`.
4. **Se versiona**: `data/eras_api/`, `data/eras_compat/`,
   `data/eras_correcciones.csv`, `data/alias_entrenadores.csv`,
   `data/raw_api/indice_partidos.csv`.
   **Nunca**: `data/raw_api/{events,lineups,frames}/`, `data/api/*`,
   `.venv-sb/`, `.env`.
5. **No hay `git push`** hasta que los titulares retirados estén marcados
   como retirados en el README.

---

## 9 bis. Convención de trabajo (cómo se opera esta migración)

Se trabaja **todo en terminal**. El asistente no edita archivos del repo
directamente: entrega paquetes y el humano los instala.

### El ciclo

1. El asistente entrega un **`.tar.gz`** que contiene `scripts/`, `docs/` y
   un `INSTALAR.sh`.
2. El humano lo descarga a `~/Descargas` y ejecuta:

```bash
cd ~/Descargas && tar xzf <paquete>.tar.gz && bash paquete/INSTALAR.sh
```

3. `INSTALAR.sh` copia a `scripts/` y `docs/` del proyecto, **respalda** lo
   que iba a sobrescribir como `<archivo>.anterior_AAAAMMDDHHMM`, y añade los
   patrones necesarios a `.gitignore`. No borra nada.
4. Los diagnósticos de una sola vez van como **heredoc** pegado a la terminal
   (`python - << 'PY' ... PY`), no como archivo. Los que se vuelven a usar se
   promueven a `scripts/`.

### Rutas

```
/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026/   ← el repo ES esta carpeta
  ├── .venv/           ← pipeline + tests (dtdecoder, polars, pytest)
  ├── .venv-sb/        ← SOLO el API (statsbombpy, pandas<3)
  ├── scripts/         ← 00_fetch, 01_construir_eras, 02_adaptar, sondas
  ├── src/dtdecoder/   ← núcleo. NO importa statsbombpy
  ├── docs/
  └── data/
       ├── raw_api/    ← JSON crudo del API (NO se versiona)
       ├── api/        ← eventos adaptados (NO se versiona)
       ├── eras_api/   ← eras con banderas (SÍ)
       └── eras_compat/← 3 columnas para eras.load_eras (SÍ)
```

**La ruta tiene espacios.** Siempre entre comillas.

### Los dos entornos

Ya están creados. Si hubiera que rehacer el del API:

```bash
cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"
uv venv .venv-sb --python 3.12
source .venv-sb/bin/activate
uv pip install statsbombpy "pandas<3"
```

`pandas<3` es deliberado: statsbombpy 1.22 es anterior a pandas 3.0.
**Por qué dos entornos**: statsbombpy arrastra pandas y numpy, y meterlos en
el entorno del pipeline invita a deriva numérica
(`08_REPRODUCIBILITY.md` §8).

Cuál usar en cada caso:

| tarea | entorno |
|---|---|
| descargar del API, construir eras, adaptar eventos | `.venv-sb` |
| `dtdecoder`, `pytest`, scripts de análisis, polars | `.venv` |
| leer un `.json.gz` ya descargado | cualquiera (es stdlib) |

Credenciales en cada sesión de terminal nueva:

```bash
export SB_USERNAME="itam_hackathon@hudl.com"
read -rs -p "Password: " SB_PASSWORD && export SB_PASSWORD && echo
```

---

## 9 ter. Arrancar una sesión nueva desde cero

### Qué subir al asistente

**Imprescindible** (con esto se puede trabajar):

- `docs/17_BITACORA_MIGRACION.md` ← este archivo
- `docs/16_MIGRACION_API.md`

**Muy recomendable** (evita repetir decisiones ya cerradas):

- `docs/02_STATE_OF_PLAY.md`
- `docs/10_RESULTADOS.md`
- `docs/06_DECISIONS.md`
- `docs/04_DATA_CONTRACT.md`

**Según la tarea**:

- tocar el reporte → `docs/15_REPORTE_HTML.md`
- tocar `src/` → `docs/01_ARCHITECTURE.md` + el `.py` concreto
- justificar matemática → `docs/03_METHODS.md`, `docs/11_MATEMATICA_APLICADA.md`

**Nunca subir**: `eventos_completos_*.csv` ni nada de `data/raw_api/` o
`data/api/`. Son datos licenciados de StatsBomb, pesan cientos de MB y no
aportan: el esquema está en `04_DATA_CONTRACT.md`. Si hace falta ver el
formato, una muestra de 100 filas basta.

Tampoco hace falta subir `scripts/00`, `01` ni `02`: están descritos aquí y
el asistente los reconstruye o los parchea entregando un paquete nuevo.

### Mensaje de arranque

Ver §0. Y añadir la tarea concreta: *"Quiero trabajar en H2"*.

### Verificación de que el entorno sigue bien

```bash
cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"
source .venv/bin/activate && pytest -q          # 135 en verde
ls data/raw_api/events/*.json.gz | wc -l        # 1767
wc -l data/eras_api/eras_todas.csv              # 135 (134 + cabecera)
```

---

## 9 quater. Roadmap de las 5 semanas

| semana | hitos | entregable |
|---|---|---|
| **1** | descarga, eras, decisiones, **H1** | ✅ **HECHA** (en un día) |
| **2** | H2 + H3 | liga completa procesada, prior de liga, λ\* reinterpretado |
| **3** | H4 + H5 + H6 | titulares recalculados, la firma que viaja, τ² con 53 unidades |
| **4** | H7 | `reporte.html` con entrada por entrenador |
| **5** | H8 | repo limpio, CI, licencias, push |

### Riesgos declarados

1. **H7 se va a quedar corto de tiempo.** H2–H6 son análisis y salen rápido
   porque la maquinaria existe; el reporte es diseño e iteración visual y
   siempre cuesta más. **Si en la semana 3 hay retraso, se recorta H5/H6
   antes que el reporte**: el entregable es el HTML.
2. **La firma podría no viajar.** Es posible que Larcamón en Puebla se
   parezca más a Puebla que a Larcamón en León. **Decidido de antemano: ese
   resultado se reporta igual.** No sería un fracaso sino un hallazgo —el
   estilo lo mandaría el plantel y no el técnico— y contradiría la narrativa
   habitual del fútbol. Es la misma disciplina que "no afirmar la nula".
3. **El hueco del par nulo** (§4). Sin un ejemplo de cambio de entrenador
   *sin* efecto, el método pierde el argumento que lo hace creíble.

### Reparto con un agente (Antigravity / Claude Code)

**No antes de la semana 5 para la limpieza**: `14_LIMPIEZA_REPO.md` le
prohíbe tocar `src/`, `tests/` y `config/`, y limpiar un blanco en
movimiento no sirve. Entonces se le entrega el doc 14 tal cual, que ya es un
brief ejecutable con inventario previo y cuarentena en vez de borrado.

**Durante las semanas 2–4** sí, para trabajo mecánico y bien especificado:
correr el pipeline sobre 19 clubes, regenerar figuras, maquetar el HTML
contra un contrato escrito.

**Nunca**: decisiones estadísticas, verificación de eras, cambios en el
espacio de estados. Ahí es donde salieron los bugs #1–#14, y todos fueron
silenciosos.

---

## 10. Siguiente acción concreta (H2)

```bash
cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"
source .venv-sb/bin/activate

# los 19 clubes a parquet, con el alcance decidido
for club in "América" "Atlas" "Atlético San Luis" "Cruz Azul" "Guadalajara" \
            "Juárez" "León" "Mazatlán" "Monterrey" "Necaxa" "Pachuca" \
            "Puebla" "Pumas UNAM" "Querétaro" "Santos Laguna" "Tigres UANL" \
            "Tijuana" "Toluca"; do
  python scripts/02_adaptar_eventos.py --club "$club" --formato parquet \
      --excluir-liguilla --excluir-temporadas 351
done
```

Luego `phase0` por club con las eras de `data/eras_compat/`, y verificar
`13_verificar_ejes.py` en dos o tres clubes que no sean el América: la
orientación y la absorción hay que confirmarlas fuera del club donde se
validaron.

**Comprobación aritmética gratis**: las eras nuevas del América dan
27 + 55 + 129 = 211 partidos sobre la ventana completa. Los conteos de
`phase0` tienen que cuadrar contra eso.

## Bugs #17 y #18 — identificar una unidad por una clave incompleta

Cuatro apariciones en una sola sesión del mismo patrón: usar como
identificador algo que no es la clave completa `(club, entrenador)`.

- **#12 (reaparecido)**: el reporte emparejaba huellas por subcadena de la
  última palabra. «Diego Cocca I» daba `ap="i"`, e `"i"` está dentro de casi
  cualquier nombre de archivo.
- **#17**: el slug de la huella era solo el entrenador. Jardine dirigió
  América y San Luis; al llegar a San Luis el archivo ya existía y el script
  lo saltó. Cuatro huellas cruzadas entre clubes, y precisamente las cuatro
  que sostienen el argumento de que la firma viaja. Se previeron 21 huellas
  y había 17 en disco: el conteo lo delató.
- **#18**: la tabla de referencia de `29_panorama_liga.py` se indexaba por
  nombre, así que comparaba a San José/Mazatlán contra los valores de
  San José/Atlas. En el script escrito para verificar.

**Regla**: en este dominio la unidad es `(club, coach, era)`. Cualquier
diccionario, nombre de archivo o emparejamiento que use menos que eso es un
bug esperando a que dos clubes compartan entrenador — y con 8 técnicos en
varios clubes, eso ocurre.

Ninguno lanzó excepción. Los tres se detectaron contando.
