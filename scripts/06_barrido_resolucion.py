#!/usr/bin/env python3
"""
06_barrido_resolucion.py — El efecto, ¿sobrevive al cambiar la malla?

LA PRUEBA DECISIVA
------------------
El diagnostico de auto-transiciones dio frac_auto = 0.28 a 5x4, con el 42% de
la longitud esperada explicado por permanencia en zona. Eso deja abierta la
pregunta: cuando decimos "Jardine sostiene posesiones mas largas", ¿es tactica
o es que sus pases cortos caben dentro de zonas de 24 x 20 m?

La respuesta es empirica. Si el efecto SOBREVIVE al afinar la malla, es
tactico. Si se DISUELVE, era resolucion espacial.

Este script recarga los eventos UNA vez y reconstruye las transiciones a
varias resoluciones, sin tocar el config ni pisar `data/processed`.

QUE SE REPORTA POR MALLA
------------------------
  frac_auto          : cuanto de la cadena es quedarse en el sitio
  frac_below_min     : renglones con <30 obs en la unidad MAS CHICA
  params_per_obs     : sobreajuste (glosario: >0.5 es demasiado)
  E[T] por unidad    : con y sin diagonal
  delta vs baseline  : el efecto que se quiere probar, malla por malla

CUIDADO CON EL COSTO
--------------------
Afinar la malla multiplica los parametros por (4Z)^2. 02_STATE_OF_PLAY §5
advierte que 6x4 sobre la era mas chica da params_per_obs ~0.48, al filo. Este
script lo mide en cada malla para que la decision no sea a ojo.

Uso:
  python scripts/06_barrido_resolucion.py --src eventos_completos_america.csv \\
      --eras data/coach_eras.csv --match-dates data/match_dates.csv \\
      --club "América" --a "Andre Jardine" --b "Santiago Solari"
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder import eras as eras_mod
    from dtdecoder import ingest
    from dtdecoder.config import Config
    from dtdecoder.estimate import count_matrix, mle, sparsity_report
    from dtdecoder.grid import StateSpace
    from dtdecoder.possessions import build_transitions
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12
MALLAS = [(4, 3), (5, 4), (6, 4), (6, 5)]


def _E_T(trans: pl.DataFrame, space: StateSpace, quitar_diagonal: bool) -> float | None:
    C = count_matrix(trans, space)
    if quitar_diagonal:
        idx = np.arange(space.n_transient)
        C = C.copy()
        C[idx, idx] = 0.0
    Q = mle(C)[:, : space.n_transient]
    if float(np.abs(np.linalg.eigvals(Q)).max()) >= 1.0:
        return None
    N1 = np.linalg.solve(np.eye(space.n_transient) - Q, np.ones(space.n_transient))
    w = C.sum(axis=1)
    return float((N1 * w / max(w.sum(), _EPS)).sum())


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--src", required=True)
    ap.add_argument("--eras", required=True)
    ap.add_argument("--match-dates", required=True, dest="match_dates")
    ap.add_argument("--club", required=True)
    ap.add_argument("--a", required=True, help="unidad focal")
    ap.add_argument("--b", required=True, help="unidad de contraste")
    ap.add_argument("--mallas", nargs="+", default=None,
                    help="p.ej. 4x3 5x4 6x4")
    ap.add_argument("--out", default="reports/barrido_resolucion.json")
    args = ap.parse_args()

    mallas = MALLAS
    if args.mallas:
        mallas = [tuple(int(v) for v in m.lower().split("x")) for m in args.mallas]

    cfg = Config.load(args.config)
    print(f"cargando eventos de {args.src} (una sola vez)...", file=sys.stderr)
    eventos = ingest.load(args.src)
    eras = eras_mod.load_eras(args.eras)
    md = eras_mod.load_match_dates(args.match_dates)
    mc = eras_mod.match_coach_table(md, eras, args.club)

    filas, detalle = [], {}
    for nx, ny in mallas:
        raw = copy.deepcopy(cfg.raw)
        raw["pitch"]["nx"], raw["pitch"]["ny"] = nx, ny
        phases = tuple(raw.get("phase_order") or sorted(raw["phases"].keys()))
        space = StateSpace(nx=nx, ny=ny, length=raw["pitch"]["length"],
                           width=raw["pitch"]["width"], phases=phases)

        trans = build_transitions(eventos, space, raw, team=None)
        trans = eras_mod.attach_coach(trans, mc, args.club)

        auto = trans.filter(pl.col("from_state") == pl.col("to_state")).height
        frac_auto = auto / max(trans.height, 1)

        sub_a = trans.filter(pl.col("coach") == args.a)
        sub_b = trans.filter(pl.col("coach") == args.b)
        if sub_a.height == 0 or sub_b.height == 0:
            sys.exit(f"Sin transiciones para '{args.a}' o '{args.b}' en {nx}x{ny}")

        et_a, et_b = _E_T(sub_a, space, False), _E_T(sub_b, space, False)
        et_a_sd, et_b_sd = _E_T(sub_a, space, True), _E_T(sub_b, space, True)

        # La unidad mas chica manda para el diagnostico de esparsidad.
        chica = sub_a if sub_a.height < sub_b.height else sub_b
        sp = sparsity_report(count_matrix(chica, space))

        fila = {
            "malla": f"{nx}x{ny}",
            "zona_m": f"{raw['pitch']['length']/nx:.0f}x{raw['pitch']['width']/ny:.0f}",
            "n_transient": space.n_transient,
            "frac_auto": round(frac_auto, 4),
            "frac_below_min_unidad_chica": round(sp["frac_below_min"], 4),
            "params_per_obs_unidad_chica": round(sp["params_per_obs"], 4),
            "E_T_a": round(et_a, 4) if et_a else None,
            "E_T_b": round(et_b, 4) if et_b else None,
            "delta_pct": round((et_a / et_b - 1) * 100, 2) if et_a and et_b else None,
            "delta_pct_sin_diagonal": round((et_a_sd / et_b_sd - 1) * 100, 2)
            if et_a_sd and et_b_sd else None,
            "malla_usable": bool(sp["frac_below_min"] < 0.30 and sp["params_per_obs"] < 0.5),
        }
        filas.append(fila)
        detalle[fila["malla"]] = {"sparsity_unidad_chica": sp}
        print(f"  {fila['malla']:>5}  frac_auto={frac_auto:.4f}  "
              f"delta={fila['delta_pct']}%  usable={fila['malla_usable']}",
              file=sys.stderr)

    res = {"focal": args.a, "contraste": args.b, "club": args.club,
           "por_malla": filas, "detalle": detalle}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))

    print(f"\n== {args.a}  vs  {args.b} ==\n")
    print(f"{'malla':>6} {'zona':>8} {'frac_auto':>10} {'delta%':>8} "
          f"{'delta% s/diag':>14} {'below_min':>10} {'p/obs':>7}  usable")
    print("-" * 82)
    for f in filas:
        print(f"{f['malla']:>6} {f['zona_m']:>8} {f['frac_auto']:>10.4f} "
              f"{str(f['delta_pct']):>8} {str(f['delta_pct_sin_diagonal']):>14} "
              f"{f['frac_below_min_unidad_chica']:>10.4f} "
              f"{f['params_per_obs_unidad_chica']:>7.3f}  {f['malla_usable']}")

    print(f"\nescrito: {out}")
    print("\nCOMO LEERLO")
    print("  frac_auto DEBE bajar al afinar la malla: zonas mas chicas retienen")
    print("  menos. Si no baja, algo esta mal en la construccion de estados.")
    print("\n  delta% ESTABLE entre mallas usables -> el efecto es TACTICO y")
    print("  no depende de la particion. Es el argumento fuerte.")
    print("  delta% que se DISUELVE al afinar -> era resolucion espacial. Hay")
    print("  que retirar la afirmacion del reporte.")
    print("\n  Solo comparar entre mallas con usable=True. Una malla que no")
    print("  pasa esparsidad da un delta sin sentido, no un contraejemplo.")


if __name__ == "__main__":
    main()
