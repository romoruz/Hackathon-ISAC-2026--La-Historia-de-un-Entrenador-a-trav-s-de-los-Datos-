"""Ida y vuelta: lo que `phase1` ESCRIBE debe satisfacer lo que `phase2` EXIGE.

POR QUE ESTE ARCHIVO EXISTE APARTE
----------------------------------
`test_matrices_identity.py` prueba el verificador contra diccionarios
construidos a mano. Eso paso en verde mientras `phase1` NO escribia los
metadatos: el verificador era correcto y el productor no cumplia su parte, y
ningun test cruzaba los dos lados. El resultado fue un guardarrail que
abortaba SIEMPRE.

La leccion general: probar consumidor y productor por separado no prueba el
contrato entre ellos.
"""

from __future__ import annotations

import argparse
import inspect

import numpy as np

from dtdecoder import cli


# Campos que phase1 debe grabar en P_matrices.npz.
CAMPOS_IDENTIDAD = ("unit", "value", "baseline", "lam")


def test_phase1_graba_los_campos_de_identidad():
    """Inspeccion del fuente: el savez de phase1 nombra los campos exigidos."""
    src = inspect.getsource(cli.cmd_phase1)
    assert "P_matrices.npz" in src
    for campo in CAMPOS_IDENTIDAD:
        assert f"{campo}=np.array(" in src, (
            f"cmd_phase1 no graba '{campo}' en P_matrices.npz. "
            "El guardarrail de phase2/phase3 abortara siempre."
        )


def test_npz_real_satisface_al_verificador(tmp_path):
    """Escribe un .npz como lo hace phase1 y verificalo como lo hace phase2."""
    ruta = tmp_path / "P_matrices.npz"
    np.savez_compressed(
        ruta,
        P_focus=np.eye(3), P_base=np.eye(3), prior=np.eye(3),
        C_focus=np.zeros((3, 3)), C_base=np.zeros((3, 3)),
        unit=np.array("coach"),
        value=np.array("Andre Jardine"),
        baseline=np.array("other_coaches"),
        perspective=np.array("attack"),
        prior_mode=np.array("exclude_focus"),
        lam=np.array(500.0),
    )
    mats = np.load(ruta)
    args = argparse.Namespace(
        unit="coach", value="Andre Jardine", baseline="other_coaches", perspective="attack")
    assert cli._check_matrices_identity(mats, args) is None, (
        "phase1 y phase2 no se entienden: el productor escribe algo que el "
        "consumidor rechaza"
    )


def test_npz_real_de_otra_unidad_es_rechazado(tmp_path):
    """El caso que motivo todo: phase1 sobre Ortiz, phase2 sobre Jardine."""
    ruta = tmp_path / "P_matrices.npz"
    np.savez_compressed(
        ruta, P_focus=np.eye(3),
        unit=np.array("coach"), value=np.array("Fernando Ortiz"),
        baseline=np.array("other_coaches"), perspective=np.array("attack"), lam=np.array(500.0),
    )
    mats = np.load(ruta)
    args = argparse.Namespace(
        unit="coach", value="Andre Jardine", baseline="other_coaches", perspective="attack")
    err = cli._check_matrices_identity(mats, args)
    assert err is not None and "Fernando Ortiz" in err


def test_valores_con_acento_sobreviven_al_npz(tmp_path):
    """El club es 'América' y las eras usan el mismo literal.

    numpy guarda strings como arrays 0-d; un problema de codificacion aqui
    haria que el guardarrail rechazara corridas validas.
    """
    ruta = tmp_path / "P_matrices.npz"
    np.savez_compressed(
        ruta, unit=np.array("team"), value=np.array("América"),
        baseline=np.array("rest"), perspective=np.array("attack"), lam=np.array(0.0),
    )
    mats = np.load(ruta)
    args = argparse.Namespace(unit="team", value="América", baseline="rest", perspective="attack")
    assert cli._check_matrices_identity(mats, args) is None


def test_npz_sin_perspective_se_rechaza(tmp_path):
    """El campo `perspective` NO es opcional. Anadido con el parche D0.

    Antes de la cadena conjugada todo .npz era necesariamente ofensivo, asi que
    "falta el campo" implicaria "es attack". Aceptarlo por inferencia seria
    comodo y estaria MAL por dos razones:

      1. Un .npz de procedencia no declarada entraria al pipeline, y phase2
         podria calcular la cadena ofensiva rotulando figuras defensivas. Es
         el bug #7 con un campo mas, y no avisa.
      2. El parquet CAMBIO: `min_actions_defense = 1` altera
         transitions.parquet, asi que todos los artefactos anteriores estan
         obsoletos de todas formas. 04_DATA_CONTRACT §5.4 ya lo exige -- al
         cambiar una definicion, rerun completo desde phase0.

    Rechazar cuesta un `generar_todo.sh`. Aceptar cuesta una figura mal
    rotulada que nadie detecta. El precio correcto es obvio.

    Este test es la contraparte de los que verifican que un .npz coherente SI
    pasa: sin el, actualizar los tests para que dejen de fallar habria
    debilitado el contrato sin que quedara constancia en ningun sitio.
    """
    ruta = tmp_path / "P_matrices.npz"
    np.savez_compressed(
        ruta,
        unit=np.array("coach"),
        value=np.array("Andre Jardine"),
        baseline=np.array("other_coaches"),
        lam=np.array(500.0),
    )
    args = argparse.Namespace(
        unit="coach", value="Andre Jardine", baseline="other_coaches",
        perspective="attack",
    )
    err = cli._check_matrices_identity(np.load(ruta), args)
    assert err is not None, "un .npz sin `perspective` no puede pasar el contrato"
    assert "perspective" in err, "el mensaje debe nombrar el campo que falta"


def test_npz_defensivo_no_pasa_por_ofensivo(tmp_path):
    """EL CASO QUE MOTIVO EL CAMBIO.

        dtdecoder phase1 --unit coach_faced --value X --perspective defense
        dtdecoder phase2 --unit coach_faced --value X        (default: attack)

    `unit` coincide, `value` coincide: con el contrato anterior el guardarrail
    PASABA, y phase2 calculaba sobre la cadena ofensiva rotulando las figuras
    como defensivas.
    """
    ruta = tmp_path / "P_matrices.npz"
    np.savez_compressed(
        ruta,
        unit=np.array("coach_faced"),
        value=np.array("Andre Jardine"),
        baseline=np.array("other_coaches"),
        lam=np.array(500.0),
        perspective=np.array("defense"),
    )
    args = argparse.Namespace(
        unit="coach_faced", value="Andre Jardine", baseline="other_coaches",
        perspective="attack",
    )
    err = cli._check_matrices_identity(np.load(ruta), args)
    assert err is not None and "perspective" in err
