"""Contrato de identidad de `P_matrices.npz`.

EL BUG (encontrado 2026-08-20)
------------------------------
`phase2` y `phase3` leen la matriz de transicion del .npz que dejo la ULTIMA
corrida de `phase1`, pero reciben --unit/--value propios y los usan para
rotular figuras y reportes. Esta secuencia:

    dtdecoder phase1 --unit coach --value "Fernando Ortiz"
    dtdecoder phase2 --unit coach --value "Andre Jardine"

modelaba a Ortiz y producia `xt.png` con el titulo "xT propio -- Andre
Jardine". Ninguna excepcion, ningun aviso. Se detecto solo porque
`expected_length_mean` cambio 5% entre dos corridas del MISMO comando.

Estado compartido en disco entre fases, sin contrato de procedencia.

ACTUALIZADO (parche D0, cadena conjugada)
-----------------------------------------
`perspective` entra al contrato. Sin ella, esta secuencia volvia a colar:

    dtdecoder phase1 --unit coach_faced --value X --perspective defense
    dtdecoder phase2 --unit coach_faced --value X          (default: attack)

`unit` coincide, `value` coincide, el guardarrail PASABA, y phase2 calculaba
sobre la cadena ofensiva rotulando las figuras como defensivas. Es el mismo
bug con un campo mas.
"""

from __future__ import annotations

import argparse

import numpy as np
import pytest

from dtdecoder.cli import _check_matrices_identity


def _args(unit="coach", value="Andre Jardine", baseline="other_coaches",
          perspective="attack"):
    return argparse.Namespace(unit=unit, value=value, baseline=baseline,
                              perspective=perspective)


def _mats(unit="coach", value="Andre Jardine", perspective="attack"):
    return {
        "unit": np.array(unit),
        "value": np.array(value),
        "perspective": np.array(perspective),
    }


def test_identidad_coincidente_pasa():
    assert _check_matrices_identity(_mats(), _args()) is None


def test_value_distinto_es_rechazado():
    """El caso real: phase1 sobre Ortiz, phase2 sobre Jardine."""
    err = _check_matrices_identity(_mats(value="Fernando Ortiz"), _args())
    assert err is not None
    assert "Fernando Ortiz" in err and "Andre Jardine" in err


def test_unit_distinto_es_rechazado():
    err = _check_matrices_identity(_mats(unit="team"), _args(unit="coach"))
    assert err is not None


def test_perspective_distinta_es_rechazada():
    """EL CASO QUE MOTIVO ANADIR EL CAMPO.

    Mismo DT, misma unidad, perspectivas opuestas: con el contrato anterior
    esto pasaba, y phase2 rotulaba de defensiva una cadena ofensiva.
    """
    err = _check_matrices_identity(
        _mats(unit="coach_faced", perspective="defense"),
        _args(unit="coach_faced", perspective="defense"),
    )
    assert err is None, "una corrida coherente en defensa debe pasar"

    err = _check_matrices_identity(
        _mats(unit="coach_faced", perspective="defense"),
        _args(unit="coach_faced", perspective="attack"),
    )
    assert err is not None and "perspective" in err


def test_npz_sin_metadatos_es_rechazado():
    """Un .npz de una version previa de phase1 no declara identidad.

    Debe abortar, no asumir que coincide: asumir es como empezo el bug.
    """
    err = _check_matrices_identity({}, _args())
    assert err is not None
    assert "phase1" in err


@pytest.mark.parametrize("campo", ["unit", "value", "perspective"])
def test_falta_un_solo_campo_es_rechazado(campo):
    """`perspective` no es opcional.

    Se considero tratar su ausencia como "attack" -- inferencia VERDADERA,
    porque antes del parche D0 todo .npz era ofensivo. Se descarto: el parquet
    cambio (min_actions_defense = 1 altera transitions.parquet), asi que TODOS
    los artefactos anteriores estan obsoletos de todas formas, y
    04_DATA_CONTRACT §5.4 ya exige rerun completo al cambiar una definicion.
    Rechazar cuesta un generar_todo.sh; aceptar cuesta una figura mal rotulada
    que nadie detecta.
    """
    m = _mats()
    del m[campo]
    assert _check_matrices_identity(m, _args()) is not None


def test_el_mensaje_dice_como_arreglarlo():
    """Un error silencioso se cambia por uno que explica el remedio."""
    err = _check_matrices_identity(_mats(value="Santiago Solari"), _args())
    assert "dtdecoder phase1" in err


def test_el_mensaje_incluye_la_perspectiva():
    """El comando sugerido debe ser el que de verdad arregla el problema.

    Si el mensaje omite --perspective, seguir la instruccion al pie de la letra
    reproduce el fallo.
    """
    err = _check_matrices_identity(
        _mats(unit="coach_faced", value="Fernando Ortiz", perspective="defense"),
        _args(unit="coach_faced", value="Andre Jardine", perspective="defense"),
    )
    assert "--perspective defense" in err
