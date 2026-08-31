"""Test de integracion + recuperacion de parametros."""
import numpy as np
import polars as pl

from dtdecoder.config import Config
from dtdecoder.estimate import count_matrix, cv_lambda, shrink
from dtdecoder.grid import StateSpace
from dtdecoder.inference import context_contrast, tactical_fingerprint
from dtdecoder.possessions import build_transitions, coordinate_sanity
from dtdecoder.synth import synth_events


def _setup(n_matches=50, dt_bias=0.35, seed=5):
    cfg = Config.load()
    space = StateSpace(nx=cfg["pitch"]["nx"], ny=cfg["pitch"]["ny"])
    ev = synth_events(n_matches=n_matches, dt_bias=dt_bias, seed=seed).lazy()
    from dtdecoder.ingest import normalize
    trans = build_transitions(normalize(ev), space, cfg.raw)
    return cfg, space, trans


def test_transitions_are_wellformed():
    _, space, trans = _setup()
    assert trans.height > 1000
    assert trans["from_state"].max() < space.n_transient
    assert trans["to_state"].max() < space.n_states
    # toda posesion termina absorbida
    last = trans.sort(["poss_uid", "event_index"]).group_by("poss_uid").last()
    assert last["is_absorbing"].all()


def test_rows_sum_to_one_and_chain_absorbs():
    cfg, space, trans = _setup()
    from dtdecoder.absorbing import AbsorbingChain
    Q = np.full((space.n_transient, space.n_states), 1 / space.n_states)
    P = shrink(count_matrix(trans, space), Q, 5.0)
    assert np.allclose(P.sum(axis=1), 1.0)
    assert AbsorbingChain(P=P, space=space).check()["rho_ok"]


def test_coordinate_sanity_detects_orientation():
    _, space, trans = _setup()
    assert coordinate_sanity(trans, space)["corr"] > 0.0


def test_cv_picks_finite_lambda():
    cfg, space, trans = _setup()
    dt = trans.filter(pl.col("team") == "Club A")
    Q = np.full((space.n_transient, space.n_states), 1 / space.n_states)
    league = shrink(count_matrix(trans, space), Q, 1.0)
    cv = cv_lambda(dt, space, league, cfg["estimation"]["lambda_grid"], k=3, seed=1)
    assert np.isfinite(cv.scores).all()
    assert cv.lam_star in cfg["estimation"]["lambda_grid"]


def test_fingerprint_recovers_injected_bias():
    """El DT sintetico tiene sesgo real -> debe haber rechazos.
    Un equipo sin sesgo -> practicamente ninguno."""
    cfg, space, trans = _setup(n_matches=60, dt_bias=0.6, seed=9)
    Q = np.full((space.n_transient, space.n_states), 1 / space.n_states)
    league_P = shrink(count_matrix(trans, space), Q, 1.0)

    dt = trans.filter(pl.col("team") == "Club A")
    rest = trans.filter(pl.col("team") != "Club A")
    fp = tactical_fingerprint(dt, rest, space, league_P, n_boot=200, seed=2)
    assert fp.rejected.sum() >= 1, "no detecto el sesgo inyectado"

    placebo = trans.filter(pl.col("team") == "Club C")
    others = trans.filter(pl.col("team") != "Club C")
    fp0 = tactical_fingerprint(placebo, others, space, league_P, n_boot=200, seed=2)
    assert fp0.rejected.sum() <= fp.rejected.sum()


def test_context_contrast_runs():
    cfg, space, trans = _setup()
    Q = np.full((space.n_transient, space.n_states), 1 / space.n_states)
    league = shrink(count_matrix(trans, space), Q, 1.0)
    out = context_contrast(trans.filter(pl.col("team") == "Club A"), space, league, 20.0)
    assert out.height >= 1
    assert (out["tv_weighted"] >= 0).all()
