"""
Eras de entrenador: mapeo partido -> DT y diseno de comparacion.

EL DISENO QUE CAMBIA CON UN DATASET DE UN SOLO CLUB
---------------------------------------------------
Con eventos de un solo club no tienes "la liga" como referencia. Lo que tienes
es mejor para la pregunta del reto: puedes comparar DT contra DT DENTRO DEL
MISMO CLUB. Eso controla plantel, cantera, presupuesto, estadio, arbitraje y
calendario -- variables que una comparacion contra el promedio de liga deja
sueltas. La afirmacion "Jardine progresa por dentro un 8% mas que Solari en el
MISMO club" es mucho mas fuerte que "el America progresa por dentro mas que la
liga", porque en la segunda no sabes si es el DT o es el plantel.

Tres lineas base disponibles (`--baseline`):
  rest          : todo lo demas del archivo (incluye rivales). Util para
                  contextualizar contra el resto de la liga, con el sesgo de que
                  "el resto" son solo rivales del America.
  other_coaches : otras eras del MISMO club. ES EL DEFAULT y el diseno fuerte.
  opponents     : solo los rivales, excluyendo las demas eras del club.

REQUISITO: fechas de partido
----------------------------
El volcado de eventos NO trae fecha. Hay que traerla del endpoint de partidos
(ver scripts/fetch_match_dates.py). Sin fecha no hay forma confiable de asignar
eras: `match_id` no es un orden temporal garantizado entre competencias.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

ERA_COLUMNS = ["coach", "start_date", "end_date"]


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------
def load_eras(path: str | Path) -> pl.DataFrame:
    """Lee el CSV de eras y valida que no haya traslapes ni huecos raros."""
    df = pl.read_csv(path)
    missing = [c for c in ERA_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Al CSV de eras le faltan columnas: {missing}")
    df = df.with_columns(
        pl.col("start_date").str.to_date(),
        pl.col("end_date").str.to_date(),
    ).sort("start_date")

    if (df["end_date"] < df["start_date"]).any():
        raise ValueError("Hay eras con end_date anterior a start_date.")

    starts = df["start_date"].to_list()
    ends = df["end_date"].to_list()
    for k in range(1, len(starts)):
        if starts[k] <= ends[k - 1]:
            raise ValueError(
                f"Eras traslapadas: '{df['coach'][k - 1]}' termina {ends[k - 1]} "
                f"pero '{df['coach'][k]}' empieza {starts[k]}. Un partido no puede "
                "tener dos DT."
            )
    return df


def load_match_dates(path: str | Path) -> pl.DataFrame:
    """CSV con al menos (match_id, match_date)."""
    df = pl.read_csv(path)
    for c in ("match_id", "match_date"):
        if c not in df.columns:
            raise KeyError(f"El CSV de fechas necesita la columna '{c}'")
    return df.select(
        pl.col("match_id").cast(pl.Int64),
        pl.col("match_date").cast(pl.Utf8).str.head(10).str.to_date().alias("match_date"),
    ).unique(subset=["match_id"])


# --------------------------------------------------------------------------
# Asignacion
# --------------------------------------------------------------------------
def match_coach_table(
    match_dates: pl.DataFrame, eras: pl.DataFrame, club: str
) -> pl.DataFrame:
    """Devuelve (match_id, coach) para los partidos que caen dentro de una era."""
    md = match_dates.sort("match_date")
    er = eras.sort("start_date")
    # join_asof toma la era mas reciente cuyo inicio <= fecha del partido
    out = md.join_asof(er, left_on="match_date", right_on="start_date", strategy="backward")
    out = out.filter(pl.col("coach").is_not_null() & (pl.col("match_date") <= pl.col("end_date")))
    return out.select(
        pl.col("match_id"),
        pl.col("coach"),
        pl.col("match_date"),
        pl.lit(club).alias("club"),
    )


def attach_coach(
    trans: pl.DataFrame, mc: pl.DataFrame, club: str
) -> pl.DataFrame:
    """Anade `coach` a las transiciones del club; los rivales quedan en null.

    El null es deliberado y significativo: identifica las filas que sirven como
    linea base externa sin contaminarse con eras del propio club.
    """
    mc = mc.select("match_id", "coach", "match_date")
    out = trans.join(mc, on="match_id", how="left")
    return out.with_columns(
        pl.when(pl.col("team") == club).then(pl.col("coach")).otherwise(None).alias("coach")
    )


def attach_coach_faced(trans: pl.DataFrame, mc: pl.DataFrame) -> pl.DataFrame:
    """Anade `coach_faced`: el DT del club en ese partido, para TODAS las filas.

    `coach`        responde "quien dirigia al EJECUTANTE?" -> null en rivales.
    `coach_faced`  responde "contra que DT se jugo este partido?" -> aplica a
                   todas las filas del partido, incluidas las del rival.

    Son dos preguntas distintas y necesitan dos columnas. Colapsarlas hacia que
    `select_units(unit='coach')` devolviera VACIO sobre transiciones defensivas,
    con un ValueError que decia "Sin transiciones para coach='Andre Jardine'" y
    apuntaba al lugar equivocado.

    Contrato verificable: sobre las filas del club, `coach` y `coach_faced`
    deben coincidir exactamente. Lo comprueba tests/test_coach_faced.py.
    """
    mc = mc.select("match_id", pl.col("coach").alias("coach_faced"))
    return trans.join(mc, on="match_id", how="left")


def select_units(
    trans: pl.DataFrame, unit: str, value: str, baseline: str, club: str | None = None
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Devuelve (foco, linea_base) segun el diseno de comparacion elegido."""
    if unit not in trans.columns:
        raise KeyError(
            f"La columna '{unit}' no existe en transitions.parquet. "
            "Corre phase0 con --eras y --match-dates para generar `coach`."
        )
    focus = trans.filter(pl.col(unit) == value)
    if focus.height == 0:
        avail = trans[unit].drop_nulls().unique().to_list()
        raise ValueError(f"Sin transiciones para {unit}='{value}'. Disponibles: {avail}")

    if baseline == "rest":
        base = trans.filter((pl.col(unit) != value) | pl.col(unit).is_null())
    elif baseline == "other_coaches":
        # La columna de DT depende de la perspectiva: `coach` en la ofensiva,
        # `coach_faced` en la conjugada (donde `coach` es null en TODAS las
        # filas). Cablear "coach" aqui hacia que la linea base saliera vacia en
        # defensa, con un mensaje que no decia por que.
        # Para unit='team' se conserva `coach`: comportamiento historico intacto.
        coach_col = unit if unit in ("coach", "coach_faced") else "coach"
        base = trans.filter(
            pl.col(coach_col).is_not_null() & (pl.col(coach_col) != value)
        )
    elif baseline == "opponents":
        if club is None:
            raise ValueError("baseline='opponents' requiere --club")
        if unit == "coach_faced":
            raise ValueError(
                "baseline='opponents' no tiene sentido en perspectiva defensiva: "
                "TODAS las filas son de rivales, asi que la linea base contendria "
                "al foco. Es fuga de prior (ADR-06). Usa --baseline other_coaches."
            )
        base = trans.filter(pl.col("team") != club)
    else:
        raise ValueError(f"baseline desconocido: {baseline}")

    if base.height == 0:
        raise ValueError(f"La linea base '{baseline}' quedo vacia.")
    return focus, base


# --------------------------------------------------------------------------
# Diagnostico de cobertura
# --------------------------------------------------------------------------
def coverage_report(trans: pl.DataFrame, club: str) -> pl.DataFrame:
    """Tamano de muestra por era. LEELO ANTES DE MODELAR NADA.

    Regla practica: con menos de ~25 partidos por era, la Fase 3 no va a
    distinguir nada y la estratificacion por marcador es inviable.
    """
    club_rows = trans.filter(pl.col("team") == club)
    total_matches = club_rows["match_id"].n_unique()
    out = (
        club_rows.group_by("coach")
        .agg(
            pl.col("match_id").n_unique().alias("matches"),
            pl.col("poss_uid").n_unique().alias("possessions"),
            pl.len().alias("transitions"),
        )
        .sort("matches", descending=True)
        .with_columns(
            (pl.col("matches") / total_matches * 100).round(1).alias("pct_matches"),
            (pl.col("matches") >= 25).alias("suficiente"),
        )
    )
    return out


def unmapped_matches(trans: pl.DataFrame, club: str) -> pl.DataFrame:
    """Partidos del club que ninguna era cubre: huecos del CSV de eras."""
    return (
        trans.filter((pl.col("team") == club) & pl.col("coach").is_null())
        .group_by("match_id")
        .agg(pl.col("match_date").first())
        .sort("match_date")
    )


# --------------------------------------------------------------------------
# Verificacion empirica de las fronteras de era
# --------------------------------------------------------------------------
def detect_regime_changes(
    trans: pl.DataFrame, space, club: str, window: int = 8
) -> pl.DataFrame:
    """Quiebres estructurales en la matriz de transicion, partido a partido.

    NO sustituye al mapeo real: sirve para VERIFICARLO. Si tus fronteras de era
    (sacadas de Wikipedia) coinciden con los picos de esta serie, tienes
    evidencia independiente de que las fechas estan bien. Si no coinciden,
    alguna fecha esta mal y hay que revisarla.

    Distancia: variacion total entre las matrices de dos ventanas contiguas de
    `window` partidos, ponderada por masa de transiciones.
    """
    from .estimate import count_matrix

    sub = trans.filter(pl.col("team") == club)
    order_col = "match_date" if "match_date" in sub.columns else "match_id"
    matches = (
        sub.group_by("match_id").agg(pl.col(order_col).first()).sort(order_col)["match_id"].to_list()
    )
    rows = []
    for k in range(window, len(matches) - window + 1):
        left = sub.filter(pl.col("match_id").is_in(matches[k - window : k]))
        right = sub.filter(pl.col("match_id").is_in(matches[k : k + window]))
        Cl, Cr = count_matrix(left, space), count_matrix(right, space)
        Pl_, Pr_ = _row_normalize(Cl), _row_normalize(Cr)
        w = Cl.sum(axis=1) + Cr.sum(axis=1)
        w = w / max(w.sum(), 1e-12)
        tv = 0.5 * np.abs(Pl_ - Pr_).sum(axis=1)
        rec = {"split_at_match_id": matches[k], "tv_weighted": float((tv * w).sum())}
        if "match_date" in sub.columns:
            d = sub.filter(pl.col("match_id") == matches[k])["match_date"].first()
            rec["split_date"] = d
        rows.append(rec)
    if not rows:
        return pl.DataFrame(schema={"split_at_match_id": pl.Int64, "tv_weighted": pl.Float64})
    return pl.DataFrame(rows)


def _row_normalize(C: np.ndarray) -> np.ndarray:
    s = C.sum(axis=1, keepdims=True)
    return np.where(s > 0, C / np.maximum(s, 1e-12), 1.0 / C.shape[1])


# --------------------------------------------------------------------------
# Plantilla
# --------------------------------------------------------------------------
AMERICA_ERAS = [
    # FECHAS APROXIMADAS derivadas de la tabla de Wikipedia (solo anos).
    # VERIFICALAS con detect_regime_changes y con la ficha de cada partido
    # antes de reportar nada. Las fronteras mal puestas mezclan dos DT en una
    # misma era y diluyen justo el efecto que quieres medir.
    ("Miguel Herrera", "2017-01-01", "2021-12-05"),
    ("Gilberto Adame", "2021-12-06", "2021-12-14"),
    ("Santiago Solari", "2021-12-15", "2022-10-09"),
    ("Fernando Ortiz", "2022-10-10", "2023-05-31"),
    ("Andre Jardine", "2023-06-01", "2026-12-31"),
]


def write_template(path: str | Path, eras: list[tuple[str, str, str]] | None = None) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = eras if eras is not None else AMERICA_ERAS
    pl.DataFrame(
        {
            "coach": [r[0] for r in rows],
            "start_date": [r[1] for r in rows],
            "end_date": [r[2] for r in rows],
        }
    ).write_csv(p)
    return p
