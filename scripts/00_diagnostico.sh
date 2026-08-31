#!/usr/bin/env bash
# 00_diagnostico.sh — Reporta el estado real del repo y del entorno.
# Correr desde la raiz de dt-decoder. La salida se pega tal cual en el chat.
#
#   bash scripts/00_diagnostico.sh 2>&1 | tee reports/diagnostico.txt

set -uo pipefail

sec() { printf '\n===== %s =====\n' "$1"; }

sec "ENTORNO"
uname -srm
python --version 2>&1 || true
uv --version 2>&1 || echo "uv no encontrado"
echo "cwd: $(pwd)"

sec "VERSIONES DE PAQUETES"
python - <<'PY' 2>&1 || true
for m in ("polars", "numpy", "scipy", "pandas", "matplotlib", "pyarrow"):
    try:
        print(f"{m:12} {__import__(m).__version__}")
    except Exception as e:
        print(f"{m:12} AUSENTE ({type(e).__name__})")
PY

sec "ARBOL DEL REPO (2 niveles, sin basura)"
if command -v tree >/dev/null 2>&1; then
  tree -L 2 -I '__pycache__|*.egg-info|.git|.venv|node_modules'
else
  find . -maxdepth 2 \
    -not -path '*/.git/*' -not -path '*/__pycache__/*' \
    -not -path '*/.venv/*' -not -path '*.egg-info*' | sort
fi

sec "MODULOS EN src/dtdecoder (lineas por archivo)"
if [ -d src/dtdecoder ]; then
  wc -l src/dtdecoder/*.py 2>/dev/null | sort -n
else
  echo "NO EXISTE src/dtdecoder"
fi

sec "FUNCIONES Y CLASES PUBLICAS POR MODULO"
python - <<'PY' 2>&1 || true
import pathlib, re
d = pathlib.Path("src/dtdecoder")
if not d.exists():
    print("sin src/dtdecoder"); raise SystemExit
for f in sorted(d.glob("*.py")):
    names = re.findall(r"^(?:def|class)\s+(\w+)", f.read_text(errors="replace"), re.M)
    pub = [n for n in names if not n.startswith("_")]
    print(f"\n{f.name}:")
    print("  " + (", ".join(pub) if pub else "(nada publico)"))
PY

sec "CLI DISPONIBLE"
dtdecoder --help 2>&1 | head -40 || echo "dtdecoder no instalado en el PATH"

sec "CONFIG"
if [ -f config/default.yaml ]; then
  echo "--- config/default.yaml ---"; cat config/default.yaml
else
  echo "NO EXISTE config/default.yaml"
fi

sec "TESTS"
pytest -q 2>&1 | tail -25 || echo "pytest fallo o no esta instalado"

sec "DATOS PRESENTES"
for p in data data/raw data/interim data/processed reports; do
  [ -d "$p" ] && { echo "--- $p ---"; ls -la "$p" | head -20; }
done
echo "--- CSV grandes en el arbol y el padre ---"
find . .. -maxdepth 2 -name '*.csv' -size +1M 2>/dev/null | head -20

sec "ARTEFACTOS DE CORRIDAS PREVIAS"
find . -name 'phase*_report.json' -o -name '*.npz' -o -name 'fingerprint*.parquet' 2>/dev/null | head -20

sec "GIT"
git rev-parse --short HEAD 2>/dev/null || echo "sin repo git"
git status --short 2>/dev/null | head -20 || true

sec "FIN"
echo "Pega esta salida completa en el chat."
