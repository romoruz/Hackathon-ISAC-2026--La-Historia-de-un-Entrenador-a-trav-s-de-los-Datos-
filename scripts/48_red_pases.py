#!/usr/bin/env python3
"""
48_red_pases.py — F4 / ADR-62, paso 0: DIAGNÓSTICO DE VIABILIDAD.

Este modo NO calcula ningún estimando y NO mira ninguna relación entre
variables. Solo responde lo que hace falta para poder preinscribir ADR-62 con
umbrales reales en vez de inventados:

  * ¿existe `pass_recipient_id` en los parquets, y en cuántos clubes?
  * ¿qué proporción de los pases trae receptor?
  * ¿cuántos jugadores y cuántas parejas pasador→receptor tiene cada era?
  * ¿cuántas parejas de técnicos consecutivos del mismo club quedarían
    comparables con distintos umbrales?

Mirar la forma de los datos (cobertura, tamaños) es lo que permite escribir una
preinscripción honesta. Mirar una relación sería contaminarla. Por eso este
script **no** admite, de momento, ningún modo que no sea `--solo-diagnostico`:
la medición llega en un paquete posterior, después de que ADR-62 esté commiteada.

Uso:
    python scripts/48_red_pases.py --solo-diagnostico
    python scripts/48_red_pases.py --solo-diagnostico --out reports/red_diag.json
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAND_RECEPTOR = ["pass_recipient_id", "recipient_id", "pass_recipient", "receiver_id"]
UMBRALES_JUG = [100, 200, 400]     # pases del jugador en la era
UMBRALES_PAR = [3, 5, 8]           # jugadores en común por pareja de técnicos


class Aborta(Exception):
    pass


def columnas(p: Path):
    import polars as pl
    return set(pl.read_parquet_schema(p))


def diagnostico(indirs, pares):
    import polars as pl
    filas, sin_col, receptor_en = [], [], Counter()
    eras = {}
    for d in indirs:
        p = Path(d) / "transitions.parquet"
        if not p.exists():
            raise Aborta(f"falta {p}")
        cols = columnas(p)
        rec = next((c for c in CAND_RECEPTOR if c in cols), None)
        if rec is None:
            sin_col.append(Path(d).name)
            continue
        receptor_en[rec] += 1
        need = ["team", "coach", "player_id", rec]
        if "action_type" in cols:
            need.append("action_type")
        t = pl.read_parquet(p, columns=need).filter(pl.col("coach").is_not_null())
        club = t["team"].unique().to_list()[0]
        n_tot = t.height
        con = t.filter(pl.col(rec).is_not_null() & pl.col("player_id").is_not_null())
        for (coach,), g in con.group_by("coach", maintain_order=True):
            pas = g.group_by("player_id").agg(pl.len().alias("n"))
            pares_ij = g.group_by(["player_id", rec]).agg(pl.len().alias("n"))
            eras[(club, coach)] = {
                "club": club, "coach": coach, "n_con_receptor": g.height,
                "n_jugadores": pas.height,
                "n_jugadores_por_umbral": {str(u): int((pas["n"] >= u).sum()) for u in UMBRALES_JUG},
                "n_parejas_ij": pares_ij.height,
                "parejas_ij_con_10_o_mas": int((pares_ij["n"] >= 10).sum()),
            }
        filas.append({"club": club, "columna_receptor": rec, "n_filas": n_tot,
                      "n_con_receptor": int(con.height),
                      "cobertura": round(con.height / n_tot, 4) if n_tot else None})
    return filas, sin_col, dict(receptor_en), eras


def comparables(eras, pares, u_jug, u_par):
    """Cuántas parejas de técnicos quedarían con al menos u_par jugadores en común
    que superen u_jug pases en las DOS eras. No mira ningún valor, solo cuenta."""
    ok, detalle = 0, []
    for p in pares:
        a, b = (p["club"], p["a"]), (p["club"], p["b"])
        if a not in eras or b not in eras:
            continue
        n = min(eras[a]["n_jugadores_por_umbral"][str(u_jug)],
                eras[b]["n_jugadores_por_umbral"][str(u_jug)])
        detalle.append({"club": p["club"], "a": p["a"], "b": p["b"], "cota_jugadores": n})
        if n >= u_par:
            ok += 1
    return ok, detalle


def inventario():
    """Qué archivos y qué columnas hay de verdad. No lee una sola fila de datos:
    solo el esquema. Sirve para saber si la red de pases es reconstruible."""
    import polars as pl
    dirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    if not dirs:
        sys.exit("ABORTA: no hay directorios data/processed_api_*")
    print(f"=== {len(dirs)} directorios ===")
    porarch = {}
    for d in dirs:
        for f in sorted(Path(d).glob("*")):
            porarch.setdefault(f.name, []).append(f)
    for nombre, fs in sorted(porarch.items()):
        print(f"\n--- {nombre} · en {len(fs)} de {len(dirs)} directorios ---")
        if not nombre.endswith(".parquet"):
            print("    (no es parquet; no se lee su esquema)")
            continue
        try:
            cols = pl.read_parquet_schema(fs[0])
        except Exception as e:                      # noqa: BLE001
            print(f"    no pude leer el esquema: {e}")
            continue
        comunes = set(cols)
        for f in fs[1:]:
            try:
                comunes &= set(pl.read_parquet_schema(f))
            except Exception:                        # noqa: BLE001
                pass
        print(f"    {len(cols)} columnas en el primero, {len(comunes)} comunes a todos:")
        for c in sorted(comunes):
            print(f"      {c}: {cols.get(c)}")
        solo = sorted(set(cols) - comunes)
        if solo:
            print(f"    solo en algunos: {', '.join(solo)}")
    print("\n=== ¿se puede reconstruir el receptor de un pase? ===")
    p0 = Path(dirs[0]) / "transitions.parquet"
    cols = set(pl.read_parquet_schema(p0))
    need = {"poss_uid": "la posesión", "event_index": "el orden dentro de la posesión",
            "player_id": "quién hace la acción", "team": "el equipo"}
    tipo = next((c for c in ("action_type", "type", "event_type") if c in cols), None)
    for c, para in need.items():
        print(f"  {'sí' if c in cols else 'NO':>3}  {c:<14s} ({para})")
    print(f"  {'sí' if tipo else 'NO':>3}  tipo de acción ({tipo or 'ninguna de action_type/type/event_type'})")
    if all(c in cols for c in need) and tipo:
        print("\n  SE PUEDE, con un sustituto declarado: el receptor de un pase sería el")
        print("  player_id de la siguiente acción del mismo equipo en la misma posesión.")
        print("  Sesgos a declarar: los pases fallidos no tienen receptor propio, y un")
        print("  rebote o un despeje se contarían como recepción.")
    else:
        print("\n  NO se puede reconstruir con estas columnas.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "red_pases_diagnostico.json"))
    ap.add_argument("--solo-diagnostico", action="store_true",
                    help="único modo de medición disponible hasta que ADR-62 esté commiteada")
    ap.add_argument("--que-hay", action="store_true",
                    help="inventario: qué archivos y qué columnas hay en data/processed_api_*")
    a = ap.parse_args()
    if not (a.solo_diagnostico or a.que_hay):
        ap.error("elige --que-hay o --solo-diagnostico")
    if a.que_hay:
        return inventario()
    rep = Path(a.reports)
    try:
        h4 = json.loads((rep / "did_h4_v1.json").read_text(encoding="utf-8"))
        indirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
        if len(indirs) != 18:
            raise Aborta(f"se esperaban 18 directorios data/processed_api_*; hay {len(indirs)}")
        filas, sin_col, cols_rec, eras = diagnostico(indirs, h4["pares"])
        if not eras:
            raise Aborta("ningún parquet trae columna de receptor: ADR-62 no es viable con estos datos. "
                         f"Se buscaron {CAND_RECEPTOR}")
        print("=== columna de receptor ===")
        for c, n in cols_rec.items():
            print(f"  «{c}» en {n} de {len(indirs)} clubes")
        if sin_col:
            print(f"  SIN columna de receptor: {', '.join(sin_col)}")
        print("\n=== cobertura por club (pases con receptor / filas con técnico) ===")
        for f in sorted(filas, key=lambda x: x["cobertura"] or 0):
            print(f"  {f['club']:<20s} {f['cobertura']:.1%}  ({f['n_con_receptor']:,} de {f['n_filas']:,})"
                  .replace(",", " "))
        print("\n=== tamaño de cada era ===")
        for k in sorted(eras):
            e = eras[k]
            print(f"  {e['club']:<20s} {e['coach']:<22s} {e['n_jugadores']:3d} jugadores · "
                  f"{e['n_parejas_ij']:4d} parejas · con ≥10 pases: {e['parejas_ij_con_10_o_mas']:4d}")
        print("\n=== parejas de técnicos comparables, por umbral ===")
        rejilla = {}
        for uj in UMBRALES_JUG:
            for up in UMBRALES_PAR:
                ok, det = comparables(eras, h4["pares"], uj, up)
                rejilla[f"{uj}_{up}"] = ok
                print(f"  ≥{uj:3d} pases por jugador y ≥{up} jugadores en común: {ok:2d} parejas")
        salida = {"adr": "ADR-62 (paso 0: diagnóstico, sin estimandos)",
                  "columna_receptor": cols_rec, "sin_columna": sin_col,
                  "cobertura_por_club": filas,
                  "eras": [eras[k] for k in sorted(eras)],
                  "parejas_comparables": rejilla,
                  "nota": "este archivo no contiene ningún estimando ni ninguna relación entre "
                          "variables; solo la forma de los datos, para poder preinscribir ADR-62"}
    except Aborta as e:
        sys.exit(f"ABORTA: {e}")
    except KeyError as e:
        sys.exit(f"ABORTA: falta la clave {e} en did_h4_v1.json")
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nescrito {a.out}")
    print("Este diagnóstico NO mide nada. La medición va después de commitear ADR-62.")


if __name__ == "__main__":
    main()
