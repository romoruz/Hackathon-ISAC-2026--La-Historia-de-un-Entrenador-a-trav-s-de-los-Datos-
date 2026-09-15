#!/usr/bin/env python3
"""
22_deriva_proveedor.py — ¿cambio tactico o cambio de anotacion?

EL PROBLEMA
===========
En el America, transiciones por posesion: Jardine 8.04, Ortiz 7.32,
Solari 6.30. Un 28% entre extremos, y E[T] es una de las cantidades que se
reportan. El mismo patron esta en el volcado viejo (Jardine 7.76, Solari
6.50), asi que no es un artefacto de la migracion.

Pero **la era esta perfectamente confundida con el tiempo**: Solari es 2021,
Jardine es 2023-2026. Si Hudl StatsBomb cambio la granularidad con la que
anota acarreos, o donde corta las posesiones, eso se ve EXACTAMENTE igual que
"Solari jugaba posesiones mas cortas". El diseno no puede separarlos con los
datos de un solo club.

REGLAS PREINSCRITAS (2026-09-14, antes de correr esto)
======================================================

D1. QUE SE MIDE. Cantidades **mecanicas**, que dependen del protocolo de
    anotacion y no de como se juega:
      - eventos por partido, ANTES de cualquier filtro;
      - fraccion de acarreos por debajo de `min_carry_length` -- si el
        proveedor cambio como parte los acarreos, esa fraccion salta;
      - acciones por posesion ANTES de `min_actions`;
      - tasa de `under_pressure` por accion, que es una marca del anotador.
    Se anade la distribucion de `play_pattern` por torneo con TV y KL, pero
    ESA SOLA NO DISCRIMINA: si la liga entera juega distinto en 2025, la
    distribucion cambia y eso es futbol, no anotacion. Entra como descriptivo.

D2. QUE PATRON CUENTA COMO DERIVA. No la magnitud, la FORMA:
      deriva de medicion -> SALTO en frontera de torneo, SINCRONIZADO en los
                            18 clubes;
      cambio tactico     -> tendencia suave y HETEROGENEA entre clubes.
    Por eso todo se calcula por (torneo x club) y se reporta la dispersion
    entre clubes ademas de la media. Un salto que comparten los 18 no lo
    produce la tactica.

D3. NINGUNA DISTANCIA SIN SU NULA (ADR-30). Una TV entre dos torneos es
    positiva por puro ruido de muestreo. La nula es la distribucion de TV
    entre pares de bloques de partidos del MISMO torneo, del mismo tamano.
    Sin esa nula el numero no dice nada y no se reporta.

D4. ESTE SCRIPT NO CORRIGE NADA. Si hay deriva, la decision de ajustar o de
    declarar la limitacion es humana y va a un ADR. Si no la hay, la
    diferencia entre eras se sostiene y se dice asi.

El torneo se deriva de la FECHA, no de `competition_stage`: la etiqueta es
inconsistente entre temporadas. Julio-diciembre = Apertura, enero-junio =
Clausura.

Uso:

    python scripts/22_deriva_proveedor.py \
        --src data/api/eventos_api_ligamx \
        --match-dates data/api/match_dates_ligamx.csv \
        --out reports/deriva_proveedor.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl

from dtdecoder import ingest
from dtdecoder.config import Config

N_NULA = 200


def torneo_expr() -> list[pl.Expr]:
    """Etiqueta del torneo Y su orden CRONOLOGICO.

    BUG CORREGIDO (2026-09-14). La version anterior emitia solo la etiqueta y
    despues se ordenaba por ella, que es ALFABETICO: A2021, A2022, A2023,
    A2024, A2025, C2022, C2023... Asi, el par "consecutivo" A2025 -> C2022
    retrocede tres anos y medio, y la frontera real A2022 -> C2023 --donde
    cae el escalon-- nunca se evaluaba. En una serie de tiempo el indice es
    lo unico que no se puede improvisar.

    `orden` = anio*2 + (0 si enero-junio, 1 si julio-diciembre), asi que
    C2022 < A2022 < C2023 < A2023, que es el calendario real de la Liga MX.
    """
    anio = pl.col("match_date").dt.year()
    es_apertura = pl.col("match_date").dt.month() >= 7
    return [
        pl.when(es_apertura)
        .then(pl.lit("A") + anio.cast(pl.Utf8))
        .otherwise(pl.lit("C") + anio.cast(pl.Utf8))
        .alias("torneo"),
        (anio * 2 + es_apertura.cast(pl.Int32)).alias("torneo_orden"),
    ]


def tv(p: np.ndarray, q: np.ndarray) -> float:
    return float(0.5 * np.abs(p - q).sum())


def kl(p: np.ndarray, q: np.ndarray) -> float:
    m = p > 0
    return float((p[m] * np.log(p[m] / np.maximum(q[m], 1e-12))).sum())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--match-dates", required=True, dest="match_dates")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", type=Path,
                    default=Path("reports/deriva_proveedor.json"))
    ap.add_argument("--seed", type=int, default=20260914)
    args = ap.parse_args()

    cfg = Config.load(args.config)
    pcfg = cfg["possession"]
    min_carry = float(pcfg.get("min_carry_length") or 0.0)
    min_acc = int(pcfg.get("min_actions") or 0)
    moving = list(pcfg["moving_types"])

    md = pl.read_csv(args.match_dates).select(
        pl.col("match_id").cast(pl.Int64),
        pl.col("match_date").cast(pl.Utf8).str.head(10).str.to_date(),
    ).unique(subset=["match_id"])

    # Se trabaja sobre los eventos CRUDOS normalizados, no sobre
    # transitions.parquet: todas las cantidades de D1 son ANTERIORES a los
    # filtros del pipeline, que es justo lo que las hace mecanicas.
    lf = ingest.load(args.src)
    ev = (lf.select("match_id", "team", "type", "possession",
                    "under_pressure", "play_pattern",
                    "start_x", "start_y", "carry_end_x", "carry_end_y")
          .collect(engine="streaming"))
    ev = ev.join(md, on="match_id", how="inner").with_columns(torneo_expr())
    orden_de = dict(ev.select("torneo", "torneo_orden").unique().iter_rows())
    print(f"eventos: {ev.height:,}  partidos: {ev['match_id'].n_unique():,}  "
          f"torneos: {ev['torneo'].n_unique()}")

    ev = ev.with_columns(
        pl.col("under_pressure").fill_null(False).alias("presion"),
        (
            (pl.col("carry_end_x") - pl.col("start_x")) ** 2
            + (pl.col("carry_end_y") - pl.col("start_y")) ** 2
        ).sqrt().alias("largo_carry"),
    )

    # --- D1: mecanicas por (torneo, club) -------------------------------
    por = (
        ev.group_by(["torneo", "torneo_orden", "team"])
        .agg(
            pl.col("match_id").n_unique().alias("partidos"),
            pl.len().alias("eventos"),
            (pl.len() / pl.col("match_id").n_unique()).alias("ev_por_partido"),
            pl.col("type").is_in(moving).mean().alias("frac_moving"),
            pl.col("presion").mean().alias("tasa_presion"),
            (pl.col("type") == "Carry").mean().alias("frac_carry"),
            pl.col("largo_carry").filter(pl.col("type") == "Carry")
              .lt(min_carry).mean().alias("frac_carry_corto"),
            # BUG CORREGIDO: `possession` es un indice DENTRO de cada
            # partido, asi que `n_unique()` sobre varios partidos cuenta
            # valores distintos, no posesiones. Daba ~100 acciones por
            # posesion, que es absurdo y deberia haber saltado a la vista.
            (pl.len() / pl.struct("match_id", "possession").n_unique())
              .alias("acc_por_posesion_cruda"),
        )
        .sort(["torneo_orden", "team"])
    )

    resumen = (
        por.group_by(["torneo", "torneo_orden"])
        .agg(
            pl.col("partidos").sum().alias("partidos"),
            pl.col("team").n_unique().alias("clubes"),
            *[pl.col(c).mean().alias(f"{c}_media") for c in
              ("ev_por_partido", "tasa_presion", "frac_carry",
               "frac_carry_corto", "acc_por_posesion_cruda")],
            # D2: la dispersion entre clubes es la mitad del diagnostico.
            *[pl.col(c).std().alias(f"{c}_sd_clubes") for c in
              ("ev_por_partido", "tasa_presion", "frac_carry",
               "frac_carry_corto", "acc_por_posesion_cruda")],
        )
        .sort("torneo_orden")
    )
    print("\n== mecanicas por torneo (media entre clubes) ==")
    print(resumen.select(
        "torneo", "partidos", "clubes",
        pl.col("ev_por_partido_media").round(1),
        pl.col("frac_carry_media").round(4),
        pl.col("frac_carry_corto_media").round(4),
        pl.col("tasa_presion_media").round(4),
        pl.col("acc_por_posesion_cruda_media").round(3),
    ))

    torneos = resumen["torneo"].to_list()   # orden cronologico
    # --- D1 bis: ¿el escalon es uniforme entre TIPOS de evento? ----------
    # Decide QUE correccion hace falta:
    #   uniforme entre tipos  -> granularidad global; una linea base
    #                            contemporanea lo absorbe;
    #   concentrado en un tipo -> empezaron a registrar algo nuevo, y ese
    #                            tipo hay que tratarlo aparte.
    por_tipo = (
        ev.group_by(["torneo", "torneo_orden", "type"])
        .agg((pl.len() / pl.col("match_id").n_unique()).alias("por_partido"))
        .sort(["torneo_orden", "type"])
    )
    frecuentes = (
        ev.group_by("type").agg(pl.len().alias("n"))
        .sort("n", descending=True).head(10)["type"].to_list()
    )
    piv_tipo = (por_tipo.filter(pl.col("type").is_in(frecuentes))
                .pivot(index="type", on="torneo", values="por_partido"))
    print("\n== eventos por partido, por tipo (columnas en orden cronologico) ==")
    cols = ["type"] + [t for t in torneos if t in piv_tipo.columns]
    print(piv_tipo.select(cols).with_columns(
        [pl.col(c).round(1) for c in cols[1:]]))

    # Crecimiento relativo de cada tipo a traves del escalon: si todos crecen
    # el mismo porcentaje, es granularidad; si uno se dispara, es otra cosa.
    mitad = len(torneos) // 2
    antes, despues = torneos[:mitad], torneos[mitad:]
    crecimiento = []
    for t in frecuentes:
        fila = piv_tipo.filter(pl.col("type") == t)
        if fila.height == 0:
            continue
        va = [fila[c][0] for c in antes if c in fila.columns and fila[c][0] is not None]
        vd = [fila[c][0] for c in despues if c in fila.columns and fila[c][0] is not None]
        if not va or not vd:
            continue
        ma, mdp = float(np.mean(va)), float(np.mean(vd))
        crecimiento.append({"type": t, "antes": ma, "despues": mdp,
                            "crecimiento_rel": (mdp - ma) / max(ma, 1e-9)})
    print("\n== crecimiento relativo por tipo (primera mitad vs segunda) ==")
    for c in sorted(crecimiento, key=lambda x: -x["crecimiento_rel"]):
        print(f"  {c['type']:<22} {c['antes']:>8.1f} -> {c['despues']:>8.1f}   "
              f"{c['crecimiento_rel']:+.1%}")

    # --- D1 ter: LA cifra que decide, transiciones POST-filtro ------------
    # Todo lo anterior son eventos CRUDOS. El pipeline no los usa: usa
    # Pass/Carry/Shot, descarta acarreos cortos y exige min_actions. Si el
    # escalon desaparece aqui, no contamina E[T]; si sobrevive, si.
    post = ev.filter(pl.col("type").is_in(moving))
    if min_carry > 0:
        post = post.filter(
            (pl.col("type") != "Carry")
            | pl.col("largo_carry").is_null()
            | (pl.col("largo_carry") >= min_carry)
        )
    pos = (
        post.group_by(["torneo", "torneo_orden", "team", "match_id", "possession"])
        .agg(pl.len().alias("acciones"))
        .filter(pl.col("acciones") >= min_acc)
    )
    post_torneo = (
        pos.group_by(["torneo", "torneo_orden"])
        .agg(
            pl.col("acciones").mean().alias("acc_por_posesion_filtrada"),
            pl.len().alias("posesiones"),
        )
        .sort("torneo_orden")
    )
    print("\n== acciones por posesion DESPUES de los filtros ==")
    print(post_torneo.select("torneo", "posesiones",
                             pl.col("acc_por_posesion_filtrada").round(3)))
    v = post_torneo["acc_por_posesion_filtrada"].to_list()
    if len(v) >= 4:
        a, b = float(np.mean(v[:len(v) // 2])), float(np.mean(v[len(v) // 2:]))
        print(f"\n  primera mitad {a:.3f}  ->  segunda mitad {b:.3f}   "
              f"({(b - a) / a:+.1%})")
        print("  Si este porcentaje es chico comparado con el de eventos "
              "crudos,\n  los filtros absorbieron buena parte del escalon.")

    # D2: ¿los saltos son sincronizados? Se mide la fraccion de clubes que se
    # mueven en el MISMO sentido de un torneo al siguiente. Con 18 clubes,
    # 18/18 en la misma direccion es practicamente imposible por tactica.
    torneos = resumen["torneo"].to_list()   # ya en orden cronologico
    sincronia = []
    for metrica in ("ev_por_partido", "frac_carry_corto", "tasa_presion",
                    "acc_por_posesion_cruda"):
        piv = por.pivot(index="team", on="torneo", values=metrica)
        for a, b in zip(torneos, torneos[1:]):
            if a not in piv.columns or b not in piv.columns:
                continue
            d = (piv[b] - piv[a]).drop_nulls().to_numpy()
            if d.size == 0:
                continue
            sincronia.append({
                "metrica": metrica, "de": a, "a": b,
                "clubes": int(d.size),
                "suben": int((d > 0).sum()),
                "frac_mismo_sentido": float(max((d > 0).mean(),
                                                (d < 0).mean())),
                "delta_mediano": float(np.median(d)),
            })

    # --- D3: TV/KL de play_pattern por torneo, CON su nula ---------------
    pats = sorted(ev["play_pattern"].drop_nulls().unique().to_list())

    def dist(sub: pl.DataFrame) -> np.ndarray:
        c = (sub.group_by("play_pattern").agg(pl.len().alias("n"))
             .sort("play_pattern"))
        m = dict(zip(c["play_pattern"].to_list(), c["n"].to_list()))
        v = np.array([m.get(p, 0) for p in pats], dtype=float)
        return v / max(v.sum(), 1.0)

    rng = np.random.default_rng(args.seed)
    nula = []
    for t in torneos:
        sub = ev.filter(pl.col("torneo") == t)
        mids = sub["match_id"].unique().to_numpy()
        if mids.size < 20:
            continue
        for _ in range(N_NULA // max(len(torneos), 1) + 1):
            perm = rng.permutation(mids)
            mitad = perm.size // 2
            a = dist(sub.filter(pl.col("match_id").is_in(perm[:mitad])))
            b = dist(sub.filter(pl.col("match_id").is_in(perm[mitad:])))
            nula.append(tv(a, b))
    nula = np.asarray(nula)
    p95 = float(np.quantile(nula, 0.95)) if nula.size else float("nan")
    print(f"\nnula de TV dentro de torneo: n={nula.size}, "
          f"p95={p95:.4f}  (ADR-30)")

    fases = []
    dists = {t: dist(ev.filter(pl.col("torneo") == t)) for t in torneos}
    for a, b in zip(torneos, torneos[1:]):
        d_tv = tv(dists[a], dists[b])
        fases.append({
            "de": a, "a": b,
            "tv": d_tv,
            "kl": kl(dists[a], dists[b]),
            "p95_nulo": p95,
            "supera_nula": bool(d_tv > p95) if nula.size else None,
        })
    print("\n== play_pattern entre torneos consecutivos ==")
    for f in fases:
        print(f"  {f['de']} -> {f['a']}   TV={f['tv']:.4f}  "
              f"{'SUPERA la nula' if f['supera_nula'] else 'dentro de la nula'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "reglas_preinscritas": {
            "D1": "cantidades mecanicas, previas a los filtros del pipeline",
            "D2": "deriva = salto sincronizado en los 18 clubes; "
                  "tactica = tendencia suave y heterogenea",
            "D3": "ninguna distancia sin su nula (ADR-30)",
            "D4": "este script no corrige nada; la decision es humana",
        },
        "config": {"min_carry_length": min_carry, "min_actions": min_acc,
                   "moving_types": moving},
        "por_torneo": resumen.to_dicts(),
        "por_tipo": por_tipo.to_dicts(),
        "crecimiento_por_tipo": crecimiento,
        "post_filtro_por_torneo": post_torneo.to_dicts(),
        "por_torneo_club": por.to_dicts(),
        "sincronia": sincronia,
        "play_pattern": fases,
        "nula_tv": {"n": int(nula.size), "p95": p95,
                    "media": float(nula.mean()) if nula.size else None},
    }, indent=2, ensure_ascii=False, default=str))
    print(f"\nescrito {args.out}")
    print("\nLECTURA: busca metricas con `frac_mismo_sentido` cerca de 1.0 en "
          "una frontera concreta.\nEso es un salto que comparten los 18 "
          "clubes, y la tactica no produce eso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
