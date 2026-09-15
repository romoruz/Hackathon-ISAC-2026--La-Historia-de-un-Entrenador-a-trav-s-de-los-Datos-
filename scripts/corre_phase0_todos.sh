#!/usr/bin/env bash
# corre_phase0_todos.sh — phase0 de los 18 clubes, desatendido y reanudable.
#
#   bash scripts/corre_phase0_todos.sh              # los que falten
#   bash scripts/corre_phase0_todos.sh --rehacer    # todos desde cero
#
# Reanudable a proposito: si se corta a la mitad, se relanza y sigue donde
# quedo. Un bucle de una hora que hay que empezar de cero por un corte es una
# invitacion a saltarse verificaciones.
#
# Cada club escribe en data/processed_api_<slug>/ y su log en
# logs/phase0_<slug>.log. Al final imprime una tabla de cobertura y marca
# cualquier club cuya suma de partidos por era NO cuadre con sus partidos.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

[ -z "${VIRTUAL_ENV:-}" ] && { echo "Activa el venv: source .venv/bin/activate"; exit 1; }
command -v dtdecoder >/dev/null || { echo "dtdecoder no esta en el PATH: entorno equivocado"; exit 1; }

REHACER=0
[ "${1:-}" = "--rehacer" ] && REHACER=1

CLUBES_DIR="data/api/clubes"
ERAS_DIR="data/eras_compat"
EXCL="data/eras_api/absorbidos.csv"
mkdir -p logs

[ -d "$CLUBES_DIR" ] || { echo "Falta $CLUBES_DIR. Corre scripts/03_subconjuntos_por_club.py"; exit 1; }

ok=0; fallo=0; saltado=0
for eras in "$ERAS_DIR"/coach_eras_*.csv; do
  s="$(basename "$eras")"; s="${s#coach_eras_}"; s="${s%.csv}"
  src="$CLUBES_DIR/$s"
  fechas="$CLUBES_DIR/match_dates_${s}.csv"
  out="data/processed_api_${s}"

  if [ ! -d "$src" ]; then echo "[salto] $s: sin eventos en $src"; saltado=$((saltado+1)); continue; fi
  if [ ! -f "$fechas" ]; then echo "[salto] $s: sin $fechas"; saltado=$((saltado+1)); continue; fi
  if [ "$REHACER" -eq 0 ] && [ -f "$out/phase0_report.json" ]; then
    echo "[ya]    $s"; ok=$((ok+1)); continue
  fi

  # El nombre del club NO se deriva del slug: 'atletico_san_luis' no vuelve a
  # ser 'Atlético San Luis'. Se saca de los datos, que es la unica fuente que
  # no puede desalinearse con el filtro de `team`.
  club="$(python - "$src" "$s" <<'PY'
import sys, unicodedata, polars as pl
src, s = sys.argv[1], sys.argv[2]
def slug(n):
    x = "".join(c for c in unicodedata.normalize("NFD", n)
                if unicodedata.category(c) != "Mn")
    return x.lower().replace(" ", "_")
equipos = (pl.scan_parquet(f"{src}/*.parquet").select("team").unique()
           .collect()["team"].drop_nulls().to_list())
hit = [e for e in equipos if slug(e) == s]
print(hit[0] if len(hit) == 1 else "")
PY
)"
  if [ -z "$club" ]; then
    echo "[FALLO] $s: no se pudo resolver el nombre del club"; fallo=$((fallo+1)); continue
  fi

  echo "[corre] $s  ->  \"$club\""
  mkdir -p "$out"
  if dtdecoder phase0 --src "$src" --club "$club" \
        --eras "$eras" --match-dates "$fechas" \
        ${EXCL:+--exclusiones "$EXCL"} \
        --outdir "$out" > "logs/phase0_${s}.log" 2>&1; then
    ok=$((ok+1))
  else
    echo "        FALLO. Ultimas lineas:"; tail -5 "logs/phase0_${s}.log" | sed 's/^/        /'
    fallo=$((fallo+1))
  fi
done

echo
echo "=================================================================="
echo " ok=$ok  fallo=$fallo  saltado=$saltado"
echo "=================================================================="
python - <<'PY'
import json, pathlib
filas, malos = [], []
for p in sorted(pathlib.Path(".").glob("data/processed_api_*/phase0_report.json")):
    r = json.loads(p.read_text())
    co = r.get("coaches") or {}
    cov = co.get("coverage", [])
    suma = sum(c["matches"] for c in cov)
    n = r.get("n_matches")
    # La suma de partidos por era tiene que dar los partidos del club. Si no,
    # hay partidos sin era y `unmapped_matches` deberia decirlo.
    if suma != n:
        malos.append((co.get("club"), suma, n, co.get("unmapped_matches")))
    filas.append({
        "club": co.get("club"), "partidos": n,
        "eras": len(cov),
        "analizables": sum(1 for c in cov if c.get("suficiente")),
        "sin_era": co.get("unmapped_matches"),
        "sanity": (r.get("coordinate_sanity") or {}).get("ok"),
    })
print(f"{'club':<24}{'partidos':>9}{'eras':>6}{'analiz.':>9}{'sin era':>9}{'sanity':>8}")
for f in filas:
    print(f"{str(f['club']):<24}{f['partidos']:>9}{f['eras']:>6}"
          f"{f['analizables']:>9}{str(f['sin_era']):>9}{str(f['sanity']):>8}")
print(f"\nclubes: {len(filas)}   unidades analizables: "
      f"{sum(f['analizables'] for f in filas)}")
if malos:
    print("\nDESCUADRES (suma de eras != partidos del club):")
    for m in malos:
        print(f"  {m[0]}: eras suman {m[1]}, club tiene {m[2]}, sin era {m[3]}")
    print("  Revisa esos clubes antes de usarlos en H4.")
if any(f["sanity"] is not True for f in filas):
    print("\nAVISO: algun club no pasa coordinate_sanity. No lo uses hasta mirarlo.")
PY
