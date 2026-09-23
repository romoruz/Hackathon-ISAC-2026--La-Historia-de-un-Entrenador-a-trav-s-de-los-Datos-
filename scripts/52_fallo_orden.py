#!/usr/bin/env python3
"""
52_fallo_orden.py — ADR-62 adenda 1c y ADR-59 adenda 10 §6: cuenta el fallo 3.

El placebo (51_placebo_red.py, corrido una vez) cortaba `ia[-m:]` contra
`ib[:m]` suponiendo que la era *a* va antes que la *b*. Este script cuenta en
cuántos pares del acta eso era falso.

NO calcula ninguna distancia ni vuelve a medir nada: lee las fechas de los
parquets publicados y el acta `reports/placebo_red_v1.json`, y escribe
`reports/placebo_red_fallo.json`. No puede escribir sobre ninguna de las dos
actas de corrida única.

Uso:
    python scripts/52_fallo_orden.py
    python scripts/52_fallo_orden.py --out /tmp/fallo.json
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REP = RAIZ / "reports"
ACTAS = {(REP / "red_pases_v1.json").resolve(), (REP / "placebo_red_v1.json").resolve()}


def rangos(raiz: Path):
    """(club, técnico) -> (primera fecha, última fecha), de los parquets publicados."""
    import polars as pl
    dirs = sorted(glob.glob(str(raiz / "data" / "processed_api_*")))
    if not dirs:
        sys.exit("ABORTA: no hay data/processed_api_*")
    t = pl.concat([pl.read_parquet(Path(d) / "transitions.parquet", columns=["team", "coach", "match_date"])
                   for d in dirs]).filter(pl.col("coach").is_not_null())
    g = t.group_by(["team", "coach"]).agg(pl.col("match_date").min().alias("ini"),
                                          pl.col("match_date").max().alias("fin"))
    return {(r["team"], r["coach"]): (str(r["ini"]), str(r["fin"])) for r in g.iter_rows(named=True)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ),
                    help="raíz del repo (para correrlo desde fuera, como hace el instalador)")
    ap.add_argument("--acta", default=None, help="por omisión, <raiz>/reports/placebo_red_v1.json")
    ap.add_argument("--out", default=None, help="por omisión, <raiz>/reports/placebo_red_fallo.json")
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    rep = raiz / "reports"
    a.acta = a.acta or str(rep / "placebo_red_v1.json")
    a.out = a.out or str(rep / "placebo_red_fallo.json")
    actas = ACTAS | {(rep / "red_pases_v1.json").resolve(), (rep / "placebo_red_v1.json").resolve()}
    if Path(a.out).resolve() in actas:
        sys.exit("ABORTA: este script no escribe sobre un acta de corrida única")
    acta = json.loads(Path(a.acta).read_text(encoding="utf-8"))
    rg = rangos(raiz)
    filas, sin_fechas = [], []
    for r in acta["relevos"]:
        club, ca, cb = r["club"], r["a"], r["b"]
        ra, rb = rg.get((club, ca)), rg.get((club, cb))
        if ra is None or rb is None:
            sin_fechas.append({"club": club, "a": ca, "b": cb})
            continue
        filas.append({"club": club, "a": ca, "b": cb,
                      "a_ini": ra[0], "a_fin": ra[1], "b_ini": rb[0], "b_fin": rb[1],
                      "invertido": ra[0] > rb[0],
                      "solapan": not (ra[1] < rb[0] or rb[1] < ra[0]),
                      "sin_T": r.get("T_relevo") is None})
    inv = [f for f in filas if f["invertido"]]
    salida = {"adr": "ADR-62 adenda 1c · ADR-59 adenda 10 §6",
              "que_es": "conteo del fallo 3 (pares al revés en el placebo); no mide nada",
              "acta": Path(a.acta).name,
              "n_relevos": len(filas), "n_invertidos": len(inv),
              "n_invertidos_sin_T": sum(f["sin_T"] for f in inv),
              "n_solapan": sum(f["solapan"] for f in filas),
              "sin_fechas": sin_fechas, "relevos": filas}
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"relevos en el acta: {len(filas)} (+{len(sin_fechas)} sin fechas)")
    print(f"invertidos: {len(inv)} · de ellos sin T: {salida['n_invertidos_sin_T']} · "
          f"con épocas que se solapan: {salida['n_solapan']}")
    print(f"escrito {a.out}")


if __name__ == "__main__":
    main()
