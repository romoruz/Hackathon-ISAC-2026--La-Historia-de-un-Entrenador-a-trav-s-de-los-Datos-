#!/usr/bin/env python3
"""
47_jugadores_zona.py — ADR-63: los mismos jugadores, con otro técnico.

Para cada pareja de técnicos consecutivos en el mismo club (las de
`did_h4_v1 › pares`, sin añadir ninguna), calcula para cada jugador presente en
las dos eras su distribución de toques por zona (20 zonas, suma 1) y la
distancia de variación total T = ½‖p_a − p_b‖₁ entre las dos.

TODO ES DESCRIPTIVO (nivel C): sin familia, sin p, sin q, sin veredicto y fuera
del marcador. Se publica un nulo de referencia (ADR-63 §4): la misma T entre las
dos mitades por fecha de una misma era, donde el técnico NO cambia.

Guardas que abortan: D63-5 (cada distribución suma 1), D63-6 (T en [0, 1]),
D63-7 (ningún jugador repetido en una pareja), D63-8 (sin player_id, aborta).

Uso:
    python scripts/47_jugadores_zona.py --out reports/jugadores_zona_v1.json
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
UMBRAL_TOQUES = 200      # D63-1
MIN_JUGADORES = 5        # D63-2
TOL = 1e-9


def _g45():
    spec = importlib.util.spec_from_file_location("prog45", RAIZ / "scripts" / "45_progresion.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def carga(G, indirs):
    """Como 45.carga, pero exigiendo player_id (D63-8) y quedándose con lo justo."""
    import polars as pl
    partes = []
    for d in indirs:
        p = Path(d) / "transitions.parquet"
        if not p.exists():
            raise G.Aborta(f"falta {p}")
        cols = set(pl.read_parquet_schema(p))
        need = ["match_id", "team", "coach", "from_state", "match_date", "player_id"]
        falta = [c for c in need if c not in cols]
        if falta:
            raise G.Aborta(f"D63-8: {p} no trae {falta}; no se inventa un sustituto")
        extra = [c for c in ("player", "position") if c in cols]
        t = (pl.read_parquet(p, columns=need + extra)
             .filter(pl.col("coach").is_not_null() & pl.col("player_id").is_not_null()))
        eq = t["team"].unique().to_list()
        if len(eq) != 1:
            raise G.Aborta(f"{p}: las filas con técnico son de {len(eq)} equipos")
        partes.append(t.with_columns(pl.lit(eq[0]).alias("club")))
    return pl.concat(partes, how="diagonal_relaxed")


def reparto(G, sub):
    """{player_id: (vector de 20 que suma 1, n_toques)} para las filas dadas."""
    import polars as pl
    z = (pl.col("from_state") // G.NF).alias("z")
    t = sub.with_columns(z).group_by(["player_id", "z"]).agg(pl.len().alias("n"))
    out = {}
    for pid, zz, nn in zip(*[t[c].to_list() for c in ("player_id", "z", "n")]):
        v = out.setdefault(int(pid), np.zeros(20))
        v[int(zz)] += nn
    return {k: (v / v.sum(), int(v.sum())) for k, v in out.items() if v.sum() > 0}


def T_de(pa, pb):
    return float(np.abs(np.asarray(pa) - np.asarray(pb)).sum() / 2)


def nombres_y_pos(G, sub):
    import polars as pl
    nom, pos = {}, {}
    if "player" in sub.columns:
        t = (sub.filter(pl.col("player").is_not_null())
             .group_by(["player_id", "player"]).agg(pl.len().alias("n"))
             .sort(["player_id", "n"], descending=[False, True])
             .group_by("player_id", maintain_order=True).first())
        nom = {int(i): p for i, p in t.select("player_id", "player").iter_rows()}
    if "position" in sub.columns:
        t = (sub.filter(pl.col("position").is_not_null())
             .group_by(["player_id", "position"]).agg(pl.len().alias("n"))
             .sort(["player_id", "n"], descending=[False, True])
             .group_by("player_id", maintain_order=True).first())
        pos = {int(i): p for i, p in t.select("player_id", "position").iter_rows()}
    return nom, pos


def mitades(G, sub):
    """ADR-63 §4: parte los partidos de la era en dos por fecha."""
    import polars as pl
    ps = sub.group_by("match_id").agg(pl.col("match_date").min()).select("match_date", "match_id").rows()
    if any(f is None for f, _ in ps):
        raise G.Aborta("hay partidos sin match_date; no se pueden ordenar por fecha")
    ids = [i for _, i in sorted(ps)]
    if len(ids) < 4:
        return None
    c = len(ids) // 2
    return (sub.filter(pl.col("match_id").is_in(ids[:c])),
            sub.filter(pl.col("match_id").is_in(ids[c:])))


def nulo_de(G, sub):
    """T de los mismos jugadores entre las dos mitades de una era, sin cambio de técnico."""
    m = mitades(G, sub)
    if m is None:
        return []
    ra, rb = reparto(G, m[0]), reparto(G, m[1])
    return [T_de(ra[k][0], rb[k][0]) for k in set(ra) & set(rb)
            if ra[k][1] >= UMBRAL_TOQUES // 2 and rb[k][1] >= UMBRAL_TOQUES // 2]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "jugadores_zona_v1.json"))
    a = ap.parse_args()
    G = _g45()
    rep = Path(a.reports)
    h4 = json.loads((rep / "did_h4_v1.json").read_text(encoding="utf-8"))
    indirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    try:
        if len(indirs) != 18:
            raise G.Aborta(f"se esperaban 18 directorios data/processed_api_*; hay {len(indirs)}")
        import polars as pl
        df = carga(G, indirs)
        coaches = {c for _, c in G.HISTORIAS}
        pares = [p for p in h4["pares"]
                 if p["a"] in coaches or p["b"] in coaches]
        salida = {"adr": "ADR-63", "nivel": "C",
                  "parametros": {"umbral_toques": UMBRAL_TOQUES, "min_jugadores": MIN_JUGADORES,
                                 "fases": "todas", "zonas": 20,
                                 "nulo": "mitades por fecha de la misma era, sin cambio de técnico"},
                  "pares": []}
        for p in pares:
            club, ca, cb = p["club"], p["a"], p["b"]
            sa = df.filter((pl.col("club") == club) & (pl.col("coach") == ca))
            sb = df.filter((pl.col("club") == club) & (pl.col("coach") == cb))
            if sa.height == 0 or sb.height == 0:
                continue
            ra, rb = reparto(G, sa), reparto(G, sb)
            nom, pos = nombres_y_pos(G, pl.concat([sa, sb], how="diagonal_relaxed"))
            comunes = sorted(k for k in set(ra) & set(rb)
                             if ra[k][1] >= UMBRAL_TOQUES and rb[k][1] >= UMBRAL_TOQUES)   # D63-1
            fila = {"club": club, "a": ca, "b": cb, "n_jugadores": len(comunes)}
            if len(comunes) < MIN_JUGADORES:                                                # D63-2
                fila["hueco"] = (f"solo {len(comunes)} jugadores con al menos {UMBRAL_TOQUES} "
                                 f"toques en las dos etapas; el mínimo preinscrito es {MIN_JUGADORES}")
                salida["pares"].append(fila)
                print(f"{club} · {ca} ↔ {cb}: hueco ({len(comunes)} jugadores)")
                continue
            js = []
            for k in comunes:
                pa, na = ra[k]
                pb, nb = rb[k]
                for v, quien in ((pa, ca), (pb, cb)):                                       # D63-5
                    if abs(v.sum() - 1) > TOL:
                        raise G.Aborta(f"D63-5: la distribución de {k} con {quien} suma {v.sum()}")
                T = T_de(pa, pb)
                if not (0 - TOL <= T <= 1 + TOL):                                           # D63-6
                    raise G.Aborta(f"D63-6: T = {T} fuera de [0, 1] para {k}")
                js.append({"player_id": int(k), "nombre": nom.get(int(k), str(int(k))),
                           "posicion_modal": pos.get(int(k)), "toques_a": na, "toques_b": nb,
                           "p_a": [round(x, 6) for x in pa], "p_b": [round(x, 6) for x in pb],
                           "dif": [round(x - y, 6) for x, y in zip(pa, pb)], "T": round(T, 6)})
            if len({j["player_id"] for j in js}) != len(js):                                # D63-7
                raise G.Aborta(f"D63-7: {club} {ca}↔{cb} trae un jugador repetido")
            js.sort(key=lambda j: -j["T"])
            nl = nulo_de(G, sa) + nulo_de(G, sb)
            fila["jugadores"] = js
            fila["nulo"] = ({"p50": round(float(np.percentile(nl, 50)), 6),
                             "p90": round(float(np.percentile(nl, 90)), 6), "n": len(nl)}
                            if len(nl) >= MIN_JUGADORES else
                            {"hueco": f"solo {len(nl)} medias etapas comparables", "n": len(nl)})
            salida["pares"].append(fila)
            print(f"{club} · {ca} ↔ {cb}: {len(js)} jugadores · el que más se movió, "
                  f"{js[0]['nombre']} ({js[0]['T']:.3f})")
    except G.Aborta as e:
        sys.exit(f"ABORTA: {e}")
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    con = [p for p in salida["pares"] if "jugadores" in p]
    print(f"escrito {a.out} · {len(con)} parejas con datos de {len(salida['pares'])}")


if __name__ == "__main__":
    main()
