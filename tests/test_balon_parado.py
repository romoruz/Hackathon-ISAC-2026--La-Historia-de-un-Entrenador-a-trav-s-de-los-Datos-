"""Tests de ADR-55 (scripts/35_balon_parado.py): numeros, no ejecucion."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("balon_parado", RAIZ / "scripts" / "35_balon_parado.py")
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)


def _p(n, per, pat, eq, ini=None, tiros=()):
    return {"possession": n, "period": per, "patron": pat, "equipo": eq,
            "inicia": ini, "tiros": list(tiros)}


CORNER = {"pass_type": "Corner", "x": 120.0}


def test_secuencia_con_segunda_jugada_y_gol():
    poss = [_p(1, 1, "From Corner", "A", CORNER),
            _p(2, 1, "From Corner", "B"),                       # despeje del rival
            _p(3, 1, "From Corner", "A", tiros=[("A", True)]),  # segunda jugada
            _p(4, 1, "Regular Play", "B")]
    s = bp.construye_secuencias(poss, "Corner", "From Corner", None)
    assert len(s) == 1
    assert s[0]["posesiones"] == [1, 2, 3] and s[0]["S"] == 1 and s[0]["G"] == 1


def test_un_nuevo_cobro_abre_otra_secuencia():
    poss = [_p(1, 1, "From Corner", "A", CORNER),
            _p(2, 1, "From Corner", "A", CORNER, tiros=[("A", False)])]
    s = bp.construye_secuencias(poss, "Corner", "From Corner", None)
    assert [x["posesiones"] for x in s] == [[1], [2]]
    assert [x["S"] for x in s] == [0, 1]


def test_el_remate_del_defensor_no_cuenta_y_el_periodo_corta():
    poss = [_p(1, 1, "From Corner", "A", CORNER, tiros=[("B", True)]),
            _p(2, 2, "From Corner", "A", tiros=[("A", True)])]
    s = bp.construye_secuencias(poss, "Corner", "From Corner", None)
    assert s[0]["posesiones"] == [1] and s[0]["S"] == 0 and s[0]["G"] == 0


def test_tiro_libre_exige_campo_rival():
    poss = [_p(1, 1, "From Free Kick", "A", {"pass_type": "Free Kick", "x": 40.0}),
            _p(2, 1, "From Free Kick", "A", {"pass_type": "Free Kick", "x": 75.0})]
    s = bp.construye_secuencias(poss, "Free Kick", "From Free Kick", 60.0)
    assert [x["posesiones"] for x in s] == [[2]]


def test_la_deriva_por_torneo_se_cancela():
    # la liga remata 0.20 en T1 y 0.30 en T2; la unidad hace lo mismo que su liga
    n_b, s_b = np.array([1000.0, 1000.0]), np.array([200.0, 300.0])
    tu, base, did = bp.tasa_estandarizada(np.array([30.0, 10.0]), np.array([6.0, 3.0]), n_b, s_b)
    assert tu == pytest.approx(9 / 40)
    assert did == pytest.approx(0.0, abs=1e-12)
    # y un efecto real sobrevive
    _, _, did2 = bp.tasa_estandarizada(np.array([0.0, 100.0]), np.array([0.0, 40.0]), n_b, s_b)
    assert did2 == pytest.approx(0.10)


def test_base_sin_el_torneo_de_la_unidad_da_nan():
    _, base, did = bp.tasa_estandarizada(np.array([10.0, 0.0]), np.array([2.0, 0.0]),
                                         np.array([0.0, 50.0]), np.array([0.0, 10.0]))
    assert np.isnan(base) and np.isnan(did)


@pytest.mark.parametrize("disp", ["inicio", "final"])
def test_disposicion_de_coeficientes(disp):
    rng = np.random.default_rng(0)
    Z = rng.normal(size=(50, 3))
    b = np.array([0.5, -1.0, 0.3, 2.0])
    if disp == "inicio":
        pred = bp.sigm(b[0] + Z @ b[1:])
    else:
        pred = bp.sigm(Z @ b[:-1] + b[-1])
    assert bp.disposicion_coef(b, Z, pred) == disp
    assert bp.disposicion_coef(b, Z, pred + 0.1) == "desconocida"
    esperado = b[1:] if disp == "inicio" else b[:-1]
    np.testing.assert_allclose(bp.pendientes(b, disp), esperado)


def test_zonas():
    assert bp.zona_remate(116, 40) == "area_chica"
    assert bp.zona_remate(106, 40) == "area_central"
    assert bp.zona_remate(106, 20) == "area_lateral"
    assert bp.zona_remate(90, 40) == "fuera_del_area"
    assert bp.zona_destino(0.5, 30) == "primer_palo"      # cobro desde y<40, cae en y<40
    assert bp.zona_destino(0.5, 50) == "segundo_palo"
    assert bp.zona_destino(79.5, 40) == "central"


def test_auc_y_parsers():
    assert bp.auc(np.array([0, 0, 1, 1]), np.array([.1, .2, .3, .4])) == 1.0
    assert bp.xy_de("[108.5, 40.0]") == (108.5, 40.0)
    assert np.isnan(bp.xy_de(None)[0])
    assert bp.seg("00:01:02.500") == pytest.approx(62.5)


def test_a_literal_convierte_json_a_python():
    import ast
    s = '[{"location": [1.0, 2.0], "teammate": false, "x": null}]'
    with pytest.raises(ValueError):
        ast.literal_eval(s)                          # el bug #21
    assert ast.literal_eval(bp.a_literal(s))[0]["teammate"] is False
    assert bp.a_literal("[1.5, 2.5]") == "[1.5, 2.5]"
    assert bp.a_literal(None) is None


def test_elige_formato():
    assert bp.elige_formato(0, 480, 500) == "literal"
    assert bp.elige_formato(495, 495, 500) == "crudo"
    assert bp.elige_formato(10, 300, 500) is None
    assert bp.elige_formato(0, 0, 0) is None
