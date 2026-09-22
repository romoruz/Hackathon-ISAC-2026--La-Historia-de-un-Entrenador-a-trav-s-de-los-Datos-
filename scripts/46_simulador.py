#!/usr/bin/env python3
"""
46_simulador.py — ADR-59 adenda 3 §6: los datos del simulador "dónde vive el balón".

Exporta la matriz del bloque de juego abierto (20 × 20) de la liga del torneo de
1.6 y de la era principal de cada historia, con las mismas funciones de
45_progresion.py (λ = 0, la misma base). No es inferencia nueva (nivel C).

Guarda: la distribución cuasi-estacionaria que sale de cada matriz exportada
tiene que coincidir a 1e-9 con la ya publicada en supervivencia_v1 › liga_16.pi
y progresion_v1 › eras[].cuasi.era.pi. Si no, aborta.

Uso:
    python scripts/46_simulador.py --out reports/simulador_v1.json
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
    ap.add_argument("--out", default=str(RAIZ / "reports" / "simulador_v1.json"))
    a = ap.parse_args()
    G = _g45()
    rep = Path(a.reports)
    sup = json.loads((rep / "supervivencia_v1.json").read_text(encoding="utf-8"))
    prog = json.loads((rep / "progresion_v1.json").read_text(encoding="utf-8"))
    indirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    try:
        if len(indirs) != 18:
            raise G.Aborta(f"se esperaban 18 directorios data/processed_api_*; hay {len(indirs)}")
        df = G.carga(indirs)
        t = sup["liga_16"]["torneo"]
        P, al, _ = G.liga_torneo(df, t)
        Q, a0 = bloque_abierto(G, P, al)
        dl = verifica(G, Q, a0, sup["liga_16"]["pi"], f"liga {t}")
        salida = {"adr": "ADR-59 adenda 3 §6", "nivel": "C",
                  "liga": {"torneo": t, "Q": Q.tolist(), "alfa": (a0 / a0.sum()).tolist(), "dif_pi": dl},
                  "eras": []}
        print(f"liga {t}: coincide con supervivencia_v1 (dif {dl:.1e})")
        for e in prog["eras"]:
            Pe, ae = matrices_era(G, df, e["club"], e["coach"])
            Qe, ae0 = bloque_abierto(G, Pe, ae)
            pub = e["cuasi"]["era"]["pi"] if e["cuasi"]["evaluable"] else None
            d = verifica(G, Qe, ae0, pub, f"{e['club']} · {e['coach']}")
            salida["eras"].append({"hid": e["hid"], "club": e["club"], "coach": e["coach"], "Q": Qe.tolist(),
                                   "alfa": (ae0 / ae0.sum()).tolist(), "dif_pi": d})
            print(f"{e['club']} · {e['coach']}: " + ("coincide con progresion_v1 (dif %.1e)" % d if d is not None
                                                   else "no evaluable en progresion_v1; se exporta sin guarda"))
    except G.Aborta as e:
        sys.exit(f"ABORTA: {e}")
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    print(f"escrito {a.out}")


if __name__ == "__main__":
    main()
