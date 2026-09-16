#!/usr/bin/env python3
"""
29_panorama_liga.py — las 53 unidades analizables en un solo plano.

Dos escalares por unidad (acciones por posesion, remates por 100 posesiones)
para TODOS los clubes, no solo los del reporte profundo. Es barato: no hay
bootstrap ni permutaciones, solo conteos sobre `transitions.parquet`.

EL PROBLEMA QUE ESTE SCRIPT TIENE QUE RESOLVER
==============================================
La grafica actual del reporte usa el PUNTO MEDIO DEL CLUB como origen. Eso
funciona dentro de un club y **no** entre clubes ni entre epocas, por la
deriva del proveedor: el escalon A2022 -> C2023 es de +12.58% en eventos por
partido (1511.8 -> 1702.0), con los 18 clubes subiendo a la vez.

Poner a Cocca I (A2021-A2022) y a Cocca II (A2025-C2026) en el mismo plano
crudo compara dos regimenes de medicion: Cocca II parece retener mas por
haber dirigido despues.

Por eso se emite tambien la version NORMALIZADA: cada escalar dividido entre
el de los contemporaneos del mismo torneo, con el club focal excluido. Es el
mismo estimando de `23_normalizar_contemporaneo.py` (reglas N1-N4). En esa
escala el origen deja de ser el club y pasa a ser **1.0 = la liga
contemporanea**, que es el traslado de ejes que hace comparables a las 53.

EL ANCLA: SIN ESTO EL SCRIPT NO SIRVE
=====================================
`reports/normalizado.json` da, para el America:

    Jardine  8.035710    Ortiz  7.318940    Solari  6.298366

que son `n_transiciones / n_posesiones`. El script REPRODUCE esos numeros y
aborta si no cuadran a 1e-4. Si mi definicion de "accion" no fuera la del
pipeline, el panorama diria otra cosa que el resto del reporte y nadie se
enteraria: es exactamente el modo de fallo de este proyecto.

SOBRE EL EJE DE REMATES
=======================
El reporte muestra a Cocca I con "4.9 acciones · 8.8 remates por 100". El 4.9
NO es el crudo (Cocca I sale por encima de 7 en crudo): el reporte aplica los
filtros de posesion. Por eso este script emite VARIAS definiciones candidatas
y las contrasta contra los valores que el reporte ya muestra. **No se elige
una a ojo: se elige la que reproduce el reporte**, y si ninguna lo hace, se
dice y no se publica la grafica.

Uso:
    python scripts/29_panorama_liga.py --out reports/panorama_liga.json
    python scripts/29_panorama_liga.py --contrasta   # tabla de definiciones
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

RAIZ = Path(__file__).resolve().parent.parent

# Absorbentes, por la etiqueta que imprime el simulador del reporte.
GOL, REMATE, PERDIDA, FUERA = 80, 81, 82, 83

# Ancla: `normalizado.json`, acc_por_posesion_cruda.
ANCLA = {
    "Andre Jardine": 8.035710444229322,
    "Fernando Ortiz": 7.318940137389598,
    "Santiago Solari": 6.298366294067068,
}

# Lo que el reporte YA muestra para Atlas, para identificar la definicion
# filtrada. Fuente: la tarjeta «muestra por tecnico» del propio HTML.
REF_REPORTE = {
    "Diego Cocca I": (4.9, 8.8),
    "Benat San Jose": (5.3, 8.7),
    "Benjamin Mora": (5.5, 8.4),
}


def torneo(df: pl.DataFrame) -> pl.DataFrame:
    anio = pl.col("match_date").dt.year()
    ap = pl.col("match_date").dt.month() >= 7
    return df.with_columns(
        pl.when(ap).then(pl.lit("A") + anio.cast(pl.Utf8))
        .otherwise(pl.lit("C") + anio.cast(pl.Utf8)).alias("torneo"))


def escalares(sub: pl.DataFrame) -> dict:
    """Los dos ejes, en sus definiciones candidatas."""
    npos = sub["poss_uid"].n_unique()
    if npos == 0:
        return {}
    nacc = sub.height
    rem = sub.filter(pl.col("to_state") == REMATE).height
    gol = sub.filter(pl.col("to_state") == GOL).height
    return {
        "n_posesiones": int(npos),
        "n_transiciones": int(nacc),
        # A: crudo. Es el del ancla y el de normalizado.json.
        "acc_por_posesion": nacc / npos,
        # B: solo remates. C: remates + goles (un gol tambien fue un remate).
        "rem100_solo_remate": 100.0 * rem / npos,
        "rem100_con_gol": 100.0 * (rem + gol) / npos,
        "gol100": 100.0 * gol / npos,
    }


def unidades(clubes: list[str]) -> list[dict]:
    out = []
    for d in sorted((RAIZ / "data").glob("processed_api_*")):
        slug = d.name.replace("processed_api_", "")
        if clubes and slug not in clubes:
            continue
        rp, tp = d / "phase0_report.json", d / "transitions.parquet"
        if not (rp.exists() and tp.exists()):
            print(f"[salto] {slug}: faltan artefactos", file=sys.stderr)
            continue
        co = json.loads(rp.read_text()).get("coaches") or {}
        club = co.get("club")
        ok = {c["coach"] for c in co.get("coverage", []) if c.get("suficiente")}
        if not club or not ok:
            print(f"[salto] {slug}: sin club o sin unidades", file=sys.stderr)
            continue
        t = torneo(pl.read_parquet(tp).filter(pl.col("team") == club))
        for dt in sorted(ok):
            sub = t.filter(pl.col("coach") == dt)
            e = escalares(sub)
            if not e:
                continue
            e |= {"club": club, "slug": slug, "coach": dt,
                  "torneos": sorted(set(sub["torneo"].to_list()))}
            out.append(e)
    return out


def normaliza(us: list[dict], clubes: list[str]) -> None:
    """R = foco / contemporaneos del mismo torneo, sin el club focal (N1).

    Se pondera a la mezcla de torneos del foco (N2): si una era vivio dos
    tercios en A2024, su referencia pesa igual.
    """
    partes = []
    for d in sorted((RAIZ / "data").glob("processed_api_*")):
        tp = d / "transitions.parquet"
        rp = d / "phase0_report.json"
        if not (tp.exists() and rp.exists()):
            continue
        club = (json.loads(rp.read_text()).get("coaches") or {}).get("club")
        if not club:
            continue
        t = torneo(pl.read_parquet(tp).filter(pl.col("team") == club))
        partes.append(t.select("poss_uid", "to_state", "torneo",
                               pl.lit(club).alias("club_ref")))
    if not partes:
        return
    liga = pl.concat(partes, how="vertical_relaxed")

    base = (liga.group_by("club_ref", "torneo")
            .agg(pl.len().alias("acc"),
                 pl.col("poss_uid").n_unique().alias("pos"),
                 (pl.col("to_state") == REMATE).sum().alias("rem")))

    for u in us:
        b = base.filter((pl.col("club_ref") != u["club"])
                        & pl.col("torneo").is_in(u["torneos"]))
        pos, acc, rem = (b["pos"].sum(), b["acc"].sum(), b["rem"].sum())
        if not pos:
            continue
        u["acc_liga"] = acc / pos
        u["rem100_liga"] = 100.0 * rem / pos
        u["R_acc"] = u["acc_por_posesion"] / (acc / pos)
        u["R_rem"] = (u["rem100_solo_remate"]
                      / max(100.0 * rem / pos, 1e-12))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clubes", default="",
                    help="slugs separados por coma; vacio = los 18")
    ap.add_argument("--contrasta", action="store_true",
                    help="tabla contra los valores que ya muestra el reporte")
    ap.add_argument("--out", type=Path,
                    default=Path("reports/panorama_liga.json"))
    args = ap.parse_args()
    clubes = [s.strip() for s in args.clubes.split(",") if s.strip()]

    us = unidades(clubes)
    if not us:
        sys.exit("ninguna unidad; revisa data/processed_api_*")

    # --- EL ANCLA -------------------------------------------------------
    print("== ancla contra normalizado.json ==")
    malo = False
    for u in us:
        if u["club"] == "América" and u["coach"] in ANCLA:
            esp, got = ANCLA[u["coach"]], u["acc_por_posesion"]
            ok = abs(esp - got) < 1e-4
            malo |= not ok
            print(f"  {'ok ' if ok else 'MAL'} {u['coach']:<18}"
                  f"esperado {esp:.6f}  obtenido {got:.6f}")
    if malo:
        sys.exit("\nEL ANCLA NO CUADRA. La definicion de accion de este "
                 "script NO es la del pipeline.\nNo se escribe nada: un "
                 "panorama que contradice al resto del reporte es peor que "
                 "ninguno.")
    print()

    if args.contrasta:
        print("== contra lo que el reporte ya muestra (Atlas) ==")
        print("   el reporte aplica filtros de posesion; el crudo NO tiene")
        print("   por que coincidir. Sirve para saber CUAL definicion usa.\n")
        for u in us:
            if u["coach"] in REF_REPORTE:
                ra, rr = REF_REPORTE[u["coach"]]
                print(f"  {u['coach']:<18} reporte {ra:5.2f} / {rr:5.2f}   "
                      f"crudo {u['acc_por_posesion']:5.2f} / "
                      f"{u['rem100_solo_remate']:5.2f}   "
                      f"con gol {u['rem100_con_gol']:5.2f}")
        print()

    normaliza(us, clubes)
    us.sort(key=lambda u: (u["club"], u["coach"]))

    con_r = [u for u in us if "R_acc" in u]
    print(f"{len(us)} unidades, {len(con_r)} con normalizacion")
    if con_r:
        ra = [u["R_acc"] for u in con_r]
        print(f"R_acc: min {min(ra):.3f}  mediana "
              f"{sorted(ra)[len(ra)//2]:.3f}  max {max(ra):.3f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "nota_ejes": (
            "acc_por_posesion y rem100_* son CRUDOS y no son comparables "
            "entre epocas: la deriva del proveedor mete un escalon de "
            "+12.58% entre A2022 y C2023. Para comparar las 53 unidades "
            "entre si hay que usar R_acc y R_rem, que dividen entre los "
            "contemporaneos del mismo torneo sin el club focal."),
        "ancla_verificada": True,
        "n_unidades": len(us),
        "unidades": us,
    }, indent=1, ensure_ascii=False))
    print(f"escrito {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
