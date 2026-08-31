"""Regresion: el prior no debe contener a la unidad focal."""

import numpy as np
import polars as pl

from dtdecoder.config import Config
from dtdecoder.estimate import count_matrix, cv_lambda, shrink
from dtdecoder.grid import StateSpace
from dtdecoder.ingest import normalize
from dtdecoder.possessions import build_transitions
from dtdecoder.synth import synth_events


def _setup(seed=17, n_matches=70):
    cfg = Config.load()
    space = StateSpace(nx=cfg["pitch"]["nx"], ny=cfg["pitch"]["ny"],
                       phases=tuple(cfg["phase_order"]))
    trans = build_transitions(normalize(synth_events(n_matches=n_matches, seed=seed).lazy()),
                              space, cfg.raw)
    return cfg, space, trans


def _uniform(space):
    return np.full((space.n_transient, space.n_states), 1.0 / space.n_states)


def test_dominant_unit_inflates_lambda_when_prior_leaks():
    """Si el foco domina el archivo, el prior contaminado dispara lambda*.

    Reproduce el sintoma observado con datos reales: un club que es >50% del
    archivo hace que la CV elija el tope de la rejilla, porque el prior predice
    bien los datos retenidos... por ser suyos.
    """
    cfg, space, trans = _setup()
    focus = trans.filter(pl.col("team") == "Club A")
    rest = trans.filter(pl.col("team") != "Club A")

    # fuerza dominancia: el foco replicado pesa mucho mas que el resto
    heavy = pl.concat([focus] * 6 + [rest.head(focus.height // 6)])

    grid = cfg["estimation"]["lambda_grid"]
    prior_leak = shrink(count_matrix(heavy, space), _uniform(space), 1.0)
    prior_clean = shrink(count_matrix(rest, space), _uniform(space), 1.0)

    cv_leak = cv_lambda(focus, space, prior_leak, grid, k=3, seed=1)
    cv_clean = cv_lambda(focus, space, prior_clean, grid, k=3, seed=1)

    assert cv_leak.lam_star >= cv_clean.lam_star, (
        f"prior contaminado deberia pedir MAS encogimiento: "
        f"{cv_leak.lam_star} vs {cv_clean.lam_star}"
    )


def test_clean_prior_keeps_lambda_off_the_ceiling():
    cfg, space, trans = _setup()
    focus = trans.filter(pl.col("team") == "Club A")
    rest = trans.filter(pl.col("team") != "Club A")
    prior = shrink(count_matrix(rest, space), _uniform(space), 1.0)
    grid = cfg["estimation"]["lambda_grid"]
    cv = cv_lambda(focus, space, prior, grid, k=3, seed=1)
    assert cv.lam_star < max(grid), "lambda* pegado al techo con prior limpio"


def test_neutral_prior_excludes_both_compared_units():
    cfg, space, trans = _setup()
    a, b = "Club A", "Club B"
    neutral = trans.filter(
        (pl.col("team") != a) & (pl.col("team") != b) | pl.col("team").is_null()
    )
    assert neutral.height > 0
    assert a not in set(neutral["team"].unique())
    assert b not in set(neutral["team"].unique())


def test_lambda_grid_spans_enough_range():
    grid = Config.load()["estimation"]["lambda_grid"]
    assert min(grid) == 0.0
    assert max(grid) >= 1000.0, "la rejilla debe permitir detectar el tope"
