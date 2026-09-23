#!/usr/bin/env python3
"""
45_progresion.py — ADR-61: progresión hasta la franja del área, dónde vive una
posesión viva (cuasi-estacionaria por bloque) y supervivencia por torneo.

Preinscrito en docs/preinscritos/ADR-61_BORRADOR.md v2 (commit 6f307c1). Este
script NO decide nada que la ADR no fije:

  * D61-0  fracción f de transiciones que cambian de fase; si f ≥ 0.01, aborta;
  * D61-1  franja = ix 4 (estados 64..79); α′ con las posesiones que empiezan
           fuera; el α′ de la era en los dos términos;
  * D61-2  λ = 0 en todas las magnitudes;
  * D61-3  bootstrap por partido estratificado por torneo, B = 4000, basic en
           log, seed 20260923;
  * D61-4  F61 = 5 eras principales × {D_L, D_τ}, BH al 5%;
  * D61-5  π y λ₁ sobre el bloque de juego abierto; irreducible; eigen y
           potencias coinciden a 1e-6;
  * D61-6  supervivencia por torneo, modelo condicionado a L ≥ 2;
  * D61-7  jugada de ejemplo por regla.

La base es la liga sin el club, en los torneos de la era y ponderada a la
mezcla de posesiones de la era por torneo. Antes de medir nada se comprueba
contra did_h4_v1 (ADR-53): el E[T] de la era tiene que coincidir a 0.5% y el
de la base a 2%. Si no, la base no es la misma y el script aborta.

Uso:
    python scripts/45_progresion.py --solo-diagnostico      # D61-0 y la base
    python scripts/45_progresion.py                         # todo
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
NT, NA = 80, 4
NS = NT + NA
NF = 4                                   # fases, en el orden de phase_order
FASES = ("open", "transition", "restart", "set_piece")
FRANJA_IX = 4
FRANJA_TXT = ("franja del área: ix = 4, la última de las cinco columnas de la malla, de 96 a 120 "
              "en la escala del proveedor (120 × 80); el área grande empieza en 102, así que la "
              "franja la contiene completa y un poco más")
HISTORIAS = [("jardine", "Andre Jardine"), ("larcamon", "Nicolas Larcamon"),
             ("ambriz", "Ignacio Ambriz"), ("herrera", "Miguel Herrera"), ("ortiz", "Fernando Ortiz")]
N_BOOT = 4000
SEED = 20260923
ALPHA = 0.05
MIN_POSS_EXPL = 200        # ADR-61 adenda 1, D61A-3
F_MAX = 0.01
TOL_ET_ERA, TOL_ET_BASE = 0.005, 0.02
TOL_POT = 1e-6
DIST_ANIM, MAX_FRAMES = 0.01, 80
K_MAX = 30
MAX_NO_FINITAS = 0.01
PREINSCRIPCION = "docs/preinscritos/ADR-61_BORRADOR.md v2 (commit 6f307c1)"
REGLAS = {
    "D61-0": "f = fracción de transiciones entre transitorios que cambian de fase; si f ≥ 0.01, aborta",
    "D61-1": "franja = ix 4; α′ solo con posesiones que empiezan fuera; el α′ de la era en los dos términos",
    "D61-2": "λ = 0 en todas las magnitudes",
    "D61-3": "bootstrap por partido estratificado por torneo, B = 4000, basic en log, seed 20260923",
    "D61-4": "F61 = 5 eras principales × {D_L, D_τ}; BH al 5%; no evaluables fuera y declarados",
    "D61-5": "π y λ₁ sobre el bloque de juego abierto; irreducible; eigen y potencias coinciden",
    "D61-6": "supervivencia por torneo, modelo condicionado a L ≥ 2",
    "D61-7": "jugada de ejemplo: la que tarda round(τ) acciones en llegar; empate, la más antigua",
}


class Aborta(Exception):
    pass


# ---------------------------------------------------------------------------
# álgebra (sin E/S: es lo que prueban los tests)
# ---------------------------------------------------------------------------
def franja(ix_min=FRANJA_IX):
    """Máscara de estados transitorios en la franja: zona = s // 4, ix = zona // 4."""
    s = np.arange(NT)
    return (s // NF) // 4 >= ix_min


def bloque(fase):
    return np.arange(NT)[np.arange(NT) % NF == fase]


def P_de(C, respaldo=None):
    """Probabilidades a λ = 0. Un renglón sin datos toma el del respaldo (la base,
    como `shrink` con λ = 0 en 25_pares_h4.py) o la uniforme."""
    n = C.sum(1, keepdims=True)
    P = np.where(n > 0, C / np.maximum(n, 1e-300), 0.0)
    vacio = n.ravel() == 0
    if vacio.any():
        P[vacio] = respaldo[vacio] if respaldo is not None else 1.0 / C.shape[1]
    return P


def E_T(P, alfa):
    Q = P[:, :NT]
    t = np.linalg.solve(np.eye(NT) - Q, np.ones(NT))
    return float(alfa @ t / alfa.sum())


def llegada(P, alfa, mask=None):
    """L = P(llegar a la franja antes de absorber) y τ = E[acciones hasta llegar |
    llega], desde α restringida a los estados fuera de la franja."""
    f = franja() if mask is None else mask
    o = ~f
    a = alfa[o]
    if a.sum() <= 0:
        return math.nan, math.nan
    a = a / a.sum()
    Q = P[:, :NT]
    I_Qoo = np.eye(o.sum()) - Q[np.ix_(o, o)]
    h = np.linalg.solve(I_Qoo, Q[np.ix_(o, f)].sum(1))
    L = float(a @ h)
    if L <= 0:
        return 0.0, math.nan
    g = np.linalg.solve(I_Qoo, h)
    return L, float(a @ g / L)


def irreducible(Qb):
    from scipy.sparse.csgraph import connected_components
    k, _ = connected_components(Qb > 0, directed=True, connection="strong")
    return k == 1


def cuasi(Qb, alfa0, frames=False):
    """π (vector propio izquierdo de Perron) y λ₁ del bloque; verificado por
    potencias desde α. Devuelve None si el bloque no es irreducible."""
    if not irreducible(Qb):
        return None
    w, V = np.linalg.eig(Qb.T)
    i = int(np.argmax(w.real))
    lam = float(w[i].real)
    v = V[:, i].real
    v = v / v.sum()
    if (v < -1e-10).any():
        raise Aborta("el vector de Perron tiene signos mezclados")
    pi = np.clip(v, 0, None)
    pi /= pi.sum()
    mu = alfa0 / alfa0.sum() if alfa0.sum() > 0 else np.full(len(pi), 1 / len(pi))
    fr = [mu.tolist()]
    for _ in range(200000):
        nu = mu @ Qb
        nu /= nu.sum()
        if frames and len(fr) < MAX_FRAMES and np.abs(np.array(fr[-1]) - pi).sum() >= DIST_ANIM:
            fr.append(nu.tolist())
        if np.abs(nu - mu).sum() < 1e-14:
            mu = nu
            break
        mu = nu
    if np.abs(mu - pi).sum() > TOL_POT:
        raise Aborta(f"cuasi-estacionaria: eigen y potencias difieren en {np.abs(mu - pi).sum():.2e}")
    out = {"pi": pi.tolist(), "lambda1": lam, "vida": 1.0 / (1.0 - lam)}
    if frames:
        out["frames"] = fr
    return out


def supervivencia_modelo(P, alfa, kmax=K_MAX):
    """S(k) = α Qᵏ 1 condicionada a L ≥ 2, para k = 1..kmax."""
    Q = P[:, :NT]
    a = alfa / alfa.sum()
    S = []
    for _ in range(kmax + 1):
        S.append(a.sum())
        a = a @ Q
    S = np.array(S)
    return (S[1:] / S[1]).tolist()


def supervivencia_obs(largos, kmax=K_MAX):
    L = np.asarray(largos)
    L = L[L >= 2]
    return [float((L > k).mean()) for k in range(1, kmax + 1)]


def p_basic(d, reps):
    """p por inversión del intervalo basic: el menor α con el cero fuera."""
    r = np.asarray(reps)
    B = len(r)
    k = min((r >= 2 * d).sum(), (r <= 2 * d).sum())
    return min(1.0, 2 * (k + 1) / (B + 1))


def ic_basic(d, reps, nivel=0.95):
    lo, hi = np.quantile(reps, [(1 - nivel) / 2, (1 + nivel) / 2])
    return [float(2 * d - hi), float(2 * d - lo)]


def bh(ps, alpha=ALPHA):
    m = len(ps)
    orden = np.argsort(ps)
    q = np.empty(m)
    prev = 1.0
    for rango, i in reversed(list(enumerate(orden, 1))):
        prev = min(prev, ps[i] * m / rango)
        q[i] = prev
    return q.tolist(), [x <= alpha for x in q]


def spearman(x, y):
    from scipy.stats import spearmanr
    return float(spearmanr(x, y).statistic)


# ---------------------------------------------------------------------------
# datos
# ---------------------------------------------------------------------------
def _torneo_cols():
    spec = importlib.util.spec_from_file_location("pares_h4_torneo", RAIZ / "scripts" / "25_pares_h4.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.torneo_cols


def carga(indirs):
    """Acciones propias de cada club (coach no nulo), con su posesión y su orden."""
    import polars as pl
    tcols = _torneo_cols()
    partes = []
    for d in indirs:
        p = Path(d) / "transitions.parquet"
        if not p.exists():
            raise Aborta(f"falta {p}")
        cols = set(pl.read_parquet_schema(p))
        need = ["match_id", "team", "coach", "poss_uid", "event_index", "from_state", "to_state", "match_date"]
        falta = [c for c in need if c not in cols]
        if falta:
            raise Aborta(f"{p}: faltan columnas {falta}")
        extra = [c for c in ("player", "action_type") if c in cols]
        t = pl.read_parquet(p, columns=need + extra).filter(pl.col("coach").is_not_null())
        eq = t["team"].unique().to_list()
        if len(eq) != 1:
            raise Aborta(f"{p}: las filas con técnico son de {len(eq)} equipos")
        partes.append(t.with_columns(pl.lit(eq[0]).alias("club"), *tcols()))
    df = pl.concat(partes, how="diagonal_relaxed")
    return df.with_columns(pl.concat_str([pl.col("club"), pl.col("poss_uid").cast(pl.Utf8)],
                                         separator="|").alias("pid"))


def diagnostico_fase(df):
    import polars as pl
    t = df.filter(pl.col("to_state") < NT)
    cam = t.filter((pl.col("from_state") % NF) != (pl.col("to_state") % NF))
    por = (t.group_by("club").agg(pl.len().alias("n"),
                                  ((pl.col("from_state") % NF) != (pl.col("to_state") % NF)).sum().alias("k"))
           .sort("club"))
    n, k = t.height, cam.height
    f = k / n if n else math.nan
    return {"n": n, "cambian": k, "f": f, "rama": "bloques" if f < F_MAX else "aborta",
            "por_club": [{"club": c, "n": a, "cambian": b} for c, a, b in por.iter_rows()]}


def agrega(sub):
    """Por partido: conteos (M, 80·84), inicios de posesión (M, 80) y torneo."""
    import polars as pl
    ids = sorted(sub["match_id"].unique().to_list())
    idx = {m: i for i, m in enumerate(ids)}
    M = len(ids)
    C = np.zeros((M, NT * NS))
    mi = np.array([idx[m] for m in sub["match_id"].to_list()])
    np.add.at(C, (mi, sub["from_state"].to_numpy() * NS + sub["to_state"].to_numpy()), 1.0)
    ini = sub.sort(["pid", "event_index"]).group_by("pid", maintain_order=True).first()
    A = np.zeros((M, NT))
    np.add.at(A, (np.array([idx[m] for m in ini["match_id"].to_list()]), ini["from_state"].to_numpy()), 1.0)
    tor = dict(sub.select("match_id", "torneo").unique().iter_rows())
    return {"ids": ids, "C": C, "A": A, "torneo": [tor[m] for m in ids]}


def pesos_base(Gb, s_t, w=None):
    """Peso por partido de la base: s_t / S_t en su torneo (mezcla de la era)."""
    w = np.ones(len(Gb["ids"])) if w is None else w
    pos = Gb["A"].sum(1) * w
    out = np.zeros_like(w)
    for t, s in s_t.items():
        m = np.array([x == t for x in Gb["torneo"]])
        S = pos[m].sum()
        if S <= 0:
            raise Aborta(f"la base no tiene posesiones en {t}")
        out[m] = w[m] * s / S
    return out


def estratos(torneos):
    e = {}
    for i, t in enumerate(torneos):
        e.setdefault(t, []).append(i)
    return {t: np.array(v) for t, v in e.items()}


def remuestra(estr, M, rng):
    w = np.zeros(M)
    for v in estr.values():
        np.add.at(w, rng.choice(v, len(v)), 1.0)
    return w


def matrices(Ge, Gb, s_t, we=None, wb=None):
    we = np.ones(len(Ge["ids"])) if we is None else we
    Cb = (pesos_base(Gb, s_t, wb) @ Gb["C"]).reshape(NT, NS)
    Pb = P_de(Cb)
    Ce = (we @ Ge["C"]).reshape(NT, NS)
    return P_de(Ce, Pb), Pb, we @ Ge["A"]


# ---------------------------------------------------------------------------
# eras
# ---------------------------------------------------------------------------
def era_principal(met, h4, coach):
    orden = {t: i for i, t in enumerate(h4["parametros"]["torneos_orden"])}
    t0 = {(u["club"], u["coach"]): min(orden[t] for t in u["torneos"]) for u in h4["unidades"]}
    eras = [u for u in met["unidades"] if u["coach"] == coach]
    if not eras:
        raise Aborta(f"{coach} no está en metricas_v1")
    return min(eras, key=lambda u: (-u["n_partidos"], t0.get((u["club"], coach), 99)))


def unidad_h4(h4, club, coach):
    for u in h4["unidades"]:
        if u["club"] == club and u["coach"] == coach:
            return u
    raise Aborta(f"{club} · {coach} no está en did_h4_v1")


def jugada(sub, tau):
    """D61-7: la posesión que tarda round(τ) acciones en llegar a la franja."""
    import polars as pl
    obj = int(round(tau))
    fm = franja()
    cands = []
    for (pid,), g in sub.sort(["match_date", "pid", "event_index"]).group_by("pid", maintain_order=True):
        fs, ts = g["from_state"].to_list(), g["to_state"].to_list()
        if fm[fs[0]]:
            continue
        k = next((i + 1 for i, t in enumerate(ts) if t < NT and fm[t]), None)
        if k is None:
            continue
        cands.append((abs(k - obj), k, g["match_date"][0], pid, g.head(k)))
    if not cands:
        return None
    _, k, fecha, pid, g = min(cands, key=lambda c: (c[0], c[1], str(c[2]), c[3]))
    zonas = [s // NF for s in g["from_state"].to_list()] + [g["to_state"][-1] // NF]
    return {"objetivo": obj, "acciones": k, "fecha": str(fecha), "pid": pid,
            "zonas": zonas, "fase": FASES[g["from_state"][0] % NF],
            "tipos": g["action_type"].to_list() if "action_type" in g.columns else None,
            "jugadores": g["player"].to_list() if "player" in g.columns else None}


def mide_era(df, club, coach, rng, n_boot):
    import polars as pl
    sub = df.filter((pl.col("club") == club) & (pl.col("coach") == coach))
    if sub.height == 0:
        raise Aborta(f"{club} · {coach}: 0 acciones")
    tors = sorted(sub["torneo"].unique().to_list())
    base = df.filter((pl.col("club") != club) & pl.col("torneo").is_in(tors))
    Ge, Gb = agrega(sub), agrega(base)
    s_t = {t: float(Ge["A"][np.array([x == t for x in Ge["torneo"]])].sum()) for t in tors}
    Pe, Pb, ae = matrices(Ge, Gb, s_t)
    obs = {"E_T": E_T(Pe, ae), "E_T_base": E_T(Pb, ae)}
    Le, te = llegada(Pe, ae)
    Lb, tb = llegada(Pb, ae)
    f3 = franja(3)
    L3e, _ = llegada(Pe, ae, f3)
    L3b, _ = llegada(Pb, ae, f3)
    res = {"club": club, "coach": coach, "torneos": tors, "n_partidos": len(Ge["ids"]),
           "n_poss": int(ae.sum()), "n_poss_fuera": int(ae[~franja()].sum()),
           "n_partidos_base": len(Gb["ids"]), "verif": obs,
           "sens_ix3": {"era": L3e, "base": L3b, "rel": L3e / L3b - 1 if L3b > 0 else None}}
    D = {"L": (math.log(Le / Lb) if Le > 0 and Lb > 0 else math.nan, Le, Lb),
         "tau": (math.log(te / tb) if te > 0 and tb > 0 else math.nan, te, tb)}
    reps = {"L": [], "tau": []}
    malas = {"L": 0, "tau": 0}
    ee, eb = estratos(Ge["torneo"]), estratos(Gb["torneo"])
    for _ in range(n_boot):
        we, wb = remuestra(ee, len(Ge["ids"]), rng), remuestra(eb, len(Gb["ids"]), rng)
        try:
            Pr, Pbr, ar = matrices(Ge, Gb, s_t, we, wb)
            l1, t1 = llegada(Pr, ar)
            l2, t2 = llegada(Pbr, ar)
        except (np.linalg.LinAlgError, Aborta):
            l1 = t1 = l2 = t2 = math.nan
        for k, (x, y) in (("L", (l1, l2)), ("tau", (t1, t2))):
            if np.isfinite(x) and np.isfinite(y) and x > 0 and y > 0:
                reps[k].append(math.log(x / y))
            else:
                malas[k] += 1
    for k, (d, a, b) in D.items():
        r = {"era": a, "base": b, "D": d, "rel": math.exp(d) - 1 if np.isfinite(d) else None,
             "replicas_validas": len(reps[k]), "replicas_no_finitas": malas[k]}
        ok = np.isfinite(d) and n_boot > 0 and malas[k] <= MAX_NO_FINITAS * n_boot
        r["evaluable"] = bool(ok)
        if ok:
            ic = ic_basic(d, reps[k])
            r["ic95"] = ic
            r["ic95_rel"] = [math.exp(ic[0]) - 1, math.exp(ic[1]) - 1]
            r["p"] = p_basic(d, reps[k])
        res[k] = r
    ob = bloque(0)
    ca = cuasi(Pe[np.ix_(ob, ob)], ae[ob])
    cb = cuasi(Pb[np.ix_(ob, ob)], ae[ob])
    res["cuasi"] = {"evaluable": ca is not None and cb is not None,
                    "era": ca, "base": cb}
    res["jugada"] = jugada(sub, te) if np.isfinite(te) else None
    return res


def liga_torneo(df, t):
    import polars as pl
    sub = df.filter(pl.col("torneo") == t)
    G = agrega(sub)
    C = G["C"].sum(0).reshape(NT, NS)
    return P_de(C), G["A"].sum(0), sub


def largos(sub):
    import polars as pl
    return sub.group_by("pid").agg(pl.len().alias("L"))["L"].to_numpy()


# ---------------------------------------------------------------------------
# predicciones
# ---------------------------------------------------------------------------
def predicciones(eras, met_glob, h4_rel, surv):
    out = []
    ev = [e for e in eras if e["L"]["evaluable"]]
    coinc = [int(np.sign(e["L"]["D"]) == np.sign(met_glob[e["hid"]])) for e in ev]
    out.append({"n": 1, "texto": "signo de D_L igual al del field tilt contra la liga en al menos 4 de 5 eras",
                "cumple": (sum(coinc) >= 4) if len(ev) >= 4 else None,
                "valor": {"coinciden": sum(coinc), "evaluables": len(ev)}})
    j = next(e for e in eras if e["hid"] == "jardine")
    out.append({"n": 2, "texto": "Jardine en el América: D_L > 0 y sobrevive a BH",
                "cumple": (j["L"]["D"] > 0 and j["L"]["rechaza"]) if j["L"]["evaluable"] else None,
                "valor": {"D": j["L"]["D"], "q": j["L"].get("q")}, "informada_por": "ADR-53"})
    n = len(surv)
    k = sum(s["encima_12"] for s in surv)
    out.append({"n": 3, "texto": "cola observada por encima del modelo en k = 12 en al menos dos tercios de los torneos",
                "cumple": k >= math.ceil(2 * n / 3) if n else None, "valor": {"torneos": k, "de": n},
                "contaminada": "en parte (ADR-21, América, torneos juntos)"})
    pts = [{"hid": e["hid"], "D_L": e["L"]["D"], "rel_E_T": h4_rel[e["hid"]]} for e in ev]
    rho = spearman([p["D_L"] for p in pts], [p["rel_E_T"] for p in pts]) if len(pts) >= 4 else None
    out.append({"n": 4, "texto": "Spearman entre D_L y ΔE[T] de ADR-53 menor a 0.9",
                "cumple": (rho < 0.9) if rho is not None and np.isfinite(rho) else None,
                "valor": {"rho": rho, "n": len(pts)}, "puntos": pts})
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "progresion_v1.json"))
    ap.add_argument("--out-surv", default=str(RAIZ / "reports" / "supervivencia_v1.json"))
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--solo-diagnostico", action="store_true")
    ap.add_argument("--solo-principales", action="store_true",
                    help="ADR-61 adenda 1 §5: vuelve al comportamiento de h2_35 (sin eras_todas)")
    a = ap.parse_args()
    t0 = time.time()
    rep = Path(a.reports)
    h4 = json.loads((rep / "did_h4_v1.json").read_text(encoding="utf-8"))
    met = json.loads((rep / "metricas_v1.json").read_text(encoding="utf-8"))
    indirs = sorted(glob.glob(str(RAIZ / "data" / "processed_api_*")))
    rng = np.random.default_rng(SEED)
    try:
        if len(indirs) != 18:
            raise Aborta(f"se esperaban 18 directorios data/processed_api_*; hay {len(indirs)}")
        df = carga(indirs)
        d0 = diagnostico_fase(df)
        print(f"D61-0: {d0['cambian']} de {d0['n']} transiciones cambian de fase (f = {d0['f']:.5f})")
        if d0["rama"] == "aborta":
            raise Aborta(f"f = {d0['f']:.4f} ≥ {F_MAX}: la fase no es constante dentro de la posesión")
        principales = []
        for hid, coach in HISTORIAS:
            u = era_principal(met, h4, coach)
            principales.append((hid, u["club"], coach, u))
        # verificación de la base contra ADR-53, sin bootstrap
        print("base contra did_h4_v1 (E[T] de la era y de la base):")
        verif = []
        for hid, club, coach, _ in principales:
            r = mide_era(df, club, coach, rng, 0)
            uh = unidad_h4(h4, club, coach)
            de = r["verif"]["E_T"] / uh["E_T"] - 1
            db = r["verif"]["E_T_base"] / uh["E_T_base"] - 1
            verif.append({"hid": hid, "club": club, "coach": coach, "E_T": r["verif"]["E_T"],
                          "E_T_h4": uh["E_T"], "dif_era": de, "E_T_base": r["verif"]["E_T_base"],
                          "E_T_base_h4": uh["E_T_base"], "dif_base": db})
            print(f"  {club:<18s} {coach:<18s} era {r['verif']['E_T']:.3f} vs {uh['E_T']:.3f} ({de:+.2%}) · "
                  f"base {r['verif']['E_T_base']:.3f} vs {uh['E_T_base']:.3f} ({db:+.2%})")
        malas = [v for v in verif if abs(v["dif_era"]) > TOL_ET_ERA or abs(v["dif_base"]) > TOL_ET_BASE]
        if malas:
            raise Aborta("la base no reproduce did_h4_v1 (tolerancia era 0.5%, base 2%): "
                         + ", ".join(f"{v['club']}·{v['coach']}" for v in malas))
        if a.solo_diagnostico:
            print(f"diagnóstico OK en {time.time() - t0:.0f} s")
            return
        # progresión con bootstrap
        eras = []
        for hid, club, coach, u in principales:
            r = mide_era(df, club, coach, rng, a.n_boot)
            r["hid"] = hid
            eras.append(r)
            print(f"  {club:<18s} {coach:<18s} L {r['L']['era']:.3f} vs {r['L']['base']:.3f} · "
                  f"τ {r['tau']['era']:.2f} vs {r['tau']['base']:.2f}", flush=True)
        # ADR-61 adenda 1: las eras no principales, DESCRIPTIVAS y fuera de F61
        todas = []
        if not a.solo_principales:
            pr = {(c, co) for _, c, co, _ in principales}
            otras = sorted({(u["club"], u["coach"]) for u in met["unidades"]
                            if u["coach"] in [co for _, co in HISTORIAS] and (u["club"], u["coach"]) not in pr})
            hid_de = {co: h for h, co in HISTORIAS}
            for club, coach in otras:
                te = time.time()
                r = mide_era(df, club, coach, rng, a.n_boot)
                if r["n_poss"] < MIN_POSS_EXPL:          # D61A-3
                    r["hueco"] = (f"solo {r['n_poss']} posesiones; el mínimo preinscrito es "
                                  f"{MIN_POSS_EXPL}")
                    for k in ("L", "tau"):
                        r[k]["evaluable"] = False
                for k in ("L", "tau"):
                    r[k].pop("p", None)                   # sin p y sin q: no es una prueba
                r.pop("jugada", None)                     # D61-7 sigue solo para la principal
                r["hid"], r["principal"], r["exploratoria"] = hid_de[coach], False, True
                todas.append(r)
                print(f"  [descriptiva] {club:<18s} {coach:<18s} "
                      f"L {r['L']['era']:.3f} vs {r['L']['base']:.3f} · {time.time() - te:.0f} s", flush=True)
        fam = [(i, k) for i, e in enumerate(eras) for k in ("L", "tau") if e[k]["evaluable"]]
        qs, rech = bh([eras[i][k]["p"] for i, k in fam]) if fam else ([], [])
        for (i, k), q, r in zip(fam, qs, rech):
            eras[i][k]["q"], eras[i][k]["rechaza"] = q, bool(r)
        for e in eras:
            for k in ("L", "tau"):
                e[k].setdefault("rechaza", False)
        prev = Path(a.out)
        if prev.exists():                                # D61A-1
            vj = json.loads(prev.read_text(encoding="utf-8"))
            for e in eras:
                p0 = next((x for x in vj.get("eras", []) if x["club"] == e["club"] and x["coach"] == e["coach"]), None)
                if p0 is None:
                    continue
                for k in ("L", "tau"):
                    if not (p0[k]["evaluable"] and e[k]["evaluable"]):
                        if p0[k]["evaluable"] != e[k]["evaluable"]:
                            raise Aborta(f"D61A-1: {e['club']}·{e['coach']} {k} cambió de evaluable")
                        continue
                    for campo in ("era", "base", "D"):
                        if abs(p0[k][campo] - e[k][campo]) > 1e-9:
                            raise Aborta(f"D61A-1: {e['club']}·{e['coach']} {k}.{campo} se movió "
                                         f"({p0[k][campo]} → {e[k][campo]})")
                    if abs(p0[k]["p"] - e[k]["p"]) > 1e-9:
                        raise Aborta(f"D61A-1: {e['club']}·{e['coach']} {k}.p se movió")
            print("D61A-1: las cinco eras principales reproducen lo publicado")
        if len(fam) != 10 and not a.solo_principales:   # D61A-2
            raise Aborta(f"F61 pasó de 10 a {len(fam)} contrastes; la adenda 1 no puede tocar la familia")
        # liga: 1.6 y 1.7
        import polars as pl
        orden = h4["parametros"]["torneos_orden"]
        tors = [t for t in orden if t in set(df["torneo"].unique().to_list())]
        surv = []
        npos = {}
        for t in tors:
            P, al, sub = liga_torneo(df, t)
            Ls = largos(sub)
            so, sm = supervivencia_obs(Ls), supervivencia_modelo(P, al)
            npos[t] = int((Ls >= 2).sum())
            surv.append({"torneo": t, "n_poss": npos[t], "descartadas_L1": int((Ls < 2).sum()),
                         "S_obs": so, "S_mod": sm, "ks": float(np.max(np.abs(np.array(so) - np.array(sm)))),
                         "encima_12": so[11] > sm[11], "debajo_5": so[4] < sm[4]})
        t_fig = max(tors, key=lambda t: (npos[t], -orden.index(t)))
        P, al, _ = liga_torneo(df, t_fig)
        lam_b = {}
        for fi, fn in enumerate(FASES):
            b = bloque(fi)
            w = np.linalg.eigvals(P[np.ix_(b, b)])
            lam_b[fn] = float(np.max(w.real))
        ob = bloque(0)
        liga16 = cuasi(P[np.ix_(ob, ob)], al[ob], frames=True)
        if liga16 is None:
            raise Aborta(f"el bloque de juego abierto de la liga ({t_fig}) no es irreducible")
        met_glob = {e["hid"]: next(u for u in met["unidades"] if u["club"] == e["club"] and u["coach"] == e["coach"])
                    ["global"]["field_tilt"]["dif"] for e in eras}
        h4_rel = {e["hid"]: unidad_h4(h4, e["club"], e["coach"])["rel_E_T_vs_liga"] for e in eras}
        preds = predicciones(eras, met_glob, h4_rel, surv)
    except Aborta as e:
        sys.exit(f"ABORTA: {e}")
    comun = {"adr": "ADR-61", "preinscripcion": PREINSCRIPCION, "reglas_preinscritas": REGLAS}
    salida = {**comun,
              "parametros": {"franja_ix": FRANJA_IX, "franja": FRANJA_TXT, "n_boot": a.n_boot, "seed": SEED,
                             "alpha": ALPHA, "lambda": 0},
              "verificacion_base": verif,
              "eras": eras, "familia": {"m": len(fam), "n_rechazados": int(sum(rech))},
              "eras_todas": ([{**e, "principal": True, "exploratoria": False} for e in eras] + todas
                             if not a.solo_principales else None),
              "adenda1": {"min_poss": MIN_POSS_EXPL, "n_descriptivas": len(todas),
                          "nota": "las eras no principales son descriptivas: sin p, sin q y fuera del marcador"},
              "predicciones": preds, "segundos": round(time.time() - t0, 1)}
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    sv = {**comun, "fase": d0,
          "liga_16": {"torneo": t_fig, "n_poss": npos[t_fig], "lambda_bloques": lam_b, **liga16},
          "supervivencia": {"k_max": K_MAX, "por_torneo": surv, "torneo_figura": t_fig,
                            "encima_12": sum(s["encima_12"] for s in surv),
                            "debajo_5": sum(s["debajo_5"] for s in surv), "de": len(surv)}}
    Path(a.out_surv).write_text(json.dumps(sv, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"escrito {a.out} y {a.out_surv} · F61 {len(fam)} contrastes, {int(sum(rech))} rechazan · "
          f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
