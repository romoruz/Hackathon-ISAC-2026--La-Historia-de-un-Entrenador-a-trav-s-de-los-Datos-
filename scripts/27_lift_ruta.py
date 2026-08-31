#!/usr/bin/env python3
"""Condicionales inversas: ¿de dónde nace el peligro?

DOS LECTURAS, Y NO SON LA MISMA
-------------------------------
«De dónde nace el peligro» se puede leer de dos formas, y conviene calcular las
dos porque cuentan cosas distintas:

  A) REMATE  P(zona | la posesión acabó en GOL)
     La zona de la ULTIMA acción. Responde «¿desde dónde se remata?».
     Sale concentrada en el área. Es exacta y sin supuestos: es una columna de
     la matriz R normalizada.

  B) RUTA    P(la posesión visitó la zona | acabó en GOL)
     Por dónde PASÓ la jugada. Responde «¿por dónde se construye?».
     Sale mucho más repartida, e incluye el origen de la jugada.

Y la cantidad que de verdad informa es el COCIENTE de B contra la marginal:

  lift(zona) = P(visitó zona | GOL) / P(visitó zona)

Un lift de 2.3 significa que las jugadas que acaban en gol pasan 2.3 veces más
por esa casilla que una jugada cualquiera. Eso es informativo; el porcentaje
crudo no, porque las zonas por las que se pasa siempre saldrian altas en las dos.

LO QUE HAY QUE DECLARAR
-----------------------
El gol es raro (~1.6% de las posesiones). Con 8,694 posesiones eso son ~140
goles repartidos en 20 zonas: unos 7 por zona. El lift de una zona con 3 goles
detrás no significa nada. Por eso se emite `n` por desenlace y por zona, y el
lift se recorta cuando el soporte es insuficiente.

NO ES CAUSAL. Que las jugadas que acaban en gol pasen mas por una zona no
significa que pasar por ahi cause goles: puede ser que las jugadas que ya iban
bien lleguen ahi. Es el mismo caveat que la presion (ADR-48).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

NX, NY = 5, 4
NZ = NX * NY


def zona_de(estado, nf):
    z = int(estado) // nf
    return (z // NY, z % NY)


def condicionales(t: pl.DataFrame, coach: str, nf: int, fin: dict,
                  min_n: int = 25) -> dict:
    """Devuelve, por desenlace, el reparto de remate y de ruta con su lift."""
    sub = t.filter(pl.col("coach") == coach)
    if sub.height == 0:
        return {}

    # desenlace de cada posesion: el estado absorbente al que llego
    fin_pos = (sub.filter(pl.col("is_absorbing"))
                  .group_by("poss_uid").agg(pl.col("to_state").last().alias("fin")))
    n_tot = fin_pos.height

    # zona de cada accion, y zonas VISITADAS por cada posesion
    z = (sub.with_columns(((pl.col("from_state") // nf) // NY * NY
                           + (pl.col("from_state") // nf) % NY).alias("zona"))
            .select(["poss_uid", "zona", "from_state", "to_state", "is_absorbing"]))
    visitas = z.select(["poss_uid", "zona"]).unique()

    # marginal: P(una posesion cualquiera visita la zona)
    marg = (visitas.group_by("zona").agg(pl.col("poss_uid").n_unique().alias("n"))
                   .with_columns((pl.col("n") / n_tot).alias("p")))
    p_marg = dict(zip(marg["zona"].to_list(), marg["p"].to_list()))

    out = {}
    for est_abs, nombre in fin.items():
        pos = fin_pos.filter(pl.col("fin") == int(est_abs))["poss_uid"]
        n = pos.len()
        if n < min_n:
            out[nombre] = {"n": n, "suficiente": False}
            continue

        # (A) zona de la ULTIMA accion
        ult = (z.filter(pl.col("is_absorbing")
                        & pl.col("to_state").eq(int(est_abs)))
                .group_by("zona").len())
        tot_u = ult["len"].sum() or 1
        remate = {int(k): v / tot_u for k, v in ult.iter_rows()}

        # (B) zonas VISITADAS por esas posesiones, y su lift
        vis = (visitas.join(pos.to_frame(), on="poss_uid", how="semi")
                      .group_by("zona").agg(pl.col("poss_uid").n_unique().alias("n")))
        ruta, lift, soporte = {}, {}, {}
        for k, c in vis.iter_rows():
            p_cond = c / n
            ruta[int(k)] = p_cond
            soporte[int(k)] = int(c)
            pm = p_marg.get(k, 0)
            # el lift solo se emite con soporte suficiente: con 3 posesiones
            # detras, un lift de 3.0 es ruido con aspecto de hallazgo
            lift[int(k)] = (p_cond / pm) if (pm > 0 and c >= 10) else None

        out[nombre] = {"n": n, "suficiente": True, "remate": remate,
                       "ruta": ruta, "lift": lift, "soporte": soporte}
    return out


def main() -> None:
    ruta = Path(sys.argv[1] if len(sys.argv) > 1
                else "data/processed/transitions.parquet")
    coach = sys.argv[2] if len(sys.argv) > 2 else None
    t = pl.read_parquet(ruta)
    if coach is None:
        coach = (t.filter(pl.col("coach").is_not_null())
                  .group_by("coach").len().sort("len", descending=True)["coach"][0])

    trans = t.filter(~pl.col("is_absorbing"))["from_state"]
    nf = (int(trans.max()) + 1) // NZ
    absorb = sorted(t.filter(pl.col("is_absorbing"))["to_state"].unique().to_list())
    print(f"{coach} · {nf} fases · absorbentes {absorb}\n")

    # etiquetas por el criterio fisico (concentracion hacia la porteria rival)
    d = t.filter(pl.col("coach") == coach).with_columns(
        ((pl.col("from_state") // nf) // NY).alias("ix"))
    tot = dict(d.group_by("ix").len().iter_rows())
    perf, masa = {}, {}
    for e in absorb:
        c = dict(d.filter(pl.col("to_state") == e).group_by("ix").len().iter_rows())
        perf[e] = [c.get(i, 0) / max(1, tot.get(i, 1)) for i in range(NX)]
        masa[e] = sum(c.values())
    perd = max(absorb, key=lambda e: masa[e])
    resto = [e for e in absorb if e != perd]
    conc = {e: (perf[e][-1] + perf[e][-2]) /
               (perf[e][0] + perf[e][1] + perf[e][-1] + perf[e][-2] + 1e-12)
            for e in resto}
    ofen = sorted(resto, key=lambda e: -conc[e])[:2]
    fin = {perd: "PERDIDA"}
    for e in resto:
        if e not in ofen:
            fin[e] = "BALON FUERA"
    for k, e in enumerate(sorted(ofen, key=lambda e: masa[e])):
        fin[e] = "GOL" if k == 0 else "REMATE"
    print("etiquetas:", {k: v for k, v in fin.items()})

    r = condicionales(t, coach, nf, fin)

    FR = ["banda izq", "centro-izq", "centro-der", "banda der"]
    TE = ["propio", "prop-medio", "medio", "med-rival", "rival"]
    for nombre in ("GOL", "REMATE"):
        d_ = r.get(nombre)
        if not d_:
            continue
        print(f"\n{'='*68}\n{nombre} · {d_['n']} posesiones")
        if not d_["suficiente"]:
            print("  soporte insuficiente: no se emite")
            continue
        s = sum(d_["remate"].values())
        print(f"  (A) reparto de DONDE se remato  — suma {s:.4f}")
        for k, v in sorted(d_["remate"].items(), key=lambda x: -x[1])[:5]:
            print(f"      {FR[k%NY]:12} {TE[k//NY]:11} {100*v:5.1f}%")
        print("  (B) por DONDE paso la jugada, y cuanto mas que una cualquiera")
        filas = [(k, d_["ruta"][k], d_["lift"].get(k), d_["soporte"][k])
                 for k in d_["ruta"] if d_["lift"].get(k)]
        for k, p, lf, n_ in sorted(filas, key=lambda x: -(x[2] or 0))[:5]:
            print(f"      {FR[k%NY]:12} {TE[k//NY]:11} {100*p:5.1f}%  "
                  f"lift {lf:4.2f}x  (n={n_})")
        sin = [k for k in d_["ruta"] if not d_["lift"].get(k)]
        if sin:
            print(f"      ({len(sin)} zonas sin lift por soporte < 10)")


if __name__ == "__main__":
    main()
