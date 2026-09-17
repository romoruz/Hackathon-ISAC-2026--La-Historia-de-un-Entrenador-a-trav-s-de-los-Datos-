#!/usr/bin/env python3
"""
34_sonda_vista_defensora.py — ¿la union de los 18 directorios es una base valida?

Hipotesis que se verifica (adenda de ADR-54, D54-10):
  cada posesion de la liga aparece EXACTAMENTE UNA VEZ como fila rival
  (`team != club`) en el directorio del club que defiende, con
  `min_actions_defense = 1`. La union de esas filas es una "vista defensora"
  de la liga con la misma regla que la unidad focal de D1 y de balon parado.

Solo lectura. Imprime conteos, nunca valores licenciados.

Uso:
    python scripts/34_sonda_vista_defensora.py 2>&1 | tee reports/sonda_vista_defensora.txt
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import polars as pl

RAIZ = Path(__file__).resolve().parent.parent
COLS = ["poss_uid", "match_id", "team", "event_index", "action_type"]


def main() -> int:
    dirs = sorted(Path(p) for p in glob.glob(str(RAIZ / "data/processed_api_*"))
                  if (Path(p) / "phase0_report.json").exists())
    print(f"directorios con phase0: {len(dirs)}")
    partes = []
    for d in dirs:
        club = (json.loads((d / "phase0_report.json").read_text()).get("coaches") or {}).get("club")
        t = pl.read_parquet(d / "transitions.parquet")
        falt = [c for c in COLS + ["coach_faced"] if c not in t.columns]
        if falt:
            print(f"  !! {d.name}: faltan {falt}")
            continue
        r = (t.filter(pl.col("team") != club).select(COLS)
             .with_columns(pl.lit(club).alias("defensor")))
        partes.append(r)
        print(f"  {d.name:<36} club={club:<20} filas rivales={r.height:>8,} "
              f"partidos={r['match_id'].n_unique():>4}")
    u = pl.concat(partes)

    # 1. unicidad: cada (poss_uid, event_index) en un solo directorio
    dup = u.group_by(["poss_uid", "event_index"]).agg(pl.len().alias("n")).filter(pl.col("n") > 1)
    print(f"\n1. filas repetidas entre directorios: {dup.height:,}")
    poss_multi = (u.select("poss_uid", "defensor").unique()
                  .group_by("poss_uid").agg(pl.len().alias("n")).filter(pl.col("n") > 1))
    print(f"   posesiones con mas de un defensor: {poss_multi.height:,}")

    # 2. cobertura contra la liga (min_actions = 2)
    lg = pl.read_parquet(RAIZ / "data/prior_liga/transitions.parquet", columns=COLS)
    key = ["poss_uid", "event_index"]
    solo_liga = lg.join(u.select(key), on=key, how="anti")
    solo_union = u.join(lg.select(key), on=key, how="anti")
    print(f"\n2. liga: {lg.height:,} filas · union: {u.height:,} filas")
    print(f"   solo en la liga: {solo_liga.height:,}   <- debe ser 0")
    print(f"   solo en la union: {solo_union.height:,}")
    extra = (u.join(solo_union.select("poss_uid").unique(), on="poss_uid")
             .group_by("poss_uid")
             .agg((pl.col("action_type") != "TERMINAL").sum().alias("L"),
                  (pl.col("action_type") == "TERMINAL").any().alias("term")))
    print("   posesiones extra por (L, con TERMINAL):")
    print(extra.group_by(["L", "term"]).agg(pl.len()).sort("len", descending=True))
    if solo_liga.height:
        print("   partidos con filas solo en la liga:",
              solo_liga["match_id"].unique().sort().head(20).to_list())

    # 3. cada partido con sus dos equipos atacando
    pm = lg["match_id"].unique()
    cov = u.group_by("match_id").agg(pl.col("team").n_unique().alias("eq"))
    print(f"\n3. partidos en la liga: {pm.len()} · en la union: {cov.height} · "
          f"con 2 equipos: {(cov['eq'] == 2).sum()}")
    faltan = set(pm.to_list()) - set(cov["match_id"].to_list())
    print(f"   partidos de la liga ausentes de la union: {len(faltan)} {sorted(faltan)[:20]}")

    # 4. posesiones de corner y lo que min_actions = 2 se llevaba
    ev = sorted(glob.glob(str(RAIZ / "data/api/eventos_api_ligamx/*.parquet")))
    pp = (pl.scan_parquet(ev).group_by(["match_id", "possession"])
          .agg(pl.col("play_pattern").first()).collect())
    def con_patron(df):
        return (df.select("poss_uid", "match_id").unique()
                .with_columns(pl.col("poss_uid").str.split("_").list.last()
                              .cast(pl.Int64, strict=False).alias("possession"))
                .join(pp, on=["match_id", "possession"], how="left"))
    cu, cl = con_patron(u), con_patron(lg)
    t = (cu.group_by("play_pattern").agg(pl.len().alias("union"))
         .join(cl.group_by("play_pattern").agg(pl.len().alias("liga")), on="play_pattern", how="left")
         .with_columns((1 - pl.col("liga") / pl.col("union")).alias("frac_perdida"))
         .sort("union", descending=True))
    print("\n4. posesiones por patron (union con min 1 contra liga con min 2):")
    print(t)
    print(f"   sin patron tras la union: {cu['play_pattern'].is_null().sum()}")

    # 5. set_piece_phase: que es
    sp = (pl.scan_parquet(ev).group_by(["play_pattern", "set_piece_phase"])
          .agg(pl.len()).sort(["play_pattern", "set_piece_phase"]).collect())
    print("\n5. set_piece_phase por play_pattern:")
    for r in sp.filter(pl.col("play_pattern").is_in(["From Corner", "From Free Kick", "Regular Play"])).iter_rows():
        print(f"   {r[0]:<16} {str(r[1]):<6} {r[2]:>9,}")

    # 6. secuencias de corner: posesiones por corner
    co = (pl.scan_parquet(ev).filter(pl.col("pass_type") == "Corner")
          .select("match_id", "possession").collect())
    print(f"\n6. corners: {co.height:,} · posesiones que empiezan con corner: "
          f"{co.unique().height:,} · posesiones From Corner (eventos): "
          f"{pp.filter(pl.col('play_pattern') == 'From Corner').height:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
