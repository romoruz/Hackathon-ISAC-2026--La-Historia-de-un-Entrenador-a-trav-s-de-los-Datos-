#!/usr/bin/env python3
"""
34_sonda_contexto.py — condiciones de validez de ADR-56. Solo lectura.

Uso:
    python scripts/34_sonda_contexto.py 2>&1 | tee reports/sonda_contexto.txt
"""
from __future__ import annotations

import glob
import json
import traceback
from pathlib import Path

import polars as pl

RAIZ = Path(__file__).resolve().parent.parent
EV = sorted(glob.glob(str(RAIZ / "data/api/eventos_api_ligamx/*.parquet")))


def bloque(t):
    def d(fn):
        def run():
            print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)
            try:
                fn()
            except Exception:
                print("  !! FALLO:\n  " + traceback.format_exc().replace("\n", "\n  "))
        return run
    return d


def dirs():
    out = []
    for d in sorted(Path(p) for p in glob.glob(str(RAIZ / "data/processed_api_*"))):
        club = json.loads((d / "phase0_report.json").read_text())["coaches"]["club"]
        out.append((d, club))
    return out


@bloque("1. MARCADOR: ¿a quien se refieren score_state y score_state_club?")
def b1():
    d, club = next((x for x in dirs() if x[1] == "América"), dirs()[0])
    t = pl.read_parquet(d / "transitions.parquet",
                        columns=["team", "score_state", "score_state_club", "action_type"])
    print(f"  directorio: {d.name} (club {club}) · dtypes: "
          f"{t.schema['score_state']} / {t.schema['score_state_club']}")
    for lado, f in (("filas DEL CLUB", pl.col("team") == club), ("filas DEL RIVAL", pl.col("team") != club)):
        x = (t.filter(f & (pl.col("action_type") != "TERMINAL"))
             .group_by(["score_state", "score_state_club"]).len().sort("len", descending=True))
        print(f"\n  {lado}: score_state × score_state_club")
        for r in x.iter_rows():
            print(f"    {str(r[0]):<12} {str(r[1]):<12} {r[2]:>9,}")
    p = pl.read_parquet(RAIZ / "data/prior_liga/transitions.parquet", columns=["score_state"])
    print("\n  liga (prior), score_state:", p.group_by("score_state").len().sort("len").rows())


@bloque("2. MOMENTO: minute por (match_id, possession)")
def b2():
    d, club = dirs()[0]
    t = pl.read_parquet(d / "transitions.parquet", columns=["poss_uid", "match_id"]).unique()
    t = t.with_columns(pl.col("poss_uid").str.split("_").list.last().cast(pl.Int64, strict=False).alias("possession"))
    m = (pl.scan_parquet(EV).group_by(["match_id", "possession"])
         .agg(pl.col("minute").min().alias("minuto"), pl.col("period").first()).collect())
    j = t.join(m, on=["match_id", "possession"], how="left")
    print(f"  {d.name}: posesiones {t.height:,} · con minuto {j['minuto'].is_not_null().sum():,} "
          f"({j['minuto'].is_not_null().mean():.4f})")
    print("  minuto >= 60:", float((j['minuto'] >= 60).mean()), "· periodos:",
          j.group_by("period").len().sort("period").rows())


@bloque("3. LOCALIA")
def b3():
    idx = pl.read_csv(RAIZ / "data/raw_api/indice_partidos.csv", infer_schema_length=None)
    ternas = []
    for d, club in dirs():
        t = pl.read_parquet(d / "transitions.parquet", columns=["match_id", "team"]).unique()
        ternas.append(t.filter(pl.col("team") != club).with_columns(pl.lit(club).alias("defensor")))
    u = pl.concat(ternas).unique()
    lados = u.group_by("match_id").agg(pl.col("team").n_unique().alias("eq"), pl.len().alias("n"))
    comp = lados.filter((pl.col("eq") == 2) & (pl.col("n") == 2))["match_id"]
    j = pl.DataFrame({"match_id": comp}).join(idx, on="match_id", how="left")
    print(f"  completos: {comp.len()} · en el indice: {j['home_team'].is_not_null().sum()}")
    eq = u.group_by("match_id").agg(pl.col("team").unique().alias("equipos"))
    jj = j.join(eq, on="match_id").with_columns(
        pl.col("equipos").list.contains(pl.col("home_team")).alias("h_ok"),
        pl.col("equipos").list.contains(pl.col("away_team")).alias("a_ok"))
    print(f"  local y visitante coinciden con los equipos del partido: "
          f"{int((jj['h_ok'] & jj['a_ok']).sum())} de {jj.height}")
    malos = jj.filter(~(pl.col("h_ok") & pl.col("a_ok")))
    if malos.height:
        print("  NO coinciden (nombres):", malos.select("home_team", "away_team", "equipos").head(5).rows())


@bloque("4. RIVAL: diferencia de xG por partido, por equipo y torneo")
def b4():
    lf = pl.scan_parquet(EV)
    tiros = (lf.filter(pl.col("type") == "Shot")
             .group_by(["match_id", "team"]).agg(pl.col("shot_statsbomb_xg").sum().alias("xg")).collect())
    idx = pl.read_csv(RAIZ / "data/raw_api/indice_partidos.csv", infer_schema_length=None)
    idx = idx.with_columns(pl.col("match_date").str.to_date())
    idx = idx.with_columns(
        pl.when(pl.col("match_date").dt.month() >= 7)
        .then(pl.lit("A") + pl.col("match_date").dt.year().cast(pl.Utf8))
        .otherwise(pl.lit("C") + pl.col("match_date").dt.year().cast(pl.Utf8)).alias("torneo"))
    part = tiros.join(idx.select("match_id", "torneo"), on="match_id", how="inner")
    por = part.group_by(["team", "torneo"]).agg(pl.len().alias("partidos"))
    print(f"  equipo-torneo: {por.height} · partidos por equipo-torneo min {por['partidos'].min()} "
          f"max {por['partidos'].max()}")
    print("  con menos de 10 partidos:", por.filter(pl.col("partidos") < 10).sort("partidos").rows()[:12])
    print("  partidos sin ningun tiro de un equipo (xg ausente):",
          idx.height - part['match_id'].n_unique(), "(del indice completo, incluye fuera de alcance)")
    og = lf.filter(pl.col("type").str.contains("Own Goal")).group_by("type").len().collect()
    print("  eventos de autogol:", og.rows())


if __name__ == "__main__":
    for b in (b1, b2, b3, b4):
        b()
