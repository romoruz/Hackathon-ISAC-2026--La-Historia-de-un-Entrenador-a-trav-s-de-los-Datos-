"""`coach` y `coach_faced`: dos preguntas distintas, un contrato verificable.

`coach`        -> quien dirigia al EJECUTANTE. Null en las filas de rivales.
`coach_faced`  -> contra que DT se jugo el partido. No nulo en ninguna fila
                  de partido mapeado, incluidas las del rival.

Probar solo una de las dos dejaria pasar dos fallos distintos: un join de
fechas roto y un cambio de semantica en `attach_coach`. El test cruza los dos
lados, que es la leccion de `test_npz_contract.py`.
"""
from __future__ import annotations

import polars as pl

from dtdecoder.eras import attach_coach, attach_coach_faced

CLUB = "América"


def _fixture():
    mc = pl.DataFrame(
        {
            "match_id": [1, 2, 3],
            "coach": ["Andre Jardine", "Andre Jardine", "Fernando Ortiz"],
            "match_date": ["2024-01-01", "2024-01-08", "2023-02-01"],
        }
    )
    trans = pl.DataFrame(
        {
            "match_id": [1, 1, 2, 3, 3],
            "team": [CLUB, "Toluca", CLUB, "Tigres UANL", CLUB],
        }
    )
    return trans, mc


def test_coinciden_sobre_las_filas_del_club():
    trans, mc = _fixture()
    out = attach_coach_faced(attach_coach(trans, mc, CLUB), mc)
    club = out.filter(pl.col("team") == CLUB)
    assert club["coach"].to_list() == club["coach_faced"].to_list()


def test_coach_es_null_en_rivales_y_coach_faced_no():
    trans, mc = _fixture()
    out = attach_coach_faced(attach_coach(trans, mc, CLUB), mc)
    riv = out.filter(pl.col("team") != CLUB)
    assert riv["coach"].null_count() == riv.height
    assert riv["coach_faced"].null_count() == 0
    assert riv["coach_faced"].to_list() == ["Andre Jardine", "Fernando Ortiz"]


def test_partido_sin_era_deja_ambas_null():
    """Los huecos del CSV de eras salen como `unmapped_matches`, no inventados."""
    trans, mc = _fixture()
    trans = pl.concat(
        [trans, pl.DataFrame({"match_id": [99], "team": [CLUB]})], how="vertical"
    )
    out = attach_coach_faced(attach_coach(trans, mc, CLUB), mc)
    huerfano = out.filter(pl.col("match_id") == 99)
    assert huerfano["coach"].null_count() == 1
    assert huerfano["coach_faced"].null_count() == 1


def test_no_duplica_filas():
    """Un join mal hecho multiplica transiciones y todo conteo sale inflado."""
    trans, mc = _fixture()
    out = attach_coach_faced(attach_coach(trans, mc, CLUB), mc)
    assert out.height == trans.height
