"""La regla de alcance (decision 3) y el candado de fronteras sin verificar.

`scripts/_alcance.py` no es parte del paquete `dtdecoder` -- los scripts son
standalone (13_CONTEXTO_IA §4) -- asi que se carga por ruta. Se testea igual
porque decide QUE PARTIDOS entran al ajuste, que es tan estructural como
cualquier cosa de `src/`.

Que cubre cada test:

  test_las_21_etapas_reales
      Las etiquetas que trae el indice del 2026-09-14, clasificadas a mano. Si
      un refactor de la regla moviera una sola, el universo de partidos
      cambiaria y las eras dejarian de cuadrar contra los eventos.

  test_prefijo_no_basta
      'Apertura - Quarter-finals' empieza con 'apertura' y NO es fase regular.
      Es el caso que la regla vieja de 01_construir_eras.py atrapaba por otra
      via; si alguien "simplifica" a un startswith, esto lo detiene.

  test_desconocida_se_excluye
      El default conservador. Una etiqueta nueva no se adivina: se excluye y se
      avisa. Un partido de mas contamina una era en silencio; uno de menos sale
      en el conteo.

  test_candado_*
      El candado de PRIMERA_DE_VENTANA: bloquea si nadie verifico, deja pasar
      si hay fila con fuente, y esta INACTIVO cuando no existe el CSV de eras
      del API -- si no, la demo con datos sinteticos y los tests dejarian de
      correr.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import polars as pl
import pytest

from dtdecoder.eras import check_verificada

_RUTA = Path(__file__).resolve().parents[1] / "scripts" / "_alcance.py"
_spec = importlib.util.spec_from_file_location("_alcance", _RUTA)
alcance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(alcance)


REGULARES = ["Apertura", "Clausura", "Regular Season"]

LIGUILLA = [
    "Apertura - Quarter-finals", "Quarter-finals", "Clausura - Quarter-finals",
    "Clausura - Semi-finals", "Apertura - Semi-finals", "Semi-finals",
    "Clausura - Reclasificacion", "Apertura - Reclasificación",
    "Clausura - Final", "Apertura - Final", "Play-In Round",
    "Apertura - Play-in Round", "Clausura - Finals", "Play-offs - Semi-Finals",
    "Finals", "Apertura - Finals", "Final", "Play-Offs - Finals",
]


def test_las_21_etapas_reales():
    assert len(REGULARES) + len(LIGUILLA) == 21
    for e in REGULARES:
        assert alcance.es_regular(e), e
    for e in LIGUILLA:
        assert not alcance.es_regular(e), e


def test_prefijo_no_basta():
    assert alcance.clasificar("Apertura - Quarter-finals") == alcance.LIGUILLA
    assert alcance.clasificar("Apertura") == alcance.REGULAR


def test_desconocida_se_excluye():
    assert alcance.clasificar("Torneo de Copa") == alcance.DESCONOCIDA
    assert alcance.es_regular("Torneo de Copa") is False
    assert alcance.clasificar("") == alcance.DESCONOCIDA
    assert alcance.clasificar(None) == alcance.DESCONOCIDA


def test_auditar_agrupa_todo():
    g = alcance.auditar(REGULARES + LIGUILLA + ["Copa MX"])
    assert sorted(g[alcance.REGULAR]) == sorted(REGULARES)
    assert len(g[alcance.LIGUILLA]) == len(LIGUILLA)
    assert g[alcance.DESCONOCIDA] == ["Copa MX"]


# --------------------------------------------------------------------------
def _eras_api(tmp_path, banderas="PRIMERA_DE_VENTANA"):
    p = tmp_path / "eras_todas.csv"
    pl.DataFrame(
        {
            "club": ["Puebla", "América"],
            "coach": ["Nicolas Larcamon", "Andre Jardine"],
            "n_partidos": [51, 102],
            "banderas": [banderas, "FUSIONADA(1)"],
        }
    ).write_csv(p)
    return p


def test_candado_bloquea_sin_verificar(tmp_path):
    with pytest.raises(SystemExit, match="PRIMERA_DE_VENTANA"):
        check_verificada("Puebla", "Nicolas Larcamon",
                         _eras_api(tmp_path), tmp_path / "no_hay.csv")


def test_candado_deja_pasar_con_fuente(tmp_path):
    ver = tmp_path / "eras_verificadas.csv"
    pl.DataFrame(
        {"club": ["Puebla"], "coach": ["Nicolas Larcamon"],
         "n_esperado": [51], "fuente": ["prensa 2022"], "fecha": ["2026-09-14"]}
    ).write_csv(ver)
    check_verificada("Puebla", "Nicolas Larcamon", _eras_api(tmp_path), ver)


def test_candado_fuente_vacia_no_vale(tmp_path):
    ver = tmp_path / "eras_verificadas.csv"
    pl.DataFrame(
        {"club": ["Puebla"], "coach": ["Nicolas Larcamon"],
         "n_esperado": [51], "fuente": [""], "fecha": [""]}
    ).write_csv(ver)
    with pytest.raises(SystemExit):
        check_verificada("Puebla", "Nicolas Larcamon", _eras_api(tmp_path), ver)


def test_candado_ignora_eras_no_marcadas(tmp_path):
    check_verificada("América", "Andre Jardine",
                     _eras_api(tmp_path), tmp_path / "no_hay.csv")


def test_candado_inactivo_sin_eras_api(tmp_path):
    # La demo sintetica y cualquier artefacto anterior a la migracion.
    check_verificada("Club A", "Quien Sea",
                     tmp_path / "no_existe.csv", tmp_path / "tampoco.csv")
