"""Determinismo de la validacion cruzada.

EL BUG (encontrado 2026-08-20)
------------------------------
Tres corridas de `dtdecoder phase1 --value "Fernando Ortiz"`, mismo config,
misma `cv_seed = 20260819`, dieron:

    loglik OOS = -2.1283
    loglik OOS = -2.1276
    loglik OOS = -2.1287

Causa: `possession_folds` hacia `trans["poss_uid"].unique().to_numpy()` y
barajaba. `unique()` en polars no garantiza orden -- depende del hashing y del
paralelismo -- asi que la semilla fija barajaba un vector distinto en cada
corrida. La semilla parecia funcionar y no funcionaba.

No cambiaba ninguna conclusion (0.001 nats), pero rompia la reproducibilidad
bit a bit que 08_REPRODUCIBILITY §8 promete, y es exactamente el detalle que
un jurado tecnico puede preguntar.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from dtdecoder.estimate import _uids_ordenados, cv_lambda, possession_folds
from dtdecoder.grid import StateSpace


SEED = 20260819


def _trans(n_poss: int = 200, seed: int = 3) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    filas = []
    for u in range(n_poss):
        for _ in range(int(rng.integers(2, 8))):
            filas.append({
                "poss_uid": f"m{u // 10}_p{u}",
                "from_state": int(rng.integers(0, 8)),
                "to_state": int(rng.integers(0, 12)),
            })
    return pl.DataFrame(filas)


def _mezclado(df: pl.DataFrame, seed: int) -> pl.DataFrame:
    """Mismo contenido, orden de filas distinto: simula lo que hace unique()."""
    idx = np.random.default_rng(seed).permutation(df.height)
    return df[idx.tolist()]


def test_uids_ordenados_no_depende_del_orden_de_filas():
    df = _trans()
    a = _uids_ordenados(df)
    b = _uids_ordenados(_mezclado(df, 11))
    assert list(a) == list(b)


def test_uids_ordenados_esta_ordenado():
    u = _uids_ordenados(_trans())
    assert list(u) == sorted(u)


def test_folds_son_deterministas_entre_llamadas():
    df = _trans()
    a = [set(f.tolist()) for f in possession_folds(df, 5, SEED)]
    b = [set(f.tolist()) for f in possession_folds(df, 5, SEED)]
    assert a == b


def test_folds_no_dependen_del_orden_de_filas():
    """EL TEST QUE HABRIA ATRAPADO EL BUG."""
    df = _trans()
    a = [set(f.tolist()) for f in possession_folds(df, 5, SEED)]
    b = [set(f.tolist()) for f in possession_folds(_mezclado(df, 23), 5, SEED)]
    assert a == b, (
        "los pliegues cambian con el orden de las filas: la semilla no "
        "esta controlando la particion"
    )


def test_folds_particionan_sin_traslape():
    df = _trans()
    folds = possession_folds(df, 5, SEED)
    todos = [u for f in folds for u in f.tolist()]
    assert len(todos) == len(set(todos)), "una posesion en dos pliegues: fuga"
    assert set(todos) == set(df["poss_uid"].unique().to_list())


def test_semillas_distintas_dan_particiones_distintas():
    df = _trans()
    a = [set(f.tolist()) for f in possession_folds(df, 5, SEED)]
    b = [set(f.tolist()) for f in possession_folds(df, 5, SEED + 1)]
    assert a != b


@pytest.mark.parametrize("orden_seed", [5, 17, 41])
def test_cv_lambda_reproduce_el_mismo_score(orden_seed):
    """De punta a punta: mismos datos en otro orden, mismo lambda* y scores."""
    space = StateSpace(nx=2, ny=2, length=120.0, width=80.0,
                       phases=("open", "transition"))
    df = _trans()
    df = df.with_columns(
        pl.col("from_state") % space.n_transient,
        pl.col("to_state") % space.n_states,
    )
    liga = np.full((space.n_transient, space.n_states), 1.0 / space.n_states)
    grid = [0.0, 10.0, 100.0]

    a = cv_lambda(df, space, liga, grid, k=5, seed=SEED)
    b = cv_lambda(_mezclado(df, orden_seed), space, liga, grid, k=5, seed=SEED)

    assert a.lam_star == b.lam_star
    np.testing.assert_allclose(a.scores, b.scores, rtol=0, atol=1e-12)
