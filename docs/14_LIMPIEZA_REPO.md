# 14 — Limpieza del repositorio y preparación para GitHub

> Encargo ejecutable para un agente (Antigravity, Claude Code, Cursor). Objetivo:
> dejar el repositorio publicable **sin perder ningún artefacto que el reporte
> necesite y sin tocar una sola línea de lógica**.
>
> Este documento es la autoridad. Si algo no está aquí, **no se borra**.

---

## 0. Las cinco reglas que no se negocian

1. **No se toca `src/dtdecoder/` ni `tests/` ni `config/`.** Ni una línea. Si
   crees que hay que cambiar código, lo propones por escrito y paras.
2. **No se borra nada sin listarlo antes.** Primero se genera el inventario
   (§2), el humano lo aprueba, y solo entonces se mueve.
3. **Nada se borra: se mueve a `_cuarentena/`.** Es un directorio ignorado por
   git. El borrado real lo hace el humano cuando haya comprobado que todo sigue
   funcionando.
4. **Antes y después se corre la misma prueba** (§6). Si el resultado cambia, se
   revierte entero.
5. **Ante la duda, se conserva.** El coste de un archivo de más es cero; el de
   un artefacto que faltaba es una tarde de recálculo o un reporte vacío.

---

## 1. Qué es imprescindible y por qué

Antes de decidir qué sobra hay que saber qué es intocable. Este proyecto tiene
tres clases de archivo que **parecen** desechables y no lo son.

### 1.1 Se versiona SIEMPRE (investigación propia, no reproducible)

| ruta | por qué |
|---|---|
| `data/coach_eras.csv` | investigación documental manual sobre Wikipedia. **Una tarde por club.** No sale de ningún pipeline |
| `data/coach_eras_cruz_azul.csv` | ídem, y Cruz Azul con once entrenadores fue el caso difícil |
| `data/match_dates.csv` | derivadas del patrón de `match_id` (ADR-26). Regenerables, pero baratas de conservar y necesarias para reproducir el resultado exacto |
| `data/match_dates_cruz_azul.csv` | ídem |
| `config/default.yaml` | **define los resultados**. Sin él los números no son reproducibles |

> Si borras `coach_eras*.csv` destruyes trabajo humano que ningún script
> reconstruye. Es el error más caro posible en esta limpieza.

### 1.2 NUNCA se versiona (licencia)

| patrón | por qué |
|---|---|
| `eventos_completos_*.csv` | **datos licenciados de Hudl StatsBomb.** Cientos de MB. Publicarlos es una infracción de licencia |
| cualquier `.csv` de más de 50 MB en la raíz | casi seguro es un volcado de eventos |

Estos archivos **se quedan en el disco del usuario**. No se mueven, no se
borran, no se suben. Solo se añaden a `.gitignore`.

### 1.3 Regenerable pero caro — decisión del humano

| ruta | coste de regenerar |
|---|---|
| `data/processed/`, `data/processed_cruzazul/` | `phase0` completo: minutos, y necesita los CSV licenciados |
| `reports/*.json` | `generar_todo.sh` entero: bastante más |
| `reports/figures/` | barato |

**Recomendación**: no se versionan (van a `.gitignore`), pero **no se borran del
disco**. El repositorio queda limpio y el usuario conserva sus artefactos.

---

## 2. Inventario antes de mover nada

Genera `_inventario.md` en la raíz con esta información y **para ahí**. No
muevas nada hasta que el humano lo lea.

```bash
cd "~/Hackathon2026"

{
  echo "# Inventario del repositorio — $(date +%F)"
  echo
  echo "## Tamaño por directorio"
  du -sh -- */ 2>/dev/null | sort -rh
  echo
  echo "## Los 30 archivos más grandes"
  find . -type f -not -path './.git/*' -not -path './.venv/*' \
    -printf '%s\t%p\n' 2>/dev/null | sort -rn | head -30 \
    | awk -F'\t' '{printf "%8.1f MB  %s\n", $1/1048576, $2}'
  echo
  echo "## Candidatos a cuarentena (ver §3)"
  find . \( -name '__pycache__' -o -name '*.pyc' -o -name '.pytest_cache' \
    -o -name '.ipynb_checkpoints' -o -name '*.orig' -o -name '*.rej' \
    -o -name '*.bak' -o -name '*~' -o -name '*.tmp' -o -name '.DS_Store' \
    -o -name 'Thumbs.db' -o -name 'nohup.out' -o -name '*.log' \) \
    -not -path './.git/*' -not -path './.venv/*' 2>/dev/null | sort
  echo
  echo "## Archivos sin tocar en 30 días fuera de src/tests/docs"
  find . -type f -mtime +30 -not -path './.git/*' -not -path './.venv/*' \
    -not -path './src/*' -not -path './tests/*' -not -path './docs/*' \
    -not -path './data/*' 2>/dev/null | sort
  echo
  echo "## Scripts que NADIE llama"
  echo "(revisar a mano contra 01_ARCHITECTURE.md y generar_todo.sh)"
  for f in scripts/*.py; do
    b=$(basename "$f")
    n=$(grep -rl -- "$b" --include='*.py' --include='*.sh' --include='*.md' \
        . 2>/dev/null | grep -v "^\./$f\$" | wc -l)
    [ "$n" -eq 0 ] && echo "  huérfano: $f"
  done
} > _inventario.md

echo "Escrito _inventario.md. NO MUEVAS NADA hasta que lo revise el humano."
```

---

## 3. Qué va a cuarentena, cuando el humano apruebe

Solo estas categorías. **Cualquier otra cosa requiere preguntar.**

### 3.1 Basura de herramientas — seguro

`__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.ruff_cache/`,
`.mypy_cache/`, `.ipynb_checkpoints/`, `.DS_Store`, `Thumbs.db`, `*~`,
`*.swp`, `nohup.out`, `*.anterior_*`.

> **Y las carpetas que dejan los tarballs de instalación al extraerse.** Un
> `tar -xzf` en la raíz deja su directorio, y un `git add -A` se lleva diez
> copias de `12_reporte_html.py` al commit. Pasó: 266 archivos y 86,178
> inserciones. Están en `.gitignore`; si aparece una carpeta nueva de este
> tipo, se añade ahí antes de comitear.

### 3.2 Restos de edición — seguro

`*.orig`, `*.rej`, `*.bak`, `*.tmp`, `*.old`, y archivos con sufijos como
`_v2`, `_final`, `_copia`, `_backup`, ` (1)`, `-copy` **cuando exista el
archivo sin sufijo y sea más reciente**. Si no existe el original, **no es un
duplicado: es la única copia.** Se conserva.

### 3.3 Salidas regenerables — con aviso

`reports/demo/`, `data/interim/*`, `reporte_demo.html`, figuras sueltas en la
raíz. Van a cuarentena, **no se borran**.

### 3.4 Lo que PARECE basura y NO lo es

| parece | es |
|---|---|
| `data/coach_eras*.csv` | investigación manual irrepetible |
| `data/match_dates*.csv` | entrada del pipeline |
| `synth.py` | genera los datos sintéticos que hacen reproducible el método sin los datos licenciados |
| `app.py` | Streamlit de exploración; ADR-38 dice explícitamente que **se conserva** |
| `docs/ACTUALIZACIONES_DOCS*.md` | histórico de parches de documentación. Ver §5 |
| `reports/manifiesto_unidades.json` | persiste las etiquetas de sobreajuste de ADR-46 |
| cualquier `.json` en `reports/` | el reporte HTML lee de ahí; si falta uno, la sección se cae |

```bash
mkdir -p _cuarentena
# mover conservando la ruta, para poder revertir con un mv inverso
mover() { mkdir -p "_cuarentena/$(dirname "$1")"; mv "$1" "_cuarentena/$1"; }
```

---

## 4. Estructura objetivo

```
Hackathon2026/                      ← el repo ES esta carpeta
├── AGENTS.md                       ← punto de entrada para agentes de IA
├── README.md
├── LICENSE                         ← MIT (código)
├── CITATION.cff
├── pyproject.toml
├── uv.lock                         ← generar con `uv lock`
├── .gitignore
├── .github/workflows/ci.yml
├── config/default.yaml
├── src/dtdecoder/
├── tests/
├── scripts/
├── docs/
├── data/
│   ├── coach_eras.csv              ← SÍ se versiona
│   ├── coach_eras_cruz_azul.csv    ← SÍ
│   ├── match_dates.csv             ← SÍ
│   ├── match_dates_cruz_azul.csv   ← SÍ
│   ├── raw/.gitkeep                ← vacío en el repo
│   ├── interim/.gitkeep
│   ├── processed/.gitkeep
│   └── processed_cruzazul/.gitkeep
├── reports/.gitkeep
└── _cuarentena/                    ← ignorado; lo vacía el humano
```

Crear los `.gitkeep` que falten. Un directorio vacío no existe para git, y sin
ellos el pipeline falla en un clon limpio con un error de ruta que no dice nada.

---

## 5. Los dos documentos de parches

`docs/ACTUALIZACIONES_DOCS.md` y `docs/ACTUALIZACIONES_DOCS_v2.md` no son
documentación: son **listas de cambios pendientes de aplicar** a los documentos
canónicos. Su contenido ya se integró (ADRs 39–48 en `06_DECISIONS.md`,
resultados D1 en `10_RESULTADOS.md`, §3.8 en `04_DATA_CONTRACT.md`).

> **HECHO el 2026-08-26.** Los dos archivos habían desaparecido del
> repositorio y del historial de git; se recuperaron y viven en
> `docs/historico/` con su nota. `verificar_docs.py` los ignora a
> propósito (busca «historico» en la ruta), así que las tres afirmaciones
> retiradas pueden vivir ahí sin disparar el aviso.

**No los borres.** Van a `docs/historico/` con una nota de cabecera:

```markdown
> **HISTÓRICO — ya aplicado.** El contenido de este documento se integró en los
> documentos canónicos el 2026-08-26. Se conserva como registro de cómo se
> llegó a esas conclusiones, no como fuente. **No cites de aquí.**
```

Razón: contienen el razonamiento de tres retractaciones, y ese razonamiento es
material de defensa ante un jurado. Borrarlo perdería el *por qué* se retiró
cada afirmación.

---

## 6. Prueba de que no se rompió nada

**Antes** de mover nada, y **después**, exactamente lo mismo:

```bash
cd "~/Hackathon2026"
source .venv/bin/activate

pytest -q                                    | tee _antes_tests.txt
python scripts/verifica_reporte.py           | tee _antes_reporte.txt
python docs/verificar_docs.py                | tee _antes_docs.txt
ls -1 reports/*.json | wc -l                 | tee _antes_jsons.txt
```

Y el criterio de aceptación:

```bash
diff _antes_tests.txt _despues_tests.txt      # debe estar vacío
diff _antes_jsons.txt _despues_jsons.txt      # debe estar vacío
python scripts/12_reporte_html.py --out /tmp/reporte_prueba.html
```

**Si el número de JSON en `reports/` bajó, revierte inmediatamente.** El reporte
HTML lee de ahí: cada JSON que falta es una sección del entregable que muestra
"falta este análisis" en lugar de datos.

Revertir es un `mv` inverso:

```bash
cd _cuarentena && find . -type f -exec sh -c 'mkdir -p "../$(dirname "$1")"; mv "$1" "../$1"' _ {} \;
```

---

## 7. Antes de publicar en GitHub

### 7.1 Comprobación de licencia — **bloqueante**

```bash
git ls-files | xargs -I{} du -k {} 2>/dev/null | sort -rn | head -20
git ls-files | grep -i 'eventos_completos'      # debe devolver VACÍO
```

Si algún CSV de eventos llegó a estar en git **en cualquier commit pasado**,
añadirlo a `.gitignore` no basta: sigue en el historial. Hace falta reescribirlo
(`git filter-repo`) o empezar el repositorio de cero. **Para y avisa al humano:
esta decisión no la toma un agente.**

### 7.2 `reporte.html` — decisión del humano, no del agente

El HTML lleva **datos agregados de StatsBomb embebidos**. Publicarlo es
publicar datos derivados de una fuente licenciada.

`08_REPRODUCIBILITY.md` §4.2 argumenta que un agregado de 84×84 sobre 120,000
eventos está muy lejos de ser reidentificable, y que publicar tablas en vez de
microdatos es práctica estándar en estadística oficial. El propio documento dice
**"verificar con StatsBomb antes de publicar"**.

**El agente no decide esto.** Opciones a presentar al humano:

| opción | qué implica |
|---|---|
| repo privado | nada que decidir, funciona hoy |
| repo público **sin** `reporte.html` | el código se publica, el entregable se entrega aparte |
| repo público **con** `reporte.html` | requiere permiso por escrito de StatsBomb |
| repo público con reporte de **datos sintéticos** | `dtdecoder demo` genera uno; demuestra el método sin publicar datos ajenos |

La última es la que recomienda este documento: un `reporte_demo.html` generado
desde `synth.py` prueba que el método funciona sin publicar un solo dato
licenciado, y es exactamente lo que hacen los papers médicos con datos de
pacientes.

### 7.3 Checklist

- [ ] `uv lock` generado y versionado
- [ ] `.gitignore` cubre `eventos_completos_*.csv`, `.venv/`, `_cuarentena/`
- [ ] `git ls-files | grep eventos_completos` devuelve vacío
- [ ] `LICENSE` (MIT) presente, con nota de que **los datos no están cubiertos**
- [ ] `CITATION.cff` presente
- [ ] `data/coach_eras*.csv` **sí** versionados, con nota sobre sus fuentes
- [ ] `.gitkeep` en todos los directorios de datos vacíos
- [ ] `.github/workflows/ci.yml` en verde
- [ ] README con instalación desde cero verificada en máquina limpia
- [ ] Hash del dataset en `docs/DATA_PROVENANCE.txt`
- [ ] Decidido y documentado qué se hace con `reporte.html` (§7.2)

---

## 8. La prueba de fuego

`08_REPRODUCIBILITY.md` §11 la define y sigue vigente:

1. Clonar el repo en un directorio nuevo, sin el venv.
2. Seguir el README **al pie de la letra**, sin usar conocimiento previo.
3. Verificar que `pytest -q` y `dtdecoder demo` funcionan.
4. Idealmente, que lo haga otra persona.

**Si en algún paso hay que "saber" algo que no está escrito, eso es un bug de
documentación.** Ya ocurrió una vez: el venv vivía dentro del repo, no se movió
con la carpeta, y el entorno quedó roto sin que nada lo advirtiera.

---

## 9. Lo que este documento NO autoriza

- Borrar cualquier cosa directamente, sin pasar por `_cuarentena/`.
- Tocar `src/`, `tests/`, `config/`.
- Reformatear código, reordenar imports, "modernizar" nada.
- Cambiar nombres de archivos que aparezcan en `01_ARCHITECTURE.md`,
  `generar_todo.sh` o `12_reporte_html.py`.
- Reescribir el historial de git.
- Decidir sobre la publicación de datos licenciados.

Si una tarea parece requerir algo de esta lista: **para y pregunta.**
