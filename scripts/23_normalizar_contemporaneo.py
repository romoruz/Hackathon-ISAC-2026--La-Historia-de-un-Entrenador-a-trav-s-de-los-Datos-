#!/usr/bin/env python3
"""
23_normalizar_contemporaneo.py — el estimando robusto a la deriva del proveedor.

EL PROBLEMA QUE RESUELVE
========================
Hudl StatsBomb cambio su granularidad de anotacion entre 2022 y 2023: los
eventos crudos por partido saltan de ~1,512 a ~1,705 (+12.6%) en dos cortes
independientes, con 17 de 18 clubes moviendose en el mismo sentido. La
distribucion de `play_pattern` casi no se mueve, asi que no cambio como se
juega: cambio cuanto se anota.

Las eras del America caen a los dos lados de ese escalon:

    Solari  jul 2021 - mar 2022   entero ANTES
    Ortiz   mar 2022 - jun 2023   A CABALLO
    Jardine jul 2023 - 2026       entero DESPUES

y sus acciones por posesion son 6.30, 7.32, 8.04: monotonas en el orden
cronologico y del mismo orden de magnitud que el escalon. La diferencia que
ibamos a atribuir a estilo esta confundida con el cambio de registro.

LA CORRECCION
=============
Se compara al entrenador contra la LIGA CONTEMPORANEA, partido a partido.
Es el efecto fijo temporal de la econometria de panel: si la deriva afecta a
los 18 clubes por igual dentro de un torneo, el cociente la cancela.

    R = E[T | foco]  /  E[T | liga del MISMO torneo, sin el club focal]

ponderando la liga por la composicion de torneos del propio foco, para que la
era de Ortiz --a caballo del escalon-- se compare contra la mezcla que a ella
le toco y no contra un promedio que no vivio.

REGLAS PREINSCRITAS (2026-09-14, antes de correr esto)
======================================================

N1. LA REFERENCIA EXCLUYE AL CLUB FOCAL. Sin eso es fuga de prior otra vez:
    el America es 1/18 de su propia referencia y Jardine el 53% del America.

N2. NINGUNA CANTIDAD SIN SU NULA (ADR-30). Un cociente entre dos estimadores
    hereda las dos varianzas. Se reportan:
      - IC bootstrap por `poss_uid`, la unidad de remuestreo del proyecto;
      - y la nula empirica: la distribucion de R sobre TODAS las unidades
        (club, torneo) de la liga. Un R de 1.06 solo significa algo contra la
        dispersion de los R que la liga produce.

N3. EL ESTIMANDO CAMBIA Y SE DICE EN EL REPORTE. Ya no es "Jardine sostiene
    8.04 acciones por posesion", es "Jardine sostiene un X% mas que sus
    contemporaneos". Es mas defendible y es una afirmacion DISTINTA. No se
    pueden mezclar las dos en el mismo parrafo.

N4. ESTO NO ARREGLA LAS MATRICES. El desmedianado transversal corrige un
    ESCALAR. El entregable de H4 son matrices: huella G^2, distancias TV,
    contraste de Fase 3. Si la deriva altero la FORMA de la matriz --por
    ejemplo fragmentando acarreos, que convierte una transicion larga en dos
    cortas y engorda la diagonal-- ningun cociente lo arregla. La correccion a
    nivel matricial es otra: construir la LINEA BASE con los partidos de los
    MISMOS torneos que el foco, para que la deriva sea un efecto comun que se
    cancela en el contraste (mismo argumento que ADR-21). Este script emite la
    tabla `torneos_del_foco` que esa correccion necesita.

Uso:

    python scripts/23_normalizar_contemporaneo.py \\
        --indirs data/processed_api_america \\
        --prior-from data/prior_liga \\
        --out reports/normalizado.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from dtdecoder.cli import _read_trans

N_BOOT = 1000
SEED = 11235       # inference.boot_seed del config


def torneo_cols() -> list[pl.Expr]:
    anio = pl.col("match_date").dt.year()
    ap = pl.col("match_date").dt.month() >= 7
    return [
        pl.when(ap).then(pl.lit("A") + anio.cast(pl.Utf8))
        .otherwise(pl.lit("C") + anio.cast(pl.Utf8)).alias("torneo"),
        (anio * 2 + ap.cast(pl.Int32)).alias("torneo_orden"),
    ]


def largo_posesiones(df: pl.DataFrame) -> pl.DataFrame:
    """(poss_uid, torneo, acciones). Una fila por posesion."""
    return (
        df.group_by(["poss_uid", "torneo", "torneo_orden"])
        .agg(pl.len().alias("acciones"))
    )


def media_ponderada_por_mezcla(
    ref: pl.DataFrame, mezcla: dict[str, float]
) -> float:
    """E[T] de la referencia, reponderada a la mezcla de torneos del foco.

    Sin esto, una era a caballo del escalon (Ortiz) se compararia contra un
    promedio de liga que incluye torneos que esa era no jugo.
    """
    m = (ref.group_by("torneo").agg(pl.col("acciones").mean().alias("m"))
         .to_dicts())
    por_t = {r["torneo"]: r["m"] for r in m}
    num = sum(w * por_t[t] for t, w in mezcla.items() if t in por_t)
    den = sum(w for t in mezcla if t in por_t for w in [mezcla[t]])
    return float(num / den) if den > 0 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indirs", nargs="+", required=True, type=Path)
    ap.add_argument("--prior-from", required=True, type=Path, dest="prior_from")
    ap.add_argument("--n-boot", type=int, default=N_BOOT, dest="n_boot")
    ap.add_argument("--out", type=Path, default=Path("reports/normalizado.json"))
    args = ap.parse_args()

    liga = _read_trans(str(args.prior_from), permitir_prior=True)
    if "match_date" not in liga.columns:
        raise SystemExit(
            "El artefacto de prior no trae `match_date`: se genero con una "
            "version anterior de `dtdecoder prior`. Vuelve a correrlo."
        )
    liga = liga.with_columns(torneo_cols())
    # Una fila por posesion, con su torneo y su equipo.
    pos_liga = (
        liga.group_by(["poss_uid", "torneo", "torneo_orden", "team"])
        .agg(pl.len().alias("acciones"))
    )
    print(f"liga: {pos_liga.height:,} posesiones, "
          f"{pos_liga['torneo'].n_unique()} torneos, "
          f"{pos_liga['team'].n_unique()} equipos\n")

    rng = np.random.default_rng(SEED)
    filas = []

    for indir in args.indirs:
        rep = json.loads((indir / "phase0_report.json").read_text())
        co = rep.get("coaches") or {}
        club = co.get("club")
        trans = _read_trans(str(indir))
        if "match_date" not in trans.columns:
            raise SystemExit(f"{indir} no trae `match_date`.")
        trans = trans.with_columns(torneo_cols())

        # N1: la referencia es la liga SIN el club focal.
        ref = pos_liga.filter(pl.col("team") != club)

        for c in co.get("coverage", []):
            if not c.get("suficiente"):
                continue
            dt = c["coach"]
            foco = trans.filter(pl.col("coach") == dt)
            if foco.height == 0:
                continue
            pf = largo_posesiones(foco)
            mezcla = {r["torneo"]: r["n"] for r in
                      pf.group_by("torneo").agg(pl.len().alias("n")).to_dicts()}

            t_foco = float(pf["acciones"].mean())
            t_ref = media_ponderada_por_mezcla(ref, mezcla)
            R = t_foco / t_ref

            # N2a: IC bootstrap por poss_uid (la unidad de remuestreo).
            v = pf["acciones"].to_numpy()
            idx = rng.integers(0, v.size, size=(args.n_boot, v.size))
            boot = v[idx].mean(axis=1) / t_ref
            lo, hi = np.quantile(boot, [0.025, 0.975])
            # bootstrap basico (percentil invertido), como el resto del proyecto
            ic = (2 * R - hi, 2 * R - lo)

            filas.append({
                "club": club, "coach": dt,
                "n_posesiones": int(v.size),
                "acc_por_posesion_cruda": t_foco,
                "acc_por_posesion_liga_contemporanea": t_ref,
                "R": R,
                "R_ic95": [float(ic[0]), float(ic[1])],
                "R_excluye_1": bool(ic[0] > 1.0 or ic[1] < 1.0),
                # N4: la tabla que necesita la correccion a nivel matricial
                "torneos_del_foco": mezcla,
            })
            print(f"  {club:<14}{dt:<22} T={t_foco:5.2f}  "
                  f"liga={t_ref:5.2f}  R={R:6.3f}  "
                  f"IC[{ic[0]:.3f}, {ic[1]:.3f}]"
                  f"{'  *' if filas[-1]['R_excluye_1'] else ''}")

    # N2b: nula empirica. La dispersion de R sobre TODAS las unidades
    # (club, torneo) de la liga. Un R de 1.06 no significa nada hasta saber
    # que R produce la liga por si sola.
    nula = []
    for (equipo, torneo), sub in pos_liga.group_by(["team", "torneo"]):
        otros = pos_liga.filter(
            (pl.col("team") != equipo) & (pl.col("torneo") == torneo)
        )
        if sub.height < 50 or otros.height < 50:
            continue
        nula.append(float(sub["acciones"].mean() / otros["acciones"].mean()))
    nula = np.asarray(nula)
    q = np.quantile(nula, [0.025, 0.5, 0.975]) if nula.size else [np.nan] * 3
    print(f"\nnula de R sobre {nula.size} unidades (club x torneo): "
          f"mediana {q[1]:.3f}, 95% central [{q[0]:.3f}, {q[2]:.3f}]")

    for f in filas:
        f["percentil_en_nula"] = (
            float((nula < f["R"]).mean()) if nula.size else None
        )
        f["fuera_del_95_de_la_nula"] = (
            bool(f["R"] < q[0] or f["R"] > q[2]) if nula.size else None
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "reglas_preinscritas": {
            "N1": "la referencia excluye al club focal",
            "N2": "IC bootstrap por poss_uid + nula empirica de R (ADR-30)",
            "N3": "el estimando cambia: 'X% mas que sus contemporaneos'",
            "N4": "esto corrige un ESCALAR, no las matrices; ver la seccion "
                  "N4 de la cabecera del script",
        },
        "unidades": filas,
        "nula": {"n": int(nula.size),
                 "q025": float(q[0]), "mediana": float(q[1]),
                 "q975": float(q[2])},
        "n_boot": args.n_boot, "seed": SEED,
    }, indent=2, ensure_ascii=False))
    print(f"\nescrito {args.out}")
    print("\nLECTURA: `R_excluye_1` dice que el foco difiere de sus "
          "contemporaneos.\n`fuera_del_95_de_la_nula` dice que difiere MAS de "
          "lo que la liga difiere de si misma.\nLos dos tienen que darse para "
          "reportar el efecto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
