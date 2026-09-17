#!/usr/bin/env python3
"""
34_sonda_alineaciones.py — lo necesario para preinscribir ADR-58 (uso de
jugadores). Solo lectura; no imprime nombres ni valores por jugador.

Uso:
    python scripts/34_sonda_alineaciones.py 2>&1 | tee reports/sonda_alineaciones.txt
"""
from __future__ import annotations

import glob
import gzip
import json
import traceback
from collections import Counter
from pathlib import Path

import numpy as np
import polars as pl

RAIZ = Path(__file__).resolve().parent.parent
EV = sorted(glob.glob(str(RAIZ / "data/api/eventos_api_ligamx/*.parquet")))
LU = sorted(glob.glob(str(RAIZ / "data/raw_api/lineups/*")))


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


def tipo(v, prof=0):
    if prof > 3:
        return "..."
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {tipo(x, prof + 1)}" for k, x in list(v.items())[:14]) + "}"
    if isinstance(v, list):
        return f"list[{len(v)}]<{tipo(v[0], prof + 1) if v else ''}>"
    return type(v).__name__


def lee(p):
    p = Path(p)
    txt = gzip.open(p, "rt").read() if p.suffix == ".gz" else p.read_text()
    return json.loads(txt)


@bloque("1. ESTRUCTURA DE UN ARCHIVO DE ALINEACION")
def b1():
    print(f"  {len(LU)} archivos")
    d = lee(LU[0])
    eq = next(iter(d.values())) if isinstance(d, dict) else d[0]
    print("  equipo:", tipo({k: v for k, v in eq.items() if k != "lineup"}))
    j = eq["lineup"][0]
    print("  jugador:", tipo({k: v for k, v in j.items() if k not in ("player_name", "player_nickname")}))
    if j.get("positions"):
        print("  posicion[0]:", tipo(j["positions"][0]))
    if isinstance(j.get("stats"), (dict, list)):
        print("  stats:", tipo(j["stats"]))


@bloque("2. POSICIONES Y MOTIVOS EN 200 ARCHIVOS")
def b2():
    razones_ini, razones_fin, npos, jug = Counter(), Counter(), Counter(), Counter()
    campos_pos, formatos = Counter(), Counter()
    for p in LU[:200]:
        d = lee(p)
        for eq in (d.values() if isinstance(d, dict) else d):
            jug[len(eq["lineup"])] += 1
            for f in eq.get("formations", []):
                formatos[type(f.get("formation")).__name__] += 1
            for j in eq["lineup"]:
                ps = j.get("positions") or []
                npos[len(ps)] += 1
                for x in ps:
                    campos_pos.update(x.keys())
                    razones_ini[str(x.get("start_reason"))] += 1
                    razones_fin[str(x.get("end_reason"))] += 1
    print("  jugadores por equipo:", sorted(jug.items()))
    print("  posiciones por jugador:", sorted(npos.items()))
    print("  campos de posicion:", dict(campos_pos))
    print("  start_reason:", razones_ini.most_common(12))
    print("  end_reason:", razones_fin.most_common(12))
    print("  tipo de formation:", dict(formatos))
    d = lee(LU[0])
    eq = next(iter(d.values())) if isinstance(d, dict) else d[0]
    ej = next((x for j in eq["lineup"] for x in (j.get("positions") or [])), None)
    if ej:
        print("  ejemplo de posicion (sin jugador):",
              {k: v for k, v in ej.items() if k in ("position", "from", "to", "from_period", "to_period",
                                                    "start_reason", "end_reason")})


@bloque("3. SUSTITUCIONES EN LOS EVENTOS")
def b3():
    lf = pl.scan_parquet(EV)
    s = (lf.filter(pl.col("type") == "Substitution")
         .select("match_id", "team", "minute", "period", "substitution_outcome").collect())
    if s.height == 0:
        print("  0 sustituciones en los eventos"); return
    por = s.group_by(["match_id", "team"]).len()["len"].to_numpy()
    print(f"  {s.height:,} sustituciones · por equipo-partido: media {por.mean():.2f}, "
          f"min {por.min()}, max {por.max()}")
    print("  minuto: cuartiles", np.quantile(s["minute"].to_numpy(), [0, .25, .5, .75, 1]).tolist())
    print("  motivo:", s.group_by("substitution_outcome").len().sort("len", descending=True).rows())
    print("  antes del minuto 46:", int((s["minute"] < 46).sum()))
    t = lf.filter(pl.col("type") == "Tactical Shift").group_by(["match_id", "team"]).len().collect()
    print(f"  cambios tacticos: {t['len'].sum():,} en {t.height:,} equipo-partidos")
    x = lf.filter(pl.col("type") == "Starting XI").select("tactics_lineup", "tactics_formation").head(1).collect()
    if x.height:
        v = x["tactics_lineup"][0]
        try:
            v = json.loads(v)
        except Exception:
            pass
        print("  Starting XI: tactics_lineup", tipo(v), "· formation", x["tactics_formation"][0].__class__.__name__)


@bloque("4. player_id EN LAS TRANSICIONES")
def b4():
    d = sorted(glob.glob(str(RAIZ / "data/processed_api_*")))[0]
    t = pl.read_parquet(Path(d) / "transitions.parquet", columns=["player_id", "action_type"])
    r = t.filter(pl.col("action_type") != "TERMINAL")
    print(f"  {Path(d).name}: acciones reales {r.height:,} · con player_id {r['player_id'].is_not_null().mean():.4f}"
          f" · dtype {t.schema['player_id']}")


@bloque("5. COBERTURA DE ARCHIVOS")
def b5():
    ids = {int(Path(p).name.split(".")[0]) for p in LU}
    pm = pl.read_parquet(RAIZ / "data/prior_liga/transitions.parquet", columns=["match_id"])["match_id"].unique()
    print(f"  partidos del alcance: {pm.len()} · con alineacion: {sum(int(m) in ids for m in pm.to_list())}")


if __name__ == "__main__":
    for b in (b1, b2, b3, b4, b5):
        b()
