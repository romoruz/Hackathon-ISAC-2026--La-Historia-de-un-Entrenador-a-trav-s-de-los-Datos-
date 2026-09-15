#!/usr/bin/env python3
"""
20_comparar_lambda.py — lambda* con prior de club contra prior de liga.

REGLAS PREINSCRITAS (escritas el 2026-09-14, ANTES de correr esto)
==================================================================

P1. PREDICCION SOBRE lambda*.  La fuga de prior (ADR-06) infla lambda* por
    construccion: con prior de club, Jardine es el 53% de las transiciones
    hacia las que se encoge a Jardine, asi que el prior parece mas creible de
    lo que es. Con prior de liga cualquier tecnico es ~4% del suyo (medido:
    74,708 de 1,883,137).
    **Se predice que lambda* BAJA.** Si sube, es un hallazgo y hay que
    explicarlo, no ajustarlo.

P2. CRITERIO DE MESETA, fijado de antemano.  La curva de CV se declara plana
    --y por tanto lambda NO identificado, ADR-22-- si el rango de la
    log-verosimilitud fuera de muestra entre lambda=100 y lambda=2000 es menor
    que 0.01 nats por transicion. Es el mismo criterio con el que se midio la
    meseta original (0.006 nats). Las dos salidas son publicables:
      - sigue plana  -> ADR-22 se sostiene con un prior nuevo y mejor;
      - deja de serlo -> lambda queda identificado y ADR-22 se puede revisar.

P3. SESGO DIFERENCIAL DE ATENUACION.  Por algebra sobre el estimador de la
    diferencia,
        p*_i - p_base = n_i / (n_i + lambda) * (p^MLE_i - p_base),
    asi que la atenuacion depende de n_i y NO se arregla usando un lambda
    comun: con lambda=500, Jardine (74,708 transiciones) queda en 0.993 y
    Solari (14,650) en 0.971. El sentido del sesgo es siempre el mismo: **la
    era chica se parece al prior mas de lo que sus datos dicen**, que es
    justo la direccion que inventa diferencias entre eras grandes y chicas.
    Este script CUANTIFICA la atenuacion por unidad. La mitigacion vive en
    H4 y esta preinscrita en 23_pares_h4.py.

P4. Nada de lo que salga aqui cambia el criterio. Si la prediccion P1 falla,
    se reporta que fallo.

Uso (agnostico de club: el club y los DT salen de phase0_report.json):

    python scripts/20_comparar_lambda.py \
        --indirs data/processed_api_america \
        --prior-from data/prior_liga \
        --out reports/lambda_prior.json

    # mas adelante, con los 18:
    python scripts/20_comparar_lambda.py \
        --indirs data/processed_api_* --prior-from data/prior_liga
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

from dtdecoder.cli import _build_prior, _read_trans
from dtdecoder.config import Config
from dtdecoder.estimate import count_matrix, cv_lambda
from dtdecoder.grid import StateSpace

MESETA_LO, MESETA_HI = 100.0, 2000.0
MESETA_NATS = 0.01


def espacio(cfg) -> StateSpace:
    p = cfg["pitch"]
    fases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"],
                      width=p["width"], phases=fases)


def meseta(grid: np.ndarray, scores: np.ndarray) -> dict:
    """Criterio P2, aplicado tal cual quedo escrito arriba."""
    m = (grid >= MESETA_LO) & (grid <= MESETA_HI)
    if m.sum() < 2:
        return {"evaluable": False}
    rango = float(scores[m].max() - scores[m].min())
    return {
        "evaluable": True,
        "rango_nats": rango,
        "umbral": MESETA_NATS,
        "es_meseta": rango < MESETA_NATS,
        "lambda_lo": MESETA_LO,
        "lambda_hi": MESETA_HI,
    }


def atenuacion(C: np.ndarray, lam: float) -> dict:
    """Factor n_i/(n_i+lambda) por renglon. Regla P3."""
    n = C.sum(axis=1)
    con_datos = n > 0
    if not con_datos.any() or lam <= 0:
        return {"lambda": float(lam), "media_ponderada": 1.0,
                "min": 1.0, "max": 1.0}
    f = n[con_datos] / (n[con_datos] + lam)
    w = n[con_datos] / n[con_datos].sum()
    return {
        "lambda": float(lam),
        "media_ponderada": float((f * w).sum()),
        "min": float(f.min()),
        "max": float(f.max()),
        "n_total": float(n.sum()),
    }


def unidades_de(indir: Path) -> tuple[str | None, list[str]]:
    """Club y entrenadores, leidos del reporte de phase0. Nada hardcodeado."""
    p = indir / "phase0_report.json"
    if not p.exists():
        raise SystemExit(f"No existe {p}. Corre phase0 sobre {indir} primero.")
    rep = json.loads(p.read_text())
    co = rep.get("coaches") or {}
    if not co.get("attached"):
        raise SystemExit(
            f"{indir} se genero SIN --eras: no tiene columna `coach` y no hay "
            "unidades que comparar."
        )
    club = co.get("club")
    dts = [c["coach"] for c in co.get("coverage", []) if c.get("suficiente")]
    return club, dts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indirs", nargs="+", required=True, type=Path,
                    help="directorios de phase0, uno por club")
    ap.add_argument("--prior-from", required=True, type=Path, dest="prior_from")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", type=Path, default=Path("reports/lambda_prior.json"))
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = espacio(cfg)
    ecfg = cfg["estimation"]
    rejilla = ecfg["lambda_grid"]

    print(f"leyendo prior de liga: {args.prior_from}")
    liga = _read_trans(str(args.prior_from), permitir_prior=True)
    print(f"  {liga.height:,} transiciones, "
          f"{liga['coach'].drop_nulls().n_unique()} entrenadores\n")

    filas = []
    for indir in args.indirs:
        club, dts = unidades_de(indir)
        trans = _read_trans(str(indir))
        print(f"== {club}  ({indir}) — {len(dts)} unidades ==")

        for dt in dts:
            foco = trans.filter(pl.col("coach") == dt)
            if foco.height == 0:
                print(f"  [salto] {dt}: sin transiciones")
                continue
            C = count_matrix(foco, space)

            # --- prior de CLUB: todo el archivo del club menos el foco
            sin_foco_club = trans.filter(
                (pl.col("coach") != dt) | pl.col("coach").is_null()
            )
            q_club = _build_prior(trans, space, "exclude_focus", sin_foco_club)

            # --- prior de LIGA: la liga menos el foco, por (coach, team).
            # Excluir solo por nombre borraria las eras del mismo tecnico en
            # OTRO club, que son datos legitimos: hay ocho carreras multiples
            # en la ventana.
            cond = (pl.col("coach") == dt)
            if club:
                cond = cond & (pl.col("team") == club)
            sin_foco_liga = liga.filter(~cond.fill_null(False))
            quitadas = liga.height - sin_foco_liga.height
            q_liga = _build_prior(sin_foco_liga, space, "exclude_focus",
                                  sin_foco_liga)

            fila = {"club": club, "coach": dt, "indir": str(indir),
                    "n_transiciones": int(C.sum()),
                    "n_posesiones": foco["poss_uid"].n_unique(),
                    "quitadas_del_prior_liga": int(quitadas)}
            if quitadas == 0:
                fila["aviso"] = (
                    "el foco no aparece en el prior de liga: o la etiqueta del "
                    "DT no coincide entre eras_compat y el artefacto, o el "
                    "club no esta en la liga procesada"
                )
                print(f"  [AVISO] {dt}: 0 transiciones quitadas del prior")

            for etiqueta, q in (("club", q_club), ("liga", q_liga)):
                cv = cv_lambda(foco, space, q, rejilla,
                               k=ecfg["cv_folds"], seed=ecfg["cv_seed"])
                g, s = np.asarray(cv.grid), np.asarray(cv.scores)
                fila[etiqueta] = {
                    "lambda_star": float(cv.lam_star),
                    "loglik_oos_max": float(s.max()),
                    "meseta": meseta(g, s),
                    "atenuacion": atenuacion(C, cv.lam_star),
                    "curva": dict(zip(map(str, g), map(float, s))),
                    "en_frontera": bool(
                        cv.lam_star in (float(min(rejilla)), float(max(rejilla)))
                    ),
                }

            lc, ll = fila["club"]["lambda_star"], fila["liga"]["lambda_star"]
            fila["lambda_bajo"] = bool(ll < lc)          # prediccion P1
            fila["lambda_igual"] = bool(ll == lc)
            print(f"  {dt:24s} n={int(C.sum()):>7,}  "
                  f"lambda* club={lc:>7g}  liga={ll:>7g}  "
                  f"{'BAJA' if ll < lc else ('IGUAL' if ll == lc else 'SUBE')}"
                  f"   meseta liga={fila['liga']['meseta'].get('es_meseta')}")
            filas.append(fila)
        print()

    # --- veredicto de las reglas preinscritas ---------------------------
    evaluadas = [f for f in filas if "club" in f and "liga" in f]
    bajan = sum(f["lambda_bajo"] for f in evaluadas)
    iguales = sum(f["lambda_igual"] for f in evaluadas)
    mesetas = sum(bool(f["liga"]["meseta"].get("es_meseta")) for f in evaluadas)
    veredicto = {
        "P1_prediccion": "lambda* baja con prior de liga",
        "P1_unidades": len(evaluadas),
        "P1_bajan": bajan,
        "P1_iguales": iguales,
        "P1_suben": len(evaluadas) - bajan - iguales,
        "P1_cumple": bajan > (len(evaluadas) - bajan - iguales),
        "P2_criterio": f"rango < {MESETA_NATS} nats entre "
                       f"{MESETA_LO:g} y {MESETA_HI:g}",
        "P2_unidades_con_meseta_prior_liga": mesetas,
        "P2_lambda_identificado": mesetas < len(evaluadas),
        "P3_nota": (
            "la atenuacion n_i/(n_i+lambda) difiere por unidad incluso con "
            "lambda comun; la mitigacion es de H4, no de aqui"
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"unidades": filas, "veredicto": veredicto,
         "rejilla": list(map(float, rejilla)),
         "prior_from": str(args.prior_from)},
        indent=2, ensure_ascii=False))
    print("== veredicto ==")
    print(json.dumps(veredicto, indent=2, ensure_ascii=False))
    print(f"\nescrito {args.out}")

    if any(f[k].get("en_frontera") for f in evaluadas for k in ("club", "liga")):
        print("\n[AVISO] algun lambda* cayo en un extremo de la rejilla: el "
              "optimo puede estar fuera. Amplia `estimation.lambda_grid`.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
