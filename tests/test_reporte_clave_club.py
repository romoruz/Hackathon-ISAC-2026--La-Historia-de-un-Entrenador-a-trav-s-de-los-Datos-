"""Clave compuesta (club, entrenador) en 12_reporte_html.defensa -- h2_11.

Patron del bug #17: el reporte filtraba los JSON de presion solo por nombre
de era. Con el mismo entrenador (o el mismo PAR, como Ambriz-Paiva en Toluca y
Leon) en dos clubes, el valor mostrado dependia del orden del glob.

El test pide que CADA club reciba SU valor. La version sin filtro no puede
cumplir las dos aserciones a la vez: devuelve lo mismo para ambos clubes.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def rep(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "reporte_html", RAIZ / "scripts" / "12_reporte_html.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "REPORTS", tmp_path)
    if hasattr(mod, "_SIN_CLUB"):
        mod._SIN_CLUB.clear()
    return mod


def _escribe(carpeta: Path, nombre: str, d: dict) -> None:
    (carpeta / nombre).write_text(json.dumps(d, ensure_ascii=False))


def test_calibracion_por_club(rep, tmp_path):
    # mismo entrenador en dos clubes, dos archivos de calibracion
    _escribe(tmp_path, "calibracion_andrejardine_fernandoortiz.json", {
        "club": "América",
        "eras": {"Andre Jardine": {"efecto_corregido": 0.111, "p": 0.01}}})
    _escribe(tmp_path, "calibracion_andrejardine_domenectorrent.json", {
        "club": "Atlético San Luis",
        "eras": {"Andre Jardine": {"efecto_corregido": 0.999, "p": 0.01}}})
    ame = rep.defensa(["Andre Jardine", "Fernando Ortiz"], "América")
    asl = rep.defensa(["Andre Jardine", "Domenec Torrent"], "Atlético San Luis")
    assert ame["instrumento"]["Andre Jardine"]["efecto"] == 0.111
    assert asl["instrumento"]["Andre Jardine"]["efecto"] == 0.999


def test_mismo_par_en_dos_clubes_q_y_nivel(rep, tmp_path):
    for club, pa, q in (("Toluca", 0.30, 0.01), ("León", 0.70, 0.90)):
        _escribe(tmp_path, f"nivel_calibracion_x_{club[:3]}.json", {
            "club": club, "era_a": "Ignacio Ambriz", "era_b": "Renato Paiva",
            "k0": 3, "nivel": {"pi_a": pa, "pi_b": 0.2, "diff": pa - 0.2,
                               "n_a": 100, "n_b": 100}})
    _escribe(tmp_path, "fdr_presion.json", {"contrastes": [
        {"club": "Toluca", "tipo": "nivel", "a": "Ignacio Ambriz",
         "b": "Renato Paiva", "detalle": "k>=3", "q": 0.01},
        {"club": "León", "tipo": "nivel", "a": "Ignacio Ambriz",
         "b": "Renato Paiva", "detalle": "k>=3", "q": 0.90}]})
    lista = ["Ignacio Ambriz", "Renato Paiva"]
    tol = rep.defensa(lista, "Toluca")["pares"]["Ignacio Ambriz|Renato Paiva"]["nivel"]
    leo = rep.defensa(lista, "León")["pares"]["Ignacio Ambriz|Renato Paiva"]["nivel"]
    assert (tol["pa"], tol["q"]) == (0.30, 0.01)
    assert (leo["pa"], leo["q"]) == (0.70, 0.90)


def test_json_sin_club_se_descarta_y_se_avisa(rep, tmp_path):
    _escribe(tmp_path, "calibracion_viejo.json", {
        "eras": {"Andre Jardine": {"efecto_corregido": 0.5, "p": 0.01}}})
    d = rep.defensa(["Andre Jardine", "Fernando Ortiz"], "América")
    assert "Andre Jardine" not in d["instrumento"]
    assert "calibracion_viejo.json" in rep._SIN_CLUB


def test_es_del_club(rep):
    assert rep._es_del_club({"club": "León"}, "León", "x")
    assert not rep._es_del_club({"club": "Cruz Azul"}, "León", "x")
    assert not rep._es_del_club({}, "León", "sin_club.json")
    assert "sin_club.json" in rep._SIN_CLUB


def test_25_ya_no_llama_ic_al_rango_de_submuestreo():
    src = (RAIZ / "scripts" / "25_pares_h4.py").read_text()
    assert "rel_E_T_ic95" not in src and "rel_xT_ic95" not in src
    assert "rel_E_T_rango_submuestreo" in src


def test_08_escribe_el_club():
    src = (RAIZ / "scripts" / "08_ic_derivados.py").read_text()
    assert '"club": club' in src
