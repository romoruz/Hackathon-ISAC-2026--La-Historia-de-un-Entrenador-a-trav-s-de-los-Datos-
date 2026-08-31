"""Trazabilidad: todo reporte debe declarar con que config y commit se produjo.

MOTIVO (08_REPRODUCIBILITY.md §9)
---------------------------------
Una `cv_lambda.png` generada en v0.3 -- rejilla hasta 500, lambda* = 50 --
sobrevivio al arreglo de la fuga de prior y siguio en `figures/` mucho despues
de que ninguna corrida respaldara ese numero. No habia forma de saber que
estaba obsoleta mirandola.

Es el patron de riesgo dominante del proyecto: no falla, miente.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dtdecoder.cli import _provenance

REPORTES = ("phase0_report.json", "phase1_report.json", "phase2_report.json")
LLAVES = ("config_sha256", "config_path", "git_commit", "dtdecoder_version")


def test_provenance_tiene_todas_las_llaves():
    prov = _provenance("config/default.yaml")
    for k in LLAVES:
        assert k in prov, f"falta la llave '{k}' en provenance"


def test_version_se_resuelve():
    """La version debe resolverse de verdad, no quedar en None.

    La llave existia pero valia None por un NameError silenciado: el reporte
    se habria escrito igual, sin version, sin avisar. Este test lo cierra.
    """
    prov = _provenance("config/default.yaml")
    assert prov["dtdecoder_version"], (
        "dtdecoder_version vacia: revisa que __init__.py exponga __version__"
    )


def test_config_hash_es_estable_y_sensible(tmp_path):
    """El mismo contenido da el mismo hash; un cambio lo cambia."""
    a = tmp_path / "a.yaml"
    a.write_text("nx: 5\nny: 4\n")
    h1 = _provenance(str(a))["config_sha256"]
    h2 = _provenance(str(a))["config_sha256"]
    assert h1 == h2

    a.write_text("nx: 6\nny: 4\n")
    assert _provenance(str(a))["config_sha256"] != h1, (
        "cambiar el config debe cambiar el hash, o la trazabilidad no sirve"
    )


def test_config_none_cae_al_default():
    """args.config llega None desde los subparsers de fase.

    Config.load(None) cae al default; _provenance debe hacer lo mismo en vez
    de reventar con TypeError al construir Path(None). Rompio phase0, phase1
    y phase2 a la vez.
    """
    prov = _provenance(None)
    assert prov["config_path"].endswith("default.yaml")


def test_config_inexistente_no_revienta():
    """Un config ausente degrada a None, no aborta el pipeline."""
    prov = _provenance("/no/existe/config.yaml")
    assert prov["config_sha256"] is None


@pytest.mark.parametrize("nombre", REPORTES)
def test_reportes_en_disco_traen_provenance(nombre):
    """Si hay reportes de corridas previas, deben traer procedencia.

    Se salta si no existen: no todo entorno ha corrido el pipeline.
    """
    p = Path("data/processed") / nombre
    if not p.exists():
        pytest.skip(f"{nombre} no existe; corre el pipeline primero")
    rep = json.loads(p.read_text())
    assert "provenance" in rep, (
        f"{nombre} sin procedencia: fue generado antes del parche. "
        "Regeneralo antes de usar sus numeros o sus figuras."
    )
    for k in LLAVES:
        assert k in rep["provenance"]
