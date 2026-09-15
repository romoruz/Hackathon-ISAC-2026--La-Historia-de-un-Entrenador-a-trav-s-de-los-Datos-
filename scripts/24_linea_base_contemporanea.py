#!/usr/bin/env python3
"""
24_linea_base_contemporanea.py — la referencia que cancela la deriva.

EL PROBLEMA
===========
Hudl StatsBomb cambio su anotacion durante la ventana, y de dos formas
distintas (medido en `22_deriva_proveedor.py`):

  * un ESCALON en A2022 -> C2023: eventos crudos de ~1,512 a ~1,702 por
    partido (+12.6%), con 17 de 18 clubes moviendose igual. Vive sobre todo
    en el NUMERO de posesiones anotadas (196 -> 213), no en su longitud.
  * una TENDENCIA suave en acciones por posesion tras los filtros:
    6.04 -> 6.97 a lo largo de la ventana (+11%), sin escalon.

Y el crecimiento NO es uniforme por tipo: Pressure +9.4%, Carry +9.0%,
Pass +6.4%, mientras Duel -14.4% y Dribble -10.0%. `Carry` y `Pass` son dos de
los tres `moving_types`, asi que la deriva entra directamente en las
transiciones del modelo. Que Carry crezca mas que Pass cambia la MEZCLA de
acciones, y mas acarreos significa mas auto-transiciones i->i, que es lo que
`04_DATA_CONTRACT` §3.5 documenta como inflador de N.

Las eras estan perfectamente confundidas con el tiempo, asi que esto no es un
detalle: es el confusor principal del contraste entre eras.

LA CORRECCION
=============
La linea base de cada unidad se construye con los partidos de los MISMOS
torneos que el foco, excluyendo su club. Asi la deriva es un efecto comun a
foco y base, y se cancela en el contraste. Es el argumento de ADR-21 --una
mala especificacion COMPARTIDA se cancela-- aplicado al tiempo en vez de al
modelo.

REGLAS PREINSCRITAS (2026-09-14, antes de correr esto)
======================================================

B1. La linea base excluye al club focal. Sin eso es fuga de prior (ADR-06).

B2. La linea base se pondera a la MEZCLA DE TORNEOS del foco. Una era a
    caballo del escalon (Ortiz, mar 2022 - jun 2023) debe compararse contra la
    mezcla que le toco, no contra un promedio que no vivio.

B3. TENDENCIAS PARALELAS, VERIFICADO NO SUPUESTO. Que la deriva se cancele
    exige que afecte igual al foco y a su base. Se comprueba sobre la razon
    Carry/Pass --la mezcla que cambia la topologia de la matriz-- torneo a
    torneo: se mide la diferencia foco-base por torneo y se contrasta su
    PENDIENTE contra cero. Si la pendiente difiere de cero mas alla del ruido,
    las tendencias NO son paralelas y queda residuo. Se reporta; no se
    esconde.

B4. Esta verificacion no tiene un periodo pre-tratamiento limpio: la deriva es
    continua, asi que no existe un tramo sin ella contra el que calibrar. Por
    eso el contraste de B3 es DEBIL por construccion y se declara asi. Detecta
    divergencia grande; no certifica paralelismo.

Uso:
    python scripts/24_linea_base_contemporanea.py \\
        --indirs data/processed_api_* \\
        --prior-from data/prior_liga \\
        --out reports/linea_base_contemporanea.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from dtdecoder.cli import _read_trans


def torneo_cols() -> list[pl.Expr]:
    anio = pl.col("match_date").dt.year()
    ap = pl.col("match_date").dt.month() >= 7
    return [
        pl.when(ap).then(pl.lit("A") + anio.cast(pl.Utf8))
        .otherwise(pl.lit("C") + anio.cast(pl.Utf8)).alias("torneo"),
        (anio * 2 + ap.cast(pl.Int32)).alias("torneo_orden"),
    ]


def carga_liga(prior_from: Path) -> pl.DataFrame:
    liga = _read_trans(str(prior_from), permitir_prior=True)
    faltan = [c for c in ("match_date", "team", "action_type")
              if c not in liga.columns]
    if faltan:
        raise SystemExit(
            f"El artefacto de prior no trae {faltan}. Vuelve a correr "
            "`dtdecoder prior`."
        )
    return liga.with_columns(torneo_cols())


def base_contemporanea(
    liga: pl.DataFrame, club: str, torneos: list[str]
) -> pl.DataFrame:
    """B1 + B2: liga de los mismos torneos, sin el club focal."""
    return liga.filter(
        (pl.col("team") != club) & pl.col("torneo").is_in(torneos)
    )


def razon_carry_pass(df: pl.DataFrame) -> pl.DataFrame:
    """Carry/Pass por torneo. Es la mezcla que mueve la diagonal de P."""
    return (
        df.group_by(["torneo", "torneo_orden"])
        .agg(
            (pl.col("action_type") == "Carry").sum().alias("carry"),
            (pl.col("action_type") == "Pass").sum().alias("pass_"),
        )
        .with_columns(
            (pl.col("carry") / pl.max_horizontal(pl.col("pass_"), pl.lit(1)))
            .alias("razon")
        )
        .sort("torneo_orden")
    )


def tendencias_paralelas(
    foco: pl.DataFrame, base: pl.DataFrame, n_boot: int, seed: int
) -> dict:
    """B3: pendiente de la diferencia foco-base en Carry/Pass contra cero.

    Si la deriva afectara igual a los dos, la diferencia seria plana y la
    pendiente cero. El IC sale de un bootstrap por poss_uid dentro de cada
    torneo, que respeta la unidad de dependencia del proyecto.
    """
    rf, rb = razon_carry_pass(foco), razon_carry_pass(base)
    j = rf.join(rb, on=["torneo", "torneo_orden"], suffix="_base")
    if j.height < 3:
        return {"evaluable": False, "torneos": j.height,
                "motivo": "hacen falta al menos 3 torneos para una pendiente"}

    x = j["torneo_orden"].to_numpy().astype(float)
    x = x - x.mean()
    d = (j["razon"] - j["razon_base"]).to_numpy()
    pend = float(np.polyfit(x, d, 1)[0])

    rng = np.random.default_rng(seed)
    uids_f = {t: foco.filter(pl.col("torneo") == t)["poss_uid"].unique().to_numpy()
              for t in j["torneo"].to_list()}
    reps = []
    for _ in range(n_boot):
        dd = []
        for t in j["torneo"].to_list():
            u = uids_f[t]
            if u.size == 0:
                dd.append(np.nan); continue
            pick = rng.choice(u, size=u.size, replace=True)
            sub = foco.filter(pl.col("poss_uid").is_in(pick.tolist()))
            c = (sub["action_type"] == "Carry").sum()
            pa = max(int((sub["action_type"] == "Pass").sum()), 1)
            fila = j.filter(pl.col("torneo") == t)
            dd.append(c / pa - float(fila["razon_base"][0]))
        dd = np.asarray(dd, dtype=float)
        m = ~np.isnan(dd)
        if m.sum() >= 3:
            reps.append(float(np.polyfit(x[m], dd[m], 1)[0]))
    reps = np.asarray(reps)
    lo, hi = (np.quantile(reps, [0.025, 0.975]) if reps.size
              else (np.nan, np.nan))
    return {
        "evaluable": True,
        "torneos": j.height,
        "pendiente": pend,
        "ic95": [float(2 * pend - hi), float(2 * pend - lo)],
        "paralelas": bool((2 * pend - hi) <= 0 <= (2 * pend - lo)),
        "razon_foco_por_torneo": dict(zip(j["torneo"].to_list(),
                                          map(float, j["razon"].to_list()))),
        "razon_base_por_torneo": dict(zip(j["torneo"].to_list(),
                                          map(float, j["razon_base"].to_list()))),
        "nota_B4": ("contraste DEBIL: no hay periodo pre-tratamiento limpio, "
                    "la deriva es continua. Detecta divergencia grande; no "
                    "certifica paralelismo."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indirs", nargs="+", required=True, type=Path)
    ap.add_argument("--prior-from", required=True, type=Path, dest="prior_from")
    ap.add_argument("--n-boot", type=int, default=300, dest="n_boot")
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--out", type=Path,
                    default=Path("reports/linea_base_contemporanea.json"))
    args = ap.parse_args()

    liga = carga_liga(args.prior_from)
    print(f"liga: {liga.height:,} transiciones, "
          f"{liga['torneo'].n_unique()} torneos\n")

    filas = []
    for indir in sorted(args.indirs):
        rp = indir / "phase0_report.json"
        if not rp.exists():
            print(f"  [salto] {indir}: sin phase0_report.json")
            continue
        rep = json.loads(rp.read_text())
        co = rep.get("coaches") or {}
        club = co.get("club")
        if not club:
            print(f"  [salto] {indir}: sin club")
            continue
        trans = _read_trans(str(indir)).with_columns(torneo_cols())

        for c in co.get("coverage", []):
            if not c.get("suficiente"):
                continue
            dt = c["coach"]
            foco = trans.filter(pl.col("coach") == dt)
            if foco.height == 0:
                continue
            torneos = (foco.group_by("torneo").agg(pl.len().alias("n"))
                       .sort("torneo")["torneo"].to_list())
            base = base_contemporanea(liga, club, torneos)
            tp = tendencias_paralelas(foco, base, args.n_boot, args.seed)
            filas.append({
                "club": club, "coach": dt, "indir": str(indir),
                "n_transiciones_foco": foco.height,
                "n_transiciones_base": base.height,
                "torneos": torneos,
                "tendencias_paralelas": tp,
            })
            est = ("n/e" if not tp["evaluable"]
                   else ("PARALELAS" if tp["paralelas"] else "DIVERGEN"))
            pend = tp.get("pendiente")
            print(f"  {club:<22}{dt:<24} {len(torneos)} torneos  "
                  f"base={base.height:>9,}  "
                  f"pend={pend:+.5f}" if pend is not None else "", end="")
            print(f"  {est}")

    divergen = [f for f in filas
                if f["tendencias_paralelas"].get("evaluable")
                and not f["tendencias_paralelas"]["paralelas"]]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "reglas_preinscritas": {
            "B1": "la linea base excluye al club focal",
            "B2": "ponderada a la mezcla de torneos del foco",
            "B3": "tendencias paralelas verificadas sobre Carry/Pass",
            "B4": "el contraste de B3 es debil: no hay pre-tratamiento limpio",
        },
        "unidades": filas,
        "n_divergen": len(divergen),
        "n_boot": args.n_boot, "seed": args.seed,
    }, indent=2, ensure_ascii=False))
    print(f"\n{len(filas)} unidades; {len(divergen)} con tendencias que "
          f"DIVERGEN de su base contemporanea.")
    if divergen:
        print("En esas, la deriva NO se cancela del todo y queda residuo:")
        for f in divergen:
            print(f"  {f['club']} / {f['coach']}  "
                  f"pendiente {f['tendencias_paralelas']['pendiente']:+.5f}")
    print(f"\nescrito {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
