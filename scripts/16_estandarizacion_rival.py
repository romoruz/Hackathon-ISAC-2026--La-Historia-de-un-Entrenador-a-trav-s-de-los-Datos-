#!/usr/bin/env python3
"""
16_estandarizacion_rival.py — ¿es el entrenador, o es el calendario?

LA AMENAZA
----------
Jardine enfrento a Cruz Azul DIEZ veces (liguilla) y a los demas rivales entre
cuatro y seis. Herrera tuvo exactamente una vuelta completa: un partido contra
cada uno de los 17. Sus calendarios no son comparables.

Cualquier cantidad defensiva cruda —acciones concedidas por posesion, remates
concedidos, tasa de presion— mezcla el efecto del entrenador con la composicion
de rivales que le toco. Un DT que enfrento mas equipos de liguilla parecera
peor defensivamente sin haber hecho nada distinto.

LA SOLUCION: ESTANDARIZACION DIRECTA
------------------------------------
Metodo clasico de epidemiologia (ajuste de tasas de mortalidad por estructura
poblacional). Sea theta_{e,o} la cantidad estimada solo con las posesiones del
rival `o` frente a la era `e`, y w_o un peso comun a todas las eras:

    theta^std_e = sum_o w_o * theta_{e,o}

Al usar los MISMOS pesos para las dos eras que comparas, la composicion deja de
influir. Es tambien muestreo estratificado (Tema 5): reduce varianza ademas de
eliminar sesgo.

POSITIVIDAD -- el supuesto que hay que verificar
------------------------------------------------
Solo es valido si cada rival con w_o > 0 aparece en LAS DOS eras. Si no, el
estimador promedia sobre conjuntos distintos y se rompe en silencio: un NaN
propagado, o peor, un promedio sobre soportes diferentes que parece un numero.

Verificado el 2026-08-24 para el America: 17/17 rivales en los seis pares de
eras, 100% de cobertura. Aun asi el script lo comprueba en cada corrida y
restringe al soporte comun O_12 = O_1 ∩ O_2, reportando cuanta masa sacrifica.

Al restringir, el estimando CAMBIA: ya no es el efecto global sino el efecto
promedio sobre el solapamiento. Hay que decirlo.

QUE SE ESTANDARIZA Y QUE NO
---------------------------
NO se estandariza E[T] de la cadena. Ajustar una matriz 80x84 por estrato con
rivales de un solo partido es imposible.

SI se estandarizan las cantidades EMPIRICAS a nivel de posesion, que son medias
simples y por tanto admiten estratos ralos sin supuestos:

    acciones_por_posesion  -- proxy directo de E[T^def]
    tasa_remate            -- P(la posesion rival termina en remate)
    tasa_gol               -- P(termina en gol)
    tasa_presion           -- pi marginal

Contrastar el E[T] del modelo (crudo) contra su version empirica estandarizada
ES el chequeo de confusion. Si el efecto sobrevive, el calendario no lo explica.

Uso:
  python scripts/16_estandarizacion_rival.py --club "América"
  python scripts/16_estandarizacion_rival.py --club "Cruz Azul" \
      --a "Martin Anselmi" --b "Juan Reynoso"
  python scripts/16_estandarizacion_rival.py --club "América" \
      --perspective attack        # el mismo ajuste sobre la fase con balon
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.config import Config
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

METRICAS = ["acciones_por_posesion", "tasa_remate", "tasa_gol", "tasa_presion"]


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=tuple(cfg["phase_order"]))


# --------------------------------------------------------------------------
# Nivel posesion: una fila por posesion, con sus cuatro cantidades
# --------------------------------------------------------------------------
def por_posesion(trans: pl.DataFrame, sp: StateSpace, club: str,
                 perspective: str) -> pl.DataFrame:
    """Colapsa transiciones a posesiones. Es la unidad de remuestreo (ADR).

    `rival` identifica el estrato. En perspectiva defensiva es el equipo que
    tiene el balon (el rival del club); en ofensiva es el oponente del partido,
    que hay que deducir porque la fila no lo trae.
    """
    goal = sp.absorbing_index("GOAL")
    shot = sp.absorbing_index("SHOT_NOGOAL")
    unit = "coach_faced" if perspective == "defense" else "coach"

    if perspective == "defense":
        sub = trans.filter(pl.col("team") != club)
        sub = sub.with_columns(pl.col("team").alias("rival"))
    else:
        # El oponente del partido: el unico `team` distinto del club en ese
        # match_id. Sin esto la perspectiva ofensiva no se puede estratificar.
        opp = (trans.filter(pl.col("team") != club)
                    .group_by("match_id")
                    .agg(pl.col("team").first().alias("rival")))
        sub = trans.filter(pl.col("team") == club).join(opp, on="match_id", how="left")

    sub = sub.filter(pl.col(unit).is_not_null())
    if sub.height == 0:
        sys.exit(f"Sin transiciones con `{unit}` no nulo para club={club!r}.")

    return (
        sub.group_by("poss_uid")
        .agg(
            pl.col(unit).first().alias("era"),
            pl.col("rival").first(),
            pl.col("match_id").first(),
            pl.len().alias("acciones_por_posesion"),
            (pl.col("to_state").is_in([goal, shot]).any()).cast(pl.Float64).alias("tasa_remate"),
            (pl.col("to_state") == goal).any().cast(pl.Float64).alias("tasa_gol"),
            pl.col("under_pressure").filter(
                pl.col("action_type") != "TERMINAL").mean().alias("tasa_presion"),
        )
        .with_columns(pl.col("acciones_por_posesion").cast(pl.Float64))
        .drop_nulls("tasa_presion")
    )


# --------------------------------------------------------------------------
# Estandarizacion directa
# --------------------------------------------------------------------------
def estandarizar(poss: pl.DataFrame, era: str, soporte: list[str],
                 pesos: dict[str, float]) -> dict[str, float]:
    """theta^std = sum_o w_o theta_{e,o}, restringido al soporte comun."""
    sub = poss.filter((pl.col("era") == era) & pl.col("rival").is_in(soporte))
    por_rival = sub.group_by("rival").agg(
        [pl.col(m).mean().alias(m) for m in METRICAS] + [pl.len().alias("n")]
    )
    d = {r["rival"]: r for r in por_rival.to_dicts()}
    out: dict[str, float] = {}
    for m in METRICAS:
        num = sum(pesos[o] * d[o][m] for o in soporte if o in d)
        den = sum(pesos[o] for o in soporte if o in d)
        out[m] = float(num / den) if den > 0 else float("nan")
    return out


def crudo(poss: pl.DataFrame, era: str) -> dict[str, float]:
    sub = poss.filter(pl.col("era") == era)
    return {m: float(sub[m].mean()) for m in METRICAS}


def n_efectivo(pesos: dict[str, float], soporte: list[str]) -> float:
    """(sum w)^2 / sum w^2. Cuantos estratos 'equivalentes' hay de verdad."""
    w = np.array([pesos[o] for o in soporte], dtype=float)
    return float(w.sum() ** 2 / max((w ** 2).sum(), 1e-12))


# --------------------------------------------------------------------------
# Bootstrap estratificado
# --------------------------------------------------------------------------
def boot_diferencia(poss: pl.DataFrame, a: str, b: str, soporte: list[str],
                    pesos: dict[str, float], n_boot: int, seed: int) -> dict:
    """IC de la diferencia estandarizada, remuestreando posesiones DENTRO de
    cada estrato (era, rival).

    Remuestrear libremente romperia la estructura que la estandarizacion
    impone: los pesos dejarian de significar lo que significan. Y remuestrear
    eventos en vez de posesiones daria intervalos artificialmente angostos
    (ADR de bootstrap por bloques).
    """
    rng = np.random.default_rng(seed)
    idx: dict[tuple[str, str], np.ndarray] = {}
    for era in (a, b):
        for o in soporte:
            sel = poss.filter((pl.col("era") == era) & (pl.col("rival") == o))
            idx[(era, o)] = np.column_stack(
                [sel[m].to_numpy().astype(float) for m in METRICAS]
            ) if sel.height else np.empty((0, len(METRICAS)))

    def una(remuestrear: bool) -> np.ndarray:
        out = np.zeros((2, len(METRICAS)))
        for k, era in enumerate((a, b)):
            num = np.zeros(len(METRICAS))
            den = 0.0
            for o in soporte:
                arr = idx[(era, o)]
                if arr.shape[0] == 0:
                    continue
                if remuestrear:
                    arr = arr[rng.integers(0, arr.shape[0], arr.shape[0])]
                num += pesos[o] * arr.mean(axis=0)
                den += pesos[o]
            out[k] = num / max(den, 1e-12)
        return out[0] - out[1]

    obs = una(False)
    reps = np.array([una(True) for _ in range(n_boot)])
    lo = np.quantile(reps, 0.025, axis=0)
    hi = np.quantile(reps, 0.975, axis=0)
    # Bootstrap basico (percentil invertido), igual que inference.bootstrap_diff.
    lo_b, hi_b = 2 * obs - hi, 2 * obs - lo

    # --- p-valor por INVERSION del mismo intervalo -------------------------
    # BH necesita p-valores y un IC no los da. Derivarlos de otra receta
    # (normalidad asintotica, por ejemplo) crearia dos rutas para la misma
    # cantidad, que es como nacio el bug #2: intervalos que no contenian su
    # propio estimador puntual.
    #
    # El nivel de significancia alcanzado del intervalo basico es el alpha mas
    # pequeno al que deja de contener el cero. El intervalo
    # [2*theta - G^-1(1-a/2), 2*theta - G^-1(a/2)] excluye el cero exactamente
    # cuando alpha > 2*min(P(theta* <= 2*theta), P(theta* >= 2*theta)). De ahi:
    #
    #     p = 2 * min(P(theta* <= 2*theta), P(theta* >= 2*theta))
    #
    # Correccion +1 (Davison & Hinkley 1997), la misma que usa
    # inference.tactical_fingerprint: evita p = 0, que BH no sabe ordenar.
    # Asi el p-valor y el IC son el MISMO objeto visto de dos formas y no
    # pueden contradecirse.
    pval = np.empty(len(METRICAS))
    for i in range(len(METRICAS)):
        centro = 2.0 * obs[i]
        n_bajo = int((reps[:, i] <= centro).sum())
        n_alto = int((reps[:, i] >= centro).sum())
        pval[i] = min(1.0, 2.0 * (1 + min(n_bajo, n_alto)) / (1 + n_boot))

    return {
        m: {
            "diff": float(obs[i]),
            "ic95": [float(lo_b[i]), float(hi_b[i])],
            "p_valor": float(pval[i]),
            # `significativa` es SIN corregir por multiplicidad. El veredicto
            # que va al reporte sale de 17_fdr_estandarizacion.py (ADR-30).
            "significativa_sin_corregir": bool(lo_b[i] > 0 or hi_b[i] < 0),
        }
        for i, m in enumerate(METRICAS)
    }


# --------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", required=True)
    ap.add_argument("--indir", default=None)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--perspective", default="defense", choices=["attack", "defense"])
    ap.add_argument("--a", default=None, help="era A (si se omite, todos los pares)")
    ap.add_argument("--b", default=None)
    ap.add_argument("--min-poss-estrato", type=int, default=20, dest="min_poss")
    ap.add_argument("--n-boot", type=int, default=2000, dest="n_boot")
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = Config.load(args.config)
    sp = _space(cfg)

    indir = args.indir or (
        "data/processed" if args.club == "América" else "data/processed_cruzazul")
    p = Path(indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0 --club` primero.")
    trans = pl.read_parquet(p)
    if "coach_faced" not in trans.columns:
        sys.exit("Falta `coach_faced`. Vuelve a correr phase0 con --club.")

    poss = por_posesion(trans, sp, args.club, args.perspective)
    eras = sorted(poss["era"].unique().to_list())
    print(f"club {args.club!r} · perspectiva {args.perspective} · "
          f"{poss.height:,} posesiones · {len(eras)} eras\n")

    pares = ([(args.a, args.b)] if args.a and args.b
             else list(combinations(eras, 2)))
    resultados = []

    for a, b in pares:
        for e in (a, b):
            if e not in eras:
                sys.exit(f"Era desconocida: {e!r}. Disponibles: {eras}")

        # --- POSITIVIDAD -------------------------------------------------
        cnt = (poss.filter(pl.col("era").is_in([a, b]))
                   .group_by(["era", "rival"]).agg(pl.len().alias("n")))
        ra = {r["rival"] for r in cnt.filter(pl.col("era") == a).to_dicts()
              if r["n"] >= args.min_poss}
        rb = {r["rival"] for r in cnt.filter(pl.col("era") == b).to_dicts()
              if r["n"] >= args.min_poss}
        soporte = sorted(ra & rb)

        n_a = poss.filter(pl.col("era") == a).height
        n_b = poss.filter(pl.col("era") == b).height
        cub_a = poss.filter((pl.col("era") == a) & pl.col("rival").is_in(soporte)).height
        cub_b = poss.filter((pl.col("era") == b) & pl.col("rival").is_in(soporte)).height

        print("=" * 74)
        print(f" {a}  vs  {b}")
        print("=" * 74)
        print(f"  rivales de A: {len(ra):2d} | de B: {len(rb):2d} | "
              f"soporte comun: {len(soporte):2d}  (min {args.min_poss} pos./estrato)")
        print(f"  masa cubierta: A {cub_a / max(n_a,1):.1%} ({cub_a:,}/{n_a:,}) | "
              f"B {cub_b / max(n_b,1):.1%} ({cub_b:,}/{n_b:,})")

        if len(soporte) < 3:
            print("\n  [salto] soporte comun < 3 rivales. La estandarizacion no es")
            print("          interpretable; reporta el crudo con su caveat.\n")
            continue
        if min(cub_a / max(n_a, 1), cub_b / max(n_b, 1)) < 0.85:
            print("\n  [!] Menos del 85% de la masa cubierta. El estimando ya no es")
            print("      el efecto global sino el efecto sobre el SOLAPAMIENTO.")
            print("      Hay que declararlo al reportar.")

        pesos = {o: 1.0 for o in soporte}     # uniforme sobre el soporte comun
        neff = n_efectivo(pesos, soporte)

        est_a = estandarizar(poss, a, soporte, pesos)
        est_b = estandarizar(poss, b, soporte, pesos)
        cru_a, cru_b = crudo(poss, a), crudo(poss, b)
        ic = boot_diferencia(poss, a, b, soporte, pesos, args.n_boot, args.seed)

        print(f"  n_efectivo de estratos: {neff:.1f} de {len(soporte)}\n")
        print(f"  {'metrica':<24} {'crudo A':>9} {'crudo B':>9} {'dif cruda':>10} "
              f"{'dif std':>9} {'IC95 std':>22} {'p':>9}")
        print("  " + "-" * 88)
        for m in METRICAS:
            dc = cru_a[m] - cru_b[m]
            ds = ic[m]["diff"]
            lo, hi = ic[m]["ic95"]
            marca = " *" if ic[m]["significativa_sin_corregir"] else "  "
            print(f"  {m:<24} {cru_a[m]:9.4f} {cru_b[m]:9.4f} {dc:10.4f} "
                  f"{ds:9.4f} [{lo:8.4f}, {hi:8.4f}] p={ic[m]['p_valor']:.4f}{marca}")

        # --- CUANTO DEL EFECTO ERA CALENDARIO ----------------------------
        print("\n  Cuanto del efecto crudo era composicion de calendario:")
        for m in METRICAS:
            dc = cru_a[m] - cru_b[m]
            ds = ic[m]["diff"]
            lo, hi = ic[m]["ic95"]
            semiancho = (hi - lo) / 2.0

            # GUARDA CONTRA EL COCIENTE ESPURIO.
            # (ds - dc)/|dc| explota cuando dc ~ 0, y produce titulares como
            # "el signo se invierte" sobre una diferencia de 0.0002 en tasa de
            # gol -- que no es una inversion, es ruido dividido por ruido.
            # Solo tiene sentido preguntar cuanto MOVIO el ajuste si habia
            # algo que mover: el efecto crudo debe ser al menos del tamano de
            # la incertidumbre.
            if abs(dc) < semiancho:
                print(f"    {m:<24} crudo {dc:+8.4f} -> std {ds:+8.4f}   "
                      f"(efecto no detectable; el cociente no informa)")
                continue

            cambio = (ds - dc) / abs(dc)
            nota = ""
            if abs(cambio) > 0.20:
                nota = "   <<< el ajuste mueve mas del 20%"
            if np.sign(ds) != np.sign(dc):
                nota = "   <<< EL SIGNO SE INVIERTE"
            print(f"    {m:<24} crudo {dc:+8.4f} -> std {ds:+8.4f}  "
                  f"({cambio:+.1%}){nota}")

        resultados.append({
            "club": args.club, "perspective": args.perspective,
            "era_a": a, "era_b": b,
            "soporte_comun": soporte, "n_soporte": len(soporte),
            "n_efectivo": neff,
            "masa_cubierta_a": cub_a / max(n_a, 1),
            "masa_cubierta_b": cub_b / max(n_b, 1),
            "crudo_a": cru_a, "crudo_b": cru_b,
            "std_a": est_a, "std_b": est_b,
            "diferencias": ic,
        })
        print()

    out = Path(args.out or
               f"reports/estandarizacion_{args.perspective}_"
               f"{args.club.lower().replace(' ', '')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(resultados, indent=2, ensure_ascii=False))
    print(f"escrito: {out}")

    print("\nCOMO LEERLO")
    print("  * = el IC de la diferencia estandarizada excluye el cero.")
    print("  Si crudo y estandarizado casi coinciden, el calendario no explicaba")
    print("  el efecto y la comparacion cruda era valida. Que se pueda AFIRMAR")
    print("  eso, en vez de suponerlo, es el resultado.")
    print("  Si el ajuste mueve mucho o invierte el signo, el titular crudo")
    print("  estaba contaminado y hay que reportar el estandarizado.")
    print("\n  Estas son cantidades EMPIRICAS por posesion, no E[T] de la cadena.")
    print("  Sirven como control de confusion de las cantidades del modelo:")
    print("  si el efecto sobrevive aqui, el calendario no lo explica alla.")


if __name__ == "__main__":
    main()
