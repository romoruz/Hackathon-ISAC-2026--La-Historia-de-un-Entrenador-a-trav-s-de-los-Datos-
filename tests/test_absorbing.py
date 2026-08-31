import numpy as np
from dtdecoder.absorbing import AbsorbingChain
from dtdecoder.grid import StateSpace


def _toy_chain(seed=0):
    s = StateSpace(nx=2, ny=2)
    rng = np.random.default_rng(seed)
    P = rng.random((s.n_transient, s.n_states)) + 0.05
    P[:, s.n_transient:] *= 2.0
    P /= P.sum(axis=1, keepdims=True)
    return AbsorbingChain(P=P, space=s)


def test_neumann_series_matches_solve():
    ch = _toy_chain()
    N, Q = ch.fundamental(), ch.Q
    acc = np.eye(Q.shape[0])
    term = np.eye(Q.shape[0])
    for _ in range(400):
        term = term @ Q
        acc = acc + term
    assert np.allclose(N, acc, atol=1e-6)


def test_absorption_rows_sum_to_one():
    assert np.allclose(_toy_chain(1).absorption().sum(axis=1), 1.0, atol=1e-8)


def test_spectral_radius_below_one():
    assert _toy_chain(2).check()["rho_ok"]


def test_expected_length_consistency():
    ch = _toy_chain(3)
    assert np.allclose(ch.expected_length(), ch.fundamental().sum(axis=1), atol=1e-8)
