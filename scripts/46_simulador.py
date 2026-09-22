#!/usr/bin/env python3
"""
46_simulador.py — ADR-59 adenda 3 §6 y adenda 4 §5-§6: los datos del simulador.

v2 (adenda 4): además de la matriz del juego abierto, exporta los CONTEOS de
paso entre zonas (20 × 24: veinte zonas y cuatro finales) de la liga y de
CADA era de las cinco historias, para "de dónde viene y a dónde va el balón"
y "simula una jugada", y el nombre más frecuente de cada jugador de esas eras
(columna `player` de transitions.parquet). Todo descriptivo.

Exporta la matriz del bloque de juego abierto (20 × 20) de la liga del torneo de
1.6 y de la era principal de cada historia, con las mismas funciones de
45_progresion.py (λ = 0, la misma base). No es inferencia nueva (nivel C).

Guarda: la distribución cuasi-estacionaria que sale de cada matriz exportada
tiene que coincidir a 1e-9 con la ya publicada en supervivencia_v1 › liga_16.pi
y progresion_v1 › eras[].cuasi.era.pi. Si no, aborta.

Uso:
    python scripts/46_simulador.py --out reports/simulador_v2.json
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
TOL = 1e-9


def _g45():
    spec = importlib.util.spec_from_file_location("prog45", RAIZ / "scripts" / "45_progresion.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bloque_abierto(G, P, alfa):
    ob = G.bloque(0)
    return P[np.ix_(ob, ob)], alfa[ob]


def verifica(G, Q, a, pi_pub, quien):
    if pi_pub is None:
        return None
    r = G.cuasi(Q, a)
    if r is None:
        raise G.Aborta(f"{quien}: el bloque exportado no es irreducible y el publicado sí")
    d = float(np.abs(np.array(r["pi"]) - np.array(pi_pub)).max())
    if d > TOL:
        raise G.Aborta(f"{quien}: la distribución difiere de la publicada en {d:.2e} (> {TOL})")
    return d


def conteos_abierto(G, sub):
    """Conteos 20 × 24 del bloque de juego abierto: de zona a zona y de zona a
    cada final (gol, remate sin gol, pérdida, fuera)."""
    import polars as pl
    t = sub.filter(pl.col("from_state") % G.NF == 0)
    fs, ts = t["from_state"].to_numpy() // G.NF, t["to_state"].to_numpy()
    col = np.where(ts >= G.NT, 20 + (ts - G.NT), ts // G.NF)
    if (ts < G.NT).any() and ((ts[ts < G.NT] % G.NF) != 0).any():
        raise G.Aborta("hay pasos del juego abierto a otra fase: D61-0 no se cumple")
    C = np.zeros((20, 24), dtype=int)
    np.add.at(C, (fs, col), 1)
    ini = sub.sort(["pid", "event_index"]).group_by("pid", maintain_order=True).first()
    ini = ini.filter(pl.col("from_state") % G.NF == 0)
    a = np.bincount(ini["from_state"].to_numpy() // G.NF, minlength=20).astype(float)
    return C, a


def nombres(indirs, coaches):
    import polars as pl
    partes = []
    for d in indirs:
        p = Path(d) / "transitions.parquet"
        cols = set(pl.read_parquet_schema(p))
        if not {"player_id", "player", "coach"} <= cols:
            continue
        partes.append(pl.read_parquet(p, columns=["player_id", "player", "coach"])
                      .filter(pl.col("coach").is_in(coaches) & pl.col("player_id").is_not_null()
                              & pl.col("player").is_not_null()))
    if not partes:
        return {}
    t = pl.concat(partes).group_by(["player_id", "player"]).agg(pl.len().alias("n"))
    t = t.sort(["player_id", "n"], descending=[False, True]).group_by("player_id", maintain_order=True).first()
    return {str(int(i)): n for i, n in t.select("player_id", "player").iter_rows()}


def matrices_era(G, df, club, coach):
    import polars as pl
    sub = df.filter((pl.col("club") == club) & (pl.col("coach") == coach))
    tors = sorted(sub["torneo"].unique().to_list())
    base = df.filter((pl.col("club") != club) & pl.col("torneo").is_in(tors))
    Ge, Gb = G.agrega(sub), G.agrega(base)
    s_t = {t: float(Ge["A"][np.array([x == t for x in Ge["torneo"]])].sum()) for t in tors}
    Pe, _, ae = G.matrices(Ge, Gb, s_t)
    return Pe, ae


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "simulador_v2.json"))
    a = ap.parse_args()
    G = _g45()
    rep = Path(a.reports)
    sup = json.loads((rep / "supervivencia_v1.json").read_text(encoding="utf-8"))
    prog = json.loads((rep / "progresion_v1.json").read_text(encoding="utf-8"))
    met = json.loads((rep / "metricas_v1.json").read_text(encoding="utf-8"))
    indirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    try:
        if len(indirs) != 18:
            raise G.Aborta(f"se esperaban 18 directorios data/processed_api_*; hay {len(indirs)}")
        df = G.carga(indirs)
        t = sup["liga_16"]["torneo"]
        import polars as pl
        P, al, sub_l = G.liga_torneo(df, t)
        Q, a0 = bloque_abierto(G, P, al)
        dl = verifica(G, Q, a0, sup["liga_16"]["pi"], f"liga {t}")
        Cl, _ = conteos_abierto(G, sub_l)
        salida = {"adr": "ADR-59 adenda 3 §6 y adenda 4 §5-§6", "nivel": "C", "version": 2,
                  "finales": ["gol", "remate sin gol", "pérdida", "fuera"],
                  "liga": {"torneo": t, "C": Cl.tolist(), "alfa": (a0 / a0.sum()).tolist(), "dif_pi": dl},
                  "eras": []}
        print(f"liga {t}: coincide con supervivencia_v1 (dif {dl:.1e})")
        principales = {(e["club"], e["coach"]): e for e in prog["eras"]}
        coaches = [c for _, c in G.HISTORIAS]
        hid_de = {c: h for h, c in G.HISTORIAS}
        eras = sorted({(u["club"], u["coach"]) for u in met["unidades"] if u["coach"] in coaches})
        for club, coach in eras:
            sub = df.filter((pl.col("club") == club) & (pl.col("coach") == coach))
            if sub.height == 0:
                raise G.Aborta(f"{club} · {coach}: 0 acciones")
            Ce, ae = conteos_abierto(G, sub)
            e = principales.get((club, coach))
            d = None
            if e is not None and e["cuasi"]["evaluable"]:
                Pe, aep = matrices_era(G, df, club, coach)
                Qe, ae0 = bloque_abierto(G, Pe, aep)
                d = verifica(G, Qe, ae0, e["cuasi"]["era"]["pi"], f"{club} · {coach}")
            salida["eras"].append({"hid": hid_de[coach], "club": club, "coach": coach, "principal": e is not None,
                                   "C": Ce.tolist(), "alfa": (ae / max(ae.sum(), 1)).tolist(), "dif_pi": d,
                                   "n_pasos": int(Ce.sum())})
            print(f"{club} · {coach}: {int(Ce.sum())} pasos de juego abierto" +
                  (f" · coincide con progresion_v1 (dif {d:.1e})" if d is not None else ""))
        salida["nombres"] = nombres(indirs, coaches)
        print(f"nombres de jugadores: {len(salida['nombres'])}")
    except G.Aborta as e:
        sys.exit(f"ABORTA: {e}")
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    print(f"escrito {a.out}")


if __name__ == "__main__":
    main()
