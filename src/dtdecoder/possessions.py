"""
Fase 0.2/0.3 -- Cadenas de posesion y extraccion de transiciones.

DEFINICIONES OPERATIVAS (esto es lo que va en el reporte, palabra por palabra):

  Posesion  : grupo (match_id, possession) de StatsBomb, restringido a las
              acciones ejecutadas por `possession_team`.
  Accion    : evento cuyo `type` esta en config.possession.moving_types
              (Pass, Carry, Shot). Todo lo demas -- Ball Receipt, Pressure,
              Duel, Ball Recovery -- NO genera transicion.
  Transicion: cada accion aporta UNA transicion (zona_inicio, fase) -> destino,
              donde destino es (zona_fin, fase) si la accion mantiene la
              posesion, o un estado absorbente si la termina.
  Absorcion terminal: si la ultima accion de la posesion deja el balon en un
              estado transitorio, se anade una transicion extra hacia LOSS/OUT.
              SIN ESTO las filas de P no suman las tasas reales de perdida y
              la matriz fundamental N queda sesgada al alza.

Justificacion del diseno "una transicion por accion" (inicio -> fin) en vez de
encadenar fin_{k-1} -> inicio_k: es el criterio de Rudd (2011) / Singh (2018) y
evita que el arrastre del control (recepcion, toque previo) contamine las
transiciones con movimiento que el modelo no explica.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from .grid import StateSpace, phase_map

GOAL_TYPES = ("Own Goal For",)


# --------------------------------------------------------------------------
# Estado del marcador
# --------------------------------------------------------------------------
def add_score_state(
    lf: pl.LazyFrame, bins: list[float], labels: list[str], club: str | None = None
) -> pl.LazyFrame:
    """Anade `goal_diff` (desde la optica de possession_team) y `score_state`.

    El gol NO cuenta para su propio evento: se usa `shift(1)` sobre el acumulado
    para que el estado del marcador sea el que habia ANTES de la accion.
    Sin ese shift, cada gol se autoexplica y el analisis condicional al marcador
    -- que es el hallazgo central del proyecto -- queda contaminado.
    """
    lf = lf.with_columns(
        (
            ((pl.col("type") == "Shot") & (pl.col("shot_outcome") == "Goal"))
            | pl.col("type").is_in(GOAL_TYPES)
        ).alias("_is_goal")
    )

    # Referencia estable de "equipo A" dentro del partido (orden lexicografico).
    lf = lf.with_columns(pl.col("team").min().over("match_id").alias("_team_a"))
    lf = lf.with_columns(
        (pl.col("_is_goal") & (pl.col("team") == pl.col("_team_a"))).cast(pl.Int32).alias("_gA"),
        (pl.col("_is_goal") & (pl.col("team") != pl.col("_team_a"))).cast(pl.Int32).alias("_gB"),
    )
    lf = lf.with_columns(
        pl.col("_gA").cum_sum().over("match_id").shift(1, fill_value=0).over("match_id").alias("_cA"),
        pl.col("_gB").cum_sum().over("match_id").shift(1, fill_value=0).over("match_id").alias("_cB"),
    )
    lf = lf.with_columns(
        pl.when(pl.col("possession_team") == pl.col("_team_a"))
        .then(pl.col("_cA") - pl.col("_cB"))
        .otherwise(pl.col("_cB") - pl.col("_cA"))
        .alias("goal_diff")
    )
    lf = lf.with_columns(
        pl.when(pl.col("goal_diff") < 0)
        .then(pl.lit(labels[0]))
        .when(pl.col("goal_diff") == 0)
        .then(pl.lit(labels[1]))
        .otherwise(pl.lit(labels[2]))
        .alias("score_state")
    )
    # `score_state` esta referido a `possession_team`. En la cadena conjugada
    # el poseedor es el RIVAL, asi que "winning" significaria "el rival va
    # ganando" y TODO el analisis de contexto defensivo saldria con el signo
    # cambiado -- la frase resultante seria literalmente la contraria de la
    # verdad, y ningun test actual lo atraparia. Se emite SIEMPRE la version
    # referida al club para que ningun consumidor tenga que acordarse de
    # invertirla.
    if club is not None:
        lf = lf.with_columns(
            pl.when(pl.col("possession_team") == club)
            .then(pl.col("goal_diff"))
            .otherwise(-pl.col("goal_diff"))
            .alias("goal_diff_club")
        ).with_columns(
            pl.when(pl.col("goal_diff_club") < 0)
            .then(pl.lit(labels[0]))
            .when(pl.col("goal_diff_club") == 0)
            .then(pl.lit(labels[1]))
            .otherwise(pl.lit(labels[2]))
            .alias("score_state_club")
        )
    else:
        lf = lf.with_columns(
            pl.lit(None, dtype=pl.Int32).alias("goal_diff_club"),
            pl.lit(None, dtype=pl.Utf8).alias("score_state_club"),
        )

    return lf.drop(["_is_goal", "_team_a", "_gA", "_gB", "_cA", "_cB"])


# --------------------------------------------------------------------------
# Extraccion de acciones
# --------------------------------------------------------------------------
def extract_actions(lf: pl.LazyFrame, cfg: dict) -> pl.LazyFrame:
    """Filtra a acciones de la posesion y resuelve coordenadas de destino."""
    pcfg = cfg["possession"]
    moving = pcfg["moving_types"]
    loss_outcomes = pcfg["pass_loss_outcomes"]

    lf = lf.filter(
        (pl.col("possession_team") == pl.col("team")) & pl.col("type").is_in(moving)
    )

    # Coordenada final segun tipo de accion.
    end_x = (
        pl.when(pl.col("type") == "Pass")
        .then(pl.col("pass_end_x"))
        .when(pl.col("type") == "Carry")
        .then(pl.col("carry_end_x"))
        .otherwise(pl.col("shot_end_x"))
    )
    end_y = (
        pl.when(pl.col("type") == "Pass")
        .then(pl.col("pass_end_y"))
        .when(pl.col("type") == "Carry")
        .then(pl.col("carry_end_y"))
        .otherwise(pl.col("shot_end_y"))
    )

    lf = lf.with_columns(end_x.alias("end_x"), end_y.alias("end_y"))

    # Clasificacion del desenlace de la accion.
    lf = lf.with_columns(
        pl.when(pl.col("type") == "Shot")
        .then(
            pl.when(pl.col("shot_outcome") == "Goal")
            .then(pl.lit("GOAL"))
            .otherwise(pl.lit("SHOT_NOGOAL"))
        )
        .when((pl.col("type") == "Pass") & (pl.col("pass_outcome") == "Out"))
        .then(pl.lit("OUT"))
        .when((pl.col("type") == "Pass") & pl.col("pass_outcome").is_in(loss_outcomes))
        .then(pl.lit("LOSS"))
        .otherwise(pl.lit(""))
        .alias("outcome_state")
    )

    # Sin coordenada de inicio no hay transicion posible.
    lf = lf.filter(pl.col("start_x").is_not_null() & pl.col("start_y").is_not_null())

    # Filtro de acarreos cortos. Ver config.possession.min_carry_length.
    min_carry = float(pcfg.get("min_carry_length", 0.0) or 0.0)
    if min_carry > 0:
        dist = (
            (pl.col("end_x") - pl.col("start_x")) ** 2
            + (pl.col("end_y") - pl.col("start_y")) ** 2
        ).sqrt()
        lf = lf.filter((pl.col("type") != "Carry") | (dist >= min_carry))

    # Marca de presion. `under_pressure` es una BANDERA, no un booleano:
    # StatsBomb escribe `true` u OMITE la llave, y polars la lee como null.
    # Medido sobre el volcado del America el 2026-08-24:
    #     114,552 true | 0 false | 468,963 null  (de 583,515 eventos)
    # Sin este fill_null, cualquier filtro por is_not_null() daria pi ~ 1 en
    # todas partes sin lanzar un solo error. Habria sido el bug #13.
    flag = (cfg.get("defense") or {}).get("pressure_flag", "under_pressure")
    if flag in lf.collect_schema().names():
        lf = lf.with_columns(
            pl.col(flag).fill_null(False).cast(pl.Boolean).alias("under_pressure")
        )
    else:
        lf = lf.with_columns(pl.lit(False, dtype=pl.Boolean).alias("under_pressure"))
    return lf


# --------------------------------------------------------------------------
# Construccion de transiciones
# --------------------------------------------------------------------------
def build_transitions(
    lf: pl.LazyFrame,
    space: StateSpace,
    cfg: dict,
    team: str | None = None,
    club: str | None = None,
) -> pl.DataFrame:
    """El artefacto contiene las posesiones de TODOS los equipos del archivo.

    `club` NO filtra nada. `transitions.parquet` sigue siendo un solo artefacto
    con los 18 equipos, y de ahi salen las DOS perspectivas:
      - ofensiva  : posesiones del club          (team == club)
      - conjugada : posesiones de los rivales    (team != club)
    La perspectiva se elige al ANALIZAR (phase1/2/3 --perspective), no al
    construir. Dos parquets paralelos serian estado compartido que hay que
    mantener sincronizado, y ese es el patron del bug #7.

    `club` sirve solo para tres cosas que dependen de saber cual es el foco:
      1. `score_state_club` -- el marcador referido al club, no al poseedor;
      2. `min_actions` asimetrico (ver `_filter_short_asimetrico`);
      3. nada mas.
    """
    """Devuelve la tabla de transiciones lista para conteo.

    Columnas de salida:
        poss_uid   : identificador unico de posesion (unidad del block bootstrap)
        match_id, team, phase, score_state
        from_state : indice de estado transitorio
        to_state   : indice de estado global (transitorio o absorbente)
        is_absorbing
    """
    ctx = cfg["context"]
    lf = add_score_state(lf, ctx["score_bins"], ctx["score_labels"], club=club)
    if team is not None:
        lf = lf.filter(pl.col("possession_team") == team)

    lf = extract_actions(lf, cfg)
    df = lf.collect()
    if df.height == 0:
        return _empty_transitions()

    # `player_id` es obligatorio desde v0.5.1: sin el no se puede separar el
    # efecto del entrenador del efecto del plantel (05_VALIDATION §4.1).
    #
    # La primera version de este parche hacia
    #     "player_id": df["player_id"] if "player_id" in df.columns else None
    # y eso TAPO el fallo: `phase0` corrio limpio, escribio un parquet sin la
    # columna, y el error solo aparecio dos comandos despues. Es exactamente el
    # patron de bug silencioso que este proyecto lleva ocho casos combatiendo.
    # Aqui se falla temprano y con el remedio en el mensaje.
    faltan = [c for c in ("player_id", "player") if c not in df.columns]
    if faltan:
        raise KeyError(
            f"Faltan columnas de jugador en los eventos: {faltan}.\n"
            "  Estan declaradas en ingest.OPTIONAL y deberian sobrevivir a "
            "`normalize`.\n"
            "  Verifica que el volcado del API las incluya:\n"
            "    python -c \"from dtdecoder import ingest; "
            "print([c for c in ingest.load('TU.csv').collect_schema().names() "
            "if 'player' in c])\""
        )

    pmap = phase_map(cfg["phases"])
    default_phase = cfg.get("phase_default", space.phases[0])
    if default_phase not in space.phases:
        raise ValueError(f"phase_default='{default_phase}' no esta en {list(space.phases)}")
    unknown = set(pmap.values()) - set(space.phases)
    if unknown:
        raise ValueError(
            f"config.phases define fases {sorted(unknown)} que no estan en el "
            f"espacio de estados {list(space.phases)}. Deben coincidir."
        )

    df = df.with_columns(
        pl.col("play_pattern")
        .replace_strict(pmap, default=default_phase)
        .alias("phase"),
        (
            pl.col("match_id").cast(pl.Utf8)
            + "_"
            + pl.col("possession").cast(pl.Utf8)
        ).alias("poss_uid"),
    )

    # --- indices numericos ------------------------------------------------
    phase_idx = np.array([space.phases.index(p) for p in df["phase"].to_list()])
    z_from = space.zone_of(df["start_x"].to_numpy(), df["start_y"].to_numpy())
    s_from = space.transient_index(z_from, phase_idx)

    end_x = df["end_x"].fill_null(np.nan).to_numpy()
    end_y = df["end_y"].fill_null(np.nan).to_numpy()
    has_end = np.isfinite(end_x) & np.isfinite(end_y)
    z_to = np.where(has_end, space.zone_of(np.nan_to_num(end_x), np.nan_to_num(end_y)), -1)
    s_to_transient = np.where(z_to >= 0, space.transient_index(z_to, phase_idx), -1)

    outcome = df["outcome_state"].to_list()
    s_to = np.empty(len(outcome), dtype=int)
    for k, oc in enumerate(outcome):
        if oc:
            s_to[k] = space.absorbing_index(oc)
        elif s_to_transient[k] >= 0:
            s_to[k] = s_to_transient[k]
        else:
            # accion sin destino resoluble (carry truncado) -> se pierde el rastro
            s_to[k] = space.absorbing_index("LOSS")

    trans = pl.DataFrame(
        {
            "poss_uid": df["poss_uid"],
            "match_id": df["match_id"],
            "team": df["team"],
            "event_index": df["index"],
            "phase": df["phase"],
            "score_state": df["score_state"],
            # `score_state` esta referido a `possession_team`. En la cadena
            # conjugada el poseedor es el RIVAL, asi que 'winning' ahi
            # significaria que el rival va ganando. `score_state_club`
            # siempre se lee desde el club focal. Es la columna que hay que
            # usar para el analisis de contexto, en las dos perspectivas.
            "score_state_club": df["score_state_club"],
            # Tipo de accion que genero la transicion. Necesario para
            # diagnosticar las auto-transiciones i -> i: sin esto no se puede
            # distinguir si vienen de acarreos cortos (que min_carry_length
            # filtra) o de pases cortos dentro de zona (que NO filtra ningun
            # umbral de acarreo). El valor "TERMINAL" marca la transicion
            # artificial de absorcion.
            "action_type": df["type"],
            # Ejecutante de la accion. Necesario para separar el efecto del
            # ENTRENADOR del efecto del PLANTEL: sin esto, "Jardine circula
            # mas que Solari" es indistinguible de "Jardine tuvo otros
            # jugadores". Es la amenaza 4.1 de 05_VALIDATION, la mas seria que
            # queda viva. Con player_id se puede medir el solapamiento entre
            # eras y, sobre todo, comparar a un MISMO jugador bajo dos DT.
            # cast a Int64: el CSV lo trae como Float64 por los nulos (eventos
            # de equipo como alineaciones), y la fila de absorcion terminal se
            # declara Int64. Sin este cast, `pl.concat` falla con SchemaError.
            "player_id": df["player_id"].cast(pl.Int64, strict=False),
            "player": df["player"].cast(pl.Utf8, strict=False),
            # Marca de presion sobre la accion. En la cadena conjugada estas
            # son acciones del RIVAL, asi que la media por zona es
            # pi(z) = P(el rival juega presionado | zona), el objeto central
            # de D1. Es un ADELGAZAMIENTO del proceso rival, no un proceso
            # propio: por eso el denominador es la exposicion.
            "under_pressure": df["under_pressure"],
            "from_state": s_from,
            "to_state": s_to,
        }
    ).with_columns((pl.col("to_state") >= space.n_transient).alias("is_absorbing"))

    trans = _append_terminal_absorption(trans, space, cfg)
    return _filter_short_asimetrico(trans, cfg, club)


def _append_terminal_absorption(
    trans: pl.DataFrame, space: StateSpace, cfg: dict
) -> pl.DataFrame:
    """Anade la transicion final -> LOSS cuando la posesion muere en transitorio.

    Sin este paso, `P` sobreestima la permanencia: las posesiones que
    simplemente terminan (falta, cambio, fin de periodo, robo sin evento del
    equipo) nunca absorberian y N = (I-Q)^-1 explotaria hacia arriba.
    """
    trans = trans.sort(["poss_uid", "event_index"])
    last = trans.group_by("poss_uid", maintain_order=True).last()
    tail = last.filter(~pl.col("is_absorbing"))
    if tail.height == 0:
        return trans

    extra = tail.with_columns(
        pl.col("to_state").alias("from_state"),
        pl.lit("TERMINAL").alias("action_type"),
        pl.lit(None, dtype=pl.Int64).alias("player_id"),
        pl.lit(None, dtype=pl.Utf8).alias("player"),
        # NULL, no False: la absorcion terminal es artificial y no
        # corresponde a ningun evento, asi que no tiene marca de presion.
        # Ponerla en False diluiria pi(z), y mas en las eras con mas
        # absorciones terminales: sesgo diferencial. Al estimar pi hay que
        # filtrar action_type != "TERMINAL".
        pl.lit(None, dtype=pl.Boolean).alias("under_pressure"),
        pl.lit(space.absorbing_index("LOSS")).cast(pl.Int64).alias("to_state"),
        (pl.col("event_index") + 1).alias("event_index"),
        pl.lit(True).alias("is_absorbing"),
    ).select(trans.columns)

    return pl.concat([trans, extra]).sort(["poss_uid", "event_index"])


def _filter_short(trans: pl.DataFrame, min_actions: int) -> pl.DataFrame:
    """Descarta posesiones cortas.

    OJO: cuenta filas DESPUES de anadir la absorcion terminal, asi que
    `min_actions = 2` conserva posesiones de UNA sola accion real mas la
    transicion artificial. Es deliberado -- esa accion unica sigue siendo
    informacion -- pero hay que decirlo: `min_actions` no es "acciones reales
    minimas". Afecta la lectura del truncamiento en la bondad de ajuste.
    """
    counts = trans.group_by("poss_uid").len().rename({"len": "n_actions"})
    keep = counts.filter(pl.col("n_actions") >= min_actions).select("poss_uid")
    return trans.join(keep, on="poss_uid", how="inner")


def _filter_short_asimetrico(
    trans: pl.DataFrame, cfg: dict, club: str | None
) -> pl.DataFrame:
    """`min_actions` distinto para las posesiones del club y las del rival.

    POR QUE ASIMETRICO
    ------------------
    Una posesion de UNA accion que termina en absorcion no recibe absorcion
    terminal, se queda con una fila, y `min_actions = 2` la descarta.

    En la cadena OFENSIVA eso ya se conocia y esta contabilizado en el analisis
    de bondad de ajuste (03_METHODS §7.1: P(T<2) = 0 por construccion, y por eso
    la phase-type se compara CONDICIONADA). Cambiarlo invalidaria resultados ya
    validados, asi que la perspectiva ofensiva NO se toca.

    En la cadena CONJUGADA es distinto: una posesion rival de una accion es
    justo el producto de una presion exitosa. Medido el 2026-08-24 sobre 18,214
    posesiones rivales del America:

        descarte global .......... 9.06%
        frente a Solari .......... 10.49%
        frente a Ortiz ........... 10.41%
        frente a Herrera ......... 10.24%
        frente a Jardine .......... 8.63%

    Rango 1.86 pp, o 22% relativo, y TODO el descarte cae en T = 1. Con
    E[T] ~ 5 el sesgo diferencial sobre E[T^def] es del orden de 0.09 acciones:
    mismo orden que los efectos que se quieren detectar. Es el bug #11 en otra
    forma -- un filtro que selecciona por la variable medida.

    LA ASIMETRIA HAY QUE DECLARARLA
    -------------------------------
    E[T^att] y E[T^def] quedan truncados a distinto nivel y NO son comparables
    entre si sin decirlo. La comparacion valida es era contra era DENTRO de la
    misma perspectiva. Para el contraste cruzado, correr tambien la conjugada
    con min_actions = 2 como sensibilidad y reportar ambas.
    """
    pcfg = cfg["possession"]
    ma_att = int(pcfg["min_actions"])
    ma_def = int(pcfg.get("min_actions_defense", ma_att))
    if club is None or ma_att == ma_def:
        return _filter_short(trans, ma_att)

    # `team` == `possession_team` por construccion: `extract_actions` filtra la
    # igualdad. Por eso basta mirar `team` para saber de quien es la posesion.
    counts = trans.group_by("poss_uid").agg(
        pl.len().alias("n_actions"),
        (pl.col("team").first() == club).alias("es_club"),
    )
    keep = counts.filter(
        pl.when(pl.col("es_club"))
        .then(pl.col("n_actions") >= ma_att)
        .otherwise(pl.col("n_actions") >= ma_def)
    ).select("poss_uid")
    return trans.join(keep, on="poss_uid", how="inner")


def _empty_transitions() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "poss_uid": pl.Utf8,
            "match_id": pl.Int64,
            "team": pl.Utf8,
            "event_index": pl.Int64,
            "phase": pl.Utf8,
            "score_state": pl.Utf8,
            "action_type": pl.Utf8,
            "player_id": pl.Int64,
            "player": pl.Utf8,
            "under_pressure": pl.Boolean,
            "score_state_club": pl.Utf8,
            "from_state": pl.Int64,
            "to_state": pl.Int64,
            "is_absorbing": pl.Boolean,
        }
    )


# --------------------------------------------------------------------------
# Sanidad de coordenadas
# --------------------------------------------------------------------------
def coordinate_sanity(trans: pl.DataFrame, space: StateSpace) -> dict[str, float]:
    """Chequeo de que las coordenadas estan en el marco de ataque correcto.

    Si StatsBomb esta normalizado (equipo ejecutor ataca hacia x=120), la
    probabilidad de gol debe CRECER con el indice de columna de zona. Si tu
    extraccion no lo esta, esta funcion lo detecta y hay que activar
    `possession.flip_defensive` (o voltear en la ingesta).
    """
    goal = space.absorbing_index("GOAL")
    n_phases = len(space.phases)
    df = trans.with_columns(
        (pl.col("from_state") // n_phases // space.ny).alias("col_idx"),
        (pl.col("to_state") == goal).cast(pl.Float64).alias("is_goal"),
    )
    agg = df.group_by("col_idx").agg(pl.col("is_goal").mean()).sort("col_idx")
    cols = agg["col_idx"].to_numpy().astype(float)
    rates = agg["is_goal"].to_numpy()
    if len(cols) < 3:
        return {"corr": float("nan"), "ok": False}
    corr = float(np.corrcoef(cols, rates)[0, 1])
    return {"corr": corr, "ok": corr > 0.5}
