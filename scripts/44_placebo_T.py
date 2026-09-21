#!/usr/bin/env python3
"""
44_placebo_T.py — ADR-60 adenda 1 §4: placebo EXPLORATORIO para T.

¿Cuánto cambia el uso del campo SIN cambio de técnico? Cada era de F60 (o del
control) con al menos 20 partidos se parte en dos mitades por fecha y se
calcula T entre ellas con el MISMO código de 42_relevos.py: ocupación en
exceso de la liga del mismo torneo sin el club, nula por permutación (B = 999).

Nivel C. No cambia ningún veredicto de F60 ni el marcador. La lectura (A o B)
se fijó en la adenda antes de correr esto:

  k = número de T de relevo por encima del percentil 90 del placebo
  A · k ≥ 11 de 21 · B · k ≤ 10

Uso:
    python scripts/44_placebo_T.py --out reports/placebo_v1.json
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
MIN_PARTIDOS = 20
N_PERM = 999
K_LECTURA_A = 11
LECTURAS = {
    "A": "los relevos mueven el uso del campo más que el paso del tiempo dentro de una misma era",
    "B": "no distinguimos el cambio que acompaña a un relevo del que ya ocurre dentro de una misma era",
}


def _r42():
    spec = importlib.util.spec_from_file_location("relevos42", RAIZ / "scripts" / "42_relevos.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mitades(partidos):
    """[(fecha, match_id)] -> (primera, segunda). Mismo número de partidos; si
    es impar, el del medio va a la primera mitad (adenda 1 §4)."""
    orden = [m for _, m in sorted(partidos)]
    corte = (len(orden) + 1) // 2
    return orden[:corte], orden[corte:]


def lectura(k):
    return "A" if k >= K_LECTURA_A else "B"


def percentil(v, xs):
    xs = sorted(xs)
    return sum(x <= v for x in xs) / len(xs)


def placebo_era(R, df, liga, club, coach, rng, n_perm=N_PERM):
    """T entre las dos mitades de una era, con el código de 42. None si la era
    tiene menos de MIN_PARTIDOS partidos."""
    import polars as pl
    sub = df.filter((pl.col("club") == club) & (pl.col("coach") == coach))
    ps = sub.group_by("match_id").agg(pl.col("match_date").min()).select("match_date", "match_id").rows()
    if any(f is None for f, _ in ps):
        raise R.Aborta(f"{club} · {coach}: hay partidos sin match_date; no se pueden ordenar por fecha")
    if len(ps) < MIN_PARTIDOS:
        return None, len(ps)
    m1, m2 = mitades(ps)
    etq = {**{m: f"{coach}|1" for m in m1}, **{m: f"{coach}|2" for m in m2}}
    df2 = sub.with_columns(pl.col("match_id").replace_strict(etq, return_dtype=pl.Utf8).alias("coach"))
    A = R.arreglos_pareja(df2, liga, club, f"{coach}|1", f"{coach}|2")
    r = R.analiza(A, rng, n_perm, 0)
    return {"club": club, "coach": coach, "n_partidos": len(ps), "n_1": len(m1), "n_2": len(m2),
            "T": r["T"], "p": r["p"], "T_nula_p95": r["T_nula_p95"]}, len(ps)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "placebo_v1.json"))
    ap.add_argument("--seed", type=int, default=20260922)
    a = ap.parse_args()
    import polars as pl
    R = _r42()
    t0 = time.time()
    rep = Path(a.reports)
    rel = json.loads((rep / "relevos_v1.json").read_text(encoding="utf-8"))
    h4 = json.loads((rep / "did_h4_v1.json").read_text(encoding="utf-8"))
    met = json.loads((rep / "metricas_v1.json").read_text(encoding="utf-8"))
    indirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    try:
        if len(indirs) != 18:
            raise R.Aborta(f"se esperaban 18 directorios data/processed_api_*; hay {len(indirs)}")
        fam, _ = R.familia(h4, met)
        eras = sorted({(c, x) for c, a_, b_ in fam + [R.CONTROL] for x in (a_, b_)})
        df = R.carga_acciones(indirs)
        liga = R.referencia_liga(df)
        rng = np.random.default_rng(a.seed)
        placebos, excluidas = [], []
        for club, coach in eras:
            r, n = placebo_era(R, df, liga, club, coach, rng)
            if r is None:
                excluidas.append({"club": club, "coach": coach, "n_partidos": n})
                continue
            placebos.append(r)
            print(f"  {club:<18s} {coach:<24s} {n:>3d} partidos · T placebo {r['T']:.3f}", flush=True)
    except R.Aborta as e:
        sys.exit(f"ABORTA: {e}")
    Ts = [p["T"] for p in placebos]
    if len(Ts) < 5:
        sys.exit(f"ABORTA: solo {len(Ts)} eras con al menos {MIN_PARTIDOS} partidos")
    p90 = float(np.quantile(Ts, 0.9))
    relevos = [{"club": p["club"], "a": p["a"], "b": p["b"], "T": p["T"],
                "percentil_placebo": percentil(p["T"], Ts), "sobre_p90": p["T"] > p90}
               for p in rel["pares"]]
    k = sum(r["sobre_p90"] for r in relevos)
    let = lectura(k)
    c = rel["control_negativo"]
    salida = {
        "adr": "ADR-60 adenda 1 §4", "nivel": "C", "exploratorio": True,
        "preinscripcion": "docs/preinscritos/ADR-60_ADENDA_1.md (commit c16ae6c)",
        "parametros": {"min_partidos": MIN_PARTIDOS, "n_perm": N_PERM, "seed": a.seed,
                       "k_lectura_A": K_LECTURA_A},
        "placebos": placebos, "excluidas": excluidas,
        "resumen": {"n": len(Ts), "mediana": float(np.median(Ts)), "p90": p90,
                    "min": float(min(Ts)), "max": float(max(Ts))},
        "relevos": relevos, "k": k, "de": len(relevos),
        "lectura": let, "lectura_texto": LECTURAS[let],
        "control": {"club": c["club"], "a": c["a"], "b": c["b"], "T": c["T"],
                    "percentil_placebo": percentil(c["T"], Ts)},
        "segundos": round(time.time() - t0, 1),
    }
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    s = salida["resumen"]
    print(f"escrito {a.out} · {s['n']} placebos · mediana {s['mediana']:.3f} · p90 {p90:.3f} · "
          f"{k} de {len(relevos)} relevos por encima del p90 · lectura {let}: {LECTURAS[let]}")


if __name__ == "__main__":
    main()
