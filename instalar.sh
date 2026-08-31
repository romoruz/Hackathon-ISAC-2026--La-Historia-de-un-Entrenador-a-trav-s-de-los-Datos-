#!/usr/bin/env bash
# instalar.sh — dt-decoder v0.6.1
#
#   cd "/home/rodrigo/Rodrigo Moreno/Codigos Deportes/Hackathon2026"
#   source .venv/bin/activate
#   tar xzf ~/Descargas/dt-decoder-v0.6.1.tar.gz
#   bash dt-decoder-v0.6.1/instalar.sh

set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$(pwd)"
BK="$DEST/.backup_$(date +%Y%m%d_%H%M%S)"
rojo(){ printf '\033[31m%s\033[0m\n' "$*"; }
verde(){ printf '\033[32m%s\033[0m\n' "$*"; }
info(){ printf '\033[36m>> %s\033[0m\n' "$*"; }

[ -d "$DEST/src/dtdecoder" ] || { rojo "No es la raiz del proyecto."; exit 1; }
[ -n "${VIRTUAL_ENV:-}" ] || { rojo "Activa el venv: source .venv/bin/activate"; exit 1; }

info "destino: $DEST"
info "python : $(python --version 2>&1)"

info "backup en $BK"
mkdir -p "$BK/src/dtdecoder"
for f in cli.py estimate.py possessions.py synth.py; do
  [ -f "$DEST/src/dtdecoder/$f" ] && cp "$DEST/src/dtdecoder/$f" "$BK/src/dtdecoder/"
done
[ -d "$DEST/docs" ] && cp -r "$DEST/docs" "$BK/docs"

info "modulos (4)"
cp "$AQUI"/src/dtdecoder/*.py "$DEST/src/dtdecoder/"
info "tests (4)"
mkdir -p "$DEST/tests"; cp "$AQUI"/tests/*.py "$DEST/tests/"
info "scripts (13)"
mkdir -p "$DEST/scripts"; cp "$AQUI"/scripts/* "$DEST/scripts/"; chmod +x "$DEST/scripts/"*
info "documentacion (9)"
mkdir -p "$DEST/docs"; cp "$AQUI"/docs/*.md "$DEST/docs/"
info "datos y app"
mkdir -p "$DEST/data"; cp "$AQUI"/data/*.csv "$DEST/data/" 2>/dev/null
cp "$AQUI/app.py" "$DEST/" 2>/dev/null

# scripts que quedaron obsoletos en iteraciones previas
for o in scripts/01_derivar_torneos.py scripts/02_fetch_match_dates.py \
         scripts/03_asignar_eras.py src/dtdecoder/coaches.py \
         data/match_torneos.csv data/match_ids_a_completar.csv; do
  [ -e "$DEST/$o" ] && { info "retirando obsoleto: $o"
    mkdir -p "$BK/$(dirname "$o")"; mv "$DEST/$o" "$BK/$o"; }
done

for v in 0.4.0 0.4.1 0.5.0; do
  grep -q "$v" "$DEST/src/dtdecoder/__init__.py" 2>/dev/null && {
    info "bump $v -> 0.6.1"
    sed -i "s/$v/0.6.1/" "$DEST/src/dtdecoder/__init__.py"
    [ -f "$DEST/pyproject.toml" ] && sed -i "s/$v/0.6.1/" "$DEST/pyproject.toml"; }
done

grep -q 'eventos_completos' "$DEST/.gitignore" 2>/dev/null || cat >> "$DEST/.gitignore" <<'EOF'

# Datos licenciados de Hudl StatsBomb: NUNCA se versionan
eventos_completos_*.csv
*.csv
!data/coach_eras*.csv
!data/match_dates*.csv
reporte.html
EOF

info "verificando con pytest..."
if pytest -q; then
  verde ""
  verde "=================================================================="
  verde " dt-decoder v0.6.1 INSTALADO"
  verde "=================================================================="
  echo ""
  echo "  Backup: $BK"
  echo ""
  echo "  Empezar a leer:"
  echo "    docs/13_CONTEXTO_IA.md      si eres una IA"
  echo "    docs/02_STATE_OF_PLAY.md    si eres humano"
  echo "    docs/12_API_STATSBOMB.md    cuando llegue el acceso"
  echo ""
  echo "  Regenerar el entregable:"
  echo "    bash scripts/generar_todo.sh"
  echo "    python scripts/12_reporte_html.py"
  echo ""
  echo "  PENDIENTE DE ALTO RIESGO: verificar la orientacion del eje Y"
  echo "  (docs/02_STATE_OF_PLAY.md 7.6). Si esta al reves, todos los mapas"
  echo "  con etiquetas de banda estan espejeados."
  echo ""
  exit 0
else
  rojo ""
  rojo "FALLARON TESTS. Modulos revertidos desde $BK"
  cp "$BK"/src/dtdecoder/*.py "$DEST/src/dtdecoder/" 2>/dev/null
  rojo "Manda la salida de pytest."
  exit 1
fi
