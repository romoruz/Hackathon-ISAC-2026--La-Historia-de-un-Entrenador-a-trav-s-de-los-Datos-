"""Tests de eras de DT: replican el caso real (un club, varios entrenadores)."""

import datetime as dt

import numpy as np
import polars as pl
import pytest

from dtdecoder.config import Config
from dtdecoder.eras import (
    attach_coach,
    coverage_report,
    load_eras,
    load_match_dates,
    match_coach_table,
    select_units,
    unmapped_matches,
    write_template,
)
from dtdecoder.grid import StateSpace
from dtdecoder.ingest import normalize, scan_events
from dtdecoder.possessions import build_transitions
from dtdecoder.synth import synth_events

CLUB = "Club A"


def _setup(tmp_path, n_matches=60):
    cfg = Config.load()
    space = StateSpace(nx=cfg["pitch"]["nx"], ny=cfg["pitch"]["ny"])
    ev = synth_events(n_matches=n_matches, dt_bias=0.5, seed=21)
    trans = build_transitions(normalize(ev.lazy()), space, cfg.raw)

    # fechas ficticias: un partido por semana
    mids = sorted(trans["match_id"].unique().to_list())
    dates = [dt.date(2021, 8, 1) + dt.timedelta(days=7 * k) for k in range(len(mids))]
    md = pl.DataFrame({"match_id": mids, "match_date": [d.isoformat() for d in dates]})
    md_path = tmp_path / "match_dates.csv"
    md.write_csv(md_path)

    split = dates[len(dates) // 2]
    eras = pl.DataFrame(
        {
            "coach": ["DT Uno", "DT Dos"],
            "start_date": ["2021-08-01", split.isoformat()],
            "end_date": [
                (split - dt.timedelta(days=1)).isoformat(),
                "2030-12-31",
            ],
        }
    )
    eras_path = tmp_path / "eras.csv"
    eras.write_csv(eras_path)
    return cfg, space, trans, eras_path, md_path


def test_template_roundtrip(tmp_path):
    p = write_template(tmp_path / "t.csv")
    df = load_eras(p)
    assert df.height >= 3
    assert df["start_date"].is_sorted()


def test_overlapping_eras_rejected(tmp_path):
    p = tmp_path / "bad.csv"
    pl.DataFrame(
        {
            "coach": ["A", "B"],
            "start_date": ["2021-01-01", "2021-06-01"],
            "end_date": ["2021-12-31", "2022-12-31"],
        }
    ).write_csv(p)
    with pytest.raises(ValueError, match="traslapadas"):
        load_eras(p)


def test_coach_assignment_partitions_matches(tmp_path):
    cfg, space, trans, eras_path, md_path = _setup(tmp_path)
    eras = load_eras(eras_path)
    md = load_match_dates(md_path)
    mc = match_coach_table(md, eras, CLUB)

    # cada partido cae en exactamente una era
    assert mc["match_id"].n_unique() == mc.height
    assert set(mc["coach"].unique()) == {"DT Uno", "DT Dos"}

    out = attach_coach(trans, mc, CLUB)
    # el rival nunca lleva DT del club
    assert out.filter(pl.col("team") != CLUB)["coach"].null_count() == out.filter(
        pl.col("team") != CLUB
    ).height
    # el club siempre lo lleva (no hay huecos en este setup)
    assert unmapped_matches(out, CLUB).height == 0


def test_coverage_report_flags_small_eras(tmp_path):
    cfg, space, trans, eras_path, md_path = _setup(tmp_path)
    mc = match_coach_table(load_match_dates(md_path), load_eras(eras_path), CLUB)
    out = attach_coach(trans, mc, CLUB)
    cov = coverage_report(out, CLUB)
    assert set(cov.columns) >= {"coach", "matches", "possessions", "suficiente"}
    assert cov["matches"].sum() == out.filter(pl.col("team") == CLUB)["match_id"].n_unique()


def test_baselines_are_disjoint_from_focus(tmp_path):
    cfg, space, trans, eras_path, md_path = _setup(tmp_path)
    mc = match_coach_table(load_match_dates(md_path), load_eras(eras_path), CLUB)
    out = attach_coach(trans, mc, CLUB)

    for baseline in ("rest", "other_coaches", "opponents"):
        focus, base = select_units(out, "coach", "DT Uno", baseline, club=CLUB)
        assert focus.height > 0 and base.height > 0
        assert base.filter(pl.col("coach") == "DT Uno").height == 0

    # other_coaches solo trae al propio club
    _, base = select_units(out, "coach", "DT Uno", "other_coaches", club=CLUB)
    assert set(base["team"].unique()) == {CLUB}
    # opponents nunca trae al club
    _, base_opp = select_units(out, "coach", "DT Uno", "opponents", club=CLUB)
    assert CLUB not in set(base_opp["team"].unique())


def test_missing_coach_column_gives_clear_error(tmp_path):
    cfg, space, trans, _, _ = _setup(tmp_path)
    with pytest.raises(KeyError, match="phase0"):
        select_units(trans, "coach", "DT Uno", "rest")


def test_csv_with_late_appearing_columns(tmp_path):
    """Reproduce el fallo real: columnas vacias en las primeras filas de un CSV.

    Con el `infer_schema_length` por defecto de polars, `shot_outcome` se tipa
    como Null y el pipeline devuelve cero goles en silencio.
    """
    ev = synth_events(n_matches=8, seed=3)
    # fuerza que los primeros 200 renglones no tengan shot_outcome
    ev = ev.sort(pl.col("shot_outcome").is_not_null())
    # serializa las listas como "[x, y]", tal como sale un volcado a CSV
    ev = ev.with_columns(
        [
            pl.when(pl.col(c).is_null())
            .then(None)
            .otherwise(
                pl.lit("[")
                + pl.col(c).list.get(0).cast(pl.Utf8)
                + pl.lit(", ")
                + pl.col(c).list.get(1).cast(pl.Utf8)
                + pl.lit("]")
            )
            .alias(c)
            for c in ("location", "pass_end_location", "carry_end_location",
                      "shot_end_location")
        ]
    )
    p = tmp_path / "events.csv"
    ev.write_csv(p)

    lf = normalize(scan_events(p))
    cfg = Config.load()
    space = StateSpace(nx=cfg["pitch"]["nx"], ny=cfg["pitch"]["ny"])
    trans = build_transitions(lf, space, cfg.raw)
    assert trans.height > 0
    # los goles deben haberse detectado
    goal_idx = space.absorbing_index("GOAL")
    assert (trans["to_state"] == goal_idx).sum() > 0
    # y las coordenadas parseadas desde string
    assert trans["from_state"].max() < space.n_transient


def test_score_state_uses_pregoal_state(tmp_path):
    """El gol no debe contar para su propio evento."""
    cfg, space, trans, _, _ = _setup(tmp_path, n_matches=20)
    counts = trans.group_by("score_state").len().to_dict(as_series=False)
    assert "drawing" in counts["score_state"]
    # el primer evento de cada partido siempre esta empatado
    first = trans.sort(["match_id", "event_index"]).group_by("match_id").first()
    assert (first["score_state"] == "drawing").all()


def test_compare_two_eras_end_to_end(tmp_path):
    from dtdecoder.estimate import count_matrix, shrink
    from dtdecoder.inference import tactical_fingerprint

    cfg, space, trans, eras_path, md_path = _setup(tmp_path)
    mc = match_coach_table(load_match_dates(md_path), load_eras(eras_path), CLUB)
    out = attach_coach(trans, mc, CLUB)

    prior = shrink(count_matrix(out, space),
                   np.full((space.n_transient, space.n_states), 1 / space.n_states), 1.0)
    a = out.filter(pl.col("coach") == "DT Uno")
    b = out.filter(pl.col("coach") == "DT Dos")
    Pb = shrink(count_matrix(b, space), prior, 50.0)
    fp = tactical_fingerprint(a, b, space, Pb, n_boot=100, seed=1)
    assert np.isfinite(fp.g2_obs).all()
    assert fp.pvalue.min() >= 0 and fp.pvalue.max() <= 1


def test_phase_order_is_explicit_not_dict_order(tmp_path):
    """Regresion: el orden de fases NO debe depender del orden de las llaves.

    `yaml.safe_dump` reordena alfabeticamente. Si los indices de fase salieran
    del dict, una recarga del mismo config produciria un layout distinto y las
    matrices guardadas quedarian desalineadas en silencio.
    """
    import yaml
    from dtdecoder.ingest import normalize
    from dtdecoder.synth import synth_events

    base = Config.load()
    raw = dict(base.raw)
    raw["phase_order"] = ["open", "transition", "restart", "set_piece"]
    raw["phase_default"] = "open"
    raw["phases"] = {
        "open": ["Regular Play", "From Kick Off"],
        "transition": ["From Counter", "From Keeper"],
        "restart": ["From Throw In", "From Goal Kick"],
        "set_piece": ["From Corner", "From Free Kick", "Other"],
    }
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(raw))          # reordena las llaves
    cfg = Config.load(p)

    assert sorted(cfg["phases"].keys()) != cfg["phase_order"], "el dump no reordeno"

    phases = tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys()))
    space = StateSpace(nx=cfg["pitch"]["nx"], ny=cfg["pitch"]["ny"], phases=phases)
    assert space.phases == ("open", "transition", "restart", "set_piece")
    assert space.n_transient == space.n_zones * 4

    trans = build_transitions(normalize(synth_events(n_matches=25, seed=8).lazy()),
                              space, cfg.raw)
    assert trans["from_state"].max() < space.n_transient
    assert set(trans["phase"].unique()) <= set(space.phases)
    assert "restart" in set(trans["phase"].unique())


def test_unknown_phase_in_config_is_rejected():
    from dtdecoder.ingest import normalize
    from dtdecoder.synth import synth_events

    cfg = Config.load()
    raw = dict(cfg.raw)
    raw["phases"] = {"open": ["Regular Play"], "fase_inventada": ["From Corner"]}
    space = StateSpace(nx=3, ny=3, phases=("open", "transition"))
    with pytest.raises(ValueError, match="no estan en el"):
        build_transitions(normalize(synth_events(n_matches=5, seed=2).lazy()), space, raw)


def test_short_carries_are_filtered():
    """El filtro debe reducir auto-transiciones sin tocar pases."""
    from dtdecoder.ingest import normalize
    from dtdecoder.synth import synth_events

    cfg = Config.load()
    space = StateSpace(nx=cfg["pitch"]["nx"], ny=cfg["pitch"]["ny"],
                       phases=tuple(cfg.get("phase_order") or sorted(cfg["phases"].keys())))
    ev = synth_events(n_matches=30, seed=6).lazy()

    raw_off = dict(cfg.raw)
    raw_off["possession"] = {**cfg.raw["possession"], "min_carry_length": 0.0}
    raw_on = dict(cfg.raw)
    raw_on["possession"] = {**cfg.raw["possession"], "min_carry_length": 8.0}

    t_off = build_transitions(normalize(ev), space, raw_off)
    t_on = build_transitions(normalize(ev), space, raw_on)
    assert t_on.height < t_off.height

    def selfloops(t):
        return t.filter(pl.col("from_state") == pl.col("to_state")).height / t.height

    assert selfloops(t_on) <= selfloops(t_off) + 1e-9
