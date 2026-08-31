import numpy as np
from dtdecoder.estimate import mle, shrink
from dtdecoder.inference import benjamini_hochberg, g2_rows


def test_shrink_is_stochastic():
    rng = np.random.default_rng(0)
    C = rng.poisson(3, size=(20, 24)).astype(float)
    Q = np.full((20, 24), 1 / 24)
    for lam in (0.0, 1.0, 50.0, 1e4):
        assert np.allclose(shrink(C, Q, lam).sum(axis=1), 1.0)


def test_shrink_limits():
    C = np.zeros((3, 4))
    C[0] = [10, 0, 0, 0]
    Q = np.full((3, 4), 0.25)
    assert np.allclose(shrink(C, Q, 0.0)[0], mle(C)[0])
    assert np.allclose(shrink(C, Q, 1e9)[0], Q[0], atol=1e-5)
    assert np.allclose(shrink(C, Q, 0.0)[1], Q[1])


def test_g2_zero_under_equality():
    Q = np.full((5, 6), 1 / 6)
    assert np.allclose(g2_rows(Q * 600, Q), 0.0, atol=1e-8)


def test_bh_conservative_under_null():
    p = np.array([0.001, 0.01, 0.2, 0.5, 0.9])
    q, rej = benjamini_hochberg(p, 0.05)
    assert rej[0] and not rej[-1]
    assert np.all((q >= 0) & (q <= 1))
    rng = np.random.default_rng(3)
    _, rej2 = benjamini_hochberg(rng.uniform(size=500), 0.05)
    assert rej2.sum() <= 5


def test_diff_ci_contains_point_estimate():
    """Regresion: el IC debe contener su propio estimador puntual."""
    import polars as pl
    from dtdecoder.config import Config
    from dtdecoder.grid import StateSpace
    from dtdecoder.inference import bootstrap_diff
    from dtdecoder.ingest import normalize
    from dtdecoder.possessions import build_transitions
    from dtdecoder.synth import synth_events

    cfg = Config.load()
    space = StateSpace(nx=cfg["pitch"]["nx"], ny=cfg["pitch"]["ny"])
    trans = build_transitions(normalize(synth_events(n_matches=40, seed=4).lazy()),
                              space, cfg.raw)
    prior = shrink(
        __import__("dtdecoder.estimate", fromlist=["count_matrix"]).count_matrix(trans, space),
        np.full((space.n_transient, space.n_states), 1 / space.n_states), 1.0)
    a = trans.filter(pl.col("team") == "Club A")
    b = trans.filter(pl.col("team") != "Club A")
    for method in ("basic", "percentile"):
        ci = bootstrap_diff(a, b, space, prior, 50.0, n_boot=150, seed=1, method=method)
        assert (ci.lo <= ci.diff + 1e-9).all() and (ci.diff <= ci.hi + 1e-9).all(), method
