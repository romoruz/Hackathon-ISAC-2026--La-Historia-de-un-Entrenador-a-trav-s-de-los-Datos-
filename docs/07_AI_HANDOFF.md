# 07 — Guía de traspaso para una IA

> Cómo retomar este proyecto sin haber participado en las conversaciones
> previas. Actualizado 2026-08-20.

---

## 0. Lee esto primero: el patrón de riesgo del proyecto

**Dieciocho bugs encontrados. Dieciocho silenciosos.** Ninguno lanzó una excepción; todos
produjeron números plausibles pero incorrectos. En este dominio, *"corre sin
error"* no significa nada.

Los dos más recientes ilustran el género:

- **#7**: `phase2` modelaba a un entrenador y rotulaba las figuras con el nombre
  de otro. Se detectó porque un número cambió 5% entre dos corridas del mismo
  comando.
- **#8**: una semilla fija sobre `unique()` de polars, cuyo orden no está
  garantizado. Tres corridas idénticas daban tres resultados distintos en el
  cuarto decimal.

Si vas a tocar algo, el test no es opcional.

---

## 1. Orden de lectura

Con presupuesto de contexto limitado, leer en este orden y parar cuando alcance:

1. **`02_STATE_OF_PLAY.md`** — dónde estamos, qué está validado, qué está
   bloqueado. Sin esto se repiten trabajos ya hechos.
2. **`10_RESULTADOS.md`** — los hallazgos con su etiqueta 🟢🟡🔴⚪ y sus caveats.
   **No cites ningún número sin leer su fila.**
3. **`06_DECISIONS.md`** — debates cerrados. **No reabrirlos sin argumento
   nuevo.** ADR-21 a ADR-32 son recientes y consecuentes. **ADR-30 es el
   principio central: ninguna distancia se reporta sin su nula.**
3b. **`11_MATEMATICA_APLICADA.md`** — dónde entra cada teorema y qué número
   produjo. Es lo que se usa para defender elecciones ante un jurado.
4. **`01_ARCHITECTURE.md`** — qué hace cada archivo y qué se rompe al tocarlo.
5. **`config/default.yaml`** — decisiones parametrizadas con justificación.
6. **`04_DATA_CONTRACT.md`** — trampas del formato StatsBomb.
7. **`src/dtdecoder/possessions.py`** + **`grid.py`** — la Fase 0 es donde se
   originan casi todos los errores silenciosos.
8. **`05_VALIDATION.md`** — antes de reportar cualquier número.
9. **`src/dtdecoder/inference.py`** — la parte estadísticamente delicada.
10. **`03_METHODS.md`** — la matemática, si hay que justificar o extender.
11. **`15_REPORTE_HTML.md`** — el contrato del entregable. Antes de tocar
    `12_reporte_html.py`.
12. **`00_ROADMAP.md`** — qué sigue y por qué en ese orden.

---

## 2. Perfil del usuario

Estudiante de matemáticas aplicadas, 6º semestre, ITAM. Cursos completados:
análisis, topología, probabilidad, inferencia estadística (IC, EMV, EMM,
contrastes simple vs compuesta), sistemas dinámicos, simulación (generación de
aleatorios, muestreo, **bondad de ajuste**, Monte Carlo, MCMC, remuestreo, todas
las técnicas de reducción de varianza), procesos estocásticos, programación
lineal (simplex, dualidad, KKT, Farkas, sensibilidad).

**No ha visto**: estadística bayesiana formal, aprendizaje automático, redes
neuronales.

Implicaciones para cómo explicar:

- El encogimiento se presenta **primero** como estimador frecuentista tipo
  James–Stein; la equivalencia Dirichlet es la segunda lectura.
- Conectar con sus cursos: la matriz fundamental es álgebra lineal + serie de
  Neumann; el LRT es contraste simple vs compuesta; el KS con bootstrap
  paramétrico es su Tema de bondad de ajuste; CRN e importance sampling son su
  Tema 5; Wasserstein es flujo a costo mínimo con interpretación dual.
- **Si no puede explicar por qué funciona, no debe ir en la presentación.**

El usuario **pide que se paren las cosas cuando falta verificar algo**. Ha
detenido la generación de documentación dos veces para correr un diagnóstico
antes. Respétalo: es la razón de que el proyecto esté validado.

---

## 3. Entorno y rutas

Arch Linux, kernel 7.1.x · Intel i7-1165G7 · 32 GiB RAM · sin CUDA ·
Python 3.12 vía `uv`.

```
~/Hackathon2026/
├── .venv/                              ← Python 3.12, YA CONFIGURADO
├── eventos_completos_america.csv       ← dataset (NO se versiona)
├── eventos_completos_cruz_azul.csv     ← dataset (NO se versiona)
├── config/default.yaml
├── data/
│   ├── coach_eras.csv                  ← América, SÍ se versiona
│   ├── coach_eras_cruz_azul.csv        ← Cruz Azul, SÍ se versiona
│   ├── match_dates.csv                 ← derivadas, SÍ se versionan
│   ├── match_dates_cruz_azul.csv
│   ├── processed/                      ← artefactos América
│   └── processed_cruzazul/             ← artefactos Cruz Azul
├── docs/
├── reports/                            ← JSONs de los scripts de validación
├── scripts/
├── src/dtdecoder/
└── tests/
```

**El repo ES la carpeta `Hackathon2026`**, no una subcarpeta `dt-decoder`.

Dos advertencias que ya causaron problemas:

- **La ruta tiene espacios.** Siempre comillas.
- **`source .venv/bin/activate` antes de todo.** El `python` del sistema es
  3.14 y no tiene las dependencias. Un diagnóstico reportó "polars AUSENTE"
  simplemente por no activar el venv.

---

## 4. Flujo de trabajo obligatorio

### Antes de tocar nada
```bash
cd "~/Hackathon2026"
source .venv/bin/activate
pytest -q          # 135 en verde
```

### Al modificar
1. Cambio pequeño y localizado.
2. **Test que capture el cambio.** No "el código corre", sino "el número es el
   correcto". Y si el cambio es un contrato entre dos módulos, **el test cruza
   los dos lados** — ver `test_npz_contract.py` y por qué existe.
3. `pytest -q` en verde.
4. Documentar en `06_DECISIONS.md` si es una decisión, en `02_STATE_OF_PLAY.md`
   si es un arreglo, en `10_RESULTADOS.md` si produce un hallazgo.

### Al empaquetar
```bash
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache reports/demo data/processed/* data/interim/*
```
Bump de versión en **`pyproject.toml` Y `src/dtdecoder/__init__.py`**.

---

## 5. El pipeline, de principio a fin

```bash
source .venv/bin/activate

# 1. fechas derivadas (o reales del API, si las hay)
python scripts/01_derivar_fechas.py --events eventos_completos_america.csv \
  --club "América" --out data/match_dates.csv

# 2. transiciones + eras
dtdecoder phase0 --src eventos_completos_america.csv \
  --eras data/coach_eras.csv --match-dates data/match_dates.csv \
  --club "América" --outdir data/processed

# 3. encogimiento (SIEMPRE antes de phase2/3 para la MISMA unidad)
dtdecoder phase1 --unit coach --value "Andre Jardine" \
  --baseline other_coaches --club "América"

# 4. cadena absorbente
dtdecoder phase2 --unit coach --value "Andre Jardine" --club "América"

# 5. inferencia
dtdecoder phase3 --unit coach --value "Andre Jardine" \
  --baseline other_coaches --club "América" --n-boot 2000
```

**El orden `phase1` → `phase2`/`phase3` para la misma unidad es obligatorio**
(ADR-24). Si no coincide, aborta con `exit=1` y un mensaje que dice el comando
correcto. Eso es deliberado: fue el bug #7.

### Scripts de validación

| script | qué contesta | salida |
|---|---|---|
| `01_derivar_fechas.py` | orden temporal sin API | `data/match_dates*.csv` |
| `02_placebo_regimes.py` | ¿hay quiebres dentro de una era? | `reports/placebo_regimes.json` |
| `03_bondad_ajuste_longitud.py` | ¿la cadena describe la duración? | `reports/bondad_ajuste_longitud.json` |
| `04_sensibilidad_lambda.py` | ¿las conclusiones dependen de λ? | `reports/sensibilidad_lambda.json` |
| `05_auto_transiciones.py` | ¿cuánto de la cadena es quedarse quieto? | `reports/auto_transiciones.json` |
| `06_barrido_resolucion.py` | ¿el efecto sobrevive al cambiar la malla? | `reports/barrido_resolucion.json` |
| `07_cobertura_ic.py` | ¿los IC cubren su nivel nominal? | `reports/cobertura_*.json` |
| `08_ic_derivados.py` | IC para E[T], P(gol), P(remate) | `reports/ic_*.json` |
| `09_huella_efecto.py` | huella táctica por tamaño de efecto | `reports/huella_*` |
| `10_nula_contextos.py` | ¿el estilo se adapta al marcador? | `reports/nula_contextos_*.json` |
| `11_confusion_plantel.py` | ¿es el DT o son los jugadores? | `reports/plantel_*.json` |
| `12_reporte_html.py` | **el entregable** | `reporte.html` |
| `13_verificar_ejes.py` | ¿las bandas están al derecho? | consola |
| `14_diagnostico_defensa.py` | ¿cómo viene el esquema defensivo? (evitó el bug #13) | consola |
| `16`, `18`–`22` | bloque defensivo D1: presión, calibración, FDR | `reports/*presion*.json` |
| `verifica_reporte.py` | ¿el HTML compila y declara sus variables? | consola |
| `humo_reporte.py` | ¿la página se pinta con datos sintéticos? | `reporte_demo.html` |
| `23_potencia_tau2.py` | ¿tiene el diseño potencia para ver variación entre eras? | consola |
| `24_diagnostico_freeze_frame.py` | ¿cómo viene el `shot_freeze_frame`? | consola |
| `25_goal_open_eras.py` | calidad del remate entre dos eras | `reports/goal_open_*.json` |
| `26_goal_open_barrido.py` | la familia `goal_open-eras` con FDR | `reports/fdr_goal_open.json` |
| `27_lift_ruta.py` | ¿de dónde nace el peligro? (sin interfaz) | consola |
| `generar_todo.sh` | todas las parejas de entrenadores | varios |

> Las cuatro filas duplicadas de `07`–`10` que había aquí se eliminaron el
> 2026-08-26. Los números de los scripts defensivos se listan agrupados
> porque el reporte los consume por patrón de nombre, no de uno en uno.

---

## 6. Errores que ya se cometieron (no repetir)

| error | por qué pasó | cómo evitarlo |
|---|---|---|
| `scan_csv` con esquema de 100 filas | default de polars | `infer_schema_length=None` siempre |
| Estimador puntual e IC con recetas distintas | dos rutas para lo mismo | una función única |
| Orden de fases derivado del dict | los cargadores de YAML reordenan | listas explícitas |
| Prior conteniendo al foco | archivo dominado por un club | prior externo al foco |
| Suponer que `play_pattern` etiqueta el evento | etiqueta la posesión | leer el contrato de datos |
| **Leer un `.npz` de otra unidad** | estado compartido sin contrato | identidad en el artefacto |
| **Semilla fija sobre `unique()`** | el orden no está garantizado | ordenar antes de barajar |
| **Test que probaba medio contrato** | consumidor y productor por separado | test que cruza los dos lados |
| **Heurística calibrada en un club** | solo se probó con el América | usar estructura conocida, no saltos |
| **Constante de un club en código general** | `FRONTERAS_RIESGOSAS` global | parametrizar por club |
| No activar el venv | `python` del sistema es 3.14 | `source .venv/bin/activate` |

---

## 7. Qué NO hacer

- **No reabrir ADR-17 (GNN) ni ADR-18 (Poincaré)** sin argumento nuevo.
- **No añadir dependencias pesadas** (torch, tensorflow, pymc).
- **No hardcodear parámetros.** Van al config.
- **No subir la resolución de la malla** mientras Ortiz esté en el análisis:
  6×4 da `params_per_obs` = 0.502 sobre su era (ADR-25 / P-02).
- **No presentar λ\*=500 como un valor preciso.** La curva es una meseta.
- **No reportar magnitudes de `bootstrap_diff` sin declarar la atenuación.**
- **No usar `detect_regime_changes` para validar fronteras de era.** Se probó y
  no funciona (🔴 en `10_RESULTADOS.md` §6).
- **No reportar ninguna TV o distancia sin su nula** (ADR-30). Es el error que
  más veces se ha cometido: tres de tres, y las tres veces la conclusión estaba
  mal.
- **No afirmar la nula.** Si un contraste no rechaza, la frase es "no detectamos
  un efecto mayor a X", nunca "no hay efecto".
- **No reportar magnitudes con λ>0 sin declarar la atenuación** (ADR-22).
- **No ordenar la huella táctica por G² ni por z**: ambos escalan con el tamaño
  de muestra. Orden por `TV_exceso` (ADR-25, ADR-28).
- **No versionar los CSV de eventos.** Son datos licenciados de StatsBomb.
- **No presentar resultados sin el checklist** de `05_VALIDATION.md` §6.

---

## 8. Estado y siguiente acción

**Fases 0, 1, 2 y 3: completas y validadas sobre dos clubes independientes.**
No hay bloqueos.

Orden sugerido para lo que sigue:

1. **Sensibilidad a `min_carry_length`** (ADR-13). La única del plan original
   sin hacer. Ya se sabe que no puede explicar las auto-transiciones (el 60%
   vienen de pases), pero sigue sin reportarse.
2. **Validación externa contra xG / OBV** (`05_VALIDATION` §4.2). Una tarde,
   vale una diapositiva.
3. **Solapamiento de plantilla entre eras** (P-08). Es la amenaza viva más
   seria y el dataset trae `player_id`.
4. **Fechas reales del API para Cruz Azul**. Sin ellas no se puede analizar a
   Gutiérrez, Ferretti ni Moreno.
5. **Curva de potencia completa** (`05_VALIDATION` §4.7).
6. **Fase 8 (Wasserstein)**: es la extensión con mejor retorno y la que más
   conecta con programación lineal.

**Escalado a 18 equipos: técnicamente viable, pero NO antes de terminar
1–4.** El método está validado como portable, así que no hay obstáculo
técnico; el orden es una decisión de prioridad, porque los puntos 1–4
cuestan una tarde cada uno y el escalado cuesta dieciocho tardes de
investigación documental (`12_API_STATSBOMB.md` §5).

Cuando se haga, **λ\* y su interpretación cambian**: hoy el prior son los
rivales del América; con la liga completa es otra cosa, y la frase "el
América se parece a sus rivales" no sobrevive al cambio.

---

## 9. Plantilla de mensaje inicial para retomar

> Estoy retomando `dt-decoder` (decodificador táctico de entrenadores con
> cadenas de Markov absorbentes sobre eventos StatsBomb de Liga MX). He leído
> `docs/02_STATE_OF_PLAY.md`, `docs/10_RESULTADOS.md` y `docs/06_DECISIONS.md`.
>
> Entiendo que:
> - Las fases 0–2 están validadas sobre América **y** Cruz Azul.
> - Las fases 0–3 y el bloque defensivo D1 están completos y validados.
> - La huella táctica se ordena por `TV_exceso`, no por G² ni z (ADR-25).
> - Markov de primer orden fue **rechazado** por sobredispersión, y ADR-21
>   explica por qué se mantiene igual.
> - λ está débilmente identificado: significancia con λ\*, magnitudes con λ=0.
> - Las fechas de partido son **sintéticas derivadas** (ADR-26), no del API.
> - `detect_regime_changes` está descartado como validador de fronteras.
> - Los **dieciocho** bugs del proyecto fueron silenciosos, y el #13 se
>   **evitó** diagnosticando el esquema antes de estimar (ADR-42).
> - ADR-30: ninguna distancia se reporta sin su nula. Tres veces se violó y las
>   tres veces la conclusión estaba mal.
> - Todo titular lleva IC, y los IC están validados por cobertura (0.944).
>
> Quiero trabajar en [X]. Antes de modificar código voy a activar el venv y
> correr `pytest -q` para confirmar los 135 tests.
