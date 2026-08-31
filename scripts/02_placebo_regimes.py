#!/usr/bin/env python3
"""
02_placebo_regimes.py — Nula por permutacion para `detect_regime_changes`.

EL PROBLEMA QUE RESUELVE
------------------------
`dtdecoder regimes` devuelve una serie de `tv_weighted` por punto de corte, pero
sin escala de referencia. Un valor de 0.22 no dice nada: puede ser una frontera
de era real o puede ser lo que da CUALQUIER corte por puro ruido de muestreo.

Este script construye la nula: permuta el orden de los partidos DENTRO de una
era (donde por definicion NO deberia haber quiebre) y recalcula el mismo
estadistico. La distribucion resultante es la de "no hay cambio de regimen".

Es la prueba placebo de 05_VALIDATION.md §4.5, y da tres cosas:
  1. Un p-valor para el maximo observado dentro de cada era.
  2. Un umbral (percentil 95 de la nula) para graficar sobre la serie real.
  3. Evidencia de si las fronteras documentales superan ese umbral.

Uso:
  python scripts/02_placebo_regimes.py --club "América" --window 8 --n-perm 500
  python scripts/02_placebo_regimes.py --club "América" --era "Andre Jardine"
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
    from dtdecoder.estimate import count_matrix
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado (pip install -e .)")

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def _row_normalize(C: np.ndarray) -> np.ndarray:
    s = C.sum(axis=1, keepdims=True)
    return np.where(s > 0, C / np.maximum(s, _EPS), 1.0 / C.shape[1])


def _tv_series(sub: pl.DataFrame, space, orden: list[int], window: int) -> np.ndarray:
    """Misma receta que eras.detect_regime_changes, sobre un orden dado.

    Se reimplementa aqui en vez de llamar a la funcion original porque esta
    necesita recibir el ORDEN como argumento para poder permutarlo. Si cambias
    la formula alla, cambiala aqui: son dos rutas para lo mismo y eso ya causo
    un bug en este proyecto (07_AI_HANDOFF §5).
    """
    # Precomputar conteos por partido: evita re-filtrar en cada permutacion.
    por_partido: dict[int, np.ndarray] = {}
    for key, grp in sub.group_by(["match_id"], maintain_order=True):
        por_partido[int(key[0])] = count_matrix(grp, space)

    out = []
    for k in range(window, len(orden) - window + 1):
        Cl = sum(por_partido[m] for m in orden[k - window:k])
        Cr = sum(por_partido[m] for m in orden[k:k + window])
        Pl_, Pr_ = _row_normalize(Cl), _row_normalize(Cr)
        w = Cl.sum(axis=1) + Cr.sum(axis=1)
        w = w / max(w.sum(), _EPS)
        tv = 0.5 * np.abs(Pl_ - Pr_).sum(axis=1)
        out.append(float((tv * w).sum()))
    return np.asarray(out)


def _orden_real(sub: pl.DataFrame) -> list[int]:
    col = "match_date" if "match_date" in sub.columns else "match_id"
    return (
        sub.group_by("match_id").agg(pl.col(col).first()).sort(col)["match_id"]
        .cast(pl.Int64).to_list()
    )


def placebo_una_era(
    sub: pl.DataFrame, space, window: int, n_perm: int, seed: int
) -> dict:
    orden = _orden_real(sub)
    if len(orden) < 2 * window + 1:
        return {"n_partidos": len(orden), "error": "muestra insuficiente para la ventana"}

    obs = _tv_series(sub, space, orden, window)
    rng = np.random.default_rng(seed)

    nulos = np.empty(n_perm)
    for b in range(n_perm):
        perm = list(rng.permutation(orden))
        nulos[b] = _tv_series(sub, space, perm, window).max()

    obs_max = float(obs.max())
    p = float((nulos >= obs_max).mean())
    return {
        "n_partidos": len(orden),
        "max_observado": obs_max,
        "nula_media": float(nulos.mean()),
        "nula_p95": float(np.percentile(nulos, 95)),
        "nula_max": float(nulos.max()),
        "p_valor": p,
        "hay_quiebre_interno": bool(p < 0.05),
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--club", required=True)
    ap.add_argument("--era", default=None, help="una sola era; default: todas")
    ap.add_argument("--window", type=int, default=8)
    ap.add_argument("--n-perm", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20260819)
    ap.add_argument("--out", default="reports/placebo_regimes.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)

    club = trans.filter(pl.col("team") == args.club)
    if "coach" not in club.columns or club["coach"].null_count() == club.height:
        sys.exit("Las transiciones no traen `coach`. Corre phase0 con --eras y --match-dates.")

    eras = [args.era] if args.era else (
        club["coach"].drop_nulls().unique().sort().to_list())

    res = {}
    for e in eras:
        sub = club.filter(pl.col("coach") == e)
        print(f"[{e}] permutando...", file=sys.stderr)
        res[e] = placebo_una_era(sub, space, args.window, args.n_perm, args.seed)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))

    print(f"\nescrito: {out}\n")
    print(f"{'era':<20} {'n':>4} {'max obs':>9} {'nula p95':>9} {'p':>7}  veredicto")
    print("-" * 68)
    for e, r in res.items():
        if "error" in r:
            print(f"{e:<20} {r['n_partidos']:>4}   {r['error']}")
            continue
        v = "QUIEBRE INTERNO" if r["hay_quiebre_interno"] else "era homogenea (ok)"
        print(f"{e:<20} {r['n_partidos']:>4} {r['max_observado']:>9.4f} "
              f"{r['nula_p95']:>9.4f} {r['p_valor']:>7.3f}  {v}")

    print("\nLECTURA:")
    print("  'era homogenea' es el resultado ESPERADO: dentro de una era no")
    print("  deberia haber quiebre. Es una prueba placebo, aprobar es no rechazar.")
    print("  Un QUIEBRE INTERNO significa: la era esta mal delimitada, el DT")
    print("  cambio de idea, o el detector capta ruido de calendario.")
    print("\n  El p95 de la nula es el umbral contra el que hay que juzgar los")
    print("  valores de `dtdecoder regimes`. Si las fronteras documentales no lo")
    print("  superan, ese cruce NO es evidencia y no debe presentarse como tal.")


if __name__ == "__main__":
    main()
