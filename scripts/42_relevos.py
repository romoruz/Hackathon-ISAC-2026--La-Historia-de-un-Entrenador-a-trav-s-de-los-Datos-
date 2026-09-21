#!/usr/bin/env python3
"""
42_relevos.py — ADR-60: cuánto cambia el uso del campo en un relevo y qué parte
viene de quién juega (composición) y qué parte de cómo juegan los que siguen (uso).

Preinscrito en docs/preinscritos/ADR-60_BORRADOR.md (commit cde8a3a). Este
script NO decide nada que la ADR no fije:

  * familia F60 = las parejas de did_h4_v1 › pares en los clubes de las cinco
    historias que incluyen al técnico de la historia; si no son 21, aborta;
  * ocupación en exceso de la liga del MISMO torneo sin el club (malla 5×4);
  * T = ½‖Δ‖₁ con nula por permutación de partidos entre las dos eras
    (B = 4999), BH al 5% sobre los 21;
  * descomposición de punto medio Δ = U + C (identidad exacta, se comprueba);
  * compartido = al menos 200 acciones en cada era; sensibilidad con 100 y 400;
  * intervalos por bootstrap de partidos dentro de cada era (B = 2000);
  * control negativo Cocca I → Cocca II fuera de la familia;
  * predicciones P1–P6 evaluadas con el criterio escrito en la ADR.

Acciones propias: filas con `team == club` y `coach` no nulo en
data/processed_api_<club>/transitions.parquet (el parquet trae a los dos
equipos; las del rival tienen `coach` nulo). El torneo sale de la fecha con la
misma regla que 25_pares_h4.py (`torneo_cols`), importada de ahí.

Uso:
    source .venv/bin/activate
    python scripts/42_relevos.py --out reports/relevos_v1.json
    python scripts/42_relevos.py --n-perm 199 --n-boot 99 --out /tmp/relevos_humo.json
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
NX, NY, NZ = 5, 4, 20
HISTORIAS = ["Andre Jardine", "Nicolas Larcamon", "Ignacio Ambriz", "Miguel Herrera", "Fernando Ortiz"]
M_FAMILIA = 21
CONTROL = ("Atlas", "Diego Cocca I", "Diego Cocca II")
UMBRAL = 200
UMBRALES_SENS = (100, 400)
MIN_COMPARTIDOS = 3
ESTABLE = 0.10
ALPHA = 0.05


class Aborta(Exception):
    pass


# ---------------------------------------------------------------------------
# álgebra (sin E/S: es lo que prueban los tests)
# ---------------------------------------------------------------------------
def era(Xc, Xl, n, peso):
    """Ocupación en exceso de una era. Xc (M×20) conteos por partido, Xl (M×20)
    n_m·L_{t(m)}, n (M) acciones por partido, peso (M) multiplicidad del partido
    en la era (0/1 en la observada, conteos en un remuestreo)."""
    N = peso @ n
    return (peso @ Xc) / N - (peso @ Xl) / N, N


def estadistico_T(Xc, Xl, n, pa, pb):
    ea, _ = era(Xc, Xl, n, pa)
    eb, _ = era(Xc, Xl, n, pb)
    return 0.5 * np.abs(eb - ea).sum()


def T_matriz(Xc, Xl, n, PA, PB):
    """T para muchas asignaciones a la vez: PA, PB (B×M)."""
    Na, Nb = PA @ n, PB @ n
    ea = (PA @ Xc) / Na[:, None] - (PA @ Xl) / Na[:, None]
    eb = (PB @ Xc) / Nb[:, None] - (PB @ Xl) / Nb[:, None]
    return 0.5 * np.abs(eb - ea).sum(1)


def descompone(Ya, Yb, La, Lb, compartidos):
    """Descomposición de punto medio (ADR-60 §3).

    Ya, Yb: (J×20) conteos por jugador en cada era (mismo orden de jugadores).
    La, Lb: referencia de liga de cada era (20). compartidos: máscara (J).
    Devuelve Δ, U, C con Δ = U + C exacto.
    """
    Na, Nb = Ya.sum(), Yb.sum()
    na, nb = Ya.sum(1), Yb.sum(1)
    wa, wb = na / Na, nb / Nb
    delta = (Yb.sum(0) / Nb - Lb) - (Ya.sum(0) / Na - La)
    S = compartidos & (na > 0) & (nb > 0)
    za = np.where(S[:, None], Ya / np.maximum(na, 1)[:, None], 0.0) - La
    zb = np.where(S[:, None], Yb / np.maximum(nb, 1)[:, None], 0.0) - Lb
    wbar, dw = (wa + wb) / 2, wb - wa
    U = (wbar[S, None] * (zb[S] - za[S])).sum(0)
    C_S = (dw[S, None] * ((za[S] + zb[S]) / 2)).sum(0)
    noS = ~S
    C_no = ((Yb[noS].sum(0) / Nb - wb[noS].sum() * Lb) -
            (Ya[noS].sum(0) / Na - wa[noS].sum() * La))
    C = C_S + C_no
    return delta, U, C


def normas(delta, U, C):
    nU, nC = np.abs(U).sum(), np.abs(C).sum()
    return {"T": 0.5 * np.abs(delta).sum(), "U": 0.5 * nU, "C": 0.5 * nC,
            "phi_U": (nU / (nU + nC)) if (nU + nC) > 0 else None}


def bh(p):
    p = np.asarray(p, float)
    m = len(p)
    orden = np.argsort(p)
    q = np.empty(m)
    acc = 1.0
    for rango in range(m, 0, -1):
        i = orden[rango - 1]
        acc = min(acc, p[i] * m / rango)
        q[i] = acc
    return q


def spearman(x, y):
    def rangos(v):
        v = np.asarray(v, float)
        o = np.argsort(v, kind="mergesort")
        r = np.empty(len(v))
        r[o] = np.arange(len(v))
        # empates: rango medio
        for val in np.unique(v):
            m = v == val
            if m.sum() > 1:
                r[m] = r[m].mean()
        return r
    rx, ry = rangos(x), rangos(y)
    rx -= rx.mean()
    ry -= ry.mean()
    d = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    return float((rx * ry).sum() / d) if d > 0 else None


def js_filas(Pa, Pb, peso):
    """Jensen–Shannon (base 2) entre filas de dos matrices de transición,
    ponderado por `peso`. Sensibilidad cruda de ADR-60 §3."""
    def kl(p, q):
        m = p > 0
        return (p[m] * np.log2(p[m] / q[m])).sum()
    tot, acc = 0.0, 0.0
    for i in range(Pa.shape[0]):
        a, b = Pa[i], Pb[i]
        if a.sum() == 0 or b.sum() == 0 or peso[i] == 0:
            continue
        a, b = a / a.sum(), b / b.sum()
        m = (a + b) / 2
        acc += peso[i] * 0.5 * (kl(a, m) + kl(b, m))
        tot += peso[i]
    return acc / tot if tot else None


# ---------------------------------------------------------------------------
# datos
# ---------------------------------------------------------------------------
def _torneo_cols():
    ruta = RAIZ / "scripts" / "25_pares_h4.py"
    spec = importlib.util.spec_from_file_location("pares_h4_torneo", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.torneo_cols


def carga_acciones(indirs):
    """Acciones propias de cada club: una tabla con club, match_id, torneo,
    coach, player_id, zona, from_state, to_state."""
    import polars as pl
    tcols = _torneo_cols()
    partes = []
    for d in indirs:
        p = Path(d) / "transitions.parquet"
        if not p.exists():
            raise Aborta(f"falta {p}")
        t = pl.read_parquet(p, columns=["match_id", "team", "coach", "player_id", "from_state",
                                        "to_state", "is_absorbing", "match_date"])
        propios = t.filter(pl.col("coach").is_not_null())
        equipos = propios["team"].unique().to_list()
        if len(equipos) != 1:
            raise Aborta(f"{p}: las filas con técnico son de {len(equipos)} equipos ({equipos[:4]})")
        partes.append(propios.with_columns(pl.lit(equipos[0]).alias("club"), *tcols()))
    df = pl.concat(partes, how="vertical_relaxed")
    return df.with_columns((pl.col("from_state") // 4).alias("zona"))


def referencia_liga(df):
    """L_t^{-club}(z) para cada club y torneo: la liga del torneo sin el club."""
    import polars as pl
    liga = {}
    g_tz = df.group_by(["torneo", "zona"]).agg(pl.len().alias("n"))
    g_ctz = df.group_by(["club", "torneo", "zona"]).agg(pl.len().alias("n"))
    base = {}
    for t, z, n in g_tz.iter_rows():
        base.setdefault(t, np.zeros(NZ))[z] += n
    propio = {}
    for c, t, z, n in g_ctz.iter_rows():
        propio.setdefault((c, t), np.zeros(NZ))[z] += n
    for (c, t), v in propio.items():
        r = base[t] - v
        if r.sum() <= 0:
            raise Aborta(f"liga vacía para {c} en {t}")
        liga[(c, t)] = r / r.sum()
    return liga


def arreglos_pareja(df, liga, club, a, b):
    """Por partido: conteos por zona, n·L y conteos por jugador y zona."""
    import polars as pl
    sub = df.filter((pl.col("club") == club) & pl.col("coach").is_in([a, b]))
    partidos = (sub.group_by(["match_id", "coach", "torneo"]).agg(pl.len().alias("n"))
                .sort("match_id"))
    ids = partidos["match_id"].to_list()
    if len(set(ids)) != len(ids):
        raise Aborta(f"{club}: un partido con los dos técnicos ({a}, {b})")
    idx = {m: i for i, m in enumerate(ids)}
    M = len(ids)
    en_a = np.array([c == a for c in partidos["coach"].to_list()], float)
    n = partidos["n"].to_numpy().astype(float)
    Xl = np.array([n[i] * liga[(club, t)] for i, t in enumerate(partidos["torneo"].to_list())])
    jug = sorted(sub["player_id"].drop_nulls().unique().to_list())
    jidx = {j: k for k, j in enumerate(jug)}
    Y = np.zeros((M, len(jug) + 1, NZ))   # última columna: acciones sin jugador
    g = sub.group_by(["match_id", "player_id", "zona"]).agg(pl.len().alias("k"))
    for m, j, z, k in g.iter_rows():
        Y[idx[m], jidx[j] if j is not None else len(jug), z] += k
    Xc = Y.sum(1)
    if not np.allclose(Xc.sum(1), n):
        raise Aborta(f"{club}: los conteos por jugador no suman las acciones del partido")
    return {"en_a": en_a, "n": n, "Xc": Xc, "Xl": Xl, "Y": Y, "jugadores": jug, "M": M}


def matrices_Q(df, club, coach):
    import polars as pl
    sub = df.filter((pl.col("club") == club) & (pl.col("coach") == coach))
    fs, ts = sub["from_state"].to_numpy(), sub["to_state"].to_numpy()
    k = int(max(fs.max(), ts.max())) + 1
    P = np.zeros((k, k))
    np.add.at(P, (fs, ts), 1)
    return P


# ---------------------------------------------------------------------------
# una pareja
# ---------------------------------------------------------------------------
def analiza(A, rng, n_perm, n_boot):
    en_a, n, Xc, Xl, Y = A["en_a"], A["n"], A["Xc"], A["Xl"], A["Y"]
    pa, pb = en_a, 1 - en_a
    Ma, Mb = int(pa.sum()), int(pb.sum())
    T_obs = estadistico_T(Xc, Xl, n, pa, pb)

    # nula: permutar etiquetas entre partidos, conservando cuántos tiene cada era
    PA = np.zeros((n_perm, A["M"]))
    for i in range(n_perm):
        PA[i, rng.permutation(A["M"])[:Ma]] = 1
    T_perm = T_matriz(Xc, Xl, n, PA, 1 - PA)
    p = (1 + int((T_perm >= T_obs - 1e-15).sum())) / (n_perm + 1)

    # jugadores por era
    Ya, Yb = (Y * pa[:, None, None]).sum(0), (Y * pb[:, None, None]).sum(0)
    La = (pa @ Xl) / (pa @ n)
    Lb = (pb @ Xl) / (pb @ n)
    na, nb = Ya.sum(1), Yb.sum(1)
    real = np.arange(Y.shape[1]) < len(A["jugadores"])   # "sin jugador" nunca es compartido

    def comp(u):
        return real & (na >= u) & (nb >= u)

    res = {"n_partidos_a": Ma, "n_partidos_b": Mb, "acciones_a": float(pa @ n),
           "acciones_b": float(pb @ n), "T": T_obs, "p": p, "n_perm": n_perm,
           "T_nula_p95": float(np.quantile(T_perm, 0.95))}
    por_umbral = {}
    for u in (UMBRAL, *UMBRALES_SENS):
        S = comp(u)
        d, U, C = descompone(Ya, Yb, La, Lb, S)
        if np.abs(d - U - C).max() > 1e-12:
            raise Aborta("la identidad Δ = U + C no cierra")
        nn = normas(d, U, C)
        por_umbral[str(u)] = {"compartidos": int(S.sum()),
                              "U": nn["U"], "C": nn["C"],
                              "phi_U": nn["phi_U"] if S.sum() >= MIN_COMPARTIDOS else None}
        if u == UMBRAL:
            res["mapas"] = {"delta": d.tolist(), "U": U.tolist(), "C": C.tolist()}
    res["umbrales"] = por_umbral
    base = por_umbral[str(UMBRAL)]
    res["estimable"] = base["compartidos"] >= MIN_COMPARTIDOS
    alt = [por_umbral[str(u)]["phi_U"] for u in UMBRALES_SENS]
    res["estable"] = (res["estimable"] and all(x is not None for x in alt)
                      and all(abs(x - base["phi_U"]) < ESTABLE for x in alt))

    # bootstrap por partido dentro de cada era (S fijo, el observado con 200)
    S = comp(UMBRAL)
    ia, ib = np.flatnonzero(pa), np.flatnonzero(pb)
    reps = {"T": [], "U": [], "C": [], "phi_U": []}
    for _ in range(n_boot):
        wa = np.bincount(rng.choice(ia, Ma), minlength=A["M"]).astype(float)
        wb = np.bincount(rng.choice(ib, Mb), minlength=A["M"]).astype(float)
        Yra, Yrb = np.tensordot(wa, Y, 1), np.tensordot(wb, Y, 1)
        Lra, Lrb = (wa @ Xl) / (wa @ n), (wb @ Xl) / (wb @ n)
        d, U, C = descompone(Yra, Yrb, Lra, Lrb, S)
        if np.abs(d - U - C).max() > 1e-12:
            raise Aborta("la identidad Δ = U + C no cierra en una réplica")
        nn = normas(d, U, C)
        for k in reps:
            if nn[k] is not None:
                reps[k].append(nn[k])
    res["ic95"] = {k: ([float(np.quantile(v, .025)), float(np.quantile(v, .975))] if v else None)
                   for k, v in reps.items()}
    if not res["estimable"]:
        res["ic95"]["phi_U"] = None
    return res


# ---------------------------------------------------------------------------
# familia, predicciones, salida
# ---------------------------------------------------------------------------
def familia(h4, met):
    clubes = {c: {u["club"] for u in met["unidades"] if u["coach"] == c} for c in HISTORIAS}
    orden = {t: i for i, t in enumerate(h4["parametros"]["torneos_orden"])}
    t0 = {(u["club"], u["coach"]): min(orden[t] for t in u["torneos"]) for u in h4["unidades"]}
    vistos, fam = set(), []
    for c in HISTORIAS:
        for p in h4["pares"]:
            k = (p["club"], p["a"], p["b"])
            if p["club"] in clubes[c] and c in (p["a"], p["b"]) and k not in vistos:
                vistos.add(k)
                a, b = sorted((p["a"], p["b"]), key=lambda x: t0[(p["club"], x)])
                fam.append((p["club"], a, b))
    if len(fam) != M_FAMILIA:
        raise Aborta(f"la familia F60 tiene {len(fam)} parejas y la ADR fija {M_FAMILIA}")
    return sorted(fam), t0


def predicciones(pares, control):
    def busca(club, a, b):
        return next(p for p in pares if (p["club"], p["a"], p["b"]) == (club, a, b))
    out = []
    ho = busca("Tijuana", "Miguel Herrera", "Juan Carlos Osorio")
    out.append({"n": 1, "texto": "Tijuana, Herrera → Osorio: T rechaza tras BH y φ_U ≥ 0.5",
                "cumple": bool(ho["rechaza"] and ho["umbrales"]["200"]["phi_U"] is not None
                               and ho["umbrales"]["200"]["phi_U"] >= 0.5)})
    hl = busca("León", "Ariel Holan", "Nicolas Larcamon")
    out.append({"n": 2, "texto": "León, Holan → Larcamón: T no rechaza", "cumple": not hl["rechaza"]})
    fa = busca("Santos Laguna", "Eduardo Fentanes", "Ignacio Ambriz")
    out.append({"n": 3, "texto": "Santos, Fentanes → Ambriz: T rechaza", "cumple": bool(fa["rechaza"])})
    sl = [busca("Atlético San Luis", "Andre Jardine", x)["rechaza"]
          for x in ("Domenec Torrent", "Guillermo Abascal", "Gustavo Leal")]
    out.append({"n": 4, "texto": "San Luis, Jardine → Torrent, Abascal, Leal: rechazan a lo sumo 1 de 3",
                "cumple": sum(sl) <= 1, "valor": [int(sum(sl)), 3]})
    est = [p for p in pares if p["estimable"]]
    if len(est) < 10:
        out.append({"n": 5, "texto": "Spearman(compartidos, φ_U) > 0", "cumple": None,
                    "no_evaluable": True, "valor": {"n": len(est)}})
    else:
        r = spearman([p["umbrales"]["200"]["compartidos"] for p in est],
                     [p["umbrales"]["200"]["phi_U"] for p in est])
        out.append({"n": 5, "texto": "Spearman(compartidos, φ_U) > 0", "cumple": r is not None and r > 0,
                    "valor": {"n": len(est), "rho": r}})
    out.append({"n": 6, "texto": "Control: Cocca I → Cocca II no rechaza (p > 0.05 sin corregir)",
                "cumple": control["p"] > ALPHA, "valor": {"p": control["p"]}})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--indirs", nargs="*", default=None)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "relevos_v1.json"))
    ap.add_argument("--n-perm", type=int, default=4999)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260921)
    a = ap.parse_args()
    t_ini = time.time()
    try:
        import polars  # noqa: F401
    except ImportError:
        sys.exit("sin polars: activa .venv")
    rep = Path(a.reports)
    h4 = json.loads((rep / "did_h4_v1.json").read_text(encoding="utf-8"))
    met = json.loads((rep / "metricas_v1.json").read_text(encoding="utf-8"))
    indirs = a.indirs or sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    try:
        if len(indirs) != 18:
            raise Aborta(f"se esperaban los 18 directorios data/processed_api_*; hay {len(indirs)}")
        fam, t0 = familia(h4, met)
        df = carga_acciones(indirs)
        liga = referencia_liga(df)
        rng = np.random.default_rng(a.seed)
        pares = []
        for club, x, y in fam + [CONTROL]:
            A = arreglos_pareja(df, liga, club, x, y)
            r = analiza(A, rng, a.n_perm, a.n_boot)
            Pa, Pb = matrices_Q(df, club, x), matrices_Q(df, club, y)
            k = max(Pa.shape[0], Pb.shape[0])
            Pa = np.pad(Pa, ((0, k - Pa.shape[0]), (0, k - Pa.shape[1])))
            Pb = np.pad(Pb, ((0, k - Pb.shape[0]), (0, k - Pb.shape[1])))
            r["js_Q_crudo"] = js_filas(Pa, Pb, Pa.sum(1) + Pb.sum(1))
            pares.append({"club": club, "a": x, "b": y, **r})
            print(f"  {club:<18s} {x} → {y}: T {r['T']:.3f} p {r['p']:.4f} · "
                  f"compartidos {r['umbrales']['200']['compartidos']} · "
                  f"φ_U {r['umbrales']['200']['phi_U'] if r['estimable'] else '—'}", flush=True)
    except Aborta as e:
        sys.exit(f"ABORTA: {e}")
    control = pares.pop()
    q = bh([p["p"] for p in pares])
    for p, qq in zip(pares, q):
        p["q"], p["rechaza"] = float(qq), bool(qq <= ALPHA)
    control["rechaza_sin_corregir"] = control["p"] <= ALPHA
    salida = {
        "adr": "ADR-60", "preinscripcion": "docs/preinscritos/ADR-60_BORRADOR.md (commit cde8a3a)",
        "parametros": {"n_perm": a.n_perm, "n_boot": a.n_boot, "seed": a.seed, "umbral": UMBRAL,
                       "umbrales_sensibilidad": list(UMBRALES_SENS), "min_compartidos": MIN_COMPARTIDOS,
                       "estable_si_dif_menor_a": ESTABLE, "alpha": ALPHA, "m_familia": M_FAMILIA,
                       "malla": [NX, NY]},
        "reglas": {
            "D60-1": "T = ½‖Δ‖₁ sobre la ocupación en exceso de la liga del mismo torneo sin el club",
            "D60-2": "nula por permutación de partidos entre las dos eras; cada partido lleva su liga",
            "D60-3": "descomposición de punto medio: la interacción va mitad a uso y mitad a composición",
            "D60-4": "compartido = al menos 200 acciones en cada era; sensibilidad 100 y 400",
            "D60-5": "familia F60 de 21 parejas, BH 5% sobre T; U, C y φ_U son nivel B",
        },
        "n_rechazados": int(sum(p["rechaza"] for p in pares)),
        "pares": pares, "control_negativo": control,
        "predicciones": predicciones(pares, control),
        "segundos": round(time.time() - t_ini, 1),
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for p in salida["predicciones"] if p["cumple"])
    print(f"escrito {a.out} · {salida['n_rechazados']} de {len(pares)} rechazan · "
          f"predicciones {ok} de {sum(p['cumple'] is not None for p in salida['predicciones'])} "
          f"(+{sum(p['cumple'] is None for p in salida['predicciones'])} no evaluables) · {salida['segundos']} s")


if __name__ == "__main__":
    main()
