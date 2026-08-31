#!/usr/bin/env python3
"""
26_goal_open_barrido.py — la familia `goal_open-eras` con control de FDR.

FAMILIA DECLARADA ANTES DE MIRAR NINGÚN RESULTADO (2026-08-26)
--------------------------------------------------------------
  Alcance   : una comparación por cada pareja de entrenadores CONTIGUOS en el
              tiempo, dentro del mismo club, con al menos `--min-remates`
              remates de juego abierto en las dos eras.
  Cantidades: tres por pareja —
                1. diferencia en xG_base medio  (posición del remate)
                2. atribución geométrica         (xG_full - xG_base)
                3. tasa empírica de gol
  Corrección: Benjamini-Hochberg al 5% sobre TODAS las pruebas de la familia.

Se declara aquí, en el código, y se copia al JSON de salida con la fecha. Es la
regla de ADR-47: decidir la estructura de la familia DESPUÉS de ver los números
es p-hacking sobre la multiplicidad, aunque el razonamiento sea correcto.

POR QUÉ ESTE SCRIPT EXISTE
--------------------------
`10_RESULTADOS.md` §16.3 registra una afirmación retirada: "Jardine gana más
balones al primer toque", p=0.0206 sin corregir, q=0.0935 sobre 46 contrastes.
Era un falso positivo marginal, exactamente lo que el FDR existe para atrapar.

Al pasar de un par a varios, `25_goal_open_eras.py` deja de ser suficiente.

TRES DECISIONES METODOLÓGICAS
-----------------------------
1. **BH bajo dependencia.** Las tres cantidades de una pareja NO son
   independientes: xG_base y la atribución salen del mismo modelo. BH conserva
   el control del FDR bajo dependencia POSITIVA (PRDS), que es el caso. Se
   declara en vez de suponerlo. Benjamini-Yekutieli (`--by`) está disponible
   como alternativa conservadora si un revisor lo objeta.

2. **Números pseudoaleatorios comunes.** Cada réplica bootstrap remuestrea los
   partidos UNA vez y calcula las tres cantidades sobre esa misma remuestra.
   Reduce la varianza de las comparaciones entre cantidades y las hace
   coherentes. Es la técnica CRN del temario de simulación.

3. **El modelo se ajusta UNA vez por club**, no por pareja. Reajustarlo en cada
   contraste cambiaría la escala del xG entre comparaciones y las volvería
   incomparables. El modelo de xG es un estorbo a estimar, no el estimando.

Uso:
    python scripts/26_goal_open_barrido.py \\
      --club "América"   --eventos eventos_completos_america.csv \\
                         --parquet data/processed/transitions.parquet \\
      --club "Cruz Azul" --eventos eventos_completos_cruz_azul.csv \\
                         --parquet data/processed_cruzazul/transitions.parquet
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dtdecoder.geometria_remate import Contadores, RADIO_DEFENSOR  # noqa: E402
from dtdecoder.xg_remate import (  # noqa: E402
    ATA, DEF, SEED, fuera_de_pliegue, features,
)

DECLARACION = {
    "familia": "goal_open-eras",
    "declarada": "2026-08-26",
    "antes_de_ver_resultados": True,
    "alcance": "parejas de entrenadores contiguos en el tiempo, mismo club",
    "cantidades_por_pareja": ["dif xG_base (posición)",
                              "atribución geométrica",
                              "tasa empírica de gol"],
    "correccion": "Benjamini-Hochberg, alpha=0.05",
    "dependencia": "las 3 cantidades de una pareja son dependientes (PRDS); "
                   "BH conserva el control del FDR bajo dependencia positiva",
    "bloque_de_remuestreo": "partido",
}


# ======================================================================
def carga_club(eventos, parquet, club, radio):
    lf = pl.scan_csv(eventos, infer_schema_length=None)
    cols = lf.collect_schema().names()
    extra = ["shot_statsbomb_xg"] if "shot_statsbomb_xg" in cols else []
    d = (lf.filter((pl.col("type") == "Shot") & (pl.col("team") == club)
                   & (pl.col("shot_type") == "Open Play"))
           .select(["match_id", "location", "shot_freeze_frame",
                    "shot_outcome"] + extra)
           .collect())

    t = pl.read_parquet(parquet)
    eras = t.select(["match_id", "coach"]).drop_nulls().unique()
    # Orden CRONOLÓGICO de las eras: hace falta para saber qué parejas son
    # contiguas. `match_date` está en el parquet (fechas derivadas, ADR-26).
    if "match_date" in t.columns:
        ord_ = (t.select(["coach", "match_date"]).drop_nulls()
                 .group_by("coach").agg(pl.col("match_date").min().alias("ini"))
                 .sort("ini"))
    else:
        ord_ = (t.select(["coach", "match_id"]).drop_nulls()
                 .group_by("coach").agg(pl.col("match_id").min().alias("ini"))
                 .sort("ini"))
    orden = ord_["coach"].to_list()
    d = d.join(eras, on="match_id", how="left")

    cont = Contadores()
    filas, y, blo, era = [], [], [], []
    for row in d.iter_rows(named=True):
        f = features(row["location"], row["shot_freeze_frame"], radio, cont)
        if f is None or not np.isfinite(f["goal_open"]):
            continue
        filas.append([f[c] for c in ATA + DEF])
        y.append(1 if row["shot_outcome"] == "Goal" else 0)
        blo.append(row["match_id"])
        era.append(row["coach"] or "")
    M = np.array(filas, float)
    ok = np.isfinite(M).all(1)
    return (M[ok], np.array(y, float)[ok], np.array(blo)[ok],
            np.array(era)[ok], orden, cont)


def p_bootstrap(muestras, B):
    """Nivel de significancia alcanzado, bilateral, con corrección de Davison.

    El +1 evita p=0 exacto, que con B réplicas no es estimable: lo mínimo
    reportable es 2/(B+1).
    """
    v = np.asarray(muestras)
    if len(v) == 0:
        return 1.0
    lo = (1 + (v <= 0).sum()) / (len(v) + 1)
    hi = (1 + (v >= 0).sum()) / (len(v) + 1)
    return float(min(1.0, 2 * min(lo, hi)))


def benjamini_hochberg(p, alpha=0.05, by=False):
    """Devuelve (q-valores, rechazos). `by=True` usa Benjamini-Yekutieli."""
    p = np.asarray(p, float)
    m = len(p)
    c = np.sum(1.0 / np.arange(1, m + 1)) if by else 1.0
    orden = np.argsort(p)
    q = np.empty(m)
    prev = 1.0
    for k in range(m - 1, -1, -1):
        i = orden[k]
        val = min(prev, p[i] * m * c / (k + 1))
        q[i] = val
        prev = val
    return q, q <= alpha


# ======================================================================
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", action="append", required=True)
    ap.add_argument("--eventos", action="append", required=True)
    ap.add_argument("--parquet", action="append", required=True)
    ap.add_argument("--min-remates", type=int, default=150)
    ap.add_argument("--radio", type=float, default=RADIO_DEFENSOR)
    ap.add_argument("--lam", type=float, default=3.0)
    ap.add_argument("--n-boot", type=int, default=4000)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--by", action="store_true",
                    help="Benjamini-Yekutieli en vez de BH (conservador)")
    ap.add_argument("--out", default="reports/fdr_goal_open.json")
    a = ap.parse_args()

    if not (len(a.club) == len(a.eventos) == len(a.parquet)):
        sys.exit("--club, --eventos y --parquet deben ir en tríos")

    print("=" * 72)
    print("FAMILIA DECLARADA ANTES DE VER LOS RESULTADOS")
    print("=" * 72)
    for k, v in DECLARACION.items():
        print(f"  {k:24} {v}")
    print(f"  ejecutado                {date.today():%Y-%m-%d}")

    rng = np.random.default_rng(SEED)
    pruebas = []

    for club, ev, pq in zip(a.club, a.eventos, a.parquet):
        M, y, blo, era, orden, cont = carga_club(ev, pq, club, a.radio)
        print("\n" + "=" * 72)
        print(f"{club}: {len(y):,} remates de juego abierto, {int(y.sum())} goles")
        print(f"  geometría: {cont.resumen()}")

        # UN modelo por club, no uno por pareja (decisión 3 del encabezado)
        p_base = fuera_de_pliegue(M[:, :len(ATA)], y, blo, lam=a.lam, rng=rng)
        p_full = fuera_de_pliegue(M, y, blo, lam=a.lam, rng=rng)

        presentes = [c for c in orden if (era == c).sum() >= a.min_remates]
        print(f"  orden cronológico con >= {a.min_remates} remates: "
              f"{' -> '.join(presentes)}")
        excluidas = [c for c in orden if c and c not in presentes
                     and (era == c).sum() > 0]
        if excluidas:
            print(f"  excluidas por muestra: "
                  f"{', '.join(f'{c} ({(era==c).sum()})' for c in excluidas)}")

        ub = np.unique(blo)
        idx_de = {b: np.where(blo == b)[0] for b in ub}

        for k in range(len(presentes) - 1):
            # el técnico POSTERIOR es "a": la pregunta es qué cambió al llegar
            b_, a_ = presentes[k], presentes[k + 1]
            ia, ib = era == a_, era == b_
            print(f"\n  --- {a_} (n={ia.sum()}) vs {b_} (n={ib.sum()}) ---")

            def stats(idx):
                sa, sb = ia[idx], ib[idx]
                if sa.sum() < 10 or sb.sum() < 10:
                    return None
                dbase = p_base[idx][sa].mean() - p_base[idx][sb].mean()
                dfull = p_full[idx][sa].mean() - p_full[idx][sb].mean()
                return (dbase, dfull - dbase, y[idx][sa].mean() - y[idx][sb].mean())

            obs = stats(np.arange(len(y)))
            # CRN: una sola remuestra de partidos por réplica, las tres
            # cantidades sobre ella. Coherentes entre sí y menos varianza.
            reps = []
            for _ in range(a.n_boot):
                sel = rng.choice(ub, size=len(ub), replace=True)
                idx = np.concatenate([idx_de[x] for x in sel])
                s = stats(idx)
                if s is not None:
                    reps.append(s)
            reps = np.array(reps)

            nombres = ["dif xG_base (posición)", "atribución geométrica",
                       "tasa de gol"]
            for j, nom in enumerate(nombres):
                v = reps[:, j]
                p = p_bootstrap(v, a.n_boot)
                lo, hi = np.percentile(v, [2.5, 97.5])
                print(f"      {nom:24} {obs[j]:+.4f}  "
                      f"IC95 [{lo:+.4f}, {hi:+.4f}]  p={p:.4f}")
                pruebas.append({"club": club, "era_a": a_, "era_b": b_,
                                "cantidad": nom, "estimador": float(obs[j]),
                                "lo": float(lo), "hi": float(hi), "p": p,
                                "n_a": int(ia.sum()), "n_b": int(ib.sum())})

    # ---------------- FDR sobre la familia completa ----------------
    if not pruebas:
        sys.exit("ninguna pareja alcanzó el mínimo de muestra")
    ps = [t["p"] for t in pruebas]
    q, rech = benjamini_hochberg(ps, alpha=a.alpha, by=a.by)
    for t, qq, rr in zip(pruebas, q, rech):
        t["q"] = float(qq)
        t["sobrevive"] = bool(rr)

    metodo = "Benjamini-Yekutieli" if a.by else "Benjamini-Hochberg"
    print("\n" + "=" * 72)
    print(f"{metodo.upper()} SOBRE {len(pruebas)} PRUEBAS  (alpha={a.alpha})")
    print("=" * 72)
    print(f"  {'pareja':38}{'cantidad':26}{'p':>8}{'q':>8}  ")
    for t in sorted(pruebas, key=lambda z: z["p"]):
        par = f'{t["era_a"][:16]} vs {t["era_b"][:16]}'
        marca = "SOBREVIVE" if t["sobrevive"] else ""
        print(f"  {par:38}{t['cantidad']:26}{t['p']:8.4f}{t['q']:8.4f}  {marca}")

    n_ok = sum(t["sobrevive"] for t in pruebas)
    print(f"\n  {n_ok} de {len(pruebas)} sobreviven a la corrección.")
    if n_ok == 0:
        print("\n  NINGUNA sobrevive. El resultado reportable es que no")
        print("  detectamos diferencias de calidad de remate entre eras")
        print("  mayores que las que produce el azar al mirar tantas parejas.")
        print("  NO es lo mismo que 'no hay diferencia'.")

    salida = {"declaracion": DECLARACION, "ejecutado": f"{date.today():%Y-%m-%d}",
              "metodo": metodo, "alpha": a.alpha, "radio": a.radio,
              "n_pruebas": len(pruebas), "n_sobreviven": n_ok,
              "pruebas": pruebas}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(salida, indent=2, ensure_ascii=False))
    print(f"\nguardado en {a.out}")


if __name__ == "__main__":
    main()
