#!/usr/bin/env python3
"""
11_confusion_plantel.py — ¿Es el entrenador o son los jugadores?

LA CRITICA QUE RESPONDE
-----------------------
Es la amenaza 4.1 de 05_VALIDATION y la mas seria que sigue viva:

    "Lo que mides no es el DT, es que Jardine tuvo mejores jugadores."

Comparar eras dentro del mismo club controla institucion, presupuesto, cantera,
estadio y calendario. NO controla rotacion de plantilla. Un DT que llega con
seis fichajes no es comparable con su predecesor.

La confusion NO SE PUEDE ELIMINAR con datos observacionales. Se puede
CUANTIFICAR y se puede DISENAR ALREDEDOR. Este script hace tres cosas:

  NIVEL 1 - SOLAPAMIENTO. Que fraccion de las acciones de la era B la
            ejecutaron jugadores que ya estaban en la era A. Si el solapamiento
            es alto, la critica se debilita sola. Es ademas la cifra mas
            comunicable del proyecto: "Jardine heredo el X% del plantel y aun
            asi el equipo circula distinto".

  NIVEL 2 - NUCLEO ESTABLE. Repetir la comparacion conservando solo las
            POSESIONES COMPLETAS donde el nucleo ejecuto la mayoria de las
            acciones. Si la diferencia persiste, no puede ser cambio de
            personal: es el mismo personal.

  NIVEL 3 - INTRA-JUGADOR. Para cada jugador con datos en ambas eras, ¿cambio
            SU comportamiento de transicion al cambiar el DT? Si Fidalgo pasa
            distinto con Jardine que con Solari, eso no puede ser el jugador:
            ES EL MISMO JUGADOR. Es el analogo de un diseno de efectos fijos y
            responde a la critica en vez de mitigarla.

POR QUE EL FILTRO ES POR POSESION Y NO POR TRANSICION
-----------------------------------------------------
La primera version filtraba TRANSICIONES por jugador. Eso rompe la cadena de
una forma que arruina E[T], y de manera NO uniforme:

  - Las absorciones terminales no tienen ejecutante, asi que sobreviven SIEMPRE
    al filtro.
  - Las transiciones transitorias se eliminan en proporcion a cuantas ejecuto
    gente fuera del nucleo.

Resultado: se drena Q y se conserva R. Como E[T] = alpha' (I-Q)^-1 1, drenar Q
hunde E[T]. Y lo hunde MAS cuanto MENOR es la cobertura del nucleo:

  | era      | cobertura | E[T] todos -> nucleo | caida  |
  |----------|-----------|----------------------|--------|
  | Ortiz    | 92.2%     | 6.298 -> 6.137       | -2.6%  |
  | Jardine  | 67.2%     | 6.796 -> 6.072       | -10.7% |
  | Anselmi  | 41.0%     | 6.632 -> 5.190       | -21.7% |
  | Reynoso  | 21.5%     | 5.282 -> 3.097       | -41.4% |

La caida es casi una funcion monotona de la cobertura: es un ARTEFACTO
MECANICO, no un efecto tactico. Y sesga el delta hacia la era con MAYOR
cobertura, en cualquier direccion:

  - Jardine (67%) vs Ortiz (92%): el delta se hundio de +7.9% a -1.1%.
  - Anselmi (41%) vs Reynoso (21%): el delta se inflo de +25.6% a +67.6%.

(No es "sesgo de supervivencia" -- ese es otro fenomeno. Es censura NO UNIFORME
de la muestra de transiciones: se censuran las transitorias pero no las
absorbentes.)

LA SOLUCION: filtrar por POSESION COMPLETA. Se conserva la posesion entera,
con todas sus transiciones, si el nucleo ejecuto al menos `--min-frac-nucleo`
de sus acciones. La cadena mantiene su integridad, E[T] sigue significando
"duracion de una posesion real", y la absorcion terminal no queda
sobrerrepresentada.

Es coherente con ADR-07: la posesion es la unidad indivisible del proyecto.

La cobertura pasa a medirse en POSESIONES RETENIDAS, no en transiciones.

LIMITACION QUE NO DESAPARECE
----------------------------
Aunque el nucleo sea el mismo, el CONTEXTO cambia: los companeros con los que
juega, el rival, la posicion en la que lo pone el DT. El nivel 3 acota mucho la
critica pero no la elimina. Decirlo.

Uso:
  python scripts/11_confusion_plantel.py --a "Andre Jardine" --b "Santiago Solari" \\
      --club "América"
  python scripts/11_confusion_plantel.py --a "Martin Anselmi" --b "Juan Reynoso" \\
      --club "Cruz Azul" --indir data/processed_cruzazul
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.absorbing import AbsorbingChain
    from dtdecoder.config import Config
    from dtdecoder.estimate import count_matrix, mle
    from dtdecoder.grid import StateSpace
    from dtdecoder.inference import benjamini_hochberg
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def _fila(C: np.ndarray, ns: int) -> np.ndarray:
    n = C.sum(axis=1, keepdims=True)
    return np.where(n > 0, C / np.maximum(n, _EPS), 1.0 / ns)


def _alpha(trans: pl.DataFrame, space: StateSpace) -> np.ndarray:
    """Distribucion inicial empirica: donde arrancan las posesiones."""
    orden = ["poss_uid"] + (["event_index"] if "event_index" in trans.columns else [])
    prim = (trans.sort(orden).group_by("poss_uid", maintain_order=True)
            .agg(pl.col("from_state").first()))
    a = np.zeros(space.n_transient)
    v, c = np.unique(prim["from_state"].to_numpy().astype(int), return_counts=True)
    ok = v < space.n_transient
    a[v[ok]] = c[ok]
    return a / max(a.sum(), _EPS)


def E_T(trans: pl.DataFrame, space: StateSpace) -> float | None:
    """E[T] = alpha' N 1, con alpha EMPIRICO.

    UNIFICACION (importante): la primera version ponderaba por masa de renglon
    y daba 8.363 para Jardine, mientras `08_ic_derivados.py` daba 6.796 con
    alpha empirico. Son cantidades DISTINTAS -- "duracion desde un estado
    tipico" contra "duracion de una posesion real" -- y tener las dos en el
    mismo reporte sin explicarlo es indefendible. Aqui se usa la misma receta
    que el script 08.
    """
    C = count_matrix(trans, space)
    if C.sum() == 0:
        return None
    Q = mle(C)[:, : space.n_transient]
    if float(np.abs(np.linalg.eigvals(Q)).max()) >= 1.0:
        return None
    N1 = np.linalg.solve(np.eye(space.n_transient) - Q, np.ones(space.n_transient))
    return float(_alpha(trans, space) @ N1)


def _boot_delta(A: pl.DataFrame, B: pl.DataFrame, space: StateSpace,
                n_boot: int, rng) -> tuple[float, float] | None:
    """IC bootstrap por POSESION del delta porcentual de E[T].

    Sin esto, un delta del +50% sobre un nucleo del 21% de la muestra parece
    un hallazgo. Con el IC se ve que es ruido.
    """
    ua = A["poss_uid"].unique().sort().to_numpy()
    ub = B["poss_uid"].unique().sort().to_numpy()
    if len(ua) < 20 or len(ub) < 20:
        return None
    reps = []
    for _ in range(n_boot):
        sa = A.filter(pl.col("poss_uid").is_in(rng.choice(ua, len(ua)).tolist()))
        sb = B.filter(pl.col("poss_uid").is_in(rng.choice(ub, len(ub)).tolist()))
        ea, eb = E_T(sa, space), E_T(sb, space)
        if ea and eb:
            reps.append((ea / eb - 1) * 100)
    if len(reps) < n_boot // 2:
        return None
    return float(np.percentile(reps, 2.5)), float(np.percentile(reps, 97.5))


def tv_ponderada(Ca: np.ndarray, Cb: np.ndarray) -> float:
    Pa, Pb = _fila(Ca, Ca.shape[1]), _fila(Cb, Cb.shape[1])
    w = Ca.sum(axis=1) + Cb.sum(axis=1)
    w = w / max(w.sum(), _EPS)
    return float(((0.5 * np.abs(Pa - Pb).sum(axis=1)) * w).sum())


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--unit", default="coach")
    ap.add_argument("--a", required=True, help="era focal (la posterior)")
    ap.add_argument("--b", required=True, help="era de contraste (la anterior)")
    ap.add_argument("--club", required=True)
    ap.add_argument("--min-frac-nucleo", type=float, default=0.5,
                    help="fraccion minima de acciones de una posesion "
                         "ejecutadas por el nucleo para conservarla (nivel 2)")
    ap.add_argument("--min-por-era", type=int, default=200,
                    help="transiciones minimas por jugador y era (nivel 3)")
    ap.add_argument("--n-boot-ic", type=int, default=300,
                    help="replicas para el IC del delta del nivel 2")
    ap.add_argument("--n-perm", type=int, default=500,
                    help="permutaciones para la nula del nivel 3")
    ap.add_argument("--seed", type=int, default=11235)
    ap.add_argument("--out", default="reports/confusion_plantel.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)
    if "player_id" not in trans.columns:
        sys.exit(
            "transitions.parquet no trae `player_id`.\n"
            "  Aplica el parche a possessions.py y vuelve a correr phase0."
        )

    # NO filtrar por player_id aqui. Las filas de ABSORCION TERMINAL tienen
    # player_id = null por construccion (son transiciones artificiales sin
    # ejecutante, ADR-14). Excluirlas hace que las posesiones no absorban: Q
    # retiene masa y N = (I-Q)^-1 se infla.
    #
    # Sintoma real: con el filtro puesto, E[T] de Jardine salia 8.834 contra
    # 6.796 del script 08. Un 30% de inflacion que los cocientes ocultaban
    # porque afectaba a las dos eras por igual.
    #
    # El filtro de jugador se aplica SOLO donde hace falta atribucion
    # (niveles 1 y 3); para E[T] se conservan las terminales.
    club = trans.filter(pl.col("team") == args.club)
    A = club.filter(pl.col(args.unit) == args.a)
    B = club.filter(pl.col(args.unit) == args.b)
    ES_TERMINAL = pl.col("player_id").is_null()
    for nom, df in ((args.a, A), (args.b, B)):
        if df.height == 0:
            sys.exit(f"Sin transiciones con jugador para '{nom}'")

    # ===================================================================
    # NIVEL 1 — solapamiento de plantilla
    # ===================================================================
    # Para atribucion: solo filas con ejecutante.
    Ap = A.filter(~ES_TERMINAL)
    Bp = B.filter(~ES_TERMINAL)
    ja = set(Ap["player_id"].unique().to_list())
    jb = set(Bp["player_id"].unique().to_list())
    compartidos = ja & jb

    acc_a = Ap.group_by("player_id").len().rename({"len": "n"})
    acc_b = Bp.group_by("player_id").len().rename({"len": "n"})
    tot_a, tot_b = Ap.height, Bp.height
    her_a = int(acc_a.filter(pl.col("player_id").is_in(list(compartidos)))["n"].sum())
    her_b = int(acc_b.filter(pl.col("player_id").is_in(list(compartidos)))["n"].sum())

    n1 = {
        "jugadores_en_a": len(ja), "jugadores_en_b": len(jb),
        "compartidos": len(compartidos),
        "jaccard_plantilla": round(len(compartidos) / max(len(ja | jb), 1), 4),
        "pct_acciones_de_a_por_compartidos": round(100 * her_a / max(tot_a, 1), 1),
        "pct_acciones_de_b_por_compartidos": round(100 * her_b / max(tot_b, 1), 1),
    }

    print(f"=== {args.a}  vs  {args.b}   ({args.club}) ===")
    print(f"    nivel 2: posesiones con >= {args.min_frac_nucleo:.0%} de acciones "
          f"del nucleo\n")
    print("== NIVEL 1: solapamiento de plantilla ==")
    print(f"  jugadores en {args.a:<18}: {n1['jugadores_en_a']}")
    print(f"  jugadores en {args.b:<18}: {n1['jugadores_en_b']}")
    print(f"  compartidos                      : {n1['compartidos']}"
          f"   (Jaccard {n1['jaccard_plantilla']:.3f})")
    print(f"  acciones de {args.a} por compartidos: "
          f"{n1['pct_acciones_de_a_por_compartidos']:.1f}%")
    print(f"  acciones de {args.b} por compartidos: "
          f"{n1['pct_acciones_de_b_por_compartidos']:.1f}%")

    # ===================================================================
    # NIVEL 2 — nucleo estable
    # ===================================================================
    def _posesiones_nucleo(df: pl.DataFrame, frac_min: float) -> tuple[pl.DataFrame, int, int]:
        """Posesiones COMPLETAS donde el nucleo ejecuto >= frac_min de acciones."""
        con_jug = df.filter(~ES_TERMINAL)
        frac = (
            con_jug.group_by("poss_uid")
            .agg(pl.col("player_id").is_in(list(compartidos)).mean().alias("f"))
        )
        # .to_list(): pasar una Series a is_in esta deprecado en polars >=1.4
        keep = frac.filter(pl.col("f") >= frac_min)["poss_uid"].to_list()
        return (df.filter(pl.col("poss_uid").is_in(keep)),
                len(keep), df["poss_uid"].n_unique())

    Ac, kpa, tpa = _posesiones_nucleo(A, args.min_frac_nucleo)
    Bc, kpb, tpb = _posesiones_nucleo(B, args.min_frac_nucleo)

    def _sesgo_longitud(df: pl.DataFrame, sub: pl.DataFrame) -> dict:
        """Longitud media de las posesiones RETENIDAS vs DESCARTADAS.

        EL PROBLEMA QUE DETECTA (length-biased sampling)
        ------------------------------------------------
        Exigir que el nucleo ejecute una fraccion alta de las acciones de una
        posesion NO selecciona "posesiones del nucleo": selecciona POSESIONES
        CORTAS. Una posesion de 3 acciones tiene alta probabilidad de ser toda
        del nucleo; una de 15, casi ninguna.

        Y la longitud es justo la variable que se esta midiendo. Es
        circularidad: se condiciona la retencion al valor de la respuesta.

        Observado con --min-frac-nucleo 0.9:
            Jardine  E[T] 6.796 -> 4.151  (-39%)
            Ortiz    E[T] 6.298 -> 6.109  ( -3%)
            delta    +7.90% -> -24.28%   EL SIGNO SE INVIERTE

        Un filtro mas estricto NO es mas riguroso. Aqui es demostrablemente
        peor, y el barrido de umbrales es lo que lo demuestra.
        """
        largos = df.group_by("poss_uid").len().rename({"len": "L"})
        keep = set(sub["poss_uid"].unique().to_list())
        ret = largos.filter(pl.col("poss_uid").is_in(list(keep)))["L"]
        des = largos.filter(~pl.col("poss_uid").is_in(list(keep)))["L"]
        mr = float(ret.mean()) if ret.len() else float("nan")
        md = float(des.mean()) if des.len() else float("nan")
        return {"len_retenidas": round(mr, 3), "len_descartadas": round(md, 3),
                "sesgo_pct": round((mr / md - 1) * 100, 2) if des.len() and md else 0.0}

    sesgo_a = _sesgo_longitud(A, Ac)
    sesgo_b = _sesgo_longitud(B, Bc)
    # Lo peligroso no es el sesgo absoluto -- si las dos eras pierden
    # posesiones largas por igual, se cancela en el cociente -- sino el
    # DIFERENCIAL entre eras.
    sesgo_dif = abs(sesgo_a["sesgo_pct"] - sesgo_b["sesgo_pct"])
    SESGO_MAX = 10.0

    et_a, et_b = E_T(A, space), E_T(B, space)
    et_ac, et_bc = E_T(Ac, space), E_T(Bc, space)
    tv_todo = tv_ponderada(count_matrix(A, space), count_matrix(B, space))
    tv_nuc = tv_ponderada(count_matrix(Ac, space), count_matrix(Bc, space))

    def pct(x, y):
        return round((x / y - 1) * 100, 2) if x and y else None

    # Cobertura = POSESIONES retenidas. Medirla en transiciones era parte del
    # mismo error: la unidad del nivel 2 es la posesion.
    cob_a = 100 * kpa / max(tpa, 1)
    cob_b = 100 * kpb / max(tpb, 1)
    COB_MIN = 35.0
    nucleo_fiable = cob_a >= COB_MIN and cob_b >= COB_MIN

    n2 = {
        "E_T_a_total": round(et_a, 4) if et_a else None,
        "E_T_b_total": round(et_b, 4) if et_b else None,
        "delta_pct_total": pct(et_a, et_b),
        "E_T_a_nucleo": round(et_ac, 4) if et_ac else None,
        "E_T_b_nucleo": round(et_bc, 4) if et_bc else None,
        "delta_pct_nucleo": pct(et_ac, et_bc),
        "tv_total": round(tv_todo, 5),
        "tv_nucleo": round(tv_nuc, 5),
        "n_trans_nucleo_a": Ac.height, "n_trans_nucleo_b": Bc.height,
        "n_terminales_a": A.filter(ES_TERMINAL).height,
        "n_terminales_b": B.filter(ES_TERMINAL).height,
        "posesiones_retenidas_a": kpa, "posesiones_totales_a": tpa,
        "posesiones_retenidas_b": kpb, "posesiones_totales_b": tpb,
        "min_frac_nucleo": args.min_frac_nucleo,
        "sesgo_longitud_a": sesgo_a, "sesgo_longitud_b": sesgo_b,
        "sesgo_longitud_diferencial_pp": round(sesgo_dif, 2),
        "sesgo_longitud_tolerable": bool(sesgo_dif <= SESGO_MAX),
        "cobertura_nucleo_a_pct": round(cob_a, 1),
        "cobertura_nucleo_b_pct": round(cob_b, 1),
        "nucleo_fiable": bool(nucleo_fiable),
        "umbral_cobertura_pct": COB_MIN,
    }
    rng2 = np.random.default_rng(args.seed)
    ic_tot = _boot_delta(A, B, space, args.n_boot_ic, rng2)
    ic_nuc = _boot_delta(Ac, Bc, space, args.n_boot_ic, rng2)
    if ic_tot:
        n2["ic_delta_total"] = [round(ic_tot[0], 2), round(ic_tot[1], 2)]
    if ic_nuc:
        n2["ic_delta_nucleo"] = [round(ic_nuc[0], 2), round(ic_nuc[1], 2)]
    if n2["delta_pct_total"] and n2["delta_pct_nucleo"]:
        n2["fraccion_del_efecto_que_sobrevive"] = round(
            n2["delta_pct_nucleo"] / n2["delta_pct_total"], 3)

    print("\n== NIVEL 2: solo el nucleo estable ==")
    print(f"  {'':<22} {'todos':>10} {'nucleo':>10}")
    def _f(x):
        # None significa "rho(Q) >= 1: la cadena no absorbe". Imprimirlo como
        # 0.000 lo disfrazaba de valor valido -- exactamente el tipo de numero
        # plausible pero falso que este proyecto persigue.
        return f"{x:>10.3f}" if x is not None else f"{'n/d':>10}"

    print(f"  {'E[T] ' + args.a:<22} {_f(n2['E_T_a_total'])} {_f(n2['E_T_a_nucleo'])}")
    print(f"  {'E[T] ' + args.b:<22} {_f(n2['E_T_b_total'])} {_f(n2['E_T_b_nucleo'])}")
    print(f"  {'diferencia %':<22} {_f(n2['delta_pct_total'])} "
          f"{_f(n2['delta_pct_nucleo'])}")
    print(f"  {'TV entre eras':<22} {n2['tv_total']:>10.5f} {n2['tv_nucleo']:>10.5f}")
    if ic_tot:
        print(f"  {'IC 95% del delta':<22} "
              f"[{ic_tot[0]:+.2f}, {ic_tot[1]:+.2f}]".rjust(11), end="")
        print(f"  [{ic_nuc[0]:+.2f}, {ic_nuc[1]:+.2f}]" if ic_nuc else "  (n/d)")
    print(f"  {'posesiones retenidas':<22} {kpa:>6}/{tpa:<3} {kpb:>6}/{tpb:<3}")
    print(f"  {'cobertura (posesiones)':<22} {cob_a:>9.1f}% {cob_b:>9.1f}%")
    print(f"  {'long. retenidas':<22} {sesgo_a['len_retenidas']:>9.2f} "
          f"{sesgo_b['len_retenidas']:>9.2f}")
    print(f"  {'long. descartadas':<22} {sesgo_a['len_descartadas']:>9.2f} "
          f"{sesgo_b['len_descartadas']:>9.2f}")
    print(f"  {'sesgo de longitud':<22} {sesgo_a['sesgo_pct']:>+8.1f}% "
          f"{sesgo_b['sesgo_pct']:>+8.1f}%")

    if "fraccion_del_efecto_que_sobrevive" in n2:
        f = n2["fraccion_del_efecto_que_sobrevive"]
        print(f"\n  El {f:.0%} del efecto sobrevive al restringir al nucleo.")
    if sesgo_dif > SESGO_MAX:
        print(f"\n  [ALERTA] SESGO DE LONGITUD DIFERENCIAL: {sesgo_dif:.1f} puntos")
        print(f"  porcentuales entre las dos eras (maximo tolerado {SESGO_MAX:.0f}).")
        print("  El filtro esta reteniendo posesiones de longitud MUY distinta en")
        print("  cada era, y la longitud es la variable que se mide: el resultado")
        print("  es CIRCULAR (length-biased sampling) y no tiene validez.")
        print("  Baja --min-frac-nucleo. Un filtro mas estricto NO es mas riguroso.")
    elif max(abs(sesgo_a["sesgo_pct"]), abs(sesgo_b["sesgo_pct"])) > 15.0:
        print(f"\n  [aviso] hay sesgo de longitud en ambas eras pero es SIMILAR")
        print(f"  ({sesgo_dif:.1f} pp de diferencia): se cancela en buena medida en")
        print("  el cociente. Declararlo, pero el delta sigue siendo interpretable.")

    if not nucleo_fiable:
        print(f"\n  [AVISO] el nucleo cubre {min(cob_a, cob_b):.1f}% de una de las")
        print(f"  eras, por debajo del {COB_MIN:.0f}% minimo. NO es un nucleo estable:")
        print("  es una submuestra chica y probablemente sesgada por puesto. El")
        print("  delta del nucleo NO es interpretable como efecto tactico.")
        print("\n  CUIDADO: un IC ESTRECHO aqui no lo rescata. El bootstrap mide")
        print("  varianza de muestreo, NO sesgo de seleccion. Los jugadores que")
        print("  sobreviven a una reconstruccion de plantilla no son una muestra")
        print("  aleatoria del equipo anterior: estan concentrados por puesto.")
        print("  Un intervalo estrecho alrededor de un estimador sesgado sigue")
        print("  estando sesgado.")

    # ===================================================================
    # NIVEL 3 — intra-jugador
    # ===================================================================
    ca = Ap.group_by("player_id").len().rename({"len": "na"})
    cb = Bp.group_by("player_id").len().rename({"len": "nb"})
    elegibles = (
        ca.join(cb, on="player_id")
        .filter((pl.col("na") >= args.min_por_era) & (pl.col("nb") >= args.min_por_era))
        .sort("na", descending=True)
    )

    rng = np.random.default_rng(args.seed)
    filas3 = []
    for row in elegibles.iter_rows(named=True):
        pid = row["player_id"]
        pa = Ap.filter(pl.col("player_id") == pid)
        pb = Bp.filter(pl.col("player_id") == pid)
        Cpa, Cpb = count_matrix(pa, space), count_matrix(pb, space)
        tv_obs = tv_ponderada(Cpa, Cpb)

        # Nula: mezclar las transiciones del jugador entre las dos eras.
        # Si su comportamiento NO cambio, las etiquetas de era son
        # intercambiables. Sin esta nula, TV > 0 siempre y no diria nada
        # (ADR-30).
        todo = pl.concat([pa, pb])
        marca = np.array([0] * pa.height + [1] * pb.height)
        nul = np.empty(args.n_perm)
        for k in range(args.n_perm):
            m = rng.permutation(marca)
            nul[k] = tv_ponderada(
                count_matrix(todo.filter(pl.Series(m == 0)), space),
                count_matrix(todo.filter(pl.Series(m == 1)), space))
        pv = float((1.0 + (nul >= tv_obs).sum()) / (1.0 + args.n_perm))
        nombre = pa["player"][0] if "player" in pa.columns and pa.height else str(pid)
        filas3.append({
            "player_id": int(pid), "player": nombre,
            "n_a": int(row["na"]), "n_b": int(row["nb"]),
            "tv_obs": round(tv_obs, 4),
            "tv_nula_mediana": round(float(np.median(nul)), 4),
            "tv_exceso": round(tv_obs - float(np.median(nul)), 4),
            "p_valor": pv, "cambio": bool(pv < 0.05),
        })

    # Multiplicidad: con 17 jugadores a alpha=0.05 se espera ~1 falso positivo
    # por azar. Mismo criterio que ADR-09 y ADR-29.
    if filas3:
        qv, rej = benjamini_hochberg(
            np.array([f["p_valor"] for f in filas3]), 0.05)
        for f, q, r in zip(filas3, qv, rej):
            f["q_valor"] = round(float(q), 4)
            f["cambio"] = bool(r)

    print(f"\n== NIVEL 3: el MISMO jugador bajo los dos DT ==")
    print(f"   (jugadores con >= {args.min_por_era} transiciones en cada era)\n")
    if filas3:
        print(f"  {'jugador':<34} {'n_a':>6} {'n_b':>6} {'TV':>7} {'ruido':>7} "
              f"{'exceso':>7} {'p':>7} {'q(BH)':>7}  cambio")
        print("  " + "-" * 96)
        for f in filas3:
            print(f"  {f['player'][:33]:<34} {f['n_a']:>6} {f['n_b']:>6} "
                  f"{f['tv_obs']:>7.4f} {f['tv_nula_mediana']:>7.4f} "
                  f"{f['tv_exceso']:>7.4f} {f['p_valor']:>7.4f} "
                  f"{f.get('q_valor', float('nan')):>7.4f}  "
                  f"{'SI' if f['cambio'] else 'no'}")
        n_cambio = sum(f["cambio"] for f in filas3)
        esperados = 0.05 * len(filas3)
        print(f"\n  {n_cambio} de {len(filas3)} jugadores cambian tras control de "
              f"FDR (BH, 5%).")
        print(f"  Por azar se esperarian ~{esperados:.1f} sin correccion.")
    else:
        print(f"  Ningun jugador alcanza {args.min_por_era} transiciones en ambas "
              "eras.\n  Baja --min-por-era o las eras son demasiado disjuntas.")

    res = {"a": args.a, "b": args.b, "club": args.club,
           "nivel1_solapamiento": n1, "nivel2_nucleo": n2,
           "nivel3_intra_jugador": filas3}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")

    # ===================================================================
    print("\n== COMO REDACTARLO ==")
    sol = n1["pct_acciones_de_a_por_compartidos"]
    if sol >= 60:
        print(f"  Solapamiento ALTO ({sol:.0f}%): la critica del plantel se debilita")
        print("  sola. Frase: 'X heredo el {:.0f}% de las acciones del plantel"
              " anterior".format(sol))
        print("  y aun asi el equipo circula distinto'.")
    elif sol >= 35:
        print(f"  Solapamiento MEDIO ({sol:.0f}%): hay que apoyarse en los niveles")
        print("  2 y 3. El nivel 1 solo no basta.")
    else:
        print(f"  Solapamiento BAJO ({sol:.0f}%): la critica es FUERTE. Sin el")
        print("  nivel 3 no se puede atribuir el efecto al entrenador.")
    print("\n  El NIVEL 3 es el argumento decisivo: si el mismo jugador se")
    print("  comporta distinto bajo dos DT, eso no es el jugador.")
    print("\n  LIMITACION QUE NO DESAPARECE: aunque el jugador sea el mismo, sus")
    print("  companeros, su posicion y el rival cambian. El nivel 3 acota mucho")
    print("  la critica pero no la elimina. Hay que decirlo en el reporte.")


if __name__ == "__main__":
    main()
