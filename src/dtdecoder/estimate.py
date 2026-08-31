"""
Fase 1 -- Estimacion de la matriz de transicion.

TEORIA (esto es lo que defiendes ante el jurado):

La verosimilitud de una cadena de Markov observada se factoriza por renglones,

    L(P | datos) = prod_{i,j} p_ij^{n_ij}

de modo que el EMV es p_ij = n_ij / n_i y cada renglon es un problema
multinomial independiente PESE a que la cadena es dependiente (Billingsley,
1961, "Statistical Methods in Markov Chains", Ann. Math. Statist.). Eso es lo
que legitima usar inferencia multinomial estandar sobre datos secuenciales.

El EMV crudo es inutilizable en renglones ralos. Usamos el estimador de
encogimiento hacia la media de la liga:

    p*_ij(lam) = (n_ij + lam * q_ij) / (n_i + lam)

con q = renglon de la liga. Doble lectura, ambas correctas:
  - frecuentista: estimador de encogimiento tipo James-Stein. Mete sesgo hacia
    q a cambio de reducir varianza; con n_i grande el sesgo se desvanece.
  - bayesiana   : es exactamente la media posterior con prior Dirichlet(lam*q),
    donde lam es el tamano de muestra efectivo del prior.

lam NO se fija a ojo: se elige por validacion cruzada por bloques de posesion
maximizando log-verosimilitud fuera de muestra. El lam* resultante es en si
mismo interpretable: "hacen falta lam* observaciones para que la evidencia del
DT domine al promedio de la liga".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from .grid import StateSpace

_EPS = 1e-12


# --------------------------------------------------------------------------
# Conteos
# --------------------------------------------------------------------------
def count_matrix(trans: pl.DataFrame, space: StateSpace) -> np.ndarray:
    """Matriz de conteos C de forma (n_transient, n_states)."""
    C = np.zeros((space.n_transient, space.n_states), dtype=np.float64)
    if trans.height == 0:
        return C
    i = trans["from_state"].to_numpy().astype(int)
    j = trans["to_state"].to_numpy().astype(int)
    np.add.at(C, (i, j), 1.0)
    return C


def counts_by_group(
    trans: pl.DataFrame, space: StateSpace, by: str
) -> dict[str, np.ndarray]:
    """Conteos separados por un campo categorico (`score_state`, `phase`, ...)."""
    return {
        str(key[0]): count_matrix(sub, space)
        for key, sub in trans.group_by([by], maintain_order=True)
    }


# --------------------------------------------------------------------------
# Estimadores
# --------------------------------------------------------------------------
def mle(C: np.ndarray) -> np.ndarray:
    """EMV crudo. Renglones vacios quedan en cero (bandera de rala)."""
    n = C.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        P = np.where(n > 0, C / np.maximum(n, _EPS), 0.0)
    return P


def shrink(C: np.ndarray, Q: np.ndarray, lam: float) -> np.ndarray:
    """Estimador de encogimiento p*(lam) hacia el renglon de liga Q.

    Q debe ser una matriz estocastica por renglones (la de la liga). Renglones
    de Q vacios se sustituyen por la uniforme para no propagar ceros.
    """
    Q = _repair_rows(Q)
    n = C.sum(axis=1, keepdims=True)
    P = (C + lam * Q) / np.maximum(n + lam, _EPS)
    # Si n_i = 0 y lam = 0 el renglon queda indefinido: cae a la liga.
    empty = (n.ravel() + lam) <= _EPS
    P[empty] = Q[empty]
    return _renormalize(P)


def _repair_rows(P: np.ndarray) -> np.ndarray:
    P = np.array(P, dtype=float, copy=True)
    s = P.sum(axis=1)
    bad = s <= _EPS
    if bad.any():
        P[bad] = 1.0 / P.shape[1]
    return _renormalize(P)


def _renormalize(P: np.ndarray) -> np.ndarray:
    s = P.sum(axis=1, keepdims=True)
    return P / np.maximum(s, _EPS)


# --------------------------------------------------------------------------
# Validacion cruzada para lambda
# --------------------------------------------------------------------------
@dataclass
class CVResult:
    lam_star: float
    grid: np.ndarray
    scores: np.ndarray  # log-verosimilitud media fuera de muestra por lam

    def summary(self) -> str:
        return (
            f"lambda* = {self.lam_star:g}  "
            f"(loglik OOS = {self.scores.max():.4f} nats/transicion)"
        )


def _uids_ordenados(trans: pl.DataFrame) -> np.ndarray:
    """Identificadores de posesion en orden CANONICO.

    `unique()` en polars NO garantiza orden: depende del hashing y del
    paralelismo, y puede variar entre corridas del mismo proceso. Una semilla
    fija sobre un vector cuyo orden cambia produce una permutacion distinta
    cada vez: la semilla parece funcionar y no funciona.

    Sintoma observado: tres corridas del mismo `dtdecoder phase1`, mismo
    config, misma cv_seed, dieron loglik OOS de -2.1283, -2.1276 y -2.1287.

    08_REPRODUCIBILITY §8 exige que todo `default_rng()` lleve semilla
    explicita. Este es el caso hermano: la semilla esta, el input no es
    determinista. Ordenar es lo que hace que la semilla signifique algo.
    """
    return trans["poss_uid"].unique().sort().to_numpy()


def possession_folds(
    trans: pl.DataFrame, k: int, seed: int
) -> list[np.ndarray]:
    """Particion en k folds POR POSESION, no por evento.

    Partir por evento filtraria informacion entre train y test: dos acciones de
    la misma posesion estan fuertemente correlacionadas y el lam optimo saldria
    artificialmente bajo.

    Los pliegues son DETERMINISTAS dados (trans, k, seed): ver
    `_uids_ordenados` para por que hace falta ordenar antes de barajar.
    """
    uids = _uids_ordenados(trans)
    rng = np.random.default_rng(seed)
    rng.shuffle(uids)
    return [np.asarray(part) for part in np.array_split(uids, k)]


def cv_lambda(
    trans: pl.DataFrame,
    space: StateSpace,
    league_P: np.ndarray,
    lam_grid: list[float],
    k: int = 5,
    seed: int = 0,
) -> CVResult:
    """Elige lambda maximizando log-verosimilitud fuera de muestra."""
    folds = possession_folds(trans, k, seed)
    grid = np.asarray(lam_grid, dtype=float)
    total = np.zeros(len(grid))
    total_n = 0.0

    for f in range(len(folds)):
        test_ids = set(folds[f].tolist())
        mask = trans["poss_uid"].is_in(list(test_ids))
        test = trans.filter(mask)
        train = trans.filter(~mask)
        if train.height == 0 or test.height == 0:
            continue
        C_tr = count_matrix(train, space)
        C_te = count_matrix(test, space)
        n_te = C_te.sum()
        total_n += n_te
        for gi, lam in enumerate(grid):
            P = shrink(C_tr, league_P, lam)
            total[gi] += float((C_te * np.log(np.maximum(P, _EPS))).sum())

    scores = total / max(total_n, 1.0)
    return CVResult(lam_star=float(grid[int(np.argmax(scores))]), grid=grid, scores=scores)


# --------------------------------------------------------------------------
# Diagnosticos
# --------------------------------------------------------------------------
def sparsity_report(C: np.ndarray, min_count: int = 30) -> dict[str, float]:
    n = C.sum(axis=1)
    return {
        "n_rows": int(C.shape[0]),
        "n_transitions": float(C.sum()),
        "rows_empty": int((n == 0).sum()),
        "rows_below_min": int((n < min_count).sum()),
        "frac_below_min": float((n < min_count).mean()),
        "median_row_count": float(np.median(n)),
        "params_per_obs": float(C.shape[0] * (C.shape[1] - 1) / max(C.sum(), 1.0)),
    }


def error_curve(
    trans: pl.DataFrame,
    space: StateSpace,
    league_P: np.ndarray,
    lam: float,
    fractions: tuple[float, ...] = (0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0),
    n_rep: int = 5,
    seed: int = 0,
) -> pl.DataFrame:
    """Curva error-vs-N: submuestrea posesiones y compara contra el ajuste full.

    Esta es la grafica que justifica tu eleccion de nx, ny ante el jurado.
    Error = norma infinito por renglon (max |p*_sub - p*_full|), promediada
    sobre renglones con soporte, ponderada por masa de visitas.
    """
    rng = np.random.default_rng(seed)
    uids = _uids_ordenados(trans)  # mismo motivo que en possession_folds
    C_full = count_matrix(trans, space)
    P_full = shrink(C_full, league_P, lam)
    w = C_full.sum(axis=1)
    w = w / max(w.sum(), 1.0)

    rows = []
    for frac in fractions:
        for rep in range(n_rep if frac < 1.0 else 1):
            m = max(1, int(round(frac * len(uids))))
            pick = rng.choice(uids, size=m, replace=False)
            sub = trans.filter(pl.col("poss_uid").is_in(pick.tolist()))
            P_sub = shrink(count_matrix(sub, space), league_P, lam)
            err_row = np.abs(P_sub - P_full).max(axis=1)
            rows.append(
                {
                    "fraction": frac,
                    "rep": rep,
                    "n_possessions": m,
                    "err_weighted": float((err_row * w).sum()),
                    "err_median": float(np.median(err_row)),
                }
            )
    return pl.DataFrame(rows)
