"""Tests de ADR-56/57 (scripts/36_contexto.py)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("contexto", RAIZ / "scripts" / "36_contexto.py")
cx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cx)

N_T = 2
NK = len(cx.CONTEXTOS) * 3 * N_T


def _T(filas):
    """filas: [(k, j, t, vals7)] -> (7, NK)."""
    vals = np.array([f[3] for f in filas], float)
    key = np.array([(f[0] * 3 + f[1]) * N_T + f[2] for f in filas])
    return cx.totales(vals, key, np.ones(len(filas)), NK)


def test_perspectiva_y_niveles():
    assert cx.invierte_marcador("winning") == "losing"
    assert cx.invierte_marcador("drawing") == "drawing"
    assert cx.nivel_marcador("losing") == 0 and cx.nivel_marcador("winning") == 1
    assert cx.nivel_marcador("drawing") == 2 and cx.nivel_marcador(None) == 2
    assert cx.nivel_momento(60) == 0 and cx.nivel_momento(59) == 1
    assert cx.nivel_momento(None) == 2 and cx.nivel_momento(float("nan")) == 2


def test_rival_sin_el_partido_propio():
    xgd = {1: 3.0, 2: 0.0, 3: 0.0}
    assert cx.media_sin(xgd, 1) == 0.0          # su goleada no lo clasifica
    assert cx.media_sin(xgd, 2) == 1.5
    corte = cx.tercios({"a": -1.0, "b": 0.0, "c": 1.0, "d": 2.0})
    assert cx.nivel_rival(2.0, corte) == 0
    assert cx.nivel_rival(-1.0, corte) == 1
    assert cx.nivel_rival(float("nan"), corte) == 2


def test_si_la_unidad_ajusta_como_la_liga_theta_es_cero():
    # liga: M1 perdiendo - ganando = 2 en los dos torneos (con deriva +1 en T2)
    liga = [(1, 0, 0, [100, 600, 0, 0, 0, 0, 0]), (1, 1, 0, [100, 400, 0, 0, 0, 0, 0]),
            (1, 0, 1, [100, 700, 0, 0, 0, 0, 0]), (1, 1, 1, [100, 500, 0, 0, 0, 0, 0])]
    unidad = [(1, 0, 1, [10, 70, 0, 0, 0, 0, 0]), (1, 1, 1, [30, 150, 0, 0, 0, 0, 0])]
    au, ab, th = cx.ajuste(_T(unidad), _T(liga), 1, "M1", N_T)
    assert au == pytest.approx(2.0) and ab == pytest.approx(2.0)
    assert th == pytest.approx(0.0, abs=1e-12)


def test_la_mezcla_de_torneos_se_estandariza_por_nivel():
    # la unidad pierde en T1 y gana en T2; la liga no ajusta, pero T2 esta inflado
    liga = [(1, 0, 0, [100, 400, 0, 0, 0, 0, 0]), (1, 1, 0, [100, 400, 0, 0, 0, 0, 0]),
            (1, 0, 1, [100, 600, 0, 0, 0, 0, 0]), (1, 1, 1, [100, 600, 0, 0, 0, 0, 0])]
    unidad = [(1, 0, 0, [10, 40, 0, 0, 0, 0, 0]), (1, 1, 1, [10, 60, 0, 0, 0, 0, 0])]
    au, ab, th = cx.ajuste(_T(unidad), _T(liga), 1, "M1", N_T)
    assert au == pytest.approx(-2.0)            # crudo: "acorta cuando pierde"
    assert th == pytest.approx(0.0, abs=1e-12)  # es la deriva, no el entrenador


def test_un_ajuste_real_sobrevive_y_M3_usa_acciones():
    liga = [(0, 0, 0, [0, 0, 0, 1000, 200, 0, 0]), (0, 1, 0, [0, 0, 0, 1000, 200, 0, 0])]
    unidad = [(0, 0, 0, [0, 0, 0, 100, 30, 0, 0]), (0, 1, 0, [0, 0, 0, 100, 20, 0, 0])]
    _, _, th = cx.ajuste(_T(unidad), _T(liga), 0, "M3", N_T)
    assert th == pytest.approx(0.10)


def test_vectorizado_igual_al_escalar():
    rng = np.random.default_rng(0)
    TU = rng.integers(0, 50, size=(30, 7, NK)).astype(float)
    TB = rng.integers(0, 500, size=(30, 7, NK)).astype(float)
    TB[3, :, :N_T] = 0                           # una replica con base vacia
    TU[5, :, :] = 0                              # una replica sin datos de la unidad
    for k in range(len(cx.CONTEXTOS)):
        for mt in cx.METRICAS:
            au, ab, th = cx.ajuste_vec(TU, TB, k, mt, N_T)
            for r in range(30):
                e = cx.ajuste(TU[r], TB[r], k, mt, N_T)
                np.testing.assert_allclose([au[r], ab[r], th[r]], e, equal_nan=True, atol=1e-12)


def test_casos_desde():
    u = [("América", "Jardine"), ("Atlético San Luis", "Jardine"), ("América", "Solari"),
         ("León", "Holan"), ("Puebla", "Larcamon"), ("León", "Larcamon")]
    c = cx.casos_desde(u)
    assert set(c) == {"Jardine", "Solari", "Larcamon"}
    assert c["Larcamon"] == {"Puebla", "León"}
