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
    trans: pl.DataFrame, mc: pl.DataFrame, club: str | None = None
) -> pl.DataFrame:
    """Anade `coach` a las transiciones del club; los rivales quedan en null.

    El null es deliberado y significativo: identifica las filas que sirven como
    linea base externa sin contaminarse con eras del propio club.

    Con `club=None` el mapeo se hace por `(match_id, club)` usando la columna
    `club` de `mc`, que es lo que necesita un artefacto de LIGA: ahi cada
    partido tiene dos entrenadores y "el club" no existe. El resultado en un
    artefacto de un solo club es EXACTAMENTE el mismo por las dos vias, y
    `tests/test_coach_faced.py` lo comprueba.
    """
    if club is not None:
        mc1 = mc.select("match_id", "coach", "match_date")
        out = trans.join(mc1, on="match_id", how="left")
        return out.with_columns(
            pl.when(pl.col("team") == club)
            .then(pl.col("coach"))
            .otherwise(None)
            .alias("coach")
        )

    if "club" not in mc.columns:
        raise KeyError(
            "attach_coach(club=None) necesita la columna `club` en la tabla de "
            "eras: es la que dice a QUE equipo dirigia cada DT."
        )
    mc1 = mc.select(
        "match_id", pl.col("club").alias("team"), "coach", "match_date"
    )
    # `match_date` es por partido, no por equipo: se pega aparte para que un
    # partido cuyo club no tiene era no pierda la fecha.
    fechas = mc.select("match_id", "match_date").unique(subset=["match_id"])
    out = trans.join(mc1.drop("match_date"), on=["match_id", "team"], how="left")
    return out.join(fechas, on="match_id", how="left")


def attach_coach_faced(trans: pl.DataFrame, mc: pl.DataFrame) -> pl.DataFrame:
    """Anade `coach_faced`: el DT del equipo que NO ejecuta la accion.

    `coach`        responde "quien dirigia al EJECUTANTE?"
    `coach_faced`  responde "contra que DT se jugo esta accion?"

    Son dos preguntas distintas y necesitan dos columnas. Colapsarlas hacia que
    `select_units(unit='coach')` devolviera VACIO sobre transiciones defensivas,
    con un ValueError que decia "Sin transiciones para coach='Andre Jardine'" y
    apuntaba al lugar equivocado.

    CAMBIO DE DEFINICION (2026-09-14)
    ---------------------------------
    La version anterior asignaba "el DT del club focal" a TODAS las filas del
    partido, incluidas las del propio club. Sobre un artefacto de un solo club
    eso hacia que en las filas del club `coach_faced == coach`, que es una
    tautologia con un nombre que promete otra cosa.

    Sobre un artefacto de LIGA la definicion vieja ni siquiera esta definida:
    cada partido tiene dos entrenadores y ninguno es "el del club".

    La definicion nueva es la general y se calcula de la MISMA forma en los dos
    casos: se identifica el equipo rival dentro del propio partido y se busca su
    DT. Consecuencias, y hay que verificarlas, no suponerlas:

      * filas de RIVALES (team != club): el rival es el club, asi que
        `coach_faced` = DT del club. IDENTICO a antes. La cadena conjugada y
        todo el bloque D1 leen solo estas filas.
      * filas del CLUB: antes = DT del club (redundante con `coach`); ahora =
        DT del rival, que en un artefacto de un solo club es NULL porque no se
        cargaron las eras de los 17 rivales.

    El rival se deriva de `trans`, no de `mc`: asi funciona aunque solo se
    conozcan las eras de un club.
    """
    if "team" not in trans.columns:
        raise KeyError("attach_coach_faced necesita la columna `team`")

    equipos = trans.select("match_id", "team").unique()
    # (match_id, team) -> equipo rival en ese mismo partido
    rivales = (
        equipos.join(equipos, on="match_id", suffix="_rival")
        .filter(pl.col("team") != pl.col("team_rival"))
        .select("match_id", "team", "team_rival")
        .unique(subset=["match_id", "team"])
    )
    mc_t = mc.select(
        "match_id",
        pl.col("club").alias("team_rival") if "club" in mc.columns
        else pl.col("team").alias("team_rival"),
        pl.col("coach").alias("coach_faced"),
    )
    puente = rivales.join(mc_t, on=["match_id", "team_rival"], how="left").select(
        "match_id", "team", "coach_faced"
    )
    return trans.join(puente, on=["match_id", "team"], how="left")


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
    elif baseline == "other_coaches_same_club":
        # Igual que `other_coaches`, pero restringido al club focal.
        #
        # POR QUE HACE FALTA UNA ETIQUETA PROPIA
        # --------------------------------------
        # Sobre un artefacto de un solo club, `other_coaches` YA significa
        # "otras eras del mismo club", porque `coach` es null fuera del club.
        # Sobre un artefacto de liga significa "todos los demas entrenadores de
        # la liga", que es un contraste distinto y que NO es el diseno fuerte de
        # ADR-16: comparar dentro del mismo club es lo que controla plantel,
        # presupuesto, cantera, estadio y calendario.
        #
        # El cambio de significado seria SILENCIOSO. Por eso existe esta
        # etiqueta: sobre un artefacto de un club da exactamente lo mismo que
        # `other_coaches` -- lo comprueba tests/test_baseline_same_club.py --
        # y sobre uno de liga dice lo que uno queria decir.
        if club is None:
            raise ValueError("baseline='other_coaches_same_club' requiere --club")
        coach_col = unit if unit in ("coach", "coach_faced") else "coach"
        mismo_club = (
            (pl.col("team") != club) if unit == "coach_faced"
            else (pl.col("team") == club)
        )
        base = trans.filter(
            pl.col(coach_col).is_not_null()
            & (pl.col(coach_col) != value)
            & mismo_club
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


def _slug_club(nombre: str) -> str:
    """Misma normalizacion que usa `scripts/01_construir_eras.py` al nombrar."""
    import unicodedata

    s = "".join(
        c for c in unicodedata.normalize("NFD", nombre)
        if unicodedata.category(c) != "Mn"
    )
    return s.lower().replace(" ", "_")


def match_coach_table_multi(
    match_dates: pl.DataFrame, eras_dir: str | Path, equipos: list[str]
) -> pl.DataFrame:
    """(match_id, coach, match_date, club) para VARIOS clubes a la vez.

    Lee `coach_eras_<slug>.csv` de `eras_dir` y lo empareja contra los equipos
    presentes en los datos. El emparejamiento es por slug -- la normalizacion
    que usa el script que escribe esos archivos -- y NO por el nombre del
    archivo tal cual: `"Tigres UANL"` vive en `coach_eras_tigres_uanl.csv`.

    Un equipo sin archivo de eras NO es un error: sus filas quedan con `coach`
    nulo, que es exactamente lo que el prior necesita para no contaminarse.
    Se avisa, eso si, porque un club entero sin eras suele ser un archivo mal
    nombrado y no una decision.
    """
    d = Path(eras_dir)
    if not d.is_dir():
        raise NotADirectoryError(f"No es un directorio de eras: {d}")
    por_slug = {_slug_club(t): t for t in equipos}
    partes, sin_archivo = [], []
    for slug, equipo in sorted(por_slug.items()):
        f = d / f"coach_eras_{slug}.csv"
        if not f.exists():
            sin_archivo.append(equipo)
            continue
        partes.append(match_coach_table(match_dates, load_eras(f), equipo))
    if sin_archivo:
        print(
            f"  [aviso] {len(sin_archivo)} equipo(s) sin CSV de eras en {d}: "
            f"{sin_archivo}. Sus filas quedan con coach nulo."
        )
    if not partes:
        raise FileNotFoundError(f"Ningun coach_eras_*.csv utilizable en {d}")
    return pl.concat(partes, how="vertical")


# --------------------------------------------------------------------------
# Exclusion de partidos
# --------------------------------------------------------------------------
def load_exclusions(
    path: str | Path, club: str, solo_absorbidos: bool = True
) -> list[int]:
    """Partidos a EXCLUIR del artefacto de un club. Clave: (club, match_id).

    POR QUE LA CLAVE ES LA TUPLA Y NO EL `match_id`
    -----------------------------------------------
    El caso que la motiva: el 11 y el 17 de enero de 2025 al Club America lo
    dirigio Diego Cervantes, no Andre Jardine, pero esos dos partidos caen
    dentro del rango de la era de Jardine porque el fusionador de interinatos
    los absorbio (`scripts/01_construir_eras.py --dump-asignacion`).

    Hay que sacarlos del artefacto del America. Pero en esos mismos partidos el
    RIVAL tenia a su propio entrenador, legitimamente: borrar el `match_id` de
    forma global mutilaria la era del rival y quitaria del prior de liga un
    partido perfectamente bueno.

    El partido se cae del artefacto del club afectado y COMPLETO -- tambien las
    filas del rival, porque en ese partido esas posesiones se jugaron contra
    Cervantes y no contra Jardine, asi que su `coach_faced` tambien seria falso.

    `solo_absorbidos=True` usa unicamente las filas con `dirigio_la_era == 0`
    cuando esa columna existe, que es el formato que emite el dump.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo de exclusiones: {p}")
    df = pl.read_csv(p)
    for c in ("club", "match_id"):
        if c not in df.columns:
            raise KeyError(f"El CSV de exclusiones necesita la columna '{c}'")
    if solo_absorbidos and "dirigio_la_era" in df.columns:
        df = df.filter(pl.col("dirigio_la_era").cast(pl.Int64, strict=False) == 0)
    ids = (
        df.filter(pl.col("club") == club)["match_id"]
        .cast(pl.Int64, strict=False)
        .drop_nulls()
        .unique()
        .sort()
        .to_list()
    )
    return [int(x) for x in ids]


def check_dates_cover(trans: pl.DataFrame, match_dates: pl.DataFrame) -> None:
    """Invariante ASIMETRICO: todo partido con eventos debe tener fecha.

    Fechas de sobra son legales -- un `match_dates` de liga sirve para los 18
    clubes y va a traer miles de partidos que no estan en este parquet. Exigir
    igualdad de conjuntos seria un error logico.

    Lo que NO es legal es un partido sin fecha: el join de `attach_coach` es
    `left`, asi que ese partido saldria con `coach` nulo, indistinguible de un
    hueco real del CSV de eras. Es la clase de fallo que este proyecto lleva
    catorce casos documentando: no falla, miente.
    """
    con_eventos = set(trans["match_id"].unique().to_list())
    con_fecha = set(match_dates["match_id"].to_list())
    faltan = sorted(con_eventos - con_fecha)
    if faltan:
        raise ValueError(
            f"{len(faltan)} partidos tienen eventos pero NO tienen fecha en el "
            f"CSV de match_dates: {faltan[:10]}"
            + (" ..." if len(faltan) > 10 else "")
            + "\n  Sin fecha no hay mapeo de era y esos partidos saldrian con "
            "`coach` nulo,\n  indistinguible de un hueco real entre eras.\n"
            "  El CSV lo emite `scripts/02_adaptar_eventos.py` en la misma "
            "corrida que el parquet:\n  si no cuadran, uno de los dos es de "
            "otra corrida con otro alcance."
        )


# --------------------------------------------------------------------------
# Candado de verificacion de fronteras
# --------------------------------------------------------------------------
VERIFICADAS_COLUMNS = ["club", "coach", "n_esperado", "fuente", "fecha"]


def check_verificada(
    club: str | None,
    coach: str,
    eras_api: str | Path = "data/eras_api/eras_todas.csv",
    verificadas: str | Path = "data/eras_verificadas.csv",
) -> None:
    """Aborta si la era esta marcada PRIMERA_DE_VENTANA y nadie la verifico.

    POR QUE
    -------
    `01_construir_eras.py` marca la primera era de cada club en la ventana:
    es la unica frontera que ninguna evidencia interna puede confirmar, porque
    no hay un partido anterior contra el que contrastar el cambio de DT. Son 18
    marcadas, 9 de ellas analizables, y al cierre de esta sesion 3 estaban
    verificadas contra fuentes externas.

    El riesgo no es teorico: bug #14 fue exactamente una frontera de era mal
    puesta en un dato de entrada investigado a mano, y ningun test podia
    atraparlo porque el pipeline hacia lo que se le pidio.

    Este candado no verifica nada -- eso lo hace un humano con una fuente
    externa y aritmetica de conteo de partidos. Lo que hace es impedir que una
    frontera sin verificar llegue a un resultado reportado por descuido.

    INACTIVO si no existe `eras_api`: la demo con datos sinteticos, los tests y
    cualquier artefacto anterior a la migracion no tienen ese archivo y no
    deben romperse.
    """
    pe = Path(eras_api)
    if not pe.exists():
        return
    eras = pl.read_csv(pe)
    if "banderas" not in eras.columns:
        return
    fila = eras.filter(pl.col("coach") == coach)
    if club is not None and "club" in eras.columns:
        fila = fila.filter(pl.col("club") == club)
    if fila.height == 0:
        return
    banderas = str(fila["banderas"][0] or "")
    if "PRIMERA_DE_VENTANA" not in banderas:
        return

    pv = Path(verificadas)
    if pv.exists():
        ver = pl.read_csv(pv)
        if "coach" in ver.columns:
            hit = ver.filter(pl.col("coach") == coach)
            if club is not None and "club" in ver.columns:
                hit = hit.filter(pl.col("club") == club)
            if "fuente" in hit.columns:
                hit = hit.filter(
                    pl.col("fuente").is_not_null()
                    & (pl.col("fuente").cast(pl.Utf8).str.strip_chars() != "")
                )
            if hit.height > 0:
                return

    n = fila["n_partidos"][0] if "n_partidos" in fila.columns else "?"
    raise SystemExit(
        f"\n[CANDADO] La era '{coach}' ({club}) esta marcada PRIMERA_DE_VENTANA "
        f"y no esta verificada.\n"
        f"  Es la primera era del club en la ventana: si el API arrastro hacia "
        f"atras al DT\n"
        f"  siguiente, estos {n} partidos son de otro entrenador y el resultado "
        f"describiria\n"
        f"  a quien no es. Paso con Herrera/Solari (bug #14).\n\n"
        f"  Verificacion: contar los partidos de fase regular que una fuente "
        f"externa le da\n"
        f"  a este DT en la ventana y contrastarlos contra los {n} del API. La "
        f"aritmetica es\n"
        f"  mas dificil de falsear por accidente que una fecha.\n\n"
        f"  Cuando cuadre, anade una fila a {verificadas}:\n"
        f"      club,coach,n_esperado,fuente,fecha\n"
        f'      "{club}","{coach}",{n},"<url o referencia>","<AAAA-MM-DD>"\n'
    )


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
