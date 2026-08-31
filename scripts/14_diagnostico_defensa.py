#!/usr/bin/env python3
"""
14_diagnostico_defensa.py — Lo que hay que saber ANTES de escribir la Fase 5.

Este script NO estima nada. Contesta cinco preguntas cuya respuesta cambia el
diseño de la cadena conjugada, y que no se pueden adivinar desde la
documentacion:

  1. ¿Existen y con que tipo llegan las columnas defensivas?
  2. `under_pressure`: ¿null, false, o ambos? Define el DENOMINADOR de pi.
  3. ¿Que eventos defensivos hay y con cuanto volumen?
  4. ORIENTACION: ¿StatsBomb normaliza por equipo ejecutante en ESTE volcado?
     Nunca se ha verificado sobre las filas de los rivales: el pipeline solo
     mira `possession_team == club`. Es media base de datos sin auditar.
  5. Cuanta masa se pierde con `min_actions` en la perspectiva defensiva, y si
     la perdida es DIFERENCIAL entre eras (sesgo tipo bug #11).

Todo se escribe a un JSON para que quede trazable.

Uso:
  source .venv/bin/activate
  python scripts/14_diagnostico_defensa.py \
      --events eventos_completos_america.csv --club "América"

  # con eras, para el chequeo de positividad y el 5:
  python scripts/14_diagnostico_defensa.py \
      --events eventos_completos_america.csv --club "América" \
      --eras data/coach_eras.csv --match-dates data/match_dates.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder import ingest
    from dtdecoder.config import Config
    from dtdecoder.eras import load_eras, load_match_dates, match_coach_table
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")


COLS_INTERES = [
    "under_pressure", "counterpress", "duration", "minute", "second", "period",
    "type", "team", "possession_team", "possession", "match_id", "location",
    "player_id", "player", "shot_outcome", "pass_outcome", "play_pattern",
    "interception_outcome", "duel_type", "duel_outcome", "clearance_body_part",
    "ball_receipt_outcome", "obv_total_net", "shot_statsbomb_xg",
]


def seccion(titulo: str) -> None:
    print(f"\n{'=' * 72}\n{titulo}\n{'=' * 72}")


# ---------------------------------------------------------------- 1. esquema
def check_esquema(lf: pl.LazyFrame) -> dict:
    seccion("1. COLUMNAS: existencia y tipo (Null tipado = bug #1 en camino)")
    schema = lf.collect_schema()
    nombres = set(schema.names())
    out = {}
    for c in COLS_INTERES:
        if c not in nombres:
            estado, tipo = "FALTA", None
        else:
            tipo = str(schema[c])
            estado = "NULL-TIPADA" if schema[c] == pl.Null else "ok"
        out[c] = {"estado": estado, "dtype": tipo}
        marca = {"ok": "  ", "FALTA": "!!", "NULL-TIPADA": "!!"}[estado]
        print(f"  {marca} {c:26s} {estado:12s} {tipo or ''}")
    print(f"\n  total de columnas en el volcado: {len(nombres)}")
    out["_n_columnas"] = len(nombres)
    return out


# --------------------------------------------- 2. under_pressure: EL CRITICO
def check_under_pressure(lf: pl.LazyFrame) -> dict:
    seccion("2. under_pressure — define el DENOMINADOR de pi(z)")
    schema = lf.collect_schema()
    if "under_pressure" not in schema.names():
        print("  !! No existe. D1 no es viable con esta columna; habria que")
        print("     derivar la presion de eventos `Pressure` propios.")
        return {"existe": False}

    dist = (
        lf.select(pl.col("under_pressure").cast(pl.Utf8).fill_null("<NULL>"))
        .group_by("under_pressure").len()
        .sort("len", descending=True).collect()
    )
    print(dist)

    d = {r["under_pressure"]: r["len"] for r in dist.to_dicts()}
    total = sum(d.values())
    n_null = d.get("<NULL>", 0)
    n_false = d.get("false", 0) + d.get("False", 0)
    n_true = d.get("true", 0) + d.get("True", 0)

    print(f"\n  total={total:,}  true={n_true:,}  false={n_false:,}  null={n_null:,}")

    if n_false == 0 and n_null > 0:
        veredicto = "BANDERA"
        print("\n  >> Es una BANDERA: StatsBomb pone `true` o NO pone nada.")
        print("     El denominador de pi(z) son TODAS las acciones, y los nulos")
        print("     cuentan como 'sin presion'. Filtrar por is_not_null() daria")
        print("     pi ~ 1 en todas partes. Seria el bug #13.")
        print("     -> usar: pl.col('under_pressure').fill_null(False)")
    elif n_false > 0 and n_null == 0:
        veredicto = "BOOLEANO"
        print("\n  >> Booleano completo. fill_null es inocuo pero se deja igual.")
    else:
        veredicto = "MIXTO"
        print("\n  >> MIXTO: hay true, false Y null. Hay que decidir que significa")
        print("     el null y DOCUMENTARLO en una ADR antes de estimar nada.")

    return {"existe": True, "veredicto": veredicto, "conteos": d,
            "tasa_marginal": round(n_true / max(total, 1), 4)}


# --------------------------------------------- 3. inventario de eventos def.
def check_eventos(lf: pl.LazyFrame) -> dict:
    seccion("3. Inventario de tipos de evento")
    tipos = lf.group_by("type").len().sort("len", descending=True).collect()
    print(tipos.head(35))
    defensivos = ["Pressure", "Duel", "Interception", "Ball Recovery", "Clearance",
                  "Block", "Foul Committed", "50/50", "Miscontrol", "Dispossessed"]
    d = {r["type"]: r["len"] for r in tipos.to_dicts()}
    print("\n  Eventos utiles para D1/D2:")
    for t in defensivos:
        print(f"    {t:20s} {d.get(t, 0):>10,}")
    return {"todos": d, "defensivos": {t: d.get(t, 0) for t in defensivos}}


# ------------------------------------------------------ 4. ORIENTACION (clave)
def check_orientacion(lf: pl.LazyFrame, club: str) -> dict:
    seccion("4. ORIENTACION — ¿normalizada por equipo EJECUTANTE?")
    print("  Hipotesis (04_DATA_CONTRACT §3.3): todo equipo ataca hacia x=120 en")
    print("  sus propios eventos. NUNCA se ha comprobado sobre los rivales.\n")

    ev = (
        lf.filter(pl.col("type").is_in(["Shot", "Goal Keeper"])
                  | (pl.col("play_pattern") == "From Goal Kick"))
        .select(["type", "team", "possession_team", "play_pattern", "start_x", "start_y"])
        .collect()
    )

    out = {}

    # 4a. Remates: si esta normalizado, x alto para TODOS los equipos.
    sh = ev.filter(pl.col("type") == "Shot").with_columns(
        (pl.col("team") == club).alias("es_club"))
    agg = sh.group_by("es_club").agg(
        pl.col("start_x").mean().round(2).alias("x_medio"),
        pl.col("start_x").quantile(0.10).round(2).alias("x_p10"),
        pl.len().alias("n"),
    ).sort("es_club", descending=True)
    print("  4a. Remates — x de origen (esperado: ~100+ en AMBAS filas)")
    print(agg)
    xs = {bool(r["es_club"]): r["x_medio"] for r in agg.to_dicts()}
    out["remates_x_medio"] = xs

    # 4b. Saques de meta: si esta normalizado, x bajo para TODOS.
    gk = (ev.filter((pl.col("play_pattern") == "From Goal Kick")
                    & (pl.col("possession_team") == pl.col("team")))
            .with_columns((pl.col("team") == club).alias("es_club")))
    if gk.height:
        agg2 = gk.group_by("es_club").agg(
            pl.col("start_x").min().round(2).alias("x_min"),
            pl.col("start_x").quantile(0.10).round(2).alias("x_p10"),
            pl.len().alias("n"),
        ).sort("es_club", descending=True)
        print("\n  4b. Posesiones 'From Goal Kick' — x de origen (esperado: ~0-20)")
        print(agg2)
        out["saque_meta_p10"] = {bool(r["es_club"]): r["x_p10"] for r in agg2.to_dicts()}

    ok = all(v is not None and v > 85.0 for v in xs.values()) and len(xs) == 2
    out["normalizada_por_ejecutante"] = bool(ok)
    print(f"\n  >> VEREDICTO: {'NORMALIZADA' if ok else 'NO CONCLUYENTE — REVISAR A MANO'}")
    if ok:
        print("     La cadena conjugada se estima en el marco NATIVO del rival.")
        print("     El espejo se aplica solo al presentar, con StateSpace.mirror_zone.")
    else:
        print("     !! Si NO esta normalizada, la reflexion (120-x, 80-y) es")
        print("        INCORRECTA y hay que orientar por partido. Parar aqui.")
    return out


# ------------------------------- 5. min_actions: perdida y si es diferencial
def check_min_actions(lf: pl.LazyFrame, cfg: Config, club: str,
                      mc: pl.DataFrame | None) -> dict:
    seccion("5. min_actions — ¿cuanta masa DEFENSIVA se descarta, y es diferencial?")
    min_actions = int(cfg["possession"]["min_actions"])
    moving = cfg["possession"]["moving_types"]
    print(f"  min_actions = {min_actions}, moving_types = {moving}\n")
    print("  Una posesion rival de UNA accion que termina en absorcion (remate,")
    print("  pase perdido) NO recibe absorcion terminal y queda con 1 fila, asi")
    print("  que `_filter_short` la descarta. Es justo el producto de una presion")
    print("  exitosa: el filtro selecciona por la variable que vas a medir.\n")

    acc = (
        lf.filter((pl.col("possession_team") == pl.col("team"))
                  & pl.col("type").is_in(moving)
                  & pl.col("start_x").is_not_null())
        .select(["match_id", "possession", "possession_team", "type",
                 "shot_outcome", "pass_outcome"])
        .collect()
    )
    riv = acc.filter(pl.col("possession_team") != club)

    loss_out = cfg["possession"]["pass_loss_outcomes"]
    riv = riv.with_columns(
        ((pl.col("type") == "Shot")
         | ((pl.col("type") == "Pass") & pl.col("pass_outcome").is_in(loss_out))
         ).alias("_absorbe")
    )
    porposs = riv.group_by(["match_id", "possession"]).agg(
        pl.len().alias("n_acc"),
        pl.col("_absorbe").last().alias("ultima_absorbe"),
    )
    porposs = porposs.with_columns(
        (pl.col("n_acc") + (~pl.col("ultima_absorbe")).cast(pl.Int32)).alias("n_filas")
    ).with_columns((pl.col("n_filas") < min_actions).alias("descartada"))

    n_tot = porposs.height
    n_desc = int(porposs["descartada"].sum())
    print(f"  posesiones rivales totales : {n_tot:,}")
    print(f"  descartadas por el filtro  : {n_desc:,}  ({n_desc / max(n_tot,1):.2%})")
    out = {"min_actions": min_actions, "n_posesiones_rival": n_tot,
           "n_descartadas": n_desc, "frac_descartada": round(n_desc / max(n_tot, 1), 4)}

    if mc is not None:
        pp = porposs.join(mc.select("match_id", "coach"), on="match_id", how="inner")
        por_era = (pp.filter(pl.col("coach").is_not_null())
                     .group_by("coach")
                     .agg(pl.len().alias("n"),
                          pl.col("descartada").mean().round(4).alias("frac_descartada"))
                     .sort("frac_descartada", descending=True))
        print("\n  Por era enfrentada (ESTO es lo que decide si el sesgo es diferencial):")
        print(por_era)
        fr = por_era["frac_descartada"].to_numpy()
        if len(fr) > 1:
            rango = float(fr.max() - fr.min())
            out["rango_entre_eras"] = round(rango, 4)
            out["por_era"] = por_era.to_dicts()
            print(f"\n  rango entre eras: {rango:.4f}")
            if rango > 0.02:
                print("  >> DIFERENCIAL. El filtro se come mas posesiones de una era")
                print("     que de otra, y son justo las posesiones cortas. Con")
                print("     min_actions=2 estarias midiendo el filtro, no la presion.")
                print("     -> usar min_actions=1 en la perspectiva defensiva.")
            else:
                print("  >> Aproximadamente uniforme. Aun asi conviene min_actions=1")
                print("     y reportar la sensibilidad.")
    return out


# ------------------------------------------- 6. positividad para estandarizar
def check_positividad(lf: pl.LazyFrame, club: str, mc: pl.DataFrame | None) -> dict:
    seccion("6. POSITIVIDAD — soporte comun de rivales entre eras")
    if mc is None:
        print("  (salta: pasa --eras y --match-dates)")
        return {}
    print("  La estandarizacion directa solo es valida si cada rival con peso")
    print("  w_o > 0 aparece en LAS DOS eras que comparas. Si no, el estimador")
    print("  promedia sobre conjuntos distintos y falla en silencio.\n")

    pares = (
        lf.filter(pl.col("possession_team") != pl.col("team"))  # placeholder no usado
        .select("match_id").unique().collect()
    )
    del pares

    rivales = (
        lf.select(["match_id", "team"]).unique()
        .filter(pl.col("team") != club)
        .collect()
        .join(mc.select("match_id", "coach"), on="match_id", how="inner")
        .filter(pl.col("coach").is_not_null())
    )
    tabla = (rivales.group_by(["coach", "team"]).agg(pl.len().alias("partidos"))
                    .pivot(on="coach", index="team", values="partidos")
                    .fill_null(0).sort("team"))
    print(tabla)

    eras = [c for c in tabla.columns if c != "team"]
    out = {"eras": eras, "n_rivales": tabla.height, "soporte_comun": {}}
    for a in range(len(eras)):
        for b in range(a + 1, len(eras)):
            ea, eb = eras[a], eras[b]
            comun = tabla.filter((pl.col(ea) > 0) & (pl.col(eb) > 0))
            n_a = int(tabla[ea].sum())
            cubierto = int(comun[ea].sum()) / max(n_a, 1)
            out["soporte_comun"][f"{ea} vs {eb}"] = {
                "rivales_comunes": comun.height,
                "frac_partidos_de_a_cubiertos": round(cubierto, 3),
            }
    print("\n  Soporte comun por par de eras:")
    for k, v in out["soporte_comun"].items():
        flag = "" if v["frac_partidos_de_a_cubiertos"] > 0.85 else "   << REVISAR"
        print(f"    {k:<45s} {v['rivales_comunes']:>3} rivales, "
              f"{v['frac_partidos_de_a_cubiertos']:.1%} cubierto{flag}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", required=True)
    ap.add_argument("--club", required=True)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--eras", default=None)
    ap.add_argument("--match-dates", default=None)
    ap.add_argument("--out", default="reports/diagnostico_defensa.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    p = cfg["pitch"]
    space = StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                       phases=tuple(cfg["phase_order"]))
    print(f"malla {space.nx}x{space.ny}  ({space.n_transient} estados transitorios)")

    lf_raw = ingest.scan_events(args.events)
    lf = ingest.load(args.events)   # normalizado: trae start_x / start_y

    mc = None
    if args.eras and args.match_dates:
        mc = match_coach_table(load_match_dates(args.match_dates),
                               load_eras(args.eras), args.club)

    res = {
        "club": args.club,
        "events": args.events,
        "esquema": check_esquema(lf_raw),
        "under_pressure": check_under_pressure(lf_raw),
        "eventos": check_eventos(lf_raw),
        "orientacion": check_orientacion(lf, args.club),
        "min_actions": check_min_actions(lf, cfg, args.club, mc),
        "positividad": check_positividad(lf, args.club, mc),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    print(f"\nescrito: {out}")

    seccion("QUE HACER SEGUN EL RESULTADO")
    print("  §2 BANDERA    -> fill_null(False) al construir pi. Documentar en ADR.")
    print("  §4 NO NORMAL. -> PARAR. La reflexion seria incorrecta.")
    print("  §5 rango>0.02 -> min_actions=1 en defensa, obligatorio.")
    print("  §6 <85%       -> restringir pesos al soporte comun y reportarlo.")


if __name__ == "__main__":
    main()
