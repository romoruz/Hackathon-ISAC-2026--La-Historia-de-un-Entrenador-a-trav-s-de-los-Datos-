#!/usr/bin/env python3
"""
Trae las fechas de partido desde el API de Hudl StatsBomb.

El volcado de eventos NO trae fecha; sin ella no se pueden asignar eras de DT.
Esto es UNA llamada por temporada.

Uso:
    export SB_USERNAME=...  SB_PASSWORD=...
    python scripts/fetch_match_dates.py --out data/match_dates.csv

Si no tienes statsbombpy instalado:
    uv pip install statsbombpy

Si el API no te da acceso al endpoint de partidos, cualquier CSV con las
columnas (match_id, match_date) sirve. Puedes armarlo a mano; son ~300 filas
y es trabajo de una tarde.
"""

import argparse
import sys

import polars as pl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/match_dates.csv")
    ap.add_argument("--competition-id", type=int, default=None)
    ap.add_argument("--season-id", type=int, nargs="*", default=None)
    args = ap.parse_args()

    try:
        from statsbombpy import sb
    except ImportError:
        print("Falta statsbombpy:  uv pip install statsbombpy", file=sys.stderr)
        return 1

    comps = sb.competitions()
    if args.competition_id is None:
        print(comps.to_string())
        print("\nElige --competition-id y --season-id de la tabla de arriba.", file=sys.stderr)
        return 1

    seasons = args.season_id or comps.loc[
        comps.competition_id == args.competition_id, "season_id"
    ].tolist()

    frames = []
    for sid in seasons:
        m = sb.matches(competition_id=args.competition_id, season_id=sid)
        frames.append(
            pl.from_pandas(m[["match_id", "match_date", "home_team", "away_team"]])
        )
        print(f"[ok] season {sid}: {len(m)} partidos", file=sys.stderr)

    out = pl.concat(frames).unique(subset=["match_id"]).sort("match_date")
    out.write_csv(args.out)
    print(f"[ok] {out.height} partidos -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
