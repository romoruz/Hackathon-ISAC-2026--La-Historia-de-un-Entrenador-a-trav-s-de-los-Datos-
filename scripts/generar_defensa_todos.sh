#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generar_defensa_todos.sh — el bloque D1 para TODAS las parejas.
#
# El reporte permite elegir cualquier pareja de entrenadores en el selector,
# pero los scripts 18-21 se corrieron solo para dos. El resultado es que la
# mayoria de las combinaciones muestran el hueco con el comando en vez del
# mapa. Esto lo llena.
#
# COSTE: 5000 permutaciones por pareja. Con seis entrenadores en Cruz Azul son
# 15 parejas, mas 6 en el America: unas 21 corridas. Cuenta con un rato.
#
# El FDR (script 22) se corre UNA VEZ AL FINAL sobre la familia completa
# (ADR-47/48). Ojo: al crecer la familia los q suben. El nivel de Anselmi
# estaba en q = 0.0414 con 46 contrastes; con 20 parejas la familia pasa de
# 400 y ese titular puede caer.
#
#   >> Esa es una decision que hay que TOMAR, no descubrir:
#      o el reporte muestra todas las parejas y la familia crece,
#      o se declara ANTES cuales son las parejas confirmatorias.
#      Ver --solo-principales.
#
# Uso:
#   bash scripts/generar_defensa_todos.sh                   # todas
#   bash scripts/generar_defensa_todos.sh --solo-principales
#   bash scripts/generar_defensa_todos.sh --n-perm 2000     # mas rapido
# ---------------------------------------------------------------------------
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -f .venv/bin/activate ]] && source .venv/bin/activate

N_PERM=5000
SOLO_PRINC=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --n-perm) N_PERM="$2"; shift 2 ;;
    --solo-principales) SOLO_PRINC=1; shift ;;
    *) echo "opcion desconocida: $1" >&2; exit 1 ;;
  esac
done

# Parejas CONFIRMATORIAS: las declaradas en 10_RESULTADOS como eje del reporte.
# Cobertura de rivales del 100% y muestra suficiente en las dos eras.
PRINCIPALES=(
  "Cruz Azul|Martin Anselmi|Juan Reynoso"
  "América|Andre Jardine|Santiago Solari"
)

declare -A DTS=(
  ["América"]="Andre Jardine|Santiago Solari|Fernando Ortiz|Miguel Herrera"
  ["Cruz Azul"]="Martin Anselmi|Juan Reynoso|Vicente Sanchez|Raul Gutierrez|Ricardo Ferretti|Joaquin Moreno II"
)

pareja() {
  local club="$1" a="$2" b="$3"
  echo "── $club · $a vs $b ───────────────────────────"
  python scripts/18_campo_presion.py --club "$club" --a "$a" --b "$b" \
    --n-perm "$N_PERM" > /dev/null 2>&1 || echo "   !! 18 fallo"
  python scripts/20_nivel_y_calibracion.py --club "$club" --a "$a" --b "$b" \
    --n-perm "$N_PERM" > /dev/null 2>&1 || echo "   !! 20 fallo"
  python scripts/21_calibracion_presion.py --club "$club" --a "$a" --b "$b" \
    > /dev/null 2>&1 || echo "   !! 21 fallo"
  # La curva de decaimiento. Alimenta la grafica de "hasta cuando aprieta",
  # que es la figura que explica el bloque de un vistazo.
  python scripts/19_presion_por_indice.py --club "$club" --a "$a" --b "$b" \
    --n-perm 1000 > /dev/null 2>&1 || echo "   !! 19 fallo"
  echo "   ok"
}

if [[ $SOLO_PRINC -eq 1 ]]; then
  echo "Solo las parejas confirmatorias (familia FDR pequena)."
  for e in "${PRINCIPALES[@]}"; do
    IFS='|' read -r c a b <<< "$e"; pareja "$c" "$a" "$b"
  done
else
  echo "TODAS las parejas. Recuerda: la familia FDR crece y los q suben."
  for club in "América" "Cruz Azul"; do
    IFS='|' read -ra L <<< "${DTS[$club]}"
    for ((i=0; i<${#L[@]}; i++)); do
      for ((j=i+1; j<${#L[@]}; j++)); do
        pareja "$club" "${L[$i]}" "${L[$j]}"
      done
    done
  done
fi

echo
echo "=================================================================="
echo " FDR sobre la familia completa"
echo "=================================================================="
python scripts/22_fdr_presion.py --min-n-perm "$N_PERM"

echo
echo "Regenera el reporte:  python scripts/12_reporte_html.py"
echo
echo "SI EL TITULAR DE ANSELMI CAYO al crecer la familia, la respuesta"
echo "honesta NO es volver a la familia pequena para recuperarlo. Es una"
echo "de estas dos, decidida y escrita en la ADR:"
echo "  (a) el reporte muestra todas las parejas y los q son los de la"
echo "      familia grande, con los titulares que sobrevivan a eso;"
echo "  (b) se declara que solo las parejas principales son"
echo "      confirmatorias y el resto se muestra como exploratorio,"
echo "      SIN q y sin afirmar significancia."
