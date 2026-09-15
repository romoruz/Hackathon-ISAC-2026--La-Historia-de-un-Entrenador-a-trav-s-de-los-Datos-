#!/usr/bin/env python3
"""
sonda_05_estructura.py — lee los metadatos YA DESCARGADOS (sin tocar la red).

Contesta las cuatro preguntas que deciden el diseno del analisis:
  1. Como se separan Apertura / Clausura / liguilla  -> competition_stage
  2. Que es Atlante y en que temporada aparece
  3. Como escribe el API los nombres de entrenador vs tu coach_eras.csv
  4. Cuantas eras analizables hay realmente, por club

Requiere haber corrido antes:
    python scripts/00_fetch_statsbomb.py --solo-metadatos
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw_api")
MIN_PARTIDOS = 15  # umbral orientativo de era analizable


def nombre(d, *claves):
    for k in claves:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d


def cargar():
    filas = []
    for p in sorted((OUT / "matches").glob("*.json.gz")):
        sid = int(p.stem.split("_")[1].split(".")[0])
        crudo = json.loads(gzip.decompress(p.read_bytes()))
        it = crudo.values() if isinstance(crudo, dict) else crudo
        for m in it:
            filas.append((sid, m))
    return filas


def dt(m, lado):
    ms = m.get(f"{lado}_team", {}).get("managers") or m.get(f"{lado}_managers")
    if isinstance(ms, list) and ms:
        return ms[0].get("name"), ms[0].get("nickname")
    if isinstance(ms, str):
        return ms, None
    return None, None


def main() -> int:
    filas = cargar()
    if not filas:
        print(f"No hay metadatos en {OUT}/matches/. Corre primero:")
        print("  python scripts/00_fetch_statsbomb.py --solo-metadatos")
        return 1
    print(f"Partidos leidos: {len(filas)}\n")

    # ---- 1. etapas por temporada
    print("=" * 70)
    print("1. ETAPAS (competition_stage) por temporada")
    print("=" * 70)
    por_temp = defaultdict(Counter)
    for sid, m in filas:
        por_temp[sid][str(nombre(m, "competition_stage", "name"))] += 1
    for sid in sorted(por_temp):
        print(f"\n  temporada {sid}:")
        for etapa, n in por_temp[sid].most_common():
            print(f"      {n:4d}  {etapa}")

    # ---- 2. Atlante y equipos raros
    print("\n" + "=" * 70)
    print("2. EQUIPOS por temporada (busca a Atlante)")
    print("=" * 70)
    eq = defaultdict(set)
    for sid, m in filas:
        for lado in ("home", "away"):
            eq[sid].add(nombre(m, f"{lado}_team", f"{lado}_team_name")
                        or m.get(f"{lado}_team"))
    for sid in sorted(eq):
        faltan = eq[sid] - set.intersection(*eq.values())
        print(f"  {sid}: {len(eq[sid])} equipos"
              + (f"   propios de esta temporada: {sorted(map(str, faltan))}"
                 if faltan else ""))
    raros = [(sid, str(nombre(m, "competition_stage", "name")),
              str(m.get("match_date"))[:10])
             for sid, m in filas
             for lado in ("home", "away")
             if "Atlante" in str(m.get(f"{lado}_team"))]
    if raros:
        print("\n  Partidos con Atlante:")
        for r in raros[:10]:
            print("     ", r)

    # ---- 3. nombres de entrenador
    print("\n" + "=" * 70)
    print("3. NOMBRES DE ENTRENADOR: name vs nickname")
    print("=" * 70)
    pares = set()
    for _, m in filas:
        for lado in ("home", "away"):
            n, nick = dt(m, lado)
            if n:
                pares.add((n, nick))
    print(f"  Entrenadores distintos: {len(pares)}\n")
    for n, nick in sorted(pares)[:20]:
        print(f"      {str(n):42s} | {nick}")
    print("      ...")

    ruta_eras = Path("data/coach_eras.csv")
    if ruta_eras.exists():
        mios = [l.split(",")[0] for l in
                ruta_eras.read_text(encoding="utf-8").strip().split("\n")[1:]]
        print(f"\n  Tu coach_eras.csv: {mios}")
        print("  -> hay que normalizar: el API da el nombre legal completo.")

    # ---- 4. eras por club
    print("\n" + "=" * 70)
    print(f"4. ERAS POR CLUB (rachas continuas, minimo {MIN_PARTIDOS} partidos)")
    print("=" * 70)
    reg = defaultdict(list)
    for _, m in filas:
        fecha = str(m.get("match_date"))[:10]
        for lado in ("home", "away"):
            equipo = str(nombre(m, f"{lado}_team", f"{lado}_team_name")
                         or m.get(f"{lado}_team"))
            n, _ = dt(m, lado)
            if n:
                reg[equipo].append((fecha, n))

    total_eras = total_ok = 0
    for club in sorted(reg):
        seq = sorted(reg[club])
        rachas, actual, quien = [], 0, None
        for _, n in seq:
            if n != quien:
                if quien is not None:
                    rachas.append((quien, actual))
                quien, actual = n, 0
            actual += 1
        if quien is not None:
            rachas.append((quien, actual))
        ok = [r for r in rachas if r[1] >= MIN_PARTIDOS]
        total_eras += len(rachas)
        total_ok += len(ok)
        print(f"\n  {club}  ({len(seq)} partidos, {len(rachas)} rachas, "
              f"{len(ok)} analizables)")
        for n, k in sorted(rachas, key=lambda r: -r[1]):
            marca = "  <-- analizable" if k >= MIN_PARTIDOS else ""
            print(f"      {k:4d}  {n}{marca}")

    print("\n" + "=" * 70)
    print(f"TOTAL rachas: {total_eras}   analizables (>={MIN_PARTIDOS}): {total_ok}")
    print("=" * 70)
    print("\nOJO: una racha cortada por un interinato de 1 partido sale partida")
    print("en tres. Eso se arregla en el constructor de eras, no aqui.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
