# 08 — Reproducibilidad y publicación en GitHub

> Cómo dejar el proyecto en un estado donde un tercero pueda reproducir cada
> número sin acceso a la conversación original ni a la máquina original.

---

## 1. Las tres capas de reproducibilidad

| capa | pregunta que responde | estado |
|---|---|---|
| **Código** | ¿Puedo correr lo mismo? | ✅ repo + `pyproject.toml` |
| **Entorno** | ¿Con las mismas versiones? | ✅ `uv.lock` versionado |
| **Datos** | ¿Sobre los mismos datos? | ❌ no publicables (licencia) |

Las tres son necesarias. La tercera es la que suele matar la reproducibilidad en
proyectos deportivos, y hay una salida estándar (§4).

---

## 2. Fijar el entorno

Actualmente `pyproject.toml` declara rangos (`polars>=1.0`). Eso permite que una
instalación futura traiga una versión con comportamiento distinto.

```bash
uv lock                      # genera uv.lock con versiones exactas
git add uv.lock              # SE VERSIONA
```

Y para reproducir:
```bash
uv sync --frozen             # instala exactamente lo del lock
```

Registrar también en el README la versión de Python (3.12) y el SO de
desarrollo.

**Por qué importa aquí en concreto**: `polars` cambió el default de
`infer_schema_length` entre versiones, y ese es exactamente el parámetro que
causó un bug silencioso en este proyecto.

---

## 3. Estructura del repositorio

```
dt-decoder/
├── .github/workflows/ci.yml     ← añadir (§5)
├── config/default.yaml          ← versionado: define los resultados
├── src/dtdecoder/
├── tests/
├── docs/
├── scripts/
├── data/
│   ├── raw/.gitkeep             ← vacío; datos NO se versionan
│   ├── interim/.gitkeep
│   ├── processed/.gitkeep
│   └── coach_eras.csv           ← SÍ se versiona (es investigación propia)
├── reports/figures/
├── uv.lock                      ← añadir
├── pyproject.toml
├── LICENSE                      ← añadir (§6)
├── CITATION.cff                 ← añadir (§7)
└── README.md
```

**Distinción importante**: los eventos de StatsBomb son datos licenciados y no
se publican. El CSV de eras de entrenador es investigación propia derivada de
fuentes públicas y **sí** debe versionarse: es un artefacto valioso e
independiente.

---

## 4. El problema de los datos

Los datos de Hudl StatsBomb son licenciados. **No se pueden subir a un repo
público.** Tres mecanismos para que el trabajo siga siendo reproducible:

### 4.1 Reproducibilidad estructural con datos sintéticos

`synth.py` genera datos con el esquema real. `dtdecoder demo` corre el pipeline
completo de extremo a extremo sin datos reales. Cualquiera puede verificar que
el **método** funciona, aunque no reproduzca los **números**.

Es lo mismo que hacen los papers médicos con datos de pacientes.

### 4.2 Publicar los agregados, no los eventos

Las matrices de conteo $C$ agregadas por era **no** permiten reconstruir los
eventos individuales. Publicar `P_matrices.npz` y `fingerprint.parquet` permite
que un tercero verifique toda la inferencia posterior sin acceso a los datos
crudos.

Es la práctica estándar en estadística oficial: se publican tablas, no
microdatos.

Verificar con StatsBomb antes de publicar, pero un agregado de 84×84 sobre
120,000 eventos está muy lejos de ser reidentificable.

### 4.3 Documentar el hash de los datos

```bash
sha256sum eventos_completos_america.csv >> docs/DATA_PROVENANCE.txt
```
Permite que alguien con acceso legítimo al mismo dataset confirme que trabaja
sobre el mismo archivo.

---

## 5. Integración continua

`.github/workflows/ci.yml`:

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --frozen --all-extras
      - run: uv run ruff check src tests
      - run: uv run pytest -q
      - run: uv run dtdecoder demo --n-matches 20 --n-boot 50
```

El último paso es el importante: verifica el pipeline **end-to-end**, no solo
las unidades. Es lo que habría detectado los bugs silenciosos de este proyecto.

---

## 6. Licencia

Sugerencia: **MIT** para el código.

Añadir en el README una nota explícita:

> Este repositorio contiene únicamente código y documentación. Los datos de
> eventos de Hudl StatsBomb están sujetos a su propia licencia y no se
> distribuyen aquí.

---

## 7. Citabilidad

`CITATION.cff` en la raíz hace que GitHub muestre un botón "Cite this
repository":

```yaml
cff-version: 1.2.0
title: "dtdecoder: decodificación táctica de entrenadores mediante cadenas de Markov absorbentes"
authors:
  - family-names: Moreno
    given-names: Rodrigo
version: 0.4.0
date-released: 2026-08-19
license: MIT
```

Para un proyecto de hackathon que se quiera usar como portafolio, esto vale más
de lo que cuesta.

---

## 8. Determinismo

| fuente de aleatoriedad | semilla | ubicación |
|---|---|---|
| Pliegues de CV | `estimation.cv_seed` = 20260819 | config |
| Bootstrap | `inference.boot_seed` = 11235 | config |
| Generador sintético | argumento `seed` | explícito en cada llamada |

Ninguna semilla está hardcodeada en el código de análisis. **Regla**: cualquier
`default_rng()` sin semilla explícita es un bug.

Advertencia honesta sobre límites: el determinismo bit a bit entre versiones de
numpy/BLAS **no** está garantizado. Los resultados son estables en distribución;
el último dígito puede variar entre máquinas. Para un trabajo de este tipo es
suficiente, pero conviene declararlo.

---

## 9. Trazabilidad de resultados

Cada corrida escribe un JSON de diagnósticos (`phase0_report.json`,
`phase1_report.json`, `phase2_report.json`).

**Mejora recomendada, no implementada**: incluir en esos reportes el hash del
config y el commit de git.

```python
import hashlib, subprocess
cfg_hash = hashlib.sha256(open("config/default.yaml","rb").read()).hexdigest()[:12]
commit = subprocess.run(["git","rev-parse","--short","HEAD"],
                        capture_output=True, text=True).stdout.strip()
```

Con eso, cualquier figura del reporte es trazable al código y a los parámetros
exactos que la produjeron. Es lo que convierte "confía en mí" en "verifícalo".

---

## 10. Checklist de publicación

- [ ] `uv lock` generado y versionado
- [ ] `.github/workflows/ci.yml` en verde
- [ ] `LICENSE` (MIT) añadida
- [ ] `CITATION.cff` añadida
- [ ] `data/raw/` vacío en el repo; `.gitignore` verificado
- [ ] `data/coach_eras.csv` **sí** versionado, con nota sobre sus fuentes
- [ ] README con instalación desde cero verificada en máquina limpia
- [ ] `docs/` completa
- [ ] Nota de licencia de datos visible en el README
- [ ] Hash del dataset registrado en `docs/DATA_PROVENANCE.txt`
- [ ] Figuras del reporte regenerables con un solo comando

---

## 11. Prueba de fuego

Antes de considerar el proyecto reproducible, hacer esto:

1. Clonar el repo en un directorio nuevo, sin el venv.
2. Seguir el README **al pie de la letra**, sin usar conocimiento previo.
3. Verificar que `pytest -q` y `dtdecoder demo` funcionan.
4. Idealmente, que lo haga otra persona.

Si en algún paso hay que "saber" algo que no está escrito, eso es un bug de
documentación. En este proyecto ya ocurrió una vez: el venv vivía dentro del
repo y no se movió con la carpeta, lo que dejó el entorno roto sin que nada en
la documentación lo advirtiera. Ahora está en el README y en
`01_ARCHITECTURE.md` §7.
