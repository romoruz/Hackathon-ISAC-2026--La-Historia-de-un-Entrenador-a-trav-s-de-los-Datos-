#!/usr/bin/env python3
"""
31_backfill_club.py — rellena `club` en los JSON de pares que no lo traen.

POR QUE EXISTE (paquete h2_11)
------------------------------
`12_reporte_html.py` ahora exige la clave compuesta (club, entrenador) y
descarta todo JSON sin `club`. Los `ic_*.json` (08_ic_derivados.py) y los
`plantel_*.json` (11_confusion_plantel.py) se generaron sin ese campo.

Regenerarlos es lo limpio. Esto es lo barato, y es verificable: el club de un
par (a, b) se INFIERE de `data/eras_api/eras_todas.csv` como el unico club en
el que dirigieron LOS DOS. Si hay cero o mas de un club posible, NO se escribe
nada para ese archivo: se reporta y se deja para regenerar a mano.

Por defecto solo muestra lo que haria. `--escribir` aplica, con respaldo en
`reports/_respaldo_h2_11/` (fuera del alcance de los glob del reporte).

Uso:
    python scripts/31_backfill_club.py
    python scripts/31_backfill_club.py --escribir
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PATRONES = ("ic_*.json", "plantel_*.json")


def clubes_por_entrenador(eras_csv: Path,
                          solo_analizables: bool = True) -> dict[str, set[str]]:
    """coach -> clubes donde dirigio.

    Por defecto solo eras analizables: los ic_/plantel_ solo existen para
    ellas. Con TODAS las eras hay tres parejas que coinciden en dos clubes
    (Ambriz-Paiva en Toluca y Leon, Herrera-Siboldi, Larcamon-Guede): la
    colision del bug #17 no es hipotetica en esta liga.
    """
    out: dict[str, set[str]] = defaultdict(set)
    with eras_csv.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if solo_analizables and r.get("analizable") != "1":
                continue
            out[r["coach"]].add(r["club"])
    return out


def infiere(a: str, b: str, mapa: dict[str, set[str]]) -> tuple[str | None, str]:
    comunes = mapa.get(a, set()) & mapa.get(b, set())
    if len(comunes) == 1:
        return next(iter(comunes)), "ok"
    if not comunes:
        return None, "ningun club comun"
    return None, f"AMBIGUO: {sorted(comunes)}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", type=Path, default=RAIZ / "reports")
    ap.add_argument("--eras", type=Path,
                    default=RAIZ / "data" / "eras_api" / "eras_todas.csv")
    ap.add_argument("--escribir", action="store_true")
    ap.add_argument("--todas-las-eras", action="store_true",
                    help="inferir con todas las eras, no solo las analizables")
    args = ap.parse_args()

    if not args.eras.exists():
        sys.exit(f"No existe {args.eras}")
    mapa = clubes_por_entrenador(args.eras, not args.todas_las_eras)

    archivos = sorted({p for pat in PATRONES for p in args.reports.glob(pat)})
    ya, rellenables, problemas = 0, [], []
    for p in archivos:
        d = json.loads(p.read_text())
        a, b = d.get("a"), d.get("b")
        if a is None or b is None:
            problemas.append((p.name, "sin campos a/b"))
            continue
        club, motivo = infiere(a, b, mapa)
        if "club" in d:
            ya += 1
            if club is not None and d["club"] != club:
                problemas.append((p.name, f"club={d['club']} pero eras dice {club}"))
            continue
        if club is None:
            problemas.append((p.name, motivo))
        else:
            rellenables.append((p, club))

    print(f"archivos revisados : {len(archivos)}")
    print(f"ya traen club      : {ya}")
    print(f"rellenables        : {len(rellenables)}")
    print(f"con problema       : {len(problemas)}")
    por_club: dict[str, int] = defaultdict(int)
    for _, c in rellenables:
        por_club[c] += 1
    for c, n in sorted(por_club.items()):
        print(f"    {c:<22} {n}")
    for nom, mot in problemas:
        print(f"  !! {nom}: {mot}")

    if not args.escribir:
        print("\n(solo lectura; usa --escribir para aplicar)")
        return 1 if problemas else 0

    resp = args.reports / "_respaldo_h2_11" / time.strftime("%Y%m%d%H%M")
    resp.mkdir(parents=True, exist_ok=True)
    for p, club in rellenables:
        shutil.copy2(p, resp / p.name)
        d = json.loads(p.read_text())
        d = {"club": club, **d}
        d["club_origen"] = "inferido por 31_backfill_club.py desde eras_todas.csv"
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False))
    print(f"\nescritos {len(rellenables)}; respaldo en {resp}")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
