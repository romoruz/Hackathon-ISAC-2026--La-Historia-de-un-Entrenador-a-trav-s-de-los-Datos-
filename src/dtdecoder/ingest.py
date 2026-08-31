"""
Fase 0.0 -- Ingesta y normalizacion de esquema.

Trabaja sobre el volcado plano del API de Hudl StatsBomb (el que tiene columnas
tipo `pass_end_location`, `obv_total_net`, `possession_team`, ...).

Decision de arquitectura: TODO es polars.LazyFrame hasta el ultimo momento.
Con 8 temporadas de Liga MX en una laptop de 32 GiB no puedes materializar el
dataset completo en memoria, pero SI puedes hacer el pipeline entero en lazy y
solo colapsar los conteos agregados, que son diminutos.

Paso obligatorio antes de cualquier analisis:
    dtdecoder convert --src data/raw --dst data/interim/events.parquet
CSV/JSON re-parsean strings en cada corrida; parquet particionado no.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

# Columnas minimas para las fases 0-3. Si tu extraccion no las trae, el
# pipeline falla temprano y con mensaje claro, en vez de dar numeros mal.
REQUIRED = [
    "id",
    "index",
    "match_id",
    "period",
    "minute",
    "second",
    "type",
    "team",
    "possession",
    "possession_team",
    "play_pattern",
    "location",
]

OPTIONAL = [
    "duration",
    "pass_end_location",
    "carry_end_location",
    "shot_end_location",
    "pass_outcome",
    "shot_outcome",
    "shot_statsbomb_xg",
    "under_pressure",
    "counterpress",
    "player",
    "player_id",
    "team_id",
    "possession_team_id",
    "obv_total_net",
    "obv_for_net",
    "obv_against_net",
]


# --------------------------------------------------------------------------
# Parsing de coordenadas
# --------------------------------------------------------------------------
def _split_xy(col: str, prefix: str) -> list[pl.Expr]:
    """Devuelve exprs que extraen x,y de una columna de localizacion.

    Soporta los dos formatos que salen del API segun como exportes:
      - lista nativa      : [60.0, 40.0]        (parquet / json -> pl.List)
      - string serializado: "[60.0, 40.0]"      (csv)
    Los remates traen un tercer componente (altura) que ignoramos aqui.
    """
    return [
        pl.col(col).alias(f"__{prefix}_raw"),
    ]


def parse_location(lf: pl.LazyFrame, col: str, prefix: str) -> pl.LazyFrame:
    """Agrega columnas {prefix}_x, {prefix}_y a partir de `col`."""
    schema = lf.collect_schema()
    if col not in schema.names():
        return lf.with_columns(
            pl.lit(None, dtype=pl.Float64).alias(f"{prefix}_x"),
            pl.lit(None, dtype=pl.Float64).alias(f"{prefix}_y"),
        )

    dtype = schema[col]
    if isinstance(dtype, pl.List):
        expr_x = pl.col(col).list.get(0, null_on_oob=True).cast(pl.Float64)
        expr_y = pl.col(col).list.get(1, null_on_oob=True).cast(pl.Float64)
    elif dtype == pl.String:
        cleaned = pl.col(col).str.strip_chars("[] ")
        parts = cleaned.str.split(",")
        expr_x = parts.list.get(0, null_on_oob=True).str.strip_chars().cast(
            pl.Float64, strict=False
        )
        expr_y = parts.list.get(1, null_on_oob=True).str.strip_chars().cast(
            pl.Float64, strict=False
        )
    else:  # ya viene desglosado o tipo raro
        expr_x = pl.lit(None, dtype=pl.Float64)
        expr_y = pl.lit(None, dtype=pl.Float64)

    return lf.with_columns(expr_x.alias(f"{prefix}_x"), expr_y.alias(f"{prefix}_y"))


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------
def _scan_csv(path) -> pl.LazyFrame:
    """CSV de StatsBomb: inferencia de esquema sobre el archivo COMPLETO.

    Por que no el default: en el volcado plano hay decenas de columnas que solo
    tienen valor en eventos raros (`shot_outcome`, `goalkeeper_type`,
    `foul_committed_card`...). Con el `infer_schema_length=100` por defecto,
    polars las tipa como `Null` y cualquier filtro sobre ellas revienta o
    devuelve vacio en silencio -- que es peor. Escanear el archivo entero cuesta
    una pasada extra una sola vez; despues se trabaja sobre parquet.
    """
    return pl.scan_csv(
        path,
        infer_schema_length=None,
        null_values=["", "NA", "N/A", "null", "None", "nan"],
        try_parse_dates=False,
        ignore_errors=False,
    )


def scan_events(src: str | Path) -> pl.LazyFrame:
    """Escanea parquet / csv / ndjson en lazy. Acepta archivo o directorio."""
    p = Path(src)
    if p.is_dir():
        for pattern, fn in (
            ("**/*.parquet", pl.scan_parquet),
            ("**/*.csv", _scan_csv),
            ("**/*.ndjson", pl.scan_ndjson),
            ("**/*.jsonl", pl.scan_ndjson),
        ):
            hits = sorted(p.glob(pattern))
            if hits:
                return fn(hits)
        raise FileNotFoundError(f"Sin archivos legibles en {p}")
    suffix = p.suffix.lower()
    if suffix == ".parquet":
        return pl.scan_parquet(p)
    if suffix == ".csv":
        return _scan_csv(p)
    if suffix in (".ndjson", ".jsonl"):
        return pl.scan_ndjson(p)
    raise ValueError(f"Extension no soportada: {suffix}")


def check_schema(lf: pl.LazyFrame) -> None:
    """Falla temprano y explicito si faltan columnas criticas."""
    have = set(lf.collect_schema().names())
    missing = [c for c in REQUIRED if c not in have]
    if missing:
        raise KeyError(
            "Faltan columnas requeridas: "
            + ", ".join(missing)
            + ". Revisa tu extraccion del API; sin ellas no se pueden construir "
            "cadenas de posesion."
        )


def normalize(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Selecciona columnas utiles, parsea coordenadas y ordena canonicamente."""
    check_schema(lf)
    have = set(lf.collect_schema().names())
    keep = REQUIRED + [c for c in OPTIONAL if c in have]
    lf = lf.select(keep)

    for col, prefix in (
        ("location", "start"),
        ("pass_end_location", "pass_end"),
        ("carry_end_location", "carry_end"),
        ("shot_end_location", "shot_end"),
    ):
        lf = parse_location(lf, col, prefix)

    lf = lf.drop([c for c in ("location", "pass_end_location", "carry_end_location",
                              "shot_end_location") if c in lf.collect_schema().names()])

    # Columnas categoricas totalmente vacias quedan tipadas como Null y cualquier
    # comparacion con string revienta. Se fuerzan a Utf8.
    schema = lf.collect_schema()
    null_cols = [
        c for c in ("pass_outcome", "shot_outcome", "play_pattern", "type", "team",
                    "possession_team", "player")
        if c in schema.names() and schema[c] == pl.Null
    ]
    if null_cols:
        lf = lf.with_columns([pl.col(c).cast(pl.Utf8) for c in null_cols])

    # `index` es el orden canonico del evento dentro del partido segun StatsBomb.
    return lf.sort(["match_id", "index"])


def load(src: str | Path) -> pl.LazyFrame:
    return normalize(scan_events(src))


def to_parquet(src: str | Path, dst: str | Path, partition_by: str | None = None) -> Path:
    """Convierte el volcado crudo a parquet normalizado (una sola vez)."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    lf = load(src)
    if partition_by:
        lf.collect(engine="streaming").write_parquet(
            dst, partition_by=partition_by, compression="zstd"
        )
    else:
        lf.sink_parquet(dst, compression="zstd")
    return dst
