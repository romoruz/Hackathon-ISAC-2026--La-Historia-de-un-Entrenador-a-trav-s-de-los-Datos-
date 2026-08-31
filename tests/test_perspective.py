"""La perspectiva: seleccion sobre un artefacto unico, y su guardarrail.

Dos clases de test aqui:

  1. NO-REGRESION. La ruta ofensiva no puede moverse ni un numero. Es la
     condicion que hace aceptable tocar modulos en produccion.
  2. EL GUARDARRAIL DEL BUG #7. Sin `perspective` en el contrato del .npz,
     phase2 puede consumir matrices defensivas y rotular figuras ofensivas
     (o al reves) sin decir nada.
"""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from dtdecoder import ingest, synth
from dtdecoder.cli import _apply_perspective, _check_matrices_identity
from dtdecoder.config import Config
from dtdecoder.grid import StateSpace
from dtdecoder.possessions import build_transitions, coordinate_sanity

CLUB = "Club A"


class NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
def trans_mini():
    return pl.DataFrame(
        {
            "poss_uid": ["1_1", "1_2", "2_1", "2_2"],
            "team": ["América", "Toluca", "América", "Tigres UANL"],
            "coach": ["Andre Jardine", None, "Andre Jardine", None],
            "coach_faced": ["Andre Jardine"] * 4,
        }
    )


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    """`build_transitions` espera el LazyFrame YA NORMALIZADO por `ingest.load`:
    necesita `start_x`, `pass_end_x`, etc., que `parse_location` deriva de las
    columnas de localizacion. Pasarle la salida cruda de `synth_events` revienta
    con ColumnNotFoundError. El pipeline real siempre pasa por ingest."""
    cfg = Config.load().raw
    sp = StateSpace(
        nx=cfg["pitch"]["nx"],
        ny=cfg["pitch"]["ny"],
        length=cfg["pitch"]["length"],
        width=cfg["pitch"]["width"],
        phases=tuple(cfg["phase_order"]),
    )
    p = tmp_path_factory.mktemp("synth") / "eventos.parquet"
    synth.synth_events(n_matches=30, dt_team=CLUB, seed=11).write_parquet(p)
    return ingest.load(p), sp, cfg


# ------------------------------------------------------------- perspectiva
def test_attack_no_filtra_nada(trans_mini):
    args = NS(perspective="attack", club="América", unit="coach")
    assert _apply_perspective(trans_mini, args).equals(trans_mini)


def test_sin_atributo_se_comporta_como_attack(trans_mini):
    """NO-REGRESION: codigo viejo que no pasa `perspective` sigue funcionando."""
    args = NS(club="América", unit="coach")
    assert _apply_perspective(trans_mini, args).equals(trans_mini)


def test_defense_excluye_al_club(trans_mini):
    args = NS(perspective="defense", club="América", unit="coach_faced")
    out = _apply_perspective(trans_mini, args)
    assert out.height == 2
    assert "América" not in out["team"].to_list()
    assert out["coach_faced"].null_count() == 0


def test_defense_con_unit_coach_falla_con_mensaje_util(trans_mini):
    """Sin este guardarrail la seleccion saldria VACIA y el error apuntaria a
    otra cosa: 'Sin transiciones para coach=...'. El fallo tiene que nombrar
    la causa."""
    args = NS(perspective="defense", club="América", unit="coach")
    with pytest.raises(SystemExit, match="coach_faced"):
        _apply_perspective(trans_mini, args)


def test_defense_sin_club_falla(trans_mini):
    args = NS(perspective="defense", club=None, unit="coach_faced")
    with pytest.raises(SystemExit, match="club"):
        _apply_perspective(trans_mini, args)


def test_defense_sin_columna_pide_rerun(trans_mini):
    args = NS(perspective="defense", club="América", unit="coach_faced")
    with pytest.raises(SystemExit, match="phase0"):
        _apply_perspective(trans_mini.drop("coach_faced"), args)


# --------------------------------------------- el guardarrail del bug #7
def test_npz_defensivo_no_pasa_por_ofensivo():
    """EL TEST QUE IMPORTA.

    `unit` y `value` coinciden, asi que el chequeo antiguo PASABA: phase2
    calculaba sobre la cadena ofensiva y rotulaba las figuras 'defensiva'.
    """
    mats = {
        "unit": np.array("coach_faced"),
        "value": np.array("Andre Jardine"),
        "perspective": np.array("defense"),
    }
    args = NS(unit="coach_faced", value="Andre Jardine",
              baseline="other_coaches", perspective="attack")
    err = _check_matrices_identity(mats, args)
    assert err is not None and "perspective" in err


def test_npz_sin_perspective_se_rechaza():
    """Un .npz de procedencia ambigua no se acepta 'por compatibilidad'."""
    mats = {"unit": np.array("coach"), "value": np.array("Andre Jardine")}
    args = NS(unit="coach", value="Andre Jardine",
              baseline="other_coaches", perspective="attack")
    err = _check_matrices_identity(mats, args)
    assert err is not None


def test_npz_coherente_pasa():
    mats = {
        "unit": np.array("coach_faced"),
        "value": np.array("Andre Jardine"),
        "perspective": np.array("defense"),
    }
    args = NS(unit="coach_faced", value="Andre Jardine",
              baseline="other_coaches", perspective="defense")
    assert _check_matrices_identity(mats, args) is None


# ------------------------------------------------------- min_actions y datos
def test_min_actions_asimetrico_no_toca_al_club(entorno):
    """NO-REGRESION dura: ni una posesion del club entra o sale."""
    ev, sp, cfg = entorno
    base = build_transitions(ev, sp, cfg, team=None, club=None)
    conclub = build_transitions(ev, sp, cfg, team=None, club=CLUB)

    a1 = set(base.filter(pl.col("team") == CLUB)["poss_uid"].to_list())
    a2 = set(conclub.filter(pl.col("team") == CLUB)["poss_uid"].to_list())
    assert a1 == a2, "el min_actions asimetrico movio posesiones del club"


def test_min_actions_defense_conserva_mas_posesiones_rivales(entorno):
    """El filtro de longitud no puede comerse lo que la presion produce."""
    ev, sp, cfg = entorno
    base = build_transitions(ev, sp, cfg, team=None, club=None)
    conclub = build_transitions(ev, sp, cfg, team=None, club=CLUB)

    d1 = set(base.filter(pl.col("team") != CLUB)["poss_uid"].to_list())
    d2 = set(conclub.filter(pl.col("team") != CLUB)["poss_uid"].to_list())
    assert d2 >= d1
    assert len(d2) > len(d1), "min_actions_defense=1 deberia conservar mas"


def test_under_pressure_es_bandera_no_booleano(entorno):
    """Ninguna accion REAL puede quedar con la marca nula tras el fill_null.
    Las filas TERMINAL si: son artificiales y no corresponden a un evento."""
    ev, sp, cfg = entorno
    tr = build_transitions(ev, sp, cfg, team=None, club=CLUB)
    reales = tr.filter(pl.col("action_type") != "TERMINAL")
    assert reales["under_pressure"].null_count() == 0
    tasa = float(reales["under_pressure"].mean())
    assert 0.0 < tasa < 1.0, f"tasa de presion degenerada: {tasa}"

    term = tr.filter(pl.col("action_type") == "TERMINAL")
    if term.height:
        assert term["under_pressure"].null_count() == term.height


def test_score_state_club_se_invierte_para_el_rival(entorno):
    """Sin esto, 'presiona mas cuando va ganando' diria lo contrario."""
    ev, sp, cfg = entorno
    tr = build_transitions(ev, sp, cfg, team=None, club=CLUB)
    assert "score_state_club" in tr.columns

    mios = tr.filter(pl.col("team") == CLUB)
    assert mios["score_state"].to_list() == mios["score_state_club"].to_list()

    riv = tr.filter((pl.col("team") != CLUB) & (pl.col("score_state") != "drawing"))
    if riv.height:
        pares = set(zip(riv["score_state"].to_list(),
                        riv["score_state_club"].to_list()))
        assert all(a != b for a, b in pares), "el marcador no se invirtio"


def test_coordinate_sanity_vale_en_marco_nativo(entorno):
    """La conjugada NO se refleja: el rival sigue atacando hacia x=120, asi que
    la correlacion debe ser POSITIVA tambien sobre sus filas."""
    ev, sp, cfg = entorno
    tr = build_transitions(ev, sp, cfg, team=None, club=CLUB)
    riv = tr.filter(pl.col("team") != CLUB)
    assert coordinate_sanity(riv, sp)["corr"] > 0.0
