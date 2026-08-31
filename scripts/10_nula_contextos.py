#!/usr/bin/env python3
"""
10_nula_contextos.py — ¿El 0.04 del contraste de contextos significa algo?

EL PROBLEMA
-----------
`context_contrast` reporta la distancia de variacion total entre las matrices
de transicion condicionadas al marcador:

    drawing vs losing   0.0405
    drawing vs winning  0.0398
    losing  vs winning  0.0444

y de ahi se queria concluir que el marcador apenas mueve el estilo: filosofia,
no reactividad. Es el hallazgo mas vendible del proyecto y responde a la
amenaza 4.2 de 05_VALIDATION.

Pero **no tiene escala**. TV >= 0 siempre, y estratificar en tres partes ya
produce TV positiva aunque las tres provengan de la MISMA distribucion, solo
por ruido de muestreo. Sin nula, 0.04 no dice nada.

Es el tercer caso del mismo error en este proyecto:
  - `detect_regime_changes` reportaba 0.22 sin nula. Al calibrarla, resulto que
    el quiebre era de calendario, no de entrenador.
  - La huella tactica ordenaba por TV cruda. Al calibrarla, el 52-63% de la TV
    tipica resulto ser tamano de muestra.

EL METODO
---------
Prueba de permutacion. Bajo la nula "la matriz de transicion NO depende del
marcador", las etiquetas de contexto son intercambiables entre posesiones. Se
barajan y se recalcula la TV. La distribucion resultante es la de "no hay
adaptacion al marcador".

LA PERMUTACION ES POR POSESION, NO POR TRANSICION
--------------------------------------------------
`score_state` es efectivamente una etiqueta de posesion: se calcula por evento
con `shift(1)` sobre el marcador acumulado, asi que es constante dentro de una
posesion salvo que caiga un gol a mitad. Permutar a nivel de TRANSICION romperia
esa estructura y produciria una nula artificialmente estrecha: se rechazaria
siempre.

NO SE PUEDE AFIRMAR LA NULA
---------------------------
Si el observado cae dentro de la nula, la conclusion NO es "el DT no se adapta
al marcador". Es "no detectamos adaptacion por encima de X", donde X es el p95
de la nula: el EFECTO MINIMO DETECTABLE.

Ya pasó en este proyecto: en el placebo de `02_placebo_regimes.py`, Solari,
Ortiz y Herrera "aprobaron" y resulto ser falta de potencia (17-39 partidos),
no homogeneidad. El script reporta el efecto minimo detectable justamente para
que la frase del reporte sea la correcta.

Uso:
  python scripts/10_nula_contextos.py --unit coach --value "Andre Jardine"
  python scripts/10_nula_contextos.py --unit coach --value "Martin Anselmi" \\
      --indir data/processed_cruzazul
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.config import Config
    from dtdecoder.estimate import count_matrix, shrink
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

try:
    from dtdecoder.cli import _provenance
except ImportError:                       # instalacion previa al parche ADR-23
    def _provenance(_p=None):             # type: ignore[misc]
        return {"aviso": "cli._provenance no disponible; instala v0.4.1"}

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def tv_ponderada(Ca: np.ndarray, Cb: np.ndarray, prior: np.ndarray,
                 lam: float) -> tuple[float, float]:
    """Misma receta que `inference.context_contrast`: TV por renglon ponderada
    por la masa combinada. Si se cambia alla, cambiar aqui (dos rutas para lo
    mismo ya causo el bug #2 de este proyecto)."""
    Pa, Pb = shrink(Ca, prior, lam), shrink(Cb, prior, lam)
    w = Ca.sum(axis=1) + Cb.sum(axis=1)
    w = w / max(w.sum(), _EPS)
    tv = 0.5 * np.abs(Pa - Pb).sum(axis=1)
    return float((tv * w).sum()), float(tv.max())


def etiquetas_por_posesion(trans: pl.DataFrame) -> pl.DataFrame:
    """Una etiqueta de contexto por posesion (la primera del bloque)."""
    return (
        trans.sort(["poss_uid"] + (["event_index"] if "event_index" in trans.columns else []))
        .group_by("poss_uid", maintain_order=True)
        .agg(pl.col("score_state").first())
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--unit", default="coach")
    ap.add_argument("--value", required=True)
    ap.add_argument("--by", default="score_state")
    ap.add_argument("--lam", type=float, default=0.0,
                    help="0 por defecto: las MAGNITUDES van con lambda=0 (ADR-22)")
    ap.add_argument("--n-perm", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--out", default="reports/nula_contextos.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)
    if args.unit not in trans.columns:
        sys.exit(f"No existe la columna '{args.unit}'")
    sub = trans.filter(pl.col(args.unit) == args.value)
    if sub.height == 0:
        disp = trans[args.unit].drop_nulls().unique().to_list()
        sys.exit(f"Sin transiciones para '{args.value}'. Disponibles: {disp}")
    if args.by != "score_state":
        sub = sub.with_columns(pl.col(args.by).alias("score_state"))

    # Prior externo a la unidad focal (ADR-06).
    fuera = trans.filter((pl.col(args.unit) != args.value) | pl.col(args.unit).is_null())
    Cf = count_matrix(fuera, space)
    nf = Cf.sum(axis=1, keepdims=True)
    prior = np.where(nf > 0, Cf / np.maximum(nf, _EPS), 1.0 / space.n_states)

    etiq = etiquetas_por_posesion(sub)
    niveles = sorted(etiq["score_state"].unique().to_list())
    print(f"{args.unit} = {args.value}")
    print(f"posesiones: {etiq.height}   contextos: {niveles}")
    print(etiq.group_by("score_state").len().sort("score_state"))
    print(f"\npermutando {args.n_perm} veces (por POSESION)...\n", file=sys.stderr)

    base = sub.drop("score_state").join(etiq, on="poss_uid", how="left")
    uids = etiq["poss_uid"].to_list()
    labs = np.array(etiq["score_state"].to_list())
    mapa_uid = {u: k for k, u in enumerate(uids)}
    idx_uid = np.array([mapa_uid[u] for u in base["poss_uid"].to_list()])

    pares = list(combinations(niveles, 2))
    obs = {}
    for a, b in pares:
        Ca = count_matrix(base.filter(pl.col("score_state") == a), space)
        Cb = count_matrix(base.filter(pl.col("score_state") == b), space)
        obs[(a, b)] = tv_ponderada(Ca, Cb, prior, args.lam)

    rng = np.random.default_rng(args.seed)
    nulos = {par: [] for par in pares}
    for _ in range(args.n_perm):
        perm = rng.permutation(labs)
        etq = perm[idx_uid]
        for a, b in pares:
            Ca = count_matrix(base.filter(pl.Series(etq == a)), space)
            Cb = count_matrix(base.filter(pl.Series(etq == b)), space)
            nulos[(a, b)].append(tv_ponderada(Ca, Cb, prior, args.lam)[0])

    filas = []
    print(f"{'contraste':<24} {'TV obs':>8} {'nula med':>9} {'nula p95':>9} "
          f"{'z':>7} {'p':>7}  veredicto")
    print("-" * 84)
    for a, b in pares:
        tv_o, tv_max = obs[(a, b)]
        nul = np.asarray(nulos[(a, b)])
        med, p95, de = float(np.median(nul)), float(np.percentile(nul, 95)), float(nul.std())
        pv = float((1.0 + (nul >= tv_o).sum()) / (1.0 + args.n_perm))
        z = (tv_o - med) / max(de, 1e-12)
        veredicto = "ADAPTA" if pv < 0.05 else "no detectado"
        filas.append({
            "contraste": f"{a} vs {b}", "tv_obs": round(tv_o, 5),
            "tv_max_renglon": round(tv_max, 5),
            "nula_mediana": round(med, 5), "nula_p95": round(p95, 5),
            "z": round(z, 2), "p_valor": pv,
            "adapta": bool(pv < 0.05),
            "efecto_minimo_detectable": round(p95, 5),
            "exceso_sobre_ruido": round(tv_o - med, 5),
        })
        print(f"{a + ' vs ' + b:<24} {tv_o:>8.5f} {med:>9.5f} {p95:>9.5f} "
              f"{z:>7.2f} {pv:>7.4f}  {veredicto}")

    p95_max = max(f["nula_p95"] for f in filas)
    res = {"unidad": f"{args.unit}={args.value}", "by": args.by, "lambda": args.lam,
           "n_perm": args.n_perm, "n_posesiones": etiq.height,
           "contrastes": filas,
           "efecto_minimo_detectable_global": round(p95_max, 5),
           "provenance": _provenance(args.config)}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")

    algun = any(f["adapta"] for f in filas)
    print("\n== COMO REDACTARLO ==")
    if algun:
        print("  Al menos un contraste supera el ruido: HAY adaptacion al")
        print("  marcador detectable. La afirmacion 'filosofia, no reactividad'")
        print("  NO se sostiene tal cual; hay que cuantificar en que contexto.")
    else:
        print("  Ningun contraste supera el ruido. La frase correcta es:")
        print(f"    'No detectamos adaptacion al marcador mayor a una TV de")
        print(f"     {p95_max:.4f} con {etiq.height} posesiones.'")
        print("  NO decir 'el DT no se adapta al marcador': no rechazar la nula")
        print("  no es probarla. Ya paso con el placebo de regimes, donde tres")
        print("  eras 'aprobaron' por falta de potencia, no por homogeneidad.")
    print("\n  El efecto minimo detectable es la cifra honesta de potencia y")
    print("  debe ir junto al resultado, no en una nota al pie.")


if __name__ == "__main__":
    main()
