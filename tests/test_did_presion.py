"""Tests de ADR-54 (scripts/33_did_presion.py): verifican numeros.

Caso central: una liga cuya tasa de presion SALTA entre dos torneos, y dos
eras sin efecto de entrenador. El crudo ve una diferencia; el DiD da cero.
Las tablas se construyen con conteos EXACTOS (sin ruido) para que el cero sea
exacto; el bootstrap se prueba aparte.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("did_presion", RAIZ / "scripts" / "33_did_presion.py")
dp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dp)

NZ = 4
S = dp.N_SUB


def _tablas(pi: np.ndarray, n: np.ndarray):
    """N, Y de UN partido con pi[z] y n[z] en todos los subconjuntos."""
    N = np.broadcast_to(n, (S, NZ)).astype(float).copy()
    return N[None], (N * pi)[None]


def _base(pis_por_torneo, n=np.array([400.0, 400, 400, 400])):
    Ns, Ys, tor = [], [], []
    for t, pi in enumerate(pis_por_torneo):
        N, Y = _tablas(pi, n)
        Ns.append(N); Ys.append(Y); tor.append(t)
    return np.concatenate(Ns), np.concatenate(Ys), np.array(tor)


def _D(Nm, Ym, tor, rate, i):
    Nu, Yu = dp.agrega(Nm, Ym, tor, np.ones(len(tor)), 2)
    pi, ba, n = dp.resumen_unidad(Nu, Yu, rate, NZ)
    return pi[i] - ba[i], pi[i]


PI1 = np.array([0.30, 0.20, 0.20, 0.15])
PI2 = PI1 + 0.03                           # la anotacion sube 3 pp en T2


@pytest.fixture
def rate():
    N, Y, tor = _base([PI1, PI2])
    Nt, Yt = dp.agrega(N, Y, tor, np.ones(2), 2)
    r, ralas = dp.tasa_base(Nt, Yt, 30)
    assert ralas == 0
    return r


@pytest.mark.parametrize("i", [0, 3, NZ + dp.S_K3 - 1, NZ + dp.S_L1A - 1])
def test_el_salto_se_cancela_y_el_crudo_no(rate, i):
    n = np.array([100.0, 50, 50, 30])
    Na, Ya = _tablas(PI1, n)
    Nb, Yb = _tablas(PI2, n)
    Da, pa = _D(Na, Ya, np.array([0]), rate, i)
    Db, pb = _D(Nb, Yb, np.array([1]), rate, i)
    assert abs(pa - pb) == pytest.approx(0.03)          # el crudo ve la deriva
    assert Da - Db == pytest.approx(0.0, abs=1e-12)     # el DiD no


def test_la_mezcla_de_zonas_no_se_confunde_con_presion(rate):
    """Un rival que juega mas en la zona de pi alto no es mas presion."""
    Na, Ya = _tablas(PI1, np.array([300.0, 10, 10, 10]))
    Nb, Yb = _tablas(PI1, np.array([10.0, 10, 10, 300]))
    i = NZ + dp.S_K3 - 1
    Da, pa = _D(Na, Ya, np.array([0]), rate, i)
    Db, pb = _D(Nb, Yb, np.array([0]), rate, i)
    assert pa - pb > 0.1                               # crudo: gran "diferencia"
    assert Da - Db == pytest.approx(0.0, abs=1e-12)


def test_un_efecto_zonal_real_sobrevive(rate):
    n = np.array([100.0, 100, 100, 100])
    Na, Ya = _tablas(PI1, n)
    efecto = PI2.copy(); efecto[2] += 0.04
    Nb, Yb = _tablas(efecto, n)
    dz = []
    for z in range(NZ):
        Da, _ = _D(Na, Ya, np.array([0]), rate, z)
        Db, _ = _D(Nb, Yb, np.array([1]), rate, z)
        dz.append(Da - Db)
    np.testing.assert_allclose(dz, [0, 0, -0.04, 0], atol=1e-12)


def test_era_a_caballo_de_dos_torneos(rate):
    Na1, Ya1 = _tablas(PI1, np.array([60.0, 60, 60, 60]))
    Na2, Ya2 = _tablas(PI2, np.array([20.0, 20, 20, 20]))
    N = np.concatenate([Na1, Na2]); Y = np.concatenate([Ya1, Ya2])
    D, _ = _D(N, Y, np.array([0, 1]), rate, NZ + dp.S_K3 - 1)
    assert D == pytest.approx(0.0, abs=1e-12)


def test_tasa_base_rala_usa_el_torneo():
    Nt = np.zeros((1, S, NZ)); Yt = np.zeros_like(Nt)
    Nt[0, :, 0], Yt[0, :, 0] = 100, 30
    Nt[0, :, 1], Yt[0, :, 1] = 10, 9          # rala: 0.9 no se usa
    r, ralas = dp.tasa_base(Nt, Yt, 30)
    assert r[0, 0, 0] == pytest.approx(0.30)
    assert r[0, 0, 1] == pytest.approx(39 / 110)
    assert ralas == S * 3                      # zona 1 y las dos vacias


def test_tabla_por_partido_cuenta_bien():
    k = np.array([1, 3, 3, 2]); L = np.array([1, 4, 4, 4])
    fase = np.array(["open", "open", "set_piece", "restart"])
    ms = dp.mascaras(k, L, fase)
    N, Y = dp.tabla_por_partido(np.array([0, 0, 1, 1]), np.array([0, 1, 1, 2]),
                                np.array([1, 0, 1, 1]), ms, 2, 3)
    assert N[:, dp.S_TODAS].sum() == 4 and Y[:, dp.S_TODAS].sum() == 3
    assert N[0, dp.S_L1A, 0] == 1 and N[:, dp.S_L1P].sum() == 0
    assert N[:, dp.S_K3].sum() == 2 and Y[1, dp.S_K3, 1] == 1
    assert N[1, dp.S_K0 + 0, 2] == 1          # k = 2


def test_pendiente_es_la_de_19():
    y = 0.30 - 0.01 * np.asarray(dp.KS, dtype=float)
    n = np.full(len(dp.KS), 300.0)
    v = np.ones(len(dp.KS), dtype=bool)
    assert dp.pendiente_pond(y, n, v) == pytest.approx(-0.01)
    v[:9] = False
    assert np.isnan(dp.pendiente_pond(y, n, v))   # menos de 3 puntos


def test_omnibus_calibrado_y_con_potencia():
    rng = np.random.default_rng(1)
    se = np.array([0.01, 0.02, 0.015])
    test = np.ones(3, dtype=bool)
    ps = []
    for _ in range(200):                       # bajo la nula
        d = rng.normal(0, se)
        R = d + rng.normal(0, se, size=(500, 3))
        ps.append(dp.omnibus(d, R, test)[1])
    assert 0.02 < np.mean(np.array(ps) < 0.05) < 0.10
    d = np.array([0.05, 0.0, 0.0])             # efecto de 5 se en una zona
    R = d + rng.normal(0, se, size=(2000, 3))
    assert dp.omnibus(d, R, test)[1] < 0.01


def test_omnibus_ignora_zonas_no_testables():
    d = np.array([0.5, 0.0]); R = np.random.default_rng(0).normal(0, .01, (100, 2))
    T, p, n = dp.omnibus(d, R, np.array([False, True]))
    assert n == 1 and T < 1


def test_partidos_completos_detecta_el_lado_faltante():
    mid = np.array([1, 1, 2, 3, 3, 3])
    ata = np.array(["A", "B", "A", "C", "D", "C"])
    dfn = np.array(["B", "A", "B", "D", "C", "D"])
    comp, inc = dp.partidos_completos(mid, ata, dfn)
    assert comp == {1, 3} and inc == {2}


def test_partidos_completos_rechaza_un_equipo_contra_si_mismo():
    comp, inc = dp.partidos_completos(np.array([1, 1]), np.array(["A", "A"]),
                                      np.array(["B", "C"]))
    assert comp == set() and inc == {1}
