#!/usr/bin/env python3
"""
19_presion_por_indice.py — por que Jardine presiona mas Y concede mas.

LA PARADOJA
-----------
Dos estimadores de la MISMA cantidad dan signos opuestos:

    ponderado por POSESION (script 16): Jardine 0.2373 vs Solari 0.2249  -> +1.24 pp
    ponderado por ACCION   (script 18): Jardine 0.2060 vs Solari 0.2116  -> -0.56 pp

No es un bug: son dos estimandos. El primero da el mismo peso a cada posesion
rival; el segundo a cada accion, asi que las posesiones largas dominan.

LA IDENTIDAD QUE LO EXPLICA
---------------------------
Sea L_p la longitud de la posesion rival p y m_p su tasa media de presion.

    pi_accion   = sum_p L_p m_p / sum_p L_p     (media ponderada por L)
    pi_posesion = (1/P) sum_p m_p               (media simple)

y por la formula de la media ponderada,

    pi_accion - pi_posesion = Cov(L, m) / E[L]

EXACTAMENTE. La inversion de signo no es un misterio de ponderacion: es esa
covarianza. Si Cov(L, m) < 0, las posesiones largas del rival estan MENOS
presionadas, y cuanto mas negativa, mayor la brecha entre los dos estimadores.

Este script la calcula, la descompone por indice de accion, y contrasta si la
diferencia entre eras es mayor que la nula por permutacion.

LA HIPOTESIS FUTBOLISTICA
-------------------------
Si pi_e(k) cae mas rapido con k bajo un entrenador, su presion es INICIAL pero
no SOSTENIDA: aprieta la salida y, cuando el rival la supera, lo deja circular.
Eso reconcilia "presiona mas por posesion" con "concede posesiones mas largas"
sin necesidad de invocar nada mas.

REMUESTREO
----------
Bootstrap por PARTIDO, no por posesion. El diagnostico de Cochran dio
phi ~ 1.7-1.8 sobre partidos mientras el bootstrap por posesion solo inflaba el
IC un 1.09x: parte de la correlacion es de nivel partido (mismo rival, misma
alineacion, mismo estado de campo) y remuestrear posesiones no la captura.
Ademas la unidad de asignacion del "tratamiento" -- el entrenador -- es el
partido. La permutacion ya era a ese nivel; el bootstrap se alinea.

Uso:
  python scripts/19_presion_por_indice.py --club "América" \
      --a "Andre Jardine" --b "Santiago Solari" --figura
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

try:
    from dtdecoder.config import Config
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


def acciones(trans: pl.DataFrame, club: str) -> pl.DataFrame:
    """Acciones rivales con su indice DENTRO de la posesion (k = 1, 2, ...)."""
    for c in ("coach_faced", "under_pressure"):
        if c not in trans.columns:
            sys.exit(f"Falta `{c}`. Corre phase0 con --club tras el parche D0.")

    sub = (trans.filter((pl.col("team") != club)
                        & (pl.col("action_type") != "TERMINAL")
                        & pl.col("coach_faced").is_not_null())
                .sort(["poss_uid", "event_index"]))
    if sub.height == 0:
        sys.exit(f"Sin acciones rivales para club={club!r}.")
    return sub.with_columns(
        (pl.int_range(pl.len()).over("poss_uid") + 1).alias("k"),
        pl.col("under_pressure").fill_null(False).cast(pl.Int8).alias("presion"),
        pl.col("coach_faced").alias("era"),
    ).select(["poss_uid", "match_id", "era", "k", "presion"])


def por_posesion(acc: pl.DataFrame) -> pl.DataFrame:
    """Una fila por posesion: longitud L y tasa media de presion m."""
    return acc.group_by("poss_uid").agg(
        pl.col("era").first(), pl.col("match_id").first(),
        pl.len().alias("L"), pl.col("presion").mean().alias("m"),
    )


def descomposicion(pos: pl.DataFrame, era: str) -> dict:
    """La identidad pi_accion - pi_posesion = Cov(L, m) / E[L]."""
    s = pos.filter(pl.col("era") == era)
    L = s["L"].to_numpy().astype(float)
    m = s["m"].to_numpy().astype(float)
    pi_pos = float(m.mean())
    pi_acc = float((L * m).sum() / max(L.sum(), _EPS))
    cov = float(((L - L.mean()) * (m - m.mean())).mean())
    return {
        "n_posesiones": int(len(L)), "n_acciones": int(L.sum()),
        "E_L": float(L.mean()),
        "pi_por_posesion": pi_pos, "pi_por_accion": pi_acc,
        "brecha": pi_acc - pi_pos,
        "cov_L_m": cov, "cov_sobre_EL": cov / max(L.mean(), _EPS),
        "corr_L_m": float(np.corrcoef(L, m)[0, 1]) if len(L) > 2 else float("nan"),
    }


def curva(acc: pl.DataFrame, era: str, kmax: int, min_n: int) -> tuple:
    """pi_e(k) para k = 1..kmax, con el n de cada punto."""
    g = (acc.filter(pl.col("era") == era)
            .group_by("k").agg(pl.col("presion").mean().alias("pi"),
                               pl.len().alias("n")).sort("k"))
    pi = np.full(kmax, np.nan); n = np.zeros(kmax, dtype=int)
    for r in g.to_dicts():
        if 1 <= r["k"] <= kmax:
            pi[r["k"] - 1] = r["pi"]; n[r["k"] - 1] = r["n"]
    pi[n < min_n] = np.nan
    return pi, n


def pendiente(acc: pl.DataFrame, era: str, kmax: int, min_n: int,
              kmin: int = 2) -> float:
    """Pendiente OLS de pi contra k, ponderada por n, AJUSTADA DESDE kmin.

    POR QUE kmin = 2 POR DEFECTO
    ----------------------------
    pi(1) ~ 0.15 y pi(2) ~ 0.26: la PRIMERA accion es la menos presionada de
    todas, con diferencia. Tiene sentido futbolistico -- muchas posesiones
    rivales nacen de saque de meta, banda o falta, con el balon parado y sin
    presion que anotar -- pero rompe la linealidad.

    Ajustar una recta a una curva que SUBE y luego BAJA convierte k=1 en un
    punto de palanca que sesga la pendiente hacia arriba. La pendiente medida
    desde k=1 no estima el decaimiento: estima una mezcla de la subida inicial
    y el decaimiento posterior.

    Desde kmin = 2 el estimando es "decaimiento de la presion en juego
    abierto", que es lo que se quiere contrastar.
    """
    pi, n = curva(acc, era, kmax, min_n)
    ok = np.isfinite(pi) & (n > 0)
    ok[:max(kmin - 1, 0)] = False
    if ok.sum() < 3:
        return float("nan")
    k = np.arange(1, kmax + 1)[ok]
    w = n[ok].astype(float)
    kb = np.average(k, weights=w); pb = np.average(pi[ok], weights=w)
    return float((w * (k - kb) * (pi[ok] - pb)).sum() /
                 max((w * (k - kb) ** 2).sum(), _EPS))


def boot_partido(acc: pl.DataFrame, era: str, kmax: int, min_n: int,
                 n_boot: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """IC de pi_e(k) remuestreando PARTIDOS (ver docstring del modulo)."""
    s = acc.filter(pl.col("era") == era)
    mids = s["match_id"].unique().sort().to_numpy()
    porm = {m: g for (m,), g in s.group_by(["match_id"])}
    rng = np.random.default_rng(seed)
    reps = np.full((n_boot, kmax), np.nan)
    for t in range(n_boot):
        elegidos = rng.choice(mids, size=len(mids), replace=True)
        d = pl.concat([porm[m] for m in elegidos])
        pi, n = curva(d.with_columns(pl.lit(era).alias("era")), era, kmax, min_n)
        reps[t] = pi
    with np.errstate(invalid="ignore"):
        return (np.nanquantile(reps, 0.025, axis=0),
                np.nanquantile(reps, 0.975, axis=0))


def nula_pendiente(acc: pl.DataFrame, a: str, b: str, kmax: int, min_n: int,
                   n_perm: int, seed: int, kmin: int = 2) -> tuple[float, float]:
    """Nula por permutacion de la etiqueta de era ENTRE PARTIDOS.

    `coach_faced` es propiedad del partido: permutar acciones destruiria la
    correlacion intra-partido y daria una nula demasiado angosta.
    """
    sub = acc.filter(pl.col("era").is_in([a, b]))
    partidos = sub.group_by("match_id").agg(pl.col("era").first())
    mid = partidos["match_id"].to_numpy(); e0 = partidos["era"].to_numpy()
    pos = {m: i for i, m in enumerate(mid)}
    idx = np.array([pos[m] for m in sub["match_id"].to_numpy()])
    kk = sub["k"].to_numpy(); pp = sub["presion"].to_numpy()

    def pend(mask) -> float:
        d = pl.DataFrame({"k": kk[mask], "presion": pp[mask],
                          "era": np.full(mask.sum(), "x")})
        return pendiente(d, "x", kmax, min_n, kmin)

    obs = pend(e0[idx] == a) - pend(e0[idx] == b)
    rng = np.random.default_rng(seed)
    nulo = np.empty(n_perm)
    for t in range(n_perm):
        e = rng.permutation(e0)
        es_a = (e[idx] == a)
        nulo[t] = pend(es_a) - pend(~es_a)
    p = (1.0 + (np.abs(nulo) >= abs(obs)).sum()) / (1.0 + n_perm)
    return float(obs), float(p)


BUCKETS = [(1, 1), (2, 2), (3, 3), (4, 5), (6, 7), (8, 10), (11, 10**9)]


def _bucket(L: np.ndarray) -> np.ndarray:
    out = np.zeros(len(L), dtype=int)
    for i, (lo, hi) in enumerate(BUCKETS):
        out[(L >= lo) & (L <= hi)] = i
    return out


def kitagawa(pos: pl.DataFrame, a: str, b: str) -> dict:
    """Descompone la diferencia de pi POR POSESION en dos partes exactas.

    LA PARADOJA DE SIMPSON, HECHA ARITMETICA
    ----------------------------------------
    Si pi_e(k) es identica entre dos eras pero una tiene posesiones rivales mas
    largas, su pi por accion baja sin que nadie haya cambiado como presiona.
    Pero el pi por POSESION tambien puede moverse por composicion, y en
    direccion contraria. Hay que separar las dos causas.

    Sea w_{e,L} la proporcion de posesiones de longitud L bajo la era e, y
    m_{e,L} la presion media dentro de ellas. Con pesos y niveles promediados,

        Delta = sum_L wbar_L (m_A,L - m_B,L)      <- EFECTO DENTRO
              + sum_L (w_A,L - w_B,L) mbar_L      <- COMPOSICION

    y la suma es EXACTAMENTE la diferencia observada (descomposicion de
    Kitagawa / Oaxaca-Blinder).

    Si casi todo cae en composicion, "presiona mas" es un artefacto de que el
    rival conserva mas el balon, no una diferencia de comportamiento, y el
    titular se archiva. Si cae en el efecto dentro, hay una diferencia real de
    nivel a longitud fija.
    """
    out = {}
    tab = {}
    for e in (a, b):
        s = pos.filter(pl.col("era") == e)
        L = s["L"].to_numpy().astype(float)
        m = s["m"].to_numpy().astype(float)
        bk = _bucket(L)
        w = np.array([(bk == i).mean() for i in range(len(BUCKETS))])
        mm = np.array([m[bk == i].mean() if (bk == i).any() else np.nan
                       for i in range(len(BUCKETS))])
        nn = np.array([int((bk == i).sum()) for i in range(len(BUCKETS))])
        tab[e] = {"w": w, "m": mm, "n": nn}

    wA, wB = tab[a]["w"], tab[b]["w"]
    mA, mB = tab[a]["m"], tab[b]["m"]
    ok = np.isfinite(mA) & np.isfinite(mB)
    wbar = (wA + wB) / 2.0
    mbar = np.where(ok, (mA + mB) / 2.0, 0.0)

    dentro = float((wbar[ok] * (mA[ok] - mB[ok])).sum())
    comp = float(((wA - wB) * mbar).sum())
    total = float(tab[a]["m"][np.isfinite(mA)] @ wA[np.isfinite(mA)] -
                  tab[b]["m"][np.isfinite(mB)] @ wB[np.isfinite(mB)])

    out["buckets"] = [
        {"rango": f"{lo}-{hi if hi < 10**9 else '+'}",
         "w_a": float(wA[i]), "w_b": float(wB[i]),
         "m_a": float(mA[i]) if np.isfinite(mA[i]) else None,
         "m_b": float(mB[i]) if np.isfinite(mB[i]) else None,
         "n_a": int(tab[a]["n"][i]), "n_b": int(tab[b]["n"][i])}
        for i, (lo, hi) in enumerate(BUCKETS)
    ]
    out["efecto_dentro"] = dentro
    out["composicion"] = comp
    out["total"] = total
    out["error_identidad"] = abs((dentro + comp) - total)
    out["frac_composicion"] = comp / total if abs(total) > 1e-12 else float("nan")
    return out


def nula_kitagawa(pos: pl.DataFrame, a: str, b: str, n_perm: int,
                  seed: int) -> float:
    """p del EFECTO DENTRO por permutacion de la etiqueta entre partidos."""
    sub = pos.filter(pl.col("era").is_in([a, b]))
    part = sub.group_by("match_id").agg(pl.col("era").first())
    mid = part["match_id"].to_numpy(); e0 = part["era"].to_numpy()
    idx = {m: i for i, m in enumerate(mid)}
    ii = np.array([idx[m] for m in sub["match_id"].to_numpy()])
    L = sub["L"].to_numpy().astype(float)
    m = sub["m"].to_numpy().astype(float)
    obs = kitagawa(pos, a, b)["efecto_dentro"]

    rng = np.random.default_rng(seed)
    nulo = np.empty(n_perm)
    for t in range(n_perm):
        e = rng.permutation(e0)[ii]
        d = pl.DataFrame({"era": e, "L": L, "m": m,
                          "match_id": np.zeros(len(L), dtype=np.int64),
                          "poss_uid": np.arange(len(L)).astype(str)})
        nulo[t] = kitagawa(d, a, b)["efecto_dentro"]
    return float((1.0 + (np.abs(nulo) >= abs(obs)).sum()) / (1.0 + n_perm))


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--club", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--indir", default=None)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--kmax", type=int, default=12)
    ap.add_argument("--kmin", type=int, default=2,
                    help="primer indice del ajuste de la pendiente. k=1 es la "
                         "accion menos presionada (balon parado) y sesga el "
                         "ajuste: ver docstring de `pendiente`.")
    ap.add_argument("--min-n", type=int, default=200, dest="min_n")
    ap.add_argument("--n-boot", type=int, default=500, dest="n_boot")
    ap.add_argument("--n-perm", type=int, default=1000, dest="n_perm")
    ap.add_argument("--figura", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = Config.load(args.config)
    indir = args.indir or ("data/processed" if args.club == "América"
                           else "data/processed_cruzazul")
    trans = pl.read_parquet(Path(indir) / "transitions.parquet")
    acc = acciones(trans, args.club)
    pos = por_posesion(acc)

    for e in (args.a, args.b):
        if acc.filter(pl.col("era") == e).height == 0:
            sys.exit(f"Era desconocida: {e!r}. "
                     f"Disponibles: {sorted(acc['era'].unique().to_list())}")

    print(f"club {args.club!r} · {acc.height:,} acciones rivales\n")

    # ---------------------------------------------------- la identidad
    print("=" * 88)
    print(" LA IDENTIDAD:  pi_accion - pi_posesion = Cov(L, m) / E[L]")
    print("=" * 88)
    d = {e: descomposicion(pos, e) for e in (args.a, args.b)}
    print(f"  {'era':<22} {'E[L]':>6} {'pi_pos':>8} {'pi_acc':>8} "
          f"{'brecha':>8} {'Cov/E[L]':>9} {'corr':>7}")
    print("  " + "-" * 76)
    for e in (args.a, args.b):
        x = d[e]
        print(f"  {e:<22} {x['E_L']:6.2f} {x['pi_por_posesion']:8.4f} "
              f"{x['pi_por_accion']:8.4f} {x['brecha']:+8.4f} "
              f"{x['cov_sobre_EL']:+9.4f} {x['corr_L_m']:+7.3f}")
    err = max(abs(d[e]["brecha"] - d[e]["cov_sobre_EL"]) for e in (args.a, args.b))
    print(f"\n  error maximo de la identidad: {err:.2e}  (debe ser ~0)")

    da = d[args.a]["pi_por_posesion"] - d[args.b]["pi_por_posesion"]
    dc = d[args.a]["pi_por_accion"] - d[args.b]["pi_por_accion"]
    print(f"\n  diferencia por POSESION : {da:+.4f}")
    print(f"  diferencia por ACCION   : {dc:+.4f}")
    if np.sign(da) != np.sign(dc):
        print("  >> EL SIGNO SE INVIERTE. La causa es la covarianza de arriba:")
        peor = args.a if d[args.a]["cov_sobre_EL"] < d[args.b]["cov_sobre_EL"] else args.b
        print(f"     bajo {peor} las posesiones rivales LARGAS estan menos")
        print("     presionadas, asi que al ponderar por accion su pi cae mas.")

    # ---------------------------------------------------- la curva
    print("\n" + "=" * 88)
    print(" pi_e(k): PRESION SEGUN EL INDICE DE LA ACCION EN LA POSESION RIVAL")
    print("=" * 88)
    pa, na = curva(acc, args.a, args.kmax, args.min_n)
    pb, nb = curva(acc, args.b, args.kmax, args.min_n)
    lo_a, hi_a = boot_partido(acc, args.a, args.kmax, args.min_n,
                              args.n_boot, int(cfg["inference"]["boot_seed"]))
    lo_b, hi_b = boot_partido(acc, args.b, args.kmax, args.min_n,
                              args.n_boot, int(cfg["inference"]["boot_seed"]))
    print(f"  {'k':>3} {'pi_a':>7} {'IC95 a':>18} {'pi_b':>7} {'IC95 b':>18} "
          f"{'delta':>8} {'n_a':>7} {'n_b':>7}")
    print("  " + "-" * 84)
    puntos = []
    for i in range(args.kmax):
        if not (np.isfinite(pa[i]) and np.isfinite(pb[i])):
            continue
        sep = "  <<" if (lo_a[i] > hi_b[i] or lo_b[i] > hi_a[i]) else ""
        print(f"  {i+1:>3} {pa[i]:7.4f} [{lo_a[i]:6.4f},{hi_a[i]:6.4f}] "
              f"{pb[i]:7.4f} [{lo_b[i]:6.4f},{hi_b[i]:6.4f}] "
              f"{pa[i]-pb[i]:+8.4f} {na[i]:>7,} {nb[i]:>7,}{sep}")
        puntos.append({"k": i + 1, "pi_a": float(pa[i]), "pi_b": float(pb[i]),
                       "ic_a": [float(lo_a[i]), float(hi_a[i])],
                       "ic_b": [float(lo_b[i]), float(hi_b[i])],
                       "n_a": int(na[i]), "n_b": int(nb[i])})
    print("\n  '<<' marca IC disjuntos. OJO: es una guia visual, NO el contraste.")
    print("  IC disjuntos implican diferencia, pero IC solapados NO implican")
    print("  ausencia de ella. El contraste formal es la pendiente de abajo.")

    # ---------------------------------------------------- la pendiente
    print("\n" + "=" * 88)
    print(" DECAIMIENTO: pendiente de pi contra k, y su nula por permutacion")
    print("=" * 88)
    sa = pendiente(acc, args.a, args.kmax, args.min_n, args.kmin)
    sb = pendiente(acc, args.b, args.kmax, args.min_n, args.kmin)
    obs, pval = nula_pendiente(acc, args.a, args.b, args.kmax, args.min_n,
                               args.n_perm, int(cfg["inference"]["boot_seed"]),
                               args.kmin)
    print(f"  ajuste desde k = {args.kmin} "
          f"(k=1 excluido: es balon parado, no juego abierto)")
    print(f"  pendiente {args.a:<22} {sa:+.5f} pp de presion por accion adicional")
    print(f"  pendiente {args.b:<22} {sb:+.5f}")
    print(f"  diferencia observada          {obs:+.5f}   p = {pval:.4f}"
          f"   ({args.n_perm} permutaciones de etiqueta entre PARTIDOS)")
    if pval <= 0.05:
        mas = args.a if sa < sb else args.b
        print(f"\n  >> La presion de {mas} decae mas rapido dentro de la posesion")
        print("     rival: es INICIAL, no SOSTENIDA. Aprieta la salida y, cuando")
        print("     el rival la supera, lo deja circular. Eso reconcilia")
        print("     'presiona mas por posesion' con 'concede posesiones mas largas'.")
    else:
        print("\n  >> No detectamos una diferencia de decaimiento mayor a la")
        print("     compatible con el azar. La brecha entre los dos estimadores")
        print("     existe igual (la identidad de arriba es exacta), pero no se")
        print("     puede atribuir a un patron de decaimiento distinto.")

    # ------------------------------ Simpson: dentro vs composicion
    print("\n" + "=" * 88)
    print(" DESCOMPOSICION DE KITAGAWA: ¿comportamiento o composicion?")
    print("=" * 88)
    kit = kitagawa(pos, args.a, args.b)
    p_kit = nula_kitagawa(pos, args.a, args.b, min(args.n_perm, 500),
                          int(cfg["inference"]["boot_seed"]))
    print(f"  {'longitud':>9} {'w_a':>7} {'w_b':>7} {'m_a':>8} {'m_b':>8} "
          f"{'m_a-m_b':>9} {'n_a':>7} {'n_b':>7}")
    print("  " + "-" * 72)
    for r in kit["buckets"]:
        if r["m_a"] is None or r["m_b"] is None:
            continue
        print(f"  {r['rango']:>9} {r['w_a']:7.3f} {r['w_b']:7.3f} "
              f"{r['m_a']:8.4f} {r['m_b']:8.4f} {r['m_a']-r['m_b']:+9.4f} "
              f"{r['n_a']:>7,} {r['n_b']:>7,}")
    print(f"\n  diferencia total en pi por posesion : {kit['total']:+.4f}")
    print(f"    efecto DENTRO (a longitud fija)    : {kit['efecto_dentro']:+.4f}"
          f"   p = {p_kit:.4f}")
    print(f"    COMPOSICION (mezcla de longitudes) : {kit['composicion']:+.4f}"
          f"   ({kit['frac_composicion']:.0%} del total)")
    print(f"  error de la identidad: {kit['error_identidad']:.2e}  (debe ser ~0)")

    if abs(kit["frac_composicion"]) > 0.7 and p_kit > 0.05:
        print("\n  >> EL TITULAR SE ARCHIVA. A longitud fija no hay diferencia")
        print("     detectable de presion. Lo que se media era que el rival")
        print("     conserva mas el balon, no que se presione distinto.")
        print("     Es la paradoja de Simpson: la variable de confusion es L.")
    elif p_kit <= 0.05:
        print("\n  >> HAY EFECTO DE NIVEL a longitud fija. El titular se")
        print("     reformula acotandolo a los tramos de la tabla donde")
        print("     m_a - m_b es grande, no como afirmacion global.")
    else:
        print("\n  >> No concluyente: ni la composicion domina claramente ni el")
        print("     efecto dentro rechaza. Reportar la tabla, no un titular.")

    res = {"club": args.club, "era_a": args.a, "era_b": args.b,
           "kmax": args.kmax, "kmin": args.kmin, "min_n": args.min_n,
           "remuestreo": "bootstrap por PARTIDO; permutacion por PARTIDO",
           "descomposicion": d,
           "dif_por_posesion": da, "dif_por_accion": dc,
           "signo_se_invierte": bool(np.sign(da) != np.sign(dc)),
           "curva": puntos,
           "pendiente_a": sa, "pendiente_b": sb,
           "dif_pendiente": obs, "p_permutacion": pval,
           "kitagawa": kit, "p_efecto_dentro": p_kit,
           "familia_fdr": "pi_e(z) — ADR-47, corregir junto con el resto al final"}
    out = Path(args.out or f"reports/presion_indice_"
               f"{args.a.lower().replace(' ','')}_{args.b.lower().replace(' ','')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(f"\nescrito: {out}")

    if args.figura:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        k = np.arange(1, args.kmax + 1)
        fig, ax = plt.subplots(figsize=(7, 4.2))
        for pi, lo, hi, lab, col in ((pa, lo_a, hi_a, args.a, "#1f77b4"),
                                     (pb, lo_b, hi_b, args.b, "#d62728")):
            ok = np.isfinite(pi)
            ax.plot(k[ok], pi[ok], marker="o", color=col, label=lab)
            ax.fill_between(k[ok], lo[ok], hi[ok], color=col, alpha=0.18)
        ax.set_xlabel("indice de la accion dentro de la posesion rival")
        ax.set_ylabel("$\\pi$ = P(accion presionada)")
        ax.set_title("Presion segun cuanto lleva el rival con el balon\n"
                     "(IC 95% por bootstrap de partidos)", fontsize=10)
        ax.legend(); fig.tight_layout()
        p = out.with_suffix(".png"); fig.savefig(p, dpi=150); plt.close(fig)
        print(f"figura: {p}")


if __name__ == "__main__":
    main()
