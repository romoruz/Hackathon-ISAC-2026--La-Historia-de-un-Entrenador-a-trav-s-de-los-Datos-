"""Clave compuesta (club, entrenador) en 12_reporte_html -- h2_11, reescrito en h2_30.

Patrón del bug #17: el reporte filtraba por nombre de era. Con el mismo
entrenador (Jardine en América y en San Luis) o el mismo PAR de nombres en dos
clubes, el valor mostrado dependía del orden de los archivos.

Los cuatro primeros tests probaban `defensa()` y `_es_del_club()` del reporte
viejo (retirados con el tablero en h2_29). Aquí se prueba la misma intención
sobre `unidad()` y `par()` del reporte de ADR-59: cada club recibe SU valor,
en cualquier orden, y una entrada sin `club` nunca se usa.
"""
from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def rep():
    spec = importlib.util.spec_from_file_location(
        "reporte_html_clave", RAIZ / "scripts" / "12_reporte_html.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.SIN_CLUB.clear()
    return mod


UNIDADES = [
    {"club": "América", "coach": "Andre Jardine", "rel_E_T_vs_liga": 0.111},
    {"club": "Atlético San Luis", "coach": "Andre Jardine", "rel_E_T_vs_liga": 0.999},
]


@pytest.mark.parametrize("orden", list(itertools.permutations(range(2))))
def test_mismo_entrenador_en_dos_clubes(rep, orden):
    J = {"h4": {"unidades": [UNIDADES[i] for i in orden]}}
    assert rep.unidad(J, "h4", "América", "Andre Jardine")["rel_E_T_vs_liga"] == 0.111
    assert rep.unidad(J, "h4", "Atlético San Luis", "Andre Jardine")["rel_E_T_vs_liga"] == 0.999


PARES = [
    {"club": "Toluca", "a": "Ignacio Ambriz", "b": "Renato Paiva", "q": 0.01},
    {"club": "León", "a": "Renato Paiva", "b": "Ignacio Ambriz", "q": 0.90},
]


@pytest.mark.parametrize("orden", list(itertools.permutations(range(2))))
def test_mismo_par_en_dos_clubes(rep, orden):
    lista = [PARES[i] for i in orden]
    tol, tol_a = rep.par(lista, "Toluca", "Ignacio Ambriz", "Renato Paiva")
    leo, leo_a = rep.par(lista, "León", "Ignacio Ambriz", "Renato Paiva")
    assert (tol["q"], tol_a) == (0.01, True)
    # en León el par viene invertido: el generador debe saber voltear el signo
    assert (leo["q"], leo_a) == (0.90, False)


def test_entrada_sin_club_se_descarta_y_se_avisa(rep):
    J = {"h4": {"unidades": [{"coach": "Andre Jardine", "rel_E_T_vs_liga": 0.5}]}}
    with pytest.raises(KeyError):
        rep.unidad(J, "h4", "América", "Andre Jardine")
    assert any("Andre Jardine" in s for s in rep.SIN_CLUB)
    with pytest.raises(KeyError):
        rep.par([{"a": "Ignacio Ambriz", "b": "Renato Paiva"}], "Toluca",
                "Ignacio Ambriz", "Renato Paiva")
    assert any("Renato Paiva" in s for s in rep.SIN_CLUB)


def test_sin_club_no_tapa_a_la_buena(rep):
    J = {"h4": {"unidades": [{"coach": "Andre Jardine", "rel_E_T_vs_liga": 0.5},
                             UNIDADES[0]]}}
    assert rep.unidad(J, "h4", "América", "Andre Jardine")["rel_E_T_vs_liga"] == 0.111


def test_duplicado_en_el_mismo_club_falla(rep):
    J = {"h4": {"unidades": [UNIDADES[0], dict(UNIDADES[0], rel_E_T_vs_liga=0.2)]}}
    with pytest.raises(KeyError, match="2 unidades"):
        rep.unidad(J, "h4", "América", "Andre Jardine")


def test_25_ya_no_llama_ic_al_rango_de_submuestreo():
    src = (RAIZ / "scripts" / "25_pares_h4.py").read_text()
    assert "rel_E_T_ic95" not in src and "rel_xT_ic95" not in src
    assert "rel_E_T_rango_submuestreo" in src


def test_08_escribe_el_club():
    src = (RAIZ / "scripts" / "08_ic_derivados.py").read_text()
    assert '"club": club' in src
