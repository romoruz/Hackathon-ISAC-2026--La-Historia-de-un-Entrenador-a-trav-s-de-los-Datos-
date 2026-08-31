#!/usr/bin/env python3
"""
03_bondad_ajuste_longitud.py — Contraste global del supuesto de Markov.

LA IDEA
-------
En una cadena absorbente, el numero de pasos hasta la absorcion T tiene
distribucion PHASE-TYPE discreta, con funcion de supervivencia

    P(T > k) = alpha^T Q^k 1

donde alpha es la distribucion inicial sobre estados transitorios. Es decir: la
cadena IMPLICA una distribucion de longitud de posesion, analiticamente y sin
simular. Compararla contra la empirica es un contraste GLOBAL del supuesto de
Markov de primer orden -- no renglon por renglon, sino de la cadena entera.

QUE ESPERAR SI MARKOV FALLA
---------------------------
La empirica tendra cola mas pesada que la predicha: las posesiones reales tienen
memoria (un equipo que ya encadeno 8 pases esta en un estado de control que la
zona por si sola no captura), asi que sobreviven mas de lo que predice un
proceso sin memoria. El diagnostico tipico es "hay que ampliar el estado".

DOS CUIDADOS, AMBOS REPORTADOS EN LA SALIDA
-------------------------------------------
C1. Los parametros se estiman de los MISMOS datos, asi que la nula de KS no es
    la estandar. Se calibra por bootstrap parametrico (tipo Lilliefors):
    simular desde la cadena ajustada, reajustar, recalcular KS.
C2. La absorcion terminal (ADR-14) es una transicion ARTIFICIAL. Parte de la
    cola es construccion propia. Se reporta la fraccion afectada.
C3. TRUNCAMIENTO. `possession.min_actions` descarta las posesiones cortas, asi
    que P(T < min_actions) = 0 por construccion mientras que la cadena les
    asigna masa. Sin condicionar, el KS mide ESE hueco y nada mas: en la
    primera version de este script el estadistico completo venia del punto
    k=1. Aqui se compara contra la phase-type CONDICIONADA a T >= min_actions,
    y el bootstrap simula con el mismo truncamiento.

Uso:
  python scripts/03_bondad_ajuste_longitud.py --unit coach --value "Andre Jardine"
  python scripts/03_bondad_ajuste_longitud.py --unit team --value "América" --lam 0
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
    from dtdecoder.estimate import count_matrix, shrink
    from dtdecoder.grid import StateSpace
except ImportError:
    sys.exit("Corre esto con el venv activado y dtdecoder instalado.")

_EPS = 1e-12


def _space(cfg: Config) -> StateSpace:
    p = cfg["pitch"]
    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    return StateSpace(nx=p["nx"], ny=p["ny"], length=p["length"], width=p["width"],
                      phases=phases)


def longitudes_empiricas(trans: pl.DataFrame) -> np.ndarray:
    """Numero de transiciones por posesion = pasos hasta absorcion."""
    return (
        trans.group_by("poss_uid").len().rename({"len": "T"})["T"].to_numpy().astype(int)
    )


def dist_inicial(trans: pl.DataFrame, space: StateSpace) -> np.ndarray:
    """alpha: distribucion sobre estados transitorios del PRIMER paso."""
    primero = (
        trans.sort(["poss_uid", "from_state"])
        .group_by("poss_uid", maintain_order=True)
        .agg(pl.col("from_state").first())
    )
    a = np.zeros(space.n_transient)
    vals, cnt = np.unique(primero["from_state"].to_numpy().astype(int), return_counts=True)
    ok = vals < space.n_transient
    a[vals[ok]] = cnt[ok]
    return a / max(a.sum(), _EPS)


def superviv_teorica(Q: np.ndarray, alpha: np.ndarray, kmax: int) -> np.ndarray:
    """S[k] = P(T > k) para k = 0..kmax, via alpha^T Q^k 1."""
    S = np.empty(kmax + 1)
    v = alpha.copy()
    for k in range(kmax + 1):
        S[k] = float(v.sum())
        v = v @ Q
    return np.clip(S, 0.0, 1.0)


def pmf_desde_superviv(S: np.ndarray) -> np.ndarray:
    """P(T = k) = S[k-1] - S[k], para k = 1..len(S)-1."""
    p = -np.diff(S)
    return np.clip(p, 0.0, None)


def condiciona(pmf: np.ndarray, t_min: int) -> np.ndarray:
    """pmf de T | T >= t_min. Anula k < t_min y renormaliza."""
    q = pmf.copy()
    q[: max(t_min - 1, 0)] = 0.0
    return q / max(q.sum(), _EPS)


def ks_discreto(obs: np.ndarray, pmf: np.ndarray, t_min: int = 1) -> float:
    """KS entre la ECDF y una pmf sobre {1, ..., K}, ambas condicionadas.

    `t_min` implementa C3: los soportes deben coincidir o el estadistico mide
    el truncamiento en vez del ajuste.
    """
    K = len(pmf)
    obs = obs[obs >= t_min]
    cnt = np.bincount(np.clip(obs, 1, K), minlength=K + 1)[1:]
    ecdf = np.cumsum(cnt) / max(cnt.sum(), 1)
    tcdf = np.cumsum(condiciona(pmf, t_min))
    tcdf = tcdf / max(tcdf[-1], _EPS)
    return float(np.abs(ecdf - tcdf).max())


def simula_longitudes(P: np.ndarray, alpha: np.ndarray, n: int,
                      n_transient: int, rng: np.random.Generator,
                      kmax: int = 200) -> np.ndarray:
    """Simula n posesiones desde la cadena y devuelve sus longitudes."""
    estados = rng.choice(len(alpha), size=n, p=alpha)
    vivos = np.ones(n, dtype=bool)
    T = np.zeros(n, dtype=int)
    cum = np.cumsum(P, axis=1)
    for _ in range(kmax):
        idx = np.flatnonzero(vivos)
        if idx.size == 0:
            break
        u = rng.random(idx.size)
        nxt = (cum[estados[idx]] < u[:, None]).sum(axis=1)
        nxt = np.clip(nxt, 0, P.shape[1] - 1)
        T[idx] += 1
        absorbe = nxt >= n_transient
        vivos[idx[absorbe]] = False
        vivo_idx = idx[~absorbe]
        estados[vivo_idx] = nxt[~absorbe]
    return T


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--indir", default="data/processed")
    ap.add_argument("--unit", default="coach")
    ap.add_argument("--value", required=True)
    ap.add_argument("--lam", type=float, default=0.0,
                    help="encogimiento; 0 = EMV crudo (default, evita mezclar "
                         "el efecto del prior con el ajuste)")
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260819)
    ap.add_argument("--kmax", type=int, default=40)
    ap.add_argument("--t-min", type=int, default=None,
                    help="truncamiento; default: config.possession.min_actions")
    ap.add_argument("--out", default="reports/bondad_ajuste_longitud.json")
    args = ap.parse_args()

    cfg = Config.load(args.config)
    space = _space(cfg)

    p = Path(args.indir) / "transitions.parquet"
    if not p.exists():
        sys.exit(f"No existe {p}. Corre `dtdecoder phase0` primero.")
    trans = pl.read_parquet(p)

    if args.unit not in trans.columns:
        sys.exit(f"No existe la columna '{args.unit}' en transitions.parquet")
    sub = trans.filter(pl.col(args.unit) == args.value)
    if sub.height == 0:
        disp = trans[args.unit].drop_nulls().unique().to_list()
        sys.exit(f"Sin transiciones para {args.unit}='{args.value}'. Hay: {disp}")

    C = count_matrix(sub, space)
    uniforme = np.full((space.n_transient, space.n_states), 1.0 / space.n_states)
    P = shrink(C, uniforme, args.lam)
    Q = P[:, : space.n_transient]
    alpha = dist_inicial(sub, space)

    t_min = args.t_min if args.t_min is not None else int(
        cfg["possession"].get("min_actions", 1))

    obs = longitudes_empiricas(sub)
    S = superviv_teorica(Q, alpha, args.kmax)
    pmf = pmf_desde_superviv(S)
    pmf_c = condiciona(pmf, t_min)

    ks_obs = ks_discreto(obs, pmf, t_min)

    # E[T] teorico SIN condicionar = alpha^T N 1 (Neumann via solve)
    N1 = np.linalg.solve(np.eye(space.n_transient) - Q, np.ones(space.n_transient))
    ET_teo_bruto = float(alpha @ N1)
    # E[T | T >= t_min]: es lo comparable con los datos truncados
    ks_grid = np.arange(1, len(pmf) + 1)
    ET_teo = float((ks_grid * pmf_c).sum())
    ET_emp = float(obs[obs >= t_min].mean())

    # Bootstrap parametrico (Lilliefors): simular, reajustar, recalcular KS.
    rng = np.random.default_rng(args.seed)
    n = len(obs)
    nulos = np.full(args.n_boot, np.nan)
    for b in range(args.n_boot):
        # Simular de mas y truncar igual que los datos (C3).
        sim = simula_longitudes(P, alpha, int(n * 2.5) + 50, space.n_transient, rng)
        sim = sim[sim >= t_min]
        if len(sim) < n:
            continue
        nulos[b] = ks_discreto(sim[:n], pmf, t_min)
    nulos = nulos[~np.isnan(nulos)]
    if len(nulos) == 0:
        sys.exit("El bootstrap no produjo replicas validas; sube --kmax.")
    pval = float((1.0 + (nulos >= ks_obs).sum()) / (1.0 + len(nulos)))

    # Cola: donde se separan
    K = min(args.kmax, int(obs.max()))
    o = obs[obs >= t_min]
    cnt = np.bincount(np.clip(o, 1, K), minlength=K + 1)[1:]
    S_emp = 1.0 - np.cumsum(cnt) / cnt.sum()
    S_teo = 1.0 - np.cumsum(condiciona(pmf, t_min))[:K]

    res = {
        "unidad": f"{args.unit}={args.value}",
        "lambda": args.lam,
        "min_actions_truncamiento": t_min,
        "n_posesiones": int(n),
        "P_T_menor_que_tmin_segun_cadena": round(float(pmf[: t_min - 1].sum()), 4)
        if t_min > 1 else 0.0,
        "E_T_teorico_sin_condicionar": round(ET_teo_bruto, 4),
        "E_T_empirico": round(ET_emp, 4),
        "E_T_teorico": round(ET_teo, 4),
        "sesgo_relativo": round((ET_teo - ET_emp) / ET_emp, 4),
        "KS_observado": round(ks_obs, 5),
        "KS_nula_p95": round(float(np.percentile(nulos, 95)), 5),
        "p_valor": pval,
        "markov_rechazado": bool(pval < 0.05),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))

    print(f"\n== Supervivencia P(T > k | T >= {t_min}): empirica vs teorica ==")
    print(f"{'k':>3} {'empirica':>10} {'teorica':>10} {'dif':>9}")
    for k in range(1, min(K, 20) + 1):
        d = S_emp[k - 1] - S_teo[k - 1]
        print(f"{k:>3} {S_emp[k-1]:>10.4f} {S_teo[k-1]:>10.4f} {d:>+9.4f}")

    print("\nLECTURA")
    print("  dif > 0 sostenida  = la empirica sobrevive MAS que la predicha:")
    print("                       cola pesada, indicio de memoria. Markov de")
    print("                       primer orden es demasiado pobre; el remedio")
    print("                       es ampliar el estado, no cambiar de modelo.")
    print("  dif < 0 sostenida  = el modelo alarga de mas. Revisar la absorcion")
    print("                       terminal (ADR-14) antes que el supuesto Markov.")
    print(f"\n  Ambas curvas condicionadas a T >= {t_min} (C3). Los primeros")
    print("  k por debajo del truncamiento no se comparan: ahi no hay datos por")
    print("  construccion, no por desajuste del modelo.")
    print("\n  CUIDADO C2: parte de la cola viene de la absorcion terminal, que es")
    print("  artificial. Un rechazo NO invalida el trabajo (05_VALIDATION §4.1):")
    print("  indica que conviene ampliar el estado. Reportalo, no lo escondas.")


if __name__ == "__main__":
    main()
