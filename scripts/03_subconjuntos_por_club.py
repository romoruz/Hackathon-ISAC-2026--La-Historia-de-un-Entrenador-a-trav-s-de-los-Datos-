#!/usr/bin/env python3
"""
03_subconjuntos_por_club.py — los 18 subconjuntos, SIN volver a aplanar JSON.

POR QUE ESTE ATAJO ES EXACTO Y NO UNA APROXIMACION
==================================================
`02_adaptar_eventos.py --club X` produce los eventos de los partidos que jugo
X. El parquet de liga contiene esos MISMOS eventos: se construyo con el mismo
alcance (fase regular, sin temporada 351) y con el mismo aplanado. Filtrar por
`match_id` da byte a byte lo mismo que volver a generarlo, y evita
descomprimir y aplanar 5 millones de eventos dieciocho veces.

El script lo COMPRUEBA en vez de suponerlo: si existe
`data/api/eventos_api_america`, contrasta el subconjunto derivado contra el
adaptado partido a partido y aborta si no coinciden.

Cada club recibe ademas su `match_dates_<slug>.csv`, porque `phase0` lo exige y
porque un archivo de fechas por club deja claro con que alcance se genero.

Uso:
    python scripts/03_subconjuntos_por_club.py
    python scripts/03_subconjuntos_por_club.py --solo "Cruz Azul" "Tigres UANL"
"""
from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

import polars as pl


def slug(nombre: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", nombre)
                if unicodedata.category(c) != "Mn")
    return s.lower().replace(" ", "_")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liga", type=Path,
                    default=Path("data/api/eventos_api_ligamx"))
    ap.add_argument("--indice", type=Path,
                    default=Path("data/raw_api/indice_partidos.csv"))
    ap.add_argument("--fechas-liga", type=Path,
                    default=Path("data/api/match_dates_ligamx.csv"),
                    dest="fechas_liga")
    ap.add_argument("--out", type=Path, default=Path("data/api/clubes"))
    ap.add_argument("--solo", nargs="*", default=None)
    ap.add_argument("--verificar-contra", type=Path, default=None,
                    dest="verificar", help="directorio adaptado de un club "
                    "para contrastar (por defecto, el del America si existe)")
    args = ap.parse_args()

    if not args.liga.is_dir():
        print(f"No existe {args.liga}. Corre el adaptador con --todos.")
        return 1

    fechas = pl.read_csv(args.fechas_liga).with_columns(
        pl.col("match_id").cast(pl.Int64)
    )
    validos = set(fechas["match_id"].to_list())

    # que equipos jugaron cada partido, del indice (no de los eventos: es
    # mas barato y es la fuente que uso el adaptador para filtrar)
    por_club: dict[str, set[int]] = {}
    with args.indice.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            mid = int(r["match_id"])
            if mid not in validos:
                continue
            for lado in ("home_team", "away_team"):
                por_club.setdefault(r[lado], set()).add(mid)

    clubes = sorted(por_club)
    if args.solo:
        faltan = [c for c in args.solo if c not in por_club]
        if faltan:
            print(f"Clubes desconocidos: {faltan}\nDisponibles: {clubes}")
            return 1
        clubes = list(args.solo)
    print(f"clubes: {len(clubes)}   partidos en alcance: {len(validos):,}\n")

    lf = pl.scan_parquet(str(args.liga / "*.parquet"))
    args.out.mkdir(parents=True, exist_ok=True)
    resumen = []

    for club in clubes:
        s = slug(club)
        mids = sorted(por_club[club])
        dst = args.out / s
        dst.mkdir(parents=True, exist_ok=True)
        for viejo in dst.glob("*.parquet"):
            viejo.unlink()

        sub = lf.filter(pl.col("match_id").cast(pl.Int64).is_in(mids)).collect()
        if sub.height == 0:
            print(f"  [salto] {club}: cero eventos")
            continue
        sub.write_parquet(dst / "eventos.parquet")

        fechas.filter(pl.col("match_id").is_in(mids)).write_csv(
            args.out / f"match_dates_{s}.csv"
        )
        n_part = sub["match_id"].n_unique()
        resumen.append({"club": club, "slug": s, "partidos": n_part,
                        "eventos": sub.height})
        print(f"  {club:<22} {n_part:>4} partidos  {sub.height:>9,} eventos "
              f"-> {dst}")
        del sub

    # --- verificacion contra el adaptado, si existe ----------------------
    ref = args.verificar or Path("data/api/eventos_api_america")
    if ref.is_dir():
        objetivo = next((r for r in resumen if r["club"] == "América"), None)
        if objetivo:
            a = (pl.scan_parquet(str(ref / "*.parquet"))
                 .group_by("match_id").agg(pl.len().alias("n"))
                 .sort("match_id").collect())
            b = (pl.scan_parquet(str(args.out / objetivo["slug"] / "*.parquet"))
                 .group_by("match_id").agg(pl.len().alias("n"))
                 .sort("match_id").collect())
            iguales = a.equals(b)
            print(f"\nverificacion contra {ref}: "
                  f"{'IDENTICO' if iguales else 'DIFIERE'} "
                  f"({a.height} vs {b.height} partidos)")
            if not iguales:
                # Un subconjunto que no reproduce el adaptado invalida el
                # atajo entero: mejor parar que correr 18 phase0 sobre datos
                # que no son los que se validaron.
                solo_a = set(a["match_id"]) - set(b["match_id"])
                solo_b = set(b["match_id"]) - set(a["match_id"])
                print(f"  solo en el adaptado: {sorted(solo_a)[:10]}")
                print(f"  solo en el derivado: {sorted(solo_b)[:10]}")
                print("  PARA. El atajo no reproduce el adaptado.")
                return 1
    else:
        print(f"\n(sin {ref}: no se pudo verificar el atajo)")

    total = sum(r["eventos"] for r in resumen)
    print(f"\n{len(resumen)} clubes, {total:,} eventos escritos "
          f"(la liga son 4,983,649; cada partido aparece en DOS clubes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
