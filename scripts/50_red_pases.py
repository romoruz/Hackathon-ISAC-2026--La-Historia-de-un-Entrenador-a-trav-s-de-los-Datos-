#!/usr/bin/env python3
"""
50_red_pases.py — ADR-62: la red de pases. UNA SOLA CORRIDA.

Mide, para cada pareja de técnicos consecutivos del mismo club:

  T_red   ½‖p_a − p_b‖₁ sobre los pares (pasador → receptor) de los jugadores
          presentes en las dos eras, renormalizando a esos pares. 0 = idéntica.
  ΔG      diferencia del Gini del reparto de pases por jugador entre las dos eras.
  φ_U     parte del cambio que viene del USO, por la descomposición de punto
          medio de ADR-60 §3 (la misma función, con referencia 0).

          AVISO DECLARADO: la descomposición de ADR-60 descompone un vector.
          Aquí la unidad es el PASADOR y su perfil es a quién pasa, así que lo
          que φ_U descompone es el cambio en la distribución marginal de
          RECEPCIÓN, no la matriz de pares que mide T_red. Son dos cosas
          distintas y por eso φ_U se publica descriptivo y fuera de F62, tal y
          como preinscribe ADR-62 §2.

Nulo (ADR-62 §4): permutación de las etiquetas de era ENTRE PARTIDOS, B = 2000.
Familia F62 (§5): relevos evaluables de las cinco historias × {T_red, ΔG}, BH 5%.

Uso:
    python scripts/50_red_pases.py                    # la corrida buena
    python scripts/50_red_pases.py --corrida 2 ...    # cualquier otra: fuera de F62
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
PASES = RAIZ / "data" / "pases_api" / "pases.parquet"
COTEJO = RAIZ / "reports" / "pases_cotejo.json"

B = 2000
SEED = 20260923
ALPHA = 0.05
MIN_PASES_ERA = 3000        # D62-1
MIN_JUG_ERA = 20            # D62-1
MIN_PASES_JUG = 100         # D62-2
MIN_COMUNES = 8             # D62-3
TOL = 1e-9

HISTORIAS = [("jardine", "Andre Jardine"), ("larcamon", "Nicolas Larcamon"),
             ("ambriz", "Ignacio Ambriz"), ("herrera", "Miguel Herrera"),
             ("ortiz", "Fernando Ortiz")]


class Aborta(Exception):
    pass


# --------------------------------------------------------------- piezas ----
def gini(x):
    """Gini del reparto de pases por jugador. 0 = todos igual, →1 = uno solo."""
    x = np.sort(np.asarray(x, float))
    n = len(x)
    if n == 0 or x.sum() <= 0:
        return None
    i = np.arange(1, n + 1)
    return float((2 * (i * x).sum()) / (n * x.sum()) - (n + 1) / n)


def T_pares(A, Bm):
    """½‖p_a − p_b‖₁ entre dos matrices de conteos, cada una normalizada aparte."""
    sa, sb = A.sum(), Bm.sum()
    if sa <= 0 or sb <= 0:
        return None
    return float(np.abs(A / sa - Bm / sb).sum() / 2)


def descompone(Ya, Yb, compartidos):
    """Descomposición de punto medio de ADR-60 §3, con referencia 0.
    Ya, Yb: (J pasadores × J receptores). Δ = U + C exacto."""
    Na, Nb = Ya.sum(), Yb.sum()
    na, nb = Ya.sum(1), Yb.sum(1)
    wa, wb = na / Na, nb / Nb
    delta = Yb.sum(0) / Nb - Ya.sum(0) / Na
    S = compartidos & (na > 0) & (nb > 0)
    za = np.where(S[:, None], Ya / np.maximum(na, 1)[:, None], 0.0)
    zb = np.where(S[:, None], Yb / np.maximum(nb, 1)[:, None], 0.0)
    wbar, dw = (wa + wb) / 2, wb - wa
    U = (wbar[S, None] * (zb[S] - za[S])).sum(0)
    C_S = (dw[S, None] * ((za[S] + zb[S]) / 2)).sum(0)
    noS = ~S
    C_no = Yb[noS].sum(0) / Nb - Ya[noS].sum(0) / Na
    C = C_S + C_no
    return delta, U, C


def phi_U(Ya, Yb, S):
    d, U, C = descompone(Ya, Yb, S)
    if np.abs(d - (U + C)).max() > 1e-9:                      # identidad exacta
        raise Aborta("la descomposición no cumple Δ = U + C")
    nU, nC = np.abs(U).sum(), np.abs(C).sum()
    return {"T_marginal": float(np.abs(d).sum() / 2), "U": float(nU / 2), "C": float(nC / 2),
            "phi_U": float(nU / (nU + nC)) if (nU + nC) > 0 else None}


def bh(p):
    p = np.asarray(p, float)
    m = len(p)
    if m == 0:
        return [], []
    o = np.argsort(p)
    q = np.empty(m)
    prev = 1.0
    for k in range(m - 1, -1, -1):
        prev = min(prev, p[o[k]] * m / (k + 1))
        q[o[k]] = prev
    return q.tolist(), (q <= ALPHA).tolist()


# ----------------------------------------------------------------- datos ----
def carga():
    import polars as pl
    if not PASES.exists():
        raise Aborta(f"falta {PASES}: corre scripts/49_pases_desde_crudo.py --extraer")   # D62-9
    if not COTEJO.exists():
        raise Aborta(f"falta {COTEJO}: corre scripts/49_pases_desde_crudo.py --cotejar")  # D62-9
    t = pl.read_parquet(PASES).filter(pl.col("completado") & pl.col("coach").is_not_null()
                                      & pl.col("player_id").is_not_null()
                                      & pl.col("recipient_id").is_not_null())
    return t


def red_por_partido(sub, idx):
    """[(match_id, matriz JxJ)] con los jugadores de idx. Precalculado una vez
    para que las 2 000 permutaciones sean sumas de matrices."""
    J = len(idx)
    out = []
    for (mid,), g in sub.group_by("match_id", maintain_order=True):
        M = np.zeros((J, J))
        for i, j, n in zip(*[g.group_by(["player_id", "recipient_id"]).agg(
                __import__("polars").len().alias("n"))[c].to_list()
                for c in ("player_id", "recipient_id", "n")]):
            a, b = idx.get(i), idx.get(j)
            if a is not None and b is not None:
                M[a, b] += n
        out.append((mid, M))
    return out


def pases_por_jugador(M):
    return M.sum(1) + M.sum(0)


# --------------------------------------------------------------- medición ----
def mide_relevo(t, club, ca, cb, rng):
    import polars as pl
    sa = t.filter((pl.col("team") == club) & (pl.col("coach") == ca))
    sb = t.filter((pl.col("team") == club) & (pl.col("coach") == cb))
    r = {"club": club, "a": ca, "b": cb,
         "n_pases_a": sa.height, "n_pases_b": sb.height}
    # D62-1
    jug_a = set(sa["player_id"].unique().to_list()) | set(sa["recipient_id"].unique().to_list())
    jug_b = set(sb["player_id"].unique().to_list()) | set(sb["recipient_id"].unique().to_list())
    r["n_jugadores_a"], r["n_jugadores_b"] = len(jug_a), len(jug_b)
    if sa.height < MIN_PASES_ERA or sb.height < MIN_PASES_ERA:
        r["hueco"] = (f"una de las dos etapas no llega a {MIN_PASES_ERA} pases completados "
                      f"({sa.height} y {sb.height})")
        return r
    if len(jug_a) < MIN_JUG_ERA or len(jug_b) < MIN_JUG_ERA:
        r["hueco"] = f"menos de {MIN_JUG_ERA} jugadores en una etapa"
        return r
    # D62-7: ningún partido en las dos eras
    ma = set(sa["match_id"].unique().to_list())
    mb = set(sb["match_id"].unique().to_list())
    if ma & mb:
        raise Aborta(f"D62-7: {len(ma & mb)} partidos caen en las dos eras de {club} {ca}↔{cb}")
    # universo de jugadores y matrices por partido
    todos = sorted(jug_a | jug_b)
    idx = {p: k for k, p in enumerate(todos)}
    pp_a, pp_b = red_por_partido(sa, idx), red_por_partido(sb, idx)
    Ma = sum(m for _, m in pp_a)
    Mb = sum(m for _, m in pp_b)
    # D62-2 y D62-3: jugadores con al menos MIN_PASES_JUG en LAS DOS
    na, nb = pases_por_jugador(Ma), pases_por_jugador(Mb)
    comunes = (na >= MIN_PASES_JUG) & (nb >= MIN_PASES_JUG)
    r["n_jugadores_comunes"] = int(comunes.sum())
    if comunes.sum() < MIN_COMUNES:
        r["hueco"] = (f"solo {int(comunes.sum())} jugadores con {MIN_PASES_JUG}+ pases en las dos "
                      f"etapas; el mínimo preinscrito es {MIN_COMUNES}")
        return r
    sel = np.ix_(comunes, comunes)

    def estad(A, Bm):
        return T_pares(A[sel], Bm[sel]), gini(pases_por_jugador(Bm)) - gini(pases_por_jugador(A))

    T_obs, dG_obs = estad(Ma, Mb)
    if T_obs is None or not (0 - TOL <= T_obs <= 1 + TOL):                     # D62-5
        raise Aborta(f"D62-5: T_red = {T_obs} fuera de [0, 1] en {club} {ca}↔{cb}")
    for X in (Ma[sel], Mb[sel]):                                               # D62-4
        if abs(X.sum() / max(X.sum(), 1) - 1) > TOL:
            raise Aborta("D62-4: una red no normaliza a 1")
    ph = phi_U(Ma, Mb, comunes)
    if ph["phi_U"] is not None and not (0 - TOL <= ph["phi_U"] <= 1 + TOL):    # D62-5
        raise Aborta(f"D62-5: φ_U = {ph['phi_U']} fuera de [0, 1]")

    # nulo por permutación de etiquetas de era ENTRE PARTIDOS (§4)
    todos_p = [m for _, m in pp_a] + [m for _, m in pp_b]
    k = len(pp_a)
    Ts, dGs = [], []
    for _ in range(B):
        o = rng.permutation(len(todos_p))
        A = sum(todos_p[i] for i in o[:k])
        Bm = sum(todos_p[i] for i in o[k:])
        T2, g2 = estad(A, Bm)
        if T2 is not None and g2 is not None:
            Ts.append(T2)
            dGs.append(g2)
    Ts, dGs = np.array(Ts), np.array(dGs)
    r["T_red"] = {"v": T_obs, "p": float((Ts >= T_obs).mean()),
                  "nulo_p50": float(np.percentile(Ts, 50)), "nulo_p90": float(np.percentile(Ts, 90)),
                  "supera_p90": bool(T_obs > np.percentile(Ts, 90)), "replicas": int(len(Ts))}
    r["gini"] = {"a": gini(na), "b": gini(nb), "delta": dG_obs,
                 "p": float((np.abs(dGs) >= abs(dG_obs)).mean()),
                 "ic95": [float(np.percentile(dGs, 2.5)), float(np.percentile(dGs, 97.5))],
                 "replicas": int(len(dGs))}
    r["phi_U"] = ph
    # sesgo 2 de ADR-62 §7: cuánto de la red pasa por el portero más usado
    r["portero"] = {"parte_a": float(na.max() / max(na.sum(), 1)),
                    "parte_b": float(nb.max() / max(nb.sum(), 1))}
    r["en_f62"] = False       # lo fija main() según §5
    return r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports", default=str(RAIZ / "reports"))
    ap.add_argument("--out", default=str(RAIZ / "reports" / "red_pases_v1.json"))
    ap.add_argument("--corrida", type=int, default=1,
                    help="1 es la corrida preinscrita. Cualquier otra queda FUERA de F62 (D62-8)")
    ap.add_argument("--n-perm", type=int, default=B)
    a = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    try:
        import polars as pl
        t = carga()
        h4 = json.loads((Path(a.reports) / "did_h4_v1.json").read_text(encoding="utf-8"))
        coaches = {c for _, c in HISTORIAS}
        rel = []
        for p in h4["pares"]:
            r = mide_relevo(t, p["club"], p["a"], p["b"], rng)
            r["de_una_historia"] = bool({p["a"], p["b"]} & coaches)
            rel.append(r)
            est = (f"T {r['T_red']['v']:.3f} (nulo p90 {r['T_red']['nulo_p90']:.3f}) · "
                   f"ΔG {r['gini']['delta']:+.3f} · φ_U {r['phi_U']['phi_U']:.2f}"
                   if "T_red" in r else r["hueco"])
            print(f"  {p['club']:<18s} {p['a'][:18]:<18s} ↔ {p['b'][:18]:<18s} {est}", flush=True)
        # F62 (§5): relevos evaluables DE LAS CINCO HISTORIAS × {T_red, ΔG}
        fam = [(i, k) for i, r in enumerate(rel) if "T_red" in r and r["de_una_historia"]
               for k in ("T_red", "gini")]
        qs, rech = bh([rel[i][k]["p"] for i, k in fam])
        for (i, k), q, rr in zip(fam, qs, rech):
            rel[i][k]["q"], rel[i][k]["rechaza"] = q, bool(rr)
            rel[i]["en_f62"] = a.corrida == 1
        if a.corrida == 1:
            esperados = 2 * len({i for i, _ in fam})
            if len(fam) != esperados:                                          # D62-6
                raise Aborta(f"D62-6: F62 tiene {len(fam)} contrastes y esperaba {esperados}")
        # predicciones preinscritas (§3)
        ev = [r for r in rel if "T_red" in r and r["de_una_historia"]]
        n = len(ev)
        p1 = sum(not r["T_red"]["supera_p90"] for r in ev)
        p2 = sum(r["gini"]["ic95"][0] <= r["gini"]["delta"] <= r["gini"]["ic95"][1] for r in ev)
        p3 = sum((r["phi_U"]["phi_U"] or 0) < .5 for r in ev)
        preds = [
            {"n": 1, "hip": "H62-1", "texto": "la red no se mueve más que sin cambiar de técnico "
             "en la mayoría de los relevos", "valor": f"{p1} de {n}", "cumple": p1 > n / 2 if n else None},
            {"n": 2, "hip": "H62-2", "texto": "la concentración del juego no se separa del cero "
             "en la mayoría", "valor": f"{p2} de {n}", "cumple": p2 > n / 2 if n else None},
            {"n": 3, "hip": "H62-3", "texto": "más de la mitad del cambio viene de que cambian los "
             "jugadores (φ_U < 0.5) en la mayoría", "valor": f"{p3} de {n}",
             "cumple": p3 > n / 2 if n else None, "nivel": "C"},
        ]
        salida = {"adr": "ADR-62", "corrida": a.corrida,
                  "preinscripcion": "docs/preinscritos/ADR-62_BORRADOR.md",
                  "parametros": {"B": a.n_perm, "seed": SEED, "alpha": ALPHA,
                                 "umbral_pases_era": MIN_PASES_ERA, "umbral_jugadores_era": MIN_JUG_ERA,
                                 "umbral_pases_jugador": MIN_PASES_JUG,
                                 "min_jugadores_comunes": MIN_COMUNES, "solo_completados": True},
                  "aviso_phi_U": "φ_U descompone el cambio en la distribución marginal de recepción "
                                 "(unidad: el pasador), no la matriz de pares que mide T_red. "
                                 "Descriptivo y fuera de F62, como preinscribe ADR-62 §2.",
                  "relevos": rel, "familia": {"m": len(fam), "n_rechazados": int(sum(rech))},
                  "predicciones": preds, "segundos": round(time.time() - t0, 1)}
    except Aborta as e:
        sys.exit(f"ABORTA: {e}")
    Path(a.out).write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n=== F62: {len(fam)} contrastes, {int(sum(rech))} rechazan ===")
    for p in preds:
        print(f"  {p['hip']}: {p['valor']} · "
              f"{'se cumplió' if p['cumple'] else 'FALLÓ' if p['cumple'] is False else 'no evaluable'}")
    print(f"\nescrito {a.out} · {time.time() - t0:.0f} s")
    if a.corrida == 1:
        print("Esta es LA corrida preinscrita. Lo que salió, salió.")


if __name__ == "__main__":
    main()
