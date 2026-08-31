#!/usr/bin/env bash
# generar_todo.sh — Artefactos para TODAS las parejas de entrenadores.
#
#   bash scripts/generar_todo.sh
#   bash scripts/generar_todo.sh --rapido      # menos replicas, para probar
#
# QUE GENERA, POR CLUB
#   huella_<apellido>.parquet   uno por entrenador (vs. todos los demas)
#   ic_<a>_<b>.json             una por PAREJA ORDENADA
#   plantel_<a>_<b>.json        una por pareja ordenada
#
# POR QUE SOLO ENTRENADORES CON MUESTRA SUFICIENTE
# ------------------------------------------------
# 05_VALIDATION §4.7 marca las eras con menos de 25 partidos como sin potencia.
# En Cruz Azul, seis de ocho no llegan; Joaquin Moreno I tiene DOS partidos.
# Generar sus comparaciones produciria intervalos enormes y tablas vacias que
# ensucian el dashboard sin aportar nada.
#
# El umbral es MIN_POSESIONES (default 1000) y se puede subir con la variable
# de entorno. Incluir eras chicas NO es un problema: sus intervalos saldran
# anchos y eso es informacion, no ruido. Ejemplo real: Sanchez vs Ferretti da
# +1.6% con IC [-3.3%, +6.8%] -- no hay diferencia detectable, y que el metodo
# lo diga es una prueba de que discrimina en vez de encontrar efectos en todas
# partes.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[ -z "${VIRTUAL_ENV:-}" ] && { echo "Activa el venv: source .venv/bin/activate"; exit 1; }

# Umbral compartido con 12_reporte_html.py. Si los dos difieren, el reporte
# lista entrenadores para los que nunca se generaron artefactos y sus tarjetas
# salen vacias. Se puede sobreescribir:  MIN_POSESIONES=2000 bash ...
MIN_POSESIONES="${MIN_POSESIONES:-1000}"
if [ "${1:-}" = "--rapido" ]; then
  NB_IC=200; NB_HU=300; NP_PL=100
  echo ">> modo rapido: pocas replicas, solo para verificar que corre"
else
  NB_IC=1000; NB_HU=2000; NP_PL=500
fi

CLUBES=("Club América|América|data/processed" "Cruz Azul|Cruz Azul|data/processed_cruzazul")

for entrada in "${CLUBES[@]}"; do
  IFS='|' read -r nombre equipo dir <<< "$entrada"
  [ -f "$dir/transitions.parquet" ] || { echo "[salto] $nombre: sin transitions.parquet"; continue; }

  echo ""
  echo "=================================================================="
  echo " $nombre"
  echo "=================================================================="

  mapfile -t DTS < <(python - "$dir" "$equipo" "$MIN_POSESIONES" <<'PY'
import sys, polars as pl
d = pl.read_parquet(f"{sys.argv[1]}/transitions.parquet")
sub = d.filter((pl.col("team") == sys.argv[2]) & pl.col("coach").is_not_null())
g = (sub.group_by("coach").agg(pl.col("poss_uid").n_unique().alias("n"))
       .filter(pl.col("n") >= int(sys.argv[3])).sort("n", descending=True))
for r in g.iter_rows(named=True):
    print(r["coach"])
PY
)
  if [ "${#DTS[@]}" -lt 2 ]; then
    echo "  Menos de dos entrenadores con >= $MIN_POSESIONES posesiones. Se omite."
    continue
  fi
  echo "  Entrenadores con muestra suficiente: ${DTS[*]}"
  echo ""

  # ---- huella: uno por entrenador, contra todos los demas ----------
  for a in "${DTS[@]}"; do
    ap=$(echo "$a" | awk '{print tolower($NF)}')
    out="reports/huella_${ap}.parquet"
    if [ -f "$out" ]; then echo "  [ya] huella $a"; continue; fi
    echo "  [huella] $a"
    python scripts/09_huella_efecto.py --unit coach --value "$a" \
      --baseline other_coaches --club "$equipo" --indir "$dir" \
      --n-boot "$NB_HU" --out "reports/huella_${ap}.json" \
      --out-parquet "$out" >/dev/null 2>&1 \
      || echo "     fallo (ver corriendolo a mano)"
  done

  # ---- parejas ORDENADAS: a vs b y b vs a no son lo mismo ----------
  for a in "${DTS[@]}"; do
    for b in "${DTS[@]}"; do
      [ "$a" = "$b" ] && continue
      ap=$(echo "$a" | tr -d ' ' | tr 'A-Z' 'a-z')
      bp=$(echo "$b" | tr -d ' ' | tr 'A-Z' 'a-z')

      if [ ! -f "reports/ic_${ap}_${bp}.json" ]; then
        echo "  [ic]      $a  vs  $b"
        python scripts/08_ic_derivados.py --a "$a" --b "$b" --club "$equipo" \
          --indir "$dir" --n-boot "$NB_IC" \
          --out "reports/ic_${ap}_${bp}.json" >/dev/null 2>&1 \
          || echo "     fallo"
      fi

      if [ ! -f "reports/plantel_${ap}_${bp}.json" ]; then
        echo "  [plantel] $a  vs  $b"
        python scripts/11_confusion_plantel.py --a "$a" --b "$b" \
          --club "$equipo" --indir "$dir" --n-perm "$NP_PL" --n-boot-ic 300 \
          --out "reports/plantel_${ap}_${bp}.json" >/dev/null 2>&1 \
          || echo "     fallo"
      fi
    done
  done
done

echo ""
echo "=================================================================="
echo " Listo. Artefactos en reports/:"
ls -1 reports/ic_*.json reports/plantel_*.json reports/huella_*.parquet 2>/dev/null \
  | sed 's/^/   /'
echo ""
echo " Los que fallaron suelen ser por muestra insuficiente en alguna era."
echo " Correlos a mano para ver el mensaje completo."
