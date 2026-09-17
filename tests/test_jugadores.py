"""Tests de ADR-58 (scripts/38_jugadores.py): numeros, no ejecucion."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("jugadores", RAIZ / "scripts" / "38_jugadores.py")
jg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jg)

FIN = {1: 47 * 60.0, 2: 50 * 60.0}       # 1T de 47 min, 2T de 50 min (relativos)


def test_seg():
    assert jg.seg("00:01:02.500") == pytest.approx(62.5)
    assert jg.seg("70:30") == pytest.approx(4230.0)


def test_detecta_reloj():
    assert jg.detecta_reloj([(2, 60 * 60.0), (2, 70 * 60.0)]) == "acumulado"
    assert jg.detecta_reloj([(2, 15 * 60.0), (2, 25 * 60.0)]) == "periodo"
    assert jg.detecta_reloj([]) == "desconocido"


def test_minutos_titular_completo_y_suplente_relativo():
    titular = [{"from": "00:00:00.000", "to": None, "from_period": 1, "to_period": None}]
    assert jg.minutos_jugados(titular, FIN, "periodo") == pytest.approx(97.0)
    sup = [{"from": "00:20:00.000", "to": None, "from_period": 2, "to_period": None}]
    assert jg.minutos_jugados(sup, FIN, "periodo") == pytest.approx(30.0)
    sale = [{"from": "00:00:00.000", "to": "00:20:00.000", "from_period": 1, "to_period": 2}]
    assert jg.minutos_jugados(sale, FIN, "periodo") == pytest.approx(47 + 20)


def test_minutos_reloj_acumulado():
    sup = [{"from": "01:05:00.000", "to": None, "from_period": 2, "to_period": None}]
    # fin acumulado = 45 + 50 = 95 min
    assert jg.minutos_jugados(sup, FIN, "acumulado") == pytest.approx(30.0)


def test_n80_y_continuidad():
    assert jg.n80([90] * 10 + [0] * 5) == 8
    assert jg.n80([500, 100, 100, 100]) == 3
    assert jg.continuidad([{1, 2, 3}, {1, 2, 4}, {1, 2, 4}]) == pytest.approx((2 / 3 + 1) / 2)
    assert np.isnan(jg.continuidad([{1}]))


def test_percentil():
    assert jg.percentil(5, [1, 2, 3, 4]) == 1.0
    assert jg.percentil(2, [1, 2, 3, 4]) == pytest.approx(0.375)


def test_ventanas_con_exclusion_y_recorte():
    antes, despues = jg.ventanas(700.0)
    assert antes == (40.0, 640.0) and despues == (760.0, 1360.0)
    antes, _ = jg.ventanas(600.0)
    assert antes[0] == 0.0                       # recorte al inicio del periodo
    t = np.array([630.0, 650.0, 700.0, 770.0])
    num = np.array([1.0, 5.0, 5.0, 2.0])
    assert jg.tasa_ventana(t, num, np.ones(4), 40.0, 640.0, True) == 1.0   # 650 excluido
    assert jg.tasa_ventana(t, num, np.ones(4), 760.0, 1360.0, False) == 2.0
    assert np.isnan(jg.tasa_ventana(t, num, np.ones(4), 2000.0, 2600.0, True))


def test_bloques_y_marcador():
    assert [jg.bloque(x) for x in (600, 1079, 1080, 1559, 1560, 2100)] == [0, 0, 1, 1, 2, 2]
    assert jg.marcador_idx("losing") == 0 and jg.marcador_idx(None) is None


def test_theta_cancela_la_mezcla_de_estratos():
    # la liga: Delta = +0.10 perdiendo (estrato 0) y -0.02 ganando (estrato 1)
    Db = np.array([0.10, 0.10, -0.02, -0.02])
    sb = np.array([0, 0, 1, 1])
    # la era solo cambia perdiendo y hace lo mismo que la liga
    De = np.array([0.10, 0.10, 0.10])
    se = np.array([0, 0, 0])
    me, mb, th, desc = jg.theta_estratificado(De, np.ones(3), se, Db, np.ones(4), sb, 2)
    assert me == pytest.approx(0.10) and mb == pytest.approx(0.10)
    assert th == pytest.approx(0.0) and desc == 0.0
    # sin estratificar, la comparacion cruda habria dado +0.06
    assert me - Db.mean() == pytest.approx(0.06)


def test_theta_descarta_estratos_sin_liga_y_ignora_nan():
    Db = np.array([0.05, np.nan])
    sb = np.array([0, 1])
    De = np.array([0.15, 0.30, np.nan])
    se = np.array([0, 1, 0])
    me, mb, th, desc = jg.theta_estratificado(De, np.ones(3), se, Db, np.ones(2), sb, 2)
    assert me == pytest.approx(0.225)
    assert mb == pytest.approx(0.05) and desc == pytest.approx(0.5)
