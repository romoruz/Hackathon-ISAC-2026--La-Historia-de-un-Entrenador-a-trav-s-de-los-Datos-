import numpy as np
from dtdecoder.grid import StateSpace


def test_zone_partition_covers_pitch():
    s = StateSpace(nx=5, ny=4)
    x = np.random.default_rng(0).uniform(0, 120, 5000)
    y = np.random.default_rng(1).uniform(0, 80, 5000)
    z = s.zone_of(x, y)
    assert z.min() >= 0 and z.max() < s.n_zones


def test_boundaries_clipped():
    s = StateSpace(nx=5, ny=4)
    z = s.zone_of(np.array([120.5, -1.0]), np.array([80.2, -0.3]))
    assert z[0] == s.n_zones - 1 and z[1] == 0


def test_index_roundtrip():
    s = StateSpace(nx=5, ny=4)
    idx = s.transient_index(np.arange(s.n_zones), np.zeros(s.n_zones, dtype=int))
    assert len(set(idx.tolist())) == s.n_zones
    assert s.absorbing_index("GOAL") >= s.n_transient
    assert len(s.state_labels()) == s.n_states
