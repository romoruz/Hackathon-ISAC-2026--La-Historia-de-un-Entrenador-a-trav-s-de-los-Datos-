#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generar_perspectivas.sh — fases 1-3 en las DOS perspectivas.
#
# NO reemplaza a generar_todo.sh: corre en paralelo y genera lo que falta.
#
# TRES COSAS QUE ESTE SCRIPT HACE Y QUE UN BUCLE INGENUO NO
# ---------------------------------------------------------
# 1. ENCADENA phase1 -> phase2 -> phase3 POR ENTRENADOR.
#    `phase1` sobrescribe P_matrices.npz en cada corrida. Correr todos los
#    phase1 primero deja solo el del ULTIMO entrenador, y phase2/3 leerian ese.
#    El guardarrail de identidad lo aborta -- pero es mejor no llegar ahi.
#
# 2. USA LA COLUMNA CORRECTA POR PERSPECTIVA.
#    `coach` es null en las filas de los rivales (attach_coach lo pone asi a
#    proposito). En la cadena conjugada hay que usar `coach_faced`.
#
# 3. PERSISTE la etiqueta de sobreajuste en un manifiesto JSON.
#    Un aviso en consola se pierde. Para la Opcion C (reportar las eras cortas
#    CON etiqueta explicita) el flag tiene que ser un dato del artefacto.
#
# Uso:
#   bash scripts/generar_perspectivas.sh                 # todo
#   bash scripts/generar_perspectivas.sh --solo america  # un club
#   bash scripts/generar_perspectivas.sh --force         # ignora la cache
#   bash scripts/generar_perspectivas.sh --dry-run
# ---------------------------------------------------------------------------
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
[[ -f .venv/bin/activate ]] && source .venv/bin/activate

N_BOOT="${N_BOOT:-2000}"
UMBRAL_PPO="${UMBRAL_PPO:-0.5}"     # ADR-25 / P-02
MANIFIESTO="reports/manifiesto_unidades.json"

FORCE=0; DRY=0; SOLO=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)   FORCE=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --solo)    SOLO="$2"; shift 2 ;;
    *) echo "opcion desconocida: $1" >&2; exit 1 ;;
  esac
done

# --- clubes: nombre real | directorio | entrenadores -----------------------
# El nombre debe ser EXACTAMENTE el valor de la columna `team`, no el de
# display: "América" sin "Club" (error de proceso #4 del proyecto).
declare -A DIR=(
  ["América"]="data/processed"
  ["Cruz Azul"]="data/processed_cruzazul"
)
declare -A DTS=(
  ["América"]="Andre Jardine|Santiago Solari|Fernando Ortiz|Miguel Herrera"
  ["Cruz Azul"]="Martin Anselmi|Juan Reynoso|Vicente Sanchez|Raul Gutierrez|Ricardo Ferretti|Joaquin Moreno II"
)

ok=0; avisos=0; fallos=0
declare -a FALLIDAS=()

# --- hash del parquet: invalida la cache cuando los datos cambian ----------
hash_parquet() {
  sha256sum "$1/transitions.parquet" 2>/dev/null | cut -c1-12
}

# --- lee un campo anidado del JSON de phase1 -------------------------------
# `params_per_obs` vive bajo `.sparsity`, no en la raiz. jq '.params_per_obs'
# devuelve null y cualquier comparacion posterior revienta o pasa en silencio.
leer_ppo() {
  python - "$1" <<'PY' 2>/dev/null || echo "nan"
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("sparsity", {}).get("params_per_obs", float("nan")))
PY
}

procesar() {
  local club="$1" dt="$2" persp="$3"
  local base="${DIR[$club]}"
  local unit outdir

  if [[ "$persp" == "attack" ]]; then
    unit="coach";        outdir="$base"
  else
    unit="coach_faced";  outdir="$base/def"
  fi
  mkdir -p "$outdir/figures"

  local slug; slug=$(echo "$dt" | tr 'A-Z ' 'a-z_' | tr -cd 'a-z_')
  local sello="$outdir/.sello_${slug}"
  local h; h=$(hash_parquet "$base")

  # CACHE POR HASH DEL PARQUET, no por existencia del artefacto.
  # Un `[ya]` basado en "el archivo existe" sirve resultados obsoletos cuando
  # transitions.parquet cambia. Ya paso: tras el parche D0 el script reporto
  # [ya] para todo, y los artefactos solo seguian siendo validos por suerte.
  if [[ $FORCE -eq 0 && -f "$sello" && "$(cat "$sello")" == "$h" ]]; then
    printf '    [ya] %-20s %-8s\n' "$dt" "$persp"
    return 0
  fi

  printf '    >>> %-20s %-8s' "$dt" "$persp"
  if [[ $DRY -eq 1 ]]; then echo " (dry-run)"; return 0; fi

  local log="/tmp/dtd_${slug}_${persp}.log"
  {
    dtdecoder phase1 --unit "$unit" --value "$dt" --baseline other_coaches \
      --club "$club" --perspective "$persp" --indir "$base" --outdir "$outdir" &&
    dtdecoder phase2 --unit "$unit" --value "$dt" \
      --club "$club" --perspective "$persp" --indir "$outdir" --outdir "$outdir" &&
    dtdecoder phase3 --unit "$unit" --value "$dt" --baseline other_coaches \
      --club "$club" --perspective "$persp" --indir "$outdir" --outdir "$outdir" \
      --n-boot "$N_BOOT"
  } > "$log" 2>&1

  if [[ $? -ne 0 ]]; then
    echo "  FALLO  (log: $log)"
    FALLIDAS+=("$club/$dt/$persp")
    ((fallos++))
    return 1
  fi

  # --- Opcion C: etiqueta persistente, no solo un aviso -------------------
  local ppo; ppo=$(leer_ppo "$outdir/phase1_report.json")
  local flag="ok"
  if python -c "import sys; sys.exit(0 if float('$ppo') > $UMBRAL_PPO else 1)" 2>/dev/null; then
    flag="sobreajuste"
    ((avisos++))
  fi

  python - "$MANIFIESTO" "$club" "$dt" "$persp" "$ppo" "$flag" "$outdir" "$h" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True)
try:
    m = json.loads(p.read_text())
except Exception:
    m = {}
club, dt, persp, ppo, flag, outdir, h = sys.argv[2:9]
m[f"{club}|{dt}|{persp}"] = {
    "club": club, "coach": dt, "perspective": persp,
    "params_per_obs": None if ppo == "nan" else float(ppo),
    "umbral": 0.5,
    "flag": flag,
    # Texto listo para el reporte. Se guarda AQUI y no se redacta en el HTML
    # para que la etiqueta y el numero que la justifica no puedan separarse.
    "nota": (
        "Era corta: mas parametros por observacion que el umbral de 0.5 "
        "(ADR-25). La malla 5x4 sobreajusta esta unidad. Ver la tabla de "
        "sensibilidad a 4x3." if flag == "sobreajuste" else ""
    ),
    "outdir": outdir,
    "hash_transitions": h,
}
p.write_text(json.dumps(m, indent=2, ensure_ascii=False))
PY

  echo "$h" > "$sello"
  if [[ "$flag" == "sobreajuste" ]]; then
    echo "  ok  [!] params_per_obs=$ppo > $UMBRAL_PPO"
  else
    echo "  ok      params_per_obs=$ppo"
  fi
  ((ok++))
}

for club in "América" "Cruz Azul"; do
  slug_club=$(echo "$club" | tr 'A-Z ' 'a-z' | iconv -f utf8 -t ascii//TRANSLIT 2>/dev/null || echo "$club")
  if [[ -n "$SOLO" && "$slug_club" != *"$SOLO"* ]]; then continue; fi

  base="${DIR[$club]}"
  if [[ ! -f "$base/transitions.parquet" ]]; then
    echo "[salto] $club: no existe $base/transitions.parquet"
    echo "        Corre phase0 CON --club primero."
    continue
  fi

  echo
  echo "=================================================================="
  echo " $club   ($base, parquet $(hash_parquet "$base"))"
  echo "=================================================================="

  IFS='|' read -ra lista <<< "${DTS[$club]}"
  for dt in "${lista[@]}"; do
    procesar "$club" "$dt" attack
    procesar "$club" "$dt" defense
  done
done

echo
echo "=================================================================="
echo " $ok generadas · $avisos con etiqueta de sobreajuste · $fallos fallidas"
echo "=================================================================="
if [[ ${#FALLIDAS[@]} -gt 0 ]]; then
  echo
  echo " Fallidas (mira el log, no asumas que es muestra insuficiente):"
  for f in "${FALLIDAS[@]}"; do echo "   $f"; done
fi
if [[ $avisos -gt 0 ]]; then
  echo
  echo " Las unidades con etiqueta van al reporte CON la advertencia (Opcion C)."
  echo " El texto exacto esta en $MANIFIESTO, campo \`nota\`."
  echo " El sesgo del sobreajuste va hacia ENCONTRAR diferencias, asi que un"
  echo " resultado nulo desde una de estas unidades es MAS creible, no menos."
fi
echo
echo " Manifiesto: $MANIFIESTO"
