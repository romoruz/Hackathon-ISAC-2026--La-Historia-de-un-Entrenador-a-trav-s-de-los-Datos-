"""`coach` y `coach_faced`: dos preguntas distintas, un contrato verificable.

`coach`        -> quien dirigia al EJECUTANTE de la accion.
`coach_faced`  -> quien dirigia al equipo que NO ejecuta.

DEFINICION NUEVA (2026-09-14). La anterior asignaba "el DT del club focal" a
todas las filas del partido, incluidas las del propio club, donde coincidia con
`coach`. Sobre un artefacto de LIGA esa definicion no existe: cada partido tiene
dos entrenadores y ninguno es "el del club".

Que cubre cada test, y que fallo dejaria pasar si faltara:

  test_filas_rival_no_cambian
      Es EL test de regresion del cambio de definicion. La cadena conjugada y
      todo el bloque D1 leen solo filas de rivales; si su `coach_faced` se
      moviera, los numeros de presion cambiarian sin que nada fallara.

  test_filas_del_club_ya_no_son_tautologia
      Sin el, un `attach_coach_faced` que siguiera copiando el coach del club a
      todas las filas pasaria inadvertido.

  test_club_none_equivale_a_club_explicito
      Cruza los dos caminos de `attach_coach`. Son el mismo mapeo por dos vias
      distintas -- por `team == club` y por join en `(match_id, club)` -- y
      tienen que coincidir fila a fila, o el artefacto de liga y el de club
      dirian cosas distintas del mismo partido.

  test_partido_sin_era
      Un partido fuera de toda era deja las dos columnas en null, no una sola.

  test_rival_con_eras_propias
      El caso de liga: cuando se conocen las eras de los dos equipos,
      `coach_faced` de cada lado es el DT del otro.
"""
from __future__ import annotations

import polars as pl

from dtdecoder.eras import attach_coach, attach_coach_faced

CLUB = "América"
RIVAL = "Cruz Azul"


def _mc(clubes=(CLUB,)):
    """Tabla (match_id, coach, match_date, club) como la emite match_coach_table."""
    filas = []
    for c in clubes:
        pref = "Andre Jardine" if c == CLUB else "Martin Anselmi"
        alt = "Fernando Ortiz" if c == CLUB else "Vicente Sanchez"
        filas += [
            {"match_id": 1, "coach": pref, "match_date": "2024-01-01", "club": c},
            {"match_id": 2, "coach": pref, "match_date": "2024-01-08", "club": c},
            {"match_id": 3, "coach": alt, "match_date": "2023-02-01", "club": c},
        ]
    return pl.DataFrame(filas)


def _trans():
    """Dos equipos por partido, tres partidos. El 4 no esta en ninguna era."""
    filas = []
    for mid in (1, 2, 3, 4):
        for team in (CLUB, RIVAL):
            for k in range(2):
                filas.append({"match_id": mid, "team": team, "poss_uid": f"{mid}_{team}_{k}"})
    return pl.DataFrame(filas)


def _full(mc, club=CLUB):
    t = attach_coach(_trans(), mc, club)
    return attach_coach_faced(t, mc)


def test_filas_rival_no_cambian():
    out = _full(_mc())
    riv = out.filter(pl.col("team") != CLUB).sort("match_id")
    # En las filas del rival, el equipo que NO ejecuta es el club: su DT.
    assert riv.filter(pl.col("match_id") == 1)["coach_faced"].to_list() == [
        "Andre Jardine"] * 2
    assert riv.filter(pl.col("match_id") == 3)["coach_faced"].to_list() == [
        "Fernando Ortiz"] * 2
    # Y `coach` sigue siendo null: el rival no es el club.
    assert riv["coach"].null_count() == riv.height


def test_filas_del_club_ya_no_son_tautologia():
    out = _full(_mc())
    club = out.filter(pl.col("team") == CLUB)
    assert club["coach"].null_count() == 2  # solo el partido 4, sin era
    # Sin las eras del rival, su DT es desconocido. NO es el del propio club.
    assert club["coach_faced"].null_count() == club.height


def test_club_none_equivale_a_club_explicito():
    mc = _mc()
    a = attach_coach(_trans(), mc, CLUB).sort(["match_id", "team", "poss_uid"])
    b = attach_coach(_trans(), mc, None).sort(["match_id", "team", "poss_uid"])
    assert a["coach"].to_list() == b["coach"].to_list()
    assert a["match_date"].to_list() == b["match_date"].to_list()


def test_partido_sin_era():
    out = _full(_mc())
    m4 = out.filter(pl.col("match_id") == 4)
    assert m4.height == 4
    assert m4["coach"].null_count() == 4
    assert m4["coach_faced"].null_count() == 4


def test_rival_con_eras_propias():
    """Artefacto de liga: los dos equipos tienen eras y se ven mutuamente."""
    mc = _mc((CLUB, RIVAL))
    out = attach_coach_faced(attach_coach(_trans(), mc, None), mc)
    m1 = out.filter(pl.col("match_id") == 1)
    club = m1.filter(pl.col("team") == CLUB)
    riv = m1.filter(pl.col("team") == RIVAL)
    assert club["coach"].unique().to_list() == ["Andre Jardine"]
    assert club["coach_faced"].unique().to_list() == ["Martin Anselmi"]
    assert riv["coach"].unique().to_list() == ["Martin Anselmi"]
    assert riv["coach_faced"].unique().to_list() == ["Andre Jardine"]
