#!/usr/bin/env python3
"""
24_diagnostico_freeze_frame.py — auditar el `shot_freeze_frame` ANTES de estimar.

POR QUÉ ESTE SCRIPT VA PRIMERO
------------------------------
El bug #13 se EVITÓ porque `14_diagnostico_defensa.py` inspeccionó el esquema de
`under_pressure` antes de escribir una línea de estimación. Sin eso, un filtro
por `is_not_null()` habría dado pi ~ 1 en todas partes sin lanzar nada.

Este script es el equivalente para el freeze frame. Contesta cinco preguntas que
si se responden mal producen números plausibles y equivocados:

  1. ¿En qué formato viene? (repr de Python, NO JSON: `json.loads` falla)
  2. ¿Cuántos remates lo traen, por era?
  3. ¿Cuántos tienen al PORTERO fuera de la foto?   <- decide el fillna
  4. ¿Cuántos están en x > 120?                     <- decide el recorte
  5. ¿Cuántos defensores de campo hay por foto?     <- ¿es una foto usable?

NO ESTIMA NADA. Solo cuenta y decide reglas de negocio.

Uso:
    python scripts/24_diagnostico_freeze_frame.py \\
        --eventos eventos_completos_america.csv \\
        --club "América" \\
        --parquet data/processed/transitions.parquet
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter

import numpy as np
import polars as pl

X_LINEA = 120.0


def parse_ff(s):
    """El freeze frame es un REPR DE PYTHON, no JSON.

    En el volcado viene como `[{'location': [118.3, 40.2], 'player': {...}}]`,
    con comillas SIMPLES. `json.loads` lanza. Es la trampa de
    `04_DATA_CONTRACT.md` §3.1 (`location` serializado) con otra cara.

    Y el peligro real no es que falle: es que alguien lo envuelva en un
    try/except que devuelva None y se quede sin la mitad de los remates SIN
    NINGÚN ERROR. Por eso aquí se cuentan los fallos y se reportan.
    """
    if s is None:
        return None
    if isinstance(s, (list, tuple)):
        return list(s)
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        try:
            return json.loads(s)
        except Exception:
            return "ERROR"


def parse_xy(s):
    if s is None:
        return (np.nan, np.nan)
    if isinstance(s, (list, tuple)):
        v = s
    else:
        try:
            v = ast.literal_eval(s)
        except Exception:
            return (np.nan, np.nan)
    try:
        return float(v[0]), float(v[1])
    except Exception:
        return (np.nan, np.nan)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--eventos", required=True)
    ap.add_argument("--club", required=True, help='valor de la columna `team`, SIN "Club"')
    ap.add_argument("--parquet", help="para desglosar por era")
    ap.add_argument("--umbral-portero", type=float, default=0.02,
                    help="fracción de remates sin portero por encima de la cual PARA")
    a = ap.parse_args()

    # `infer_schema_length=None` obligatorio: es el bug #1. Con el default de
    # 100 filas, las columnas raras quedan tipadas Null y los filtros devuelven
    # vacío en silencio.
    lf = pl.scan_csv(a.eventos, infer_schema_length=None)
    cols = lf.collect_schema().names()
    for c in ("shot_freeze_frame", "location", "type", "team", "match_id"):
        if c not in cols:
            sys.exit(f"falta la columna requerida '{c}'")

    d = (lf.filter((pl.col("type") == "Shot") & (pl.col("team") == a.club))
           .select(["match_id", "location", "shot_freeze_frame", "shot_outcome"])
           .collect())

    print("=" * 70)
    print(f"1. COBERTURA — remates de {a.club}")
    print("=" * 70)
    n = d.height
    con_ff = d.filter(pl.col("shot_freeze_frame").is_not_null()).height
    print(f"  remates            {n:>7,}")
    print(f"  con freeze frame   {con_ff:>7,}  ({con_ff/n:.1%})")
    print(f"  SIN freeze frame   {n-con_ff:>7,}")
    if n - con_ff:
        faltan = d.filter(pl.col("shot_freeze_frame").is_null())
        print("  desenlace de los que NO lo traen (¿es sistemático?):")
        for row in faltan.group_by("shot_outcome").len().sort("len", descending=True).iter_rows():
            print(f"      {str(row[0]):22} {row[1]:>5}")

    ff = d.filter(pl.col("shot_freeze_frame").is_not_null())

    print("\n" + "=" * 70)
    print("2. FORMATO Y PARSEO")
    print("=" * 70)
    fallos = 0
    sin_portero = 0
    n_def, n_att = [], []
    x_fuera = 0
    posiciones = Counter()

    for loc, fr in zip(ff["location"].to_list(), ff["shot_freeze_frame"].to_list()):
        p = parse_ff(fr)
        if p == "ERROR" or p is None:
            fallos += 1
            continue
        sx, _ = parse_xy(loc)
        if np.isfinite(sx) and sx > X_LINEA:
            x_fuera += 1
        rivales = [j for j in p if not j.get("teammate", False)]
        porteros = [j for j in rivales
                    if (j.get("position") or {}).get("name") == "Goalkeeper"]
        campo = [j for j in rivales
                 if (j.get("position") or {}).get("name") != "Goalkeeper"]
        if not porteros:
            sin_portero += 1
        n_def.append(len(campo))
        n_att.append(sum(1 for j in p if j.get("teammate", False)))
        for j in rivales:
            posiciones[(j.get("position") or {}).get("name")] += 1

    print(f"  fallos de parseo   {fallos:>7,}   <- si >0, PARAR")
    print("  formato: repr de Python (comillas simples). `json.loads` FALLA;")
    print("           hay que usar `ast.literal_eval`.")
    if fallos:
        sys.exit("\nHay fallos de parseo. No sigas hasta entender por qué.")

    print("\n" + "=" * 70)
    print("3. PORTERO EN LA FOTO  — decide la regla del fillna")
    print("=" * 70)
    frac = sin_portero / max(1, len(n_def))
    print(f"  fotos SIN portero  {sin_portero:>7,}  ({frac:.2%})")
    print("\n  El proyecto de córners imputaba `gk_depth`/`gk_offset` con la")
    print("  MEDIANA cuando faltaba el portero. Eso mete remates promedio")
    print("  disfrazados de dato real.")
    if frac <= a.umbral_portero:
        print(f"\n  REGLA: son marginales (<={a.umbral_portero:.0%}). Se DESCARTAN esos")
        print("         remates para las features de portero y se declara cuántos.")
    else:
        print(f"\n  ATENCIÓN: superan el {a.umbral_portero:.0%}. NO imputes por defecto.")
        print("         Define la regla de negocio y documéntala en una ADR antes")
        print("         de seguir: puede haber un patrón (¿remates lejanos? ¿cámara?).")

    print("\n" + "=" * 70)
    print("4. REMATES MÁS ALLÁ DE LA LÍNEA — decide el recorte")
    print("=" * 70)
    print(f"  con x > {X_LINEA}      {x_fuera:>7,}  ({x_fuera/max(1,len(n_def)):.2%})")
    print("  `04_DATA_CONTRACT.md` §3.2: no es un error de los datos, es el")
    print("  balón cruzando la línea. Rompe `arctan2` si no se recorta.")

    print("\n" + "=" * 70)
    print("5. DENSIDAD DE LA FOTO — ¿es usable?")
    print("=" * 70)
    nd = np.array(n_def)
    print(f"  defensores de campo por foto: mediana {np.median(nd):.0f}  "
          f"p10 {np.percentile(nd,10):.0f}  p90 {np.percentile(nd,90):.0f}")
    print(f"  fotos con 0 defensores de campo: {(nd==0).sum():,}  "
          f"({(nd==0).mean():.2%})  <- goal_open = 1 por construcción")
    print(f"  atacantes por foto: mediana {np.median(n_att):.0f}")
    print("\n  posiciones rivales más vistas:")
    for k, v in posiciones.most_common(6):
        print(f"      {str(k):22} {v:>7,}")

    if a.parquet:
        print("\n" + "=" * 70)
        print("6. DESGLOSE POR ERA")
        print("=" * 70)
        t = pl.read_parquet(a.parquet).select(["match_id", "coach"]).drop_nulls().unique()
        por = (ff.join(t, on="match_id", how="left")
                 .group_by("coach").len().sort("len", descending=True))
        print(por)
        print("\n  Recuerda: para comparar DOS eras basta el bootstrap por posesión.")
        print("  Para estimar tau^2 entre eras hacen falta >=8 unidades (ADR-49).")

    print("\n" + "=" * 70)
    print("REGLAS QUE ESTE DIAGNÓSTICO DEJA FIJADAS")
    print("=" * 70)
    print("  · parseo con ast.literal_eval, NUNCA json.loads")
    print("  · recortar x del tirador a 119.9 y CONTAR cuántas veces")
    print("  · portero ausente -> descartar o regla explícita, jamás fillna(median)")
    print("  · el portero NO entra a goal_open (tapa por definición); va en")
    print("    gk_depth / gk_offset")
    print("  · unidad de remuestreo = poss_uid (ADR-07), no el remate")


if __name__ == "__main__":
    main()
