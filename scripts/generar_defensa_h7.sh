#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generar_defensa_h7.sh — el bloque D1 para los clubes del reporte.
#
# Sustituye a generar_defensa_todos.sh, que tenia
#     for club in "América" "Cruz Azul"
# y una tabla DTS escrita a mano con las eras ANTERIORES al bug #14: incluye
# "Miguel Herrera" en el America, que no existe en la ventana del API.
# Correrlo hoy generaria el bloque defensivo de un club que no esta en la
# terna y de un entrenador que no existe.
#
# LA DECISION QUE ESTE SCRIPT OBLIGA A TOMAR
# ------------------------------------------
# El script viejo ya la planteaba y sigue viva: el FDR del script 22 corre
# sobre la familia COMPLETA de contrastes de presion. Al crecer la familia los
# q suben y un titular puede caer. Las dos salidas honestas son:
#   (a) mostrar todas las parejas con los q de la familia grande;
#   (b) declarar ANTES cuales son confirmatorias y mostrar el resto como
#       exploratorio, SIN q y sin afirmar significancia.
# `--solo-principales` implementa (b). El defecto es (a).
#
# COSTE: 5000 permutaciones por pareja y cuatro scripts. Con la terna son 12
# parejas no ordenadas (America 3, Leon 3, Atlas 6). No es rapido.
#
# Uso:
#   bash scripts/generar_defensa_h7.sh --dry-run
#   bash scripts/generar_defensa_h7.sh --n-perm 1000
#   bash scripts/generar_defensa_h7.sh --clubes america,leon
# ---------------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[ -z "${VIRTUAL_ENV:-}" ] && { echo "Activa el venv: source .venv/bin/activate"; exit 1; }

N_PERM=5000
SLUGS="america,leon,atlas"
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --n-perm) N_PERM="$2"; shift 2 ;;
    --clubes) SLUGS="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "opcion desconocida: $1" >&2; exit 1 ;;
  esac
done

pareja() {
  local club="$1" a="$2" b="$3" dir="$4"
  echo "-- $club · $a vs $b"
  [ "$DRY" -eq 1 ] && return
  python scripts/18_campo_presion.py --club "$club" --a "$a" --b "$b" \
    --indir "$dir" --n-perm "$N_PERM" > /dev/null 2>&1 || echo "   !! 18 fallo"
  python scripts/20_nivel_y_calibracion.py --club "$club" --a "$a" --b "$b" \
    --indir "$dir" --n-perm "$N_PERM" > /dev/null 2>&1 || echo "   !! 20 fallo"
  python scripts/21_calibracion_presion.py --club "$club" --a "$a" --b "$b" \
    --indir "$dir" > /dev/null 2>&1 || echo "   !! 21 fallo"
  python scripts/19_presion_por_indice.py --club "$club" --a "$a" --b "$b" \
    --indir "$dir" --n-perm 1000 > /dev/null 2>&1 || echo "   !! 19 fallo"
  echo "   ok"
}

total=0
IFS=',' read -r -a LISTA <<< "$SLUGS"
for slug in "${LISTA[@]}"; do
  dir="data/processed_api_${slug}"
  rp="$dir/phase0_report.json"
  [ -f "$rp" ] || { echo "[salto] $slug: sin phase0_report.json"; continue; }

  # Club y entrenadores salen de phase0, NUNCA de una tabla a mano: el campo
  # `suficiente` es el mismo criterio que uso 25_pares_h4.py.
  mapfile -t INFO < <(python - "$rp" <<'PY'
import json, sys
co = json.loads(open(sys.argv[1]).read())["coaches"]
print(co["club"])
for c in co["coverage"]:
    if c.get("suficiente"):
        print(c["coach"])
PY
)
  club="${INFO[0]}"
  DTS=("${INFO[@]:1}")
  echo "=================================================================="
  echo " $club  (${#DTS[@]} entrenadores)"
  echo "=================================================================="
  if [ "${#DTS[@]}" -lt 2 ]; then echo "  menos de dos; se omite"; continue; fi

  for ((i=0; i<${#DTS[@]}; i++)); do
    for ((j=i+1; j<${#DTS[@]}; j++)); do
      pareja "$club" "${DTS[$i]}" "${DTS[$j]}" "$dir"
      total=$((total+1))
    done
  done
  echo
done

echo "parejas: $total   (x4 scripts)"
[ "$DRY" -eq 1 ] && { echo ">> DRY RUN: no se ejecuto nada"; exit 0; }

echo
echo "=================================================================="
echo " FDR sobre la familia completa"
echo "=================================================================="
python scripts/22_fdr_presion.py --min-n-perm "$N_PERM"
echo
echo "Si un titular cayo al crecer la familia, NO se vuelve a la familia"
echo "pequena para recuperarlo. Se decide (a) o (b) y se escribe en la ADR."
