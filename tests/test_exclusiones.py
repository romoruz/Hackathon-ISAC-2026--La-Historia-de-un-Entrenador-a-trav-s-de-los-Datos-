"""Exclusion de partidos por `(club, match_id)` e invariante de fechas.

Los dos mecanismos que entran por `phase0` antes de construir nada.

Que cubre cada test:

  test_clave_es_la_tupla
      EL test del diseno. Un partido excluido para el America NO puede
      excluirse para su rival: en ese partido el rival tenia a su propio DT,
      legitimamente. Un filtro global por `match_id` pasaria todos los demas
      tests de este archivo y mutilaria la era del rival en silencio.

  test_solo_absorbidos
      El dump trae las 3,060 asignaciones; solo las filas con
      `dirigio_la_era == 0` son partidos a excluir. Sin este filtro se borraria
      el club entero.

  test_sin_columnas_falla_temprano
      Un CSV con otro formato tiene que reventar al leerlo, no devolver lista
      vacia y dejar que el pipeline corra "sin exclusiones".

  test_fechas_faltantes_abortan
      El invariante asimetrico: falta una fecha -> ValueError. Sin el, ese
      partido sale con `coach` nulo, indistinguible de un hueco real de era.

  test_fechas_de_sobra_son_legales
      El error logico contrario: exigir igualdad de conjuntos romperia el uso
      de un `match_dates` de liga sobre el parquet de un club.
"""
from __future__ import annotations

import polars as pl
import pytest

from dtdecoder.eras import check_dates_cover, load_exclusions

CLUB = "América"
RIVAL = "Cruz Azul"


def _dump(tmp_path):
    """Como lo emite `01_construir_eras.py --dump-asignacion`."""
    p = tmp_path / "absorbidos.csv"
    pl.DataFrame(
        {
            "club": [CLUB, CLUB, RIVAL, CLUB],
            "match_id": [3972016, 3972023, 3919090, 3972016],
            "era": ["Andre Jardine"] * 2 + ["Robert Siboldi", "Andre Jardine"],
            "coach_real": ["Diego Cervantes"] * 2 + ["Miguel Fuentes", "Andre Jardine"],
            "dirigio_la_era": [0, 0, 0, 1],
        }
    ).write_csv(p)
    return p


def test_clave_es_la_tupla(tmp_path):
    p = _dump(tmp_path)
    assert load_exclusions(p, CLUB) == [3972016, 3972023]
    # El 3972016 esta excluido para el America y NO para Cruz Azul.
    assert load_exclusions(p, RIVAL) == [3919090]


def test_solo_absorbidos(tmp_path):
    p = _dump(tmp_path)
    # La cuarta fila es del America con dirigio_la_era = 1: no se excluye.
    assert 3972016 in load_exclusions(p, CLUB, solo_absorbidos=False)
    assert len(load_exclusions(p, CLUB, solo_absorbidos=False)) == 2
    assert len(load_exclusions(p, CLUB, solo_absorbidos=True)) == 2


def test_club_sin_exclusiones(tmp_path):
    assert load_exclusions(_dump(tmp_path), "Toluca") == []


def test_sin_columnas_falla_temprano(tmp_path):
    p = tmp_path / "malo.csv"
    pl.DataFrame({"partido": [1], "equipo": ["X"]}).write_csv(p)
    with pytest.raises(KeyError):
        load_exclusions(p, CLUB)


def test_archivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_exclusions(tmp_path / "no_existe.csv", CLUB)


def _trans(ids):
    return pl.DataFrame({"match_id": ids, "team": [CLUB] * len(ids)})


def _dates(ids):
    return pl.DataFrame({"match_id": ids, "match_date": ["2024-01-01"] * len(ids)})


def test_fechas_faltantes_abortan():
    with pytest.raises(ValueError, match="NO tienen fecha"):
        check_dates_cover(_trans([1, 2, 3]), _dates([1, 2]))


def test_fechas_de_sobra_son_legales():
    # Un match_dates de liga sobre el parquet de un club: miles de sobra.
    check_dates_cover(_trans([1, 2]), _dates(list(range(1, 500))))


def test_cobertura_exacta():
    check_dates_cover(_trans([7, 9]), _dates([7, 9]))
