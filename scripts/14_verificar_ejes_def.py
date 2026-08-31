#!/usr/bin/env python3
"""
14_verificar_ejes_def.py — ¿El espejo de la cadena conjugada está al derecho?

EL ERROR QUE ESTE SCRIPT ATRAPA
-------------------------------
El bug #12 fue el eje Y espejeado en el reporte ofensivo. La cadena conjugada
introduce una transformación NUEVA — `StateSpace.mirror_zone` — y por tanto una
oportunidad nueva de cometer el mismo error, esta vez en los mapas defensivos.

Como los once bugs anteriores, no lanzaría excepción: produciría un mapa de
presión perfectamente creíble mostrando la banda contraria.

DOS NIVELES DE VERIFICACIÓN
---------------------------
1. EJE X — sin conocimiento externo, y por eso el más fuerte.
   Las posesiones rivales que arrancan `From Goal Kick` salen de la portería
   DEL RIVAL. En marco nativo eso es x ≈ 0. Tras el espejo debe ser x ≈ 120,
   que es hacia donde ataca el club. Si no se cumple, la reflexión en X está
   mal y no hay más que discutir.

2. EJE Y — requiere conocimiento externo, como el script 13.
   Un extremo derecho rival ocupa, en SU marco, la banda derecha (iy alto con
   la convención de StatsBomb, donde y crece hacia abajo). Tras el espejo debe
   aparecer en NUESTRA izquierda. Vale exactamente lo que valga el
   conocimiento sobre en qué banda juega cada futbolista, así que conviene
   usar varios y de bandas opuestas.

Uso:
  python scripts/14_verificar_ejes_def.py --club "América"
  python scripts/14_verificar_ejes_def.py --club "América" \
      --jugador "Antuna" --banda derecha
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.config import Config
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

# Debe coincidir con FRANJA en 12_reporte_html.py y app.py.
FRANJA = ["banda izquierda", "centro-izquierda", "centro-derecha", "banda derecha"]

# Jugadores RIVALES con banda conocida por fuera de los datos.
# VACÍO A PROPÓSITO: rellenarlo es una decisión con consecuencias, y un jugador
# mal clasificado aquí invalida la verificación entera. Añade solo futbolistas
# de cuya banda estés seguro, y preferentemente de bandas opuestas.
REFERENCIAS: list[tuple[str, str, str]] = [
    # Elegidos por concentracion lateral extrema en marco NATIVO del rival, y
    # coincidentes con su posicion conocida fuera de los datos. Ese doble
    # apoyo es lo que hace la verificacion util: si solo se usara la banda
    # observada, el test seria circular.
    ("Alan Mozo", "derecha", "lateral derecho del Guadalajara, iy3=88%"),
    ("Sanabria", "izquierda", "lateral izquierdo del San Luis, iy0=72%"),
    ("Bryan Alonso Gonz", "izquierda", "carril izquierdo del Pachuca, iy0=83%"),
]


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=tuple(cfg["phase_order"]))


def verificar_eje_x(trans: pl.DataFrame, sp: StateSpace, club: str) -> bool:
    print("=" * 72)
    print("1. EJE X — invariante del saque de meta (sin conocimiento externo)")
    print("=" * 72)

    riv = trans.filter((pl.col("team") != club) & (pl.col("phase") == "restart"))
    if riv.height == 0:
        print("  [salto] sin posesiones rivales en fase `restart`.")
        return True

    n_ph = len(sp.phases)
    z = (riv["from_state"].to_numpy().astype(int) // n_ph)
    ix_nat = z // sp.ny
    ix_esp = sp.mirror_zone(z) // sp.ny

    cx = (np.arange(sp.nx) + 0.5) * sp.length / sp.nx
    x_nat, x_esp = cx[ix_nat].mean(), cx[ix_esp].mean()

    print(f"  posesiones rivales en `restart`: {riv['poss_uid'].n_unique():,}")
    print(f"  x medio, marco NATIVO del rival : {x_nat:6.1f} m")
    print(f"  x medio, tras el espejo         : {x_esp:6.1f} m")
    print(f"  suma (debe ser ~{sp.length:.0f})        : {x_nat + x_esp:6.1f} m")

    ok = abs((x_nat + x_esp) - sp.length) < 1e-6 and x_esp > x_nat
    print(f"\n  >> {'CORRECTO' if ok else 'REVISAR'}: el espejo lleva el origen del")
    print("     rival hacia el arco que el club ataca.")
    if not ok:
        print("     !! Si x_esp < x_nat, mirror_zone invierte el eje al revés.")
    return ok


def verificar_eje_y(trans: pl.DataFrame, sp: StateSpace, club: str,
                    refs: list[tuple[str, str, str]]) -> bool | None:
    print("\n" + "=" * 72)
    print("2. EJE Y — requiere conocimiento externo sobre la banda del jugador")
    print("=" * 72)

    if not refs:
        print("  [salto] REFERENCIAS está vacío.")
        print()
        print("  Esto NO es un aprobado: es una verificación que no se hizo.")
        print("  Edita REFERENCIAS en este script con jugadores RIVALES de banda")
        print("  conocida, o pasa --jugador y --banda. Sin ella, el eje lateral")
        print("  de los mapas defensivos queda sin comprobar, que es exactamente")
        print("  la situación en la que vivió el bug #12 durante semanas.")
        return None

    print("  Etiquetas del reporte, desde NUESTRA perspectiva:")
    for k, f in enumerate(FRANJA):
        print(f"    iy={k}  {f}")
    print()

    n_ph = len(sp.phases)
    veredictos = []
    for patron, banda, desc in refs:
        sub = trans.filter(
            (pl.col("team") != club)
            & pl.col("player").is_not_null()
            & pl.col("player").str.contains(patron)
        )
        if sub.height == 0:
            print(f"  [salto] {patron}: sin acciones de rival en este archivo")
            continue

        z = sub["from_state"].to_numpy().astype(int) // n_ph
        iy_esp = sp.mirror_zone(z) % sp.ny
        r = np.bincount(iy_esp, minlength=sp.ny) / len(iy_esp)
        dom = int(np.argmax(r))

        # Un extremo DERECHO del rival debe aparecer en NUESTRA IZQUIERDA.
        esperada = "izquierda" if banda == "derecha" else "derecha"
        ok = esperada in FRANJA[dom]
        veredictos.append(ok)

        print(f"  {patron}  ({desc} del rival; en nuestro marco -> {esperada})")
        for k in range(sp.ny):
            barra = "#" * int(r[k] * 40)
            marca = " <-" if k == dom else ""
            print(f"     iy={k}  {FRANJA[k]:<18} {r[k]:6.1%}  {barra}{marca}")
        print(f"     {sub.height} acciones · {'CORRECTO' if ok else 'ESPEJEADO'}\n")

    if not veredictos:
        return None
    if all(veredictos):
        print("  >> CORRECTO: el eje lateral defensivo está al derecho.")
        return True
    if not any(veredictos):
        print("  >> ESPEJEADO: revisa mirror_zone y FRANJA.")
        return False
    print("  >> INCONSISTENTE: unos jugadores dicen una cosa y otros la contraria.")
    print("     Probablemente alguna banda declarada en REFERENCIAS está mal.")
    return False


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--club", required=True)
    ap.add_argument("--jugador", default=None, help="patrón de nombre (rival)")
    ap.add_argument("--banda", default=None, choices=["izquierda", "derecha"],
                    help="banda del jugador EN SU PROPIO marco")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    sp = _space(cfg)

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)

    if "player" not in trans.columns:
        sys.exit("transitions.parquet no trae `player`. Vuelve a correr phase0.")
    riv = trans.filter(pl.col("team") != args.club)
    if riv.height == 0:
        sys.exit(f"Cero transiciones de rivales para club={args.club!r}.")

    print(f"malla {sp.nx}x{sp.ny} · club {args.club!r} · "
          f"{riv['poss_uid'].n_unique():,} posesiones rivales\n")

    ok_x = verificar_eje_x(trans, sp, args.club)

    refs = ([(args.jugador, args.banda, "indicado a mano")]
            if args.jugador and args.banda else REFERENCIAS)
    ok_y = verificar_eje_y(trans, sp, args.club, refs)

    print("\n" + "=" * 72)
    if not ok_x or ok_y is False:
        print("VEREDICTO: NO uses los mapas defensivos hasta resolver esto.")
        sys.exit(1)
    if ok_y is None:
        print("VEREDICTO: eje X verificado; eje Y SIN VERIFICAR.")
        print("Los mapas defensivos son usables en el eje de ataque, pero no")
        print("afirmes nada sobre bandas hasta rellenar REFERENCIAS.")
        sys.exit(2)
    print("VEREDICTO: ambos ejes verificados.")


if __name__ == "__main__":
    main()
