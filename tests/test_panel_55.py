"""Tests de D59-P (scripts/40_panel_55.py): numeros, no ejecucion."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("panel55", RAIZ / "scripts" / "40_panel_55.py")
pn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pn)


def test_constantes_preinscritas():
    assert pn.ARCO == (120.0, 40.0)
    assert pn.X_PROPIO_40 == pytest.approx(0.4 * 120)
    assert pn.FRAC_PROG == 0.75
    assert pn.X_TERCIO == 80.0                    # D58-C
    assert pn.UMBRAL_FIJO == (30.0, 15.0, 10.0)
    assert set(pn.PASE_BALON_PARADO) == {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}


def test_dist_arco():
    assert pn.dist_arco(120, 40) == 0.0
    assert pn.dist_arco(90, 0) == pytest.approx(50.0)     # 30-40-50


def test_progresivo_relativo_casos_frontera():
    # d0 = 60 desde (60, 40); 25% exacto -> d1 = 45 -> x1 = 75: cuenta
    assert pn.progresivo_relativo(60, 40, 75, 40)
    assert not pn.progresivo_relativo(60, 40, 74.9, 40)
    # empieza dentro del 40% propio: nunca cuenta, aunque avance mucho
    assert not pn.progresivo_relativo(47.9, 40, 110, 40)
    assert pn.progresivo_relativo(48.0, 40, 110, 40)
    # hacia atras no cuenta
    assert not pn.progresivo_relativo(90, 40, 70, 40)
    # un pase lateral por la banda que no acerca al arco no cuenta
    assert not pn.progresivo_relativo(70, 0, 70, 80)


def test_progresivo_relativo_vectorizado():
    x0 = np.array([60.0, 47.0, 90.0])
    r = pn.progresivo_relativo(x0, [40, 40, 40], [80, 100, 70], [40, 40, 40])
    assert r.tolist() == [True, False, False]


def test_progresivo_fijo_por_mitades():
    # propio -> propio: hace falta ganar 30
    assert pn.progresivo_fijo(10, 40, 40, 40)          # gana 30
    assert not pn.progresivo_fijo(10, 40, 39, 40)      # gana 29
    # propio -> rival: 15
    assert pn.progresivo_fijo(50, 40, 65, 40)
    assert not pn.progresivo_fijo(50, 40, 64, 40)
    # rival -> rival: 10
    assert pn.progresivo_fijo(70, 40, 80, 40)
    assert not pn.progresivo_fijo(70, 40, 79, 40)
    # rival -> propio: nunca
    assert not pn.progresivo_fijo(61, 40, 59, 40)


def test_field_tilt():
    assert pn.field_tilt(30, 10) == 0.75
    assert np.isnan(pn.field_tilt(0, 0))


def test_perfil_es_simetrico_y_cuenta_faltantes_como_cero():
    por_eq = {"A": {"npxg": 1.5, "xg": 2.3, "obv": 0.4, "prog": 20, "prog_fijo": 25,
                    "pases_juego": 400, "ft": 60},
              "B": {"npxg": 0.5, "xg": 0.5, "obv": -0.1, "ft": 20}}
    p = pn.perfil_equipo_partido(por_eq, "A", "B")
    assert p["A"]["npxg_favor"] == p["B"]["npxg_contra"] == 1.5
    assert p["A"]["xg_contra_con_penales"] == 0.5
    assert p["B"]["obv_contra"] == 0.4
    assert p["A"]["field_tilt"] + p["B"]["field_tilt"] == pytest.approx(1.0)
    assert p["A"]["prog_fraccion"] == pytest.approx(0.05)
    assert p["B"]["prog_pases"] == 0.0 and np.isnan(p["B"]["prog_fraccion"])


def test_comparacion_estandariza_por_torneo():
    # la liga vale 1.0 en el torneo 0 y 3.0 en el 1; la era juega 3 partidos en
    # el torneo 0 y 1 en el 1, con los mismos valores que la liga.
    Vb = np.array([[1.0], [1.0], [3.0], [3.0]])
    tb = np.array([0, 0, 1, 1])
    Vu = np.array([[1.0], [1.0], [1.0], [3.0]])
    tu = np.array([0, 0, 0, 1])
    era, base = pn.comparacion(Vu, tu, np.ones((1, 4)), Vb, tb, np.ones((1, 4)), 2)
    assert era[0, 0] == pytest.approx(1.5)
    assert base[0, 0] == pytest.approx(0.75 * 1.0 + 0.25 * 3.0)
    # sin estandarizar, la liga cruda (2.0) habria dado una diferencia de -0.5
    assert era[0, 0] - base[0, 0] == pytest.approx(0.0)
    assert era[0, 0] - Vb.mean() == pytest.approx(-0.5)


def test_comparacion_ignora_nulos_y_anula_sin_liga():
    Vu = np.array([[np.nan, 1.0], [2.0, 1.0]])
    tu = np.array([0, 1])
    Vb = np.array([[5.0, 1.0], [7.0, np.nan]])
    tb = np.array([1, 1])                        # la liga no tiene torneo 0
    era, base = pn.comparacion(Vu, tu, np.ones((1, 2)), Vb, tb, np.ones((1, 2)), 2)
    # metrica 0: la era solo es valida en el torneo 1 -> base = 6.0
    assert era[0, 0] == pytest.approx(2.0) and base[0, 0] == pytest.approx(6.0)
    # metrica 1: la era pesa en el torneo 0, donde la liga no existe -> nulo
    assert era[0, 1] == pytest.approx(1.0) and np.isnan(base[0, 1])


def test_comparacion_respeta_los_pesos_del_bootstrap():
    Vu = np.array([[1.0], [3.0]])
    tu = np.array([0, 0])
    W = np.array([[1.0, 1.0], [2.0, 0.0], [0.0, 2.0]])
    Vb = np.array([[0.0]])
    tb = np.array([0])
    era, base = pn.comparacion(Vu, tu, W, Vb, tb, np.ones((3, 1)), 1)
    assert era[:, 0].tolist() == pytest.approx([2.0, 1.0, 3.0])
    assert base[:, 0].tolist() == pytest.approx([0.0, 0.0, 0.0])
