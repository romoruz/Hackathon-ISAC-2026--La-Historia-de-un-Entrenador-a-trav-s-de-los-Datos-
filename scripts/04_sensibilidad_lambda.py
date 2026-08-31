#!/usr/bin/env python3
"""
04_sensibilidad_lambda.py — La huella tactica, a traves de la rejilla de lambda.

LA PREGUNTA QUE CONTESTA
------------------------
No es "cual es lambda*", sino: "CAMBIAN MIS CONCLUSIONES SI LAMBDA CAMBIA?".
Es el analisis obligatorio de 05_VALIDATION.md §3 y la decision pendiente P-04
de 06_DECISIONS.md.

Una tabla de sensibilidad convence mas a un jurado tecnico que un resultado
puntual, porque demuestra que se busco activamente romper el propio resultado.

DOS COSAS DISTINTAS QUE SE MIDEN AQUI
-------------------------------------
A. ESTADOS RECHAZADOS (huella tactica, G2 + FDR).
   OJO: en inference.tactical_fingerprint, G2 se calcula sobre CONTEOS CRUDOS
   contra league_P. lambda entra SOLO a traves de league_P (la referencia).
   Asi que la sensibilidad aqui mide cuanto depende la huella del suavizado de
   la REFERENCIA, no del foco. Es una dependencia real pero indirecta.

B. TAMANO DE EFECTO (diferencia celda a celda).
   Aqui lambda si entra directo. Con algebra:

       p*_foco - p_base = [n/(n+lam)] * (p^MLE_foco - p_base)

   es decir, la diferencia reportada es la real ATENUADA por n_i/(n_i+lam),
   factor que varia POR RENGLON. Con lam=500 y mediana de renglon 170
   (caso Ortiz) el factor es 0.25: se reporta un cuarto del efecto real.
   Esto NO es un bug -- es el encogimiento haciendo su trabajo -- pero hay que
   declararlo, porque invalida leer `diff` como magnitud.

CRITERIO DE EXITO
-----------------
El conjunto de estados rechazados es estable (Jaccard alto entre lambdas).
Si es estable: argumento fuerte, el hallazgo no depende del hiperparametro.
Si cambia: hay que decirlo explicitamente en el reporte.

Uso:
  python scripts/04_sensibilidad_lambda.py --unit coach --value "Andre Jardine" \\
      --baseline other_coaches --club "América"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.config import Config
    from dtdecoder.eras import select_units
    from dtdecoder.estimate import count_matrix, shrink
    from dtdecoder.grid import StateSpace
    from dtdecoder.inference import bootstrap_diff, tactical_fingerprint
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12
LAMBDAS = [0.0, 50.0, 500.0, 2000.0]


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def _prior_excluye_foco(trans: pl.DataFrame, unit: str, value: str,
                        space: StateSpace) -> np.ndarray:
    """Prior externo al foco (ADR-06). Sin esto, lambda pierde su lectura."""
    fuera = trans.filter((pl.col(unit) != value) | pl.col(unit).is_null())
    C = count_matrix(fuera, space)
    n = C.sum(axis=1, keepdims=True)
    P = np.where(n > 0, C / np.maximum(n, _EPS), 1.0 / space.n_states)
    return P / np.maximum(P.sum(axis=1, keepdims=True), _EPS)


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(len(a | b), 1)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--unit", default="coach")
    ap.add_argument("--value", required=True)
    ap.add_argument("--baseline", default="other_coaches",
                    choices=["rest", "other_coaches", "opponents"])
    ap.add_argument("--club", default=None)
    ap.add_argument("--lambdas", type=float, nargs="+", default=LAMBDAS)
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--out", default="reports/sensibilidad_lambda.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)
    inf = cfg["inference"]

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)

    focus, base = select_units(trans, args.unit, args.value, args.baseline, args.club)
    prior = _prior_excluye_foco(trans, args.unit, args.value, space)
    C_base = count_matrix(base, space)
    labels = space.transient_labels()

    print(f"foco = {args.unit}={args.value} | baseline = {args.baseline}")
    print(f"posesiones foco = {focus['poss_uid'].n_unique()}  "
          f"base = {base['poss_uid'].n_unique()}\n")

    filas, rechazados, atenuacion = [], {}, {}
    for lam in args.lambdas:
        league_P = shrink(C_base, prior, lam)

        fp = tactical_fingerprint(
            focus, base, space, league_P,
            n_boot=args.n_boot, seed=int(inf["boot_seed"]),
            min_row_count=int(inf["min_row_count"]), alpha=float(inf["fdr_alpha"]),
        )
        rej = {labels[i] for i in np.flatnonzero(fp.rejected)}
        rechazados[lam] = rej

        ci = bootstrap_diff(focus, base, space, prior, lam,
                            n_boot=args.n_boot, seed=int(inf["boot_seed"]))
        n_i = count_matrix(focus, space).sum(axis=1)
        factor = n_i / np.maximum(n_i + lam, _EPS)

        atenuacion[lam] = {
            "factor_mediano": float(np.median(factor)),
            "factor_min": float(factor.min()),
            "factor_max": float(factor.max()),
        }
        filas.append({
            "lambda": lam,
            "n_rechazados": int(fp.rejected.sum()),
            "n_testeados": int(fp.tested.sum()),
            "G2_max": float(fp.g2_obs.max()),
            "celdas_IC_sin_cero": int(ci.excludes_zero.sum()),
            "max_abs_diff": float(np.abs(ci.diff).max()),
            "atenuacion_mediana": round(float(np.median(factor)), 4),
        })
        print(f"  lambda={lam:>7g}  rechazos={fp.rejected.sum():>3}  "
              f"celdas={int(ci.excludes_zero.sum()):>4}  "
              f"atenuacion={np.median(factor):.3f}")

    # Estabilidad del conjunto de rechazos
    lams = list(args.lambdas)
    jac = {}
    for a in range(len(lams)):
        for b in range(a + 1, len(lams)):
            jac[f"{lams[a]:g} vs {lams[b]:g}"] = round(
                jaccard(rechazados[lams[a]], rechazados[lams[b]]), 4)

    nucleo = set.intersection(*rechazados.values()) if rechazados else set()
    union = set.union(*rechazados.values()) if rechazados else set()

    res = {
        "unidad": f"{args.unit}={args.value}",
        "baseline": args.baseline,
        "por_lambda": filas,
        "jaccard": jac,
        "estados_en_TODOS_los_lambda": sorted(nucleo),
        "estados_en_ALGUN_lambda": sorted(union),
        "estabilidad": round(len(nucleo) / max(len(union), 1), 4),
        "atenuacion_por_lambda": atenuacion,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))

    print(f"\nescrito: {out}")
    print("\n== Estabilidad del conjunto de rechazos (Jaccard) ==")
    for k, v in jac.items():
        print(f"  lambda {k:<18} {v:.3f}")
    print(f"\n  nucleo (rechazado con TODOS los lambda): {len(nucleo)} estados")
    print(f"  union  (rechazado con ALGUNO)          : {len(union)} estados")
    print(f"  estabilidad = nucleo/union             : {res['estabilidad']:.3f}")

    print("\nLECTURA")
    print("  estabilidad > 0.8  -> las conclusiones NO dependen de lambda.")
    print("                        Reporta el nucleo; es tu hallazgo solido.")
    print("  estabilidad < 0.5  -> dependen del hiperparametro. Hay que decirlo")
    print("                        y reportar el nucleo como lo unico defendible.")
    print("\n  ATENUACION: el `diff` reportado es el efecto real multiplicado por")
    print("  ese factor. Con atenuacion 0.25, estas mostrando un cuarto del")
    print("  efecto. Los tamanos de efecto SOLO son interpretables con lambda=0.")
    print("  Sugerencia para el reporte: significancia con lambda*, magnitudes")
    print("  con lambda=0, y decirlo explicitamente.")


if __name__ == "__main__":
    main()
