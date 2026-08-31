#!/usr/bin/env python3
"""
05_auto_transiciones.py — Cuanto de la cadena es "quedarse donde estaba".

LA PREGUNTA
-----------
La Fase 3 encontro que Jardine tiene MAS transiciones i -> i (misma zona,
misma fase) y MENOS perdidas que sus predecesores. Cuatro de las doce celdas
significativas son auto-transiciones, todas positivas.

Eso admite dos lecturas incompatibles:

  (a) TACTICA. Jardine circula y retiene: el equipo conserva el balon dentro
      de la zona en vez de arriesgar el avance.
  (b) ARTEFACTO DE RESOLUCION. Con zonas de 24 x 20 m, un pase de 6 m cae en
      la misma zona. `min_carry_length` filtra acarreos cortos pero NINGUN
      umbral de acarreo toca los pases. Si Jardine juega mas corto, genera
      mas i -> i sin que eso signifique "retener".

No se pueden separar mirando la salida de la Fase 3. Este script mide lo que
hace falta para separarlas.

POR QUE IMPORTA MAS ALLA DE LA INTERPRETACION
----------------------------------------------
Las auto-transiciones van a la DIAGONAL de Q. Como N = (I - Q)^-1, una
diagonal inflada infla las visitas esperadas y por tanto xT, longitud esperada
y todo lo derivado. No es solo una cuestion de narrativa: es el numero.

QUE MIRAR
---------
- `frac_auto` global. Por encima de ~0.25 la diagonal domina la dinamica.
- `frac_auto` por entrenador: si Jardine esta muy por encima, el hallazgo de
  Fase 3 es en buena medida esto.
- Desglose por `action_type`: si la mayoria son Pass, `min_carry_length` NO
  puede arreglarlo y hay que subir la resolucion.
- `E[T]` con y sin diagonal: cuanto de la longitud esperada es permanencia.

Uso:
  python scripts/05_auto_transiciones.py
  python scripts/05_auto_transiciones.py --unit coach
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
    from dtdecoder.estimate import count_matrix, mle
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def resumen(trans: pl.DataFrame, space: StateSpace) -> dict:
    n = trans.height
    auto = trans.filter(pl.col("from_state") == pl.col("to_state")).height
    absorb = trans.filter(pl.col("is_absorbing")).height
    # Entre las transiciones NO absorbentes, cuantas se quedan en su estado.
    no_abs = n - absorb
    return {
        "n_transiciones": n,
        "n_auto": auto,
        "frac_auto": round(auto / max(n, 1), 4),
        "frac_auto_entre_no_absorbentes": round(auto / max(no_abs, 1), 4),
        "frac_absorbentes": round(absorb / max(n, 1), 4),
    }


def impacto_en_N(trans: pl.DataFrame, space: StateSpace) -> dict:
    """E[T] con la cadena tal cual vs. con la diagonal de Q eliminada.

    Quitar la diagonal y renormalizar equivale a preguntar: si cada
    auto-transicion no contara como un paso, cuanto duraria la posesion?
    La diferencia es la parte de la longitud esperada que es PERMANENCIA en
    zona, no progresion.
    """
    C = count_matrix(trans, space)
    P = mle(C)
    Q = P[:, : space.n_transient]

    I = np.eye(space.n_transient)
    out = {}
    for etiqueta, Qx in (("con_diagonal", Q), ("sin_diagonal", _sin_diagonal(C, space))):
        rho = float(np.abs(np.linalg.eigvals(Qx)).max())
        if rho >= 1.0:
            out[etiqueta] = {"rho_Q": round(rho, 4), "E_T_medio": None,
                             "nota": "rho >= 1: N no existe"}
            continue
        N1 = np.linalg.solve(I - Qx, np.ones(space.n_transient))
        w = C.sum(axis=1)
        w = w / max(w.sum(), _EPS)
        out[etiqueta] = {"rho_Q": round(rho, 4),
                         "E_T_medio": round(float((N1 * w).sum()), 4)}
    a, b = out["con_diagonal"].get("E_T_medio"), out["sin_diagonal"].get("E_T_medio")
    if a and b:
        out["inflacion_por_permanencia"] = round((a - b) / b, 4)
    return out


def _sin_diagonal(C: np.ndarray, space: StateSpace) -> np.ndarray:
    """Q renormalizada tras poner los conteos i -> i en cero."""
    C2 = C.copy()
    idx = np.arange(space.n_transient)
    C2[idx, idx] = 0.0
    P2 = mle(C2)
    return P2[:, : space.n_transient]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--unit", default="coach", help="columna para desglosar")
    ap.add_argument("--out", default="reports/auto_transiciones.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)

    res: dict = {
        "malla": f"{space.nx}x{space.ny}",
        "zona_metros": f"{space.length / space.nx:.0f} x {space.width / space.ny:.0f}",
        "min_carry_length": cfg["possession"].get("min_carry_length"),
        "global": resumen(trans, space),
    }

    print(f"== Malla {res['malla']}  (zonas de {res['zona_metros']} m) ==")
    print(json.dumps(res["global"], indent=2))

    # --- por tipo de accion ----------------------------------------------
    if "action_type" in trans.columns:
        por_tipo = (
            trans.with_columns(
                (pl.col("from_state") == pl.col("to_state")).alias("es_auto"))
            .group_by("action_type")
            .agg(pl.len().alias("n"), pl.col("es_auto").sum().alias("n_auto"))
            .with_columns((pl.col("n_auto") / pl.col("n")).round(4).alias("frac_auto"))
            .sort("n_auto", descending=True)
        )
        res["por_tipo_de_accion"] = por_tipo.to_dicts()
        print("\n== Auto-transiciones por tipo de accion ==")
        print(por_tipo)

        total_auto = res["global"]["n_auto"]
        pases = por_tipo.filter(pl.col("action_type") == "Pass")
        if pases.height and total_auto:
            cuota = int(pases["n_auto"][0]) / total_auto
            res["cuota_de_pases_en_auto"] = round(cuota, 4)
            print(f"\n  Los pases aportan el {cuota:.1%} de las auto-transiciones.")
            if cuota > 0.5:
                print("  >> min_carry_length NO puede arreglar esto: no toca los")
                print("     pases. La palanca real es la RESOLUCION de la malla.")
    else:
        print("\n[aviso] `transitions.parquet` no trae `action_type`.")
        print("        Aplica el parche a possessions.py y vuelve a correr phase0")
        print("        para poder separar pases de acarreos.")

    # --- por fase ---------------------------------------------------------
    por_fase = (
        trans.with_columns(
            (pl.col("from_state") == pl.col("to_state")).alias("es_auto"))
        .group_by("phase")
        .agg(pl.len().alias("n"), pl.col("es_auto").sum().alias("n_auto"))
        .with_columns((pl.col("n_auto") / pl.col("n")).round(4).alias("frac_auto"))
        .sort("frac_auto", descending=True)
    )
    res["por_fase"] = por_fase.to_dicts()
    print("\n== Por fase ==")
    print(por_fase)

    # --- por unidad -------------------------------------------------------
    if args.unit in trans.columns:
        sub = trans.filter(pl.col(args.unit).is_not_null())
        if sub.height:
            por_unidad = (
                sub.with_columns(
                    (pl.col("from_state") == pl.col("to_state")).alias("es_auto"))
                .group_by(args.unit)
                .agg(pl.len().alias("n"), pl.col("es_auto").sum().alias("n_auto"))
                .with_columns((pl.col("n_auto") / pl.col("n")).round(4).alias("frac_auto"))
                .sort("frac_auto", descending=True)
            )
            res["por_unidad"] = por_unidad.to_dicts()
            print(f"\n== Por {args.unit}  (LA COMPARACION QUE IMPORTA) ==")
            print(por_unidad)

            fr = por_unidad["frac_auto"].to_numpy()
            if len(fr) > 1:
                rango = float(fr.max() - fr.min())
                res["rango_frac_auto_entre_unidades"] = round(rango, 4)
                print(f"\n  Rango entre unidades: {rango:.4f}")
                print("  Si este rango explica el grueso de las celdas i -> i")
                print("  significativas de la Fase 3, el hallazgo es sobre CUANTO")
                print("  se queda cada DT en zona, no sobre a donde progresa.")

            # impacto en N por unidad
            imp = {}
            for u in por_unidad[args.unit].to_list():
                imp[u] = impacto_en_N(sub.filter(pl.col(args.unit) == u), space)
            res["impacto_en_N"] = imp
            print("\n== Impacto sobre E[T] (matriz fundamental) ==")
            print(f"{'unidad':<20} {'E[T] con':>9} {'E[T] sin':>9} {'inflacion':>10}")
            print("-" * 52)
            for u, d in imp.items():
                a = d["con_diagonal"].get("E_T_medio")
                b = d["sin_diagonal"].get("E_T_medio")
                infl = d.get("inflacion_por_permanencia")
                if a and b:
                    print(f"{u:<20} {a:>9.3f} {b:>9.3f} {infl:>9.1%}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")

    print("\nSIGUIENTE PASO SEGUN EL RESULTADO")
    print("  frac_auto < 0.10  -> marginal. La Fase 3 se interpreta tal cual.")
    print("  frac_auto 0.10-0.25 -> relevante. Reportar el barrido de resolucion.")
    print("  frac_auto > 0.25  -> la diagonal domina. Subir resolucion antes de")
    print("                       interpretar cualquier cosa sobre retencion.")
    print("\n  En los tres casos: el barrido nx,ny in {4x3, 5x4, 6x4} decide si")
    print("  el efecto es tactico (sobrevive) o de resolucion (se disuelve).")


if __name__ == "__main__":
    main()
