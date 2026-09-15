#!/usr/bin/env python3
"""
21_barrido_malla.py — error del estimador ENCOGIDO por malla. SENSIBILIDAD.

REGLA PREINSCRITA (2026-09-14, antes de correr esto)
====================================================

**La malla queda fijada en 5x4 a priori.** El argumento es muestral y estaba
escrito antes de medir nada: la potencia de tau^2 la manda el NUMERO de
unidades, y 6x4 cuesta 20 (68 -> 48 eras analizables).

Este barrido **no decide nada**. Responde la pregunta que
`12_API_STATSBOMB.md` §5.3 dejo abierta --`params_per_obs` mide el
sobreajuste del EMV crudo mientras el proyecto usa el encogido-- y se reporta
como sensibilidad y, si procede, como recomendacion para trabajo futuro.

POR QUE LA REGLA ES ASI Y NO CONDICIONAL
----------------------------------------
La primera version de esta regla decia "6x4 si el error baja, salvo que las
unidades perdidas incluyan a las de los titulares". Eso es seleccion: una
regla cuyo brazo de escape esta definido por QUIEN cae equivale a elegir
despues de ver los datos. Tampoco vale preinscribir "6x4 si quedan >= N
unidades", porque los conteos (68 y 48) ya estaban en la bitacora y cualquier
N elegido ahora esta contaminado por conocerlos.

LA TRAMPA DE MEDICION QUE ESTE SCRIPT EVITA
-------------------------------------------
La log-verosimilitud fuera de muestra **no es comparable entre mallas**. Cada
malla define un espacio de estados distinto, asi que las densidades viven
sobre sigma-algebras distintas: una malla mas gruesa tiene menos estados y su
loglik por transicion sube sin que el modelo sea mejor. Comparar mallas por
loglik es un error de tipo, no una aproximacion.

Lo que si es comparable es un error en **escala de probabilidad**: cuanto se
mueve la matriz encogida al submuestrear, medido como norma infinito por
renglon y ponderado por masa de visitas. Es exactamente `estimate.error_curve`,
que ya existe y ya se usa para justificar la eleccion de nx, ny.

Uso:

    python scripts/21_barrido_malla.py \
        --src data/api/eventos_api_america \
        --club "América" \
        --eras data/eras_compat/coach_eras_america.csv \
        --match-dates data/api/match_dates_america.csv \
        --exclusiones data/eras_api/absorbidos.csv \
        --mallas 4x3 5x4 6x4 6x5 \
        --out reports/barrido_malla.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from dtdecoder import eras as eras_mod
from dtdecoder import ingest
from dtdecoder.config import Config
from dtdecoder.estimate import (
    count_matrix,
    cv_lambda,
    error_curve,
    shrink,
    sparsity_report,
)
from dtdecoder.grid import StateSpace
from dtdecoder.possessions import build_transitions

FRACCION_REFERENCIA = 0.5   # el punto de la curva que se tabula


def parse_malla(s: str) -> tuple[int, int]:
    nx, ny = s.lower().split("x")
    return int(nx), int(ny)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--club", required=True)
    ap.add_argument("--eras", required=True)
    ap.add_argument("--match-dates", required=True, dest="match_dates")
    ap.add_argument("--exclusiones", default=None)
    ap.add_argument("--mallas", nargs="+", default=["4x3", "5x4", "6x4", "6x5"])
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", type=Path, default=Path("reports/barrido_malla.json"))
    args = ap.parse_args()

    cfg = Config.load(args.config)
    pitch = cfg["pitch"]
    fases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    ecfg = cfg["estimation"]

    eras = eras_mod.load_eras(args.eras)
    md = eras_mod.load_match_dates(args.match_dates)
    excl = (eras_mod.load_exclusions(args.exclusiones, args.club)
            if args.exclusiones else [])

    resultados = []
    for etiqueta in args.mallas:
        nx, ny = parse_malla(etiqueta)
        space = StateSpace(nx=nx, ny=ny, length=pitch["length"],
                           width=pitch["width"], phases=fases)

        # Las transiciones se reconstruyen DESDE LOS EVENTOS por cada malla:
        # `from_state`/`to_state` son enteros calculados con la formula del
        # espacio de estados, asi que un parquet de 5x4 no se puede reinterpretar
        # en 6x4. Reusarlo daria numeros plausibles y equivocados.
        lf = ingest.load(args.src)
        if excl:
            lf = lf.filter(~pl.col("match_id").cast(pl.Int64).is_in(excl))
        trans = build_transitions(lf, space, cfg.raw, team=None, club=args.club)
        mc = eras_mod.match_coach_table(md, eras, args.club)
        trans = eras_mod.attach_coach(trans, mc, args.club)

        for dt in (trans.filter(pl.col("team") == args.club)["coach"]
                   .drop_nulls().unique().sort().to_list()):
            foco = trans.filter(pl.col("coach") == dt)
            C = count_matrix(foco, space)
            if C.sum() == 0:
                continue
            sin_foco = trans.filter(
                (pl.col("coach") != dt) | pl.col("coach").is_null()
            )
            Cq = count_matrix(sin_foco, space)
            nq = Cq.sum(axis=1, keepdims=True)
            q = np.where(nq > 0, Cq / np.maximum(nq, 1e-12),
                         1.0 / Cq.shape[1])

            cv = cv_lambda(foco, space, q, ecfg["lambda_grid"],
                           k=ecfg["cv_folds"], seed=ecfg["cv_seed"])
            curva = error_curve(foco, space, q, cv.lam_star,
                                seed=ecfg["cv_seed"])
            ref = curva.filter(
                (pl.col("fraction") - FRACCION_REFERENCIA).abs() < 1e-9
            )
            if ref.height == 0:
                ref = curva.filter(pl.col("fraction") == curva["fraction"].min())
            sp = sparsity_report(C)

            # error del EMV crudo contra el ENCOGIDO, sobre la misma malla:
            # es la comparacion que el criterio viejo no hacia.
            P_emv = shrink(C, q, 0.0)
            P_enc = shrink(C, q, cv.lam_star)
            w = C.sum(axis=1)
            w = w / max(w.sum(), 1e-12)
            desplazamiento = float(
                (np.abs(P_enc - P_emv).max(axis=1) * w).sum()
            )

            resultados.append({
                "malla": etiqueta, "nx": nx, "ny": ny,
                "n_estados": space.n_states,
                "coach": dt,
                "n_transiciones": int(C.sum()),
                "lambda_star": float(cv.lam_star),
                # criterio VIEJO, el del EMV crudo
                "frac_below_min": sp["frac_below_min"],
                "params_per_obs": sp["params_per_obs"],
                # criterio NUEVO, sobre el estimador encogido
                "err_encogido_frac50": float(ref["err_weighted"][0]),
                "err_mediano_frac50": float(ref["err_median"][0]),
                "desplazamiento_por_encogimiento": desplazamiento,
            })
            print(f"  {etiqueta}  {dt:24s} n={int(C.sum()):>7,}  "
                  f"lam*={cv.lam_star:<7g} ppo={sp['params_per_obs']:.3f}  "
                  f"fbm={sp['frac_below_min']:.3f}  "
                  f"err50={float(ref['err_weighted'][0]):.5f}")
        del trans

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "regla_preinscrita": (
            "La malla queda fijada en 5x4 a priori por el argumento muestral "
            "(la potencia de tau^2 la manda el numero de unidades). Este "
            "barrido se reporta como SENSIBILIDAD y no decide la malla."
        ),
        "nota_metodologica": (
            "La loglik fuera de muestra NO es comparable entre mallas: cada "
            "malla define un espacio de estados distinto. Se compara error en "
            "escala de probabilidad (norma infinito por renglon, ponderada por "
            "masa de visitas), que si lo es."
        ),
        "fraccion_referencia": FRACCION_REFERENCIA,
        "club": args.club,
        "exclusiones_aplicadas": excl,
        "resultados": resultados,
    }, indent=2, ensure_ascii=False))
    print(f"\nescrito {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
