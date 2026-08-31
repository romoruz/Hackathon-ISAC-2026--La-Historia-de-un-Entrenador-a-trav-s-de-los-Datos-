#!/usr/bin/env python3
"""
13_verificar_ejes.py — ¿Las etiquetas de banda del reporte están al derecho?

EL ERROR QUE ESTE SCRIPT ATRAPA
-------------------------------
StatsBomb usa origen en la esquina ARRIBA-IZQUIERDA, con `y` creciendo HACIA
ABAJO. Un equipo que ataca hacia x=120 tiene el borde y=0 a su IZQUIERDA.

La primera version del reporte tenia el vector FRANJA al reves:

    FRANJA = ["banda derecha", ..., "banda izquierda"]   # MAL

y por tanto TODOS los mapas salian espejeados. Es un error que no rompe nada,
no lanza excepciones y produce un reporte perfectamente creible -- hasta que
alguien que ve futbol lo mira y detecta al instante que el extremo derecho
aparece por la izquierda.

Fue el bug numero 12 del proyecto, y como los once anteriores, silencioso.

COMO LO VERIFICA
----------------
Con jugadores cuya banda se conoce por fuera de los datos. Si un extremo
derecho concentra sus acciones en la franja etiquetada "banda derecha", las
etiquetas estan bien. Si aparece en la izquierda, estan espejeadas.

NO es una prueba estadistica: es una verificacion de sentido comun contra
conocimiento externo. Vale exactamente lo que valga ese conocimiento, asi que
conviene usar VARIOS jugadores y de bandas opuestas.

Uso:
  python scripts/13_verificar_ejes.py
  python scripts/13_verificar_ejes.py --jugador Zendejas --banda derecha
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

# Orden actual del reporte. Debe coincidir con FRANJA en 12_reporte_html.py
# y en app.py. Si se cambia aqui, cambiarlo alla.
FRANJA = ["banda izquierda", "centro-izquierda", "centro-derecha", "banda derecha"]
NY = 4

# Jugadores con banda conocida por fuera de los datos. Ampliar con cuidado:
# un jugador mal clasificado aqui invalida la verificacion entera.
REFERENCIAS = [
    ("Zendejas", "derecha", "extremo derecho del América"),
    ("Fuentes", "izquierda", "lateral izquierdo del América"),
    ("Layún", "derecha", "lateral derecho del América"),
]


def reparto(trans: pl.DataFrame, patron: str) -> tuple[np.ndarray, int]:
    sub = trans.filter(
        pl.col("player").is_not_null() & pl.col("player").str.contains(patron))
    if sub.height == 0:
        return np.zeros(NY), 0
    iy = (sub["from_state"].to_numpy().astype(int) // 4) % NY
    return np.bincount(iy, minlength=NY) / len(iy), sub.height


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--jugador", default=None, help="patron de nombre")
    ap.add_argument("--banda", default=None, choices=["izquierda", "derecha"])
    args = ap.parse_args()

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)
    if "player" not in trans.columns:
        sys.exit("transitions.parquet no trae `player`. Aplica el parche a "
                 "possessions.py y vuelve a correr phase0.")

    refs = ([(args.jugador, args.banda, "indicado a mano")]
            if args.jugador and args.banda else REFERENCIAS)

    print("Etiquetas actuales del reporte, de iy=0 a iy=3:")
    for k, f in enumerate(FRANJA):
        print(f"  iy={k}  {f}")
    print()

    veredictos = []
    for patron, banda, desc in refs:
        r, n = reparto(trans, patron)
        if n == 0:
            print(f"[salto] {patron}: sin acciones en este archivo")
            continue
        dom = int(np.argmax(r))
        etiqueta = FRANJA[dom]
        ok = banda in etiqueta
        veredictos.append(ok)
        print(f"{patron}  ({desc}, se espera {banda})")
        for k in range(NY):
            barra = "█" * int(r[k] * 40)
            marca = " ←" if k == dom else ""
            print(f"   iy={k}  {FRANJA[k]:<18} {r[k]:6.1%}  {barra}{marca}")
        print(f"   {n} acciones · franja dominante: {etiqueta} · "
              f"{'CORRECTO' if ok else 'ESPEJEADO'}\n")

    if not veredictos:
        sys.exit("Ningun jugador de referencia aparece en el archivo.")

    if all(veredictos):
        print("== VEREDICTO: las etiquetas estan al derecho ==")
    elif not any(veredictos):
        print("== VEREDICTO: ESPEJEADAS ==")
        print("   Invierte FRANJA en scripts/12_reporte_html.py y en app.py:")
        print(f'   {FRANJA[::-1]}')
        sys.exit(1)
    else:
        print("== VEREDICTO: INCONSISTENTE ==")
        print("   Unos jugadores dicen una cosa y otros la contraria. Revisa la")
        print("   banda declarada de cada uno en REFERENCIAS: probablemente")
        print("   alguno este mal clasificado, o juegue en las dos.")
        sys.exit(1)

    print("\nRECORDATORIO: esto verifica contra conocimiento EXTERNO sobre en")
    print("que banda juega cada futbolista. Vale lo que valga ese conocimiento.")


if __name__ == "__main__":
    main()
