#!/usr/bin/env python3
"""
25_pares_h4.py — el barrido de pares de H4, con FDR sobre los 18 clubes.

REGLAS PREINSCRITAS (2026-09-14, ANTES de correr esto)
======================================================

H4-1. MAGNITUDES A lambda=0, SIGNIFICANCIA A lambda* (ADR-22).
      No es configurable por corrida. A lambda=0 no hay encogimiento y por
      tanto no hay atenuacion, que es la unica forma de que la magnitud no
      dependa de cuanta muestra tiene cada era.

H4-2. LA ATENUACION ES DIFERENCIAL Y NO SE ARREGLA CON UN lambda COMUN.
      El factor es n_i/(n_i+lambda) y n_i difiere por unidad: con lambda=500,
      Jardine (74,708 transiciones) queda en 0.993 y Solari (14,650) en 0.971.
      El sesgo siempre va en el mismo sentido: la era chica se parece al prior
      mas de lo que sus datos dicen. Por eso H4-1 no es una preferencia.

H4-3. SENSIBILIDAD DE n IGUALADO. Cada par se recalcula submuestreando la era
      grande al numero de POSESIONES de la chica, repetido. Si el efecto
      sobrevive con n igualado, la asimetria de muestra no lo explica. Es
      preferible a un ajuste analitico porque elimina la asimetria por
      construccion en vez de modelarla.

H4-4. CRITERIO DE DECISION, corregido respecto al primer borrador.
      La nula de MUESTREO (permutacion de etiquetas dentro del par) decide la
      significancia. La distribucion empirica entre unidades de la liga es
      CONTEXTO --"este efecto esta en el percentil X de lo que la liga
      produce"-- y NUNCA criterio de rechazo: contiene heterogeneidad real
      entre clubes, que es senal, no ruido. Exigir las dos cosas era exigir
      que un entrenador fuera atipico entre TODOS los clubes, que no es lo
      que se esta midiendo.

H4-5. LINEA BASE CONTEMPORANEA (ver 24_linea_base_contemporanea.py). El prior
      de cada par se construye con los torneos de ESE par, sin el club focal,
      para que la deriva del proveedor sea un efecto comun que se cancela.

H4-6. SOLO PARES DENTRO DEL MISMO CLUB (ADR-16/ADR-37). Comparar entre clubes
      absorbe plantel, presupuesto y calendario. La comparacion entre clubes
      es H5 y tiene su propio diseno.

H4-7. FDR DE BENJAMINI-HOCHBERG sobre TODOS los pares de TODOS los clubes, en
      una sola familia, declarada de antemano. Nada de decidir la familia
      despues de ver que pares salieron.

H4-8. NINGUNA ERA MARCADA `PRIMERA_DE_VENTANA` SIN VERIFICAR entra al
      resultado. El candado vive en `eras.check_verificada` y aqui se invoca.

Uso:
    python scripts/25_pares_h4.py \\
        --indirs data/processed_api_* \\
        --prior-from data/prior_liga \\
        --out reports/pares_h4.json
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import polars as pl

from dtdecoder.absorbing import AbsorbingChain
from dtdecoder.cli import _read_trans
from dtdecoder.config import Config
from dtdecoder.eras import check_verificada
from dtdecoder.estimate import count_matrix, shrink
from dtdecoder.grid import StateSpace

LAMBDA_MAGNITUD = 0.0        # H4-1: no se toca


def torneo_cols() -> list[pl.Expr]:
    anio = pl.col("match_date").dt.year()
    ap = pl.col("match_date").dt.month() >= 7
    return [
        pl.when(ap).then(pl.lit("A") + anio.cast(pl.Utf8))
        .otherwise(pl.lit("C") + anio.cast(pl.Utf8)).alias("torneo"),
    ]


def espacio(cfg) -> StateSpace:
    p = cfg["pitch"]
    fases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"],
                      width=p["width"], phases=fases)


def escalares(df: pl.DataFrame, space: StateSpace, q: np.ndarray,
              lam: float, w: np.ndarray) -> dict | None:
    """E[T] y xT medios, ponderados por una masa COMUN al par.

    La ponderacion comun es deliberada: si cada era se ponderase por su propia
    distribucion de inicios, la diferencia mezclaria "donde empiezan" con
    "que pasa despues", y solo lo segundo es la cadena.
    """
    C = count_matrix(df, space)
    if C.sum() == 0:
        return None
    P = shrink(C, q, lam)
    ch = AbsorbingChain(P=P, space=space)
    chk = ch.check()
    if not chk.get("rho_ok", True):
        return None
    den = max(float(w.sum()), 1e-12)
    return {
        "E_T": float((ch.expected_length() * w).sum() / den),
        "xT": float((ch.xt() * w).sum() / den),
        "rho_Q": float(chk.get("rho_Q", float("nan"))),
    }


def contraste(a: pl.DataFrame, b: pl.DataFrame, space: StateSpace,
              q: np.ndarray, lam: float) -> dict | None:
    w = (count_matrix(a, space).sum(axis=1)
         + count_matrix(b, space).sum(axis=1))
    ea, eb = (escalares(a, space, q, lam, w), escalares(b, space, q, lam, w))
    if ea is None or eb is None:
        return None
    return {
        "a": ea, "b": eb,
        "dif_E_T": ea["E_T"] - eb["E_T"],
        "rel_E_T": (ea["E_T"] - eb["E_T"]) / max(eb["E_T"], 1e-12),
        "dif_xT": ea["xT"] - eb["xT"],
        "rel_xT": (ea["xT"] - eb["xT"]) / max(abs(eb["xT"]), 1e-12),
    }


def permutacion(a: pl.DataFrame, b: pl.DataFrame, space: StateSpace,
                q: np.ndarray, lam: float, obs: float, n_perm: int,
                rng: np.random.Generator) -> float:
    """p por permutacion de etiquetas, remuestreando POSESIONES enteras.

    Permutar filas sueltas romperia la dependencia dentro de la posesion y
    daria una nula demasiado estrecha: p demasiado chicos, mas rechazos de la
    cuenta. `poss_uid` es la unidad de remuestreo de todo el proyecto.
    """
    ua = a["poss_uid"].unique().sort().to_numpy()
    ub = b["poss_uid"].unique().sort().to_numpy()
    todas = np.concatenate([ua, ub])
    juntas = pl.concat([a, b], how="vertical_relaxed")
    na = ua.size
    extremos = 0
    for _ in range(n_perm):
        perm = rng.permutation(todas)
        pa = juntas.filter(pl.col("poss_uid").is_in(perm[:na].tolist()))
        pb = juntas.filter(pl.col("poss_uid").is_in(perm[na:].tolist()))
        c = contraste(pa, pb, space, q, lam)
        if c is not None and abs(c["dif_E_T"]) >= abs(obs):
            extremos += 1
    return (extremos + 1) / (n_perm + 1)


def n_igualado(a: pl.DataFrame, b: pl.DataFrame, space: StateSpace,
               q: np.ndarray, lam: float, n_rep: int,
               rng: np.random.Generator) -> dict:
    """H4-3: submuestrea la era grande al n de la chica, repetido."""
    ua = a["poss_uid"].unique().sort().to_numpy()
    ub = b["poss_uid"].unique().sort().to_numpy()
    if ua.size == ub.size:
        return {"aplicado": False, "motivo": "mismo numero de posesiones"}
    grande, chica = (a, ub.size) if ua.size > ub.size else (b, ua.size)
    es_a = ua.size > ub.size
    ug = grande["poss_uid"].unique().sort().to_numpy()
    difs = []
    for _ in range(n_rep):
        pick = rng.choice(ug, size=chica, replace=False)
        sub = grande.filter(pl.col("poss_uid").is_in(pick.tolist()))
        c = (contraste(sub, b, space, q, lam) if es_a
             else contraste(a, sub, space, q, lam))
        if c is not None:
            difs.append(c["rel_E_T"])
    if not difs:
        return {"aplicado": False, "motivo": "ninguna submuestra fue valida"}
    d = np.asarray(difs)
    return {
        "aplicado": True, "n_posesiones_igualado": int(chica),
        "rel_E_T_media": float(d.mean()),
        "rel_E_T_ic95": [float(np.quantile(d, 0.025)),
                         float(np.quantile(d, 0.975))],
        "mismo_signo_que_completo": None,   # se rellena fuera
    }


def bh(ps: list[float], alpha: float) -> list[bool]:
    """Benjamini-Hochberg. H4-7: una sola familia, declarada de antemano."""
    m = len(ps)
    orden = np.argsort(ps)
    rech = np.zeros(m, dtype=bool)
    kmax = -1
    for i, k in enumerate(orden, start=1):
        if ps[k] <= alpha * i / m:
            kmax = i
    if kmax > 0:
        rech[orden[:kmax]] = True
    return rech.tolist()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--indirs", nargs="+", required=True, type=Path)
    ap.add_argument("--prior-from", required=True, type=Path, dest="prior_from")
    ap.add_argument("--n-perm", type=int, default=500, dest="n_perm")
    ap.add_argument("--n-rep-igualado", type=int, default=100,
                    dest="n_rep_igualado")
    ap.add_argument("--config", default=None)
    ap.add_argument("--sin-candado", action="store_true",
                    help="NO usar para resultados reportables: salta H4-8")
    ap.add_argument("--out", type=Path, default=Path("reports/pares_h4.json"))
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = espacio(cfg)
    alpha = cfg["inference"]["fdr_alpha"]
    rng = np.random.default_rng(cfg["inference"]["boot_seed"])

    liga = _read_trans(str(args.prior_from), permitir_prior=True)
    liga = liga.with_columns(torneo_cols())
    print(f"liga: {liga.height:,} transiciones\n")

    pares, saltadas = [], []
    for indir in sorted(args.indirs):
        rp = indir / "phase0_report.json"
        if not rp.exists():
            continue
        rep = json.loads(rp.read_text())
        co = rep.get("coaches") or {}
        club = co.get("club")
        dts = [c["coach"] for c in co.get("coverage", []) if c.get("suficiente")]

        # H4-8: el candado, antes de gastar una sola permutacion.
        if not args.sin_candado:
            vivos = []
            for dt in dts:
                try:
                    check_verificada(club, dt)
                    vivos.append(dt)
                except SystemExit as e:
                    saltadas.append({"club": club, "coach": dt,
                                     "motivo": "PRIMERA_DE_VENTANA sin verificar"})
                    print(f"  [candado] {club} / {dt}: fuera del barrido")
                    del e
            dts = vivos
        if len(dts) < 2:
            continue

        trans = _read_trans(str(indir)).with_columns(torneo_cols())
        for x, y in itertools.combinations(sorted(dts), 2):   # H4-6
            a = trans.filter(pl.col("coach") == x)
            b = trans.filter(pl.col("coach") == y)
            if a.height == 0 or b.height == 0:
                continue
            torneos = sorted(set(a["torneo"].to_list())
                             | set(b["torneo"].to_list()))
            # H4-5: base contemporanea, sin el club focal
            base = liga.filter((pl.col("team") != club)
                               & pl.col("torneo").is_in(torneos))
            Cb = count_matrix(base, space)
            nb = Cb.sum(axis=1, keepdims=True)
            q = np.where(nb > 0, Cb / np.maximum(nb, 1e-12), 1.0 / Cb.shape[1])

            # H4-1: magnitud a lambda = 0
            mag = contraste(a, b, space, q, LAMBDA_MAGNITUD)
            if mag is None:
                continue
            p = permutacion(a, b, space, q, LAMBDA_MAGNITUD,
                            mag["dif_E_T"], args.n_perm, rng)
            ig = n_igualado(a, b, space, q, LAMBDA_MAGNITUD,
                            args.n_rep_igualado, rng)
            if ig.get("aplicado"):
                ig["mismo_signo_que_completo"] = bool(
                    np.sign(ig["rel_E_T_media"]) == np.sign(mag["rel_E_T"])
                )
            pares.append({
                "club": club, "a": x, "b": y,
                "n_poss_a": a["poss_uid"].n_unique(),
                "n_poss_b": b["poss_uid"].n_unique(),
                "torneos": torneos,
                "n_base": base.height,
                "magnitud_lambda0": mag,
                "p_permutacion": p,
                "sensibilidad_n_igualado": ig,
            })
            print(f"  {club:<20}{x:<22} vs {y:<22} "
                  f"relE[T]={mag['rel_E_T']:+7.2%}  p={p:.4f}")

    if not pares:
        print("\nNingun par evaluable.")
        return 1

    # H4-7: FDR sobre TODOS los pares, una sola familia
    ps = [x["p_permutacion"] for x in pares]
    rech = bh(ps, alpha)
    for x, r in zip(pares, rech):
        x["rechaza_fdr"] = bool(r)

    # H4-4: la distribucion empirica es CONTEXTO, no criterio
    rels = np.asarray([abs(x["magnitud_lambda0"]["rel_E_T"]) for x in pares])
    for x in pares:
        x["percentil_entre_pares"] = float(
            (rels < abs(x["magnitud_lambda0"]["rel_E_T"])).mean()
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "reglas_preinscritas": {
            "H4-1": "magnitudes a lambda=0, significancia a lambda*",
            "H4-2": "la atenuacion es diferencial; un lambda comun no la arregla",
            "H4-3": "sensibilidad de n igualado por submuestreo",
            "H4-4": "la nula de muestreo decide; la empirica es contexto",
            "H4-5": "linea base contemporanea, sin el club focal",
            "H4-6": "solo pares dentro del mismo club",
            "H4-7": "FDR de BH sobre una familia declarada de antemano",
            "H4-8": "ninguna era PRIMERA_DE_VENTANA sin verificar",
        },
        "alpha_fdr": alpha,
        "n_pares": len(pares),
        "n_rechazados": int(sum(rech)),
        "eras_bloqueadas_por_candado": saltadas,
        "pares": pares,
    }, indent=2, ensure_ascii=False))

    print(f"\n== {len(pares)} pares, {sum(rech)} significativos tras FDR "
          f"(alpha={alpha}) ==")
    for x in sorted((p for p in pares if p["rechaza_fdr"]),
                    key=lambda z: -abs(z["magnitud_lambda0"]["rel_E_T"])):
        ig = x["sensibilidad_n_igualado"]
        marca = ("" if not ig.get("aplicado")
                 else ("" if ig.get("mismo_signo_que_completo")
                       else "   [OJO: cambia de signo con n igualado]"))
        print(f"  {x['club']:<20}{x['a']:<22} vs {x['b']:<22} "
              f"{x['magnitud_lambda0']['rel_E_T']:+7.2%}  "
              f"p={x['p_permutacion']:.4f}{marca}")
    if saltadas:
        print(f"\n{len(saltadas)} era(s) fuera por el candado de "
              f"PRIMERA_DE_VENTANA. Verificalas y vuelve a correr.")
    print(f"\nescrito {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
