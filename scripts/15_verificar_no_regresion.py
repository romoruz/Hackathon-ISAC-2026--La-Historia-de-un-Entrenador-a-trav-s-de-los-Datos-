#!/usr/bin/env python3
"""
15_verificar_no_regresion.py — ¿El parche movió algún número ofensivo?

El parche D0 toca `possessions.py`, `eras.py`, `grid.py` y `cli.py`, que la
fase ofensiva usa en producción. La condición que lo hace aceptable es que la
ruta ofensiva quede **bit a bit idéntica**.

`pytest -q` verifica el código. Esto verifica el ARTEFACTO, que es lo que
sostiene las cifras de `10_RESULTADOS.md`.

Uso:
  cp data/processed/transitions.parquet /tmp/transitions_pre_parche.parquet
  # ... aplicar parche, correr phase0 con --club ...
  python scripts/15_verificar_no_regresion.py \
      --antes /tmp/transitions_pre_parche.parquet \
      --despues data/processed/transitions.parquet --club "América"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

CLAVE = ["poss_uid", "event_index"]
COMPARAR = ["match_id", "team", "phase", "score_state", "action_type",
            "player_id", "from_state", "to_state", "is_absorbing"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--antes", required=True)
    ap.add_argument("--despues", required=True)
    ap.add_argument("--club", required=True)
    args = ap.parse_args()

    for p in (args.antes, args.despues):
        if not Path(p).exists():
            sys.exit(f"No existe {p}")

    a = pl.read_parquet(args.antes)
    b = pl.read_parquet(args.despues)

    print("=" * 72)
    print("COLUMNAS")
    print("=" * 72)
    nuevas = [c for c in b.columns if c not in a.columns]
    perdidas = [c for c in a.columns if c not in b.columns]
    print(f"  nuevas   : {nuevas or 'ninguna'}")
    print(f"  perdidas : {perdidas or 'ninguna'}")
    if perdidas:
        print("\n  !! Se perdieron columnas. Eso rompe consumidores aguas abajo.")

    print("\n" + "=" * 72)
    print(f"RUTA OFENSIVA (team == {args.club!r}) — debe ser IDÉNTICA")
    print("=" * 72)
    cols = [c for c in COMPARAR if c in a.columns and c in b.columns]
    ao = a.filter(pl.col("team") == args.club).select(CLAVE + cols).sort(CLAVE)
    bo = b.filter(pl.col("team") == args.club).select(CLAVE + cols).sort(CLAVE)

    print(f"  filas antes  : {ao.height:,}")
    print(f"  filas después: {bo.height:,}")

    fallo = False
    if ao.height != bo.height:
        print("\n  !! FALLO: cambió el número de transiciones del club.")
        sa, sb = set(ao["poss_uid"].to_list()), set(bo["poss_uid"].to_list())
        print(f"     posesiones solo en 'antes'  : {len(sa - sb):,}")
        print(f"     posesiones solo en 'después': {len(sb - sa):,}")
        fallo = True
    elif not ao.equals(bo):
        print("\n  !! FALLO: mismas filas, contenido distinto.")
        for c in cols:
            n = int((ao[c] != bo[c]).sum())
            if n:
                print(f"     {c}: {n:,} filas difieren")
        fallo = True
    else:
        print("\n  OK: la ruta ofensiva es idéntica columna a columna.")

    print("\n" + "=" * 72)
    print("CADENA CONJUGADA (rivales) — debe CRECER por min_actions_defense=1")
    print("=" * 72)
    ad = a.filter(pl.col("team") != args.club)
    bd = b.filter(pl.col("team") != args.club)
    pa, pb = ad["poss_uid"].n_unique(), bd["poss_uid"].n_unique()
    print(f"  posesiones rivales antes  : {pa:,}")
    print(f"  posesiones rivales después: {pb:,}")
    if pb > pa:
        print(f"  OK: +{pb - pa:,} ({(pb - pa) / max(pa, 1):.2%}) recuperadas.")
        print("      Son las posesiones de UNA acción que la presión produce.")
    elif pb == pa:
        print("  !! Sin cambio: revisa `min_actions_defense` en el config.")
    else:
        print("  !! FALLO: se perdieron posesiones rivales. No debería pasar.")
        fallo = True

    if "under_pressure" in b.columns:
        reales = bd.filter(pl.col("action_type") != "TERMINAL")
        if reales.height:
            tasa = float(reales["under_pressure"].mean())
            nulos = int(reales["under_pressure"].null_count())
            print("\n" + "=" * 72)
            print("MARCA DE PRESIÓN — primer número de D1")
            print("=" * 72)
            print(f"  pi marginal sobre acciones rivales : {tasa:.4f}")
            print(f"  nulos en acciones reales           : {nulos:,} (debe ser 0)")
            if nulos or tasa <= 0.001 or tasa >= 0.999:
                print("\n  !! `under_pressure` se leyó mal. Es una BANDERA")
                print("     (true / ausente), no un booleano. Revisa el fill_null.")
                fallo = True
            else:
                print("\n  OK: la marca se leyó como bandera.")

    print("\n" + "=" * 72)
    if fallo:
        print("VEREDICTO: REVERTIR. Hay regresión.")
        sys.exit(1)
    print("VEREDICTO: sin regresión. Puedes regenerar con generar_todo.sh.")


if __name__ == "__main__":
    main()
