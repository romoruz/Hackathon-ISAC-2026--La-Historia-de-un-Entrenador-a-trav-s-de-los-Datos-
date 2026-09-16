#!/usr/bin/env bash
# generar_todo_h7.sh — artefactos pesados SOLO para los clubes del reporte.
#
#   bash scripts/generar_todo_h7.sh                     # los 3 preinscritos
#   bash scripts/generar_todo_h7.sh --clubes america,leon
#   bash scripts/generar_todo_h7.sh --rapido            # pocas replicas
#   bash scripts/generar_todo_h7.sh --dry-run           # solo lista, no corre
#
# QUE CAMBIA RESPECTO A generar_todo.sh
# -------------------------------------
# 1. Los clubes NO estan en el codigo: se pasan por linea de comandos y por
#    defecto son los tres preinscritos para H7 (ver LEEME del paquete 09).
#    `generar_todo.sh` tenia "Club América" y "Cruz Azul" fijos apuntando a
#    `data/processed/`, que es la epoca de dos clubes.
# 2. Las rutas son `data/processed_api_<slug>/`, los 18 directorios nuevos.
# 3. MIN_POSESIONES pasa de 1000 a **1500**.
#
# POR QUE 1500 Y NO 1000
# ----------------------
# `12_reporte_html.py` usa MIN_POSS = 1500 y `generar_todo.sh` usaba 1000. La
# consecuencia no es una excepcion: el reporte LISTA entrenadores con entre
# 1000 y 1500 posesiones, para los que el generador si creo artefactos, pero
# tambien al reves segun el script -- y las tarjetas salen vacias sin que nada
# avise. Esta en la tabla de trampas de 13_CONTEXTO_IA.md §6.
# Se sincroniza hacia ARRIBA (1500) porque el que manda es el que decide que
# se muestra, y bajar el del HTML metaria eras con menos potencia al reporte.
#
# POR QUE NO SE CORREN LOS 18 CLUBES
# ----------------------------------
# El bucle de parejas es O(n^2) por club y ademas ORDENADO (a-vs-b y b-vs-a
# son artefactos distintos). Con 53 unidades salen cientos de JSON, un HTML de
# decenas de MB y un entregable ilegible para un jurado no tecnico.
# La tabla de los 60 pares vive en `pares_h4_v5.json` y no cuesta computo; lo
# caro son los bootstraps, y esos solo se pagan para los clubes profundos.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
[ -z "${VIRTUAL_ENV:-}" ] && { echo "Activa el venv: source .venv/bin/activate"; exit 1; }
case "${VIRTUAL_ENV:-}" in
  *".venv-sb"*) echo "ERROR: estas en .venv-sb. Este script va en .venv."; exit 1 ;;
esac

# --- clubes preinscritos para H7 (slug|nombre para mostrar|valor de team) ---
declare -A CATALOGO=(
  [america]="Club América|América"
  [leon]="Club León|León"
  [atlas]="Atlas|Atlas"
  [cruz_azul]="Cruz Azul|Cruz Azul"
  [tigres_uanl]="Tigres UANL|Tigres UANL"
  [monterrey]="Monterrey|Monterrey"
  [guadalajara]="Guadalajara|Guadalajara"
  [pumas_unam]="Pumas UNAM|Pumas UNAM"
  [mazatlan]="Mazatlán|Mazatlán"
  [toluca]="Toluca|Toluca"
  [juarez]="Juárez|Juárez"
  [tijuana]="Tijuana|Tijuana"
  [necaxa]="Necaxa|Necaxa"
  [queretaro]="Querétaro|Querétaro"
  [santos_laguna]="Santos Laguna|Santos Laguna"
  [pachuca]="Pachuca|Pachuca"
  [puebla]="Puebla|Puebla"
  [atletico_san_luis]="Atlético San Luis|Atlético San Luis"
)
SLUGS="america,leon,atlas"
RAPIDO=0
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --clubes) SLUGS="$2"; shift 2 ;;
    --rapido) RAPIDO=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "argumento desconocido: $1"; exit 1 ;;
  esac
done

MIN_POSESIONES="${MIN_POSESIONES:-1500}"
if [ "$RAPIDO" -eq 1 ]; then
  NB_IC=200; NB_HU=300; NP_PL=100
  echo ">> modo rapido: pocas replicas, solo para verificar que corre"
else
  NB_IC=1000; NB_HU=2000; NP_PL=500
fi

echo "MIN_POSESIONES=$MIN_POSESIONES   clubes: $SLUGS"
[ "$DRY" -eq 1 ] && echo ">> DRY RUN: no se ejecuta nada"
echo

total_ic=0; total_pl=0; total_hu=0

IFS=',' read -r -a LISTA <<< "$SLUGS"
for slug in "${LISTA[@]}"; do
  entrada="${CATALOGO[$slug]:-}"
  if [ -z "$entrada" ]; then
    echo "[salto] slug desconocido: $slug"; continue
  fi
  IFS='|' read -r nombre equipo <<< "$entrada"
  dir="data/processed_api_${slug}"

  if [ ! -f "$dir/transitions.parquet" ]; then
    echo "[salto] $nombre: no existe $dir/transitions.parquet"; continue
  fi

  echo "=================================================================="
  echo " $nombre   ($dir)"
  echo "=================================================================="

  mapfile -t DTS < <(python - "$dir" "$equipo" "$MIN_POSESIONES" <<'PY'
import json, sys, pathlib, polars as pl
d = pl.read_parquet(f"{sys.argv[1]}/transitions.parquet")
sub = d.filter((pl.col("team") == sys.argv[2]) & pl.col("coach").is_not_null())
g = (sub.group_by("coach").agg(pl.col("poss_uid").n_unique().alias("n"))
       .filter(pl.col("n") >= int(sys.argv[3])).sort("n", descending=True))
# MISMO conjunto de unidades que H4: el campo `suficiente` de phase0.
# Filtrar solo por posesiones dejaba entrar eras que H4 excluyo por tener
# menos de 25 partidos (Leon/Bava 23, Atlas/Pineda), y esas tendrian tarjeta
# en el reporte sin aparecer en la tabla de 60 pares.
rp = pathlib.Path(sys.argv[1]) / "phase0_report.json"
ok = None
if rp.exists():
    co = json.loads(rp.read_text()).get("coaches") or {}
    ok = {c["coach"] for c in co.get("coverage", []) if c.get("suficiente")}
for r in g.iter_rows(named=True):
    if ok is None or r["coach"] in ok:
        print(r["coach"])
PY
)
  if [ "${#DTS[@]}" -lt 2 ]; then
    echo "  Menos de dos entrenadores con >= $MIN_POSESIONES posesiones. Se omite."
    echo ""
    continue
  fi
  echo "  Entrenadores: ${DTS[*]}"
  n=${#DTS[@]}
  echo "  -> ${n} huellas, $((n*(n-1))) ic, $((n*(n-1))) plantel"
  total_hu=$((total_hu+n)); total_ic=$((total_ic+n*(n-1)))
  total_pl=$((total_pl+n*(n-1)))
  echo ""
  [ "$DRY" -eq 1 ] && continue

  # ---- huella: uno por entrenador, contra todos los demas del club ----
  for a in "${DTS[@]}"; do
    # El slug era la ULTIMA palabra: "Diego Cocca II" -> huella_ii.parquet,
    # que colisiona con "Joaquin Moreno II" de Cruz Azul y con cualquier otro
    # que termine igual. El script salta lo que ya existe, asi que la colision
    # no falla: REUTILIZA el artefacto del otro entrenador. Mismo criterio que
    # ic_ y plantel_: nombre completo sin espacios.
    ap=$(echo "$a" | tr -d ' ' | tr 'A-Z' 'a-z')
    out="reports/huella_${slug}_${ap}.parquet"
    if [ -f "$out" ]; then echo "  [ya] huella $a"; continue; fi
    echo "  [huella] $a"
    python scripts/09_huella_efecto.py --unit coach --value "$a" \
      --baseline other_coaches --club "$equipo" --indir "$dir" \
      --n-boot "$NB_HU" --out "reports/huella_${slug}_${ap}.json" \
      --out-parquet "$out" >/dev/null 2>&1 \
      || echo "     fallo (correlo a mano para ver el mensaje)"
  done

  # ---- parejas ORDENADAS: a vs b y b vs a no son lo mismo ----
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
  echo ""
done

echo "=================================================================="
echo " total previsto: $total_hu huellas, $total_ic ic, $total_pl plantel"
[ "$DRY" -eq 1 ] && exit 0
echo ""
ls -1 reports/ic_*.json reports/plantel_*.json reports/huella_*.parquet 2>/dev/null \
  | sed 's/^/   /'
echo ""
echo " Siguiente: el bloque defensivo y luego"
echo "   python scripts/28_tabla_pares.py"
echo "   python scripts/12_reporte_html.py"
