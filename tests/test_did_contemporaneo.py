"""Tests de ADR-53 (scripts/30_did_contemporaneo.py).

Verifican NUMEROS, no ejecucion. El caso central: una liga con deriva de
anotacion entre dos torneos, y dos eras SIN efecto de entrenador. El contraste
crudo tiene que ver una diferencia; el corregido tiene que dar cero.

La cadena de prueba usa un estimador propio (alpha' (I-Q)^-1 1) para no
depender de dtdecoder: lo que se prueba aqui es la logica NUEVA del script
(mezcla por torneo, normalizacion, p e IC basic), no `derivadas`, que ya
cubre la validacion de 08_ic_derivados.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "did_contemporaneo", RAIZ / "scripts" / "30_did_contemporaneo.py")
did = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(did)

NT, NA = 4, 2                      # 4 transitorios, 2 absorbentes
NS = NT + NA


def _cadena(rng, autolazo=0.0):
    """P de NT x NS con absorcion garantizada."""
    P = rng.dirichlet(np.ones(NS), size=NT)
    P[:, NT:] += 0.15                        # que absorba
    P[:, :NT] += autolazo * np.eye(NT)       # deriva o efecto: mas i -> i
    return P / P.sum(axis=1, keepdims=True)


def _e_t(P, alpha):
    Q = P[:, :NT]
    return float(alpha @ np.linalg.solve(np.eye(NT) - Q, np.ones(NT)))


def _conteos(P, visitas):
    """Conteos EXACTOS (sin ruido): visitas_i * P_ij."""
    return visitas[:, None] * P


ALPHA = np.array([0.4, 0.3, 0.2, 0.1])
VIS = np.array([900.0, 700.0, 500.0, 300.0])


@pytest.fixture
def liga():
    rng = np.random.default_rng(7)
    P1 = _cadena(rng)
    # deriva: el torneo 2 anota mas acarreos -> mas autotransiciones
    P2 = P1.copy()
    P2[:, :NT] += 0.25 * np.eye(NT)
    P2 /= P2.sum(axis=1, keepdims=True)
    return {"T1": P1, "T2": P2}


def _D(C_u, alpha, C_base_t, peso):
    base = did.base_ponderada(C_base_t, peso)
    return did.logratio(_e_t(did.normaliza_filas(C_u), alpha),
                        _e_t(did.normaliza_filas(base), alpha))


def test_la_deriva_se_cancela_y_el_crudo_no(liga):
    base = {t: _conteos(P, 20 * VIS) for t, P in liga.items()}
    Ca = _conteos(liga["T1"], VIS)           # era a: torneo 1, sin efecto
    Cb = _conteos(liga["T2"], VIS)           # era b: torneo 2, sin efecto
    crudo = did.logratio(_e_t(did.normaliza_filas(Ca), ALPHA),
                         _e_t(did.normaliza_filas(Cb), ALPHA))
    theta = (_D(Ca, ALPHA, base, {"T1": 1.0})
             - _D(Cb, ALPHA, base, {"T2": 1.0}))
    assert abs(crudo) > 0.05                 # la deriva parece un efecto
    assert abs(theta) < 1e-10                # y la correccion la quita


def test_un_efecto_real_sobrevive_a_la_correccion(liga):
    base = {t: _conteos(P, 20 * VIS) for t, P in liga.items()}
    Pb = liga["T2"].copy()
    Pb[:, :NT] += 0.10 * np.eye(NT)          # el entrenador b SI retiene mas
    Pb /= Pb.sum(axis=1, keepdims=True)
    Ca = _conteos(liga["T1"], VIS)
    Cb = _conteos(Pb, VIS)
    theta = (_D(Ca, ALPHA, base, {"T1": 1.0})
             - _D(Cb, ALPHA, base, {"T2": 1.0}))
    esperado = -np.log(_e_t(Pb, ALPHA) / _e_t(liga["T2"], ALPHA))
    assert theta < 0                         # b sostiene mas que a
    assert theta == pytest.approx(esperado, rel=1e-9)


def test_era_a_caballo_de_dos_torneos(liga):
    """B2: una era en T1 y T2, con la conducta de la liga en cada uno."""
    base = {t: _conteos(P, 20 * VIS) for t, P in liga.items()}
    n1, n2 = 3.0, 1.0
    C_u = (n1 * base["T1"] / base["T1"].sum()
           + n2 * base["T2"] / base["T2"].sum())
    peso = {"T1": n1, "T2": n2}
    assert abs(_D(C_u, ALPHA, base, peso)) < 1e-10


def test_el_volumen_de_un_torneo_no_pesa(liga):
    """Un torneo con el triple de eventos no debe dominar la mezcla."""
    b1 = {"T1": _conteos(liga["T1"], VIS), "T2": _conteos(liga["T2"], VIS)}
    b3 = {"T1": _conteos(liga["T1"], VIS), "T2": _conteos(liga["T2"], 3 * VIS)}
    peso = {"T1": 1.0, "T2": 1.0}
    np.testing.assert_allclose(did.base_ponderada(b1, peso),
                               did.base_ponderada(b3, peso))


def test_torneo_ausente_es_error(liga):
    with pytest.raises(ValueError, match="T9"):
        did.base_ponderada({"T1": _conteos(liga["T1"], VIS)}, {"T9": 1.0})


@pytest.mark.parametrize("nivel", [0.90, 0.95])
def test_p_basic_equivale_a_invertir_el_ic(nivel):
    """p < a  <=>  el IC basic al nivel 1-a excluye el cero."""
    rng = np.random.default_rng(3)
    a = 1 - nivel
    discrepan = 0
    for punto in np.linspace(-0.3, 0.3, 61):
        reps = punto + rng.normal(0, 0.1, size=4000)
        lo, hi = did.ic_basic(reps, punto, nivel)
        excl = lo > 0 or hi < 0
        p = did.p_basic(reps, punto)
        # en la frontera exacta la discretizacion de cuantiles puede diferir
        if abs(p - a) > 3 / 4001:
            discrepan += int((p < a) != excl)
    assert discrepan == 0


def test_p_basic_extremos():
    rng = np.random.default_rng(5)
    assert did.p_basic(rng.normal(0, 0.1, 4000), 0.0) == 1.0
    p = did.p_basic(0.5 + rng.normal(0, 0.05, 4000), 0.5)
    assert p == pytest.approx(2 / 4001)        # piso bilateral
    assert np.isnan(did.p_basic(np.array([np.nan]), 0.1))


def test_equivalencia_y_escala():
    assert did.equivalente((-0.029, 0.029), 0.03)
    assert not did.equivalente((-0.0407, 0.0398), 0.03)    # Berizzo-Larcamon, 08
    assert did.a_rel(np.log(1.1)) == pytest.approx(0.1)


def test_semilla_estable_y_por_unidad():
    a1 = did.semilla(11235, "América", "Andre Jardine").integers(0, 10**9, 5)
    a2 = did.semilla(11235, "América", "Andre Jardine").integers(0, 10**9, 5)
    b = did.semilla(11235, "Atlético San Luis", "Andre Jardine").integers(0, 10**9, 5)
    assert (a1 == a2).all()
    assert not (a1 == b).all()                 # mismo DT, otro club: otra semilla


def test_pesos_por_torneo_cuentan_transiciones():
    lens = np.array([3, 5, 2, 4])
    tor = np.array([0, 1, 1, 0])
    w = did.pesos_por_torneo(lens, tor, np.array([0, 1, 1, 3]), 2)
    np.testing.assert_allclose(w, [3 + 4, 5 + 5])
