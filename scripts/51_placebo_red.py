#!/usr/bin/env python3
"""
51_placebo_red.py — ADR-62 adenda 1: el placebo que decide si H62-1 aguanta.

*** INERTE desde ADR-62 adenda 1c: aborta al arrancar. Tenía el fallo de orden
*** (`bl_a, bl_b = ia[-m:], ib[:m]` supone que la era a va antes que la b).
*** Se deja el código como registro de lo que se corrió.

El nulo por permutación de ADR-62 §4 destruye el orden temporal: compara dos
bloques de tiempo CONTIGUOS (las eras) contra muestras mezcladas en el tiempo,
así que recoge toda la deriva temporal y no solo el cambio de técnico. Por eso
dio 18 de 18 con p = 0.

Aquí se compara contra bloques contiguos DEL MISMO TAMAÑO y SIN cambio de
técnico (adenda 1 §4):

  m            = min(partidos de a, partidos de b), y m >= 5
  T_relevo(m)  = últimos m partidos de la era a  vs  primeros m de la era b
  T_placebo(m) = dentro de CADA era: primeros m vs últimos m (sin relevo)

Criterio fijado ANTES de correr (adenda 1 §5): H62-1 aguanta si T_relevo supera
el percentil 90 de los T_placebo en MÁS DE LA MITAD de los relevos comparables.

Nivel B, fuera de F62. NO toca reports/red_pases_v1.json (D62A-1).

Uso:
    python scripts/51_placebo_red.py
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
PASES = RAIZ / "data" / "pases_api" / "pases.parquet"
ACTA = RAIZ / "reports" / "red_pases_v1.json"

M_MIN = 5              # adenda 1 §4.1
MIN_PASES_BLOQUE = 30  # adenda 1 §4.5
MIN_COMUNES = 8        # adenda 1 §4.5 (igual que D62-3)
TOL = 1e-9


def _g50():
    spec = importlib.util.spec_from_file_location("red50", RAIZ / "scripts" / "50_red_pases.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fechas():
    """match_id -> fecha, de los parquets publicados (única fuente de fechas)."""
    import polars as pl
    dirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    partes = [pl.read_parquet(Path(d) / "transitions.parquet", columns=["match_id", "match_date"])
              for d in dirs]
    t = pl.concat(partes).group_by("match_id").agg(pl.col("match_date").min())
    if t["match_date"].is_null().any():
        raise SystemExit("ABORTA: hay partidos sin match_date")
    return dict(t.rows())


def red_de(G, sub, idx):
    """Matriz JxJ de los pases de `sub` sobre el índice de jugadores `idx`."""
    import polars as pl
    J = len(idx)
    M = np.zeros((J, J))
    g = sub.group_by(["player_id", "recipient_id"]).agg(pl.len().alias("n"))
    for i, j, n in zip(*[g[c].to_list() for c in ("player_id", "recipient_id", "n")]):
        a, b = idx.get(i), idx.get(j)
        if a is not None and b is not None:
            M[a, b] += n
    return M


def T_bloques(G, sub_a, sub_b):
    """T entre dos bloques, restringida a los jugadores con MIN_PASES_BLOQUE en
    los dos. Devuelve (T, n_comunes) o (None, n_comunes) si no llega al mínimo."""
    import polars as pl
    jug = sorted(set(sub_a["player_id"].to_list()) | set(sub_a["recipient_id"].to_list())
                 | set(sub_b["player_id"].to_list()) | set(sub_b["recipient_id"].to_list()))
    idx = {p: k for k, p in enumerate(jug)}
    A, B = red_de(G, sub_a, idx), red_de(G, sub_b, idx)
    na, nb = A.sum(1) + A.sum(0), B.sum(1) + B.sum(0)
    com = (na >= MIN_PASES_BLOQUE) & (nb >= MIN_PASES_BLOQUE)
    n = int(com.sum())
    if n < MIN_COMUNES:
        return None, n
    sel = np.ix_(com, com)
    T = G.T_pares(A[sel], B[sel])
    if T is None or not (0 - TOL <= T <= 1 + TOL):            # D62A-3
        raise SystemExit(f"ABORTA: D62A-3: T = {T} fuera de [0, 1]")
    return T, n


def por_fecha(sub, f):
    """Los match_id de `sub`, ordenados por fecha."""
    ids = sub["match_id"].unique().to_list()
    return [i for _, i in sorted((f[i], i) for i in ids)]


INERTE = ("ABORTA: ADR-62 adenda 1c. Este placebo se corrió una vez (reports/placebo_red_v1.json) y "
          "tenía un fallo: no ordenaba cada par por fecha. No se corrige ni se vuelve a correr, porque "
          "corregirlo solo serviría para correrlo otra vez y el criterio del §5 dependía del número de "
          "relevos evaluables. H62-1 queda sin resolver.")


def main():
    sys.exit(INERTE)          # adenda 1c §4: inerte. El código de abajo queda como registro.
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "placebo_red_v1.json"))
    a = ap.parse_args()
    if Path(a.out).resolve() == ACTA.resolve():                # D62A-1
        sys.exit("ABORTA: D62A-1: el placebo no puede escribir sobre el acta de la corrida única")
    t0 = time.time()
    import polars as pl
    G = _g50()
    if not PASES.exists():
        sys.exit(f"ABORTA: falta {PASES}")
    if not ACTA.exists():
        sys.exit(f"ABORTA: falta {ACTA}: el placebo va DESPUÉS de la corrida única")
    acta = json.loads(ACTA.read_text(encoding="utf-8"))
    f = fechas()
    t = pl.read_parquet(PASES).filter(pl.col("completado") & pl.col("coach").is_not_null()
                                      & pl.col("player_id").is_not_null()
                                      & pl.col("recipient_id").is_not_null())
    filas, placebos = [], []
    for r in acta["relevos"]:
        if "T_red" not in r:            # el relevo ya venía declarado con su hueco
            continue
        club, ca, cb = r["club"], r["a"], r["b"]
        sa = t.filter((pl.col("team") == club) & (pl.col("coach") == ca))
        sb = t.filter((pl.col("team") == club) & (pl.col("coach") == cb))
        ia, ib = por_fecha(sa, f), por_fecha(sb, f)
        # adenda 1b: UN SOLO tamaño de bloque para el relevo y para los dos placebos.
        # Con m = min(k_a, k_b) el placebo de la era corta usaba bloques de k/2, más
        # chicos que los del relevo: más ruido, T más alta, p90 inflado y sesgo contra
        # H62-1. Con m = min(k_a//2, k_b//2) todos los bloques miden igual.
        m = min(len(ia) // 2, len(ib) // 2)
        fila = {"club": club, "a": ca, "b": cb, "n_partidos_a": len(ia), "n_partidos_b": len(ib),
                "m": m, "T_red_eras_completas": r["T_red"]["v"]}
        if m < M_MIN:
            fila["hueco"] = f"m = {m} partidos por bloque; el mínimo preinscrito es {M_MIN}"
            filas.append(fila)
            continue
        # el relevo, con bloques del mismo tamaño y adyacentes al cambio
        bl_a, bl_b = ia[-m:], ib[:m]
        if set(bl_a) & set(bl_b):                              # D62A-2
            sys.exit(f"ABORTA: D62A-2: un partido cae en los dos bloques de {club} {ca}↔{cb}")
        T_rel, n_rel = T_bloques(G, sa.filter(pl.col("match_id").is_in(bl_a)),
                                 sb.filter(pl.col("match_id").is_in(bl_b)))
        fila["T_relevo"] = T_rel
        fila["n_comunes_relevo"] = n_rel
        # los dos placebos: dentro de cada era, primeros m contra últimos m
        fila["placebos"] = []
        for quien, sub, ids in ((ca, sa, ia), (cb, sb, ib)):
            k = len(ids)
            mm = m                                             # adenda 1b: el mismo m
            if k < 2 * mm or mm < M_MIN:
                fila["placebos"].append({"coach": quien, "hueco": f"solo {k} partidos para 2×{mm}"})
                continue
            p1, p2 = ids[:mm], ids[-mm:]
            if set(p1) & set(p2):                              # D62A-2
                sys.exit(f"ABORTA: D62A-2: bloques solapados en el placebo de {club} {quien}")
            T_pl, n_pl = T_bloques(G, sub.filter(pl.col("match_id").is_in(p1)),
                                   sub.filter(pl.col("match_id").is_in(p2)))
            fila["placebos"].append({"coach": quien, "m": mm, "T": T_pl, "n_comunes": n_pl,
                                     **({"hueco": f"solo {n_pl} jugadores comunes"} if T_pl is None else {})})
            if T_pl is not None:
                placebos.append(T_pl)
        filas.append(fila)
        print(f"  {club:<18s} {ca[:18]:<18s} ↔ {cb[:18]:<18s} m={m:2d} · "
              f"T_relevo {T_rel if T_rel is None else round(T_rel, 3)} · "
              f"placebos {[None if p.get('T') is None else round(p['T'], 3) for p in fila['placebos']]}",
              flush=True)
    if len(placebos) < 5:
        sys.exit(f"ABORTA: solo {len(placebos)} placebos calculables; no hay distribución de referencia")
    p50, p90 = float(np.percentile(placebos, 50)), float(np.percentile(placebos, 90))
    comp = [x for x in filas if x.get("T_relevo") is not None]
    supera = [x for x in comp if x["T_relevo"] > p90]
    for x in comp:
        x["supera_p90_placebo"] = bool(x["T_relevo"] > p90)
    n = len(comp)
    aguanta = len(supera) > n / 2 if n else None
    med_rel = float(np.median([x["T_relevo"] for x in comp])) if comp else None
    salida = {"adr": "ADR-62 adenda 1", "nivel": "B", "en_f62": False,
              "parametros": {"m_min": M_MIN, "min_pases_bloque": MIN_PASES_BLOQUE,
                             "min_comunes": MIN_COMUNES,
                             "m": "min(k_a//2, k_b//2), igual en el relevo y en los placebos (adenda 1b)",
                             "criterio": "H62-1 aguanta si T_relevo > p90(placebos) en > 50% de los relevos"},
              "placebos": {"n": len(placebos), "p50": p50, "p90": p90,
                           "valores": [round(x, 6) for x in sorted(placebos)]},
              "relevos": filas,
              "resultado": {"n_comparables": n, "n_superan_p90": len(supera),
                            "mediana_T_relevo": med_rel, "mediana_T_placebo": p50,
                            "diferencia_medianas": (med_rel - p50) if med_rel is not None else None,
                            "H62_1_aguanta": aguanta},
              "segundos": round(time.time() - t0, 1)}
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n=== placebo: {len(placebos)} bloques sin cambio de técnico ===")
    print(f"  mediana T placebo ... {p50:.3f}")
    print(f"  percentil 90 ........ {p90:.3f}")
    print(f"  mediana T relevo .... {med_rel:.3f}" if med_rel is not None else "")
    print(f"  diferencia .......... {med_rel - p50:+.3f}" if med_rel is not None else "")
    print(f"\n  relevos que superan el p90 del placebo: {len(supera)} de {n}")
    print(f"  criterio preinscrito (> {n / 2:.1f}): "
          f"{'H62-1 AGUANTA' if aguanta else 'H62-1 SE RETIRA'}")
    print(f"\nescrito {a.out} · {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
