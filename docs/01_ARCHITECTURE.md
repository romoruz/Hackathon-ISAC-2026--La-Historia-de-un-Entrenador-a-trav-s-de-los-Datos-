# 01 — Arquitectura del proyecto

> **Audiencia**: una IA que debe modificar este código y devolver un tarball
> ejecutable. Este documento describe cada archivo, qué hace, de qué depende y
> qué se rompe si se cambia.

---

## 1. Árbol de archivos

```
dt-decoder/
├── pyproject.toml              # metadatos, dependencias, entrypoint CLI
├── Makefile                    # atajos: setup, test, lint, demo, clean
├── README.md                   # instalación y uso (usuario final)
├── .gitignore
├── config/
│   └── default.yaml            # ÚNICO lugar donde viven los parámetros
├── src/dtdecoder/
│   ├── __init__.py             # API pública del paquete
│   ├── config.py               # cargador de YAML
│   ├── grid.py                 # espacio de estados y partición del campo
│   ├── ingest.py               # lectura y normalización de esquema
│   ├── possessions.py          # cadenas de posesión → transiciones
│   ├── eras.py                 # mapeo partido→DT y diseño de comparación
│   ├── estimate.py             # conteos, encogimiento, CV de λ
│   ├── absorbing.py            # N, B, xT, distribución de visitas
│   ├── inference.py            # bootstrap, G², FDR
│   ├── plots.py                # figuras
│   ├── synth.py                # generador sintético con esquema real
│   └── cli.py                  # orquestación: un comando por fase
├── scripts/
│   ├── quickstart.sh           # instalación + tests + demo
│   └── fetch_match_dates.py    # trae fechas del API (no vienen en eventos)
├── tests/                      # 34 tests
│   ├── test_grid.py
│   ├── test_estimate.py
│   ├── test_absorbing.py
│   ├── test_pipeline.py
│   ├── test_eras.py
│   └── test_prior.py
├── docs/                       # esta documentación
├── data/{raw,interim,processed}/   # vacíos en el repo (.gitkeep)
└── reports/figures/
```

---

## 2. Grafo de dependencias

```
config.py ──────────────┐
                        ▼
grid.py ────────► possessions.py ◄──── ingest.py
   │                    │
   │                    ▼
   ├──────────────► eras.py
   │                    │
   ├──────────────► estimate.py
   │                    │
   ├──────────────► absorbing.py
   │                    │
   ├──────────────► inference.py ◄──── estimate.py
   │                    │
   └──────────────► plots.py
                        │
                        ▼
                     cli.py  ◄──── synth.py
```

`grid.py` no importa nada del proyecto: es la base. `cli.py` es la única capa
de orquestación; ningún módulo importa `cli`.

---

## 3. Módulos y herramientas, uno por uno

### `Makefile`
Automatiza tareas comunes de desarrollo:
- `make setup`: crea el entorno virtual `.venv` con Python 3.12 e instala dependencias (`[dev]`) vía `uv`.
- `make test`: ejecuta el suite de pruebas en modo silencioso (`uv run pytest -q`).
- `make lint`: ejecuta el linter de código (`uv run ruff check src tests`).
- `make demo`: genera los datos sintéticos y salidas de prueba (`uv run dtdecoder demo --outdir reports`).
- `make clean`: elimina artefactos temporales e intermediarios (`data/interim/*`, `data/processed/*`, `reports/figures/*`, `.pytest_cache`).

### `config.py`
Carga `config/default.yaml` en un objeto `Config` con acceso tipo diccionario.
La ruta por defecto se resuelve como `Path(__file__).parents[2]/config/default.yaml`,
es decir la raíz del repo.

**Si se cambia la estructura de carpetas, esta ruta se rompe.** Es el único
lugar con una suposición de layout.

### `grid.py`
Define `StateSpace`, un dataclass congelado que encapsula toda la geometría y el
indexado.

```python
StateSpace(nx=5, ny=4, length=120.0, width=80.0,
           phases=("open","transition","restart","set_piece"))
```

Responsabilidades:
- `zone_of(x, y)` → índice de zona. **Recorta coordenadas al campo**: StatsBomb
  reporta x=120.1 en remates y y=−0.2 en centros desde la línea de fondo.
- `transient_index(zone, phase_idx)` → índice de estado transitorio.
  Layout: `zona * n_fases + fase`.
- `absorbing_index(nombre)` → índice global, con offset por los transitorios.
- `zone_centroids()` → matriz (n_zones, 2) en metros. **Es la métrica base para
  la W₁ de la Fase 8**; ya está lista aunque la fase no esté implementada.

**Invariante crítico**: el orden de `phases` determina el layout de TODAS las
matrices guardadas en disco. Se deriva de `config.phase_order`, que es
explícito precisamente para que un cargador de YAML que reordene llaves no
desalinee matrices entre corridas. Hay un test de regresión
(`test_phase_order_is_explicit_not_dict_order`).

Constantes: `ABSORBING = ("GOAL","SHOT_NOGOAL","LOSS","OUT")`,
`PHASES = ("open","transition","restart","set_piece")`.

### `ingest.py`
Lectura perezosa (`polars.LazyFrame`) de parquet / CSV / ndjson, archivo o
directorio.

**El detalle que importa**: `_scan_csv` fuerza `infer_schema_length=None`
(escanea el archivo completo). Con el default de polars (100 filas), decenas de
columnas de StatsBomb que solo tienen valor en eventos raros
(`shot_outcome`, `goalkeeper_type`, `foul_committed_card`) se tipan como `Null`
y **los filtros sobre ellas devuelven vacío en silencio** — peor que fallar.
También castea a `Utf8` las columnas categóricas que quedaron `Null`.

`parse_location` maneja los dos formatos en que puede venir `location`:
- lista nativa `[60.0, 40.0]` (parquet/JSON)
- string serializado `"[60.0, 40.0]"` (CSV)

`normalize(lf)` valida columnas requeridas (falla temprano y explícito),
selecciona, parsea coordenadas y ordena por `(match_id, index)`.

Columnas requeridas: `id, index, match_id, period, minute, second, type, team,
possession, possession_team, play_pattern, location`.
Columnas opcionales que se conservan si existen: `duration, pass_outcome,
shot_outcome, shot_statsbomb_xg, under_pressure, counterpress, obv_*`, etc.

### `possessions.py`
El corazón de la Fase 0. Convierte eventos en transiciones.

Funciones:
- `add_score_state(lf, bins, labels)` — calcula `goal_diff` desde la óptica de
  `possession_team`. **Usa `shift(1)` sobre el acumulado**: el gol no cuenta
  para su propio evento. Sin ese shift cada gol se autoexplica y el análisis
  condicional al marcador queda contaminado.
- `extract_actions(lf, cfg)` — filtra a acciones de la posesión, resuelve
  coordenadas de destino según tipo, clasifica el desenlace, y aplica el filtro
  de acarreos cortos.
- `build_transitions(lf, space, cfg, team=None)` — orquesta y devuelve el
  DataFrame de transiciones.
- `_append_terminal_absorption` — **paso crítico**: si la última acción de una
  posesión deja el balón en un estado transitorio, añade una transición extra
  hacia `LOSS`. Sin esto, `P` sobreestima la permanencia y `N = (I−Q)⁻¹` se
  infla hacia arriba.
- `coordinate_sanity(trans, space)` — correlación entre índice de columna de
  zona y tasa de gol. Debe ser positiva y alta.

Salida: DataFrame con columnas
`poss_uid, match_id, team, event_index, phase, score_state, from_state,
to_state, is_absorbing`.

`poss_uid` es la **unidad de remuestreo** de todo el bootstrap posterior.

### `eras.py`
Mapeo partido→entrenador y diseño de comparación.

- `load_eras(path)` — lee el CSV de eras y **rechaza traslapes**: un partido no
  puede tener dos DT.
- `load_match_dates(path)` — CSV `(match_id, match_date)`.
- `match_coach_table(match_dates, eras, club)` — `join_asof` hacia atrás sobre
  fecha, filtrando por `end_date`.
- `attach_coach(trans, mc, club)` — añade columna `coach`; **los rivales quedan
  en null deliberadamente**, lo que identifica las filas que sirven como línea
  base externa sin contaminarse con eras del club.
- `select_units(trans, unit, value, baseline, club)` — devuelve `(foco, base)`.
  Tres diseños:

  | baseline | contra quién | uso |
  |---|---|---|
  | `other_coaches` | otras eras del mismo club | **default**, el diseño fuerte |
  | `opponents` | solo los rivales | contextualizar contra la liga |
  | `rest` | todo lo demás | exploración |

- `coverage_report(trans, club)` — partidos, posesiones y transiciones por era,
  con bandera `suficiente` (≥25 partidos).
- `detect_regime_changes(trans, space, club, window)` — distancia TV entre
  ventanas contiguas de partidos. **No sustituye al mapeo real: lo verifica.**
  Si las fronteras documentales coinciden con los picos, hay evidencia
  independiente de que las fechas son correctas.
- `AMERICA_ERAS` + `write_template()` — plantilla prellenada. **Las fechas son
  aproximaciones derivadas de los años de Wikipedia y deben verificarse.**

### `estimate.py`
- `count_matrix(trans, space)` — matriz de conteos `(n_transient, n_states)` por
  `np.add.at`.
- `mle(C)` — EMV crudo. Renglones vacíos quedan en cero (bandera de rala).
- `shrink(C, Q, lam)` — el estimador de encogimiento. Repara renglones
  degenerados de `Q` con la uniforme y renormaliza.
- `possession_folds(trans, k, seed)` — particiona **por posesión**, no por
  evento. Partir por evento filtra información entre train y test.
- `cv_lambda(...)` → `CVResult(lam_star, grid, scores)`.
- `sparsity_report(C)` — `frac_below_min`, `median_row_count`,
  `params_per_obs`.
- `error_curve(...)` — submuestrea posesiones y compara contra el ajuste full.
  Es la gráfica que justifica la elección de malla.

### `absorbing.py`
`AbsorbingChain(P, space)` con propiedades `Q` y `R` derivadas por partición de
columnas.

- `check()` — `ρ(Q) < 1`, filas suman 1, norma infinito de Q.
- `fundamental()` — `N` resolviendo `(I−Q)N = I` con `scipy.linalg.solve`. **No
  invierte**: mismo resultado, mejor condicionamiento, menos costo.
- `absorption()` — `B = NR`, también por `solve`.
- `expected_length()` — `N·1`.
- `xt()` — columna GOAL de `B`.
- `visit_distribution(alpha)` — resuelve `(I−Q)ᵀν = α`.
- `by_zone` / `zone_weighted` — colapsan estados a la malla para graficar.
- `empirical_start_distribution(trans, space)` — α empírico.

### `inference.py`
- `PossessionIndex` — estructura tipo CSR (`flat`, `starts`, `lens`) que permite
  remuestrear miles de réplicas con `np.bincount` sin reconstruir DataFrames.
  `_gather_ranges` concatena rangos de forma vectorizada.
- `g2_rows(C, Q)` — `G²_i = 2Σ n_ij log(n_ij / (n_i q_ij))` por renglón.
- `tactical_fingerprint(...)` — calcula `G²` observado y calibra la nula
  remuestreando posesiones del pool base con el mismo número de posesiones que
  el foco. p-valor con corrección `+1`.
- `_diff_estimate(C_focus, C_base, prior, lam)` — **receta única** del
  estimador de la diferencia. El estimador puntual y cada réplica bootstrap
  DEBEN calcularse con esta función; si difieren, el IC deja de estar centrado
  en el estimador. Hay test de regresión.
- `bootstrap_diff(...)` — IC con `method="basic"` (percentil invertido) por
  defecto, que corrige el sesgo de primer orden que introduce el encogimiento.
- `benjamini_hochberg(p, alpha, mask)` — control de FDR.
- `context_contrast(...)` — distancia TV entre niveles de contexto.

### `plots.py`
Backend `Agg` (sin display). Cuatro figuras: `zone_heatmap`, `cv_curve`,
`error_vs_n`, `fingerprint_map`.

### `synth.py`
Generador con el **esquema real de StatsBomb**. `dt_bias` inclina a un equipo a
progresar por el centro; es el efecto que la Fase 3 debe recuperar. Sirve para
tests y para el experimento de recuperación de parámetros que va en el reporte.

### `cli.py`
Un comando por fase. Helpers importantes:

- `_space(cfg)` — construye `StateSpace` leyendo `phase_order` del config.
- `_build_prior(trans, space, mode, exclude)` — **corrige la fuga de prior**:
  con un archivo centrado en un club, ese club puede ser >50% de las
  transiciones; si el prior lo contiene, el foco se encoge hacia un promedio que
  ya lo incluye. Modos: `exclude_focus` (default), `pooled`, `baseline`.
- `_warn_boundary(cv, grid)` — avisa si λ\* toca cualquier extremo de la rejilla.
- `_not_focus(trans, unit, value)` — complemento del foco.

Comandos: `convert`, `eras-template`, `phase0`, `regimes`, `phase1`, `phase2`,
`phase3`, `compare`, `demo`.

---

## 4. Contrato de artefactos en disco

`cli` escribe y lee estos archivos. **Una IA que modifique el código debe
mantener este contrato o actualizar todos los consumidores.**

| archivo | escrito por | leído por | contenido |
|---|---|---|---|
| `transitions.parquet` | phase0 | phase1,2,3, regimes, compare | tabla de transiciones |
| `phase0_report.json` | phase0 | — | diagnósticos de ingesta |
| `P_matrices.npz` | phase1 | phase2, phase3 | `P_focus, P_base, prior, C_focus, C_base` |
| `phase1_report.json` | phase1 | phase3 (lee `lambda_star`) | λ\*, dispersión |
| `error_curve.parquet` | phase1 | — | curva error-vs-N |
| `phase2.npz` | phase2 | — | `xt, length, nu, B` |
| `fingerprint.parquet` | phase3 | — | G², p, q, rechazos |
| `significant_cells.parquet` | phase3 | — | celdas con IC sin cero |
| `context_contrast.parquet` | phase3 | — | TV entre contextos |
| `regime_changes.parquet` | regimes | — | quiebres estructurales |

**Acoplamiento a vigilar**: `phase3` lee `lambda_star` de `phase1_report.json`.
Si se cambia el nombre de esa clave, `phase3` truena.

---

## 5. Cómo modificar el proyecto sin romperlo

### Añadir un parámetro
1. Agregarlo a `config/default.yaml` **con comentario que explique la decisión**.
2. Leerlo en `cli.py` o en el módulo correspondiente vía `cfg`.
3. Nunca hardcodear: todo lo que afecte resultados vive en el config, porque es
   lo que se cita en el reporte.

### Cambiar el espacio de estados
- Zonas: solo `config.pitch.nx/ny`.
- Fases: `config.phase_order` **y** `config.phases`. `build_transitions` valida
  que las fases del mapeo estén en el espacio y falla explícitamente si no.
- Estados absorbentes: requiere tocar `grid.ABSORBING`,
  `possessions.extract_actions` (clasificación de desenlace) y revisar
  `absorbing.py`. **Es el cambio más invasivo.**

### Añadir una fase nueva del roadmap
1. Módulo nuevo en `src/dtdecoder/`.
2. Consume `transitions.parquet` y/o `P_matrices.npz`. **No modificar los
   módulos existentes** salvo que sea imprescindible.
3. Comando nuevo en `cli.py` siguiendo el patrón `cmd_phaseN(args)`.
4. Tests nuevos en `tests/test_<modulo>.py`.
5. Sección nueva en `00_ROADMAP.md` marcando el cambio de estado.

### Reglas duras
- **Todo cambio con un test.** Los bugs encontrados en este proyecto (fuga de
  prior, orden de fases, IC descentrado, esquema CSV) fueron todos silenciosos:
  producían números plausibles pero incorrectos.
- **No romper el contrato de artefactos** sin actualizar los consumidores.
- **No introducir aleatoriedad sin semilla** desde config.

---

## 6. Cómo producir el tarball ejecutable

```bash
cd dt-decoder
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache reports/demo data/processed/* data/interim/*
cd .. && tar czf dt-decoder-vX.Y.tar.gz dt-decoder
```

Antes de empaquetar, verificar SIEMPRE:

```bash
pytest -q                    # todos los tests en verde
dtdecoder demo               # pipeline 0→3 end-to-end sobre sintéticos
dtdecoder --help             # todos los comandos listados
```

Bump de versión en **dos** lugares: `pyproject.toml` y
`src/dtdecoder/__init__.py`.

### Script de despliegue (`instalar.sh`)

`instalar.sh` en la raíz es el script de actualización y despliegue del proyecto.
Funciones:
- Verifica la raíz del proyecto y que el venv esté activo.
- Crea un respaldo con marca de tiempo (`.backup_YYYYMMDD_HHMMSS`).
- Copia y sobrescribe los módulos de `src/dtdecoder/`, `tests/`, `scripts/`, `docs/`, `data/` y `app.py`.
- Retira scripts que quedaron obsoletos en iteraciones anteriores.
- Actualiza la versión en `pyproject.toml` e `__init__.py`.
- Protege los datos licenciados asegurando sus entradas en `.gitignore`.
- Ejecuta `pytest -q` y, **si fallan las pruebas, revierte automáticamente** restaurando los módulos desde el backup.

> [!CAUTION]
> **ADVERTENCIA PARA AGENTES DE IA**: NINGÚN agente de IA debe ejecutar `instalar.sh`. Este script solo lo ejecuta manualmente el usuario humano al desplegar o actualizar a una versión nueva.

---

## 7. Entorno de destino

| | |
|---|---|
| SO | Arch Linux, kernel 7.1.x |
| CPU | Intel i7-1165G7, 4 núcleos / 8 hilos |
| RAM | 32 GiB |
| GPU | Intel Iris Xe — **sin CUDA** |
| Python | 3.12 vía `uv` |

Ninguna parte del pipeline necesita GPU. Es una de las razones por las que se
descartó explícitamente el enfoque con redes neuronales de grafos.

**Nota de instalación**: el venv vive dentro del repo (`.venv/`) y está en
`.gitignore`. Al mover o re-extraer el proyecto hay que recrearlo:
`uv venv --python 3.12 && source .venv/bin/activate && uv pip install -e ".[dev]"`.

---

## 8. Contexto mínimo para que otra IA trabaje

Si el presupuesto de contexto es limitado, priorizar en este orden:

1. `docs/02_STATE_OF_PLAY.md` — dónde estamos y qué se estaba corrigiendo.
2. `docs/01_ARCHITECTURE.md` — este archivo.
3. `config/default.yaml` — todas las decisiones parametrizadas.
4. `src/dtdecoder/possessions.py` + `grid.py` — la Fase 0 es donde se originan
   casi todos los errores silenciosos.
5. `docs/00_ROADMAP.md` — qué sigue.
6. `src/dtdecoder/inference.py` — la parte estadísticamente delicada.
7. `docs/03_METHODS.md` — la matemática, si hay que justificar o extender.

---

## 9. Lo añadido en la sesión del entregable (2026-08-26 a 29)

### Módulos en `src/dtdecoder/`

| archivo | qué hace | por qué existe |
|---|---|---|
| `geometria_remate.py` | `goal_open`: integral de visibilidad sobre el `shot_freeze_frame` | portado del proyecto de córners con tres correcciones (ADR-51) |
| `xg_remate.py` | features y logística IRLS sin sklearn | **lógica compartida** por los scripts 25 y 26. Dos copias divergirían en silencio: es el bug #2 |

### Scripts

| script | qué contesta |
|---|---|
| `23_potencia_tau2.py` | ¿tiene el diseño potencia para ver variación entre eras? |
| `24_diagnostico_freeze_frame.py` | ¿cómo viene el `shot_freeze_frame`? (evitó repetir el bug #13) |
| `25_goal_open_eras.py` | calidad del remate entre dos eras, con atribución |
| `26_goal_open_barrido.py` | la familia `goal_open-eras` con FDR |
| `27_lift_ruta.py` | ¿de dónde nace el peligro? Los cocientes en consola, sin interfaz |
| `verifica_reporte.py` | ¿el HTML compila y declara sus variables CSS? |
| `humo_reporte.py` + `.js` | **renderiza la página** en un DOM real con datos sintéticos |

### Herramientas de documentación

`docs/verificar_docs.py` es el `pytest -q` de los documentos. Comprueba que el
conteo de bugs sea único, que ninguna afirmación retirada se cite como viva, que
toda ADR citada exista y que los enlaces internos apunten a algo.

Existe porque la documentación llegó a decir **tres cifras distintas** para el
número de bugs sin que nada fallara: la prosa no se ejecuta, así que el patrón
de riesgo del proyecto se aplica igual a ella.

### Qué se rompe al tocarlo

- `geometria_remate.py` → `tests/test_goal_open.py` (26 tests, incluido el
  contraste contra una implementación independiente por trazado de rayos).
- `xg_remate.py` → los scripts 25 y 26 a la vez. **Cambiar uno solo es el bug #2.**
- `12_reporte_html.py` → `verifica_reporte.py` y `humo_reporte.py`. El segundo
  necesita `npm install jsdom` una vez; si falta, avisa y sale sin fallar.
