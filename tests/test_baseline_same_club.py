"""`other_coaches` contra `other_coaches_same_club`.

La etiqueta nueva existe porque el significado de la vieja CAMBIA segun el
artefacto sobre el que corre, y cambia en silencio:

  * sobre el parquet de un club, `coach` es null fuera del club, asi que
    "otros entrenadores" ya son "otras eras del mismo club" (ADR-16);
  * sobre el parquet de la liga, `coach` no es null en ningun lado, asi que
    pasan a ser los 102 entrenadores de la liga -- un contraste distinto, que
    no controla plantel, presupuesto, cantera, estadio ni calendario.

Que cubre cada test:

  test_identicas_sobre_artefacto_de_un_club
      La garantia de no-regresion: sobre lo que hay hoy, la etiqueta nueva no
      cambia ni una fila. Si este test fallara, instalar el paquete moveria
      resultados ya validados.

  test_difieren_sobre_artefacto_de_liga
      Que la etiqueta sirva para algo. Sin el, `other_coaches_same_club`
      podria ser un alias inutil y nadie lo notaria hasta leer el codigo.

  test_requiere_club
      El modo nuevo sin `--club` no puede adivinar el club: tiene que fallar.

  test_perspectiva_defensiva
      En la conjugada las filas del club focal son las del RIVAL, asi que la
      restriccion se invierte. Cablearla como `team == club` dejaria la linea
      base vacia, con un mensaje que no dice por que.
"""
from __future__ import annotations

import polars as pl
import pytest

from dtdecoder.eras import select_units

CLUB = "América"


def _un_club():
    """Artefacto de un club: `coach` null en las filas de rivales."""
    return pl.DataFrame(
        {
            "team": [CLUB, CLUB, CLUB, "Toluca", "Tigres UANL"],
            "coach": ["Andre Jardine", "Fernando Ortiz", "Santiago Solari",
                      None, None],
            "coach_faced": ["Andre Jardine", "Fernando Ortiz", "Santiago Solari",
                            "Andre Jardine", "Fernando Ortiz"],
            "poss_uid": list("abcde"),
        }
    )


def _liga():
    """Artefacto de liga: todas las filas tienen DT."""
    return pl.DataFrame(
        {
            "team": [CLUB, CLUB, "Toluca", "Tigres UANL"],
            "coach": ["Andre Jardine", "Fernando Ortiz",
                      "Antonio Mohamed", "Veljko Paunovic"],
            "coach_faced": [None, None, None, None],
            "poss_uid": list("abcd"),
        }
    )


def test_identicas_sobre_artefacto_de_un_club():
    t = _un_club()
    _, b1 = select_units(t, "coach", "Andre Jardine", "other_coaches", CLUB)
    _, b2 = select_units(t, "coach", "Andre Jardine",
                         "other_coaches_same_club", CLUB)
    assert b1["poss_uid"].to_list() == b2["poss_uid"].to_list() == ["b", "c"]


def test_difieren_sobre_artefacto_de_liga():
    t = _liga()
    _, b1 = select_units(t, "coach", "Andre Jardine", "other_coaches", CLUB)
    _, b2 = select_units(t, "coach", "Andre Jardine",
                         "other_coaches_same_club", CLUB)
    assert b1["poss_uid"].to_list() == ["b", "c", "d"]   # toda la liga
    assert b2["poss_uid"].to_list() == ["b"]             # solo el America


def test_requiere_club():
    with pytest.raises(ValueError, match="requiere --club"):
        select_units(_liga(), "coach", "Andre Jardine",
                     "other_coaches_same_club", None)


def test_perspectiva_defensiva():
    t = _un_club()
    _, b = select_units(t, "coach_faced", "Andre Jardine",
                        "other_coaches_same_club", CLUB)
    # Las filas de la conjugada son las del RIVAL, no las del club.
    assert set(b["poss_uid"].to_list()) == {"e"}
    assert (b["team"] != CLUB).all()
